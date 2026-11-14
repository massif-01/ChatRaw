"""F focused revalidation for C-F01/C-F02; no business changes."""

from unittest.mock import patch

from agent_runner.adapters.claude import ClaudeAdapter
from agent_runner.adapters.codex import CodexAdapter, _Disconnected
from agent_runner.tests import test_c_adapter_protocol as protocol
from agent_runner.tests import test_c_native_adapters as native


class StopFailureTests(protocol.CodexProtocolTests):
    async def test_list_failure_does_not_confirm_cancellation(self):
        original = protocol._CodexWire.call

        async def fail_list(wire, method, params):
            if method == "thread/backgroundTerminals/list":
                wire.calls.append((method, params))
                raise _Disconnected()
            return await original(wire, method, params)

        with patch.object(protocol._CodexWire, "call", fail_list):
            result, wire = await self._interrupt_running_tool([])
        self.assertEqual(result["status"], "unknown")
        self.assertFalse(any(method.endswith("/terminate") for method, _ in wire.calls))

    async def test_terminate_failure_does_not_confirm_cancellation(self):
        original = protocol._CodexWire.call

        async def reject_terminate(wire, method, params):
            if method == "thread/backgroundTerminals/terminate":
                wire.calls.append((method, params))
                return {"terminated": False}
            return await original(wire, method, params)

        with patch.object(protocol._CodexWire, "call", reject_terminate):
            result, wire = await self._interrupt_running_tool(
                [[{"itemId": "owned-tool", "processId": "owned-process"}]]
            )
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(
            [params for method, params in wire.calls if method.endswith("/terminate")],
            [{"threadId": "thread", "processId": "owned-process"}],
        )

    async def test_terminate_ack_without_verified_disappearance_stays_unknown(self):
        owned = {"itemId": "owned-tool", "processId": "owned-process"}
        other = {"itemId": "other-turn-tool", "processId": "other-process"}
        result, wire = await self._interrupt_running_tool([[owned, other]] * 3)
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(
            [params for method, params in wire.calls if method.endswith("/terminate")],
            [{"threadId": "thread", "processId": "owned-process"}],
        )


class CredentialCommandTests(native.NativeAdapterTests):
    async def _credential_command_is_denied(self, adapter):
        marker = self.workspace / "credential-command-must-not-run"
        self.model.approval_command = f"API_TOKEN=fixture-value; printf hidden > {marker.name}"
        await self._start(adapter, {})
        await self.sink.run(adapter, "credential-command", "approval-fixture")
        self.assertFalse(marker.exists())
        self.assertFalse(any(event["type"] == "interaction_requested" for event in self.sink.events))
        self.assertTrue(any(
            event["type"] == "error" and event["data"]["code"] == "approval_unreviewable"
            for event in self.sink.events
        ))
        self.assertNotIn("fixture-value", str(self.sink.events))

    async def test_codex_redaction_required_command_is_not_authorizable(self):
        await self._credential_command_is_denied(CodexAdapter())

    async def test_claude_redaction_required_command_is_not_authorizable(self):
        await self._credential_command_is_denied(ClaudeAdapter())


for target, base in (
    (StopFailureTests, protocol.CodexProtocolTests),
    (CredentialCommandTests, native.NativeAdapterTests),
):
    for name in dir(base):
        if name.startswith("test_") and name not in target.__dict__:
            setattr(target, name, None)
del target, base, name
