"""F independent authority checks; import production code from the pinned archive.

Use PYTHONPATH=<snapshot> and run from that snapshot. Native work is controlled,
while SQLite, gateway ASGI, Runner HTTP and the crash subprocess are real.
"""

import asyncio
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from backend import test_agent_gateway as gateway_fixture
from backend.agent_gateway import GatewayError, RunnerClient
from agent_runner.runtime import Runtime
from agent_runner.store import RunnerError
from agent_runner.tests.test_runtime import ControlledAdapter
from script.agent_db_backup import backup

main = gateway_fixture.main


class GatewayAuthorityTests(gateway_fixture.GatewayTests):
    async def test_dropped_reply_then_disable_preserves_single_native_dispatch(self):
        await self.bind()
        run, adapter = await self.submit("approval")
        iid = self.runtime.store.snapshot(run["run_id"])["interactions"][0]["interaction_id"]
        path = f"/api/agents/runs/{run['run_id']}/interactions/{iid}/reply"
        adapter.reply_release.clear()
        replying = asyncio.create_task(self.client.post(path, json={"decision_id": "allow"}))
        await asyncio.wait_for(adapter.reply_entered.wait(), 2)
        replying.cancel()  # Drop browser/gateway request after the native dispatch began.
        with self.assertRaises(asyncio.CancelledError):
            await replying
        disabling = asyncio.create_task(self.client.post("/api/plugins/hermes/toggle", json={"enabled": False}))
        try:
            async with asyncio.timeout(2):
                while self.runtime.enabled("hermes"):
                    await asyncio.sleep(0.01)
            self.assertEqual(adapter.stops, 0, "Stop cannot overtake a reply that already won dispatch")
        finally:
            adapter.reply_release.set()
        self.assertEqual((await disabling).status_code, 200)
        await self.runtime.tasks[run["run_id"]]
        receipt = await self.runtime.respond(run["run_id"], iid, {"decision_id": "allow"})
        self.assertEqual(receipt["status"], "accepted")
        self.assertEqual(adapter.received, [{"decision_id": "allow"}])
        self.assertEqual(adapter.stops, 1)
        self.assertTrue((Path(adapter.binding["workspace"]) / "approved.txt").exists())

    async def test_disable_wins_before_reply_and_uninstall_keeps_data(self):
        await self.bind()
        run, adapter = await self.submit("approval")
        iid = self.runtime.store.snapshot(run["run_id"])["interactions"][0]["interaction_id"]
        workspace = Path(adapter.binding["workspace"])
        sentinel = workspace / "user-project.txt"
        sentinel.write_text("must survive uninstall")
        lock = self.runtime.control(run["run_id"])
        await lock.acquire()
        disabling = asyncio.create_task(self.client.post("/api/plugins/hermes/toggle", json={"enabled": False}))
        try:
            async with asyncio.timeout(2):
                while self.runtime.enabled("hermes"):
                    await asyncio.sleep(0.01)
            late = await self.client.post(
                f"/api/agents/runs/{run['run_id']}/interactions/{iid}/reply",
                json={"decision_id": "allow"},
            )
            self.assertEqual(late.status_code, 403)
        finally:
            lock.release()
        self.assertEqual((await disabling).status_code, 200)
        self.assertEqual((await self.client.delete("/api/plugins/hermes")).status_code, 200)
        self.assertEqual(adapter.received, [])
        self.assertFalse((workspace / "approved.txt").exists())
        self.assertEqual(sentinel.read_text(), "must survive uninstall")
        self.assertEqual(main.load_plugin_config()["api_keys"]["hermes"], "legacy-secret-kept")
        self.assertEqual((await self.client.get(f"/api/agents/runs/{run['run_id']}")).status_code, 200)
        self.assertEqual(len(await self.wait_messages(2)), 2)

    async def test_lost_202_then_gateway_and_database_reopen_project_once(self):
        await self.bind()
        original = main.agent_gateway.client.request
        body = {"chat_id": self.chat_id, "client_request_id": "lost-reopen", "message": "one operation", "attachments": []}

        async def drop_accepted_response(method, path, **kwargs):
            result = await original(method, path, **kwargs)
            if method == "POST" and path == "/v1/runs":
                raise GatewayError("runner_unavailable", "Response deliberately lost", 503)
            return result

        with patch.object(main.agent_gateway.client, "request", side_effect=drop_accepted_response):
            self.assertEqual((await self.client.post("/api/agents/runs", json=body)).status_code, 503)
        run = self.runtime.store.lookup(self.chat_id, "lost-reopen")
        adapter = self.runtime.instances[run["session_id"]]
        url = main.agent_gateway.client.base_url
        await main.agent_gateway.close()
        self.assertEqual(adapter.stops, 0)
        adapter.finish.set()
        await self.runtime.tasks[run["run_id"]]
        database_path = self.database.db_path
        self.database.get_conn().close()
        self.database = main.Database(database_path)
        main.db = self.database
        main.agent_gateway.client = RunnerClient(url, self.token)
        main.agent_gateway.locks.clear()
        await main.agent_gateway.start()
        self.assertEqual([m["content"] for m in await self.wait_messages(2)], ["one operation", "FINAL"])
        repeated = await self.client.post("/api/agents/runs", json=body)
        self.assertEqual(repeated.status_code, 202, repeated.text)
        self.assertEqual(repeated.json()["run_id"], run["run_id"])
        self.assertEqual(len(adapter.prompts), 1)
        self.assertEqual(len(self.database.get_messages(self.chat_id)), 2)
        self.assertEqual(sum(e["type"] == "done" for e in self.runtime.store.events(run["run_id"])), 1)

    async def test_empty_final_replaces_partial_and_replay_does_not_duplicate(self):
        binding = await self.bind()
        adapter = self.runtime.instances[binding["session_id"]]

        async def run_empty(binding, request, emit):
            adapter.prompts.append(request)
            await emit({"type": "text_delta", "data": {"text": "obsolete partial"}})
            adapter.started.set()
            await adapter.finish.wait()
            return {"status": "completed", "final_text": ""}

        adapter.run = run_empty
        run, _ = await self.submit()
        adapter.finish.set()
        messages = await self.wait_messages(2)
        self.assertEqual(messages[-1]["content"], "")
        for _ in range(3):
            self.assertEqual((await self.client.get(f"/api/agents/runs/{run['run_id']}")).status_code, 200)
        self.assertEqual(len(self.database.get_messages(self.chat_id)), 2)
        done = [e for e in self.runtime.store.events(run["run_id"]) if e["type"] == "done"]
        self.assertEqual(len(done), 1)
        self.assertEqual(done[0]["data"]["final_text"], "")

    async def test_cross_chat_upload_rejected_and_artifact_owner_checked(self):
        binding = await self.bind()
        upload = await self.client.post("/api/agents/attachments", data={"chat_id": self.chat_id}, files={"file": ("note.txt", b"private to session", "text/plain")})
        self.assertEqual(upload.status_code, 200)
        other_chat = (await self.client.post("/api/chats")).json()["id"]
        other = await self.client.put(f"/api/chats/{other_chat}/agent", json={"agent_id": "hermes", "workspace": {"kind": "managed"}})
        self.assertEqual(other.status_code, 200)
        rejected = await self.client.post("/api/agents/runs", json={"chat_id": other_chat, "client_request_id": "cross", "message": "read", "attachments": [{"attachment_id": upload.json()["attachment_id"]}]})
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(self.runtime.instances[other.json()["session_id"]].prompts, [])
        self.assertEqual(self.database.get_messages(other_chat), [])
        run, adapter = await self.submit()
        workspace = Path(self.runtime.store.session(binding["session_id"])["workspace"])
        source = workspace / "output.txt"
        source.write_text("fixed content")
        await self.runtime.emit(run["run_id"], {"type": "artifact", "data": {"path": source, "name": "output.txt", "mime_type": "text/plain"}})
        artifact = next(e["data"] for e in self.runtime.store.events(run["run_id"]) if e["type"] == "artifact")
        source.write_text("changed later")
        session = await main.agent_gateway.client.http()
        async with session.get(main.agent_gateway.client.base_url + "/v1/artifacts/" + artifact["artifact_id"], headers=main.agent_gateway.client.headers(other_chat)) as response:
            self.assertEqual(response.status, 403)
        adapter.finish.set()
        await self.wait_messages(2)
        await self.client.get(f"/api/agents/runs/{run['run_id']}")
        download = await self.client.get("/api/agents/artifacts/" + artifact["artifact_id"])
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.content, b"fixed content")


class PersistentCrashTests(unittest.IsolatedAsyncioTestCase):
    async def test_abrupt_runner_process_exit_preserves_unknown_and_global_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            script = '''
import asyncio,json,os,sys
from agent_runner.runtime import Runtime
from agent_runner.tests.test_runtime import ControlledAdapter
async def main():
 r=Runtime(sys.argv[1], {"hermes":ControlledAdapter}, {"max_concurrency":1})
 await r.set_enabled("hermes",True)
 await r.create_session("s1","c1","hermes",{"kind":"managed"})
 run=await r.submit("s1","c1","key","approval")
 await r.instances["s1"].started.wait()
 print(json.dumps(r.store.snapshot(run["run_id"])),flush=True)
 os._exit(0)
asyncio.run(main())
'''
            child = await asyncio.create_subprocess_exec(sys.executable, "-B", "-c", script, directory, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await asyncio.wait_for(child.communicate(), 10)
            self.assertEqual(child.returncode, 0, stderr.decode())
            before = json.loads(stdout)
            self.assertEqual(before["status"], "waiting_approval")
            runtime = Runtime(directory, {"hermes": ControlledAdapter}, {"max_concurrency": 1})
            try:
                await runtime.recover()
                await asyncio.gather(*runtime.tasks.values())
                snapshot = runtime.store.lookup("c1", "key")
                self.assertEqual(snapshot["run_id"], before["run_id"])
                self.assertEqual(snapshot["status"], "unknown")
                self.assertEqual(snapshot["interactions"], [])
                self.assertEqual(runtime.instances["s1"].prompts, [])
                self.assertNotIn("done", [e["type"] for e in runtime.store.events(snapshot["run_id"])])
                with self.assertRaises(RunnerError):
                    await runtime.respond(snapshot["run_id"], before["interactions"][0]["interaction_id"], {"decision_id": "allow"})
                await runtime.create_session("s2", "c2", "hermes", {"kind": "managed"})
                with self.assertRaises(RunnerError) as busy:
                    await runtime.submit("s2", "c2", "next", "blocked by global limit")
                self.assertEqual(busy.exception.code, "runner_busy")
                duplicate = await runtime.submit("s1", "c1", "key", "approval")
                self.assertEqual(duplicate["run_id"], before["run_id"])
                self.assertEqual(runtime.instances["s1"].prompts, [])
            finally:
                await runtime.close()

    def test_backup_copies_committed_wal_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "active.db", root / "backup.db"
            connection = sqlite3.connect(source)
            try:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA wal_autocheckpoint=0")
                connection.execute("CREATE TABLE records(value TEXT)")
                connection.execute("INSERT INTO records VALUES ('committed-in-wal')")
                connection.commit()
                self.assertGreater(Path(str(source) + "-wal").stat().st_size, 0)
                backup(source, target)
                with sqlite3.connect(target) as restored:
                    self.assertEqual(restored.execute("SELECT value FROM records").fetchone()[0], "committed-in-wal")
                    self.assertEqual(restored.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                before = target.read_bytes()
                with self.assertRaises(FileExistsError):
                    backup(source, target)
                self.assertEqual(target.read_bytes(), before)
            finally:
                connection.close()


for inherited_name in dir(gateway_fixture.GatewayTests):
    if inherited_name.startswith("test_") and inherited_name not in GatewayAuthorityTests.__dict__:
        setattr(GatewayAuthorityTests, inherited_name, None)


def tearDownModule():
    gateway_fixture.tearDownModule()
