"""Request fields and response parsing for ordinary Chat Completions."""

import json
import re
from typing import Literal

from pydantic import BaseModel, model_validator


class ThinkingControl(BaseModel):
    request_format: Literal[
        "enable_thinking", "template-enable", "template-thinking",
        "thinking-type", "reasoning-enabled", "reasoning-effort",
    ]
    actions: Literal["both", "on", "off"] = "both"
    enable_effort: Literal["minimal", "low", "medium", "high", "xhigh", "max"] | None = None

    @model_validator(mode="after")
    def validate_effort(self):
        if self.request_format == "reasoning-effort" and self.actions != "off" and not self.enable_effort:
            raise ValueError("Select the model's supported effort for enabling thinking")
        return self

    def fields(self, mode: str) -> dict:
        if self.actions not in ("both", mode):
            raise ValueError("This model connection does not support the selected thinking mode")
        enabled = mode == "on"
        match self.request_format:
            case "enable_thinking":
                return {"enable_thinking": enabled}
            case "template-enable":
                return {"chat_template_kwargs": {"enable_thinking": enabled}}
            case "template-thinking":
                return {"chat_template_kwargs": {"thinking": enabled}}
            case "thinking-type":
                return {"thinking": {"type": "enabled" if enabled else "disabled"}}
            case "reasoning-enabled":
                return {"reasoning": {"enabled": enabled}}
            case "reasoning-effort":
                return {"reasoning_effort": self.enable_effort if enabled else "none"}


class CompletionError(Exception):
    """An upstream request or response failed."""


def error_message(body, fallback: str) -> str:
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        message = error.get("message")
        code = error.get("code") or error.get("type")
        if isinstance(message, str) and message:
            message = re.sub(r"https?://[^\s<>]+", "[URL]", message)
            message = re.sub(r"(?i)Bearer\s+[^\s,;]+", "Bearer [redacted]", message)
            return f"{code}: {message[:400]}" if isinstance(code, (str, int)) else message[:400]
    return fallback


def completion_choice(body: dict, *, streamed: bool) -> dict:
    if not isinstance(body, dict):
        raise CompletionError("Invalid upstream completion response")
    if body.get("error"):
        raise CompletionError(error_message(body, "Upstream model returned an error"))
    choices = body.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        return choices[0]
    if streamed and choices in (None, []):
        return {}
    raise CompletionError("Upstream completion response has no choices")


def content_text(value, *, separator: str = "") -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return separator.join(part["text"] for part in value
                       if isinstance(part, dict) and isinstance(part.get("text"), str))
    return ""


def reasoning_text(message: dict) -> str:
    for name in ("reasoning_content", "reasoning", "thinking"):
        value = message.get(name)
        if isinstance(value, str) and value:
            return value
    details = message.get("reasoning_details")
    if isinstance(details, list):
        return "".join(content_text(item.get("summary") if item.get("type") == "reasoning.summary"
                                    else item.get("text")) for item in details
                       if isinstance(item, dict) and item.get("type") in ("reasoning.summary", "reasoning.text"))
    return ""


def completion_problem(reason: str | None, content: str) -> str | None:
    if reason == "length":
        return "Output limit reached" if content.strip() else "Output limit reached before an answer was generated"
    if reason == "content_filter":
        return "The upstream provider filtered this response"
    if reason in ("tool_calls", "function_call"):
        return "The upstream model requested a tool in ordinary chat"
    if reason == "error":
        return "Upstream model returned an error"
    if not content.strip():
        return "The upstream model returned no answer"
    return None


async def stream_choices(response):
    buffer = bytearray()
    scan_from = 0
    saw_finish = False
    async for chunk in response.content.iter_any():
        buffer.extend(chunk)
        start = 0
        while (end := buffer.find(b"\n", scan_from)) != -1:
            line = buffer[start:end].decode("utf-8").strip()
            start = scan_from = end + 1
            if not line.startswith("data:"):
                continue
            data = line[5:].lstrip()
            if data == "[DONE]":
                return
            if data:
                try:
                    body = json.loads(data)
                except json.JSONDecodeError as exc:
                    raise CompletionError("Invalid upstream streaming event") from exc
                choice = completion_choice(body, streamed=True)
                saw_finish |= bool(choice.get("finish_reason"))
                yield choice
        del buffer[:start]
        scan_from = len(buffer)
    if buffer:
        buffer.decode("utf-8")
    if not saw_finish:
        raise CompletionError("The upstream response ended before completion")
