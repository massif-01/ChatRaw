"""Real localhost HTTP transport with a controlled native adapter (simulated)."""

import asyncio
import tempfile
import unittest

import aiohttp
from aiohttp import web

from agent_runner.runtime import Runtime
from agent_runner.server import create_app
from agent_runner.tests.test_runtime import ControlledAdapter


class ServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = Runtime(self.temp.name, {"hermes": ControlledAdapter})
        self.token = "test-runner-only-credential-32-chars"
        self.server = web.AppRunner(
            create_app(self.runtime, self.token), handler_cancellation=True
        )
        await self.server.setup()
        self.site = web.TCPSite(self.server, "127.0.0.1", 0)
        await self.site.start()
        port = self.site._server.sockets[0].getsockname()[1]
        self.base = f"http://127.0.0.1:{port}"
        self.client = aiohttp.ClientSession(
            headers={
                "Authorization": "Bearer " + self.token,
                "X-ChatRaw-Chat-Id": "chat1",
            }
        )
        await self.runtime.set_enabled("hermes", True)

    async def asyncTearDown(self):
        await self.client.close()
        await self.server.cleanup()
        self.temp.cleanup()

    async def create(self):
        async with self.client.post(
            self.base + "/v1/sessions",
            json={
                "session_id": "session1",
                "chat_id": "chat1",
                "agent_id": "hermes",
                "workspace": {"kind": "managed"},
            },
        ) as response:
            self.assertEqual(response.status, 201, await response.text())
            return await response.json()

    async def test_auth_and_ownership_reject_before_native_admission(self):
        async with self.client.get(
            self.base + "/v1/health", headers={"Authorization": "Bearer wrong"}
        ) as response:
            self.assertEqual(response.status, 401)
        await self.create()
        async with self.client.get(
            self.base + "/v1/sessions/session1", headers={"X-ChatRaw-Chat-Id": "other"}
        ) as response:
            self.assertEqual(response.status, 403)
        self.assertEqual(self.runtime.store.active(), [])

    async def test_extra_prompt_context_is_rejected_and_disconnected_client_can_find_run(
        self,
    ):
        await self.create()
        body = {
            "session_id": "session1",
            "chat_id": "chat1",
            "client_request_id": "req1",
            "message": "hello",
            "attachments": [],
        }
        async with self.client.post(
            self.base + "/v1/runs", json={**body, "history": ["injected"]}
        ) as response:
            self.assertEqual(response.status, 400)
        async with self.client.post(self.base + "/v1/runs", json=body) as response:
            self.assertEqual(response.status, 202)
            run = await response.json()
        adapter = self.runtime.instances["session1"]
        await adapter.started.wait()
        stream = await self.client.get(self.base + f"/v1/runs/{run['run_id']}/events")
        await stream.content.readline()
        stream.close()
        self.assertEqual(adapter.stops, 0)
        adapter.finish.set()
        await self.runtime.tasks[run["run_id"]]
        async with self.client.get(
            self.base + "/v1/runs?chat_id=chat1&client_request_id=req1"
        ) as response:
            found = await response.json()
        self.assertEqual(found["run"]["run_id"], run["run_id"])
        self.assertEqual(found["run"]["final_text"], "FINAL")
        async with self.client.get(
            self.base + f"/v1/runs/{run['run_id']}/events"
        ) as response:
            lines = (await response.text()).splitlines()
        self.assertEqual(len(lines), found["run"]["last_seq"])
        self.assertEqual(len(adapter.prompts), 1)
        self.assertEqual(set(adapter.prompts[0]), {"run_id", "message", "attachments"})

    async def test_settings_do_not_accept_host_execution_fields(self):
        async with self.client.put(
            self.base + "/v1/agents/hermes",
            json={"enabled": True, "settings": {"executable": "/tmp/injected"}},
        ) as response:
            self.assertEqual(response.status, 400)
        self.assertEqual(self.runtime.agent_config("hermes"), {})


if __name__ == "__main__":
    unittest.main()
