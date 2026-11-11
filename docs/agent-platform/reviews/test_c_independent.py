"""F native counterexamples: approval fidelity and cancellation of a running tool.

Model requests stay on C's loopback fixture; all shell writes target its temp workspace.
"""

import asyncio
import copy
import json
import time
import unittest

from agent_runner.adapters.claude import ClaudeAdapter
from agent_runner.adapters.codex import CodexAdapter
from agent_runner.tests import test_c_native_adapters as native


def command(agent, scenario):
    marker = f"{agent}-approval-fixture"
    if scenario == "long":
        return ": " + "x" * 2300 + f"; printf hidden > {marker}"
    return f"printf started > {marker}; sleep 5; printf leaked > {marker}.late"


class CounterexampleModel(native._ModelHandler):
    def _codex(self, body):
        for event in super()._codex(body):
            event = copy.deepcopy(event)
            if event["type"] == "response.created":
                if self.server.scenario == "stop" and any(
                    item.get("type") == "function_call_output"
                    for item in body.get("input", [])
                ):
                    # Keep the model active after exec_command returns a background session.
                    yield event
                    time.sleep(7)
                    continue
            items = [event.get("item", {})] + event.get("response", {}).get("output", [])
            for item in items:
                if item.get("type") == "function_call" and item.get("name") == "exec_command" and item.get("arguments"):
                    args = json.loads(item["arguments"])
                    args["cmd"] = command("codex", self.server.scenario)
                    args["yield_time_ms"] = 1000
                    item["arguments"] = json.dumps(args)
            yield event

    def _claude(self, body):
        for event in super()._claude(body):
            event = copy.deepcopy(event)
            delta = event.get("delta", {})
            if delta.get("type") == "input_json_delta":
                args = json.loads(delta["partial_json"])
                if "command" in args:
                    args["command"] = command("claude", self.server.scenario)
                    delta["partial_json"] = json.dumps(args)
            yield event


class NativeCounterexamples(native.NativeAdapterTests):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.model.RequestHandlerClass = CounterexampleModel

    async def _approval_fidelity(self, adapter, allow):
        self.model.scenario = "long"
        await self._start(adapter, {})
        task = asyncio.create_task(self.sink.run(adapter, "long", "approval-fixture"))
        try:
            event = await self._interaction(task)
            displayed = json.dumps(event["data"], ensure_ascii=False)
            await adapter.respond(self.sink.binding, event["native_key"], {"decision_id": allow})
            result = await task
            marker = self.workspace / f"{adapter.agent_id}-approval-fixture"
            self.assertEqual(result["status"], "completed", result)
            self.assertEqual(marker.read_text(), "hidden")
            self.assertIn(
                "printf hidden", displayed,
                "Native receiver executed a command suffix absent from the entire approval payload",
            )
        finally:
            if not task.done():
                await adapter.cancel(self.sink.binding, "long")
                await task

    async def _running_tool_stop(self, adapter, allow):
        self.model.scenario = "stop"
        await self._start(adapter, {})
        task = asyncio.create_task(self.sink.run(adapter, "tool-stop", "approval-fixture"))
        try:
            event = await self._interaction(task)
            await adapter.respond(self.sink.binding, event["native_key"], {"decision_id": allow})
            marker = self.workspace / f"{adapter.agent_id}-approval-fixture"
            async with asyncio.timeout(8):
                while not marker.exists():
                    if task.done():
                        self.fail(f"Tool did not start: {task.result()}")
                    await asyncio.sleep(0.02)
            if adapter.agent_id == "codex":
                async with asyncio.timeout(8):
                    while not any(
                        any(item.get("type") == "function_call_output" for item in body.get("input", []))
                        for _, body in self.model.requests
                    ):
                        await asyncio.sleep(0.02)
            late_marker = marker.with_suffix(".late")
            self.assertFalse(late_marker.exists(), "Fixture wrote before cancellation began")
            cancel_at = time.monotonic()
            await adapter.cancel(self.sink.binding, "tool-stop")
            result = await task
            elapsed = time.monotonic() - cancel_at
            self.assertFalse(late_marker.exists(), "Fixture wrote before cancellation was confirmed")
            await asyncio.sleep(5.2)
            leaked = late_marker.exists()
            print(f"RECEIVER_RESULT agent={adapter.agent_id} status={result['status']} cancel_seconds={elapsed:.3f} absent_at_cancel_return=True late_marker={leaked}", flush=True)
            self.assertEqual(result["status"], "cancelled", result)
            self.assertFalse(leaked, "Adapter reported cancelled while its started shell still wrote later")
        finally:
            if not task.done():
                await adapter.cancel(self.sink.binding, "tool-stop")
                await task

    async def test_codex_long_approval_describes_executed_suffix(self):
        await self._approval_fidelity(CodexAdapter(), "accept")

    async def test_claude_long_approval_describes_executed_suffix(self):
        await self._approval_fidelity(ClaudeAdapter(), "allow")

    async def test_codex_cancel_stops_started_shell(self):
        await self._running_tool_stop(CodexAdapter(), "accept")

    async def test_claude_cancel_stops_started_shell(self):
        await self._running_tool_stop(ClaudeAdapter(), "allow")


# Only inherit the fixture helpers; run C's original test cases separately.
for inherited_name in dir(native.NativeAdapterTests):
    if inherited_name.startswith("test_") and inherited_name not in NativeCounterexamples.__dict__:
        setattr(NativeCounterexamples, inherited_name, None)


if __name__ == "__main__":
    unittest.main()
