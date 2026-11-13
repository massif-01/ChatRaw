"""Deterministic adapter lifecycle tests without native binaries or SDK installs."""

import asyncio
import json
from pathlib import Path
from threading import Event
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent_runner.adapters.base import AdapterError
from agent_runner.adapters.deepseek import DeepSeekAdapter, _Run
from agent_runner.adapters.pi import PiAdapter


class _ScriptedPi(PiAdapter):
    def __init__(self):
        super().__init__()
        self.commands = asyncio.Queue()

    async def _write(self, record):
        self.commands.put_nowait(record)

    def record(self, **record):
        self._active.records.put_nowait(record)


class PiProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.adapter = _ScriptedPi()
        self.binding = {
            "agent_id": "pi",
            "session_id": "s",
            "workspace": "/tmp",
            "native": {},
        }
        self.adapter._binding = self.binding
        self.events = asyncio.Queue()

    async def emit(self, event):
        self.events.put_nowait(event)

    async def start(self):
        request = {"run_id": "r", "message": "/native unchanged", "attachments": []}
        run = asyncio.create_task(self.adapter.run(self.binding, request, self.emit))
        command = await asyncio.wait_for(self.adapter.commands.get(), 1)
        self.assertEqual(command["message"], "/native unchanged")
        self.adapter.record(
            type="response",
            id=command["id"],
            success=True,
            data={"disposition": "started"},
        )
        return run

    async def test_retry_requires_settled_and_final_text_replaces_deltas(self):
        run = await self.start()
        self.adapter.record(
            type="message_end",
            message={"role": "assistant", "stopReason": "error", "content": []},
        )
        self.adapter.record(type="agent_end")
        self.adapter.record(type="auto_retry_start")
        await asyncio.sleep(0)
        self.assertFalse(run.done())
        self.adapter.record(type="message_start", message={"role": "assistant"})
        self.adapter.record(
            type="message_update",
            assistantMessageEvent={"type": "text_delta", "delta": "part"},
        )
        self.adapter.record(
            type="message_end",
            message={
                "role": "assistant",
                "stopReason": "stop",
                "content": [{"type": "text", "text": "full"}],
            },
        )
        self.adapter.record(type="agent_settled", aborted=False)
        self.assertEqual(
            await asyncio.wait_for(run, 1),
            {"status": "completed", "final_text": "full"},
        )
        self.assertEqual(
            await self.events.get(), {"type": "text_delta", "data": {"text": "part"}}
        )

    async def test_eof_is_unknown_and_fences_without_replay(self):
        run = await self.start()
        self.adapter.record(type="agent_end")
        self.adapter.record(type="_eof")
        self.assertEqual((await asyncio.wait_for(run, 1))["status"], "unknown")
        recovered = await self.adapter.recover_run(
            self.binding, {"run_id": "r"}, {}, self.emit
        )
        self.assertEqual(recovered["status"], "unknown")
        with self.assertRaises(AdapterError):
            await self.adapter.run(
                self.binding,
                {"run_id": "new", "message": "duplicate", "attachments": []},
                self.emit,
            )
        self.assertTrue(self.adapter.commands.empty())

    async def test_native_dialog_expiry_blocks_late_response(self):
        run = await self.start()
        self.adapter.record(
            type="extension_ui_request",
            id="native",
            method="select",
            title="Pick",
            options=["A"],
            timeout=5,
        )
        question = await asyncio.wait_for(self.events.get(), 1)
        self.assertEqual(
            question["data"]["questions"][0]["options"], [{"id": "1", "label": "A"}]
        )
        expired = await asyncio.wait_for(self.events.get(), 1)
        self.assertEqual(expired["data"]["outcome"], "expired")
        with self.assertRaises(AdapterError):
            await self.adapter.respond(
                self.binding, question["native_key"], {"cancelled": True}
            )
        self.assertTrue(self.adapter.commands.empty())
        self.adapter.record(type="agent_settled", aborted=False)
        self.assertEqual((await asyncio.wait_for(run, 1))["status"], "completed")

    async def test_manual_compaction_requires_response_and_native_abort_evidence(self):
        run = asyncio.create_task(
            self.adapter.compact(self.binding, {"run_id": "r"}, self.emit)
        )
        command = await asyncio.wait_for(self.adapter.commands.get(), 1)
        self.assertEqual(command["type"], "compact")
        await self.adapter.cancel(self.binding, "r")
        self.assertTrue(self.adapter.commands.empty())
        self.adapter.record(type="compaction_start", reason="manual")
        for expected in ("clear_queue", "abort"):
            self.assertEqual(
                (await asyncio.wait_for(self.adapter.commands.get(), 1))["type"],
                expected,
            )
        self.adapter.record(type="compaction_end", reason="manual", aborted=True)
        self.adapter.record(type="response", id=command["id"], success=False)
        self.assertEqual((await asyncio.wait_for(run, 1))["status"], "cancelled")

    async def test_unsupported_attachment_fails_before_dispatch(self):
        result = await self.adapter.run(
            self.binding,
            {
                "run_id": "r",
                "message": "hello",
                "attachments": [
                    {
                        "attachment_id": "file",
                        "path": Path("/tmp/missing"),
                        "name": "file",
                        "mime_type": "text/plain",
                        "size": 1,
                    }
                ],
            },
            self.emit,
        )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"]["code"], "unsupported_capability")
        self.assertTrue(self.adapter.commands.empty())


class _LostDeepSeek(DeepSeekAdapter):
    def __init__(self, graceful):
        super().__init__()
        self.graceful = graceful
        self.entered = asyncio.Event()
        self.release = Event()
        self._binding = {
            "agent_id": "deepseek",
            "session_id": "s",
            "workspace": "/tmp",
            "native": {},
        }
        self._harness = object()
        self._session = SimpleNamespace(id="native")

    def _run_sdk(self, active, harness, session, inputs):
        self._loop.call_soon_threadsafe(self.entered.set)
        self.release.wait(2)
        raise OSError("raw transport details")

    async def _stop_runtime(self, harness):
        self.release.set()
        return self.graceful


class DeepSeekProtocolTests(unittest.IsolatedAsyncioTestCase):
    def test_native_patches_are_host_only_absolute_paths(self):
        adapter = DeepSeekAdapter()
        config = {"dsh_home": "/tmp"}
        self.assertNotIn("patches", adapter.settings_schema["properties"])
        self.assertNotIn("patches", adapter.validate_config(config))
        paths = ["/etc/chatraw-runner/model.yml", "/etc/chatraw-runner/extra.yml"]
        result = adapter.validate_config({**config, "patches": paths})
        self.assertEqual(result["patches"], paths)
        self.assertIsNot(result["patches"], paths)
        for value in (
            None,
            True,
            "model.yml",
            ["relative.yml"],
            ["/bad\x00path"],
            [42],
        ):
            with self.subTest(value=value), self.assertRaises(AdapterError):
                adapter.validate_config({**config, "patches": value})

    def test_max_tokens_requires_a_positive_safe_integer(self):
        adapter = DeepSeekAdapter()
        config = {"dsh_home": "/tmp"}
        self.assertNotIn("max_tokens", adapter.validate_config(config))
        self.assertEqual(
            adapter.validate_config({**config, "max_tokens": 1})["max_tokens"], 1
        )
        for value in (True, False, None, 0, -1, 1.0, "8192", 2**53):
            with self.subTest(value=value), self.assertRaises(AdapterError) as error:
                adapter.validate_config({**config, "max_tokens": value})
            self.assertIn("max_tokens", str(error.exception))

    async def test_transport_loss_requires_owned_shutdown_evidence(self):
        async def emit(event):
            self.fail(event)

        for graceful, expected in ((True, "cancelled"), (False, "unknown")):
            with self.subTest(graceful=graceful):
                adapter = _LostDeepSeek(graceful)
                adapter._loop = asyncio.get_running_loop()
                binding = adapter._binding
                request = {"run_id": "r", "message": "one dispatch", "attachments": []}
                run = asyncio.create_task(adapter.run(binding, request, emit))
                await asyncio.wait_for(adapter.entered.wait(), 1)
                await adapter.cancel(binding, "r")
                result = await asyncio.wait_for(run, 1)
                self.assertEqual(result["status"], expected)
                self.assertNotIn("raw transport details", str(result))
                if not graceful:
                    with self.assertRaises(AdapterError):
                        await adapter.run(binding, request, emit)
                    recovered = await adapter.recover_run(
                        binding, {"run_id": "r"}, {}, emit
                    )
                    self.assertEqual(recovered["status"], "unknown")


class DeepSeekApprovalTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.events = asyncio.Queue()
        self.responses = asyncio.Queue()
        self.loop = asyncio.get_running_loop()
        self.adapter = DeepSeekAdapter()
        self.binding = {
            "agent_id": "deepseek",
            "session_id": "runner",
            "workspace": "/tmp",
            "native": {"session_id": "native"},
        }
        self.harness = SimpleNamespace(
            client=SimpleNamespace(respond=self.record_response)
        )
        self.adapter._loop = self.loop
        self.adapter._binding = self.binding
        self.adapter._harness = self.harness
        self.active = self.adapter._active = _Run("run", self.emit)

    async def emit(self, event):
        self.events.put_nowait(event)

    def record_response(self, request_id, value):
        self.loop.call_soon_threadsafe(self.responses.put_nowait, (request_id, value))

    async def call(self, session_id, call_id, arguments, name="bash"):
        notification = SimpleNamespace(
            method="session.event",
            payload={
                "sessionId": session_id,
                "event": {
                    "type": "tool/call",
                    "data": {
                        "callId": call_id,
                        "name": name,
                        "arguments": json.dumps(arguments),
                    },
                },
            },
        )
        await self.adapter._project(self.active, "native", notification)
        self.assertEqual((await self.events.get())["type"], "tool_started")

    def request(self, session_id, call_id, name="bash"):
        request = SimpleNamespace(
            method="approval/request",
            id=call_id or "missing",
            payload={
                "sessionId": session_id,
                "callId": call_id,
                "toolName": name,
            },
        )
        return asyncio.create_task(
            self.adapter._approval_request(self.active, self.harness, request)
        )

    async def test_exact_call_identity_in_either_event_order(self):
        for approval_first in (False, True):
            with self.subTest(approval_first=approval_first):
                call_id = f"target-{approval_first}"
                await self.call("native", f"other-{call_id}", {"command": "false"})
                await self.call("other", call_id, {"command": "false"})
                if approval_first:
                    task = self.request("native", call_id)
                    await asyncio.sleep(0)
                    self.assertIn(("native", call_id), self.active.awaiting_tool_calls)
                    self.assertTrue(self.events.empty())
                await self.call(
                    "native",
                    call_id,
                    {
                        "command": "printf one\nprintf two",
                        "workdir": "/tmp",
                        "sandbox_permissions": "danger-full-access",
                        "justification": "token=fixture-secret",
                    },
                )
                if not approval_first:
                    task = self.request("native", call_id)
                event = await asyncio.wait_for(self.events.get(), 1)
                self.assertEqual(event["type"], "interaction_requested")
                self.assertEqual(
                    event["data"]["operation"],
                    {
                        "tool": "bash",
                        "command": "printf one\nprintf two",
                        "cwd_label": "/tmp",
                    },
                )
                self.assertNotIn("fixture-secret", event["data"]["detail"])
                self.assertIn("danger-full-access", event["data"]["detail"])
                await self.adapter.respond(
                    self.binding, event["native_key"], {"decision_id": "allowed-once"}
                )
                self.assertEqual(
                    await asyncio.wait_for(self.responses.get(), 1),
                    (call_id, {"outcome": "allowed-once"}),
                )
                self.assertEqual(
                    (await self.events.get())["type"], "interaction_resolved"
                )
                await asyncio.wait_for(task, 1)

    async def test_missing_mismatched_or_unreviewable_calls_never_offer_allow(self):
        for index, (arguments, name, call_name) in enumerate(
            (
                ({}, "bash", "bash"),
                ({"command": "x" * 100_001}, "bash", "bash"),
                ({"command": "API_KEY=fixture-secret env"}, "bash", "bash"),
                ({"command": "pwd"}, "bash", "write"),
                ({"input": "fixture-secret"}, "apply_patch", "apply_patch"),
            )
        ):
            call_id = str(index)
            await self.call("native", call_id, arguments, call_name)
            await asyncio.wait_for(self.request("native", call_id, name), 1)
            self.assertEqual(
                await self.responses.get(), (call_id, {"outcome": "cancelled"})
            )
            if call_name == name:
                event = self.events.get_nowait()
                self.assertEqual(event["type"], "error")
                self.assertNotIn("fixture-secret", str(event))
            self.assertTrue(self.events.empty())
        await self.call("other", "crossed", {"command": "pwd", "workdir": "/tmp"})
        with patch("agent_runner.adapters.deepseek._APPROVAL_LOOKUP_TIMEOUT", 0.01):
            await asyncio.wait_for(self.request("native", "crossed"), 1)
        self.assertEqual(
            await self.responses.get(), ("crossed", {"outcome": "cancelled"})
        )
        await asyncio.wait_for(self.request("native", None), 1)
        self.assertEqual(
            await self.responses.get(), ("missing", {"outcome": "cancelled"})
        )
        self.assertTrue(self.events.empty())

    async def test_file_approval_projects_scope_without_file_contents(self):
        with patch.object(
            self.adapter, "_approval_working_directory", return_value="/tmp/workspace"
        ):
            await self.call(
                "native",
                "write",
                {"file_path": "file.txt", "content": "fixture-secret"},
                "write",
            )
            task = self.request("native", "write", "write")
            event = await asyncio.wait_for(self.events.get(), 1)
            self.assertEqual(
                event["data"]["operation"],
                {"tool": "write", "paths": ["file.txt"], "cwd_label": "/tmp/workspace"},
            )
            self.assertNotIn("fixture-secret", str(event))
            await self.adapter.respond(
                self.binding, event["native_key"], {"decision_id": "rejected"}
            )
            await asyncio.wait_for(task, 1)
            self.assertEqual(
                await self.responses.get(), ("write", {"outcome": "rejected"})
            )

    async def test_stop_rejects_new_or_pending_approval(self):
        await self.call("native", "pending", {"command": "pwd", "workdir": "/tmp"})
        pending = self.request("native", "pending")
        event = await asyncio.wait_for(self.events.get(), 1)
        waiting = self.request("native", "racing")
        await asyncio.sleep(0)
        await self.adapter.cancel(self.binding, self.active.id)
        await self.call("native", "racing", {"command": "pwd", "workdir": "/tmp"})
        with self.assertRaises(AdapterError):
            await self.adapter.respond(
                self.binding, event["native_key"], {"decision_id": "allowed-once"}
            )
        await asyncio.wait_for(waiting, 1)
        self.assertEqual(
            await self.responses.get(), ("racing", {"outcome": "cancelled"})
        )
        self.assertTrue(self.events.empty())
        pending.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await pending
