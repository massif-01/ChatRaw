"""Optional native CLI/SDK tests with a deterministic loopback model.

No provider credential or remote model is needed. See docs/agent-platform/D-adapters.md.
"""

import asyncio
import base64
import json
import os
import shlex
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from uuid import uuid4
from unittest.mock import patch

from agent_runner.adapters.base import AdapterError
from agent_runner.adapters.deepseek import DeepSeekAdapter
from agent_runner.adapters.pi import PiAdapter


_COMPACTION_CONTEXT = "TEST_COMPACTION_CONTEXT"


class _Model(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        if self.path.endswith("/files"):
            # This fixture exposes Messages without the optional Files API.
            self.send_error(404)
            return
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if (requests := getattr(self.server, "provider_requests", None)) is not None:
            requests.append((self.path, body))
        messages = body["messages"]
        latest = messages[-1]
        content = latest["content"]
        deepseek = self.path.endswith("/messages")
        text = (
            content
            if isinstance(content, str)
            else " ".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        )
        if deepseek and "TEST_MAX_TOKENS" in text:
            self.server.max_tokens.append(body.get("max_tokens"))
        if deepseek and "TEST_IMAGE" in text and isinstance(content, list):
            self.server.image_sources.extend(
                part["source"] for part in content if part.get("type") == "image"
            )
        tool = None
        tool_result = (
            latest["role"] == "tool"
            or isinstance(content, list)
            and any(part.get("type") == "tool_result" for part in content)
        )
        if "TEST_BATCH" in text and not tool_result:
            if deepseek:
                tool = (
                    "ask_user_question",
                    {
                        "questions": [
                            {
                                "id": "pick",
                                "question": "Choose one",
                                "options": [{"label": "A"}, {"label": "B"}],
                            },
                            {
                                "id": "many",
                                "question": "Choose several",
                                "multi_select": True,
                                "options": [{"label": "C"}, {"label": "D"}],
                            },
                            {"id": "note", "question": "Write a note"},
                        ]
                    },
                )
            else:
                tool = (
                    "ask_user",
                    {
                        "title": "Fixture questions",
                        "questions": [
                            {"text": "Choose one", "options": ["A", "B"]},
                            {
                                "text": "Choose several",
                                "options": ["C", "D"],
                                "multi": True,
                            },
                            {"text": "Write a note"},
                        ],
                    },
                )
        elif "TEST_BASH " in text and not tool_result:
            target = shlex.quote(text.split("TEST_BASH ", 1)[1].split()[0])
            args = {
                "command": f"printf ran > {target}",
                "description": "Write fixture marker",
            }
            if deepseek or body["model"] == "fixture-qwen":
                args.update(
                    command="# " + "x" * 2200 + "\n" + args["command"],
                    sandbox_permissions="danger-full-access",
                    justification="Write the fixture marker",
                )
            tool = ("bash", args)
        elif text.startswith("TEST_STOP_TOOL ") and not tool_result:
            target = shlex.quote(text.removeprefix("TEST_STOP_TOOL ").split()[0])
            args = {
                "command": f"printf started > {target}; sleep 3; printf leaked > {target}.late",
                "description": "Run a cancellable fixture command",
            }
            if deepseek:
                args.update(
                    sandbox_permissions="danger-full-access",
                    justification="Run the stop fixture",
                )
            tool = ("bash", args)
        elif "TEST_PLAN" in text and not tool_result:
            tool = ("exit_plan_mode", {"plan": "# Fixture plan\n\nAdd a test."})

        if text.startswith("You are now acting as a compaction engine"):
            answer = (
                "Checkpoint preserves " + _COMPACTION_CONTEXT
                if _COMPACTION_CONTEXT in json.dumps(messages)
                else "Checkpoint did not receive early context"
            )
        elif "TEST_COMPACTION_CONTINUATION" in json.dumps(messages):
            history = json.dumps(messages)
            answer = (
                "checkpoint present"
                if "Checkpoint preserves " + _COMPACTION_CONTEXT in history
                and "<compacted-summary>" in history
                else "checkpoint missing"
            )
        elif "TEST_IMAGE" in text and isinstance(content, list):
            answer = (
                "image present"
                if any(part.get("type") in ("image", "image_url") for part in content)
                else "native image reference"
            )
        elif "TEST_RESUME" in text:
            answer = (
                "history present"
                if "TEST_HISTORY" in json.dumps(messages)
                else "history missing"
            )
        elif tool_result:
            answer = "received " + json.dumps(content, ensure_ascii=False)
        else:
            answer = "fixture reply"

        if not body.get("tools"):
            tool = None
        name, arguments = tool if tool else ("", {})
        call_id = "call_" + uuid4().hex
        if deepseek:
            block = (
                {"type": "tool_use", "id": call_id, "name": name, "input": {}}
                if tool
                else {
                    "type": "text",
                    "text": "",
                }
            )
            delta = (
                {"type": "input_json_delta", "partial_json": json.dumps(arguments)}
                if tool
                else {
                    "type": "text_delta",
                    "text": answer,
                }
            )
            events = [
                {
                    "type": "message_start",
                    "message": {
                        "id": "msg_test",
                        "model": body["model"],
                        "type": "message",
                        "role": "assistant",
                        "content": [],
                        "usage": {"input_tokens": 3, "output_tokens": 0},
                    },
                },
                {"type": "content_block_start", "index": 0, "content_block": block},
                {"type": "content_block_delta", "index": 0, "delta": delta},
                {"type": "content_block_stop", "index": 0},
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "tool_use" if tool else "end_turn"},
                    "usage": {"output_tokens": 1},
                },
                {"type": "message_stop"},
            ]
            stream = "".join(
                f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
                for event in events
            )
        else:
            first = {"role": "assistant"}
            if tool:
                first["tool_calls"] = [
                    {
                        "index": 0,
                        "id": call_id,
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(arguments)},
                    }
                ]
            else:
                first["content"] = answer
            chunks = [
                {"index": 0, "delta": first, "finish_reason": None},
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "tool_calls" if tool else "stop",
                },
            ]
            stream = (
                "".join(
                    "data: "
                    + json.dumps(
                        {
                            "id": "chatcmpl_fixture",
                            "object": "chat.completion.chunk",
                            "created": 0,
                            "model": body["model"],
                            "choices": [chunk],
                        }
                    )
                    + "\n\n"
                    for chunk in chunks
                )
                + "data: [DONE]\n\n"
            )
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(stream.encode())))
        self.end_headers()
        self.wfile.write(stream.encode())


class _NativeCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="chatraw-native-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Model)
        Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1"
        self.events = asyncio.Queue()

    async def emit(self, event):
        self.events.put_nowait(event)

    async def binding(self, adapter, config, name):
        workspace = self.root / name
        workspace.mkdir()
        binding = await adapter.create_session(name, workspace, config)
        self.addAsyncCleanup(adapter.close, binding)
        return binding

    async def run_input(self, adapter, binding, prompt, name):
        request = {"run_id": name, "message": prompt, "attachments": []}
        return await adapter.run(binding, request, self.emit)

    async def run_image(self, adapter, binding):
        image = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
        )
        path = self.root / "upload.png"
        path.write_bytes(image)
        return await adapter.run(
            binding,
            {
                "run_id": "image",
                "message": "TEST_IMAGE",
                "attachments": [
                    {
                        "attachment_id": "upload",
                        "path": path,
                        "name": path.name,
                        "mime_type": "image/png",
                        "size": len(image),
                    }
                ],
            },
            self.emit,
        )

    async def interaction(self, task):
        while True:
            event = asyncio.create_task(self.events.get())
            try:
                await asyncio.wait(
                    (event, task), timeout=15, return_when=asyncio.FIRST_COMPLETED
                )
                if not event.done():
                    self.fail(
                        f"No interaction received. Result: {task.result() if task.done() else 'pending'}"
                    )
                record = event.result()
                if record["type"] == "interaction_requested":
                    return record
            finally:
                if not event.done():
                    event.cancel()

    async def check_batch(self, adapter, binding):
        task = asyncio.create_task(
            self.run_input(adapter, binding, "TEST_BATCH", "batch")
        )
        record = await self.interaction(task)
        self.assertEqual(
            [q["type"] for q in record["data"]["questions"]],
            ["single", "multi", "text"],
        )
        q1, q2, q3 = record["data"]["questions"]
        reply = {
            "answers": [
                {"question_id": q1["id"], "option_ids": ["2"]},
                {"question_id": q2["id"], "option_ids": ["1", "2"]},
                {"question_id": q3["id"], "option_ids": [], "text": "hello-user"},
            ]
        }
        with self.assertRaises(AdapterError):
            await adapter.respond(
                binding, record["native_key"], {"answers": reply["answers"][:2]}
            )
        await adapter.respond(binding, record["native_key"], reply)
        with self.assertRaises(AdapterError):
            await adapter.respond(binding, record["native_key"], reply)
        result = await asyncio.wait_for(task, 15)
        self.assertEqual(result["status"], "completed", result)
        self.assertIn("hello-user", result["final_text"])

    async def check_stop_and_resume(self, adapter, binding, other, other_binding):
        first = asyncio.create_task(
            self.run_input(adapter, binding, "TEST_BATCH", "stop")
        )
        dialog = await self.interaction(first)
        second = asyncio.create_task(
            self.run_input(other, other_binding, "TEST_BATCH", "keep")
        )
        other_dialog = await self.interaction(second)
        with self.assertRaises(AdapterError):
            await other.respond(
                other_binding, dialog["native_key"], {"cancelled": True}
            )
        await adapter.cancel(binding, "stop")
        with self.assertRaises(AdapterError):
            await adapter.respond(binding, dialog["native_key"], {"cancelled": True})
        self.assertEqual((await asyncio.wait_for(first, 20))["status"], "cancelled")
        self.assertFalse(second.done())
        await other.respond(
            other_binding, other_dialog["native_key"], {"cancelled": True}
        )
        self.assertEqual((await asyncio.wait_for(second, 15))["status"], "completed")
        resumed = await self.run_input(adapter, binding, "TEST_RESUME", "resume")
        self.assertEqual(
            resumed, {"status": "completed", "final_text": "history present"}
        )

    async def check_child_stop(self, adapter, binding, decision):
        marker = Path(binding["workspace"]) / "started"
        task = asyncio.create_task(
            self.run_input(adapter, binding, f"TEST_STOP_TOOL {marker}", "tool-stop")
        )
        request = await self.interaction(task)
        await adapter.respond(binding, request["native_key"], {"decision_id": decision})
        async with asyncio.timeout(2):
            while not marker.exists():
                if task.done():
                    self.fail(
                        f"Tool finished before writing its marker: {task.result()}"
                    )
                await asyncio.sleep(0.02)
        await adapter.cancel(binding, "tool-stop")
        result = await asyncio.wait_for(task, 20)
        self.assertEqual(result["status"], "cancelled", result)
        await asyncio.sleep(3)
        self.assertFalse(marker.with_suffix(".late").exists())


@unittest.skipUnless(
    os.getenv("CHATRAW_TEST_PI"), "Set CHATRAW_TEST_PI to the pinned Pi executable"
)
class PiNativeTests(_NativeCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        home = self.root / "pi-home"
        home.mkdir()
        (home / "models.json").write_text(
            json.dumps(
                {
                    "providers": {
                        "fixture": {
                            "baseUrl": self.url,
                            "api": "openai-completions",
                            "apiKey": "fixture-key",
                            "models": [
                                {"id": "fixture-model", "input": ["text", "image"]}
                            ],
                        }
                    }
                }
            )
        )
        (home / "settings.json").write_text(
            json.dumps(
                {
                    "retry": {"enabled": False},
                    "compaction": {"keepRecentTokens": 1},
                }
            )
        )
        environment = patch.dict(os.environ, {"PI_CODING_AGENT_DIR": str(home)})
        environment.start()
        self.addCleanup(environment.stop)
        self.config = {
            "session_root": str(self.root),
            "executable": os.environ["CHATRAW_TEST_PI"],
            "model": "fixture-model",
            "provider": "fixture",
        }

    async def test_rpc_batch_approval_stop_and_strict_resume(self):
        adapter = PiAdapter()
        self.assertEqual((await adapter.probe(self.config))["availability"], "ready")
        binding = await self.binding(adapter, self.config, "one")
        await self.check_batch(adapter, binding)

        for decision, should_exist in (("deny", False), ("allow", True)):
            marker = self.root / "one" / decision
            task = asyncio.create_task(
                self.run_input(adapter, binding, f"TEST_BASH {marker}", decision)
            )
            record = await self.interaction(task)
            self.assertEqual(record["data"]["kind"], "approval")
            self.assertIn(str(marker), record["data"]["operation"]["command"])
            await adapter.respond(
                binding, record["native_key"], {"decision_id": decision}
            )
            self.assertEqual((await asyncio.wait_for(task, 15))["status"], "completed")
            self.assertEqual(marker.exists(), should_exist)

        await self.run_input(adapter, binding, "TEST_HISTORY", "history")
        await adapter.close(binding)
        await adapter.resume_session(binding, self.config)
        other = PiAdapter()
        other_binding = await self.binding(other, self.config, "two")
        await self.check_stop_and_resume(adapter, binding, other, other_binding)
        await self.check_child_stop(adapter, binding, "allow")
        result = await self.run_image(adapter, binding)
        self.assertEqual(result, {"status": "completed", "final_text": "image present"})
        result = await adapter.compact(binding, {"run_id": "compact"}, self.emit)
        self.assertEqual(result["status"], "completed", result)
        transcript = Path(binding["native"]["transcript"])
        self.assertTrue(
            any(
                json.loads(line).get("type") == "compaction"
                for line in transcript.read_text().splitlines()
            )
        )
        await adapter.close(binding)
        transcript.unlink()
        with self.assertRaises(AdapterError):
            await adapter.resume_session(binding, self.config)


@unittest.skipUnless(
    os.getenv("CHATRAW_TEST_DEEPSEEK"),
    "Set CHATRAW_TEST_DEEPSEEK=1 with the pinned SDK",
)
class DeepSeekNativeTests(_NativeCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        environment = patch.dict(
            os.environ,
            {
                "DEEPSEEK_API_KEY": "fixture-key",
                "DEEPSEEK_BASE_URL": self.url,
                "DSH_PERMISSION_MODE": "workspace-write",
            },
        )
        environment.start()
        self.addCleanup(environment.stop)
        self.config = {"dsh_home": str(self.root)}
        self.server.max_tokens = []
        self.server.image_sources = []

    async def test_sdk_output_budget_reaches_model_and_omission_keeps_default(self):
        from deepseek_harness import HarnessClient

        initialize = []
        request = HarnessClient.request

        def record_request(client, method, params, **kwargs):
            if method == "initialize":
                initialize.append(dict(params))
            return request(client, method, params, **kwargs)

        with patch.object(HarnessClient, "request", record_request):
            for name, settings in (("explicit", {"max_tokens": 8192}), ("default", {})):
                adapter = DeepSeekAdapter()
                binding = await self.binding(adapter, {**self.config, **settings}, name)
                result = await asyncio.wait_for(
                    self.run_input(adapter, binding, "TEST_MAX_TOKENS", name), 15
                )
                self.assertEqual(result["status"], "completed", result)

        # The pinned runtime supplies its own budget when the setting is absent.
        explicit, default = initialize
        self.assertEqual(default["provider"], "deepseek-official")
        self.assertEqual(explicit["maxTokens"], 8192)
        self.assertNotIn("maxTokens", default)
        self.assertEqual(self.server.max_tokens, [8192, 256_000])

    async def test_sdk_resume_applies_new_output_budget_to_same_session(self):
        adapter = DeepSeekAdapter()
        binding = await self.binding(adapter, self.config, "budget-change")
        first = await asyncio.wait_for(
            self.run_input(adapter, binding, "TEST_MAX_TOKENS TEST_HISTORY", "before"),
            15,
        )
        self.assertEqual(first["status"], "completed", first)
        self.assertEqual(self.server.max_tokens, [256_000])
        await adapter.close(binding)

        resumed_adapter = DeepSeekAdapter()
        resumed = await resumed_adapter.resume_session(
            binding, {**self.config, "max_tokens": 8192}
        )
        self.addAsyncCleanup(resumed_adapter.close, resumed)
        self.assertEqual(resumed, binding)
        result = await asyncio.wait_for(
            self.run_input(
                resumed_adapter, resumed, "TEST_MAX_TOKENS TEST_RESUME", "after"
            ),
            15,
        )
        self.assertEqual(
            result, {"status": "completed", "final_text": "history present"}
        )
        self.assertEqual(self.server.max_tokens, [256_000, 8192])

    async def test_sdk_resumes_with_explicit_openai_provider_and_native_approval(self):
        patch_file = self.root / "openai-provider.yml"
        patch_source = (
            Path(__file__).resolve().parents[2]
            / "docs/agent-platform/handoffs/D-field/deepseek-rm01-models-v2.patch.yml"
        )
        patch_file.write_text(
            patch_source.read_text(encoding="utf-8")
            .replace("http://10.10.99.98:58000/v1", self.url)
            .replace("RM-01 VLM", "fixture-qwen"),
            encoding="utf-8",
        )
        config = {
            **self.config,
            "model": "fixture-qwen",
            "max_tokens": 8192,
        }
        chat_config = {
            **config,
            "patches": [str(patch_file)],
            "provider": "rm01-qwen",
            "reasoning_effort": "high",
        }
        self.server.provider_requests = []
        for official_key in ("", "fixture-key"):
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": official_key}):
                health = await DeepSeekAdapter().probe(chat_config)
            self.assertEqual(health["availability"], "ready", health)
            self.assertEqual(
                health["checks"],
                {
                    "program": "passed",
                    "protocol": "passed",
                    "authentication": "not_checked",
                    "model_request": "not_checked",
                },
            )
            self.assertIn(
                "authentication and model request unverified", health["reason"]
            )
            self.assertFalse(self.server.provider_requests)

        legacy = DeepSeekAdapter()
        legacy_binding = await self.binding(legacy, config, "legacy")
        self.assertEqual(
            (await self.run_input(legacy, legacy_binding, "TEST_HISTORY", "old"))[
                "status"
            ],
            "completed",
        )
        await legacy.close(legacy_binding)

        adapter = DeepSeekAdapter()
        binding = await self.binding(adapter, chat_config, "chat-provider")
        self.assertEqual(
            (
                await asyncio.wait_for(
                    self.run_input(
                        adapter,
                        binding,
                        f"TEST_HISTORY {_COMPACTION_CONTEXT}",
                        "before",
                    ),
                    15,
                )
            )["status"],
            "completed",
        )
        await adapter.close(binding)

        for effort, decision in (("high", "rejected"), ("off", "allowed-once")):
            adapter = DeepSeekAdapter()
            resumed = await adapter.resume_session(
                binding,
                {**chat_config, "reasoning_effort": effort},
            )
            self.addAsyncCleanup(adapter.close, resumed)
            self.assertEqual(resumed, binding)
            cursor = len(self.server.provider_requests)
            marker = Path(binding["workspace"]) / effort
            task = asyncio.create_task(
                self.run_input(adapter, resumed, f"TEST_BASH {marker}", effort)
            )
            approval = await self.interaction(task)
            self.assertEqual(
                approval["data"]["operation"],
                {
                    "tool": "bash",
                    "command": "# "
                    + "x" * 2200
                    + f"\nprintf ran > {shlex.quote(str(marker))}",
                    "cwd_label": binding["workspace"],
                },
            )
            self.assertFalse(marker.exists())
            await adapter.respond(
                resumed, approval["native_key"], {"decision_id": decision}
            )
            self.assertEqual((await asyncio.wait_for(task, 15))["status"], "completed")
            self.assertEqual(marker.exists(), decision == "allowed-once")
            path, outgoing = self.server.provider_requests[cursor]
            self.assertEqual(path, "/v1/chat/completions")
            self.assertEqual(
                outgoing["chat_template_kwargs"], {"enable_thinking": effort == "high"}
            )
            self.assertIn("TEST_HISTORY", json.dumps(outgoing["messages"]))
            self.assertEqual(outgoing["max_tokens"], 8192)
            self.assertEqual(
                {tool["function"]["name"] for tool in outgoing["tools"]},
                {tool["name"] for tool in self.server.provider_requests[0][1]["tools"]},
            )
            await adapter.close(resumed)

        path, outgoing = self.server.provider_requests[0]
        self.assertEqual(path, "/v1/messages")
        self.assertEqual(len(outgoing["tools"]), 31)
        self.assertEqual(outgoing["max_tokens"], 8192)
        self.assertNotIn("chat_template_kwargs", outgoing)
        path, first_chat_request = self.server.provider_requests[1]
        self.assertEqual(path, "/v1/chat/completions")
        self.assertEqual(
            first_chat_request["chat_template_kwargs"], {"enable_thinking": True}
        )

        resumed = await adapter.resume_session(binding, chat_config)
        self.assertEqual(resumed, binding)
        async with asyncio.timeout(20):
            self.assertEqual(
                await self.run_image(adapter, resumed),
                {"status": "completed", "final_text": "image present"},
            )
        path, image_request = self.server.provider_requests[-1]
        self.assertEqual(path, "/v1/chat/completions")
        (image_url,) = [
            part["image_url"]["url"]
            for part in image_request["messages"][-1]["content"]
            if part["type"] == "image_url"
        ]
        media, encoded = image_url.split(",", 1)
        signatures = {
            "data:image/png;base64": b"\x89PNG\r\n\x1a\n",
            "data:image/jpeg;base64": b"\xff\xd8",
            "data:image/webp;base64": b"RIFF",
        }
        self.assertIn(media, signatures)
        self.assertTrue(
            base64.b64decode(encoded, validate=True).startswith(signatures[media])
        )

        cursor = len(self.server.provider_requests)
        async with asyncio.timeout(20):
            compact = await adapter.compact(resumed, {"run_id": "compact"}, self.emit)
        self.assertEqual(compact["status"], "completed", compact)
        self.assertRegex(compact["final_text"], r"^Compacted [1-9][0-9]* history items")
        ((path, summary_request),) = self.server.provider_requests[cursor:]
        self.assertEqual(path, "/v1/chat/completions")
        self.assertIn(_COMPACTION_CONTEXT, json.dumps(summary_request["messages"]))
        await adapter.close(resumed)

        resumed = await adapter.resume_session(binding, chat_config)
        self.assertEqual(resumed, binding)
        self.assertEqual(adapter._session.id, binding["native"]["session_id"])
        async with asyncio.timeout(20):
            self.assertEqual(
                await self.run_input(
                    adapter, resumed, "TEST_COMPACTION_CONTINUATION", "after-compact"
                ),
                {"status": "completed", "final_text": "checkpoint present"},
            )
        path, continued_request = self.server.provider_requests[-1]
        self.assertEqual(path, "/v1/chat/completions")
        self.assertIn(
            "Checkpoint preserves " + _COMPACTION_CONTEXT,
            json.dumps(continued_request["messages"]),
        )
        await adapter.close(resumed)

        resumed_legacy = await legacy.resume_session(legacy_binding, config)
        self.assertEqual(resumed_legacy, legacy_binding)
        self.assertEqual(
            await self.run_input(
                legacy, resumed_legacy, "TEST_RESUME", "legacy-resume"
            ),
            {"status": "completed", "final_text": "history present"},
        )
        path, legacy_request = self.server.provider_requests[-1]
        self.assertEqual(path, "/v1/messages")
        self.assertNotIn("chat_template_kwargs", legacy_request)

    async def test_host_profile_patch_delivers_custom_model_image(self):
        patch_file = self.root / "vision.patch.yml"
        patch_file.write_text(
            "- id: llm-deepseek\n"
            "  config:\n"
            "    models:\n"
            "      - id: fixture-vision\n"
            "        inputModalities: [text, image]\n"
            "        contextWindow: 262144\n",
            encoding="utf-8",
        )
        for name, settings, expected in (
            ("uncatalogued", {}, "native image reference"),
            ("catalogued", {"patches": [str(patch_file)]}, "image present"),
        ):
            adapter = DeepSeekAdapter()
            config = {
                **self.config,
                "model": "fixture-vision",
                "max_tokens": 8192,
                **settings,
            }
            binding = await self.binding(adapter, config, name)
            result = await asyncio.wait_for(self.run_image(adapter, binding), 20)
            self.assertEqual(result, {"status": "completed", "final_text": expected})
        (source,) = self.server.image_sources
        self.assertEqual(source["type"], "base64")
        self.assertIn(source["media_type"], ("image/png", "image/jpeg", "image/webp"))
        self.assertTrue(base64.b64decode(source["data"], validate=True))

    async def test_sdk_batch_stop_and_strict_resume(self):
        adapter = DeepSeekAdapter()
        self.assertEqual((await adapter.probe(self.config))["availability"], "ready")
        binding = await self.binding(adapter, self.config, "one")
        await self.check_batch(adapter, binding)
        await self.run_input(adapter, binding, "TEST_HISTORY", "history")
        await adapter.close(binding)
        await adapter.resume_session(binding, self.config)
        other = DeepSeekAdapter()
        other_binding = await self.binding(other, self.config, "two")
        await self.check_stop_and_resume(adapter, binding, other, other_binding)
        await adapter.close(binding)
        home = Path(binding["native"]["dsh_home"])
        home.rename(home.with_name("missing"))
        with self.assertRaises(AdapterError):
            await adapter.resume_session(binding, self.config)

    async def test_sdk_empty_native_compaction(self):
        adapter = DeepSeekAdapter()
        binding = await self.binding(adapter, self.config, "compact")
        result = await asyncio.wait_for(
            adapter.compact(binding, {"run_id": "compact"}, self.emit), 15
        )
        self.assertEqual(
            result, {"status": "completed", "final_text": "No compactable history yet."}
        )
        result = await self.run_image(adapter, binding)
        self.assertEqual(result["status"], "completed", result)
        home = Path(binding["native"]["dsh_home"])
        self.assertTrue(
            any(path.is_file() for path in (home / "attachments" / "v1").rglob("*"))
        )

    async def test_sdk_native_plan_and_permission(self):
        adapter = DeepSeekAdapter()
        binding = await self.binding(adapter, self.config, "permission")
        changed_cwd = Path(binding["workspace"]) / "other"
        changed_cwd.mkdir()
        self.assertEqual(
            await asyncio.to_thread(
                adapter._harness.client.set_working_directory,
                binding["native"]["session_id"],
                str(changed_cwd),
            ),
            str(changed_cwd),
        )
        for decision, should_exist in (("rejected", False), ("allowed-once", True)):
            marker = self.root / "permission" / decision
            task = asyncio.create_task(
                self.run_input(adapter, binding, f"TEST_BASH {marker}", decision)
            )
            approval = await self.interaction(task)
            self.assertEqual(approval["data"]["kind"], "approval")
            self.assertEqual(
                approval["data"]["operation"],
                {
                    "tool": "bash",
                    "command": "# "
                    + "x" * 2200
                    + f"\nprintf ran > {shlex.quote(str(marker))}",
                    "cwd_label": str(changed_cwd),
                },
            )
            with self.assertRaises(AdapterError):
                await adapter.respond(
                    binding, approval["native_key"], {"decision_id": "always"}
                )
            await adapter.respond(
                binding, approval["native_key"], {"decision_id": decision}
            )
            self.assertEqual((await asyncio.wait_for(task, 15))["status"], "completed")
            self.assertEqual(marker.exists(), should_exist)

        task = asyncio.create_task(
            self.run_input(adapter, binding, "/plan TEST_PLAN", "plan")
        )
        review = await self.interaction(task)
        self.assertEqual(review["data"]["presentation"], "plan")
        self.assertEqual(review["data"]["detail"], "# Fixture plan\n\nAdd a test.")
        await adapter.respond(binding, review["native_key"], {"cancelled": True})
        self.assertEqual((await asyncio.wait_for(task, 15))["status"], "completed")

    async def test_sdk_stop_waits_for_active_shell(self):
        adapter = DeepSeekAdapter()
        binding = await self.binding(adapter, self.config, "tool-stop")
        await self.check_child_stop(adapter, binding, "allowed-once")
