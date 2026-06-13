import asyncio
import json
import os
import shutil
import sys
import tempfile
import unittest

from aiohttp import web
from starlette.routing import Match

PREVIOUS_DATA_DIR = os.environ.get("DATA_DIR")
TEST_DATA_DIR = tempfile.mkdtemp(prefix="chatraw-hermes-smoke-test-")
os.environ["DATA_DIR"] = TEST_DATA_DIR

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend import main  # noqa: E402
from backend.hermes_fake_server import FakeHermesServer  # noqa: E402


def tearDownModule():
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)
    if PREVIOUS_DATA_DIR is None:
        os.environ.pop("DATA_DIR", None)
    else:
        os.environ["DATA_DIR"] = PREVIOUS_DATA_DIR


class JsonRequest:
    def __init__(
        self,
        body=None,
        origin=None,
        url="http://testserver/api/hermes/chat",
        headers=None,
        disconnected=False,
        fetch_site="same-origin",
    ):
        self.body = body if body is not None else {}
        self.headers = dict(headers or {})
        if origin:
            self.headers["origin"] = origin
        if fetch_site is not None and "sec-fetch-site" not in self.headers:
            self.headers["sec-fetch-site"] = fetch_site
        self.url = url
        self.disconnected = disconnected

    async def json(self):
        return self.body

    async def is_disconnected(self):
        return self.disconnected


class HermesSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await main.close_http_session()
        shutil.rmtree(main.PLUGINS_DIR, ignore_errors=True)
        os.makedirs(main.PLUGINS_INSTALLED_DIR, exist_ok=True)
        main.save_plugin_config({"plugins": {}, "api_keys": {}})

        conn = main.db.get_conn()
        cursor = conn.cursor()
        for table in (
            "chat_skill_activations",
            "chat_compactions",
            "messages",
            "chats",
        ):
            cursor.execute(f"DELETE FROM {table}")
        conn.commit()
        main._context_compaction_locks.clear()
        main._active_hermes_runs.clear()

        self.fake = FakeHermesServer()
        self.runner = web.AppRunner(self.fake.create_app())
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await self.site.start()
        sockets = self.site._server.sockets
        self.fake_base_url = f"http://127.0.0.1:{sockets[0].getsockname()[1]}/v1"
        self.enable_hermes(api_mode=main.HERMES_API_MODE_RUNS, session_key="trusted-session-key")

    async def asyncTearDown(self):
        await main.close_http_session()
        await self.runner.cleanup()
        main._active_hermes_runs.clear()

    def enable_hermes(
        self,
        enabled=True,
        installed=True,
        api_key="secret",
        session_key="",
        api_mode=None,
    ):
        if installed:
            plugin_dir = os.path.join(main.PLUGINS_INSTALLED_DIR, main.HERMES_PLUGIN_ID)
            os.makedirs(plugin_dir, exist_ok=True)
            with open(os.path.join(plugin_dir, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump({"id": main.HERMES_PLUGIN_ID}, f)
        settings_values = {
            "baseUrl": self.fake_base_url,
            "model": "hermes-agent",
        }
        if api_mode is not None:
            settings_values["apiMode"] = api_mode
        config = {
            "plugins": {
                main.HERMES_PLUGIN_ID: {
                    "enabled": enabled,
                    "settings_values": settings_values,
                }
            },
            "api_keys": {},
        }
        if api_key:
            config["api_keys"][main.HERMES_API_KEY_SERVICE_ID] = api_key
        if session_key:
            config["api_keys"][main.HERMES_SESSION_KEY_SERVICE_ID] = session_key
        main.save_plugin_config(config)

    def configure_chat(self, stream=True):
        settings = main.db.get_settings()
        settings.chat_settings.stream = stream
        settings.chat_settings.system_prompt = "Smoke system prompt."
        main.db.save_settings(settings)

    def decode_result(self, result):
        if isinstance(result, main.JSONResponse):
            return result.status_code, json.loads(result.body.decode("utf-8"))
        return 200, result

    async def collect_stream(self, response, chunks):
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk)

    async def wait_until(self, predicate, timeout=3):
        deadline = asyncio.get_running_loop().time() + timeout
        last_error = None
        while asyncio.get_running_loop().time() < deadline:
            try:
                value = predicate()
            except Exception as exc:
                last_error = exc
                value = None
            if value:
                return value
            await asyncio.sleep(0.01)
        if last_error:
            raise AssertionError(f"condition was not met; last error: {last_error}")
        raise AssertionError("condition was not met before timeout")

    async def start_stream(self, body, disconnected=False):
        response = await main.hermes_chat(JsonRequest(body, disconnected=disconnected))
        chunks = []
        task = asyncio.create_task(self.collect_stream(response, chunks))
        return chunks, task

    async def read_stream_chunk(self, iterator, timeout=3):
        chunk = await asyncio.wait_for(anext(iterator), timeout=timeout)
        return chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk

    async def wait_for_pending_run(self):
        run_id = await self.wait_until(self.fake.latest_run_id)

        def pending_record():
            record = main.get_active_hermes_run(run_id)
            if record and record.get("pending_approval"):
                return record
            return None

        record = await self.wait_until(pending_record)
        return run_id, record

    def approval_request(self, chat_id, choice, **extra):
        body = {"chat_id": chat_id, "choice": choice, "resolve_all": False}
        body.update(extra)
        return JsonRequest(body, url="http://testserver/api/hermes/runs/fake/approval")

    async def approve(self, run_id, chat_id, choice):
        result = await main.hermes_run_approval(run_id, self.approval_request(chat_id, choice))
        return self.decode_result(result)

    async def test_loopback_base_url_works_for_remote_browser_origin(self):
        result = await main.hermes_health(JsonRequest(
            url="http://10.10.99.99:51111/api/hermes/health",
            origin="http://10.10.99.99:51111",
        ))
        status, data = self.decode_result(result)

        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["base_url"], self.fake_base_url)
        self.assertEqual(len(self.fake.model_requests), 1)
        self.assertEqual(self.fake.model_requests[0]["headers"]["Authorization"], "Bearer secret")
        self.assertNotIn("X-Hermes-Session-Id", self.fake.model_requests[0]["headers"])

    def test_approval_route_accepts_opaque_run_id_path_segments(self):
        scope = {
            "type": "http",
            "path": "/api/hermes/runs/run/quoted/approval",
            "method": "POST",
            "headers": [],
        }
        matches = []
        for route in main.app.router.routes:
            match, child_scope = route.matches(scope)
            if match == Match.FULL and getattr(route, "endpoint", None) == main.hermes_run_approval:
                matches.append(child_scope)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["path_params"]["run_id"], "run/quoted")

    async def test_real_http_sse_approval_deny_blocks_without_saving_assistant(self):
        self.configure_chat(stream=True)
        chunks, task = await self.start_stream({"message": "approval deny dangerous action"})
        run_id, record = await self.wait_for_pending_run()

        status, data = await self.approve(run_id, record["chat_id"], "deny")
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "blocked")

        await asyncio.wait_for(task, timeout=3)
        stream = "".join(chunks)
        self.assertIn('"approval.request"', stream)
        self.assertIn('"approval.responded"', stream)
        self.assertIn('"run.failed"', stream)
        self.assertIn("BLOCKED", stream)
        self.assertNotIn("approved once answer", stream)
        self.assertNotIn('"done": true', stream)

        self.assertEqual(len(self.fake.approval_requests), 1)
        approval = self.fake.approval_requests[0]
        self.assertEqual(approval["json"], {"choice": "deny", "resolve_all": False})
        self.assertEqual(approval["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(approval["headers"]["X-Hermes-Session-Id"], f"chatraw-{record['chat_id']}")
        self.assertEqual(approval["headers"]["X-Hermes-Session-Key"], "trusted-session-key")

        messages = main.db.get_messages(record["chat_id"])
        self.assertEqual(len(messages), 1)
        self.assertNotIn(run_id, main._active_hermes_runs)

    async def test_real_http_sse_approval_once_completes_and_saves_final_content(self):
        self.configure_chat(stream=True)
        chunks, task = await self.start_stream({"message": "approval once"})
        run_id, record = await self.wait_for_pending_run()

        status, data = await self.approve(run_id, record["chat_id"], "once")
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "running")

        await asyncio.wait_for(task, timeout=3)
        stream = "".join(chunks)
        self.assertIn('"tool.completed"', stream)
        self.assertIn('"duration_ms": 0', stream)
        self.assertIn("approved once answer", stream)
        self.assertIn('"done": true', stream)

        messages = main.db.get_messages(record["chat_id"])
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[1].content, "approved once answer")
        self.assertNotIn("dangerous command", messages[1].content)
        self.assertNotIn(run_id, main._active_hermes_runs)

    async def test_real_http_sse_session_approval_allows_later_matching_command(self):
        self.configure_chat(stream=True)
        chunks, task = await self.start_stream({"message": "approval session"})
        run_id, record = await self.wait_for_pending_run()
        chat_id = record["chat_id"]

        status, data = await self.approve(run_id, chat_id, "session")
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        await asyncio.wait_for(task, timeout=3)
        self.assertIn("approved session answer", "".join(chunks))
        self.assertEqual(len(self.fake.approval_requests), 1)
        self.assertIn(f"chatraw-{chat_id}", self.fake.session_allowed)

        second_chunks, second_task = await self.start_stream({
            "chat_id": chat_id,
            "message": "session followup matching command",
        })
        await asyncio.wait_for(second_task, timeout=3)
        second_stream = "".join(second_chunks)
        self.assertNotIn('"approval.request"', second_stream)
        self.assertIn("session reused answer", second_stream)
        self.assertEqual(len(self.fake.approval_requests), 1)
        self.assertEqual(self.fake.run_requests[-1]["headers"]["X-Hermes-Session-Id"], f"chatraw-{chat_id}")
        self.assertEqual(self.fake.run_requests[-1]["headers"]["X-Hermes-Session-Key"], "trusted-session-key")

        messages = main.db.get_messages(chat_id)
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[-1].content, "session reused answer")

    async def test_real_http_sse_disconnect_stops_and_stale_approval_does_not_forward(self):
        self.configure_chat(stream=True)
        chunks, task = await self.start_stream({"message": "stop generation"}, disconnected=True)
        run_id = await self.wait_until(self.fake.latest_run_id)

        await asyncio.wait_for(task, timeout=3)
        stream = "".join(chunks)
        self.assertIn('"chat_id"', stream)
        self.assertNotIn('"done": true', stream)
        self.assertEqual(len(self.fake.stop_requests), 1)
        self.assertEqual(self.fake.stop_requests[0]["run_id"], run_id)
        self.assertNotIn(run_id, main._active_hermes_runs)

        chat_id = self.fake.run_requests[0]["headers"]["X-Hermes-Session-Id"].replace("chatraw-", "", 1)
        before = len(self.fake.approval_requests)
        result = await main.hermes_run_approval(
            run_id,
            JsonRequest(
                {"chat_id": chat_id, "choice": "once", "resolve_all": False},
                url=f"http://testserver/api/hermes/runs/{run_id}/approval",
            ),
        )
        status, data = self.decode_result(result)
        self.assertEqual(status, 404)
        self.assertFalse(data["success"])
        self.assertEqual(len(self.fake.approval_requests), before)

    async def test_real_http_sse_stream_close_stops_quiet_run(self):
        self.configure_chat(stream=True)
        response = await main.hermes_chat(JsonRequest({"message": "quiet stop generation"}))
        iterator = response.body_iterator

        first_chunk = await self.read_stream_chunk(iterator)
        second_chunk = await self.read_stream_chunk(iterator)
        self.assertIn('"chat_id"', first_chunk)
        self.assertIn('"run.started"', second_chunk)
        run_id = await self.wait_until(self.fake.latest_run_id)
        self.assertIn(run_id, main._active_hermes_runs)

        await iterator.aclose()

        await self.wait_until(lambda: len(self.fake.stop_requests) == 1)
        self.assertEqual(self.fake.stop_requests[0]["run_id"], run_id)
        self.assertNotIn(run_id, main._active_hermes_runs)

    async def test_real_http_sse_terminal_stopped_event_does_not_trigger_extra_stop_request(self):
        self.configure_chat(stream=True)

        chunks, task = await self.start_stream({"message": "externally stopped run"})
        run_id = await self.wait_until(self.fake.latest_run_id)
        await asyncio.wait_for(task, timeout=3)
        stream = "".join(chunks)

        self.assertIn('"type": "run.cancelled"', stream)
        self.assertIn('"done": true', stream)
        self.assertNotIn("ended before completion", stream)
        self.assertEqual(self.fake.stop_requests, [])
        self.assertNotIn(run_id, main._active_hermes_runs)

    async def test_real_http_sse_non_stream_approval_requires_stream_output_and_stops(self):
        self.configure_chat(stream=False)

        result = await main.hermes_chat(JsonRequest({"message": "non stream approval once"}))
        status, data = self.decode_result(result)

        self.assertEqual(status, 409)
        self.assertIn("Hermes Runs approval requires stream output", data["error"])
        self.assertEqual(len(self.fake.stop_requests), 1)
        run_id = self.fake.run_requests[0]["run_id"]
        self.assertEqual(self.fake.stop_requests[0]["run_id"], run_id)
        self.assertNotIn(run_id, main._active_hermes_runs)

        chat_id = self.fake.run_requests[0]["headers"]["X-Hermes-Session-Id"].replace("chatraw-", "", 1)
        messages = main.db.get_messages(chat_id)
        self.assertEqual(len(messages), 1)

    async def test_real_approval_bridge_rejects_invalid_requests_without_forwarding(self):
        self.configure_chat(stream=True)
        chunks, task = await self.start_stream({"message": "approval once invalid checks"})
        run_id, record = await self.wait_for_pending_run()
        chat_id = record["chat_id"]

        cases = [
            ("always", run_id, {"chat_id": chat_id, "choice": "always", "resolve_all": False}, 400, "same-origin", True),
            ("transport", run_id, {"chat_id": chat_id, "choice": "once", "apiKey": "evil"}, 400, "same-origin", True),
            ("chat mismatch", run_id, {"chat_id": "other-chat", "choice": "once"}, 403, "same-origin", True),
            ("cross site", run_id, {"chat_id": chat_id, "choice": "once"}, 403, "cross-site", True),
            ("unknown", "missing-run", {"chat_id": chat_id, "choice": "once"}, 404, "same-origin", True),
            ("plugin disabled", run_id, {"chat_id": chat_id, "choice": "once"}, 403, "same-origin", False),
        ]

        for label, target_run_id, body, expected_status, fetch_site, enabled in cases:
            with self.subTest(label=label):
                self.enable_hermes(
                    enabled=enabled,
                    api_mode=main.HERMES_API_MODE_RUNS,
                    session_key="trusted-session-key",
                )
                before = len(self.fake.approval_requests)
                result = await main.hermes_run_approval(
                    target_run_id,
                    JsonRequest(
                        body,
                        url=f"http://testserver/api/hermes/runs/{target_run_id}/approval",
                        fetch_site=fetch_site,
                    ),
                )
                status, data = self.decode_result(result)
                self.assertEqual(status, expected_status)
                self.assertFalse(data["success"])
                self.assertEqual(len(self.fake.approval_requests), before)

        self.enable_hermes(api_mode=main.HERMES_API_MODE_RUNS, session_key="trusted-session-key")
        status, data = await self.approve(run_id, chat_id, "deny")
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        await asyncio.wait_for(task, timeout=3)
        self.assertIn("BLOCKED", "".join(chunks))


if __name__ == "__main__":
    unittest.main()
