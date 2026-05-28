import ipaddress
import io
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend import main  # noqa: E402


class SecurityRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="chatraw-security-")
        self.old_auth_token = os.environ.get("CHATRAW_AUTH_TOKEN")
        self.old_backend_dir = main.BACKEND_DIR
        self.old_db = main.db
        self.old_llm_service = main.llm_service
        self.old_rag_service = main.rag_service
        self.old_plugins_dir = main.PLUGINS_DIR
        self.old_plugins_installed_dir = main.PLUGINS_INSTALLED_DIR
        self.old_plugins_config_file = main.PLUGINS_CONFIG_FILE

        os.environ["CHATRAW_AUTH_TOKEN"] = "test-token"
        self.db = main.Database(os.path.join(self.tmpdir, "chatraw.db"))
        main.db = self.db
        main.llm_service = main.LLMService(main.db)
        main.rag_service = main.RAGService(main.db, main.llm_service)
        main.PLUGINS_DIR = os.path.join(self.tmpdir, "plugins")
        main.PLUGINS_INSTALLED_DIR = os.path.join(main.PLUGINS_DIR, "installed")
        main.PLUGINS_CONFIG_FILE = os.path.join(main.PLUGINS_DIR, "config.json")
        os.makedirs(main.PLUGINS_INSTALLED_DIR, exist_ok=True)
        self.client = TestClient(main.app)

    def tearDown(self):
        try:
            self.db.get_conn().close()
        finally:
            main.BACKEND_DIR = self.old_backend_dir
            main.db = self.old_db
            main.llm_service = self.old_llm_service
            main.rag_service = self.old_rag_service
            main.PLUGINS_DIR = self.old_plugins_dir
            main.PLUGINS_INSTALLED_DIR = self.old_plugins_installed_dir
            main.PLUGINS_CONFIG_FILE = self.old_plugins_config_file
            if self.old_auth_token is None:
                os.environ.pop("CHATRAW_AUTH_TOKEN", None)
            else:
                os.environ["CHATRAW_AUTH_TOKEN"] = self.old_auth_token
            shutil.rmtree(self.tmpdir, ignore_errors=True)

    def auth_headers(self):
        return {"Authorization": "Bearer test-token"}

    def make_plugin_zip(self, plugin_id="zip-plugin", main_js="main.js"):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "plugin/manifest.json",
                f'{{"id": "{plugin_id}", "main": "{main_js}"}}',
            )
            archive.writestr(f"plugin/{main_js}", "window.zipPlugin = true;")
        return buffer.getvalue()

    def save_secret_model(self):
        main.db.save_model_config(
            main.ModelConfig(
                id="secret-chat",
                name="Secret Chat",
                api_key="sk-secret",
                api_url="https://api.example.com/v1",
                model_id="chat-model",
                type="chat",
            )
        )

    class SuccessfulVerifyResponse:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def text(self):
            return ""

    class SuccessfulVerifySession:
        def __init__(self):
            self.headers = None
            self.url = None
            self.json = None
            self.allow_redirects = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json, headers, allow_redirects=False):
            self.url = url
            self.json = json
            self.headers = headers
            self.allow_redirects = allow_redirects
            return SecurityRegressionTests.SuccessfulVerifyResponse()

    def test_models_require_auth_when_token_is_configured(self):
        unauthenticated = self.client.get("/api/models")
        self.assertEqual(unauthenticated.status_code, 401)

        authenticated = self.client.get("/api/models", headers=self.auth_headers())
        self.assertEqual(authenticated.status_code, 200)

    def test_models_require_auth_when_token_is_not_configured(self):
        os.environ.pop("CHATRAW_AUTH_TOKEN", None)

        response = self.client.get("/api/models")

        self.assertEqual(response.status_code, 401)

    def test_models_do_not_return_plaintext_api_key(self):
        self.save_secret_model()

        response = self.client.get("/api/models", headers=self.auth_headers())

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("sk-secret", response.text)
        model = next(item for item in response.json() if item["id"] == "secret-chat")
        self.assertEqual(model["api_key"], "")
        self.assertTrue(model["api_key_set"])

    def test_model_save_without_api_key_preserves_existing_secret(self):
        self.save_secret_model()

        response = self.client.post(
            "/api/models",
            headers=self.auth_headers(),
            json={
                "id": "secret-chat",
                "name": "Secret Chat Updated",
                "api_url": "https://api.example.com/v1",
                "model_id": "chat-model-v2",
                "type": "chat",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("sk-secret", response.text)
        saved = main.db.get_model_config("secret-chat")
        self.assertEqual(saved.api_key, "sk-secret")
        self.assertEqual(saved.model_id, "chat-model-v2")

    def test_model_save_preserves_secret_for_trailing_slash_url_change_only(self):
        self.save_secret_model()

        response = self.client.post(
            "/api/models",
            headers=self.auth_headers(),
            json={
                "id": "secret-chat",
                "name": "Secret Chat Updated",
                "api_url": "https://api.example.com/v1/",
                "model_id": "chat-model-v2",
                "type": "chat",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("sk-secret", response.text)
        self.assertTrue(response.json()["api_key_set"])
        saved = main.db.get_model_config("secret-chat")
        self.assertEqual(saved.api_key, "sk-secret")
        self.assertEqual(saved.api_url, "https://api.example.com/v1/")

    def test_model_save_without_api_key_clears_secret_when_url_changes(self):
        self.save_secret_model()

        response = self.client.post(
            "/api/models",
            headers=self.auth_headers(),
            json={
                "id": "secret-chat",
                "name": "Moved Chat",
                "api_url": "https://evil.example.com/v1",
                "model_id": "chat-model-v2",
                "type": "chat",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("sk-secret", response.text)
        self.assertFalse(response.json()["api_key_set"])
        saved = main.db.get_model_config("secret-chat")
        self.assertEqual(saved.api_key, "")
        self.assertEqual(saved.api_url, "https://evil.example.com/v1")

        fake_session = self.SuccessfulVerifySession()

        with patch.object(main, "create_external_http_session", lambda: fake_session):
            verify_response = self.client.post(
                "/api/models/verify",
                headers=self.auth_headers(),
                json={
                    "id": "secret-chat",
                    "api_url": "https://evil.example.com/v1",
                    "model_id": "chat-model-v2",
                    "type": "chat",
                },
            )

        self.assertEqual(verify_response.status_code, 200)
        self.assertTrue(verify_response.json()["success"])
        self.assertEqual(
            fake_session.url, "https://evil.example.com/v1/chat/completions"
        )
        self.assertNotIn("Authorization", fake_session.headers)
        self.assertFalse(fake_session.allow_redirects)

    def test_model_save_restores_backed_up_secret_for_original_endpoint(self):
        main.db.save_model_config(
            main.ModelConfig(
                id="default-chat",
                name="Original Chat",
                api_key="sk-original",
                api_url="https://api.original.example/v1",
                model_id="original-model",
                type="chat",
            )
        )

        activate_response = self.client.post(
            "/api/models",
            headers=self.auth_headers(),
            json={
                "id": "default-chat",
                "name": "Temporary Chat",
                "api_url": "https://api.temporary.example/v1",
                "api_key": "sk-temporary",
                "model_id": "temporary-model",
                "type": "chat",
                "preserve_previous_api_key": True,
            },
        )

        self.assertEqual(activate_response.status_code, 200)
        self.assertNotIn("sk-original", activate_response.text)
        self.assertNotIn("sk-temporary", activate_response.text)
        active = main.db.get_model_config("default-chat")
        self.assertEqual(active.api_key, "sk-temporary")
        self.assertEqual(active.api_url, "https://api.temporary.example/v1")

        restore_response = self.client.post(
            "/api/models",
            headers=self.auth_headers(),
            json={
                "id": "default-chat",
                "name": "Original Chat",
                "api_url": "https://api.original.example/v1",
                "model_id": "original-model",
                "type": "chat",
                "restore_previous_api_key": True,
            },
        )

        self.assertEqual(restore_response.status_code, 200)
        self.assertNotIn("sk-original", restore_response.text)
        self.assertNotIn("sk-temporary", restore_response.text)
        self.assertTrue(restore_response.json()["api_key_set"])
        restored = main.db.get_model_config("default-chat")
        self.assertEqual(restored.api_key, "sk-original")
        self.assertEqual(restored.api_url, "https://api.original.example/v1")
        self.assertEqual(
            main.db.get_model_api_key_backup(
                "default-chat", "https://api.original.example/v1"
            ),
            "",
        )

    def test_model_restore_without_backed_up_secret_does_not_overwrite_active_model(
        self,
    ):
        main.db.save_model_config(
            main.ModelConfig(
                id="default-chat",
                name="Temporary Chat",
                api_key="sk-temporary",
                api_url="https://api.temporary.example/v1",
                model_id="temporary-model",
                type="chat",
            )
        )

        response = self.client.post(
            "/api/models",
            headers=self.auth_headers(),
            json={
                "id": "default-chat",
                "name": "Original Chat",
                "api_url": "https://api.original.example/v1",
                "model_id": "original-model",
                "type": "chat",
                "restore_previous_api_key": True,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("sk-temporary", response.text)
        active = main.db.get_model_config("default-chat")
        self.assertEqual(active.api_key, "sk-temporary")
        self.assertEqual(active.api_url, "https://api.temporary.example/v1")

    def test_model_verify_uses_existing_secret_when_key_is_omitted(self):
        self.save_secret_model()

        fake_session = self.SuccessfulVerifySession()

        with patch.object(main, "create_external_http_session", lambda: fake_session):
            with patch.object(
                main.aiohttp,
                "DefaultResolver",
                side_effect=AssertionError("external resolver should not be used"),
            ):
                response = self.client.post(
                    "/api/models/verify",
                    headers=self.auth_headers(),
                    json={
                        "id": "secret-chat",
                        "api_url": "https://api.example.com/v1",
                        "model_id": "chat-model",
                        "type": "chat",
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(
            fake_session.url,
            "https://api.example.com/v1/chat/completions",
        )
        self.assertEqual(fake_session.headers["Authorization"], "Bearer sk-secret")
        self.assertFalse(fake_session.allow_redirects)

    def test_model_verify_does_not_reuse_existing_secret_for_changed_url(self):
        self.save_secret_model()

        fake_session = self.SuccessfulVerifySession()

        with patch.object(main, "create_external_http_session", lambda: fake_session):
            response = self.client.post(
                "/api/models/verify",
                headers=self.auth_headers(),
                json={
                    "id": "secret-chat",
                    "api_url": "https://evil.example.com/v1",
                    "model_id": "chat-model",
                    "type": "chat",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(
            fake_session.url, "https://evil.example.com/v1/chat/completions"
        )
        self.assertNotIn("Authorization", fake_session.headers)
        self.assertFalse(fake_session.allow_redirects)

    def test_model_verify_empty_api_key_does_not_reuse_existing_secret(self):
        self.save_secret_model()

        fake_session = self.SuccessfulVerifySession()

        with patch.object(main, "create_external_http_session", lambda: fake_session):
            response = self.client.post(
                "/api/models/verify",
                headers=self.auth_headers(),
                json={
                    "id": "secret-chat",
                    "api_url": "https://api.example.com/v1",
                    "api_key": "",
                    "model_id": "chat-model",
                    "type": "chat",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertNotIn("Authorization", fake_session.headers)
        self.assertFalse(fake_session.allow_redirects)

    def test_model_verify_rejects_literal_internal_targets_without_network(self):
        def fail_if_called():
            raise AssertionError("create_external_http_session should not be called")

        blocked_urls = [
            "http://127.0.0.1:11434/v1",
            "http://localhost:11434/v1",
            "http://10.0.0.1/v1",
            "http://192.168.1.1/v1",
            "http://169.254.169.254/latest/meta-data",
        ]

        with patch.object(main, "create_external_http_session", fail_if_called):
            for url in blocked_urls:
                with self.subTest(url=url):
                    response = self.client.post(
                        "/api/models/verify",
                        headers=self.auth_headers(),
                        json={
                            "api_url": url,
                            "api_key": "sk-local",
                            "model_id": "chat-model",
                            "type": "chat",
                        },
                    )

                    self.assertEqual(response.status_code, 400)

    def test_model_verify_blocks_private_ip_at_connection_resolution(self):
        class PrivateResolver:
            async def resolve(self, host, port=0, family=0):
                return [
                    {
                        "hostname": host,
                        "host": "169.254.169.254",
                        "port": port,
                        "family": socket.AF_INET,
                        "proto": 0,
                        "flags": 0,
                    }
                ]

            async def close(self):
                pass

        with patch.object(main.aiohttp, "DefaultResolver", lambda: PrivateResolver()):
            response = self.client.post(
                "/api/models/verify",
                headers=self.auth_headers(),
                json={
                    "api_url": "http://rebind.example/v1",
                    "api_key": "sk-test",
                    "model_id": "chat-model",
                    "type": "chat",
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("internal networks", response.text)

    def test_model_endpoints_reject_invalid_payloads(self):
        invalid_payload = {"id": "secret-chat", "context_length": "not-an-int"}

        for endpoint in ("/api/models", "/api/models/verify"):
            with self.subTest(endpoint=endpoint):
                response = self.client.post(
                    endpoint,
                    headers=self.auth_headers(),
                    json=invalid_payload,
                )
                self.assertEqual(response.status_code, 400)

    def test_font_route_blocks_encoded_path_traversal(self):
        app_root = Path(self.tmpdir) / "app"
        (app_root / "static" / "fonts").mkdir(parents=True)
        data_dir = app_root / "data"
        data_dir.mkdir()
        secret_db = data_dir / "chatraw.db"
        secret_db.write_text("font traversal secret", encoding="utf-8")
        main.BACKEND_DIR = str(app_root)

        response = self.client.get("/fonts/%2e%2e/%2e%2e/data/chatraw.db")

        self.assertIn(response.status_code, (400, 404))
        self.assertNotIn("font traversal secret", response.text)

    def test_external_url_ip_guard_allows_only_global_unicast(self):
        allowed_addresses = [
            "8.8.8.8",
            "2001:4860:4860::8888",
        ]
        blocked_addresses = [
            "10.0.0.1",
            "100.64.0.1",
            "127.0.0.1",
            "169.254.169.254",
            "224.0.0.1",
            "0.0.0.0",
            "::1",
        ]

        for address in allowed_addresses:
            with self.subTest(address=address):
                self.assertFalse(main.is_blocked_ip(ipaddress.ip_address(address)))

        for address in blocked_addresses:
            with self.subTest(address=address):
                self.assertTrue(main.is_blocked_ip(ipaddress.ip_address(address)))

    def test_parse_url_rejects_internal_targets_without_network(self):
        def fail_if_called():
            raise AssertionError("create_external_http_session should not be called")

        blocked_urls = [
            "HTTP://127.0.0.1:51111",
            "http://127.0.0.1:51111",
            "http://localhost:51111",
            "http://100.64.0.1",
            "http://169.254.169.254/latest/meta-data",
            "http://192.168.1.1",
        ]
        with patch.object(main, "create_external_http_session", fail_if_called):
            for url in blocked_urls:
                with self.subTest(url=url):
                    response = self.client.post("/api/parse-url", json={"url": url})
                    self.assertEqual(response.status_code, 400)

    def test_parse_url_blocks_private_ip_at_connection_resolution(self):
        class PrivateResolver:
            async def resolve(self, host, port=0, family=0):
                return [
                    {
                        "hostname": host,
                        "host": "169.254.169.254",
                        "port": port,
                        "family": socket.AF_INET,
                        "proto": 0,
                        "flags": 0,
                    }
                ]

            async def close(self):
                pass

        with patch.object(main.aiohttp, "DefaultResolver", lambda: PrivateResolver()):
            response = self.client.post(
                "/api/parse-url",
                json={"url": "http://rebind.example"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("internal networks", response.text)

    def test_parse_url_follows_safe_redirects(self):
        calls = []

        class FakeResponse:
            def __init__(self, status, headers=None, body=""):
                self.status = status
                self.headers = headers or {}
                self.body = body

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def text(self):
                return self.body

        class FakeSession:
            def get(self, url, headers, timeout, allow_redirects):
                calls.append((url, allow_redirects))
                if url == "https://example.com/start":
                    return FakeResponse(302, {"Location": "/article"})
                if url == "https://example.com/article":
                    return FakeResponse(
                        200,
                        body="<html><head><title>Final</title></head><body><p>Redirected body</p></body></html>",
                    )
                raise AssertionError(f"unexpected URL {url}")

        class FakeSessionManager:
            async def __aenter__(self):
                return FakeSession()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch.object(
            main, "create_external_http_session", lambda: FakeSessionManager()
        ):
            response = self.client.post(
                "/api/parse-url",
                json={"url": "example.com/start"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["url"], "https://example.com/article")
        self.assertEqual(
            calls,
            [
                ("https://example.com/start", False),
                ("https://example.com/article", False),
            ],
        )

    def test_parse_url_blocks_redirect_to_internal_target(self):
        calls = []

        class FakeResponse:
            status = 302
            headers = {"Location": "http://169.254.169.254/latest/meta-data"}

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class FakeSession:
            def get(self, url, headers, timeout, allow_redirects):
                calls.append((url, allow_redirects))
                return FakeResponse()

        class FakeSessionManager:
            async def __aenter__(self):
                return FakeSession()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch.object(
            main, "create_external_http_session", lambda: FakeSessionManager()
        ):
            response = self.client.post(
                "/api/parse-url",
                json={"url": "https://example.com/start"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("internal networks", response.text)
        self.assertEqual(calls, [("https://example.com/start", False)])

    def test_fetch_raw_url_rejects_internal_targets_without_network(self):
        def fail_if_called():
            raise AssertionError("create_external_http_session should not be called")

        with patch.object(main, "create_external_http_session", fail_if_called):
            response = self.client.post(
                "/api/fetch-raw-url",
                json={"url": "http://169.254.169.254/latest/meta-data"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("internal networks", response.text)

    def test_fetch_raw_url_follows_safe_redirects(self):
        calls = []

        class FakeResponse:
            def __init__(self, status, headers=None, body=""):
                self.status = status
                self.headers = headers or {}
                self.body = body

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def text(self):
                return self.body

        class FakeSession:
            def get(self, url, headers, timeout, allow_redirects):
                calls.append((url, allow_redirects))
                if url == "https://example.com/raw-start":
                    return FakeResponse(301, {"Location": "raw-final"})
                if url == "https://example.com/raw-final":
                    return FakeResponse(200, body="<html>Raw body</html>")
                raise AssertionError(f"unexpected URL {url}")

        class FakeSessionManager:
            async def __aenter__(self):
                return FakeSession()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch.object(
            main, "create_external_http_session", lambda: FakeSessionManager()
        ):
            response = self.client.post(
                "/api/fetch-raw-url",
                json={"url": "example.com/raw-start"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["html"], "<html>Raw body</html>")
        self.assertEqual(payload["url"], "https://example.com/raw-final")
        self.assertEqual(
            calls,
            [
                ("https://example.com/raw-start", False),
                ("https://example.com/raw-final", False),
            ],
        )

    def test_fetch_raw_url_blocks_redirect_to_internal_target(self):
        calls = []

        class FakeResponse:
            status = 302
            headers = {"Location": "http://169.254.169.254/latest/meta-data"}

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class FakeSession:
            def get(self, url, headers, timeout, allow_redirects):
                calls.append((url, allow_redirects))
                return FakeResponse()

        class FakeSessionManager:
            async def __aenter__(self):
                return FakeSession()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch.object(
            main, "create_external_http_session", lambda: FakeSessionManager()
        ):
            response = self.client.post(
                "/api/fetch-raw-url",
                json={"url": "https://example.com/raw-start"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("internal networks", response.text)
        self.assertEqual(calls, [("https://example.com/raw-start", False)])

    def test_proxy_request_rejects_literal_internal_targets_without_network(self):
        def fail_if_called():
            raise AssertionError("create_external_http_session should not be called")

        blocked_urls = [
            "HTTP://127.0.0.1:51111",
            "http://127.0.0.1:51111",
            "http://localhost:51111",
            "http://100.64.0.1",
            "http://169.254.169.254/latest/meta-data",
            "http://192.168.1.1",
            "http://[::1]/",
        ]
        with patch.object(main, "create_external_http_session", fail_if_called):
            for url in blocked_urls:
                with self.subTest(url=url):
                    response = self.client.post(
                        "/api/proxy/request",
                        json={"service_id": "test", "url": url},
                    )
                    self.assertEqual(response.status_code, 400)

    def test_proxy_request_accepts_case_insensitive_http_scheme(self):
        captured = {}

        class FakeResponse:
            status = 200

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def json(self):
                return {"ok": True}

        class FakeSession:
            def request(self, method, url, headers, json, timeout, allow_redirects):
                captured["url"] = url
                return FakeResponse()

        class FakeSessionManager:
            async def __aenter__(self):
                return FakeSession()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch.object(
            main, "create_external_http_session", lambda: FakeSessionManager()
        ):
            response = self.client.post(
                "/api/proxy/request",
                json={"service_id": "test", "url": "HTTP://api.example.com/v1"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["url"], "HTTP://api.example.com/v1")
        self.assertNotIn("https://HTTP://", captured["url"])

    def test_proxy_request_rejects_unsupported_explicit_scheme_without_network(self):
        def fail_if_called():
            raise AssertionError("create_external_http_session should not be called")

        with patch.object(main, "create_external_http_session", fail_if_called):
            response = self.client.post(
                "/api/proxy/request",
                json={"service_id": "test", "url": "ftp://api.example.com/v1"},
            )

        self.assertEqual(response.status_code, 400)

    def test_proxy_upload_rejects_internal_target_without_network(self):
        def fail_if_called():
            raise AssertionError("create_external_http_session should not be called")

        with patch.object(main, "create_external_http_session", fail_if_called):
            response = self.client.post(
                "/api/proxy/upload",
                data={
                    "service_id": "test",
                    "url": "http://169.254.169.254/latest/meta-data",
                },
                files={"file": ("sample.txt", b"hello", "text/plain")},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("internal networks", response.text)

    def test_proxy_upload_uses_validated_url_and_disables_redirects(self):
        captured = {}

        class FakeResponse:
            status = 200

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def json(self):
                return {"ok": True}

        class FakeSession:
            def post(self, url, data, headers, timeout, allow_redirects):
                captured["url"] = url
                captured["allow_redirects"] = allow_redirects
                return FakeResponse()

        class FakeSessionManager:
            async def __aenter__(self):
                return FakeSession()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch.object(
            main, "create_external_http_session", lambda: FakeSessionManager()
        ):
            response = self.client.post(
                "/api/proxy/upload",
                data={"service_id": "test", "url": "api.example.com/upload"},
                files={"file": ("sample.txt", b"hello", "text/plain")},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["url"], "https://api.example.com/upload")
        self.assertFalse(captured["allow_redirects"])

    def test_proxy_upload_blocks_private_ip_at_connection_resolution(self):
        class PrivateResolver:
            async def resolve(self, host, port=0, family=0):
                return [
                    {
                        "hostname": host,
                        "host": "10.0.0.1",
                        "port": port,
                        "family": socket.AF_INET,
                        "proto": 0,
                        "flags": 0,
                    }
                ]

            async def close(self):
                pass

        with patch.object(main.aiohttp, "DefaultResolver", lambda: PrivateResolver()):
            response = self.client.post(
                "/api/proxy/upload",
                data={"service_id": "test", "url": "http://rebind-upload.example"},
                files={"file": ("sample.txt", b"hello", "text/plain")},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("internal networks", response.text)

    def test_plugin_install_rejects_internal_source_without_network(self):
        def fail_if_called():
            raise AssertionError("create_external_http_session should not be called")

        with patch.object(main, "create_external_http_session", fail_if_called):
            response = self.client.post(
                "/api/plugins/install",
                json={"source_url": "http://169.254.169.254/plugin"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("internal networks", response.text)

    def test_plugin_install_uses_guarded_session_without_auto_redirects(self):
        calls = []

        class FakeResponse:
            def __init__(self, status, body="", headers=None):
                self.status = status
                self.body = body
                self.headers = headers or {}

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def text(self):
                return self.body

            async def read(self):
                return self.body.encode("utf-8")

        class FakeSession:
            closed = False

            def get(self, url, timeout, allow_redirects):
                calls.append((url, allow_redirects))
                if url == "https://plugins.example.com/safe/manifest.json":
                    return FakeResponse(
                        302,
                        headers={
                            "Location": "https://downloads.example.com/safe/manifest.json"
                        },
                    )
                if url == "https://downloads.example.com/safe/manifest.json":
                    return FakeResponse(
                        200,
                        '{"id": "safe-plugin", "main": "main.js", "icon": "icon.png"}',
                    )
                if url == "https://plugins.example.com/safe/main.js":
                    return FakeResponse(200, "window.safePlugin = true;")
                if url == "https://plugins.example.com/safe/icon.png":
                    return FakeResponse(
                        302,
                        headers={"Location": "http://169.254.169.254/icon.png"},
                    )
                raise AssertionError(f"unexpected URL {url}")

            async def close(self):
                self.closed = True

        with patch.object(main, "create_external_http_session", lambda: FakeSession()):
            response = self.client.post(
                "/api/plugins/install",
                json={"source_url": "plugins.example.com/safe"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(
            calls,
            [
                ("https://plugins.example.com/safe/manifest.json", False),
                ("https://downloads.example.com/safe/manifest.json", False),
                ("https://plugins.example.com/safe/main.js", False),
                ("https://plugins.example.com/safe/icon.png", False),
            ],
        )
        installed_main = Path(main.PLUGINS_INSTALLED_DIR) / "safe-plugin" / "main.js"
        self.assertTrue(installed_main.exists())
        self.assertEqual(
            installed_main.read_text(encoding="utf-8"), "window.safePlugin = true;"
        )

    def test_plugin_install_rejects_main_redirect_to_internal_network(self):
        calls = []

        class FakeResponse:
            def __init__(self, status, body="", headers=None):
                self.status = status
                self.body = body
                self.headers = headers or {}

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def read(self):
                return self.body.encode("utf-8")

        class FakeSession:
            closed = False

            def get(self, url, timeout, allow_redirects):
                calls.append((url, allow_redirects))
                if url == "https://plugins.example.com/safe/manifest.json":
                    return FakeResponse(
                        200,
                        '{"id": "safe-plugin", "main": "main.js", "icon": "icon.png"}',
                    )
                if url == "https://plugins.example.com/safe/main.js":
                    return FakeResponse(
                        302,
                        headers={"Location": "http://169.254.169.254/main.js"},
                    )
                raise AssertionError(f"unsafe redirect should not be requested: {url}")

            async def close(self):
                self.closed = True

        with patch.object(main, "create_external_http_session", lambda: FakeSession()):
            response = self.client.post(
                "/api/plugins/install",
                json={"source_url": "plugins.example.com/safe"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("internal networks", response.text)
        self.assertEqual(
            calls,
            [
                ("https://plugins.example.com/safe/manifest.json", False),
                ("https://plugins.example.com/safe/main.js", False),
            ],
        )
        installed_dir = Path(main.PLUGINS_INSTALLED_DIR) / "safe-plugin"
        self.assertFalse(installed_dir.exists())

    def test_plugin_zip_install_follows_safe_redirects_manually(self):
        calls = []
        zip_content = self.make_plugin_zip()

        class FakeResponse:
            def __init__(self, status, body=b"", headers=None):
                self.status = status
                self.body = body
                self.headers = headers or {}

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def read(self):
                return self.body

        class FakeSession:
            closed = False

            def get(self, url, timeout, allow_redirects):
                calls.append((url, allow_redirects))
                if url == "https://plugins.example.com/release.zip":
                    return FakeResponse(
                        302,
                        headers={
                            "Location": "https://downloads.example.com/release.zip"
                        },
                    )
                if url == "https://downloads.example.com/release.zip":
                    return FakeResponse(
                        200,
                        zip_content,
                        headers={"Content-Length": str(len(zip_content))},
                    )
                raise AssertionError(f"unexpected URL {url}")

            async def close(self):
                self.closed = True

        with patch.object(main, "create_external_http_session", lambda: FakeSession()):
            response = self.client.post(
                "/api/plugins/install",
                json={"source_url": "plugins.example.com/release.zip"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(
            calls,
            [
                ("https://plugins.example.com/release.zip", False),
                ("https://downloads.example.com/release.zip", False),
            ],
        )
        installed_main = Path(main.PLUGINS_INSTALLED_DIR) / "zip-plugin" / "main.js"
        self.assertTrue(installed_main.exists())
        self.assertEqual(
            installed_main.read_text(encoding="utf-8"), "window.zipPlugin = true;"
        )

    def test_plugin_zip_install_rejects_redirect_to_internal_network(self):
        calls = []

        class FakeResponse:
            def __init__(self, status, headers=None):
                self.status = status
                self.headers = headers or {}

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def read(self):
                return b""

        class FakeSession:
            closed = False

            def get(self, url, timeout, allow_redirects):
                calls.append((url, allow_redirects))
                if url == "https://plugins.example.com/release.zip":
                    return FakeResponse(
                        302,
                        headers={"Location": "http://169.254.169.254/plugin.zip"},
                    )
                raise AssertionError(f"unsafe redirect should not be requested: {url}")

            async def close(self):
                self.closed = True

        with patch.object(main, "create_external_http_session", lambda: FakeSession()):
            response = self.client.post(
                "/api/plugins/install",
                json={"source_url": "plugins.example.com/release.zip"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("internal networks", response.text)
        self.assertEqual(calls, [("https://plugins.example.com/release.zip", False)])

    def test_plugin_install_blocks_private_ip_at_connection_resolution(self):
        class PrivateResolver:
            async def resolve(self, host, port=0, family=0):
                return [
                    {
                        "hostname": host,
                        "host": "10.0.0.1",
                        "port": port,
                        "family": socket.AF_INET,
                        "proto": 0,
                        "flags": 0,
                    }
                ]

            async def close(self):
                pass

        with patch.object(main.aiohttp, "DefaultResolver", lambda: PrivateResolver()):
            response = self.client.post(
                "/api/plugins/install",
                json={"source_url": "http://plugin-install.example/safe"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("internal networks", response.text)

    def test_proxy_request_blocks_private_ip_at_connection_resolution(self):
        class PrivateResolver:
            async def resolve(self, host, port=0, family=0):
                return [
                    {
                        "hostname": host,
                        "host": "93.184.216.34",
                        "port": port,
                        "family": socket.AF_INET,
                        "proto": 0,
                        "flags": 0,
                    },
                    {
                        "hostname": host,
                        "host": "10.0.0.1",
                        "port": port,
                        "family": socket.AF_INET,
                        "proto": 0,
                        "flags": 0,
                    },
                ]

            async def close(self):
                pass

        with patch.object(main.aiohttp, "DefaultResolver", lambda: PrivateResolver()):
            response = self.client.post(
                "/api/proxy/request",
                json={"service_id": "test", "url": "http://rebind.example"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("internal networks", response.text)

    def test_proxy_request_blocks_shared_ip_at_connection_resolution(self):
        class SharedResolver:
            async def resolve(self, host, port=0, family=0):
                return [
                    {
                        "hostname": host,
                        "host": "100.64.0.1",
                        "port": port,
                        "family": socket.AF_INET,
                        "proto": 0,
                        "flags": 0,
                    }
                ]

            async def close(self):
                pass

        with patch.object(main.aiohttp, "DefaultResolver", lambda: SharedResolver()):
            response = self.client.post(
                "/api/proxy/request",
                json={"service_id": "test", "url": "http://shared.example"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("internal networks", response.text)

    def test_markdown_sanitizer_removes_event_handlers_and_dangerous_urls(self):
        script = textwrap.dedent(
            f"""
            const fs = require('fs');
            const vm = require('vm');
            const source = fs.readFileSync({str(REPO_ROOT / 'backend' / 'static' / 'app.js')!r}, 'utf8');
            const sandbox = {{
                marked: {{
                    setOptions() {{}},
                    parse(value) {{ return value; }}
                }},
                window: {{ matchMedia() {{ return {{ matches: false }}; }} }},
                localStorage: {{ getItem() {{ return null; }}, setItem() {{}} }},
                document: {{
                    head: {{ appendChild() {{}} }},
                    createElement() {{ return {{}}; }},
                    querySelectorAll() {{ return []; }}
                }}
            }};
            vm.runInNewContext(source + `
                const state = app();
                const cases = [
                    {{
                        name: 'space-delimited event attribute',
                        dirty: '<img src=x onerror=alert(1)>',
                        forbidden: [/onerror/i],
                        required: ['<img src=x>']
                    }},
                    {{
                        name: 'slash-delimited event attribute',
                        dirty: '<svg/onload=alert(2)>',
                        forbidden: [/onload/i],
                        required: ['<svg>']
                    }},
                    {{
                        name: 'quoted greater-than event attribute',
                        dirty: '<img src=x onerror="alert(9)//>">',
                        forbidden: [/onerror/i],
                        required: ['<img src=x>']
                    }},
                    {{
                        name: 'event attribute after double-quoted greater-than',
                        dirty: '<img alt=">" src=x onerror=alert(11)>',
                        forbidden: [/onerror/i],
                        required: []
                    }},
                    {{
                        name: 'event attribute after single-quoted greater-than',
                        dirty: "<img alt='>' src=x onerror=alert(12)>",
                        forbidden: [/onerror/i],
                        required: []
                    }},
                    {{
                        name: 'dangerous href after quoted greater-than',
                        dirty: '<a title=">" href="javascript:alert(13)">x</a>',
                        forbidden: [/href=/i, /javascript:/i],
                        required: ['<a title=">">x</a>']
                    }},
                    {{
                        name: 'entity and newline encoded href after quoted greater-than',
                        dirty: '<a title=">" href="java&#x0A;script:alert(14)">x</a>',
                        forbidden: [/href=/i, /java&#x0A;script/i],
                        required: ['<a title=">">x</a>']
                    }},
                    {{
                        name: 'xlink href after quoted greater-than',
                        dirty: '<svg><a data-x=">" xlink:href="javascript:alert(15)">x</a></svg>',
                        forbidden: [/xlink:href/i, /javascript:/i],
                        required: ['<svg><a data-x=">">x</a></svg>']
                    }},
                    {{
                        name: 'malformed tag-like tail is dropped',
                        dirty: '<img src=x onerror="alert(16)',
                        forbidden: [/onerror/i, /alert\\(16\\)/i],
                        required: []
                    }},
                    {{
                        name: 'blocked script tag with quoted greater-than attribute',
                        dirty: '<script data-x=">">alert(10)</script><strong>ok</strong>',
                        forbidden: [/script/i, /alert\\(10\\)/i],
                        required: ['<strong>ok</strong>']
                    }},
                    {{
                        name: 'blocked iframe tag with srcdoc payload',
                        dirty: '<iframe title=">" srcdoc="<img src=x onerror=alert(17)>">',
                        forbidden: [/iframe/i, /srcdoc/i, /onerror/i, /alert\\(17\\)/i],
                        required: []
                    }},
                    {{
                        name: 'entity-encoded dangerous link',
                        dirty: '<a href="jav&#x61;script:alert(3)">x</a>',
                        forbidden: [/href=/i, /javascript:/i, /jav&#x61;script:/i],
                        required: ['<a>x</a>']
                    }},
                    {{
                        name: 'slash-delimited dangerous link',
                        dirty: '<a/href="javascript:alert(4)">x</a>',
                        forbidden: [/href=/i, /javascript:/i],
                        required: ['<a>x</a>']
                    }},
                    {{
                        name: 'data html link',
                        dirty: '<a href="data:text/html,<script>alert(18)</script>">x</a>',
                        forbidden: [/href=/i, new RegExp('data:text/html', 'i'), /script/i],
                        required: ['<a>x</a>']
                    }},
                    {{
                        name: 'data html charset form action',
                        dirty: '<form action="data:text/html;charset=utf-8,<script>alert(19)</script>"><button>open</button></form>',
                        forbidden: [/action=/i, new RegExp('data:text/html', 'i'), /script/i],
                        required: ['<form><button>open</button></form>']
                    }},
                    {{
                        name: 'form URL attributes',
                        dirty: '<form action="javascript:alert(5)"><button formaction="jav&#x61;script:alert(6)">open</button></form>',
                        forbidden: [/action=/i, /formaction=/i, /javascript:/i, /jav&#x61;script:/i],
                        required: ['<form><button>open</button></form>']
                    }},
                    {{
                        name: 'slash-delimited form URL attributes',
                        dirty: '<form/action="javascript:alert(7)"><button/formaction="javascript:alert(8)">open</button></form>',
                        forbidden: [/action=/i, /formaction=/i, /javascript:/i],
                        required: ['<form><button>open</button></form>']
                    }},
                    {{
                        name: 'nested malformed image tag',
                        dirty: '<<img src=x onerror=alert(20)>',
                        forbidden: [/onerror/i, /alert\\(20\\)/i],
                        required: ['&lt;<img src=x>']
                    }},
                    {{
                        name: 'spaced nested malformed image tag',
                        dirty: '< <img src=x onerror=alert(21)>',
                        forbidden: [/onerror/i, /alert\\(21\\)/i],
                        required: ['&lt; <img src=x>']
                    }},
                    {{
                        name: 'nested malformed script tag',
                        dirty: '<<<script>alert(22)</script><strong>ok</strong>',
                        forbidden: [/script/i, /alert\\(22\\)/i],
                        required: ['&lt;&lt;<strong>ok</strong>']
                    }},
                    {{
                        name: 'malformed event attribute value',
                        dirty: '<img src=x onerror=<svg/onload=alert(23)>>',
                        forbidden: [/onerror/i, /onload/i, /alert\\(23\\)/i],
                        required: ['<img src=x>']
                    }},
                    {{
                        name: 'nested malformed event attribute value',
                        dirty: '<<img src=x onerror=<svg/onload=alert(24)>>',
                        forbidden: [/onerror/i, /onload/i, /alert\\(24\\)/i],
                        required: ['&lt;<img src=x>']
                    }},
                    {{
                        name: 'safe URL and formatting tags',
                        dirty: '<a href="https://example.com">ok</a><img src="/image.png"><strong>ok</strong>',
                        forbidden: [/javascript:/i, /onerror/i],
                        required: ['href="https://example.com"', 'src="/image.png"', '<strong>ok</strong>']
                    }}
                ];
                this.failures = [];
                for (const item of cases) {{
                    const result = state.renderMarkdown(item.dirty);
                    for (const pattern of item.forbidden) {{
                        if (pattern.test(result)) {{
                            this.failures.push(item.name + ' retained ' + pattern + ' in ' + result);
                        }}
                    }}
                    for (const expected of item.required) {{
                        if (!result.includes(expected)) {{
                            this.failures.push(item.name + ' missing ' + expected + ' in ' + result);
                        }}
                    }}
                }}
            `, sandbox);
            if (sandbox.failures.length) {{
                process.stderr.write(sandbox.failures.join('\\n'));
                process.exit(1);
            }}
            """
        )

        result = subprocess.run(
            ["node", "-e", script],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_minified_bundle_uses_security_runtime(self):
        script = textwrap.dedent(
            f"""
            const fs = require('fs');
            const vm = require('vm');
            const source = fs.readFileSync({str(REPO_ROOT / 'backend' / 'static' / 'app.min.js')!r}, 'utf8');
            const sandbox = {{
                marked: {{
                    setOptions() {{}},
                    parse(value) {{ return value; }}
                }},
                window: {{ matchMedia() {{ return {{ matches: false }}; }} }},
                localStorage: {{ getItem() {{ return null; }}, setItem() {{}} }},
                sessionStorage: {{
                    getItem(key) {{ return key === 'chatraw_model_auth_token' ? 'plugin-token' : null; }},
                    setItem() {{}}
                }},
                fetchCalls: [],
                document: {{
                    head: {{ appendChild() {{}} }},
                    createElement() {{ return {{}}; }},
                    querySelectorAll() {{ return []; }}
                }}
            }};
            vm.runInNewContext(source + `
                this.fetch = (url, options = {{}}) => {{
                    this.fetchCalls.push({{ url, options }});
                    return Promise.resolve({{ status: 200, ok: true, json: async () => [] }});
                }};
                const state = app();
                const markdownCases = [
                    {{
                        name: 'quoted greater-than event handler',
                        dirty: '<img src=x onerror="alert(1)//>">',
                        forbidden: /onerror|alert\\(1\\)/i,
                        required: '<img src=x>'
                    }},
                    {{
                        name: 'nested malformed image tag',
                        dirty: '<<img src=x onerror=alert(2)>',
                        forbidden: /onerror|alert\\(2\\)/i,
                        required: '&lt;<img src=x>'
                    }},
                    {{
                        name: 'spaced nested malformed image tag',
                        dirty: '< <img src=x onerror=alert(3)>',
                        forbidden: /onerror|alert\\(3\\)/i,
                        required: '&lt; <img src=x>'
                    }},
                    {{
                        name: 'nested malformed script tag',
                        dirty: '<<<script>alert(4)</script><strong>ok</strong>',
                        forbidden: /script|alert\\(4\\)/i,
                        required: '&lt;&lt;<strong>ok</strong>'
                    }},
                    {{
                        name: 'malformed event attribute value',
                        dirty: '<img src=x onerror=<svg/onload=alert(5)>>',
                        forbidden: /onerror|onload|alert\\(5\\)/i,
                        required: '<img src=x>'
                    }},
                    {{
                        name: 'nested malformed event attribute value',
                        dirty: '<<img src=x onerror=<svg/onload=alert(6)>>',
                        forbidden: /onerror|onload|alert\\(6\\)/i,
                        required: '&lt;<img src=x>'
                    }}
                ];
                this.markdownFailures = [];
                for (const item of markdownCases) {{
                    const rendered = state.renderMarkdown(item.dirty);
                    if (item.forbidden.test(rendered) || !rendered.includes(item.required)) {{
                        this.markdownFailures.push(item.name + ': ' + rendered);
                    }}
                }}
                this.payload = state.prepareModelPayload({{
                    id: 'secret-chat',
                    api_key_set: true,
                    api_key: '',
                    api_key_touched: false
                }});
                state.initPluginSystem();
                window.ChatRawPlugin.modelFetch('/api/models', {{
                    headers: {{ 'Content-Type': 'application/json' }}
                }});
                this.pluginPreservePayload = window.ChatRawPlugin.prepareModelPayload({{
                    id: 'default-chat',
                    api_url: 'https://api.example.com/v1',
                    model_id: 'gpt-test',
                    api_key: '',
                    api_key_set: true,
                    api_key_touched: false
                }});
                this.pluginClearPayload = window.ChatRawPlugin.prepareModelPayload({{
                    id: 'default-chat',
                    api_url: 'https://api.example.com/v1',
                    model_id: 'gpt-test',
                    api_key: '',
                    api_key_set: true,
                    api_key_touched: true
                }});
                this.pluginRestorePayload = window.ChatRawPlugin.prepareModelPayload({{
                    id: 'default-chat',
                    api_url: 'https://api.example.com/v1',
                    model_id: 'gpt-test',
                    api_key: '',
                    api_key_set: true,
                    api_key_touched: false,
                    restore_previous_api_key: true
                }});
            `, sandbox);
            if (sandbox.markdownFailures.length) {{
                process.stderr.write(sandbox.markdownFailures.join('\\n'));
                process.exit(1);
            }}
            if (Object.prototype.hasOwnProperty.call(sandbox.payload, 'api_key')) {{
                process.stderr.write(JSON.stringify(sandbox.payload));
                process.exit(1);
            }}
            const pluginCall = sandbox.fetchCalls.find(call => call.url === '/api/models');
            if (!pluginCall || pluginCall.options.headers.Authorization !== 'Bearer plugin-token') {{
                process.stderr.write(JSON.stringify(sandbox.fetchCalls));
                process.exit(1);
            }}
            if (Object.prototype.hasOwnProperty.call(sandbox.pluginPreservePayload, 'api_key')) {{
                process.stderr.write(JSON.stringify(sandbox.pluginPreservePayload));
                process.exit(1);
            }}
            if (sandbox.pluginClearPayload.api_key !== '') {{
                process.stderr.write(JSON.stringify(sandbox.pluginClearPayload));
                process.exit(1);
            }}
            if (
                Object.prototype.hasOwnProperty.call(sandbox.pluginRestorePayload, 'api_key') ||
                sandbox.pluginRestorePayload.restore_previous_api_key !== true
            ) {{
                process.stderr.write(JSON.stringify(sandbox.pluginRestorePayload));
                process.exit(1);
            }}
            """
        )

        result = subprocess.run(
            ["node", "-e", script],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_bundled_model_plugins_use_auth_aware_fetch(self):
        plugin_paths = [
            REPO_ROOT / "Plugins" / "Plugin_market" / "multi-model-manager" / "main.js",
            REPO_ROOT / "Plugins" / "Plugin_market" / "lightweight-rag" / "main.js",
        ]
        for path in plugin_paths:
            source = path.read_text()
            with self.subTest(path=path.name):
                self.assertIn("ChatRaw.modelFetch", source)
                self.assertIn("ChatRaw.prepareModelPayload", source)
                self.assertNotRegex(source, r"fetch\(\s*['\"`]/api/models")
                self.assertNotRegex(source, r"body:\s*JSON\.stringify\(\s*model\s*\)")
        multi_model_source = plugin_paths[0].read_text()
        self.assertNotIn("Cannot restore redacted original API key", multi_model_source)
        self.assertIn("restore_previous_api_key", multi_model_source)
        self.assertIn("preserve_previous_api_key", multi_model_source)
        rag_source = plugin_paths[1].read_text()
        self.assertIn("model.api_key_touched = false", rag_source)

    def test_multi_model_manager_preserves_state_when_restore_fails(self):
        script = textwrap.dedent(
            f"""
            (async () => {{
                const fs = require('fs');
                const vm = require('vm');
                const source = fs.readFileSync(
                    {str(REPO_ROOT / 'Plugins' / 'Plugin_market' / 'multi-model-manager' / 'main.js')!r},
                    'utf8'
                );
                const harnessedSource = source.replace(
                    /\\n\\s*init\\(\\);\\s*\\n\\s*\\}}\\)\\(window\\.ChatRawPlugin\\);\\s*$/,
                    `
                    window.__mmTest = {{
                        get pluginData() {{ return pluginData; }},
                        setPluginData(value) {{ pluginData = value; }},
                        get selectedModelId() {{ return selectedModelId; }},
                        setSelectedModelId(value) {{ selectedModelId = value; }},
                        activateModel,
                        deactivateModel,
                        deleteModel,
                        restoreOriginalConfig,
                        backupOriginalConfig
                    }};

                }})(window.ChatRawPlugin);
                    `
                );
                if (harnessedSource === source) {{
                    throw new Error('failed to install multi-model-manager test harness');
                }}

                const sandbox = {{
                    modelCalls: [],
                    saveCalls: [],
                    toasts: [],
                    console,
                    setTimeout() {{}},
                    confirm() {{ return true; }},
                    document: {{
                        getElementById() {{ return null; }},
                        querySelector() {{ return null; }}
                    }},
                    window: {{
                        addEventListener() {{}},
                        ChatRawPlugin: {{
                            hooks: {{ register() {{}} }},
                            modelFetch: async (url, options = {{}}) => {{
                                sandbox.modelCalls.push({{ url, options }});
                                return {{
                                    ok: false,
                                    status: 400,
                                    text: async () => 'restore unavailable'
                                }};
                            }},
                            prepareModelPayload(model) {{
                                const payload = {{ ...model }};
                                const apiKeyTouched = !!model.api_key_touched;
                                delete payload.api_key_set;
                                delete payload.api_key_touched;
                                delete payload.status;
                                delete payload.verifyMessage;
                                if (model.api_key_set && !model.api_key && !apiKeyTouched) {{
                                    delete payload.api_key;
                                }}
                                return payload;
                            }},
                            utils: {{
                                getLanguage() {{ return 'en'; }},
                                showToast(message, type) {{
                                    sandbox.toasts.push({{ message, type }});
                                }}
                            }}
                        }}
                    }},
                    fetch: async (url, options = {{}}) => {{
                        sandbox.saveCalls.push({{ url, options }});
                        return {{ ok: true, status: 200, text: async () => '{{}}' }};
                    }}
                }};

                vm.runInNewContext(harnessedSource, sandbox);
                const api = sandbox.window.__mmTest;

                api.setPluginData({{
                    models: [
                        {{
                            id: 'temp-model',
                            displayName: 'Temp',
                            active: true,
                            api_url: 'https://api.temp.example/v1',
                            api_key: 'sk-temp',
                            model_id: 'temp',
                            capability: {{}},
                            context_length: 8192,
                            max_output: 4096
                        }}
                    ],
                    originalConfig: {{
                        id: 'default-chat',
                        type: 'chat',
                        api_url: 'https://api.original.example/v1',
                        api_key: '',
                        api_key_set: true,
                        model_id: 'original',
                        capability: {{}},
                        context_length: 8192,
                        max_output: 4096
                    }}
                }});
                api.setSelectedModelId('temp-model');

                const deactivateResult = await api.deactivateModel('temp-model');
                if (deactivateResult !== false) {{
                    throw new Error('deactivate should report restore failure');
                }}
                if (!api.pluginData.models[0].active || api.selectedModelId !== 'temp-model') {{
                    throw new Error('deactivate drifted plugin state after restore failure');
                }}
                if (sandbox.saveCalls.length !== 0) {{
                    throw new Error('deactivate saved failed restore state');
                }}
                const restorePayload = JSON.parse(sandbox.modelCalls[0].options.body);
                if (
                    restorePayload.restore_previous_api_key !== true ||
                    Object.prototype.hasOwnProperty.call(restorePayload, 'api_key')
                ) {{
                    throw new Error('restore payload did not preserve redacted key semantics');
                }}

                sandbox.modelCalls = [];
                sandbox.saveCalls = [];
                sandbox.toasts = [];
                api.setPluginData({{
                    models: [
                        {{
                            id: 'temp-model',
                            displayName: 'Temp',
                            active: true,
                            api_url: 'https://api.temp.example/v1',
                            api_key: 'sk-temp',
                            model_id: 'temp',
                            capability: {{}},
                            context_length: 8192,
                            max_output: 4096
                        }}
                    ],
                    originalConfig: {{
                        id: 'default-chat',
                        type: 'chat',
                        api_url: 'https://api.original.example/v1',
                        api_key: '',
                        api_key_set: true,
                        model_id: 'original',
                        capability: {{}},
                        context_length: 8192,
                        max_output: 4096
                    }}
                }});
                api.setSelectedModelId('temp-model');

                const deleteResult = await api.deleteModel('temp-model');
                if (deleteResult !== false) {{
                    throw new Error('delete should report restore failure');
                }}
                if (
                    api.pluginData.models.length !== 1 ||
                    api.pluginData.models[0].id !== 'temp-model' ||
                    !api.pluginData.models[0].active ||
                    api.selectedModelId !== 'temp-model'
                ) {{
                    throw new Error('delete drifted plugin state after restore failure');
                }}
                if (sandbox.saveCalls.length !== 0) {{
                    throw new Error('delete saved failed restore state');
                }}
                if (sandbox.toasts.some(toast => toast.type === 'success')) {{
                    throw new Error('delete showed success after restore failure');
                }}
            }})().catch(error => {{
                process.stderr.write(error.stack || String(error));
                process.exit(1);
            }});
            """
        )

        result = subprocess.run(
            ["node", "-e", script],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_multi_model_manager_aborts_activation_when_backup_fails(self):
        script = textwrap.dedent(
            f"""
            (async () => {{
                const fs = require('fs');
                const vm = require('vm');
                const source = fs.readFileSync(
                    {str(REPO_ROOT / 'Plugins' / 'Plugin_market' / 'multi-model-manager' / 'main.js')!r},
                    'utf8'
                );
                const harnessedSource = source.replace(
                    /\\n\\s*init\\(\\);\\s*\\n\\s*\\}}\\)\\(window\\.ChatRawPlugin\\);\\s*$/,
                    `
                    window.__mmTest = {{
                        get pluginData() {{ return pluginData; }},
                        setPluginData(value) {{ pluginData = value; }},
                        activateModel
                    }};

                }})(window.ChatRawPlugin);
                    `
                );
                const sandbox = {{
                    modelCalls: [],
                    saveCalls: [],
                    console,
                    setTimeout() {{}},
                    document: {{
                        getElementById() {{ return null; }},
                        querySelector() {{ return null; }}
                    }},
                    window: {{
                        addEventListener() {{}},
                        ChatRawPlugin: {{
                            hooks: {{ register() {{}} }},
                            modelFetch: async (url, options = {{}}) => {{
                                sandbox.modelCalls.push({{ url, options }});
                                return {{
                                    ok: false,
                                    status: 500,
                                    text: async () => 'backup unavailable'
                                }};
                            }},
                            prepareModelPayload(model) {{ return {{ ...model }}; }},
                            utils: {{ getLanguage() {{ return 'en'; }}, showToast() {{}} }}
                        }}
                    }},
                    fetch: async (url, options = {{}}) => {{
                        sandbox.saveCalls.push({{ url, options }});
                        return {{ ok: true, status: 200, text: async () => '{{}}' }};
                    }}
                }};

                vm.runInNewContext(harnessedSource, sandbox);
                const api = sandbox.window.__mmTest;
                api.setPluginData({{
                    models: [
                        {{
                            id: 'temp-model',
                            displayName: 'Temp',
                            active: false,
                            api_url: 'https://api.temp.example/v1',
                            api_key: 'sk-temp',
                            model_id: 'temp',
                            capability: {{}},
                            context_length: 8192,
                            max_output: 4096
                        }}
                    ],
                    originalConfig: null
                }});

                await api.activateModel('temp-model');
                if (api.pluginData.models[0].active) {{
                    throw new Error('activation changed local state after backup failure');
                }}
                if (sandbox.modelCalls.length !== 1 || sandbox.modelCalls[0].url !== '/api/models') {{
                    throw new Error('activation should stop after failed backup fetch');
                }}
                if (sandbox.saveCalls.length !== 0) {{
                    throw new Error('activation saved state after backup failure');
                }}

                sandbox.modelCalls = [];
                sandbox.saveCalls = [];
                sandbox.window.ChatRawPlugin.modelFetch = async (url, options = {{}}) => {{
                    sandbox.modelCalls.push({{ url, options }});
                    return {{
                        ok: true,
                        status: 200,
                        json: async () => [
                            {{
                                id: 'default-chat',
                                type: 'chat',
                                api_url: 'https://api.original.example/v1',
                                api_key: '',
                                api_key_set: true,
                                model_id: 'original'
                            }}
                        ],
                        text: async () => '[]'
                    }};
                }};
                sandbox.fetch = async (url, options = {{}}) => {{
                    sandbox.saveCalls.push({{ url, options }});
                    return {{ ok: false, status: 500, text: async () => 'settings save failed' }};
                }};
                api.setPluginData({{
                    models: [
                        {{
                            id: 'temp-model',
                            displayName: 'Temp',
                            active: false,
                            api_url: 'https://api.temp.example/v1',
                            api_key: 'sk-temp',
                            model_id: 'temp',
                            capability: {{}},
                            context_length: 8192,
                            max_output: 4096
                        }}
                    ],
                    originalConfig: null
                }});

                await api.activateModel('temp-model');
                if (api.pluginData.models[0].active || api.pluginData.originalConfig) {{
                    throw new Error('activation proceeded after backup persistence failure');
                }}
                if (sandbox.modelCalls.length !== 1 || sandbox.modelCalls[0].url !== '/api/models') {{
                    throw new Error('backup persistence failure should stop before model save');
                }}
                if (sandbox.saveCalls.length !== 1) {{
                    throw new Error('backup persistence failure should only try to persist backup once');
                }}

                sandbox.modelCalls = [];
                sandbox.saveCalls = [];
                sandbox.window.ChatRawPlugin.modelFetch = async (url, options = {{}}) => {{
                    sandbox.modelCalls.push({{ url, options }});
                    if (sandbox.modelCalls.length === 1) {{
                        return {{
                            ok: true,
                            status: 200,
                            json: async () => [
                                {{
                                    id: 'default-chat',
                                    type: 'chat',
                                    api_url: 'https://api.original.example/v1',
                                    api_key: '',
                                    api_key_set: true,
                                    model_id: 'original'
                                }}
                            ],
                            text: async () => '[]'
                        }};
                    }}
                    return {{
                        ok: false,
                        status: 400,
                        text: async () => 'activation save failed'
                    }};
                }};
                sandbox.fetch = async (url, options = {{}}) => {{
                    sandbox.saveCalls.push({{ url, options }});
                    return {{ ok: true, status: 200, text: async () => '{{}}' }};
                }};
                api.setPluginData({{
                    models: [
                        {{
                            id: 'temp-model',
                            displayName: 'Temp',
                            active: false,
                            api_url: 'https://api.temp.example/v1',
                            api_key: 'sk-temp',
                            model_id: 'temp',
                            capability: {{}},
                            context_length: 8192,
                            max_output: 4096
                        }}
                    ],
                    originalConfig: null
                }});

                await api.activateModel('temp-model');
                if (api.pluginData.models[0].active) {{
                    throw new Error('activation left local state active after backend save failure');
                }}
                if (!api.pluginData.originalConfig) {{
                    throw new Error('activation failure lost backed up original config');
                }}
                if (sandbox.modelCalls.length !== 2) {{
                    throw new Error('activation failure should fetch backup then attempt model save');
                }}
                if (sandbox.saveCalls.length !== 2) {{
                    throw new Error('activation failure should save backup and reverted plugin state');
                }}
                const activationPayload = JSON.parse(sandbox.modelCalls[1].options.body);
                if (activationPayload.preserve_previous_api_key !== true) {{
                    throw new Error('activation did not request server-side key backup');
                }}
            }})().catch(error => {{
                process.stderr.write(error.stack || String(error));
                process.exit(1);
            }});
            """
        )

        result = subprocess.run(
            ["node", "-e", script],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_plugin_model_fetch_prompts_and_retries_after_unauthorized(self):
        script = textwrap.dedent(
            f"""
            (async () => {{
                const fs = require('fs');
                const vm = require('vm');
                const source = fs.readFileSync({str(REPO_ROOT / 'backend' / 'static' / 'app.min.js')!r}, 'utf8');
                const tokenStore = {{}};
                const sandbox = {{
                    marked: {{ setOptions() {{}}, parse(value) {{ return value; }} }},
                    window: {{
                        matchMedia() {{ return {{ matches: false }}; }},
                        prompt() {{ return 'fresh-token'; }},
                        addEventListener() {{}}
                    }},
                    localStorage: {{ getItem() {{ return null; }}, setItem() {{}} }},
                    sessionStorage: {{
                        getItem(key) {{ return tokenStore[key] || null; }},
                        setItem(key, value) {{ tokenStore[key] = value; }}
                    }},
                    document: {{
                        documentElement: {{ setAttribute() {{}} }},
                        head: {{ appendChild() {{}} }},
                        createElement() {{ return {{}}; }},
                        querySelectorAll() {{ return []; }}
                    }},
                    requestAnimationFrame(callback) {{ callback(); return 1; }},
                    cancelAnimationFrame() {{}},
                    fetchCalls: []
                }};
                sandbox.fetch = (url, options = {{}}) => {{
                    sandbox.fetchCalls.push({{ url, options }});
                    if (sandbox.fetchCalls.length === 1) {{
                        return Promise.resolve({{ status: 401, ok: false, json: async () => ({{}}) }});
                    }}
                    return Promise.resolve({{ status: 200, ok: true, json: async () => [] }});
                }};
                vm.runInNewContext(source + `
                    this.state = app();
                    this.state.initPluginSystem();
                `, sandbox);

                const response = await sandbox.window.ChatRawPlugin.modelFetch('/api/models', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: '{{}}'
                }});
                if (!response.ok || sandbox.fetchCalls.length !== 2) {{
                    throw new Error(JSON.stringify({{ status: response.status, calls: sandbox.fetchCalls }}));
                }}
                const retryHeaders = sandbox.fetchCalls[1].options.headers;
                if (
                    retryHeaders.Authorization !== 'Bearer fresh-token' ||
                    retryHeaders['Content-Type'] !== 'application/json'
                ) {{
                    throw new Error(JSON.stringify(sandbox.fetchCalls));
                }}
            }})().catch(error => {{
                process.stderr.write(error.stack || String(error));
                process.exit(1);
            }});
            """
        )

        result = subprocess.run(
            ["node", "-e", script],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_model_payload_preserves_or_clears_api_key_by_user_intent(self):
        script = textwrap.dedent(
            f"""
            const fs = require('fs');
            const vm = require('vm');
            const source = fs.readFileSync({str(REPO_ROOT / 'backend' / 'static' / 'app.js')!r}, 'utf8');
            const sandbox = {{
                marked: {{ setOptions() {{}} }},
                window: {{ matchMedia() {{ return {{ matches: false }}; }} }},
                localStorage: {{ getItem() {{ return null; }}, setItem() {{}} }},
                document: {{
                    head: {{ appendChild() {{}} }},
                    createElement() {{ return {{}}; }},
                    querySelectorAll() {{ return []; }}
                }}
            }};
            vm.runInNewContext(source + `
                const state = app();
                this.preserve = state.prepareModelPayload({{
                    id: 'secret-chat',
                    api_key_set: true,
                    api_key: '',
                    api_key_touched: false,
                    status: 'loading',
                    verifyMessage: 'pending'
                }});
                this.clear = state.prepareModelPayload({{
                    id: 'secret-chat',
                    api_key_set: true,
                    api_key: '',
                    api_key_touched: true
                }});
            `, sandbox);
            if (Object.prototype.hasOwnProperty.call(sandbox.preserve, 'api_key')) {{
                process.stderr.write(JSON.stringify(sandbox.preserve));
                process.exit(1);
            }}
            if (sandbox.clear.api_key !== '') {{
                process.stderr.write(JSON.stringify(sandbox.clear));
                process.exit(1);
            }}
            if ('api_key_set' in sandbox.clear || 'api_key_touched' in sandbox.clear) {{
                process.stderr.write(JSON.stringify(sandbox.clear));
                process.exit(1);
            }}
            """
        )

        result = subprocess.run(
            ["node", "-e", script],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_model_fetch_prompts_and_retries_with_auth_token(self):
        script = textwrap.dedent(
            f"""
            const fs = require('fs');
            const vm = require('vm');
            const source = fs.readFileSync({str(REPO_ROOT / 'backend' / 'static' / 'app.js')!r}, 'utf8');
            const calls = [];
            const store = {{}};
            const sandbox = {{
                calls,
                store,
                marked: {{ setOptions() {{}} }},
                window: {{
                    matchMedia() {{ return {{ matches: false }}; }},
                    prompt() {{ return 'test-token'; }}
                }},
                localStorage: {{ getItem() {{ return null; }}, setItem() {{}} }},
                sessionStorage: {{
                    getItem(key) {{ return store[key] || null; }},
                    setItem(key, value) {{ store[key] = value; }}
                }},
                document: {{
                    head: {{ appendChild() {{}} }},
                    createElement() {{ return {{}}; }},
                    querySelectorAll() {{ return []; }}
                }},
                fetch: async (url, options = {{}}) => {{
                    calls.push({{ url, headers: options.headers || {{}} }});
                    return {{
                        status: calls.length === 1 ? 401 : 200,
                        ok: calls.length > 1,
                        json: async () => []
                    }};
                }}
            }};
            (async () => {{
                vm.runInNewContext(source + `
                    this.done = (async () => {{
                        const state = app();
                        const response = await state.modelFetch('/api/models');
                        this.status = response.status;
                        this.storedToken = store.chatraw_model_auth_token;
                    }})();
                `, sandbox);
                await sandbox.done;
                if (sandbox.status !== 200) {{
                    process.stderr.write('unexpected status ' + sandbox.status);
                    process.exit(1);
                }}
                if (sandbox.calls.length !== 2) {{
                    process.stderr.write(JSON.stringify(sandbox.calls));
                    process.exit(1);
                }}
                if (sandbox.calls[0].headers.Authorization) {{
                    process.stderr.write(JSON.stringify(sandbox.calls[0]));
                    process.exit(1);
                }}
                if (sandbox.calls[1].headers.Authorization !== 'Bearer test-token') {{
                    process.stderr.write(JSON.stringify(sandbox.calls[1]));
                    process.exit(1);
                }}
                if (sandbox.storedToken !== 'test-token') {{
                    process.stderr.write('token not stored');
                    process.exit(1);
                }}
            }})().catch(error => {{
                process.stderr.write(error.stack || String(error));
                process.exit(1);
            }});
            """
        )

        result = subprocess.run(
            ["node", "-e", script],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_save_all_settings_reports_model_save_failure(self):
        script = textwrap.dedent(
            f"""
            const fs = require('fs');
            const vm = require('vm');
            const source = fs.readFileSync({str(REPO_ROOT / 'backend' / 'static' / 'app.js')!r}, 'utf8');
            const calls = [];
            const toasts = [];
            const sandbox = {{
                calls,
                toasts,
                marked: {{ setOptions() {{}} }},
                window: {{
                    matchMedia() {{ return {{ matches: false }}; }},
                    prompt() {{ return ''; }}
                }},
                localStorage: {{ getItem() {{ return null; }}, setItem() {{}} }},
                sessionStorage: {{ getItem() {{ return null; }}, setItem() {{}} }},
                document: {{
                    head: {{ appendChild() {{}} }},
                    createElement() {{ return {{}}; }},
                    querySelectorAll() {{ return []; }},
                    documentElement: {{ setAttribute() {{}} }}
                }},
                fetch: async (url, options = {{}}) => {{
                    calls.push({{ url, method: options.method || 'GET' }});
                    if (url === '/api/settings') {{
                        return {{ status: 200, ok: true, json: async () => ({{ success: true }}) }};
                    }}
                    if (url === '/api/models') {{
                        return {{ status: 401, ok: false, json: async () => ({{ error: 'Unauthorized' }}) }};
                    }}
                    return {{ status: 404, ok: false, json: async () => ({{}}) }};
                }}
            }};
            (async () => {{
                vm.runInNewContext(source + `
                    this.done = (async () => {{
                        const state = app();
                        state.showToast = (message, type) => toasts.push({{ message, type }});
                        state.applyTheme = () => {{ this.appliedTheme = true; }};
                        state.showSettings = true;
                        state.models = [{{
                            id: 'secret-chat',
                            name: 'Secret Chat',
                            model_id: 'chat-model',
                            api_url: 'https://example.com/v1',
                            type: 'chat',
                            api_key: '',
                            api_key_set: true,
                            api_key_touched: false
                        }}];
                        await state.saveAllSettings();
                        this.showSettings = state.showSettings;
                    }})();
                `, sandbox);
                await sandbox.done;
                if (sandbox.showSettings !== true) {{
                    process.stderr.write('settings panel closed after failed model save');
                    process.exit(1);
                }}
                if (sandbox.appliedTheme) {{
                    process.stderr.write('theme applied after failed model save');
                    process.exit(1);
                }}
                if (!sandbox.calls.some(call => call.url === '/api/models' && call.method === 'POST')) {{
                    process.stderr.write(JSON.stringify(sandbox.calls));
                    process.exit(1);
                }}
                if (sandbox.toasts.some(toast => toast.message === 'Settings saved')) {{
                    process.stderr.write(JSON.stringify(sandbox.toasts));
                    process.exit(1);
                }}
                const lastToast = sandbox.toasts[sandbox.toasts.length - 1];
                if (!lastToast || lastToast.type !== 'error' || !lastToast.message.startsWith('Save failed:')) {{
                    process.stderr.write(JSON.stringify(sandbox.toasts));
                    process.exit(1);
                }}
            }})().catch(error => {{
                process.stderr.write(error.stack || String(error));
                process.exit(1);
            }});
            """
        )

        result = subprocess.run(
            ["node", "-e", script],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
