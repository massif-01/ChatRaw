import asyncio
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


TEST_DATA_DIR = tempfile.mkdtemp(prefix="chatraw-linkdb-agent-test-")
os.environ["DATA_DIR"] = TEST_DATA_DIR

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend import main  # noqa: E402


LINKDB_AGENT_ENV_KEYS = (
    "CHATRAW_LINKDB_AGENT_ENABLED",
    "CHATRAW_LINKDB_AGENT_BASE_URL",
    "CHATRAW_LINKDB_AGENT_API_KEY",
    "CHATRAW_LINKDB_AGENT_TIMEOUT_SECONDS",
    "CHATRAW_LINKDB_AGENT_PRINCIPAL",
)


def tearDownModule():
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)


class JsonRequest:
    def __init__(
        self,
        body=None,
        raw_body=None,
        body_chunks=None,
        url="http://testserver/api/linkdb-agent/chat",
        headers=None,
        fetch_site="same-origin",
    ):
        self.body = body if body is not None else {}
        self.raw_body = (
            raw_body
            if raw_body is not None
            else json.dumps(self.body, ensure_ascii=False).encode("utf-8")
        )
        self.body_chunks = list(body_chunks) if body_chunks is not None else [self.raw_body]
        self.stream_reads = 0
        self.url = url
        self.headers = dict(headers or {})
        if fetch_site is not None and "sec-fetch-site" not in self.headers:
            self.headers["sec-fetch-site"] = fetch_site

    async def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body

    async def stream(self):
        for chunk in self.body_chunks:
            self.stream_reads += 1
            yield chunk


class FakeContent:
    def __init__(self, payload):
        self.payload = payload
        self.offset = 0
        self.read_sizes = []

    async def read(self, size):
        self.read_sizes.append(size)
        chunk = self.payload[self.offset:self.offset + size]
        self.offset += len(chunk)
        return chunk


class FakeResponse:
    def __init__(self, status=200, json_data=None, raw_data=None):
        self.status = status
        if raw_data is None:
            raw_data = json.dumps(json_data if json_data is not None else {}).encode("utf-8")
        self.content = FakeContent(raw_data)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeSession:
    def __init__(self, get_response=None, post_response=None, get_error=None, post_error=None):
        self.get_response = get_response or FakeResponse(
            json_data={
                "status": "healthy",
                "service": "chatraw-agent",
                "version": "0.1.0",
            }
        )
        self.post_response = post_response or FakeResponse(
            json_data={
                "answer": "ok",
                "need_clarification": False,
                "clarification_question": None,
                "trace": [],
                "result_sets": [],
            }
        )
        self.get_error = get_error
        self.post_error = post_error
        self.gets = []
        self.posts = []

    def get(self, url, **kwargs):
        self.gets.append({"url": url, **kwargs})
        if self.get_error:
            raise self.get_error
        return self.get_response

    def post(self, url, **kwargs):
        self.posts.append({"url": url, **kwargs})
        if self.post_error:
            raise self.post_error
        return self.post_response


class FakeProxyResponse:
    status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def json(self):
        return {"ok": True}

    async def text(self):
        return "ok"


class FakeProxySession:
    def __init__(self):
        self.requests = []

    def request(self, method, url, **kwargs):
        self.requests.append({"method": method, "url": url, **kwargs})
        return FakeProxyResponse()


class FakeRateURL:
    def __init__(self, path):
        self.path = path


class FakeRateClient:
    host = "203.0.113.5"


class FakeRateRequest:
    def __init__(self, path):
        self.url = FakeRateURL(path)
        self.headers = {}
        self.client = FakeRateClient()


class LinkDBAgentBridgeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.original_environment = {
            key: os.environ.get(key)
            for key in LINKDB_AGENT_ENV_KEYS
        }
        for key in LINKDB_AGENT_ENV_KEYS:
            os.environ.pop(key, None)

        self.original_cors_origins = main.CORS_ORIGINS
        main.CORS_ORIGINS = "*"
        shutil.rmtree(main.PLUGINS_INSTALLED_DIR, ignore_errors=True)
        os.makedirs(main.PLUGINS_INSTALLED_DIR, exist_ok=True)
        main.save_plugin_config({"plugins": {}, "api_keys": {}})

        connection = main.db.get_conn()
        cursor = connection.cursor()
        for table in (
            "chat_skill_activations",
            "chat_compactions",
            "messages",
            "chats",
        ):
            cursor.execute(f"DELETE FROM {table}")
        connection.commit()
        main._context_compaction_locks.clear()

    def tearDown(self):
        for key, value in self.original_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        main.CORS_ORIGINS = self.original_cors_origins

    def configure_bridge(
        self,
        base_url="http://agent.internal:8767/v1",
        api_key="agent-secret-key",
        timeout="120",
        principal="organization-default/chatraw-local",
    ):
        os.environ["CHATRAW_LINKDB_AGENT_ENABLED"] = "true"
        os.environ["CHATRAW_LINKDB_AGENT_BASE_URL"] = base_url
        os.environ["CHATRAW_LINKDB_AGENT_API_KEY"] = api_key
        os.environ["CHATRAW_LINKDB_AGENT_TIMEOUT_SECONDS"] = timeout
        if principal is None:
            os.environ.pop("CHATRAW_LINKDB_AGENT_PRINCIPAL", None)
        else:
            os.environ["CHATRAW_LINKDB_AGENT_PRINCIPAL"] = principal

    def patch_session(self, fake_session):
        original = main.get_http_session

        async def fake_get_http_session():
            return fake_session

        main.get_http_session = fake_get_http_session
        self.addCleanup(lambda: setattr(main, "get_http_session", original))
        return fake_session

    def decode_result(self, result):
        if isinstance(result, main.JSONResponse):
            return result.status_code, json.loads(result.body.decode("utf-8"))
        return 200, result

    def chat_count(self):
        cursor = main.db.get_conn().cursor()
        cursor.execute("SELECT COUNT(*) AS count FROM chats")
        return cursor.fetchone()["count"]

    def message_count(self):
        cursor = main.db.get_conn().cursor()
        cursor.execute("SELECT COUNT(*) AS count FROM messages")
        return cursor.fetchone()["count"]

    def test_routes_and_frontend_allowlist_are_present(self):
        route_methods = {
            route.path: getattr(route, "methods", set())
            for route in main.app.routes
        }
        self.assertIn("GET", route_methods["/api/linkdb-agent/health"])
        self.assertIn("POST", route_methods["/api/linkdb-agent/chat"])

        app_js = Path(main.BACKEND_DIR, "static", "app.js").read_text(encoding="utf-8")
        app_min_js = Path(main.BACKEND_DIR, "static", "app.min.js").read_text(encoding="utf-8")
        for source in (app_js, app_min_js):
            self.assertIn("chatraw-linkdb-agent", source)
            self.assertIn("/api/linkdb-agent/chat", source)
        self.assertIn("NON_STREAMING_CHAT_ENDPOINTS", app_js)

    async def test_disabled_and_missing_environment_fail_closed(self):
        fake_session = self.patch_session(FakeSession())

        result = await main.linkdb_agent_health(
            JsonRequest(url="http://testserver/api/linkdb-agent/health")
        )
        status, data = self.decode_result(result)
        self.assertEqual(status, 503)
        self.assertEqual(data["code"], "agent_unavailable")
        self.assertFalse(data["success"])

        os.environ["CHATRAW_LINKDB_AGENT_ENABLED"] = "true"
        result = await main.linkdb_agent_health(
            JsonRequest(url="http://testserver/api/linkdb-agent/health")
        )
        status, data = self.decode_result(result)
        self.assertEqual(status, 503)
        self.assertEqual(data["code"], "agent_unavailable")

        main.save_plugin_config({
            "plugins": {
                "chatraw-linkdb-agent": {
                    "enabled": True,
                    "settings_values": {
                        "baseUrl": "http://browser-controlled.invalid/v1",
                        "requestTimeoutSeconds": 1,
                    },
                }
            },
            "api_keys": {"chatraw-linkdb-agent": "browser-stored-secret"},
        })
        result = await main.linkdb_agent_health(
            JsonRequest(url="http://testserver/api/linkdb-agent/health")
        )
        status, data = self.decode_result(result)
        self.assertEqual(status, 503)
        self.assertNotIn("browser", json.dumps(data))
        self.assertEqual(fake_session.gets, [])

    def test_legacy_browser_key_migration_is_persistent_and_idempotent(self):
        legacy_config = {
            "plugins": {
                main.LINKDB_AGENT_PLUGIN_ID: {
                    "enabled": True,
                    "settings_values": {
                        "baseUrl": "https://browser.invalid/v1",
                        "requestTimeoutSeconds": 1,
                        "polish": False,
                        "showTrace": True,
                    },
                },
            },
            "api_keys": {
                main.LINKDB_AGENT_PLUGIN_ID: "legacy-agent-secret",
                "other-plugin": "other-plugin-secret",
            },
        }
        Path(main.PLUGINS_CONFIG_FILE).write_text(
            json.dumps(legacy_config),
            encoding="utf-8",
        )

        first = main.load_plugin_config()
        second = main.load_plugin_config()
        persisted = json.loads(Path(main.PLUGINS_CONFIG_FILE).read_text(encoding="utf-8"))

        for config in (first, second, persisted):
            self.assertNotIn(main.LINKDB_AGENT_PLUGIN_ID, config["api_keys"])
            self.assertEqual(config["api_keys"]["other-plugin"], "other-plugin-secret")
            self.assertEqual(
                config["plugins"][main.LINKDB_AGENT_PLUGIN_ID]["settings_values"],
                {"polish": False, "showTrace": True},
            )

        for _ in range(2):
            config = main.load_plugin_config()
            config["api_keys"][main.LINKDB_AGENT_PLUGIN_ID] = "reintroduced-secret"
            main.save_plugin_config(config)
            self.assertNotIn(
                main.LINKDB_AGENT_PLUGIN_ID,
                main.load_plugin_config()["api_keys"],
            )

    async def test_reserved_plugin_settings_and_manifest_are_allowlisted(self):
        plugin_dir = Path(main.PLUGINS_INSTALLED_DIR, main.LINKDB_AGENT_PLUGIN_ID)
        plugin_dir.mkdir(parents=True)
        legacy_manifest = {
            "id": main.LINKDB_AGENT_PLUGIN_ID,
            "main": "main.js",
            "proxy": [{"id": main.LINKDB_AGENT_PLUGIN_ID}],
            "settings": [
                {"id": "baseUrl", "type": "string"},
                {"id": "polish", "type": "boolean"},
                {"id": "showTrace", "type": "boolean"},
                {"id": "requestTimeoutSeconds", "type": "number"},
            ],
        }
        Path(plugin_dir, "manifest.json").write_text(
            json.dumps(legacy_manifest),
            encoding="utf-8",
        )
        Path(plugin_dir, "main.js").write_text("", encoding="utf-8")
        Path(main.PLUGINS_CONFIG_FILE).write_text(json.dumps({
            "plugins": {
                main.LINKDB_AGENT_PLUGIN_ID: {
                    "enabled": True,
                    "settings_values": {
                        "baseUrl": "https://browser.invalid/v1",
                        "requestTimeoutSeconds": 1,
                        "polish": False,
                        "showTrace": True,
                    },
                },
            },
            "api_keys": {main.LINKDB_AGENT_PLUGIN_ID: "legacy-agent-secret"},
        }), encoding="utf-8")

        listed = next(
            plugin
            for plugin in main.get_installed_plugins()
            if plugin["id"] == main.LINKDB_AGENT_PLUGIN_ID
        )
        self.assertEqual(
            [setting["id"] for setting in listed["settings"]],
            ["polish", "showTrace"],
        )
        self.assertNotIn("proxy", listed)
        self.assertEqual(
            listed["settings_values"],
            {"polish": False, "showTrace": True},
        )
        self.assertNotIn("browser.invalid", json.dumps(listed))

        for invalid_settings in (
            {"baseUrl": "https://browser.invalid/v1"},
            {"polish": "false"},
            {"showTrace": 0},
        ):
            with self.subTest(invalid_settings=invalid_settings):
                result = await main.update_plugin_settings(
                    main.LINKDB_AGENT_PLUGIN_ID,
                    main.PluginSettingsUpdate(settings=invalid_settings),
                )
                status, data = self.decode_result(result)
                self.assertEqual(status, 400)
                self.assertIn("Only polish and showTrace", data["error"])

        accepted = await main.update_plugin_settings(
            main.LINKDB_AGENT_PLUGIN_ID,
            main.PluginSettingsUpdate(settings={"polish": False, "showTrace": False}),
        )
        accepted_status, accepted_data = self.decode_result(accepted)
        self.assertEqual(accepted_status, 200)
        self.assertTrue(accepted_data["success"])
        self.assertEqual(
            main.get_linkdb_agent_preferences(),
            {"polish": False, "showTrace": False},
        )

        manifest_result = await main.get_plugin_manifest(main.LINKDB_AGENT_PLUGIN_ID)
        manifest_status, manifest_data = self.decode_result(manifest_result)
        self.assertEqual(manifest_status, 200)
        self.assertNotIn("proxy", manifest_data)
        self.assertEqual(
            [setting["id"] for setting in manifest_data["settings"]],
            ["polish", "showTrace"],
        )
        self.assertEqual(
            manifest_data["settings_values"],
            {"polish": False, "showTrace": False},
        )

    async def test_reserved_plugin_upload_migration_is_idempotent(self):
        legacy_manifest = {
            "id": main.LINKDB_AGENT_PLUGIN_ID,
            "main": "main.js",
            "proxy": [{"id": main.LINKDB_AGENT_PLUGIN_ID}],
            "settings": [
                {"id": "baseUrl", "type": "string"},
                {"id": "polish", "type": "boolean"},
                {"id": "showTrace", "type": "boolean"},
                {"id": "requestTimeoutSeconds", "type": "number"},
            ],
        }
        archive_buffer = io.BytesIO()
        with zipfile.ZipFile(archive_buffer, "w") as archive:
            archive.writestr(
                "chatraw-linkdb-agent/manifest.json",
                json.dumps(legacy_manifest),
            )
            archive.writestr("chatraw-linkdb-agent/main.js", "")
        archive_bytes = archive_buffer.getvalue()

        for _ in range(2):
            Path(main.PLUGINS_CONFIG_FILE).write_text(json.dumps({
                "plugins": {
                    main.LINKDB_AGENT_PLUGIN_ID: {
                        "enabled": True,
                        "settings_values": {
                            "baseUrl": "https://browser.invalid/v1",
                            "polish": False,
                        },
                    },
                },
                "api_keys": {
                    main.LINKDB_AGENT_PLUGIN_ID: "legacy-agent-secret",
                    "other-plugin": "other-plugin-secret",
                },
            }), encoding="utf-8")
            upload = main.UploadFile(
                filename="chatraw-linkdb-agent.zip",
                file=io.BytesIO(archive_bytes),
            )

            result = await main.upload_plugin(upload)
            status, data = self.decode_result(result)

            self.assertEqual(status, 200)
            self.assertTrue(data["success"])
            self.assertNotIn("proxy", data["manifest"])
            self.assertEqual(
                [setting["id"] for setting in data["manifest"]["settings"]],
                ["polish", "showTrace"],
            )
            config = main.load_plugin_config()
            self.assertNotIn(main.LINKDB_AGENT_PLUGIN_ID, config["api_keys"])
            self.assertEqual(config["api_keys"]["other-plugin"], "other-plugin-secret")
            self.assertEqual(
                config["plugins"][main.LINKDB_AGENT_PLUGIN_ID]["settings_values"],
                {},
            )
            installed_manifest = json.loads(Path(
                main.PLUGINS_INSTALLED_DIR,
                main.LINKDB_AGENT_PLUGIN_ID,
                "manifest.json",
            ).read_text(encoding="utf-8"))
            self.assertNotIn("proxy", installed_manifest)
            self.assertEqual(
                [setting["id"] for setting in installed_manifest["settings"]],
                ["polish", "showTrace"],
            )

    async def test_reserved_agent_service_id_is_closed_across_generic_key_apis(self):
        fake_session = self.patch_session(FakeProxySession())

        save_result = await main.save_api_key(JsonRequest({
            "service_id": main.LINKDB_AGENT_PLUGIN_ID,
            "api_key": "browser-secret",
        }))
        save_status, save_data = self.decode_result(save_result)
        self.assertEqual(save_status, 400)
        self.assertIn("Reserved", save_data["error"])

        proxy_result = await main.proxy_request(main.ProxyRequest(
            service_id=main.LINKDB_AGENT_PLUGIN_ID,
            url="https://collector.example/capture",
        ))
        proxy_status, proxy_data = self.decode_result(proxy_result)
        self.assertEqual(proxy_status, 400)
        self.assertIn("Reserved", proxy_data["error"])

        upload_result = await main.proxy_upload(
            file=None,
            service_id=main.LINKDB_AGENT_PLUGIN_ID,
            url="https://collector.example/upload",
        )
        upload_status, upload_data = self.decode_result(upload_result)
        self.assertEqual(upload_status, 400)
        self.assertIn("Reserved", upload_data["error"])
        self.assertEqual(fake_session.requests, [])

    async def test_generic_key_proxy_remains_available_to_other_plugins(self):
        save_result = await main.save_api_key(JsonRequest({
            "service_id": "other-plugin",
            "api_key": "other-plugin-secret",
        }))
        save_status, save_data = self.decode_result(save_result)
        self.assertEqual(save_status, 200)
        self.assertTrue(save_data["success"])

        keys_result = await main.get_api_keys()
        keys_status, keys_data = self.decode_result(keys_result)
        self.assertEqual(keys_status, 200)
        self.assertIn("other-plugin", keys_data["api_keys"])
        self.assertNotIn("other-plugin-secret", keys_data["api_keys"]["other-plugin"])
        self.assertNotIn(main.LINKDB_AGENT_PLUGIN_ID, keys_data["api_keys"])

        fake_session = self.patch_session(FakeProxySession())
        proxy_result = await main.proxy_request(main.ProxyRequest(
            service_id="other-plugin",
            url="https://api.example/v1/query",
            body={"query": "ok"},
        ))
        proxy_status, proxy_data = self.decode_result(proxy_result)
        self.assertEqual(proxy_status, 200)
        self.assertTrue(proxy_data["success"])
        self.assertEqual(len(fake_session.requests), 1)
        outgoing = fake_session.requests[0]
        self.assertEqual(outgoing["url"], "https://api.example/v1/query")
        self.assertEqual(
            outgoing["headers"]["Authorization"],
            "Bearer other-plugin-secret",
        )
        self.assertFalse(outgoing["allow_redirects"])

    async def test_health_uses_only_fixed_server_transport(self):
        self.configure_bridge(principal=None)
        fake_session = self.patch_session(FakeSession())

        result = await main.linkdb_agent_health(
            JsonRequest(url="http://testserver/api/linkdb-agent/health")
        )
        status, data = self.decode_result(result)

        self.assertEqual(status, 200)
        self.assertEqual(data, {
            "success": True,
            "status": "healthy",
            "service": "chatraw-agent",
            "version": "0.1.0",
        })
        request = fake_session.gets[0]
        self.assertEqual(request["url"], "http://agent.internal:8767/v1/health")
        self.assertEqual(request["headers"]["Authorization"], "Bearer agent-secret-key")
        self.assertNotIn("X-ChatRaw-Principal", request["headers"])
        self.assertFalse(request["allow_redirects"])
        self.assertEqual(request["timeout"].total, 120)
        self.assertEqual(request["timeout"].connect, 10)

    async def test_health_rejects_wrong_service_identity_and_invalid_json(self):
        self.configure_bridge()
        cases = (
            FakeResponse(json_data={
                "status": "healthy",
                "service": "different-service",
                "version": "0.1.0",
            }),
            FakeResponse(raw_data=b"not-json"),
        )
        for response in cases:
            with self.subTest(payload=response.content.payload):
                self.patch_session(FakeSession(get_response=response))
                result = await main.linkdb_agent_health(
                    JsonRequest(url="http://testserver/api/linkdb-agent/health")
                )
                status, data = self.decode_result(result)
                self.assertEqual(status, 502)
                self.assertEqual(data["code"], "upstream_invalid_response")
                self.assertFalse(data["success"])

    def test_environment_validation_fails_closed(self):
        self.configure_bridge(principal=None)
        config = main.get_linkdb_agent_config()
        self.assertEqual(config["principal"], main.LINKDB_AGENT_DEFAULT_PRINCIPAL)
        self.assertEqual(config["timeout_seconds"], 120)

        for timeout in ("0", "3601", "slow", "1.5"):
            with self.subTest(timeout=timeout):
                self.configure_bridge(timeout=timeout)
                with self.assertRaises(main.LinkDBAgentBridgeError):
                    main.get_linkdb_agent_config()

        for base_url in (
            "file:///tmp/agent",
            "http://user:password@agent.internal/v1",
            "http://agent.internal/v1?token=secret",
            "http://agent.internal/v1/../admin",
        ):
            with self.subTest(base_url=base_url):
                self.configure_bridge(base_url=base_url)
                with self.assertRaises(main.LinkDBAgentBridgeError):
                    main.get_linkdb_agent_config()

        self.configure_bridge(api_key="key with spaces")
        with self.assertRaises(main.LinkDBAgentBridgeError):
            main.get_linkdb_agent_config()

    async def test_origin_gate_rejects_cross_site_before_state_change(self):
        self.configure_bridge()
        fake_session = self.patch_session(FakeSession())
        result = await main.linkdb_agent_chat(JsonRequest(
            {"message": "blocked"},
            headers={"origin": "http://evil.test"},
            fetch_site="cross-site",
        ))

        status, data = self.decode_result(result)
        self.assertEqual(status, 403)
        self.assertEqual(data["code"], "unauthorized")
        self.assertEqual(fake_session.posts, [])
        self.assertEqual(self.chat_count(), 0)
        self.assertEqual(self.message_count(), 0)

    def test_body_validation_recursively_rejects_host_owned_fields(self):
        main.validate_linkdb_agent_chat_body({
            "chat_id": "allowed-chat-id",
            "message": "hello",
            "web_url": "https://customer.example/reference",
            "metadata": [{"display": {"theme": "dark"}}],
        })

        forbidden_fields = (
            "url",
            "endpoint",
            "path",
            "headers",
            "authorization",
            "apiKey",
            "api_key",
            "token",
            "baseUrl",
            "base_url",
            "principal",
            "session",
            "sessionId",
            "session_id",
            "timeout",
            "timeoutMs",
            "timeoutSeconds",
            "requestTimeout",
            "requestTimeoutSeconds",
        )
        for field in forbidden_fields:
            body = {"message": "hello", "nested": [{field: "browser-owned"}]}
            with self.subTest(field=field):
                with self.assertRaises(main.LinkDBAgentBridgeError) as context:
                    main.validate_linkdb_agent_chat_body(body)
                self.assertEqual(context.exception.status_code, 400)
                self.assertEqual(context.exception.code, "invalid_request")

        for body in ([], {"message": 42}, {"message": ""}, {"message": "ok", "chat_id": 42}):
            with self.subTest(body=body):
                with self.assertRaises(main.LinkDBAgentBridgeError):
                    main.validate_linkdb_agent_chat_body(body)

    async def test_request_body_limit_precedes_json_parsing_and_persistence(self):
        self.configure_bridge()
        fake_session = self.patch_session(FakeSession())

        declared_oversize = JsonRequest(
            {"message": "small"},
            headers={"content-length": str(main.LINKDB_AGENT_REQUEST_MAX_BYTES + 1)},
        )
        result = await main.linkdb_agent_chat(declared_oversize)
        status, data = self.decode_result(result)
        self.assertEqual(status, 413)
        self.assertEqual(data["code"], "invalid_request")
        self.assertEqual(declared_oversize.stream_reads, 0)

        prefix = b'{"message":"ok","web_content":"'
        streamed_oversize = JsonRequest(
            raw_body=b"",
            body_chunks=[prefix, b"x" * main.LINKDB_AGENT_REQUEST_MAX_BYTES],
        )
        result = await main.linkdb_agent_chat(streamed_oversize)
        status, data = self.decode_result(result)
        self.assertEqual(status, 413)
        self.assertEqual(data["code"], "invalid_request")
        self.assertEqual(streamed_oversize.stream_reads, 2)

        invalid_length = JsonRequest(
            {"message": "small"},
            headers={"content-length": "not-a-number"},
        )
        result = await main.linkdb_agent_chat(invalid_length)
        status, data = self.decode_result(result)
        self.assertEqual(status, 400)
        self.assertEqual(data["code"], "invalid_request")
        self.assertEqual(invalid_length.stream_reads, 0)

        self.assertEqual(fake_session.posts, [])
        self.assertEqual(self.chat_count(), 0)
        self.assertEqual(self.message_count(), 0)

    async def test_agent_payload_uses_only_allowlisted_presentation_preferences(self):
        self.configure_bridge()
        main.save_plugin_config({
            "plugins": {
                main.LINKDB_AGENT_PLUGIN_ID: {
                    "enabled": True,
                    "settings_values": {
                        "polish": False,
                        "showTrace": False,
                        "baseUrl": "https://browser.invalid/v1",
                    },
                },
            },
            "api_keys": {main.LINKDB_AGENT_PLUGIN_ID: "browser-secret"},
        })
        fake_session = self.patch_session(FakeSession())

        result = await main.linkdb_agent_chat(JsonRequest({"message": "query"}))
        status, _data = self.decode_result(result)

        self.assertEqual(status, 200)
        outgoing = fake_session.posts[0]
        self.assertFalse(outgoing["json"]["polish"])
        self.assertFalse(outgoing["json"]["options"]["show_trace"])
        self.assertEqual(outgoing["url"], "http://agent.internal:8767/v1/chat")
        self.assertEqual(outgoing["timeout"].total, 120)
        self.assertEqual(outgoing["headers"]["X-ChatRaw-Principal"], "organization-default/chatraw-local")
        serialized = json.dumps(outgoing["json"])
        self.assertNotIn("browser.invalid", serialized)
        self.assertNotIn("browser-secret", serialized)

    async def test_chat_generates_stable_principal_and_session_and_persists_messages(self):
        self.configure_bridge(principal="trusted-organization")
        fake_session = self.patch_session(FakeSession(
            post_response=FakeResponse(json_data={
                "answer": "查询完成",
                "need_clarification": False,
                "clarification_question": None,
                "trace": [{"step": "resolve", "status": "ok"}],
                "result_sets": [],
            })
        ))

        first = await main.linkdb_agent_chat(JsonRequest({
            "chat_id": None,
            "message": "查昨天出口流水",
            "use_rag": False,
            "use_thinking": False,
            "web_content": "",
            "web_url": "",
        }))
        first_status, first_data = self.decode_result(first)

        self.assertEqual(first_status, 200)
        self.assertEqual(first_data["content"], "查询完成")
        self.assertEqual(first_data["thinking"], "")
        self.assertEqual(first_data["references"], [])
        chat_id = first_data["chat_id"]

        outgoing = fake_session.posts[0]
        self.assertEqual(outgoing["url"], "http://agent.internal:8767/v1/chat")
        self.assertEqual(outgoing["headers"]["Authorization"], "Bearer agent-secret-key")
        self.assertEqual(outgoing["headers"]["X-ChatRaw-Principal"], "trusted-organization")
        self.assertFalse(outgoing["allow_redirects"])
        self.assertEqual(outgoing["json"], {
            "session_id": f"chatraw-{chat_id}",
            "message": "查昨天出口流水",
            "polish": True,
            "stream": False,
            "options": {
                "show_trace": True,
                "timeout_seconds": 120,
                "max_iterations": 4,
            },
        })
        self.assertEqual(self.chat_count(), 1)
        self.assertEqual(self.message_count(), 2)

        fake_session.post_response = FakeResponse(json_data={
            "answer": "第一条详情",
            "need_clarification": False,
            "clarification_question": None,
            "trace": [],
            "result_sets": [],
        })
        second = await main.linkdb_agent_chat(JsonRequest({
            "chat_id": chat_id,
            "message": "第一条详情是什么？",
        }))
        second_status, second_data = self.decode_result(second)
        self.assertEqual(second_status, 200)
        self.assertEqual(second_data["chat_id"], chat_id)
        self.assertEqual(fake_session.posts[1]["json"]["session_id"], f"chatraw-{chat_id}")
        self.assertEqual(self.chat_count(), 1)
        self.assertEqual(self.message_count(), 4)

    async def test_clarification_question_fills_empty_answer(self):
        self.configure_bridge()
        self.patch_session(FakeSession(post_response=FakeResponse(json_data={
            "answer": "",
            "need_clarification": True,
            "clarification_question": "请提供车牌号",
            "trace": [],
            "result_sets": [],
        })))

        result = await main.linkdb_agent_chat(JsonRequest({"message": "查出口流水"}))
        status, data = self.decode_result(result)
        self.assertEqual(status, 200)
        self.assertEqual(data["content"], "请提供车牌号")

    async def test_success_redaction_removes_credentials_but_preserves_ordinary_terms(self):
        self.configure_bridge()
        ordinary_url = "https://docs.example/services/token"
        answer = (
            f"The authorization workflow and token budget are documented at {ordinary_url}. "
            "Never expose Authorization: Bearer agent-secret-key."
        )
        self.patch_session(FakeSession(post_response=FakeResponse(json_data={
            "answer": answer,
            "need_clarification": False,
            "clarification_question": None,
            "trace": [],
            "result_sets": [],
        })))

        result = await main.linkdb_agent_chat(JsonRequest({"message": "security guidance"}))
        status, data = self.decode_result(result)
        self.assertEqual(status, 200)
        self.assertNotIn("agent-secret-key", data["content"])
        self.assertIn("authorization workflow", data["content"])
        self.assertIn("token budget", data["content"])
        self.assertIn(ordinary_url, data["content"])

        messages = main.db.get_messages(data["chat_id"])
        self.assertNotIn("agent-secret-key", messages[-1].content)
        self.assertIn(ordinary_url, messages[-1].content)

    async def test_upstream_statuses_have_useful_redacted_mappings(self):
        self.configure_bridge()
        cases = (
            (401, 401, "unauthorized"),
            (403, 403, "unauthorized"),
            (302, 502, "upstream_invalid_response"),
            (422, 502, "upstream_invalid_response"),
            (500, 502, "agent_unavailable"),
            (504, 504, "upstream_timeout"),
        )
        secret_body = (
            b"Authorization: Bearer agent-secret-key at "
            b"http://agent.internal:8767/v1 customer=SuA12345" + b"x" * 5000
        )

        for upstream_status, expected_status, expected_code in cases:
            with self.subTest(upstream_status=upstream_status):
                response = FakeResponse(status=upstream_status, raw_data=secret_body)
                fake_session = self.patch_session(FakeSession(post_response=response))
                result = await main.linkdb_agent_chat(JsonRequest({"message": "test"}))
                status, data = self.decode_result(result)

                self.assertEqual(status, expected_status)
                self.assertEqual(data["code"], expected_code)
                exposed = json.dumps(data, ensure_ascii=False)
                self.assertNotIn("agent-secret-key", exposed)
                self.assertNotIn("agent.internal", exposed)
                self.assertNotIn("SuA12345", exposed)
                self.assertEqual(response.content.read_sizes, [main.LINKDB_AGENT_ERROR_MAX_BYTES + 1])
                self.assertFalse(fake_session.posts[0]["allow_redirects"])

    async def test_timeout_network_invalid_json_and_oversize_are_mapped(self):
        self.configure_bridge()

        cases = (
            (
                FakeSession(post_error=asyncio.TimeoutError()),
                504,
                "upstream_timeout",
            ),
            (
                FakeSession(post_error=main.aiohttp.ClientError("agent-secret-key")),
                502,
                "agent_unavailable",
            ),
            (
                FakeSession(post_response=FakeResponse(raw_data=b"not-json")),
                502,
                "upstream_invalid_response",
            ),
            (
                FakeSession(post_response=FakeResponse(
                    raw_data=b"{" + b"x" * main.LINKDB_AGENT_RESPONSE_MAX_BYTES
                )),
                502,
                "upstream_invalid_response",
            ),
        )
        for fake_session, expected_status, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                self.patch_session(fake_session)
                result = await main.linkdb_agent_chat(JsonRequest({"message": "test"}))
                status, data = self.decode_result(result)
                self.assertEqual(status, expected_status)
                self.assertEqual(data["code"], expected_code)
                self.assertNotIn("agent-secret-key", json.dumps(data))
                self.assertNotIn("chat_id", data)
                self.assertEqual(self.chat_count(), 0)
                self.assertEqual(self.message_count(), 0)

    async def test_db_failure_after_upstream_success_rolls_back_and_returns_no_chat_id(self):
        self.configure_bridge()
        fake_session = self.patch_session(FakeSession())
        connection = main.db.get_conn()
        connection.execute("""
            CREATE TRIGGER fail_linkdb_assistant_insert
            BEFORE INSERT ON messages
            WHEN NEW.role = 'assistant'
            BEGIN
                SELECT RAISE(ABORT, 'forced assistant failure');
            END;
        """)
        connection.commit()
        self.addCleanup(lambda: (
            connection.execute("DROP TRIGGER IF EXISTS fail_linkdb_assistant_insert"),
            connection.commit(),
        ))

        result = await main.linkdb_agent_chat(JsonRequest({"message": "query"}))
        status, data = self.decode_result(result)

        self.assertEqual(status, 500)
        self.assertEqual(data["code"], "agent_unavailable")
        self.assertNotIn("chat_id", data)
        self.assertEqual(len(fake_session.posts), 1)
        self.assertEqual(self.chat_count(), 0)
        self.assertEqual(self.message_count(), 0)

    def test_recursive_redaction_removes_nested_secrets(self):
        value = {
            "message": "call http://agent.internal/v1 with Authorization: Bearer raw-token",
            "nested": [
                {"api_key": "raw-token"},
                {"safe": "token=raw-token"},
            ],
        }
        redacted = main._redact_linkdb_agent_value(
            value,
            ("raw-token",),
            redact_urls=True,
        )
        serialized = json.dumps(redacted)
        self.assertNotIn("raw-token", serialized)
        self.assertNotIn("agent.internal", serialized)
        self.assertEqual(redacted["nested"][0]["api_key"], "[REDACTED]")

    async def test_linkdb_agent_routes_are_not_rate_limit_exempt(self):
        async def call_next(_request):
            return main.JSONResponse({"ok": True})

        for path in ("/api/linkdb-agent/chat", "/api/linkdb-agent/health"):
            with self.subTest(path=path):
                middleware = main.RateLimitMiddleware(
                    lambda scope, receive, send: None,
                    requests_per_window=1,
                    window_seconds=60,
                )
                first = await middleware.dispatch(FakeRateRequest(path), call_next)
                second = await middleware.dispatch(FakeRateRequest(path), call_next)
                self.assertEqual(first.status_code, 200)
                self.assertEqual(second.status_code, 429)


if __name__ == "__main__":
    unittest.main()
