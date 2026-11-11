"""Deterministic native receiver tests against the real SQLite Runner ledger."""

import asyncio
import io
import tempfile
import unittest
from pathlib import Path

from agent_runner.adapters.base import AgentAdapter
from agent_runner.files import FileStore
from agent_runner.runtime import Runtime, unavailable
from agent_runner.store import RunnerError


class ControlledAdapter(AgentAdapter):
    agent_id = "hermes"
    settings_schema = {
        "type": "object",
        "properties": {"model": {"type": "string"}},
        "additionalProperties": False,
    }

    def __init__(self):
        self.started = asyncio.Event()
        self.finish = asyncio.Event()
        self.reply_entered = asyncio.Event()
        self.reply_release = asyncio.Event()
        self.reply_release.set()
        self.received = []
        self.prompts = []
        self.stops = 0
        self.binding = None
        self.config = {}
        self.received_configs = []

    def validate_config(self, config):
        return config

    async def probe(self, config):
        result = unavailable("")
        result["availability"] = "ready"
        result["capabilities"].update(
            cancel=True,
            cancel_mode="native",
            resume=True,
            compact=True,
            files=True,
            images=True,
        )
        return result

    async def create_session(self, session_id, workspace, config):
        self.config = dict(config)
        self.binding = {
            "session_id": session_id,
            "agent_id": "hermes",
            "workspace": str(workspace),
            "native": {"session": session_id},
        }
        return self.binding

    async def resume_session(self, binding, config):
        self.config = dict(config)
        self.binding = binding
        return binding

    async def run(self, binding, request, emit):
        self.received_configs.append(dict(self.config))
        self.prompts.append(request)
        await emit(
            {
                "type": "binding_updated",
                "data": {
                    **binding,
                    "native": {
                        "session": binding["session_id"],
                        "run": request["run_id"],
                    },
                },
            }
        )
        await emit({"type": "text_delta", "data": {"text": "partial"}})
        if request["message"] == "approval":
            await emit(
                {
                    "type": "interaction_requested",
                    "native_key": "approval-1",
                    "data": {
                        "kind": "approval",
                        "title": "Write a file?",
                        "decisions": [
                            {"id": "allow", "label": "Allow"},
                            {"id": "deny", "label": "Deny"},
                        ],
                        "allow_cancel": True,
                    },
                }
            )
        self.started.set()
        if request["message"] == "lost":
            raise EOFError("Native stream closed")
        await self.finish.wait()
        return {
            "status": "cancelled" if self.stops else "completed",
            "final_text": "FINAL",
        }

    async def compact(self, binding, request, emit):
        self.prompts.append(request)
        return {"status": "completed", "final_text": ""}

    async def respond(self, binding, interaction_key, reply):
        self.reply_entered.set()
        await self.reply_release.wait()
        self.received.append(reply)
        if reply == {"decision_id": "allow"}:
            (Path(binding["workspace"]) / "approved.txt").write_text(
                "native action executed"
            )

    async def cancel(self, binding, run_id):
        self.stops += 1
        self.finish.set()

    async def close(self, binding):
        pass


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = Runtime(self.temp.name, {"hermes": ControlledAdapter})
        self.runtime.file_store = FileStore(self.runtime.store)
        await self.runtime.set_enabled("hermes", True)
        await self.runtime.create_session(
            "session1", "chat1", "hermes", {"kind": "managed"}
        )

    async def asyncTearDown(self):
        await self.runtime.close()
        self.temp.cleanup()

    async def start(
        self, message="hello", key="key1", session="session1", chat="chat1"
    ):
        run = await self.runtime.submit(session, chat, key, message)
        adapter = self.runtime.instances[session]
        await asyncio.wait_for(adapter.started.wait(), 1)
        return run["run_id"], adapter

    async def settle(self, run_id, adapter):
        adapter.finish.set()
        await asyncio.wait_for(self.runtime.tasks[run_id], 1)
        return self.runtime.store.snapshot(run_id)

    async def test_idempotency_is_durable_and_payload_conflict_does_not_dispatch(self):
        run_id, adapter = await self.start()
        repeated = await self.runtime.submit("session1", "chat1", "key1", "hello")
        self.assertEqual(repeated["run_id"], run_id)
        with self.assertRaises(RunnerError) as conflict:
            await self.runtime.submit("session1", "chat1", "key1", "changed")
        self.assertEqual(conflict.exception.status, 409)
        self.assertEqual(len(adapter.prompts), 1)
        await self.settle(run_id, adapter)
        self.assertEqual(self.runtime.store.lookup("chat1", "key1")["run_id"], run_id)
        self.assertIsNone(self.runtime.store.lookup("other-chat", "key1"))

    async def test_changed_model_applies_on_next_run_without_changing_native_session(
        self,
    ):
        run_id, original = await self.start()
        self.runtime.set_settings("hermes", {"model": "new-model"})
        self.assertEqual(original.config, {})
        await self.settle(run_id, original)
        next_run = await self.runtime.submit("session1", "chat1", "next", "continue")
        updated = self.runtime.instances["session1"]
        await updated.started.wait()
        self.assertIsNot(original, updated)
        self.assertEqual(updated.received_configs, [{"model": "new-model"}])
        self.assertEqual(updated.binding["native"]["session"], "session1")
        self.assertEqual(original.received_configs, [{}])
        await self.settle(next_run["run_id"], updated)

    async def test_public_settings_can_be_saved_before_host_is_configured(self):
        class NeedsHost(ControlledAdapter):
            def validate_config(self, config):
                raise RunnerError("host_missing", "Configure the host first")

        self.runtime.factories["pi"] = NeedsHost
        self.runtime.set_settings("pi", {"model": "saved-before-host-setup"})
        self.assertEqual(
            self.runtime.agent_config("pi")["model"], "saved-before-host-setup"
        )

    async def test_disconnect_does_not_cancel_and_replay_is_contiguous_with_single_done(
        self,
    ):
        run_id, adapter = await self.start()
        stream = self.runtime.events(run_id)
        first = await anext(stream)
        await stream.aclose()
        self.assertEqual(adapter.stops, 0)
        self.assertFalse(self.runtime.tasks[run_id].done())
        snapshot = await self.settle(run_id, adapter)
        events = [e async for e in self.runtime.events(run_id, first["seq"])]
        self.assertEqual(
            [e["seq"] for e in events],
            list(range(first["seq"] + 1, snapshot["last_seq"] + 1)),
        )
        self.assertEqual(sum(e["type"] == "done" for e in events), 1)
        self.assertEqual(events[-1]["data"]["final_text"], "FINAL")
        self.assertNotIn("binding_updated", [e["type"] for e in events])
        self.assertEqual(
            self.runtime.store.session("session1")["binding"]["native"]["run"], run_id
        )

    async def test_unknown_retains_session_and_global_slot_without_done(self):
        run_id, adapter = await self.start("lost")
        await self.runtime.tasks[run_id]
        self.assertEqual(self.runtime.store.snapshot(run_id)["status"], "unknown")
        self.assertNotIn("done", [e["type"] for e in self.runtime.store.events(run_id)])
        with self.assertRaises(RunnerError) as busy:
            await self.runtime.submit("session1", "chat1", "key2", "next")
        self.assertEqual(busy.exception.code, "session_busy")
        self.assertEqual(len(adapter.prompts), 1)

    async def test_stop_before_approval_never_reaches_native_receiver(self):
        run_id, adapter = await self.start("approval")
        iid = self.runtime.store.snapshot(run_id)["interactions"][0]["interaction_id"]
        await self.runtime.cancel(run_id)
        with self.assertRaises(RunnerError) as stale:
            await self.runtime.respond(run_id, iid, {"decision_id": "allow"})
        self.assertEqual(stale.exception.status, 409)
        self.assertEqual(adapter.received, [])
        self.assertFalse((Path(adapter.binding["workspace"]) / "approved.txt").exists())

    async def test_approval_first_is_forwarded_once_and_stop_waits_for_dispatch(self):
        run_id, adapter = await self.start("approval")
        iid = self.runtime.store.snapshot(run_id)["interactions"][0]["interaction_id"]
        adapter.reply_release.clear()
        reply = asyncio.create_task(
            self.runtime.respond(run_id, iid, {"decision_id": "allow"})
        )
        await adapter.reply_entered.wait()
        stop = asyncio.create_task(self.runtime.cancel(run_id))
        await asyncio.sleep(0)
        self.assertEqual(adapter.stops, 0)
        adapter.reply_release.set()
        await reply
        await stop
        repeated = await self.runtime.respond(run_id, iid, {"decision_id": "allow"})
        self.assertEqual(repeated["status"], "accepted")
        self.assertEqual(adapter.received, [{"decision_id": "allow"}])
        self.assertTrue((Path(adapter.binding["workspace"]) / "approved.txt").exists())
        with self.assertRaises(RunnerError):
            await self.runtime.respond(run_id, iid, {"decision_id": "deny"})

    async def test_lost_reply_ack_is_not_retransmitted(self):
        run_id, adapter = await self.start("approval")
        iid = self.runtime.store.snapshot(run_id)["interactions"][0]["interaction_id"]
        original = adapter.respond

        async def lose_ack(*args):
            await original(*args)
            raise ConnectionError("Response lost after native execution")

        adapter.respond = lose_ack
        first = await self.runtime.respond(run_id, iid, {"decision_id": "allow"})
        second = await self.runtime.respond(run_id, iid, {"decision_id": "allow"})
        self.assertEqual(first["status"], "unknown")
        self.assertEqual(second, first)
        self.assertEqual(adapter.received, [{"decision_id": "allow"}])

    async def test_disable_and_cross_run_reply_do_not_authorize(self):
        run_id, adapter = await self.start("approval")
        iid = self.runtime.store.snapshot(run_id)["interactions"][0]["interaction_id"]
        await self.runtime.create_session(
            "session2", "chat2", "hermes", {"kind": "managed"}
        )
        other_id, other = await self.start(session="session2", chat="chat2")
        with self.assertRaises(RunnerError) as cross:
            await self.runtime.respond(other_id, iid, {"decision_id": "allow"})
        self.assertEqual(cross.exception.status, 404)
        await self.runtime.set_enabled("hermes", False)
        with self.assertRaises(RunnerError):
            await self.runtime.respond(run_id, iid, {"decision_id": "allow"})
        self.assertEqual(adapter.received, [])
        self.assertEqual(other.received, [])
        self.assertEqual(self.runtime.store.lookup("chat1", "key1")["run_id"], run_id)

    async def test_restart_does_not_resubmit_or_restore_old_approval(self):
        run_id, adapter = await self.start("approval")
        iid = self.runtime.store.snapshot(run_id)["interactions"][0]["interaction_id"]
        self.runtime.tasks[run_id].cancel()
        await self.runtime.tasks[run_id]
        self.runtime.store.close()
        self.runtime = Runtime(self.temp.name, {"hermes": ControlledAdapter})
        await self.runtime.recover()
        await self.runtime.tasks[run_id]
        self.assertEqual(self.runtime.store.snapshot(run_id)["status"], "unknown")
        self.assertEqual(self.runtime.instances["session1"].prompts, [])
        with self.assertRaises(RunnerError):
            await self.runtime.respond(run_id, iid, {"decision_id": "allow"})
        self.assertEqual(len(adapter.prompts), 1)

    async def test_attachment_ownership_and_artifact_symlink_boundary(self):
        store = self.runtime.file_store
        session = self.runtime.store.session("session1")
        with self.runtime.store.db:
            upload = store.save(
                session, io.BytesIO(b"test"), "source.txt", "text/plain"
            )
        await self.runtime.create_session(
            "session2", "chat2", "hermes", {"kind": "managed"}
        )
        with self.assertRaises(RunnerError):
            await self.runtime.submit(
                "session2",
                "chat2",
                "key2",
                "read",
                [{"attachment_id": upload["attachment_id"]}],
            )
        workspace = Path(session["workspace"])
        outside = Path(self.temp.name) / "private.txt"
        outside.write_text("private")
        (workspace / "link.txt").symlink_to(outside)
        with self.assertRaises(RunnerError):
            store.artifact(
                session,
                "run1",
                {
                    "path": workspace / "link.txt",
                    "name": "out.txt",
                    "mime_type": "text/plain",
                },
            )
        (workspace / "out.txt").write_text("safe")
        with self.runtime.store.db:
            artifact = store.artifact(
                session,
                "run1",
                {
                    "path": workspace / "out.txt",
                    "name": "out.txt",
                    "mime_type": "text/plain",
                },
            )
        (workspace / "out.txt").write_text("modified")
        self.assertEqual(store.path(artifact["artifact_id"]).read_text(), "safe")

    async def test_compaction_uses_same_busy_and_idempotency_rules(self):
        run_id, adapter = await self.start()
        with self.assertRaises(RunnerError):
            await self.runtime.submit("session1", "chat1", "compact1", kind="compact")
        await self.settle(run_id, adapter)
        result = await self.runtime.submit(
            "session1", "chat1", "compact1", kind="compact"
        )
        await self.runtime.tasks[result["run_id"]]
        self.assertEqual(adapter.prompts[-1], {"run_id": result["run_id"]})
        self.assertEqual(
            self.runtime.store.snapshot(result["run_id"])["final_text"], ""
        )


if __name__ == "__main__":
    unittest.main()
