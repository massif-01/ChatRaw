"""Serial, opt-in checks of the RM-01 model service and native Agent clients."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import ProxyHandler, Request, build_opener


HOST = "10.10.99.98"
BASE = f"http://{HOST}:58000"
MODEL = "RM-01 VLM"
ANTHROPIC_HEADERS = {
    "anthropic-version": "2023-06-01",
    "x-api-key": "chatraw-local-probe",
}
FUNCTION = {
    "name": "probe_echo",
    "description": "Return a short diagnostic string.",
    "parameters": {
        "type": "object",
        "properties": {"value": {"type": "string"}},
        "required": ["value"],
        "additionalProperties": False,
    },
}
CODEX_CONFIG = f"""model_provider = "rm01-local"
model = "{MODEL}"
model_context_window = 262144
model_reasoning_effort = "none"
sandbox_mode = "read-only"

[model_providers.rm01-local]
name = "RM-01"
base_url = "{BASE}/v1"
wire_api = "responses"
requires_openai_auth = false
supports_websockets = false
request_max_retries = 0
stream_max_retries = 0

[model_providers.rm01-local.capabilities]
remote_compaction = "unsupported"
"""


def output(**data):
    print(json.dumps(data, ensure_ascii=False), flush=True)


def request(path, body=None, headers=None, *, stream=False):
    opener = build_opener(ProxyHandler({}))
    payload = None if body is None else json.dumps({"model": MODEL, **body}).encode()
    req = Request(
        BASE + path,
        data=payload,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with opener.open(req, timeout=25) as response:
        if not stream:
            return json.load(response)
        events = []
        for line in response:
            if line.startswith(b"data:"):
                data = line[5:].strip()
                events.append(
                    {"type": "[DONE]"} if data == b"[DONE]" else json.loads(data)
                )
        return events


def read_chat(events):
    choices = [choice for event in events for choice in event.get("choices", [])]
    calls = {}
    for choice in choices:
        for fragment in choice.get("delta", {}).get("tool_calls") or []:
            call = calls.setdefault(
                fragment["index"],
                {"type": "function", "function": {"name": "", "arguments": ""}},
            )
            if fragment.get("id"):
                call["id"] = fragment["id"]
            for field in ("name", "arguments"):
                call["function"][field] += fragment.get("function", {}).get(field) or ""
    text = "".join(choice.get("delta", {}).get("content") or "" for choice in choices)
    finish = [
        choice["finish_reason"] for choice in choices if choice.get("finish_reason")
    ]
    return text, finish, list(calls.values())


def read_responses(events):
    text = "".join(
        e["delta"] for e in events if e.get("type") == "response.output_text.delta"
    )
    finish = [
        e["type"]
        for e in events
        if e.get("type")
        in {"response.completed", "response.incomplete", "response.failed", "error"}
    ]
    calls = [
        e["item"]
        for e in events
        if e.get("type") == "response.output_item.done"
        and e["item"].get("type") == "function_call"
    ]
    return text, finish, calls


def read_messages(events):
    text, finish, calls, arguments = [], [], {}, {}
    for e in events:
        if (
            e.get("type") == "content_block_start"
            and e["content_block"]["type"] == "tool_use"
        ):
            calls[e["index"]] = e["content_block"]
        elif e.get("type") == "content_block_delta":
            delta = e["delta"]
            if delta["type"] == "text_delta":
                text.append(delta["text"])
            elif delta["type"] == "input_json_delta":
                index = e["index"]
                arguments[index] = arguments.get(index, "") + delta["partial_json"]
        elif e.get("type") == "message_delta":
            finish.append(e["delta"].get("stop_reason"))
    for index, raw in arguments.items():
        calls[index]["input"] = json.loads(raw)
    return "".join(text), finish, list(calls.values())


def http_probe():
    models = request("/v1/models")
    routes = request("/openapi.json")["paths"]
    output(
        version=request("/version")["version"],
        models=[
            {key: item.get(key) for key in ("id", "max_model_len")}
            for item in models["data"]
        ],
        remote_compact_route="/v1/responses/compact" in routes,
    )
    ready = {"role": "user", "content": "Reply with only the word READY."}
    user = {
        "role": "user",
        "content": 'Call probe_echo with value "ready". After the result, repeat its exact text.',
    }
    chat_tool = {"type": "function", "function": FUNCTION}
    messages_tool = {
        "name": FUNCTION["name"],
        "description": FUNCTION["description"],
        "input_schema": FUNCTION["parameters"],
    }
    paths = (
        (
            "/v1/chat/completions",
            "messages",
            "max_tokens",
            {},
            read_chat,
            chat_tool,
            {"type": "function", "function": {"name": "probe_echo"}},
        ),
        (
            "/v1/responses",
            "input",
            "max_output_tokens",
            {},
            read_responses,
            {"type": "function", **FUNCTION},
            {"type": "function", "name": "probe_echo"},
        ),
        (
            "/v1/messages?beta=true",
            "messages",
            "max_tokens",
            ANTHROPIC_HEADERS,
            read_messages,
            messages_tool,
            {"type": "tool", "name": "probe_echo"},
        ),
    )
    for path, field, limit, headers, parse, tool, forced in paths:
        common = {
            "stream": True,
            **({"store": False} if field == "input" else {"temperature": 0}),
        }
        text_input = ready["content"] if parse is read_responses else [ready]
        text, finish, _ = parse(
            request(
                path.partition("?")[0],
                {**common, field: text_input, limit: 48},
                headers,
                stream=True,
            )
        )
        output(path=path, case="text", text=text, finish=finish)
        if text.strip() != "READY":
            raise RuntimeError(f"{path}: unexpected text result")
        body = {
            **common,
            field: [user],
            limit: 72,
            "tools": [tool],
            "tool_choice": forced,
        }
        _, finish, calls = parse(request(path, body, headers, stream=True))
        output(path=path, case="tool", calls=calls, finish=finish)
        if len(calls) != 1:
            raise RuntimeError(f"{path}: expected one tool call")
        call = calls[0]
        if parse is read_chat:
            history = [
                user,
                {"role": "assistant", "content": None, "tool_calls": calls},
                {"role": "tool", "tool_call_id": call["id"], "content": "PROBE_OK"},
            ]
        elif parse is read_responses:
            history = [
                user,
                call,
                {
                    "type": "function_call_output",
                    "call_id": call["call_id"],
                    "output": "PROBE_OK",
                },
            ]
        else:
            history = [
                user,
                {"role": "assistant", "content": calls},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": call["id"],
                            "content": "PROBE_OK",
                        },
                    ],
                },
            ]
        choice = {"type": "none"} if parse is read_messages else "none"
        text, finish, _ = parse(
            request(
                path,
                {**body, field: history, "tool_choice": choice},
                headers,
                stream=True,
            )
        )
        output(
            path=path, case="manually supplied tool result", text=text, finish=finish
        )
        if text.strip() != "PROBE_OK":
            raise RuntimeError(f"{path}: unexpected tool result")
    tokens = request(
        "/v1/messages/count_tokens", {"messages": [ready]}, ANTHROPIC_HEADERS
    )
    output(path="/v1/messages/count_tokens", input_tokens=tokens["input_tokens"])


async def native_probe():
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
    from agent_runner.adapters.claude import ClaudeAdapter
    from agent_runner.adapters.codex import CodexAdapter

    with TemporaryDirectory(prefix="chatraw-local-model-") as directory:
        root = Path(directory)
        home, workspace = root / "home", root / "workspace"
        codex_home = home / ".codex"
        codex_home.mkdir(parents=True)
        workspace.mkdir()
        (codex_home / "config.toml").write_text(CODEX_CONFIG)
        marker = workspace / "marker.txt"
        marker.write_text("RM98_NATIVE_OK\n")
        executable_path = os.environ["PATH"]
        os.environ.clear()
        os.environ.update(
            PATH=executable_path,
            HOME=str(home),
            CODEX_HOME=str(codex_home),
            CLAUDE_CONFIG_DIR=str(home / ".claude"),
            NO_PROXY=HOST,
            no_proxy=HOST,
            ANTHROPIC_BASE_URL=BASE,
            ANTHROPIC_API_KEY="chatraw-local-probe",
            ANTHROPIC_MODEL=MODEL,
            ANTHROPIC_DEFAULT_HAIKU_MODEL=MODEL,
            ANTHROPIC_DEFAULT_SONNET_MODEL=MODEL,
            ANTHROPIC_DEFAULT_OPUS_MODEL=MODEL,
            CLAUDE_CODE_MAX_OUTPUT_TOKENS="256",
            CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1",
            DISABLE_NONESSENTIAL_MODEL_CALLS="1",
            DISABLE_TELEMETRY="1",
            DISABLE_ERROR_REPORTING="1",
        )
        for adapter in (CodexAdapter(), ClaudeAdapter()):
            binding = await adapter.create_session(
                "local-model-probe", workspace, {"model": MODEL}
            )
            tools = []

            async def emit(event):
                nonlocal binding
                if event["type"] == "binding_updated":
                    binding = event["data"]
                if event["type"] == "tool_completed":
                    tools.append(event["data"]["name"])
                if event["type"] == "interaction_requested":
                    if event["data"]["allow_cancel"]:
                        await adapter.respond(
                            binding, event["native_key"], {"cancelled": True}
                        )
                    else:
                        await adapter.cancel(binding, run_id)

            read = (
                "read",
                f"Use a read-only tool to read {marker}, then output only its exact one-line content. Do not change any files.",
                "RM98_NATIVE_OK",
            )
            cases = [read]
            if adapter.agent_id == "codex":
                cases.insert(
                    0,
                    (
                        "text",
                        "Do not call tools. Reply with only the word READY.",
                        "READY",
                    ),
                )
            try:
                for run_id, prompt, expected in cases:
                    tools.clear()
                    async with asyncio.timeout(28):
                        result = await adapter.run(
                            binding,
                            {
                                "run_id": run_id,
                                "message": prompt,
                                "attachments": [],
                            },
                            emit,
                        )
                    output(agent=adapter.agent_id, case=run_id, tools=tools, **result)
                    if (
                        result["status"] != "completed"
                        or result["final_text"].strip() != expected
                    ):
                        raise RuntimeError(
                            f"{adapter.agent_id}: unexpected {run_id} result"
                        )
                    if run_id == "read" and not tools:
                        raise RuntimeError(
                            f"{adapter.agent_id}: no completed read tool"
                        )
            finally:
                await adapter.close(binding)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("http", "native"), nargs="?")
    args = parser.parse_args()
    if args.mode == "http":
        http_probe()
    elif args.mode == "native":
        asyncio.run(native_probe())
    else:
        parser.print_help()
