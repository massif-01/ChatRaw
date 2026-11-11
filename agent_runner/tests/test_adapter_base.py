"""Simulated contract consumer, not evidence of a native Agent integration."""

import asyncio
import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

from agent_runner.adapters.base import (
    AdapterConfig, AdapterError, AdapterEvent, AdapterFactory, AgentAdapter,
    CompactRequest, Emit, InteractionReply, ProbeResult, RecoveryRequest,
    RunRequest, RunResult, SessionBinding, TERMINAL_STATUSES,
    UnsupportedCapability,
)


class MinimalAdapter(AgentAdapter):
    agent_id = "hermes"
    settings_schema = {"type": "object", "properties": {}, "additionalProperties": False}

    def validate_config(self, config: AdapterConfig) -> AdapterConfig:
        if config:
            raise AdapterError("invalid_config", "No settings are supported")
        return {}

    async def probe(self, config: AdapterConfig) -> ProbeResult:
        raise UnsupportedCapability("probe_fixture")

    async def create_session(
        self, session_id: str, workspace: Path, config: AdapterConfig,
    ) -> SessionBinding:
        return {"session_id": session_id, "agent_id": self.agent_id,
                "workspace": str(workspace), "native": {}}

    async def run(self, binding: SessionBinding, request: RunRequest, emit: Emit) -> RunResult:
        raise UnsupportedCapability("run_fixture")

    async def close(self, binding: SessionBinding) -> None:
        pass


class WaitingAdapter(MinimalAdapter):
    """Shows the required concurrent call shape without creating a runtime."""

    def __init__(self):
        self.answer = asyncio.Event()
        self.stop_requested = asyncio.Event()
        self.stopped = asyncio.Event()

    async def run(self, binding: SessionBinding, request: RunRequest, emit: Emit) -> RunResult:
        updated: SessionBinding = {**binding, "native": {"session": "native-session"}}
        await emit({"type": "binding_updated", "data": updated})
        await emit({
            "type": "interaction_requested", "native_key": request["run_id"] + ":q1",
            "data": {"kind": "question", "title": "Choose", "allow_cancel": True,
                     "questions": [{"id": "q1", "text": "Continue?", "type": "single",
                                    "options": [{"id": "yes", "label": "Yes"}],
                                    "allow_custom": False, "required": True}]},
        })
        await self.answer.wait()
        await self.stop_requested.wait()
        await self.stopped.wait()
        return {"status": "cancelled", "final_text": ""}

    async def respond(
        self, binding: SessionBinding, interaction_key: str, reply: InteractionReply,
    ) -> None:
        self.answer.set()

    async def cancel(self, binding: SessionBinding, run_id: str) -> None:
        self.stop_requested.set()


class AdapterContractTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        factory: AdapterFactory = MinimalAdapter
        self.adapter = factory()
        self.binding = await self.adapter.create_session("session-1", Path.cwd(), {})

    def test_import_has_no_optional_dependencies_or_backend_startup(self):
        result = subprocess.run(
            [sys.executable, "-S", "-c",
             "import sys; from agent_runner.adapters.base import AgentAdapter; "
             "assert 'backend.main' not in sys.modules; "
             "assert not any(n in sys.modules for n in "
             "('aiohttp', 'claude_agent_sdk', 'deepseek_harness'))"],
            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    async def test_optional_methods_fail_explicitly_without_success_fallback(self):
        async def emit(event: AdapterEvent) -> None:
            self.fail("Unsupported operations must not emit progress")

        request: CompactRequest = {"run_id": "compact-1"}
        for operation in (
            self.adapter.resume_session(self.binding, {}),
            self.adapter.respond(self.binding, "q1", {"cancelled": True}),
            self.adapter.cancel(self.binding, "run-1"),
            self.adapter.compact(self.binding, request, emit),
        ):
            with self.assertRaises(UnsupportedCapability) as raised:
                await operation
            self.assertEqual(raised.exception.code, "unsupported_capability")
            self.assertFalse(raised.exception.retryable)

    async def test_default_recovery_does_not_resubmit_or_claim_terminal(self):
        async def emit(event: AdapterEvent) -> None:
            self.fail("Unverified recovery cannot emit native progress")

        request: RecoveryRequest = {"run_id": "existing-run"}
        result = await self.adapter.recover_run(self.binding, request, {}, emit)
        self.assertEqual(result["status"], "unknown")
        self.assertNotIn(result["status"], TERMINAL_STATUSES)
        self.assertFalse(result["error"]["retryable"])
        self.assertEqual(json.loads(json.dumps(self.binding)), self.binding)

    async def test_leaf_can_checkpoint_and_receive_reply_stop_while_waiting(self):
        adapter = WaitingAdapter()
        events = []
        checkpoint_entered = asyncio.Event()
        checkpoint_persisted = asyncio.Event()
        question_received = asyncio.Event()

        async def emit(event: AdapterEvent) -> None:
            if event["type"] == "binding_updated":
                checkpoint_entered.set()
                await checkpoint_persisted.wait()
            events.append(copy.deepcopy(event))
            if event["type"] == "interaction_requested":
                question_received.set()

        task = asyncio.create_task(adapter.run(
            self.binding, {"run_id": "run-1", "message": "/native", "attachments": []}, emit,
        ))
        try:
            await asyncio.wait_for(checkpoint_entered.wait(), 1)
            self.assertFalse(events)
            checkpoint_persisted.set()
            await asyncio.wait_for(question_received.wait(), 1)
            self.assertEqual([e["type"] for e in events],
                             ["binding_updated", "interaction_requested"])
            await asyncio.wait_for(adapter.respond(
                self.binding, "run-1:q1", {"answers": [{"question_id": "q1", "option_ids": ["yes"]}]},
            ), 1)
            await asyncio.wait_for(adapter.cancel(self.binding, "run-1"), 1)
            self.assertFalse(task.done(), "A stop acknowledgement is not native settlement")
            adapter.stopped.set()
            result = await asyncio.wait_for(task, 1)
            self.assertEqual(result["status"], "cancelled")
            self.assertNotIn("done", [e["type"] for e in events])
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    def test_safe_error_payload_is_serializable(self):
        error = AdapterError("invalid_config", "Unknown setting")
        self.assertEqual(json.loads(json.dumps(error.as_data())), {
            "code": "invalid_config", "message": "Unknown setting", "retryable": False,
        })


if __name__ == "__main__":
    unittest.main()
