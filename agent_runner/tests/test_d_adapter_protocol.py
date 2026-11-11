"""Deterministic adapter lifecycle tests without native binaries or SDK installs."""

import asyncio
from pathlib import Path
from threading import Event
import unittest
from types import SimpleNamespace

from agent_runner.adapters.base import AdapterError
from agent_runner.adapters.deepseek import DeepSeekAdapter
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
