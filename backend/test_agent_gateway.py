"""ChatRaw ASGI -> real Runner HTTP -> controlled native receiver integration."""

import asyncio
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from aiohttp import web

PREVIOUS_DATA_DIR = os.environ.get("DATA_DIR")
TEST_DATA_DIR = tempfile.mkdtemp(prefix="chatraw-agent-gateway-")
os.environ["DATA_DIR"] = TEST_DATA_DIR
from backend import main
from backend.agent_gateway import GatewayError, RunnerClient
from agent_runner.runtime import Runtime
from agent_runner.server import create_app
from agent_runner.tests.test_runtime import ControlledAdapter


def tearDownModule():
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)
    if PREVIOUS_DATA_DIR is None:
        os.environ.pop("DATA_DIR", None)
    else:
        os.environ["DATA_DIR"] = PREVIOUS_DATA_DIR


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.database = main.Database(str(root / "chatraw.db"))
        plugins = root / "plugins"
        installed = plugins / "installed"
        (installed / "hermes").mkdir(parents=True)
        (installed / "hermes/manifest.json").write_text(
            '{"id":"hermes","name":"Hermes"}'
        )
        self.patches = patch.multiple(
            main,
            db=self.database,
            PLUGINS_DIR=str(plugins),
            PLUGINS_INSTALLED_DIR=str(installed),
            PLUGINS_CONFIG_FILE=str(plugins / "config.json"),
        )
        self.patches.start()
        main.save_plugin_config(
            {
                "plugins": {"hermes": {"enabled": True, "settings_values": {}}},
                "api_keys": {"hermes": "legacy-secret-kept"},
            }
        )
        self.runtime = Runtime(root / "runner", {"hermes": ControlledAdapter})
        self.token = "test-runner-only-credential-32-chars"
        self.server = web.AppRunner(
            create_app(self.runtime, self.token), handler_cancellation=True
        )
        await self.server.setup()
        site = web.TCPSite(self.server, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        self.original_client = main.agent_gateway.client
        main.agent_gateway.client = RunnerClient(f"http://127.0.0.1:{port}", self.token)
        main.agent_gateway.locks.clear()
        await main.agent_gateway.start()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app),
            base_url="http://testserver",
            headers={"Origin": "http://testserver"},
        )
        self.chat_id = (await self.client.post("/api/chats")).json()["id"]

    async def asyncTearDown(self):
        await self.client.aclose()
        await main.agent_gateway.close()
        main.agent_gateway.client = self.original_client
        await self.server.cleanup()
        self.database.get_conn().close()
        self.patches.stop()
        self.temp.cleanup()

    async def bind(self):
        response = await self.client.put(
            f"/api/chats/{self.chat_id}/agent",
            json={"agent_id": "hermes", "workspace": {"kind": "managed"}},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def submit(self, message="hello", key="req1"):
        response = await self.client.post(
            "/api/agents/runs",
            json={
                "chat_id": self.chat_id,
                "client_request_id": key,
                "message": message,
                "attachments": [],
            },
        )
        self.assertEqual(response.status_code, 202, response.text)
        run = response.json()
        adapter = self.runtime.instances[run["session_id"]]
        await asyncio.wait_for(adapter.started.wait(), 1)
        return run, adapter

    async def wait_messages(self, count):
        for _ in range(60):
            response = await self.client.get(f"/api/chats/{self.chat_id}/messages")
            if len(response.json()) >= count:
                return response.json()
            await asyncio.sleep(0.05)
        self.fail("Background display projection did not finish")

    async def test_native_context_and_offline_completion_are_persisted_once(self):
        self.assertEqual(
            self.database.get_conn().execute("PRAGMA synchronous").fetchone()[0], 2
        )
        await self.bind()
        with patch.object(
            main,
            "prepare_chat_submission",
            side_effect=AssertionError("Agent must bypass ordinary context"),
        ):
            run, adapter = await self.submit("native-only")
        self.assertEqual(adapter.prompts[0]["message"], "native-only")
        self.assertEqual(set(adapter.prompts[0]), {"run_id", "message", "attachments"})
        adapter.finish.set()
        messages = await self.wait_messages(2)
        self.assertEqual([m["content"] for m in messages], ["native-only", "FINAL"])
        self.assertTrue(all(m["run_id"] == run["run_id"] for m in messages))
        repeated = await self.client.post(
            "/api/agents/runs",
            json={
                "chat_id": self.chat_id,
                "client_request_id": "req1",
                "message": "native-only",
                "attachments": [],
            },
        )
        self.assertEqual(repeated.json()["run_id"], run["run_id"])
        self.assertEqual(len(self.database.get_messages(self.chat_id)), 2)
        self.assertEqual(len(adapter.prompts), 1)

    async def test_lost_admission_response_is_found_without_new_dispatch(self):
        await self.bind()
        original = main.agent_gateway.client.request

        async def lose_response(method, path, **kwargs):
            result = await original(method, path, **kwargs)
            if method == "POST" and path == "/v1/runs":
                raise GatewayError("runner_unavailable", "Test lost response", 503)
            return result

        with patch.object(
            main.agent_gateway.client, "request", side_effect=lose_response
        ):
            response = await self.client.post(
                "/api/agents/runs",
                json={
                    "chat_id": self.chat_id,
                    "client_request_id": "lost-key",
                    "message": "hello",
                    "attachments": [],
                },
            )
        self.assertEqual(response.status_code, 503)
        found = await self.client.get(
            f"/api/agents/runs?chat_id={self.chat_id}&client_request_id=lost-key"
        )
        self.assertEqual(found.json()["admission"], "accepted")
        run = found.json()["run"]
        adapter = self.runtime.instances[run["session_id"]]
        self.assertEqual(len(adapter.prompts), 1)
        adapter.finish.set()
        await self.wait_messages(2)

    async def test_invalid_context_and_ordinary_bypass_are_rejected_before_saving(self):
        await self.bind()
        response = await self.client.post(
            "/api/agents/runs",
            json={
                "chat_id": self.chat_id,
                "client_request_id": "bad",
                "message": "hello",
                "attachments": [],
                "history": [],
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            set(response.json()["error"]), {"code", "message", "retryable"}
        )
        ordinary = await self.client.post(
            "/api/chat", json={"chat_id": self.chat_id, "message": "bypass"}
        )
        self.assertEqual(ordinary.status_code, 409)
        compact = await self.client.post(f"/api/chats/{self.chat_id}/compact")
        self.assertEqual(compact.status_code, 409)
        self.assertEqual(self.database.get_messages(self.chat_id), [])
        self.assertEqual(self.runtime.store.active(), [])

    async def test_active_delete_rebind_and_plugin_disable(self):
        await self.bind()
        run, adapter = await self.submit("approval")
        deletion = await self.client.delete(f"/api/chats/{self.chat_id}")
        self.assertEqual(deletion.status_code, 409)
        self.assertEqual(deletion.json()["detail"]["code"], "chat_run_active")
        with self.runtime.store.db:
            self.runtime.store.status(run["run_id"], "unknown", "Test unverified task")
        blocked = await self.client.delete(f"/api/chats/{self.chat_id}")
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json()["detail"]["code"], "chat_run_unverified")
        self.assertIn(self.chat_id, [chat.id for chat in self.database.get_chats()])
        rebind = await self.client.put(
            f"/api/chats/{self.chat_id}/agent",
            json={"agent_id": None, "workspace": {"kind": "managed"}},
        )
        self.assertEqual(rebind.status_code, 409)
        disabled = await self.client.post(
            "/api/plugins/hermes/toggle", json={"enabled": False}
        )
        self.assertEqual(disabled.status_code, 200, disabled.text)
        self.assertEqual(adapter.stops, 1)
        result = await self.client.get(f"/api/agents/runs/{run['run_id']}")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            main.load_plugin_config()["api_keys"]["hermes"], "legacy-secret-kept"
        )

    async def test_schema_and_secrets_and_retired_hermes_route(self):
        agents = (await self.client.get("/api/agents")).json()["agents"]
        self.assertIsInstance(
            next(a for a in agents if a["id"] == "hermes")["settings_schema"], dict
        )
        invalid = await self.client.post(
            "/api/plugins/hermes/settings",
            json={"settings": {"executable": "/tmp/command"}},
        )
        self.assertEqual(invalid.status_code, 400)
        config = main.load_plugin_config()
        config["plugins"]["hermes"]["settings_values"] = {
            "api_key": "must-not-echo",
            "headers": {"Authorization": "Bearer must-not-echo"},
            "model": "kept",
        }
        main.save_plugin_config(config)
        listing = await self.client.get("/api/plugins")
        self.assertNotIn("must-not-echo", listing.text)
        self.assertNotIn("legacy-secret-kept", listing.text)
        retired = await self.client.post(
            "/api/hermes/chat", json={"chat_id": self.chat_id, "message": "hello"}
        )
        self.assertEqual(retired.status_code, 410)
        self.assertEqual(self.database.get_messages(self.chat_id), [])

    async def test_artifact_is_downloadable_without_a_live_browser_subscription(self):
        binding = await self.bind()
        run, adapter = await self.submit()
        workspace = Path(self.runtime.store.session(binding["session_id"])["workspace"])
        source = workspace / "result.txt"
        source.write_text("artifact content")
        await self.runtime.emit(
            run["run_id"],
            {
                "type": "artifact",
                "data": {
                    "path": source,
                    "name": "result.txt",
                    "mime_type": "text/plain",
                },
            },
        )
        artifact = next(
            e["data"]
            for e in self.runtime.store.events(run["run_id"])
            if e["type"] == "artifact"
        )
        adapter.finish.set()
        await self.wait_messages(2)
        # Finish event projection even if the display row became visible first.
        await self.client.get(f"/api/agents/runs/{run['run_id']}")
        download = await self.client.get(
            f"/api/agents/artifacts/{artifact['artifact_id']}"
        )
        self.assertEqual(download.status_code, 200, download.text)
        self.assertEqual(download.text, "artifact content")
        self.assertEqual(download.headers["x-content-type-options"], "nosniff")

    async def test_bound_chat_is_not_deleted_by_ordinary_ten_chat_retention(self):
        await self.bind()
        for _ in range(12):
            await self.client.post("/api/chats")
        self.assertTrue(self.database.chat_exists(self.chat_id))
        self.assertIn(self.chat_id, [chat.id for chat in self.database.get_chats()])

    async def test_disable_in_progress_cannot_be_reenabled_by_a_new_submission(self):
        binding = await self.bind()
        original = main.agent_gateway.client.request
        disabled = asyncio.Event()
        release = asyncio.Event()

        async def hold_disable(method, path, **kwargs):
            result = await original(method, path, **kwargs)
            if (
                method == "PUT"
                and path == "/v1/agents/hermes"
                and kwargs.get("body", {}).get("enabled") is False
            ):
                disabled.set()
                await release.wait()
            return result

        with patch.object(
            main.agent_gateway.client, "request", side_effect=hold_disable
        ):
            stopping = asyncio.create_task(
                self.client.post("/api/plugins/hermes/toggle", json={"enabled": False})
            )
            await asyncio.wait_for(disabled.wait(), 1)
            sending = asyncio.create_task(
                self.client.post(
                    "/api/agents/runs",
                    json={
                        "chat_id": self.chat_id,
                        "client_request_id": "race",
                        "message": "must not start",
                        "attachments": [],
                    },
                )
            )
            await asyncio.sleep(0)
            release.set()
            self.assertEqual((await stopping).status_code, 200)
            self.assertEqual((await sending).status_code, 403)
        self.assertFalse(self.runtime.enabled("hermes"))
        self.assertEqual(self.runtime.instances[binding["session_id"]].prompts, [])

    async def test_two_agents_settings_merge_after_delayed_runner_response(self):
        codex = Path(main.PLUGINS_INSTALLED_DIR) / "codex"
        codex.mkdir()
        (codex / "manifest.json").write_text('{"id":"codex"}')
        self.runtime.factories["codex"] = ControlledAdapter
        config = main.load_plugin_config()
        config["plugins"]["codex"] = {"enabled": True, "settings_values": {}}
        main.save_plugin_config(config)
        original = main.agent_gateway.client.request
        entered, release = asyncio.Event(), asyncio.Event()

        async def delayed(method, path, **kwargs):
            result = await original(method, path, **kwargs)
            if path == "/v1/agents/hermes" and kwargs.get("body", {}).get(
                "settings"
            ) == {"model": "model-a"}:
                entered.set()
                await release.wait()
            return result

        with patch.object(main.agent_gateway.client, "request", side_effect=delayed):
            first = asyncio.create_task(
                self.client.post(
                    "/api/plugins/hermes/settings",
                    json={"settings": {"model": "model-a"}},
                )
            )
            await asyncio.wait_for(entered.wait(), 1)
            second = await self.client.post(
                "/api/plugins/codex/settings", json={"settings": {"model": "model-b"}}
            )
            release.set()
            self.assertEqual((await first).status_code, 200)
            self.assertEqual(second.status_code, 200)
        saved = main.load_plugin_config()
        self.assertEqual(
            saved["plugins"]["hermes"]["settings_values"], {"model": "model-a"}
        )
        self.assertEqual(
            saved["plugins"]["codex"]["settings_values"], {"model": "model-b"}
        )
        self.assertEqual(saved["api_keys"]["hermes"], "legacy-secret-kept")

    async def test_multipart_upload_reaches_only_the_bound_native_run(self):
        binding = await self.bind()
        upload = await self.client.post(
            "/api/agents/attachments",
            data={"chat_id": self.chat_id},
            files={"file": ("note.txt", b"local attachment", "text/plain")},
        )
        self.assertEqual(upload.status_code, 200, upload.text)
        self.assertNotIn("path", upload.json())
        response = await self.client.post(
            "/api/agents/runs",
            json={
                "chat_id": self.chat_id,
                "client_request_id": "attachment-run",
                "message": "read this",
                "attachments": [{"attachment_id": upload.json()["attachment_id"]}],
            },
        )
        self.assertEqual(response.status_code, 202, response.text)
        adapter = self.runtime.instances[binding["session_id"]]
        await asyncio.wait_for(adapter.started.wait(), 1)
        delivered = adapter.prompts[0]["attachments"][0]
        self.assertEqual(delivered["path"].read_bytes(), b"local attachment")
        adapter.finish.set()


if __name__ == "__main__":
    unittest.main()
