"""F independent acceptance probes; native executables use only a loopback model.

Run with the same CHATRAW_TEST_PI / CHATRAW_TEST_DEEPSEEK variables as D's suite.
The fixture only supplies model output; production adapter code is unchanged.
"""

import asyncio
import copy
import io
import json
import unittest
from pathlib import Path

from agent_runner.adapters.base import AdapterError
from agent_runner.adapters.deepseek import DeepSeekAdapter
from agent_runner.adapters.pi import PiAdapter
from agent_runner.tests import test_d_native_adapters as native


class CapturingModel(native._Model):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self.server.model_requests.append(json.loads(body))
        self.rfile = io.BytesIO(body)
        super().do_POST()


class IndependentNativeMixin:
    async def test_fresh_adapter_restores_identity_cwd_and_isolates_context(self):
        self.server.RequestHandlerClass = CapturingModel
        self.server.model_requests = []
        adapter_type = PiAdapter if isinstance(self, PiIndependent) else DeepSeekAdapter
        first = adapter_type()
        health = await first.probe(self.config)
        self.assertEqual(health["checks"]["authentication"], "not_checked")
        self.assertEqual(health["checks"]["model_request"], "not_checked")
        binding = await self.binding(first, self.config, "original")
        self.assertEqual(self.server.model_requests, [], "Probe/create must not query model")
        result = await self.run_input(first, binding, "TEST_HISTORY", "seed")
        self.assertEqual(result["status"], "completed", result)
        checkpoint = json.loads(json.dumps(binding))
        await first.close(binding)

        restored = adapter_type()
        self.addAsyncCleanup(restored.close, checkpoint)
        before = len(self.server.model_requests)
        resumed = await restored.resume_session(checkpoint, self.config)
        self.assertEqual(resumed, checkpoint)
        self.assertEqual(len(self.server.model_requests), before, "Resume must not resend prompt")
        if isinstance(restored, DeepSeekAdapter):
            cwd = await asyncio.to_thread(restored._session.get_working_directory)
        else:
            header = json.loads(Path(checkpoint["native"]["transcript"]).read_text().splitlines()[0])
            cwd = header["cwd"]
        self.assertEqual(Path(cwd).resolve(), Path(binding["workspace"]).resolve())
        result = await self.run_input(restored, checkpoint, "TEST_RESUME", "restored")
        self.assertEqual(result, {"status": "completed", "final_text": "history present"})

        other = adapter_type()
        other_binding = await self.binding(other, self.config, "other")
        result = await self.run_input(other, other_binding, "TEST_RESUME", "isolated")
        self.assertEqual(result, {"status": "completed", "final_text": "history missing"})

    async def test_no_approval_until_explicit_response_and_cancel_is_not_allow(self):
        adapter_type = PiAdapter if isinstance(self, PiIndependent) else DeepSeekAdapter
        adapter = adapter_type()
        binding = await self.binding(adapter, self.config, "approval")
        marker = Path(binding["workspace"]) / "must-not-exist"
        task = asyncio.create_task(self.run_input(adapter, binding, f"TEST_BASH {marker}", "approval"))
        try:
            event = await self.interaction(task)
            self.assertEqual(event["data"]["kind"], "approval")
            await asyncio.sleep(0.15)
            self.assertFalse(task.done(), "Unanswered approval must remain pending")
            self.assertFalse(marker.exists(), "Native tool must wait for explicit approval")
            for reply in ({}, {"decision_id": "not-declared"}):
                with self.assertRaises(AdapterError):
                    await adapter.respond(binding, event["native_key"], reply)
            self.assertFalse(marker.exists())
            await adapter.respond(binding, event["native_key"], {"cancelled": True})
            result = await asyncio.wait_for(task, 15)
            self.assertIn(result["status"], {"completed", "failed", "cancelled"})
            self.assertFalse(marker.exists(), "Dismissal must not grant the native operation")
        finally:
            if not task.done():
                await adapter.cancel(binding, "approval")
                await asyncio.wait_for(task, 20)


class PiIndependent(IndependentNativeMixin, native.PiNativeTests):
    # Reuse setup only; D's existing acceptance case is run separately.
    test_rpc_batch_approval_stop_and_strict_resume = None


class DeepSeekIndependent(IndependentNativeMixin, native.DeepSeekNativeTests):
    test_sdk_batch_stop_and_strict_resume = None
    test_sdk_empty_native_compaction = None
    test_sdk_native_plan_and_permission = None
    test_sdk_stop_waits_for_active_shell = None


class AdmissionBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_recovery_never_starts_native_program(self):
        for adapter_type in (PiAdapter, DeepSeekAdapter):
            adapter = adapter_type()
            binding = {
                "session_id": "persisted", "agent_id": adapter.agent_id,
                "workspace": "/missing", "native": {},
            }
            async def emit(event):
                self.fail(f"Unverified recovery emitted {event}")
            result = await adapter.recover_run(binding, {"run_id": "old"}, {}, emit)
            self.assertEqual(result["status"], "unknown")
            self.assertIsNone(getattr(adapter, "_process", None))
            self.assertIsNone(getattr(adapter, "_harness", None))

    def test_browser_schema_excludes_execution_paths_and_secrets(self):
        for adapter_type, config in (
            (PiAdapter, {"executable": "/trusted/pi", "session_root": "/trusted/sessions"}),
            (DeepSeekAdapter, {"dsh_home": "/trusted/sessions"}),
        ):
            schema = adapter_type.settings_schema
            self.assertIs(schema["additionalProperties"], False)
            self.assertFalse(set(schema["properties"]) & {"api_key", "executable", "dsh_home", "session_root", "cwd"})
            for field in ("api_key", "cwd", "argv"):
                with self.assertRaises(AdapterError):
                    adapter_type().validate_config({**copy.deepcopy(config), field: "untrusted"})


if __name__ == "__main__":
    unittest.main()
