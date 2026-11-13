import asyncio
import importlib.util
import json
import sys
import unittest
from unittest.mock import patch

from agent_runner.adapters.base import AdapterError
from agent_runner.adapters.codex import CodexAdapter, _AppServer
from agent_runner.adapters.codex_responses import (
    UPSTREAM_SETTING,
    ResponsesEndpoint,
    normalize_instructions,
)


class InstructionNormalizationTests(unittest.TestCase):
    def test_preserves_order_and_non_instruction_items(self):
        items = [
            {
                "role": "user",
                "content": [
                    {"type": "input_image", "image_url": "data:image/png;base64,abc"}
                ],
            },
            {
                "role": "developer",
                "id": "msg_1",
                "type": "message",
                "content": [
                    {"type": "input_text", "text": "Permission rules"},
                    {"type": "input_text", "text": "line 2"},
                ],
            },
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "echo",
                "arguments": "{}",
            },
            {"role": "system", "content": "Another native instruction"},
            {"type": "function_call_output", "call_id": "call_1", "output": "done"},
        ]
        payload = {
            "instructions": "Native base",
            "input": items,
            "stream": True,
            "metadata": {"x": "y"},
        }
        normalize_instructions(payload)
        self.assertEqual(
            payload,
            {
                "instructions": "Native base\n\nPermission rules\nline 2\n\nAnother native instruction",
                "input": [items[0], items[2], items[4]],
                "stream": True,
                "metadata": {"x": "y"},
            },
        )

    def test_passthrough_for_requests_without_message_instructions(self):
        for input_ in ("hello", [{"role": "user", "content": "hello"}]):
            payload = {"input": input_, "instructions": "Native base", "stream": True}
            normalize_instructions(payload)
            self.assertEqual(
                payload,
                {"input": input_, "instructions": "Native base", "stream": True},
            )

    def test_host_setting_is_private_and_requires_a_fixed_responses_path(self):
        adapter = CodexAdapter()
        self.assertNotIn(UPSTREAM_SETTING, adapter.settings_schema["properties"])
        self.assertFalse(adapter.settings_schema["additionalProperties"])
        for url in (
            "file:///v1/responses",
            "http://user:password@host/v1/responses",
            "http://host/v1/responses?other=1",
            "http://host/v1/models",
            "http://host:0/v1/responses",
        ):
            with self.subTest(url=url), self.assertRaises(AdapterError):
                adapter.validate_config({UPSTREAM_SETTING: url})


@unittest.skipUnless(
    importlib.util.find_spec("aiohttp"), "requires Runner aiohttp dependency"
)
class ResponsesEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from aiohttp import ClientSession, web

        self.received = []
        self.cancelled = asyncio.Event()
        self.body_sent = asyncio.Event()
        self.behavior = "normal"
        app = web.Application()
        app.router.add_post("/v1/responses", self.upstream)
        app.router.add_route("*", "/redirect-target", self.upstream)
        runner = web.AppRunner(
            app, access_log=None, handler_cancellation=True, shutdown_timeout=0.1
        )
        await runner.setup()
        self.addAsyncCleanup(runner.cleanup)
        await web.TCPSite(runner, "127.0.0.1", 0).start()
        self.endpoint = await ResponsesEndpoint.open(
            f"http://127.0.0.1:{runner.addresses[0][1]}/v1/responses"
        )
        self.addAsyncCleanup(self.endpoint.close)
        self.client = await self.enterAsyncContext(ClientSession())
        self.url = self.endpoint.base_url + "/responses"
        self.auth = {"Authorization": f"Bearer {self.endpoint.token}"}

    async def upstream(self, request):
        from aiohttp import web

        self.received.append(
            (request.path, request.headers.get("Authorization"), await request.read())
        )
        if self.behavior == "redirect":
            raise web.HTTPTemporaryRedirect("/redirect-target")
        if self.behavior == "error":
            return web.Response(
                status=429,
                body=b'{"error":"busy"}',
                headers={"Content-Type": "application/json", "Retry-After": "7"},
            )
        response = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
        await response.prepare(request)
        await response.write(b"data: first\n\n")
        if self.behavior == "hold":
            self.body_sent.set()
            try:
                await asyncio.Future()
            finally:
                self.cancelled.set()
        await response.write(b"data: last\n\n")
        return response

    async def test_only_authorized_exact_post_can_reach_upstream(self):
        for method, url, headers, status in (
            ("POST", self.url, {}, 401),
            ("POST", self.url, {"Authorization": "Bearer wrong"}, 401),
            ("GET", self.url, self.auth, 405),
            ("POST", self.url + "?destination=other", self.auth, 404),
            ("POST", self.endpoint.base_url + "/responses/compact", self.auth, 404),
        ):
            async with self.client.request(
                method, url, headers=headers, json={}
            ) as response:
                self.assertEqual(response.status, status)
        self.assertFalse(self.received)

    async def test_forwards_sse_unchanged_without_forwarding_listener_token(self):
        payload = {
            "input": [
                {"role": "developer", "content": "keep"},
                {"role": "user", "content": "hi"},
            ]
        }
        async with self.client.post(
            self.url, headers=self.auth, json=payload
        ) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(await response.read(), b"data: first\n\ndata: last\n\n")
        path, auth, body = self.received[0]
        self.assertEqual(path, "/v1/responses")
        self.assertIsNone(auth)
        self.assertEqual(
            json.loads(body), {"instructions": "keep", "input": [payload["input"][1]]}
        )

    async def test_rejects_nontext_instruction_before_forwarding(self):
        payload = {
            "input": [
                {
                    "role": "developer",
                    "content": [{"type": "input_image", "image_url": "x"}],
                }
            ]
        }
        async with self.client.post(
            self.url, headers=self.auth, json=payload
        ) as response:
            self.assertEqual(response.status, 400)
            self.assertIn(
                "only input text", (await response.json())["error"]["message"]
            )
        self.assertFalse(self.received)

    async def test_upstream_errors_are_preserved_and_redirects_are_not_followed(self):
        self.behavior = "error"
        async with self.client.post(self.url, headers=self.auth, json={}) as response:
            self.assertEqual(response.status, 429)
            self.assertEqual(response.headers["Retry-After"], "7")
            self.assertEqual(await response.read(), b'{"error":"busy"}')
        self.behavior = "redirect"
        async with self.client.post(self.url, headers=self.auth, json={}) as response:
            self.assertEqual(response.status, 502)
        self.assertEqual([path for path, _, _ in self.received], ["/v1/responses"] * 2)

    async def test_client_disconnect_cancels_stalled_upstream_stream(self):
        self.behavior = "hold"
        response = await self.client.post(self.url, headers=self.auth, json={})
        async with asyncio.timeout(3):
            await self.body_sent.wait()
            self.assertEqual(await response.content.readexactly(13), b"data: first\n\n")
            response.close()
            await self.cancelled.wait()

    async def test_shutdown_cancels_stalled_stream_and_closes_listener(self):
        from aiohttp import ClientConnectorError

        self.behavior = "hold"
        response = await self.client.post(self.url, headers=self.auth, json={})
        try:
            async with asyncio.timeout(3):
                await self.body_sent.wait()
                await self.endpoint.close()
                await self.cancelled.wait()
            with self.assertRaises(ClientConnectorError):
                await self.client.post(self.url, headers=self.auth, json={})
        finally:
            response.close()

    async def test_app_server_eof_releases_its_listener(self):
        from aiohttp import ClientConnectorError

        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "pass",
            stdout=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
        )
        server = _AppServer(process, self.endpoint)
        async with asyncio.timeout(3):
            await server.reader
            await server.close()
        with self.assertRaises(ClientConnectorError):
            await self.client.post(self.url, headers=self.auth, json={})

    async def test_failed_app_server_spawn_releases_its_listener(self):
        from aiohttp import ClientConnectorError

        with patch.object(ResponsesEndpoint, "open", return_value=self.endpoint), patch(
            "agent_runner.adapters.codex.asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError,
        ):
            with self.assertRaises(FileNotFoundError):
                await _AppServer.open(upstream=self.url)
        with self.assertRaises(ClientConnectorError):
            await self.client.post(self.url, headers=self.auth, json={})
