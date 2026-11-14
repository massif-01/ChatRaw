"""Live WebSocket protocol fixture; no real Hermes installation/model is used."""

import asyncio
import base64
import sys
import tempfile
import unittest
from pathlib import Path

from aiohttp import web

from agent_runner.adapters.hermes import HermesAdapter


class GatewayFixture:
    def __init__(self):
        self.requests = []
        self.receipt = None
        self.cwd = None
        self.socket = None
        self.generation = 1
        self.prompt = None
        self.event_sequence = 0
        self.revision = 1

    def snapshot(self):
        return {
            "session_id": "native-session",
            "stored_session_id": "native-session",
            "info": {"cwd": self.cwd},
            "execution_generation": self.generation,
            "running": bool(self.receipt and self.receipt["status"] == "started"),
            "pending": [],
            "prompts": [self.prompt] if self.prompt else [],
            "revision": self.revision,
        }

    async def event(self, kind, payload, admission_id="admission-1"):
        self.event_sequence += 1
        await self.socket.send_json(
            {
                "jsonrpc": "2.0",
                "method": "event",
                "params": {
                    "type": kind,
                    "payload": payload,
                    "session_id": "native-session",
                    "admission_id": admission_id,
                    "execution_generation": self.generation,
                    "seq": self.event_sequence,
                    "replay_epoch": "fixture-epoch",
                },
            }
        )

    async def handle(self, request):
        socket = web.WebSocketResponse(protocols=["hermes-gateway-v1"])
        await socket.prepare(request)
        self.socket = socket
        async for message in socket:
            frame = message.json()
            method, params = frame["method"], frame["params"]
            self.requests.append((method, params))
            result = {}
            if method == "runtime.describe":
                result = {
                    "profile_id": "fixture-profile",
                    "instance_id": "fixture-owner",
                    "session_create": {
                        "sources": ["tui"],
                        "parameters": [
                            "cwd",
                            "request_id",
                            "source",
                            "model",
                            "provider",
                            "reasoning",
                        ],
                    },
                }
            elif method == "model.options":
                result = {
                    "providers": [
                        {
                            "slug": "fixture",
                            "authenticated": True,
                            "models": ["fixture-model"],
                        }
                    ]
                }
            elif method == "session.create":
                self.cwd = params["cwd"]
                result = self.snapshot()
            elif method == "session.resume":
                result = self.snapshot()
            elif method == "prompt.submit":
                if params.get("attachments") == []:
                    await socket.send_json(
                        {
                            "jsonrpc": "2.0",
                            "id": frame["id"],
                            "error": {
                                "code": "invalid_params",
                                "message": "Omit empty attachments",
                            },
                        }
                    )
                    continue
                if any(
                    not a["path"].startswith("/fixture-cache/")
                    for a in params.get("attachments", [])
                ):
                    await socket.send_json(
                        {
                            "jsonrpc": "2.0",
                            "id": frame["id"],
                            "error": {"code": "invalid_attachment_path"},
                        }
                    )
                    continue
                self.receipt = {
                    "status": "started",
                    "admission_id": "admission-1",
                    "execution_generation": self.generation,
                }
                result = self.receipt
            elif method == "prompt.receipt":
                result = self.receipt
            elif method == "prompt.cancel":
                self.receipt = {
                    **self.receipt,
                    "status": "terminal",
                    "outcome": "cancelled",
                    "result": {"final_response": ""},
                }
                result = self.receipt
            elif method == "approval.respond":
                self.prompt = None
                self.receipt = {
                    **self.receipt,
                    "status": "terminal",
                    "outcome": "completed" if params["choice"] == "once" else "failed",
                    "result": {
                        "final_response": (
                            "approved" if params["choice"] == "once" else ""
                        )
                    },
                }
                result = {"status": "resolved"}
            elif method == "clarify.respond":
                self.prompt = None
                self.receipt = {
                    **self.receipt,
                    "status": "terminal",
                    "outcome": "completed",
                    "result": {"final_response": params["answer"]},
                }
                result = {"status": "resolved"}
            elif method == "session.mutate":
                if params["expected_revision"] != self.revision:
                    await socket.send_json(
                        {
                            "jsonrpc": "2.0",
                            "id": frame["id"],
                            "error": {"code": "stale_revision"},
                        }
                    )
                    continue
                self.revision += 1
                result = {
                    "operation": params["operation"],
                    "revision": self.revision,
                    "state": "committed",
                }
            elif method == "command.dispatch":
                result = {"type": "exec", "output": "Native command output"}
            elif method == "image.attach_bytes":
                result = {
                    "attached": True,
                    "path": "/fixture-cache/image.png",
                    "mime": "image/png",
                }
            await socket.send_json(
                {"jsonrpc": "2.0", "id": frame["id"], "result": result}
            )
            if method == "prompt.submit":
                await self.event("message.delta", {"text": "live "})
                if params["text"] == "approval":
                    self.prompt = {
                        "kind": "approval",
                        "prompt_id": "prompt-1",
                        "execution_generation": 1,
                        "choices": ["once", "deny"],
                        "command": "touch approved.txt",
                    }
                    await self.event("approval.request", self.prompt)
                elif params["text"] == "question":
                    self.prompt = {
                        "kind": "clarify",
                        "prompt_id": "prompt-1",
                        "execution_generation": 1,
                        "choices": ["A", "B"],
                        "question": "Choose",
                        "multi_select": True,
                    }
                    await self.event("clarify.request", self.prompt)
        return socket


class HermesAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.native = GatewayFixture()
        app = web.Application()
        app.router.add_get("/ws", self.native.handle)
        self.server = web.AppRunner(app)
        await self.server.setup()
        site = web.TCPSite(self.server, "127.0.0.1", 0)
        await site.start()
        url = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}/ws"

        class FixtureAdapter(HermesAdapter):
            async def _ticket(self, config):
                return {"url": url, "protocols": ["hermes-gateway-v1"]}

        self.adapter = FixtureAdapter()
        self.config = {"executable": sys.executable}
        self.binding = await self.adapter.create_session(
            "safe-session", Path(self.temp.name), self.config
        )
        self.events = []
        self.interaction = asyncio.Event()
        self.tasks = []

    async def asyncTearDown(self):
        for task in self.tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await self.adapter.close(self.binding)
        await self.server.cleanup()
        self.temp.cleanup()

    async def emit(self, event):
        self.events.append(event)
        if event["type"] == "binding_updated":
            self.binding = event["data"]
        if event["type"] == "interaction_requested":
            self.interaction.set()

    def run_task(self, text, attachments=None):
        task = asyncio.create_task(
            self.adapter.run(
                self.binding,
                {
                    "run_id": "public-run",
                    "message": text,
                    "attachments": attachments or [],
                },
                self.emit,
            )
        )
        self.tasks.append(task)
        return task

    async def test_cwd_context_is_native_and_approval_uses_generation_identity(self):
        task = self.run_task("approval")
        await asyncio.wait_for(self.interaction.wait(), 2)
        interaction = next(
            e for e in self.events if e["type"] == "interaction_requested"
        )
        await self.adapter.respond(
            self.binding, interaction["native_key"], {"decision_id": "0"}
        )
        result = await asyncio.wait_for(task, 2)
        self.assertEqual(result, {"status": "completed", "final_text": "approved"})
        self.assertEqual(self.native.cwd, self.temp.name)
        submit = next(
            p for method, p in self.native.requests if method == "prompt.submit"
        )
        self.assertEqual(set(submit), {"session_id", "input_id", "text"})
        response = next(
            p for method, p in self.native.requests if method == "approval.respond"
        )
        self.assertEqual(
            response,
            {
                "session_id": "native-session",
                "prompt_id": "prompt-1",
                "execution_generation": 1,
                "choice": "once",
            },
        )

    async def test_multiselect_maps_back_to_native_labels(self):
        task = self.run_task("question")
        await asyncio.wait_for(self.interaction.wait(), 2)
        event = next(e for e in self.events if e["type"] == "interaction_requested")
        self.assertEqual(event["data"]["questions"][0]["type"], "multi")
        await self.adapter.respond(
            self.binding,
            event["native_key"],
            {"answers": [{"question_id": "answer", "option_ids": ["0", "1"]}]},
        )
        self.assertEqual((await asyncio.wait_for(task, 2))["final_text"], "A, B")

    async def test_stop_is_admission_scoped_and_closing_socket_does_not_stop_owner(
        self,
    ):
        task = self.run_task("hello")
        await asyncio.wait_for(self.adapter.admitted.wait(), 2)
        await self.adapter.cancel(self.binding, "public-run")
        self.assertEqual((await asyncio.wait_for(task, 2))["status"], "cancelled")
        await self.adapter.close(self.binding)
        cancel = [p for method, p in self.native.requests if method == "prompt.cancel"]
        self.assertEqual(
            cancel, [{"session_id": "native-session", "admission_id": "admission-1"}]
        )
        self.assertNotIn("process.stop", [m for m, _ in self.native.requests])

    async def test_native_command_and_compaction_do_not_become_chatraw_prompts(self):
        self.assertEqual(
            (await self.run_task("/status"))["final_text"], "Native command output"
        )
        result = await self.adapter.compact(
            self.binding, {"run_id": "compact-run"}, self.emit
        )
        self.assertEqual(result["status"], "completed")
        mutation = next(
            p for method, p in self.native.requests if method == "session.mutate"
        )
        self.assertEqual(mutation["operation"], "compress")
        self.assertEqual(mutation["request_id"], "compact-run")
        self.assertNotIn("prompt.submit", [m for m, _ in self.native.requests])

    async def test_eof_is_unknown_and_recovery_does_not_resubmit(self):
        task = self.run_task("hello")
        await asyncio.wait_for(self.adapter.admitted.wait(), 2)
        await self.native.socket.close()
        self.assertEqual((await asyncio.wait_for(task, 2))["status"], "unknown")
        self.native.receipt = {
            **self.native.receipt,
            "status": "terminal",
            "outcome": "completed",
            "result": {"final_response": "settled while offline"},
        }
        recovered = await self.adapter.recover_run(
            self.binding, {"run_id": "public-run"}, self.config, self.emit
        )
        self.assertEqual(recovered["final_text"], "settled while offline")
        self.assertEqual(
            len([m for m, _ in self.native.requests if m == "prompt.submit"]), 1
        )

    async def test_new_settings_mutate_the_existing_native_session(self):
        original_id = self.binding["native"]["session_id"]
        await self.adapter.close(self.binding)
        updated = await self.adapter.resume_session(
            self.binding, {**self.config, "model": "new-model", "reasoning": "high"}
        )
        mutations = [p for m, p in self.native.requests if m == "session.mutate"]
        self.assertEqual([p["operation"] for p in mutations], ["model", "reasoning"])
        self.assertEqual(mutations[0]["payload"], {"model": "new-model"})
        self.assertEqual(mutations[1]["payload"], {"effort": "high"})
        self.assertEqual([p["expected_revision"] for p in mutations], [1, 2])
        self.assertEqual(updated["native"]["session_id"], original_id)
        self.assertEqual(
            len([m for m, _ in self.native.requests if m == "session.create"]), 1
        )

    async def test_images_are_staged_in_native_profile_cache_before_submission(self):
        image = Path(self.temp.name) / "upload.png"
        image.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aFo0AAAAASUVORK5CYII="
            )
        )
        task = self.run_task(
            "image",
            [
                {
                    "attachment_id": "image1",
                    "path": image,
                    "name": image.name,
                    "mime_type": "image/png",
                    "size": image.stat().st_size,
                }
            ],
        )
        await asyncio.wait_for(self.adapter.admitted.wait(), 2)
        upload = next(p for m, p in self.native.requests if m == "image.attach_bytes")
        self.assertEqual(base64.b64decode(upload["content_base64"]), image.read_bytes())
        submit = next(p for m, p in self.native.requests if m == "prompt.submit")
        self.assertEqual(
            submit["attachments"],
            [{"path": "/fixture-cache/image.png", "mime": "image/png"}],
        )
        self.native.receipt = {
            **self.native.receipt,
            "status": "terminal",
            "outcome": "completed",
            "result": {"final_response": "image handled"},
        }
        self.assertEqual((await asyncio.wait_for(task, 2))["status"], "completed")

    async def test_tool_metadata_omits_raw_secrets_and_registers_native_image(self):
        output = Path(self.temp.name) / "output.png"
        output.write_bytes(b"native image fixture")
        await self.adapter._event(
            {
                "type": "tool.complete",
                "payload": {
                    "tool_id": "native-tool-1",
                    "name": "render",
                    "args": {"api_key": "fixture-secret"},
                    "result": "fixture-secret",
                    "image_path": str(output),
                },
            },
            self.emit,
        )
        self.assertEqual(
            self.events[0],
            {
                "type": "tool_completed",
                "data": {"tool_call_id": "native-tool-1", "name": "render"},
            },
        )
        self.assertEqual(self.events[1]["type"], "artifact")
        self.assertEqual(self.events[1]["data"]["path"], output)


if __name__ == "__main__":
    unittest.main()
