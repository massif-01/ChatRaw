"""Opt-in tests of both native runtimes against loopback model substitutes.

Run with CHATRAW_C_NATIVE_TESTS=1 and the documented CLI/SDK versions.
Each test starts with a temporary home and dummy credentials.
"""

import asyncio
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from agent_runner.adapters.claude import ClaudeAdapter
from agent_runner.adapters.codex import CodexAdapter
from agent_runner.adapters.base import AdapterError


class _ModelServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _ModelHandler)
        self.requests = []
        self.counts = Counter()


class _ModelHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_error(404)

    def do_POST(self):
        if self.path.startswith("/v1/messages"):
            authenticated = self.headers.get("x-api-key") == "sk-ant-fixture"
        else:
            authenticated = self.headers.get("Authorization") == "Bearer sk-fixture"
        if not authenticated:
            self.send_error(401)
            return
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        self.server.requests.append((self.path, body))
        self.server.counts[self.path] += 1
        if self.path.startswith("/v1/messages"):
            if "count_tokens" in self.path:
                self._json({"input_tokens": 5})
            elif body.get("stream"):
                self._sse(self._claude(body))
            else:
                self._json(
                    self._claude_message(
                        body, [{"type": "text", "text": "Claude fixture"}]
                    )
                )
        elif self.path == "/v1/responses/compact":
            self._json(
                {
                    "id": "resp_compact",
                    "object": "response.compaction",
                    "created_at": 0,
                    "output": [
                        {
                            "type": "compaction",
                            "id": "cmp_1",
                            "encrypted_content": "fixture",
                        }
                    ],
                    "usage": {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7},
                }
            )
        elif self.path == "/v1/responses":
            self._sse(self._codex(body))
        else:
            self.send_error(404)

    def _json(self, value):
        body = json.dumps(value).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _sse(self, events):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        try:
            for event in events:
                self.wfile.write(
                    f"event: {event['type']}\ndata: {json.dumps(event)}\n\n".encode()
                )
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _claude_message(self, body, blocks):
        return {
            "type": "message",
            "id": f"msg_{len(self.server.requests)}",
            "role": "assistant",
            "model": body["model"],
            "content": blocks,
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 5, "output_tokens": 2},
        }

    def _claude(self, body):
        messages = body.get("messages", [])
        last = next(
            (message for message in reversed(messages) if message["role"] == "user"), {}
        )
        text = json.dumps(last.get("content", []))
        tool = None
        if "ask-fixture" in text and "tool_result" not in text:
            tool = {
                "type": "tool_use",
                "id": "toolu_fixture_question",
                "name": "AskUserQuestion",
                "input": {
                    "questions": [
                        {
                            "question": "Which color?",
                            "header": "Color",
                            "multiSelect": False,
                            "options": [
                                {"label": "Blue", "description": "Blue color"},
                                {"label": "Green", "description": "Green color"},
                            ],
                        },
                        {
                            "question": "Which sizes?",
                            "header": "Sizes",
                            "multiSelect": True,
                            "options": [
                                {"label": "Small", "description": "Small size"},
                                {"label": "Large", "description": "Large size"},
                            ],
                        },
                    ]
                },
            }
        elif "approval-fixture" in text and "tool_result" not in text:
            tool = {
                "type": "tool_use",
                "id": "toolu_fixture_bash",
                "name": "Bash",
                "input": {
                    "command": "touch claude-approval-fixture",
                    "description": "Create fixture file",
                },
            }
        message = self._claude_message(body, [])
        message.update(stop_reason=None, usage={"input_tokens": 5, "output_tokens": 0})
        yield {"type": "message_start", "message": message}
        if "stop-fixture" in text and "tool_result" not in text:
            time.sleep(5)
        block = {**tool, "input": {}} if tool else {"type": "text", "text": ""}
        yield {"type": "content_block_start", "index": 0, "content_block": block}
        delta = (
            {"type": "input_json_delta", "partial_json": json.dumps(tool["input"])}
            if tool
            else {"type": "text_delta", "text": "Claude fixture"}
        )
        yield {"type": "content_block_delta", "index": 0, "delta": delta}
        yield {"type": "content_block_stop", "index": 0}
        yield {
            "type": "message_delta",
            "delta": {
                "stop_reason": "tool_use" if tool else "end_turn",
                "stop_sequence": None,
            },
            "usage": {"output_tokens": 2},
        }
        yield {"type": "message_stop"}

    def _codex(self, body):
        response_id = f"resp_{len(self.server.requests)}"
        inputs = body.get("input", [])
        last = inputs[-1] if inputs else {}
        text = json.dumps(last)
        output = {
            "id": f"{response_id}_msg",
            "type": "message",
            "role": "assistant",
            "status": "completed",
            "content": [
                {"type": "output_text", "text": "Codex fixture", "annotations": []}
            ],
        }
        if "ask-fixture" in text and last.get("role") == "user":
            output = {
                "id": f"{response_id}_call",
                "type": "function_call",
                "name": "request_user_input",
                "call_id": f"{response_id}_tool",
                "status": "completed",
                "arguments": json.dumps(
                    {
                        "questions": [
                            {
                                "id": "color",
                                "header": "Color",
                                "question": "Which color?",
                                "options": [
                                    {"label": "Blue", "description": "Blue color"},
                                    {"label": "Green", "description": "Green color"},
                                ],
                            }
                        ]
                    }
                ),
            }
        if "approval-fixture" in text and last.get("role") == "user":
            output = {
                "id": f"{response_id}_call",
                "type": "function_call",
                "name": "exec_command",
                "call_id": f"{response_id}_tool",
                "status": "completed",
                "arguments": json.dumps(
                    {
                        "cmd": "touch codex-approval-fixture",
                        "sandbox_permissions": "require_escalated",
                        "justification": "Create fixture file",
                    }
                ),
            }
        response = {
            "id": response_id,
            "object": "response",
            "status": "in_progress",
            "created_at": 0,
            "model": body.get("model"),
            "output": [],
        }
        yield {"type": "response.created", "response": response}
        if "stop-fixture" in text:
            time.sleep(5)
        yield {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {
                **output,
                "status": "in_progress",
                **(
                    {"content": []}
                    if output["type"] == "message"
                    else {"arguments": ""}
                ),
            },
        }
        if output["type"] == "message":
            yield {
                "type": "response.output_text.delta",
                "item_id": output["id"],
                "output_index": 0,
                "content_index": 0,
                "delta": "Codex fixture",
            }
        yield {"type": "response.output_item.done", "output_index": 0, "item": output}
        yield {
            "type": "response.completed",
            "response": {
                **response,
                "status": "completed",
                "output": [output],
                "usage": {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7},
            },
        }


class _Sink:
    def __init__(self, binding):
        self.binding = binding
        self.events = []
        self.interactions = asyncio.Queue()

    async def emit(self, event):
        self.events.append(event)
        if event["type"] == "binding_updated":
            self.binding = event["data"]
        elif event["type"] == "interaction_requested":
            self.interactions.put_nowait(event)

    async def run(self, adapter, run_id, message, attachments=()):
        return await asyncio.wait_for(
            adapter.run(
                self.binding,
                {
                    "run_id": run_id,
                    "message": message,
                    "attachments": list(attachments),
                },
                self.emit,
            ),
            25,
        )


@unittest.skipUnless(
    os.environ.get("CHATRAW_C_NATIVE_TESTS") == "1",
    "requires the native Codex CLI and Claude Agent SDK",
)
class NativeAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        home = Path(directory, "home")
        self.workspace = Path(directory, "workspace")
        home.mkdir()
        self.workspace.mkdir()
        self.model = _ModelServer()
        worker = threading.Thread(
            target=self.model.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        )
        worker.start()
        self.addCleanup(self.model.server_close)
        self.addCleanup(self.model.shutdown)
        url = f"http://127.0.0.1:{self.model.server_port}"
        self.enterContext(
            patch.dict(
                os.environ,
                {
                    "PATH": os.environ["PATH"],
                    "HOME": str(home),
                    "CODEX_HOME": str(home / ".codex"),
                    "CLAUDE_CONFIG_DIR": str(home / ".claude"),
                    "ANTHROPIC_API_KEY": "sk-ant-fixture",
                    "ANTHROPIC_BASE_URL": url,
                    "OPENAI_API_KEY": "sk-fixture",
                    "DISABLE_TELEMETRY": "1",
                    "DISABLE_ERROR_REPORTING": "1",
                    "DISABLE_NONESSENTIAL_MODEL_CALLS": "1",
                    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
                },
                clear=True,
            )
        )
        codex_home = home / ".codex"
        codex_home.mkdir()
        (codex_home / "config.toml").write_text(
            f'model_provider = "fixture"\nmodel = "gpt-5.4"\n'
            f'sandbox_mode = "workspace-write"\n'
            f'[model_providers.fixture]\nname = "Fixture"\nbase_url = "{url}/v1"\n'
            f'env_key = "OPENAI_API_KEY"\nwire_api = "responses"\n'
        )
        self.adapter = None
        self.sink = None

    async def asyncTearDown(self):
        if self.adapter and self.sink:
            await self.adapter.close(self.sink.binding)

    async def _start(self, adapter, config):
        self.adapter = adapter
        self.sink = _Sink(await adapter.create_session("s1", self.workspace, config))

    async def test_codex_native_text_and_resume(self):
        adapter = CodexAdapter()
        await self._start(adapter, {})
        self.assertEqual(
            await self.sink.run(adapter, "r1", "hello"),
            {"status": "completed", "final_text": "Codex fixture"},
        )
        self.assertIn("turn_id", self.sink.binding["native"])
        await adapter.close(self.sink.binding)
        await adapter.resume_session(self.sink.binding, {})
        self.assertEqual(
            (await self.sink.run(adapter, "r2", "follow-up"))["status"], "completed"
        )
        latest = [
            body for path, body in self.model.requests if path == "/v1/responses"
        ][-1]
        self.assertIn("hello", json.dumps(latest["input"]))
        result = await adapter.recover_run(
            self.sink.binding, {"run_id": "r2"}, {}, self.sink.emit
        )
        self.assertEqual(result, {"status": "completed", "final_text": "Codex fixture"})

    async def test_claude_native_text_and_resume(self):
        adapter = ClaudeAdapter()
        await self._start(adapter, {})
        self.assertEqual(
            await self.sink.run(adapter, "r1", "hello"),
            {"status": "completed", "final_text": "Claude fixture"},
        )
        session_id = self.sink.binding["native"]["session_id"]
        await adapter.resume_session(self.sink.binding, {})
        self.assertEqual(
            (await self.sink.run(adapter, "r2", "follow-up"))["status"], "completed"
        )
        self.assertEqual(self.sink.binding["native"]["session_id"], session_id)
        requests = [
            body
            for path, body in self.model.requests
            if path.startswith("/v1/messages") and body.get("stream")
        ]
        self.assertIn("hello", json.dumps(requests[-1]["messages"]))

    async def _exercise_question(self, adapter, config, answers):
        await self._start(adapter, config)
        task = asyncio.create_task(self.sink.run(adapter, "ask", "ask-fixture"))
        event = await self._interaction(task)
        self.assertEqual(event["data"]["kind"], "question")
        self.assertEqual(event["data"]["questions"][0]["text"], "Which color?")
        with self.assertRaisesRegex(AdapterError, "Answer each"):
            await adapter.respond(
                self.sink.binding, event["native_key"], {"answers": []}
            )
        with self.assertRaisesRegex(AdapterError, "no longer active"):
            await adapter.respond(
                {**self.sink.binding, "session_id": "different"},
                event["native_key"],
                {"answers": answers},
            )
        await adapter.respond(
            self.sink.binding, event["native_key"], {"answers": answers}
        )
        self.assertEqual((await task)["status"], "completed")
        with self.assertRaisesRegex(AdapterError, "no longer active"):
            await adapter.respond(
                self.sink.binding, event["native_key"], {"answers": answers}
            )
        self.assertIn(
            {
                "type": "interaction_resolved",
                "native_key": event["native_key"],
                "data": {"outcome": "answered"},
            },
            self.sink.events,
        )

    async def test_codex_native_question(self):
        await self._exercise_question(
            CodexAdapter(),
            {"mode": "plan"},
            [
                {"question_id": "color", "option_ids": ["0"]},
            ],
        )
        self.assertIn("Blue", json.dumps(self.model.requests[-1][1]["input"][-1]))

    async def test_claude_native_question_batch(self):
        await self._exercise_question(
            ClaudeAdapter(),
            {},
            [
                {"question_id": "0", "option_ids": [], "text": "Crimson"},
                {"question_id": "1", "option_ids": ["0", "1"]},
            ],
        )
        latest = [body for path, body in self.model.requests if body.get("stream")][-1]
        self.assertIn("Crimson", json.dumps(latest["messages"][-1]))
        self.assertIn("Large", json.dumps(latest["messages"][-1]))

    async def _exercise_approval(self, adapter, allow, deny):
        await self._start(adapter, {})
        file = self.workspace / f"{adapter.agent_id}-approval-fixture"
        for decision in (deny, allow):
            task = asyncio.create_task(
                self.sink.run(adapter, decision, "approval-fixture")
            )
            event = await self._interaction(task)
            self.assertEqual(event["data"]["kind"], "approval")
            self.assertFalse(file.exists())
            with self.assertRaisesRegex(AdapterError, "available"):
                await adapter.respond(
                    self.sink.binding, event["native_key"], {"decision_id": "invalid"}
                )
            await adapter.respond(
                self.sink.binding, event["native_key"], {"decision_id": decision}
            )
            status = (await task)["status"]
            self.assertIn(
                status,
                {"completed", "interrupted"} if decision == "cancel" else {"completed"},
            )
            self.assertEqual(file.exists(), decision == allow)

    async def _interaction(self, task):
        read = asyncio.create_task(self.sink.interactions.get())
        try:
            done, _ = await asyncio.wait(
                (read, task), timeout=10, return_when=asyncio.FIRST_COMPLETED
            )
            if read in done:
                return read.result()
            self.fail(
                f"No native interaction. Result: {task.result() if task.done() else 'pending'}. "
                f"Events: {[event['type'] for event in self.sink.events]}. "
                f"Upstream calls: {self.model.counts}."
            )
        finally:
            if not read.done():
                read.cancel()
            if not task.done() and not read.done():
                task.cancel()

    async def test_codex_native_approval(self):
        await self._exercise_approval(CodexAdapter(), "accept", "cancel")

    async def test_claude_native_approval(self):
        await self._exercise_approval(ClaudeAdapter(), "allow", "deny")

    async def _exercise_stop(self, adapter):
        await self._start(adapter, {})
        task = asyncio.create_task(self.sink.run(adapter, "stop", "stop-fixture"))
        async with asyncio.timeout(15):
            while not any(
                "stop-fixture" in json.dumps(body) for _, body in self.model.requests
            ):
                await asyncio.sleep(0.02)
        await adapter.cancel(self.sink.binding, "stop")
        self.assertEqual((await task)["status"], "cancelled")
        self.assertEqual(
            (await self.sink.run(adapter, "next", "hello"))["status"], "completed"
        )

    async def test_codex_native_stop(self):
        await self._exercise_stop(CodexAdapter())

    async def test_claude_native_stop(self):
        await self._exercise_stop(ClaudeAdapter())

    async def _stop_during_approval(self, adapter):
        await self._start(adapter, {})
        task = asyncio.create_task(
            self.sink.run(adapter, "approval-stop", "approval-fixture")
        )
        event = await self._interaction(task)
        await adapter.cancel(self.sink.binding, "approval-stop")
        with self.assertRaisesRegex(AdapterError, "no longer active"):
            await adapter.respond(
                self.sink.binding,
                event["native_key"],
                {
                    "decision_id": event["data"]["decisions"][0]["id"],
                },
            )
        self.assertEqual((await task)["status"], "cancelled")
        self.assertFalse(
            (self.workspace / f"{adapter.agent_id}-approval-fixture").exists()
        )

    async def test_codex_native_stop_during_approval(self):
        await self._stop_during_approval(CodexAdapter())

    async def test_claude_native_stop_during_approval(self):
        await self._stop_during_approval(ClaudeAdapter())

    async def _exercise_compact(self, adapter):
        await self._start(adapter, {})
        self.assertEqual(
            (await self.sink.run(adapter, "start", "hello"))["status"], "completed"
        )
        result = await asyncio.wait_for(
            adapter.compact(self.sink.binding, {"run_id": "compact"}, self.sink.emit),
            25,
        )
        self.assertEqual(result["status"], "completed", result)

    async def test_codex_native_compaction(self):
        await self._exercise_compact(CodexAdapter())

    async def test_claude_native_compaction(self):
        await self._exercise_compact(ClaudeAdapter())

    async def _exercise_image(self, adapter, key):
        import base64

        data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
        )
        # Runner stores attachments under opaque IDs without file extensions.
        image = self.workspace / "opaque-attachment-id"
        image.write_bytes(data)
        await self._start(adapter, {})
        attachment = {
            "attachment_id": "a",
            "name": "pixel.png",
            "mime_type": "image/png",
            "path": image,
            "size": len(data),
        }
        self.assertEqual(
            (await self.sink.run(adapter, "img", "image-fixture", [attachment]))[
                "status"
            ],
            "completed",
        )
        self.assertTrue(
            any(
                key in json.dumps(body.get("input", body.get("messages", [])))
                for _, body in self.model.requests
                if body.get("stream")
            ),
            "the native runtime did not include an image in the model request",
        )

    async def test_codex_native_image(self):
        await self._exercise_image(CodexAdapter(), "data:image/png;base64,")

    async def test_claude_native_image(self):
        await self._exercise_image(ClaudeAdapter(), '"media_type": "image/png"')
