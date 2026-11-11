"""Deterministic edge cases at the native protocol and callback boundaries."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from agent_runner.adapters.base import AdapterError
from agent_runner.adapters.claude import ClaudeAdapter
from agent_runner.adapters.codex import CodexAdapter


async def _sink(events, event):
    events.append(event)


class _CodexWire:
    def __init__(self, *events):
        self.events = asyncio.Queue()
        for event in events:
            self.events.put_nowait(event)
        self.reader = SimpleNamespace(done=lambda: False)
        self.broken = False
        self.calls = []
        self.sent = []

    async def call(self, method, params):
        self.calls.append((method, params))
        if method == "thread/start":
            return {"thread": {"id": "thread"}, "model": "model"}
        if method == "turn/start":
            return {"turn": {"id": "turn"}}
        if method == "thread/turns/list":
            return {
                "data": [{"id": "some-other-turn", "status": "completed", "items": []}]
            }
        return {}

    async def send(self, message):
        self.sent.append(message)

    async def close(self):
        pass


def _codex_question(
    request_id, *, thread="thread", turn="turn", expiry=None, secret=False
):
    return {
        "method": "item/tool/requestUserInput",
        "id": request_id,
        "params": {
            "threadId": thread,
            "turnId": turn,
            "isBlocking": expiry is None,
            "autoResolutionMs": expiry,
            "questions": [
                {
                    "id": "q",
                    "question": "Question?",
                    "isSecret": secret,
                    "options": None,
                },
            ],
        },
    }


class CodexProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.adapter = CodexAdapter()
        self.binding = await self.adapter.create_session("s", Path("/workspace"), {})
        self.events = []

    async def _run(self, wire):
        with patch(
            "agent_runner.adapters.codex._AppServer.open", AsyncMock(return_value=wire)
        ):
            return await asyncio.wait_for(
                self.adapter.run(
                    self.binding,
                    {
                        "run_id": "r",
                        "message": "hello",
                        "attachments": [],
                    },
                    lambda event: _sink(self.events, event),
                ),
                2,
            )

    async def test_eof_leaves_turn_unknown_with_last_text(self):
        wire = _CodexWire(
            {
                "method": "item/agentMessage/delta",
                "params": {
                    "threadId": "thread",
                    "turnId": "turn",
                    "itemId": "m",
                    "delta": "Partial",
                },
            },
            None,
        )
        result = await self._run(wire)
        self.assertEqual(
            (result["status"], result["final_text"]), ("unknown", "Partial")
        )
        self.assertEqual(
            self.events[1]["data"]["native"],
            {
                "thread_id": "thread",
                "turn_id": "turn",
                "run_id": "r",
            },
        )

    async def test_cross_thread_turn_and_secret_requests_cannot_be_authorized(self):
        wire = _CodexWire(
            _codex_question(11, turn="different-turn"),
            _codex_question("12", thread="different-thread"),
            _codex_question(13, secret=True),
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "thread",
                    "turn": {"id": "different-turn", "status": "completed"},
                },
            },
            None,
        )
        self.assertEqual((await self._run(wire))["status"], "unknown")
        self.assertEqual([packet["id"] for packet in wire.sent], [11, "12", 13])
        self.assertTrue(all("error" in packet for packet in wire.sent))
        self.assertFalse(
            any(event["type"] == "interaction_requested" for event in self.events)
        )

    async def test_timed_question_resolves_empty_and_rejects_late_reply(self):
        wire = _CodexWire(_codex_question("question-id", expiry=0))
        task = asyncio.create_task(self._run(wire))
        try:
            async with asyncio.timeout(1):
                while not any(
                    event["type"] == "interaction_resolved" for event in self.events
                ):
                    await asyncio.sleep(0)
            request = next(
                event
                for event in self.events
                if event["type"] == "interaction_requested"
            )
            self.assertIn("expires_at", request["data"])
            self.assertIn({"id": "question-id", "result": {"answers": {}}}, wire.sent)
            self.assertIn(
                {
                    "type": "interaction_resolved",
                    "native_key": request["native_key"],
                    "data": {"outcome": "expired"},
                },
                self.events,
            )
            with self.assertRaisesRegex(AdapterError, "no longer active"):
                await self.adapter.respond(
                    self.binding,
                    request["native_key"],
                    {
                        "answers": [
                            {"question_id": "q", "option_ids": [], "text": "late"}
                        ],
                    },
                )
        finally:
            wire.events.put_nowait(None)
            self.assertEqual((await task)["status"], "unknown")

    async def test_recovery_never_replays_or_substitutes_a_different_turn(self):
        wire = _CodexWire()
        binding = {
            **self.binding,
            "native": {"thread_id": "thread", "turn_id": "turn", "run_id": "r"},
        }
        with patch(
            "agent_runner.adapters.codex._AppServer.open", AsyncMock(return_value=wire)
        ):
            result = await self.adapter.recover_run(binding, {"run_id": "r"}, {}, None)
            self.assertEqual(result["status"], "unknown")
            mismatch = await self.adapter.recover_run(
                binding, {"run_id": "other"}, {}, None
            )
            self.assertEqual(mismatch["status"], "unknown")
        self.assertEqual([method for method, _ in wire.calls], ["thread/turns/list"])


class _NativeMessage:
    def __init__(self, **fields):
        vars(self).update(fields)


class _ClaudeWire:
    def __init__(self, messages):
        self.messages = messages
        self.client = None
        self.sdk = SimpleNamespace(
            ClaudeAgentOptions=SimpleNamespace,
            ClaudeSDKClient=self.make_client,
            ClaudeSDKError=type("ClaudeSDKError", (Exception,), {}),
            **{
                name: type(name, (_NativeMessage,), {})
                for name in (
                    "SystemMessage",
                    "StreamEvent",
                    "AssistantMessage",
                    "UserMessage",
                    "ResultMessage",
                )
            },
        )

    def make_client(self, options):
        self.client = _ClaudeClient(self.messages(self.sdk), options)
        return self.client


class _ClaudeClient:
    def __init__(self, messages, options):
        self.messages = messages
        self.options = options
        self.closed = False
        self.interrupted = asyncio.Event()
        self.submitted = asyncio.Event()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        self.closed = True

    async def query(self, prompt):
        self.submitted.set()

    async def receive_messages(self):
        for message in self.messages:
            if message == "wait_for_interrupt":
                await self.interrupted.wait()
            else:
                yield message

    async def interrupt(self):
        self.interrupted.set()


class ClaudeProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.adapter = ClaudeAdapter()
        self.binding = await self.adapter.create_session("s", Path("/workspace"), {})
        self.events = []
        self.enterContext(
            patch("agent_runner.adapters.claude._api_key_configured", return_value=True)
        )

    async def _run(self, wire):
        with patch("agent_runner.adapters.claude._load_sdk", return_value=wire.sdk):
            return await asyncio.wait_for(
                self.adapter.run(
                    self.binding,
                    {
                        "run_id": "r",
                        "message": "hello",
                        "attachments": [],
                    },
                    lambda event: _sink(self.events, event),
                ),
                2,
            )

    async def test_eof_after_interrupt_ack_is_unknown_and_transport_is_closed(self):
        wire = _ClaudeWire(
            lambda sdk: [
                sdk.SystemMessage(subtype="init", data={"session_id": "native"}),
                "wait_for_interrupt",
            ]
        )
        task = asyncio.create_task(self._run(wire))
        try:
            async with asyncio.timeout(1):
                while wire.client is None:
                    await asyncio.sleep(0)
                await wire.client.submitted.wait()
            await self.adapter.cancel(self.binding, "r")
        finally:
            self.assertEqual((await task)["status"], "unknown")
        self.assertTrue(wire.client.interrupted.is_set())
        self.assertTrue(wire.client.closed)

    async def test_background_result_does_not_settle_the_human_turn(self):
        wire = _ClaudeWire(
            lambda sdk: [
                sdk.SystemMessage(subtype="init", data={"session_id": "native"}),
                sdk.ResultMessage(origin={"kind": "task-notification"}),
            ]
        )
        result = await self._run(wire)
        self.assertEqual(result["status"], "unknown")
        self.assertTrue(wire.client.closed)

    async def test_unknown_recovery_never_launches_sdk(self):
        with patch("agent_runner.adapters.claude._load_sdk") as sdk:
            result = await self.adapter.recover_run(
                self.binding, {"run_id": "r"}, {}, None
            )
            self.assertEqual(result["status"], "unknown")
        sdk.assert_not_called()


class AttachmentAndSettingsTests(unittest.IsolatedAsyncioTestCase):
    async def test_unsupported_files_are_rejected_before_native_start(self):
        for adapter in (CodexAdapter(), ClaudeAdapter()):
            binding = await adapter.create_session("s", Path("/workspace"), {})
            result = await adapter.run(
                binding,
                {
                    "run_id": "r",
                    "message": "hello",
                    "attachments": [{"mime_type": "application/pdf"}],
                },
                None,
            )
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["error"]["code"], "unsupported_capability")

    def test_settings_omit_blank_defaults_and_reject_host_overrides(self):
        for adapter in (CodexAdapter(), ClaudeAdapter()):
            self.assertEqual(
                adapter.validate_config({"model": "  ", "reasoning": ""}), {}
            )
            self.assertEqual(
                adapter.validate_config({"model": " requested ", "reasoning": "high"}),
                {"model": "requested", "reasoning": "high"},
            )
            with self.assertRaises(AdapterError):
                adapter.validate_config({"executable": "/tmp/unsafe"})
            with self.assertRaises(AdapterError):
                adapter.validate_config({"api_key": "blocked"})
