"""Claude Code adapter backed by Anthropic's Python Agent SDK."""

from __future__ import annotations

import asyncio
import base64
import os
import re
from contextlib import aclosing
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from .base import (
    AdapterConfig,
    AdapterError,
    AgentAdapter,
    Capabilities,
    CompactRequest,
    Emit,
    InteractionReply,
    ProbeResult,
    RunRequest,
    RunResult,
    SessionBinding,
    UnsupportedCapability,
)


_EFFORTS = ("low", "medium", "high", "xhigh", "max")
_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_MAX_IMAGES = 4
_STOP_TIMEOUT = 30
_STOP_RPC_TIMEOUT = 5


def _load_sdk():
    try:
        import claude_agent_sdk
    except ImportError:
        raise AdapterError(
            "claude_sdk_missing",
            "Install the Claude Agent SDK in the Runner environment.",
        ) from None
    return claude_agent_sdk


def _api_key_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def _read_image(path: Path) -> bytes:
    with path.open("rb") as image:
        return image.read(_MAX_IMAGE_BYTES + 1)


def _safe_preview(value: str) -> str:
    value = re.sub(
        r"(?i)(\b(?:[\w-]*(?:token|secret|password|api[_-]?key)[\w-]*)"
        r'(?:\s*[:=]\s*|\s+)|\bBearer\s+)(?:"[^"]*"|\x27[^\x27]*\x27|[^\s]+)',
        r"\1[redacted]",
        value,
    )
    return value[:2048]


def _failure(
    code: str, message: str, *, dispatched: bool = False, text: str = ""
) -> RunResult:
    return {
        "status": "unknown" if dispatched else "failed",
        "final_text": text,
        "error": AdapterError(code, message).as_data(),
    }


@dataclass
class _Pending:
    questions: dict
    future: asyncio.Future
    outcome: str | None = None


@dataclass
class _Turn:
    binding: SessionBinding
    run_id: str
    emit: Emit
    sdk: object
    native_id: str | None
    client: object | None = None
    accepting: bool = False
    submitted: bool = False
    stopping: bool = False
    timeout: asyncio.Timeout | None = None
    pending: dict[str, _Pending] = field(default_factory=dict)
    replied_tools: dict[str, tuple[str, str]] = field(default_factory=dict)
    tool_names: dict[str, str] = field(default_factory=dict)
    texts: dict[str, dict[int, str]] = field(default_factory=dict)
    stream_ids: dict[str | None, str] = field(default_factory=dict)
    compacted: bool = False

    def text(self) -> str:
        return "".join(
            blocks[index] for blocks in self.texts.values() for index in sorted(blocks)
        )


class ClaudeAdapter(AgentAdapter):
    agent_id = "claude"
    settings_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "title": "Model", "maxLength": 128},
            "reasoning": {
                "type": "string",
                "title": "Reasoning effort",
                "enum": list(_EFFORTS),
            },
        },
        "additionalProperties": False,
    }
    capabilities: Capabilities = {
        "streaming_text": True,
        "tools": True,
        "questions": True,
        "approvals": True,
        "cancel": True,
        "cancel_mode": "native",
        "resume": True,
        "compact": True,
        "images": True,
        "files": False,
        "steer": False,
        "queue": False,
        "limits": {
            "image_mime_types": sorted(_IMAGE_TYPES),
            "max_image_bytes": _MAX_IMAGE_BYTES,
            "max_images": _MAX_IMAGES,
            "authentication": "Anthropic API key configured on the Runner host.",
            "approvals": "Native permission callbacks offer allow once or deny.",
        },
    }

    def __init__(self):
        self._config: AdapterConfig = {}
        self._active: _Turn | None = None

    def validate_config(self, config: AdapterConfig) -> AdapterConfig:
        normalized = {}
        for key, value in config.items():
            if key not in self.settings_schema["properties"] or not isinstance(
                value, str
            ):
                raise AdapterError("invalid_config", "Invalid Claude settings.")
            value = value.strip()
            if value:
                if (key == "model" and len(value) > 128) or (
                    key == "reasoning" and value not in _EFFORTS
                ):
                    raise AdapterError(
                        "invalid_config", "Invalid Claude model or reasoning effort."
                    )
                normalized[key] = value
        return normalized

    @staticmethod
    def _options(sdk, **kwargs):
        return sdk.ClaudeAgentOptions(
            **kwargs,
            system_prompt={"type": "preset", "preset": "claude_code"},
            permission_mode="default",
            # This integration uses the documented API-key path. Do not pass
            # a browser key or fall back to Claude Code subscription tokens.
            env={
                "CLAUDE_CODE_OAUTH_TOKEN": "",
                "ANTHROPIC_AUTH_TOKEN": "",
                "CLAUDE_CODE_USE_BEDROCK": "0",
                "CLAUDE_CODE_USE_ANTHROPIC_AWS": "0",
                "CLAUDE_CODE_USE_VERTEX": "0",
                "CLAUDE_CODE_USE_FOUNDRY": "0",
                "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",
                "CLAUDE_CODE_DISABLE_AGENT_VIEW": "1",
            },
        )

    async def probe(self, config: AdapterConfig) -> ProbeResult:
        self.validate_config(config)
        checks = dict.fromkeys(
            ("program", "protocol", "authentication", "model_request"), "not_checked"
        )
        result: ProbeResult = {
            "availability": "unavailable",
            "reason": "Claude Agent SDK was not found.",
            "version": None,
            "capabilities": self.capabilities,
            "checks": checks,
        }
        try:
            sdk = _load_sdk()
        except AdapterError:
            checks["program"] = "failed"
            return result
        result["version"] = sdk.__version__
        try:
            with TemporaryDirectory(prefix="chatraw-claude-probe-") as directory:
                options = self._options(
                    sdk,
                    cwd=directory,
                    setting_sources=[],
                    extra_args={"strict-mcp-config": None},
                )
                async with sdk.ClaudeSDKClient(options) as client:
                    info = await client.get_server_info()
            checks["program"] = "passed"
            if not isinstance(info, dict):
                checks["protocol"] = "failed"
                result["reason"] = (
                    "Claude Agent SDK initialization returned no server info."
                )
                return result
            checks["protocol"] = "passed"
            if isinstance(version := info.get("claude_code_version"), str):
                result["version"] = f"{sdk.__version__} / Claude Code {version}"
            result["models"] = [
                {
                    "id": model["value"],
                    "label": model.get("displayName") or model["value"],
                    "reasoning": model.get("supportedEffortLevels", []),
                }
                for model in info.get("models", [])
                if isinstance(model, dict) and isinstance(model.get("value"), str)
            ]
        except sdk.CLINotFoundError:
            checks["program"] = "failed"
            result["reason"] = "Claude Code runtime was not found by the Agent SDK."
            return result
        except (sdk.ClaudeSDKError, OSError, TimeoutError):
            checks["protocol"] = "failed"
            result["reason"] = "Claude Agent SDK initialization failed."
            return result
        if _api_key_configured():
            checks["authentication"] = "unknown"
            result.update(
                availability="ready",
                reason="Claude API key is configured. Authentication and model request untested.",
            )
        else:
            checks["authentication"] = "failed"
            result.update(
                availability="unconfigured",
                reason="Configure ANTHROPIC_API_KEY for the Runner account.",
            )
        return result

    async def create_session(
        self, session_id: str, workspace: Path, config: AdapterConfig
    ) -> SessionBinding:
        self._config = self.validate_config(config)
        return {
            "session_id": session_id,
            "agent_id": self.agent_id,
            "workspace": str(workspace),
            "native": {},
        }

    async def resume_session(
        self, binding: SessionBinding, config: AdapterConfig
    ) -> SessionBinding:
        normalized = self.validate_config(config)
        native_id = binding["native"].get("session_id")
        if native_id:
            sdk = _load_sdk()
            try:
                info = await asyncio.to_thread(
                    sdk.get_session_info, native_id, directory=binding["workspace"]
                )
            except (sdk.ClaudeSDKError, OSError, ValueError, TypeError):
                info = None
            if info is None:
                raise AdapterError(
                    "claude_resume_failed",
                    "The saved Claude session could not be found.",
                )
        self._config = normalized
        return binding

    async def run(
        self, binding: SessionBinding, request: RunRequest, emit: Emit
    ) -> RunResult:
        if request["message"].strip() == "/compact" and not request["attachments"]:
            return await self.compact(binding, {"run_id": request["run_id"]}, emit)
        prompt = request["message"]
        attachments = request["attachments"]
        if attachments:
            if len(attachments) > _MAX_IMAGES or any(
                item["mime_type"] not in _IMAGE_TYPES or item["size"] > _MAX_IMAGE_BYTES
                for item in attachments
            ):
                return _failure(
                    "unsupported_capability",
                    "Claude accepts up to four PNG, JPEG, WebP or GIF images of 5 MiB each.",
                )
            try:
                content = await self._image_content(prompt, attachments)
            except UnsupportedCapability as error:
                return {"status": "failed", "final_text": "", "error": error.as_data()}
            except OSError:
                return _failure(
                    "attachment_unavailable",
                    "Claude image attachment could not be read.",
                )
            prompt = self._image_prompt(content)
        return await self._execute(
            binding, request["run_id"], prompt, emit, compact=False
        )

    @staticmethod
    async def _image_content(text: str, attachments: list) -> list:
        content = [{"type": "text", "text": text}] if text else []
        for attachment in attachments:
            data = await asyncio.to_thread(_read_image, attachment["path"])
            if len(data) > _MAX_IMAGE_BYTES:
                raise UnsupportedCapability("Claude image exceeds 5 MiB")
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": attachment["mime_type"],
                        "data": base64.b64encode(data).decode("ascii"),
                    },
                }
            )
        return content

    @staticmethod
    async def _image_prompt(content: list):
        yield {
            "type": "user",
            "message": {"role": "user", "content": content},
            "parent_tool_use_id": None,
            "origin": {"kind": "human"},
        }

    async def compact(
        self, binding: SessionBinding, request: CompactRequest, emit: Emit
    ) -> RunResult:
        if not binding["native"].get("session_id"):
            return _failure(
                "no_native_history", "Start a Claude turn before compacting."
            )
        return await self._execute(
            binding, request["run_id"], "/compact", emit, compact=True
        )

    async def _execute(
        self, binding: SessionBinding, run_id: str, prompt, emit: Emit, *, compact: bool
    ) -> RunResult:
        try:
            sdk = _load_sdk()
        except AdapterError as error:
            return {"status": "failed", "final_text": "", "error": error.as_data()}
        if not _api_key_configured():
            return _failure(
                "claude_auth_unconfigured",
                "Configure ANTHROPIC_API_KEY for the Runner account.",
            )
        turn = _Turn(binding, run_id, emit, sdk, binding["native"].get("session_id"))
        self._active = turn
        dispatched = False
        settled = None

        async def can_use_tool(name, tool_input, context):
            return await self._permission(turn, name, tool_input, context)

        try:
            options = self._options(
                sdk,
                cwd=binding["workspace"],
                resume=turn.native_id,
                model=self._config.get("model"),
                effort=self._config.get("reasoning"),
                # Leave setting_sources and skills unset to use CLI discovery.
                include_partial_messages=True,
                can_use_tool=can_use_tool,
            )
            async with sdk.ClaudeSDKClient(options) as client:
                turn.client = client
                if turn.stopping:
                    return {"status": "cancelled", "final_text": ""}
                if compact:
                    info = await client.get_server_info()
                    if not any(
                        cmd.get("name") == "compact"
                        for cmd in (info or {}).get("commands", [])
                    ):
                        return _failure(
                            "claude_compact_unavailable",
                            "This Claude runtime does not expose /compact.",
                        )
                if turn.stopping:
                    return {"status": "cancelled", "final_text": ""}
                turn.accepting = True
                try:
                    dispatched = True
                    await client.query(prompt)
                    turn.submitted = True
                    async with asyncio.timeout(None) as timeout:
                        turn.timeout = timeout
                        if turn.stopping:
                            await self._interrupt(turn)
                        async with aclosing(client.receive_messages()) as messages:
                            async for message in messages:
                                settled = await self._message(turn, message, compact)
                                if settled is not None:
                                    break
                finally:
                    turn.timeout = None
                    turn.accepting = False
                    self._invalidate(turn)
        except (sdk.ClaudeSDKError, OSError, TimeoutError, ValueError):
            if settled is not None:
                return settled
            code = "claude_turn_unverified" if dispatched else "claude_start_failed"
            message = (
                "Claude did not confirm how the turn ended."
                if dispatched
                else "Claude Agent SDK could not start the session."
            )
            return _failure(code, message, dispatched=dispatched, text=turn.text())
        finally:
            self._active = None
        return settled or _failure(
            "claude_turn_unverified",
            "Claude ended its event stream without a result.",
            dispatched=True,
            text=turn.text(),
        )

    async def _checkpoint(self, turn: _Turn, native_id: str) -> None:
        if not native_id or (
            turn.native_id is not None and native_id != turn.native_id
        ):
            raise ValueError("Claude session mismatch")
        if (
            turn.binding["native"].get("session_id") != native_id
            and turn.native_id is None
        ):
            turn.native_id = native_id
            await turn.emit(
                {
                    "type": "binding_updated",
                    "data": {
                        **turn.binding,
                        "native": {"session_id": native_id},
                    },
                }
            )

    async def _message(self, turn: _Turn, message, compact: bool) -> RunResult | None:
        sdk = turn.sdk
        if isinstance(message, sdk.SystemMessage):
            if message.subtype == "init":
                await self._checkpoint(turn, message.data.get("session_id"))
            elif message.subtype == "compact_boundary":
                turn.compacted = True
        elif isinstance(message, sdk.StreamEvent):
            if not message.parent_tool_use_id:
                await self._stream(turn, message)
        elif isinstance(message, sdk.AssistantMessage):
            if not message.parent_tool_use_id and not message.error:
                await self._assistant(turn, message)
        elif isinstance(message, sdk.UserMessage):
            if isinstance(message.content, list):
                for block in message.content:
                    if not isinstance(block, sdk.ToolResultBlock):
                        continue
                    if resolution := turn.replied_tools.pop(block.tool_use_id, None):
                        key, outcome = resolution
                        await turn.emit(
                            {
                                "type": "interaction_resolved",
                                "native_key": key,
                                "data": {"outcome": outcome},
                            }
                        )
                    if name := turn.tool_names.pop(block.tool_use_id, None):
                        await turn.emit(
                            {
                                "type": "tool_completed",
                                "data": {
                                    "tool_call_id": block.tool_use_id,
                                    "name": name,
                                    "status": (
                                        "failed" if block.is_error else "completed"
                                    ),
                                },
                            }
                        )
        elif isinstance(message, sdk.ResultMessage):
            if message.origin and message.origin.get("kind") != "human":
                return None
            await self._checkpoint(turn, message.session_id)
            usage = {
                key: value
                for key, value in (message.usage or {}).items()
                if key in {"input_tokens", "output_tokens"} and type(value) is int
            }
            if isinstance(message.total_cost_usd, (int, float)):
                usage.update(cost=message.total_cost_usd, currency="USD")
            if usage:
                await turn.emit({"type": "usage", "data": usage})
            if message.terminal_reason in {"aborted_streaming", "aborted_tools"}:
                return {
                    "status": "cancelled" if turn.stopping else "interrupted",
                    "final_text": turn.text(),
                }
            if message.is_error or message.subtype != "success":
                code = "claude_native_failed"
                if message.api_error_status in {401, 403}:
                    code = "claude_auth_failed"
                return _failure(
                    code, "Claude reported a failed turn.", text=turn.text()
                )
            if compact and not turn.compacted:
                return _failure(
                    "claude_compact_unconfirmed",
                    "Claude did not confirm that it compacted the session.",
                )
            return {
                "status": "completed",
                "final_text": "" if compact else turn.text() or message.result or "",
            }
        return None

    @staticmethod
    async def _stream(turn: _Turn, message) -> None:
        event = message.event
        kind = event.get("type")
        parent = message.parent_tool_use_id
        if kind == "message_start":
            if message_id := event.get("message", {}).get("id"):
                turn.stream_ids[parent] = message_id
            return
        message_id = turn.stream_ids.get(parent)
        if not message_id:
            return
        if kind == "content_block_start" and event["content_block"]["type"] == "text":
            text = event["content_block"].get("text")
        elif kind == "content_block_delta" and event["delta"]["type"] == "text_delta":
            text = event["delta"].get("text")
        else:
            return
        if text:
            blocks = turn.texts.setdefault(message_id, {})
            index = event["index"]
            blocks[index] = blocks.get(index, "") + text
            await turn.emit(
                {"type": "text_delta", "data": {"text": text, "message_id": message_id}}
            )

    @staticmethod
    async def _assistant(turn: _Turn, message) -> None:
        sdk = turn.sdk
        message_id = message.message_id or message.uuid or uuid4().hex
        for index, block in enumerate(message.content):
            if isinstance(block, sdk.TextBlock):
                blocks = turn.texts.setdefault(message_id, {})
                previous = blocks.get(index, "")
                blocks[index] = block.text
                if block.text.startswith(previous) and len(block.text) > len(previous):
                    await turn.emit(
                        {
                            "type": "text_delta",
                            "data": {
                                "text": block.text[len(previous) :],
                                "message_id": message_id,
                            },
                        }
                    )
            elif (
                isinstance(block, sdk.ToolUseBlock) and block.id not in turn.tool_names
            ):
                name = block.name[:128]
                turn.tool_names[block.id] = name
                await turn.emit(
                    {
                        "type": "tool_started",
                        "data": {"tool_call_id": block.id, "name": name},
                    }
                )

    async def _permission(self, turn: _Turn, name: str, tool_input: dict, context):
        sdk = turn.sdk
        if not turn.accepting or turn.stopping or self._active is not turn:
            return sdk.PermissionResultDeny(
                message="This Claude request is no longer active."
            )
        if name == "AskUserQuestion":
            questions = self._questions(tool_input)
            if not questions:
                return sdk.PermissionResultDeny(
                    message="This question batch cannot be displayed."
                )
            data = {
                "kind": "question",
                "title": "Claude needs input",
                "questions": list(questions.values()),
                "allow_cancel": True,
            }
        else:
            questions = {}
            operation = {"tool": name[:128]}
            if name == "Bash" and isinstance(tool_input.get("command"), str):
                operation["command"] = _safe_preview(tool_input["command"])
            if isinstance(
                path := tool_input.get("file_path") or context.blocked_path, str
            ):
                operation["paths"] = [path[:512]]
            data = {
                "kind": "approval",
                "title": "Claude requests approval",
                "operation": operation,
                "decisions": [
                    {"id": "allow", "label": "Allow once", "scope": "once"},
                    {"id": "deny", "label": "Deny", "scope": "once"},
                ],
                "allow_cancel": True,
            }
            if name == "ExitPlanMode":
                plan = tool_input.get("plan")
                if not isinstance(plan, str) or not plan.strip():
                    return sdk.PermissionResultDeny(
                        message="Claude did not provide a plan to review."
                    )
                data.update(presentation="plan", detail=plan)
            elif isinstance(
                description := context.description or context.decision_reason, str
            ):
                data["detail"] = _safe_preview(description)

        key = uuid4().hex
        pending = _Pending(questions, asyncio.get_running_loop().create_future())
        turn.pending[key] = pending
        published = False
        try:
            try:
                await turn.emit(
                    {"type": "interaction_requested", "native_key": key, "data": data}
                )
                published = True
            except Exception:
                return sdk.PermissionResultDeny(
                    message="ChatRaw could not accept this Claude request."
                )
            response = await pending.future
            if (
                pending.outcome is not None
                and context.tool_use_id
                and not turn.stopping
            ):
                turn.replied_tools[context.tool_use_id] = (key, pending.outcome)
            if turn.stopping or not turn.accepting or response is None:
                return sdk.PermissionResultDeny(
                    message="The user declined or cancelled this request."
                )
            if questions:
                return sdk.PermissionResultAllow(
                    updated_input={**tool_input, "answers": response}
                )
            return sdk.PermissionResultAllow()
        finally:
            turn.pending.pop(key, None)
            if not pending.future.done() or pending.future.cancelled():
                pending.future.cancel()
                if published and turn.accepting and not turn.stopping:
                    await turn.emit(
                        {
                            "type": "interaction_resolved",
                            "native_key": key,
                            "data": {"outcome": "invalidated"},
                        }
                    )

    @staticmethod
    def _questions(tool_input: dict) -> dict:
        questions = {}
        seen = set()
        for index, question in enumerate(tool_input.get("questions") or []):
            text = question.get("question")
            if not isinstance(text, str) or not text or text in seen:
                return {}
            seen.add(text)
            choices = [
                {
                    "id": str(option_index),
                    "label": option["label"],
                    "description": option.get("description", ""),
                }
                for option_index, option in enumerate(question.get("options") or [])
            ]
            question_type = "multi" if question.get("multiSelect") else "single"
            qid = str(index)
            questions[qid] = {
                "id": qid,
                "text": text,
                "type": question_type if choices else "text",
                "options": choices,
                "allow_custom": True,
                "required": True,
            }
        return questions

    async def respond(
        self, binding: SessionBinding, interaction_key: str, reply: InteractionReply
    ) -> None:
        turn = self._active
        pending = turn.pending.get(interaction_key) if turn else None
        if (
            turn is None
            or pending is None
            or turn.stopping
            or not turn.accepting
            or pending.future.done()
            or turn.binding["session_id"] != binding["session_id"]
        ):
            raise AdapterError(
                "interaction_inactive", "This Claude request is no longer active."
            )
        response = None
        if not reply.get("cancelled"):
            if pending.questions:
                response = self._answers(pending.questions, reply)
            elif reply.get("decision_id") == "allow":
                response = True
            elif reply.get("decision_id") != "deny":
                raise AdapterError(
                    "invalid_reply", "Choose an available Claude decision."
                )
        pending.outcome = "cancelled" if reply.get("cancelled") else "answered"
        pending.future.set_result(response)

    @staticmethod
    def _answers(questions: dict, reply: InteractionReply) -> dict:
        seen = set()
        result = {}
        for answer in reply.get("answers", []):
            qid = answer["question_id"]
            question = questions.get(qid)
            selected, custom = answer["option_ids"], answer.get("text", "")
            choices = (
                {option["id"]: option["label"] for option in question["options"]}
                if question
                else {}
            )
            if (
                question is None
                or qid in seen
                or len(set(selected)) != len(selected)
                or (question["type"] != "multi" and len(selected) > 1)
                or any(choice not in choices for choice in selected)
                or bool(selected) == bool(custom.strip())
            ):
                raise AdapterError(
                    "invalid_reply",
                    "Answer each Claude question using its available options.",
                )
            seen.add(qid)
            labels = [choices[choice] for choice in selected]
            result[question["text"]] = (
                (labels if question["type"] == "multi" else labels[0])
                if labels
                else custom
            )
        if seen != questions.keys():
            raise AdapterError(
                "invalid_reply", "Answer each Claude question before submitting."
            )
        return result

    @staticmethod
    def _invalidate(turn: _Turn) -> None:
        for pending in turn.pending.values():
            if not pending.future.done():
                pending.future.set_result(None)

    @staticmethod
    async def _interrupt(turn: _Turn) -> None:
        turn.timeout.reschedule(asyncio.get_running_loop().time() + _STOP_TIMEOUT)
        try:
            await asyncio.wait_for(turn.client.interrupt(), _STOP_RPC_TIMEOUT)
        except (turn.sdk.ClaudeSDKError, OSError, TimeoutError):
            pass

    async def cancel(self, binding: SessionBinding, run_id: str) -> None:
        turn = self._active
        if (
            turn is None
            or turn.run_id != run_id
            or turn.stopping
            or turn.binding["session_id"] != binding["session_id"]
        ):
            return
        turn.stopping = True
        # Keep callbacks fenced immediately. Deliver interrupt before releasing
        # blocked callbacks so an early deny cannot start another model step.
        try:
            if turn.submitted and turn.timeout is not None:
                await self._interrupt(turn)
        finally:
            self._invalidate(turn)

    async def close(self, binding: SessionBinding) -> None:
        # The run task owns the SDK context and closes its CLI after reading
        # the terminal result (or losing the transport).
        pass
