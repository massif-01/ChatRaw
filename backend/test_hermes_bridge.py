import asyncio
import json
import os
import shutil
import sys
import tempfile
import unittest

TEST_DATA_DIR = tempfile.mkdtemp(prefix="chatraw-hermes-test-")
os.environ["DATA_DIR"] = TEST_DATA_DIR

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend import main  # noqa: E402


def tearDownModule():
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)


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


class FakeStreamContent:
    def __init__(self, chunks):
        self.chunks = chunks

    async def iter_any(self):
        for chunk in self.chunks:
            yield chunk


class FakeHermesResponse:
    def __init__(self, status=200, json_data=None, text_data="", stream_chunks=None):
        self.status = status
        self._json_data = json_data if json_data is not None else {}
        self._text_data = text_data
        self.content = FakeStreamContent(stream_chunks or [])

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return self._json_data

    async def text(self):
        return self._text_data


class FakeHermesSession:
    def __init__(self, get_response=None, post_response=None, get_responses=None, post_responses=None):
        self.get_response = get_response or FakeHermesResponse(json_data={"data": []})
        self.post_response = post_response or FakeHermesResponse(json_data={"choices": [{"message": {"content": "ok"}}]})
        self.get_responses = list(get_responses or [])
        self.post_responses = list(post_responses or [])
        self.gets = []
        self.posts = []

    def get(self, url, **kwargs):
        self.gets.append({"url": url, **kwargs})
        if self.get_responses:
            return self.get_responses.pop(0)
        return self.get_response

    def post(self, url, **kwargs):
        self.posts.append({"url": url, **kwargs})
        if self.post_responses:
            return self.post_responses.pop(0)
        return self.post_response


class FailingSession:
    def __init__(self, error):
        self.error = error

    def post(self, *args, **kwargs):
        raise self.error


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


class HermesBridgeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
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

        self.original_cors_origins = main.CORS_ORIGINS
        self.addCleanup(lambda: setattr(main, "CORS_ORIGINS", self.original_cors_origins))

    def enable_hermes(
        self,
        enabled=True,
        installed=True,
        api_key="secret",
        base_url="http://127.0.0.1:8642/v1",
        model="hermes-agent",
        session_key="",
        api_mode=None,
        allowed_remote_base_urls="",
        remote_warning_accepted=False,
        remote_warning_accepted_for="",
    ):
        if installed:
            plugin_dir = os.path.join(main.PLUGINS_INSTALLED_DIR, main.HERMES_PLUGIN_ID)
            os.makedirs(plugin_dir, exist_ok=True)
            with open(os.path.join(plugin_dir, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump({"id": main.HERMES_PLUGIN_ID}, f)
        settings_values = {
            "baseUrl": base_url,
            "model": model,
        }
        if api_mode is not None:
            settings_values["apiMode"] = api_mode
        if allowed_remote_base_urls:
            settings_values["allowedRemoteBaseUrls"] = allowed_remote_base_urls
        if remote_warning_accepted:
            settings_values["remoteBaseUrlWarningAccepted"] = True
        if remote_warning_accepted_for:
            settings_values["remoteBaseUrlWarningAcceptedFor"] = remote_warning_accepted_for
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

    def configure_chat(self, stream=False, system_prompt="Base system prompt."):
        settings = main.db.get_settings()
        settings.chat_settings.stream = stream
        settings.chat_settings.system_prompt = system_prompt
        main.db.save_settings(settings)

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

    async def collect_stream(self, response):
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk)
        return chunks

    def chat_count(self):
        cursor = main.db.get_conn().cursor()
        cursor.execute("SELECT COUNT(*) AS count FROM chats")
        return cursor.fetchone()["count"]

    def message_count(self):
        cursor = main.db.get_conn().cursor()
        cursor.execute("SELECT COUNT(*) AS count FROM messages")
        return cursor.fetchone()["count"]

    async def test_hermes_requires_installed_enabled_plugin(self):
        result = await main.hermes_health(JsonRequest(url="http://testserver/api/hermes/health"))
        status, data = self.decode_result(result)
        self.assertEqual(status, 403)
        self.assertFalse(data["success"])

        self.enable_hermes(enabled=True, installed=False)
        result = await main.hermes_chat(JsonRequest({"message": "hi"}))
        status, data = self.decode_result(result)
        self.assertEqual(status, 403)
        self.assertIn("Hermes plugin is not enabled", data["error"])

        self.enable_hermes(enabled=False)
        result = await main.hermes_chat(JsonRequest({"message": "hi"}))
        status, data = self.decode_result(result)
        self.assertEqual(status, 403)
        self.assertIn("Hermes plugin is not enabled", data["error"])

    async def test_origin_gate_allows_same_origin_and_explicit_cors_only(self):
        self.enable_hermes()
        fake_session = self.patch_session(FakeHermesSession())

        for fetch_site in ("cross-site", "same-site", "unknown", None):
            with self.subTest(fetch_site=fetch_site):
                result = await main.hermes_health(JsonRequest(
                    url="http://testserver/api/hermes/health",
                    fetch_site=fetch_site,
                ))
                status, data = self.decode_result(result)
                self.assertEqual(status, 403)
                self.assertFalse(data["success"])
        self.assertEqual(fake_session.gets, [])

        result = await main.hermes_health(JsonRequest(
            origin="http://evil.test",
            url="http://testserver/api/hermes/health",
        ))
        status, data = self.decode_result(result)
        self.assertEqual(status, 403)
        self.assertFalse(data["success"])
        self.assertEqual(fake_session.gets, [])

        result = await main.hermes_health(JsonRequest(
            url="http://testserver/api/hermes/health",
            headers={"referer": "http://testserver/"},
            fetch_site=None,
        ))
        status, data = self.decode_result(result)
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])

        result = await main.hermes_health(JsonRequest(
            url="http://testserver/api/hermes/health",
            headers={"referer": "http://evil.test/"},
            fetch_site=None,
        ))
        status, data = self.decode_result(result)
        self.assertEqual(status, 403)
        self.assertFalse(data["success"])

        result = await main.hermes_health(JsonRequest(
            origin="http://testserver",
            url="http://testserver/api/hermes/health",
        ))
        status, data = self.decode_result(result)
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])

        result = await main.hermes_health(JsonRequest(
            url="http://testserver/api/hermes/health",
            fetch_site="none",
        ))
        status, data = self.decode_result(result)
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])

        main.CORS_ORIGINS = "http://allowed.test"
        result = await main.hermes_health(JsonRequest(
            origin="http://allowed.test",
            url="http://testserver/api/hermes/health",
        ))
        status, data = self.decode_result(result)
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])

    async def test_origin_gate_blocks_chat_without_allowed_fetch_metadata(self):
        self.enable_hermes()
        fake_session = self.patch_session(FakeHermesSession())

        for fetch_site in ("cross-site", "same-site", "unknown", None):
            with self.subTest(fetch_site=fetch_site):
                result = await main.hermes_chat(JsonRequest(
                    {"message": "blocked"},
                    fetch_site=fetch_site,
                ))
                status, data = self.decode_result(result)
                self.assertEqual(status, 403)
                self.assertIn("Origin", data["error"])

        self.assertEqual(fake_session.posts, [])
        self.assertEqual(fake_session.gets, [])
        self.assertEqual(self.chat_count(), 0)
        self.assertEqual(self.message_count(), 0)

    async def test_limited_hermes_error_text_reads_bounded_bytes(self):
        class LimitedContent:
            def __init__(self, payload):
                self.payload = payload
                self.read_sizes = []

            async def read(self, size):
                self.read_sizes.append(size)
                return self.payload[:size]

        class LimitedResponse:
            def __init__(self, payload):
                self.content = LimitedContent(payload)

            async def text(self):
                raise AssertionError("text() should not be used when content.read is available")

        response = LimitedResponse(b"a" * 1000)
        text = await main._read_limited_response_text(response, limit=25)

        self.assertEqual(response.content.read_sizes, [26])
        self.assertEqual(text, "a" * 25)

        boundary_response = LimitedResponse("€".encode("utf-8"))
        boundary_text = await main._read_limited_response_text(boundary_response, limit=1)
        self.assertEqual(boundary_response.content.read_sizes, [2])
        self.assertEqual(boundary_text, "\ufffd")

    async def test_missing_api_key_calls_chat_without_authorization(self):
        self.enable_hermes(api_key="")
        self.configure_chat(stream=False)
        fake_session = self.patch_session(FakeHermesSession())

        result = await main.hermes_chat(JsonRequest({"message": "hi"}))
        status, data = self.decode_result(result)
        self.assertEqual(status, 200)
        self.assertEqual(data["content"], "ok")
        self.assertEqual(fake_session.posts[0]["url"], "http://127.0.0.1:8642/v1/chat/completions")
        self.assertNotIn("Authorization", fake_session.posts[0]["headers"])

    async def test_hermes_health_without_api_key_omits_authorization(self):
        self.enable_hermes(api_key="")
        fake_session = self.patch_session(FakeHermesSession())

        result = await main.hermes_health(JsonRequest(url="http://testserver/api/hermes/health"))
        status, data = self.decode_result(result)

        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertEqual(fake_session.gets[0]["url"], "http://127.0.0.1:8642/v1/models")
        self.assertNotIn("Authorization", fake_session.gets[0]["headers"])
        self.assertEqual(fake_session.posts, [])

    async def test_invalid_persisted_api_mode_does_not_call_hermes(self):
        self.enable_hermes(api_mode="https://evil.test/runs")
        called = False

        async def fail_if_called():
            nonlocal called
            called = True
            return FakeHermesSession()

        original = main.get_http_session
        main.get_http_session = fail_if_called
        self.addCleanup(lambda: setattr(main, "get_http_session", original))

        result = await main.hermes_chat(JsonRequest({"message": "hi"}))
        status, data = self.decode_result(result)
        self.assertEqual(status, 400)
        self.assertIn("Unsupported Hermes API mode", data["error"])
        self.assertFalse(called)
        self.assertEqual(self.chat_count(), 0)

    def test_hermes_base_url_validation(self):
        accepted = [
            "http://127.0.0.1:8642/v1",
            "http://localhost:8642/v1",
            "http://[::1]:8642/v1",
        ]
        for url in accepted:
            with self.subTest(url=url):
                self.assertEqual(main.validate_hermes_base_url(url), url.rstrip("/"))

        rejected = [
            "http://example.com/v1",
            "https://example.com/v1",
            "http://8.8.8.8:8642/v1",
            "http://192.168.1.10:8642/v1",
            "http://10.0.0.2:8642/v1",
            "http://172.16.0.5:8642/v1",
            "http://0.0.0.0:8642/v1",
            "http://user:pass@127.0.0.1:8642/v1",
            "http://127.0.0.1:8642/v1?x=1",
            "http://127.0.0.1:8642/v1#frag",
            "http:///v1",
            "ftp://127.0.0.1:8642/v1",
        ]
        for url in rejected:
            with self.subTest(url=url):
                with self.assertRaises(main.HermesBridgeError):
                    main.validate_hermes_base_url(url)

        allowed = "http://10.10.99.99:9119, http://10.10.99.100:8642/v1/"
        allowed_urls, canonical_allowed = main.parse_hermes_allowed_remote_base_urls(allowed)
        self.assertEqual(allowed_urls, [
            "http://10.10.99.100:8642/v1",
            "http://10.10.99.99:9119",
        ])
        self.assertEqual(
            canonical_allowed,
            "http://10.10.99.100:8642/v1\nhttp://10.10.99.99:9119",
        )
        self.assertEqual(
            main.validate_hermes_base_url(
                "http://10.10.99.99:9119/",
                allowed,
                True,
                canonical_allowed,
            ),
            "http://10.10.99.99:9119",
        )
        self.assertEqual(
            main.validate_hermes_base_url(
                "http://10.10.99.100:8642/v1",
                allowed,
                True,
                canonical_allowed,
            ),
            "http://10.10.99.100:8642/v1",
        )

        remote_rejected = [
            ("http://10.10.99.99:9119", allowed, False, canonical_allowed),
            ("http://10.10.99.99:9119", allowed, True, "http://10.10.99.99:9119"),
            ("http://10.10.99.98:9119", allowed, True, canonical_allowed),
            ("http://10.10.99.99:9119", "http://10.10.99.99:9119\nftp://bad.test/v1", True, canonical_allowed),
        ]
        for base_url, allowed_value, accepted_warning, accepted_for in remote_rejected:
            with self.subTest(base_url=base_url, allowed=allowed_value, accepted_for=accepted_for):
                with self.assertRaises(main.HermesBridgeError):
                    main.validate_hermes_base_url(base_url, allowed_value, accepted_warning, accepted_for)

        with self.assertRaises(main.HermesBridgeError):
            main.parse_hermes_allowed_remote_base_urls(
                "\n".join(f"http://10.10.99.{index}:9119" for index in range(21))
            )

        with self.assertRaises(main.HermesBridgeError):
            main.parse_hermes_allowed_remote_base_urls(f"http://10.10.99.99/{'a' * 300}")

        idn_allowed = "http://例子.测试:8642/v1/\nhttp://faß.de/v1\nhttp://☃.net/v1"
        idn_urls, idn_canonical = main.parse_hermes_allowed_remote_base_urls(idn_allowed)
        self.assertEqual(idn_urls, [
            "http://xn--fa-hia.de/v1",
            "http://xn--fsqu00a.xn--0zwm56d:8642/v1",
            "http://xn--n3h.net/v1",
        ])
        self.assertEqual(idn_canonical, "\n".join(idn_urls))
        self.assertEqual(
            main.validate_hermes_base_url(
                "http://例子.测试:8642/v1/",
                idn_allowed,
                True,
                "http://xn--fa-hia.de/v1\nhttp://xn--fsqu00a.xn--0zwm56d:8642/v1\nhttp://xn--n3h.net/v1",
            ),
            "http://xn--fsqu00a.xn--0zwm56d:8642/v1",
        )
        self.assertEqual(
            main.validate_hermes_base_url(
                "http://faß.de/v1",
                "http://xn--fa-hia.de/v1",
                True,
                "http://faß.de/v1",
            ),
            "http://xn--fa-hia.de/v1",
        )

        path_or_host_rejected = [
            "http://127.0.0.256:8642/v1",
            "http://127.999.1.1:8642/v1",
            "http://10.10.99.99/é",
            "http://10.10.99.99/v%201",
            "http://10.10.99.99/v 1",
            "http://10.10.99.99/a/../b",
            "http://10.10.99.99//v1",
            "http://10.10.99.99/v1//",
        ]
        for url in path_or_host_rejected:
            with self.subTest(url=url):
                with self.assertRaises(main.HermesBridgeError):
                    main.parse_hermes_allowed_remote_base_urls(url)

    async def test_hermes_remote_base_url_normalize_endpoint(self):
        result = await main.hermes_normalize_remote_base_urls(JsonRequest(
            {
                "baseUrl": "http://例子.测试:8642/v1/",
                "allowedRemoteBaseUrls": "http://faß.de/v1\nhttp://例子.测试:8642/v1/",
            },
            url="http://testserver/api/hermes/remote-base-urls/normalize",
        ))
        status, data = self.decode_result(result)

        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["baseUrl"], "http://xn--fsqu00a.xn--0zwm56d:8642/v1")
        self.assertFalse(data["baseUrlIsLoopback"])
        self.assertEqual(data["allowedRemoteBaseUrls"], [
            "http://xn--fa-hia.de/v1",
            "http://xn--fsqu00a.xn--0zwm56d:8642/v1",
        ])
        self.assertEqual(
            data["canonicalAllowed"],
            "http://xn--fa-hia.de/v1\nhttp://xn--fsqu00a.xn--0zwm56d:8642/v1",
        )

        result = await main.hermes_normalize_remote_base_urls(JsonRequest(
            {
                "baseUrl": "http://127.0.0.256:8642/v1",
                "allowedRemoteBaseUrls": "",
            },
            url="http://testserver/api/hermes/remote-base-urls/normalize",
        ))
        status, data = self.decode_result(result)

        self.assertEqual(status, 400)
        self.assertFalse(data["success"])
        self.assertIn("Invalid Hermes base URL", data["error"])

    async def test_hermes_health_allows_confirmed_remote_base_url(self):
        allowed = "http://10.10.99.100:8642/v1\nhttp://10.10.99.99:9119"
        _, canonical_allowed = main.parse_hermes_allowed_remote_base_urls(allowed)
        self.enable_hermes(
            base_url="http://10.10.99.99:9119/",
            allowed_remote_base_urls=allowed,
            remote_warning_accepted=True,
            remote_warning_accepted_for=canonical_allowed,
        )
        fake_session = self.patch_session(FakeHermesSession())

        result = await main.hermes_health(JsonRequest(url="http://testserver/api/hermes/health"))
        status, data = self.decode_result(result)

        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertEqual(fake_session.gets[0]["url"], "http://10.10.99.99:9119/models")
        self.assertEqual(fake_session.gets[0]["headers"]["Authorization"], "Bearer secret")

    async def test_hermes_health_uses_punycode_for_unicode_remote_base_url(self):
        allowed = "http://例子.测试:8642/v1"
        _, canonical_allowed = main.parse_hermes_allowed_remote_base_urls(allowed)
        self.enable_hermes(
            base_url="http://例子.测试:8642/v1/",
            allowed_remote_base_urls=allowed,
            remote_warning_accepted=True,
            remote_warning_accepted_for=canonical_allowed,
        )
        fake_session = self.patch_session(FakeHermesSession())

        result = await main.hermes_health(JsonRequest(url="http://testserver/api/hermes/health"))
        status, data = self.decode_result(result)

        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["base_url"], "http://xn--fsqu00a.xn--0zwm56d:8642/v1")
        self.assertEqual(fake_session.gets[0]["url"], "http://xn--fsqu00a.xn--0zwm56d:8642/v1/models")

    async def test_hermes_chat_allows_confirmed_remote_base_url(self):
        allowed = "http://10.10.99.100:8642/v1\nhttp://10.10.99.99:9119"
        _, canonical_allowed = main.parse_hermes_allowed_remote_base_urls(allowed)
        self.enable_hermes(
            base_url="http://10.10.99.100:8642/v1/",
            allowed_remote_base_urls=allowed,
            remote_warning_accepted=True,
            remote_warning_accepted_for=canonical_allowed,
        )
        self.configure_chat(stream=False)
        fake_session = self.patch_session(FakeHermesSession())

        result = await main.hermes_chat(JsonRequest({"message": "hi"}))
        status, data = self.decode_result(result)

        self.assertEqual(status, 200)
        self.assertEqual(data["content"], "ok")
        self.assertEqual(fake_session.posts[0]["url"], "http://10.10.99.100:8642/v1/chat/completions")
        self.assertEqual(fake_session.posts[0]["headers"]["Authorization"], "Bearer secret")

    async def test_hermes_health_uses_models_without_chat_side_effects(self):
        self.enable_hermes()
        fake_session = self.patch_session(FakeHermesSession())

        result = await main.hermes_health(JsonRequest(url="http://testserver/api/hermes/health"))
        status, data = self.decode_result(result)

        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertEqual(fake_session.gets[0]["url"], "http://127.0.0.1:8642/v1/models")
        self.assertEqual(fake_session.gets[0]["headers"]["Authorization"], "Bearer secret")
        self.assertNotIn("X-Hermes-Session-Id", fake_session.gets[0]["headers"])
        self.assertNotIn("X-Hermes-Session-Key", fake_session.gets[0]["headers"])
        self.assertFalse(fake_session.gets[0]["allow_redirects"])
        self.assertEqual(len(fake_session.gets), 1)
        self.assertEqual(fake_session.posts, [])
        self.assertEqual(self.chat_count(), 0)
        self.assertEqual(self.message_count(), 0)

    async def test_hermes_non_stream_saves_history_thinking_and_title(self):
        self.enable_hermes(base_url="http://localhost:8642/v1", model="hermes-model")
        self.configure_chat(stream=False)
        fake_session = self.patch_session(FakeHermesSession(post_response=FakeHermesResponse(
            json_data={
                "choices": [
                    {
                        "message": {
                            "content": "assistant answer",
                            "reasoning_content": "private thought",
                        }
                    }
                ]
            }
        )))

        result = await main.hermes_chat(JsonRequest({
            "message": "hello hermes",
            "use_thinking": True,
        }))
        status, data = self.decode_result(result)

        self.assertEqual(status, 200)
        self.assertEqual(set(data.keys()), {"chat_id", "content", "thinking", "references"})
        self.assertEqual(data["content"], "assistant answer")
        self.assertEqual(data["thinking"], "private thought")
        self.assertEqual(fake_session.posts[0]["url"], "http://localhost:8642/v1/chat/completions")
        self.assertEqual(fake_session.posts[0]["json"]["model"], "hermes-model")
        self.assertEqual(fake_session.posts[0]["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(fake_session.posts[0]["headers"]["X-Hermes-Session-Id"], f"chatraw-{data['chat_id']}")
        self.assertNotIn("X-Hermes-Session-Key", fake_session.posts[0]["headers"])

        messages = main.db.get_messages(data["chat_id"])
        self.assertEqual(messages[0].role, "user")
        self.assertEqual(messages[0].content, "hello hermes")
        self.assertEqual(
            messages[1].content,
            "<thinking>\nprivate thought\n</thinking>\n\nassistant answer",
        )
        chats = main.db.get_chats()
        self.assertEqual(chats[0].title, "hello hermes")

    async def test_hermes_rejects_transport_fields_before_side_effects(self):
        self.enable_hermes()
        fake_session = self.patch_session(FakeHermesSession())

        result = await main.hermes_chat(JsonRequest({
            "message": "hi",
            "baseUrl": "https://evil.test/v1",
            "model": "evil-model",
            "apiKey": "leaked",
            "headers": {"Authorization": "Bearer leaked"},
            "session_id": "attacker-session",
            "x-hermes-session-key": "attacker-key",
        }))
        status, data = self.decode_result(result)

        self.assertEqual(status, 400)
        self.assertIn("transport fields", data["error"])
        self.assertEqual(fake_session.posts, [])
        self.assertEqual(self.chat_count(), 0)

    async def test_hermes_rejects_session_fields_before_config_lookup(self):
        self.enable_hermes(api_key="")
        called = False

        async def fail_if_called():
            nonlocal called
            called = True
            return FakeHermesSession()

        original = main.get_http_session
        main.get_http_session = fail_if_called
        self.addCleanup(lambda: setattr(main, "get_http_session", original))

        result = await main.hermes_chat(JsonRequest({
            "message": "hi",
            "sessionId": "attacker-session",
        }))
        status, data = self.decode_result(result)

        self.assertEqual(status, 400)
        self.assertIn("transport fields", data["error"])
        self.assertFalse(called)
        self.assertEqual(self.chat_count(), 0)

    async def test_hermes_suppresses_thinking_unless_requested(self):
        self.enable_hermes()
        self.configure_chat(stream=False)
        self.patch_session(FakeHermesSession(post_response=FakeHermesResponse(
            json_data={
                "choices": [
                    {
                        "message": {
                            "content": "assistant answer",
                            "reasoning_content": "private thought",
                        }
                    }
                ]
            }
        )))

        result = await main.hermes_chat(JsonRequest({"message": "hello hermes"}))
        status, data = self.decode_result(result)

        self.assertEqual(status, 200)
        self.assertEqual(data["content"], "assistant answer")
        self.assertEqual(data["thinking"], "")
        messages = main.db.get_messages(data["chat_id"])
        self.assertEqual(messages[1].content, "assistant answer")

    async def test_missing_api_mode_defaults_to_chat_completions_without_run(self):
        self.enable_hermes()
        self.configure_chat(stream=False)
        fake_session = self.patch_session(FakeHermesSession(post_response=FakeHermesResponse(
            json_data={"choices": [{"message": {"content": "default answer"}}]}
        )))

        result = await main.hermes_chat(JsonRequest({"message": "default mode"}))
        status, data = self.decode_result(result)

        self.assertEqual(status, 200)
        self.assertEqual(data["content"], "default answer")
        self.assertEqual(len(fake_session.posts), 1)
        self.assertEqual(fake_session.posts[0]["url"], "http://127.0.0.1:8642/v1/chat/completions")
        self.assertFalse(fake_session.posts[0]["allow_redirects"])
        self.assertEqual(fake_session.gets, [])

    async def test_hermes_session_header_is_stable_per_chat_and_differs_across_chats(self):
        self.enable_hermes()
        self.configure_chat(stream=False)
        fake_session = self.patch_session(FakeHermesSession(post_response=FakeHermesResponse(
            json_data={"choices": [{"message": {"content": "answer"}}]}
        )))

        first = await main.hermes_chat(JsonRequest({"message": "first"}))
        _, first_data = self.decode_result(first)
        second = await main.hermes_chat(JsonRequest({"chat_id": first_data["chat_id"], "message": "second"}))
        _, second_data = self.decode_result(second)
        third = await main.hermes_chat(JsonRequest({"message": "third"}))
        _, third_data = self.decode_result(third)

        first_session = fake_session.posts[0]["headers"]["X-Hermes-Session-Id"]
        second_session = fake_session.posts[1]["headers"]["X-Hermes-Session-Id"]
        third_session = fake_session.posts[2]["headers"]["X-Hermes-Session-Id"]
        self.assertEqual(first_data["chat_id"], second_data["chat_id"])
        self.assertEqual(first_session, second_session)
        self.assertEqual(first_session, f"chatraw-{first_data['chat_id']}")
        self.assertEqual(third_session, f"chatraw-{third_data['chat_id']}")
        self.assertNotEqual(first_session, third_session)

    async def test_hermes_session_key_is_optional_backend_saved_header(self):
        self.enable_hermes(session_key="trusted-session-key")
        self.configure_chat(stream=False)
        fake_session = self.patch_session(FakeHermesSession(post_response=FakeHermesResponse(
            json_data={"choices": [{"message": {"content": "answer"}}]}
        )))

        result = await main.hermes_chat(JsonRequest(
            {"message": "hi"},
            headers={
                "X-Hermes-Session-Id": "attacker-session",
                "X-Hermes-Session-Key": "attacker-key",
            },
        ))
        _, data = self.decode_result(result)

        headers = fake_session.posts[0]["headers"]
        self.assertEqual(headers["X-Hermes-Session-Id"], f"chatraw-{data['chat_id']}")
        self.assertEqual(headers["X-Hermes-Session-Key"], "trusted-session-key")

    async def test_hermes_stream_converts_sse_multibyte_and_saves(self):
        self.enable_hermes()
        self.configure_chat(stream=True)
        line_content = 'data: {"choices":[{"delta":{"content":"你"}}]}\n'.encode("utf-8")
        line_thinking = 'data: {"choices":[{"delta":{"thinking":"想"}}]}\n'.encode("utf-8")
        chunks = [
            line_content[:38],
            line_content[38:],
            line_thinking,
            b"data: [DONE]\n",
        ]
        fake_session = self.patch_session(FakeHermesSession(post_response=FakeHermesResponse(stream_chunks=chunks)))

        response = await main.hermes_chat(JsonRequest({"message": "stream please", "use_thinking": True}))
        stream_chunks = await self.collect_stream(response)

        self.assertIn('"chat_id"', stream_chunks[0])
        self.assertTrue(any('"content": "\\u4f60"' in chunk for chunk in stream_chunks))
        self.assertTrue(any('"thinking": "\\u60f3"' in chunk for chunk in stream_chunks))
        self.assertTrue(any('"done": true' in chunk for chunk in stream_chunks))
        self.assertEqual(fake_session.posts[0]["json"]["stream"], True)

        chat_id = json.loads(stream_chunks[0])["chat_id"]
        self.assertEqual(fake_session.posts[0]["headers"]["X-Hermes-Session-Id"], f"chatraw-{chat_id}")
        messages = main.db.get_messages(chat_id)
        self.assertEqual(messages[1].content, "<thinking>\n想\n</thinking>\n\n你")

    def test_hermes_run_event_parser_maps_supported_fields_and_ignores_tools(self):
        self.assertEqual(
            main.normalize_hermes_run_event({"type": "message.delta", "delta": {"content": "Hi"}})["content_delta"],
            "Hi",
        )
        self.assertEqual(
            main.normalize_hermes_run_event({"type": "message.delta", "delta": "Hi"})["content_delta"],
            "Hi",
        )
        self.assertEqual(
            main.normalize_hermes_run_event({
                "event": "message",
                "data": {"type": "message.delta", "delta": {"content": "Hi"}},
            })["content_delta"],
            "Hi",
        )
        self.assertEqual(
            main.normalize_hermes_run_event({"output_text": "Answer"})["content_delta"],
            "Answer",
        )
        self.assertEqual(
            main.normalize_hermes_run_event({"delta": {"reasoning_content": "Think"}})["thinking_delta"],
            "Think",
        )
        self.assertEqual(
            main.normalize_hermes_run_event({"type": "tool.progress", "message": "running"}),
            {},
        )
        self.assertEqual(
            main.normalize_hermes_run_event({
                "event": "message",
                "data": {"type": "tool.progress", "message": "running"},
            }),
            {},
        )
        failed = main.normalize_hermes_run_event({"status": "failed", "error": {"message": "boom"}})
        self.assertTrue(failed["terminal"])
        self.assertEqual(failed["error"], "boom")
        approval = main.normalize_hermes_run_event({"type": "run.requires_action"})
        self.assertTrue(approval["approval_required"])
        self.assertIn("approval", approval["error"])

    async def test_hermes_runs_stream_converts_events_and_saves(self):
        self.enable_hermes(api_mode=main.HERMES_API_MODE_RUNS)
        self.configure_chat(stream=True)
        event_chunks = [
            b'event: message.delta\ndata: {"delta":"Hello "}\n\n',
            b'event: message.delta\ndata: {"delta":{"reasoning_content":"Plan"}}\n\n',
            b'event: tool.progress\ndata: {"message":"ignored"}\n\n',
            b'data: {"output_text":"world"}\n\n',
            b'event: run.completed\ndata: {}\n\n',
        ]
        fake_session = self.patch_session(FakeHermesSession(
            post_responses=[FakeHermesResponse(json_data={"run_id": "run-1"})],
            get_response=FakeHermesResponse(stream_chunks=event_chunks),
        ))

        response = await main.hermes_chat(JsonRequest({"message": "run please", "use_thinking": True}))
        stream_chunks = await self.collect_stream(response)

        self.assertIn('"chat_id"', stream_chunks[0])
        self.assertEqual(fake_session.posts[0]["url"], "http://127.0.0.1:8642/v1/runs")
        self.assertEqual(fake_session.gets[0]["url"], "http://127.0.0.1:8642/v1/runs/run-1/events")
        run_payload = fake_session.posts[0]["json"]
        self.assertEqual(run_payload["model"], "hermes-agent")
        self.assertEqual(run_payload["input"], "run please")
        self.assertEqual(run_payload["instructions"], "Base system prompt.")
        self.assertNotIn("messages", run_payload)
        self.assertNotIn("stream", run_payload)
        self.assertTrue(any('"content": "Hello "' in chunk for chunk in stream_chunks))
        self.assertTrue(any('"content": "world"' in chunk for chunk in stream_chunks))
        self.assertTrue(any('"thinking": "Plan"' in chunk for chunk in stream_chunks))
        self.assertTrue(any('"done": true' in chunk for chunk in stream_chunks))

        chat_id = json.loads(stream_chunks[0])["chat_id"]
        self.assertEqual(fake_session.posts[0]["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(fake_session.gets[0]["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(fake_session.posts[0]["headers"]["X-Hermes-Session-Id"], f"chatraw-{chat_id}")
        self.assertEqual(fake_session.gets[0]["headers"]["X-Hermes-Session-Id"], f"chatraw-{chat_id}")
        messages = main.db.get_messages(chat_id)
        self.assertEqual(messages[1].content, "<thinking>\nPlan\n</thinking>\n\nHello world")

    async def test_hermes_runs_payload_uses_input_and_conversation_history(self):
        self.enable_hermes(api_mode=main.HERMES_API_MODE_RUNS)
        self.configure_chat(stream=False, system_prompt="Run system prompt.")
        chat = main.db.create_chat("Existing")
        main.db.add_message(chat.id, "user", "previous question")
        main.db.add_message(chat.id, "assistant", "previous answer")
        fake_session = self.patch_session(FakeHermesSession(
            post_responses=[FakeHermesResponse(json_data={"run_id": "run-history"})],
            get_response=FakeHermesResponse(stream_chunks=[
                b'data: {"delta":"done"}\n\n',
                b'event: run.completed\ndata: {}\n\n',
            ]),
        ))

        result = await main.hermes_chat(JsonRequest({
            "chat_id": chat.id,
            "message": "next run",
        }))
        status, data = self.decode_result(result)

        self.assertEqual(status, 200)
        self.assertEqual(data["content"], "done")
        run_payload = fake_session.posts[0]["json"]
        self.assertEqual(run_payload["input"], "next run")
        self.assertEqual(run_payload["instructions"], "Run system prompt.")
        self.assertEqual(run_payload["conversation_history"], [
            {"role": "user", "content": "previous question"},
            {"role": "assistant", "content": "previous answer"},
        ])
        self.assertNotIn("messages", run_payload)
        self.assertNotIn("stream", run_payload)

    async def test_hermes_runs_non_stream_aggregates_events_and_saves(self):
        self.enable_hermes(api_mode=main.HERMES_API_MODE_RUNS)
        self.configure_chat(stream=False)
        event_chunks = [
            b'data: {"delta":{"content":"Final "}}\n\n',
            b'data: {"delta":{"thinking":"Reason"}}\n\n',
            b'data: {"output_text":"answer"}\n\n',
            b'event: run.succeeded\ndata: {}\n\n',
        ]
        fake_session = self.patch_session(FakeHermesSession(
            post_responses=[FakeHermesResponse(json_data={"id": "run-2"})],
            get_response=FakeHermesResponse(stream_chunks=event_chunks),
        ))

        result = await main.hermes_chat(JsonRequest({"message": "non stream run", "use_thinking": True}))
        status, data = self.decode_result(result)

        self.assertEqual(status, 200)
        self.assertEqual(data["content"], "Final answer")
        self.assertEqual(data["thinking"], "Reason")
        self.assertEqual(data["references"], [])
        self.assertEqual(fake_session.posts[0]["url"], "http://127.0.0.1:8642/v1/runs")
        self.assertEqual(fake_session.gets[0]["url"], "http://127.0.0.1:8642/v1/runs/run-2/events")
        messages = main.db.get_messages(data["chat_id"])
        self.assertEqual(messages[1].content, "<thinking>\nReason\n</thinking>\n\nFinal answer")

    async def test_hermes_runs_approval_returns_clear_error_without_final_content(self):
        self.enable_hermes(api_mode=main.HERMES_API_MODE_RUNS)
        self.configure_chat(stream=True)
        fake_session = self.patch_session(FakeHermesSession(
            post_responses=[
                FakeHermesResponse(json_data={"run_id": "run-approval"}),
                FakeHermesResponse(json_data={"stopped": True}),
            ],
            get_response=FakeHermesResponse(stream_chunks=[b'event: run.requires_action\ndata: {}\n\n']),
        ))

        response = await main.hermes_chat(JsonRequest({"message": "needs approval"}))
        stream_chunks = await self.collect_stream(response)
        chat_id = json.loads(stream_chunks[0])["chat_id"]

        self.assertTrue(any("requires approval" in chunk for chunk in stream_chunks))
        self.assertEqual(len(main.db.get_messages(chat_id)), 1)
        self.assertEqual(fake_session.posts[1]["url"], "http://127.0.0.1:8642/v1/runs/run-approval/stop")

    async def test_hermes_runs_events_error_stops_run(self):
        self.enable_hermes(api_mode=main.HERMES_API_MODE_RUNS)
        self.configure_chat(stream=False)
        fake_session = self.patch_session(FakeHermesSession(
            post_responses=[
                FakeHermesResponse(json_data={"run_id": "run-error"}),
                FakeHermesResponse(json_data={"stopped": True}),
            ],
            get_response=FakeHermesResponse(status=503, text_data="events down"),
        ))

        result = await main.hermes_chat(JsonRequest({"message": "events fail"}))
        status, data = self.decode_result(result)

        self.assertEqual(status, 502)
        self.assertIn("Hermes API error (503)", data["error"])
        self.assertEqual(fake_session.posts[1]["url"], "http://127.0.0.1:8642/v1/runs/run-error/stop")
        self.assertEqual(self.chat_count(), 1)

    async def test_hermes_runs_disconnect_stops_run_without_done(self):
        self.enable_hermes(api_mode=main.HERMES_API_MODE_RUNS)
        self.configure_chat(stream=True)
        fake_session = self.patch_session(FakeHermesSession(
            post_responses=[
                FakeHermesResponse(json_data={"run_id": "run-stop"}),
                FakeHermesResponse(json_data={"stopped": True}),
            ],
            get_response=FakeHermesResponse(stream_chunks=[b'data: {"delta":{"content":"late"}}\n\n']),
        ))

        response = await main.hermes_chat(JsonRequest({"message": "stop me"}, disconnected=True))
        stream_chunks = await self.collect_stream(response)

        self.assertIn('"chat_id"', stream_chunks[0])
        self.assertFalse(any('"done": true' in chunk for chunk in stream_chunks))
        chat_id = json.loads(stream_chunks[0])["chat_id"]
        self.assertEqual(fake_session.posts[0]["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(fake_session.gets[0]["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(fake_session.posts[1]["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(fake_session.posts[0]["headers"]["X-Hermes-Session-Id"], f"chatraw-{chat_id}")
        self.assertEqual(fake_session.gets[0]["headers"]["X-Hermes-Session-Id"], f"chatraw-{chat_id}")
        self.assertEqual(fake_session.posts[1]["headers"]["X-Hermes-Session-Id"], f"chatraw-{chat_id}")
        self.assertEqual(fake_session.posts[1]["url"], "http://127.0.0.1:8642/v1/runs/run-stop/stop")

    async def test_hermes_runs_without_api_key_omits_authorization_on_stop_path(self):
        self.enable_hermes(api_key="", api_mode=main.HERMES_API_MODE_RUNS)
        self.configure_chat(stream=True)
        fake_session = self.patch_session(FakeHermesSession(
            post_responses=[
                FakeHermesResponse(json_data={"run_id": "run-no-key"}),
                FakeHermesResponse(json_data={"stopped": True}),
            ],
            get_response=FakeHermesResponse(stream_chunks=[b'data: {"delta":{"content":"late"}}\n\n']),
        ))

        response = await main.hermes_chat(JsonRequest({"message": "stop me"}, disconnected=True))
        stream_chunks = await self.collect_stream(response)

        self.assertIn('"chat_id"', stream_chunks[0])
        self.assertNotIn("Authorization", fake_session.posts[0]["headers"])
        self.assertNotIn("Authorization", fake_session.gets[0]["headers"])
        self.assertNotIn("Authorization", fake_session.posts[1]["headers"])
        self.assertEqual(fake_session.posts[0]["url"], "http://127.0.0.1:8642/v1/runs")
        self.assertEqual(fake_session.gets[0]["url"], "http://127.0.0.1:8642/v1/runs/run-no-key/events")
        self.assertEqual(fake_session.posts[1]["url"], "http://127.0.0.1:8642/v1/runs/run-no-key/stop")

    async def test_hermes_rejects_runs_transport_fields_before_side_effects(self):
        self.enable_hermes(api_key="")
        called = False

        async def fail_if_called():
            nonlocal called
            called = True
            return FakeHermesSession()

        original = main.get_http_session
        main.get_http_session = fail_if_called
        self.addCleanup(lambda: setattr(main, "get_http_session", original))

        result = await main.hermes_chat(JsonRequest({
            "message": "hi",
            "api_mode": "runs",
            "run-id": "run-1",
            "eventsUrl": "http://evil.test/events",
            "stop_url": "http://evil.test/stop",
        }))
        status, data = self.decode_result(result)

        self.assertEqual(status, 400)
        self.assertIn("transport fields", data["error"])
        self.assertFalse(called)
        self.assertEqual(self.chat_count(), 0)

    async def test_hermes_rejects_non_object_body_before_side_effects(self):
        self.enable_hermes(api_key="")
        called = False

        async def fail_if_called():
            nonlocal called
            called = True
            return FakeHermesSession()

        original = main.get_http_session
        main.get_http_session = fail_if_called
        self.addCleanup(lambda: setattr(main, "get_http_session", original))

        result = await main.hermes_chat(JsonRequest(["not", "an", "object"]))
        status, data = self.decode_result(result)

        self.assertEqual(status, 400)
        self.assertIn("JSON object", data["error"])
        self.assertFalse(called)
        self.assertEqual(self.chat_count(), 0)

    async def test_hermes_runs_eof_without_terminal_stops_without_saving_assistant(self):
        self.enable_hermes(api_mode=main.HERMES_API_MODE_RUNS)
        self.configure_chat(stream=True)
        fake_session = self.patch_session(FakeHermesSession(
            post_responses=[
                FakeHermesResponse(json_data={"run_id": "run-eof"}),
                FakeHermesResponse(json_data={"stopped": True}),
            ],
            get_response=FakeHermesResponse(stream_chunks=[
                b'data: {"delta":{"content":"partial"}}\n\n',
            ]),
        ))

        response = await main.hermes_chat(JsonRequest({"message": "unexpected eof"}))
        stream_chunks = await self.collect_stream(response)
        chat_id = json.loads(stream_chunks[0])["chat_id"]

        self.assertTrue(any('"content": "partial"' in chunk for chunk in stream_chunks))
        self.assertTrue(any("ended before completion" in chunk for chunk in stream_chunks))
        self.assertFalse(any('"done": true' in chunk for chunk in stream_chunks))
        self.assertEqual(fake_session.posts[1]["url"], "http://127.0.0.1:8642/v1/runs/run-eof/stop")
        self.assertEqual(len(main.db.get_messages(chat_id)), 1)

    async def test_stale_chat_id_creates_new_chat_without_orphan_messages(self):
        self.enable_hermes()
        self.configure_chat(stream=False)
        fake_session = self.patch_session(FakeHermesSession(post_response=FakeHermesResponse(
            json_data={"choices": [{"message": {"content": "new answer"}}]}
        )))
        old_chat = main.db.create_chat("Old")
        main.db.delete_chat(old_chat.id)

        result = await main.hermes_chat(JsonRequest({"chat_id": old_chat.id, "message": "after delete"}))
        status, data = self.decode_result(result)

        self.assertEqual(status, 200)
        self.assertNotEqual(data["chat_id"], old_chat.id)
        self.assertEqual(fake_session.posts[0]["headers"]["X-Hermes-Session-Id"], f"chatraw-{data['chat_id']}")
        self.assertNotEqual(fake_session.posts[0]["headers"]["X-Hermes-Session-Id"], f"chatraw-{old_chat.id}")
        self.assertEqual(main.db.get_messages(old_chat.id), [])
        self.assertEqual(len(main.db.get_messages(data["chat_id"])), 2)

    async def test_hermes_errors_are_readable(self):
        self.enable_hermes()
        self.configure_chat(stream=False)
        self.patch_session(FakeHermesSession(post_response=FakeHermesResponse(
            status=401,
            text_data="bad key",
        )))

        result = await main.hermes_chat(JsonRequest({"message": "hi"}))
        status, data = self.decode_result(result)
        self.assertEqual(status, 401)
        self.assertIn("Hermes API error (401)", data["error"])

    async def test_hermes_5xx_network_and_timeout_errors_are_readable(self):
        self.enable_hermes()
        self.configure_chat(stream=False)

        self.patch_session(FakeHermesSession(post_response=FakeHermesResponse(
            status=503,
            text_data="busy",
        )))
        result = await main.hermes_chat(JsonRequest({"message": "hi"}))
        status, data = self.decode_result(result)
        self.assertEqual(status, 502)
        self.assertIn("Hermes API error (503)", data["error"])

        original = main.get_http_session

        async def network_session():
            return FailingSession(main.aiohttp.ClientError("connection refused"))

        main.get_http_session = network_session
        result = await main.hermes_chat(JsonRequest({"message": "hi"}))
        status, data = self.decode_result(result)
        self.assertEqual(status, 502)
        self.assertIn("Hermes network error", data["error"])

        async def timeout_session():
            return FailingSession(asyncio.TimeoutError())

        main.get_http_session = timeout_session
        result = await main.hermes_chat(JsonRequest({"message": "hi"}))
        status, data = self.decode_result(result)
        self.assertEqual(status, 504)
        self.assertIn("timeout", data["error"])

        main.get_http_session = original

    async def test_hermes_redirect_is_blocked(self):
        self.enable_hermes()
        health_session = self.patch_session(FakeHermesSession(get_response=FakeHermesResponse(
            status=302,
            text_data="redirect",
        )))

        result = await main.hermes_health(JsonRequest(url="http://testserver/api/hermes/health"))
        status, data = self.decode_result(result)

        self.assertEqual(status, 400)
        self.assertIn("redirect blocked", data["error"])
        self.assertFalse(health_session.gets[0]["allow_redirects"])

        self.enable_hermes()
        self.configure_chat(stream=False)
        chat_session = self.patch_session(FakeHermesSession(post_response=FakeHermesResponse(
            status=302,
            text_data="redirect",
        )))

        result = await main.hermes_chat(JsonRequest({"message": "chat redirect"}))
        status, data = self.decode_result(result)

        self.assertEqual(status, 400)
        self.assertIn("redirect blocked", data["error"])
        self.assertEqual(chat_session.posts[0]["url"], "http://127.0.0.1:8642/v1/chat/completions")
        self.assertFalse(chat_session.posts[0]["allow_redirects"])
        self.assertEqual(len(chat_session.posts), 1)

        self.enable_hermes(api_mode=main.HERMES_API_MODE_RUNS)
        runs_create_session = self.patch_session(FakeHermesSession(post_responses=[
            FakeHermesResponse(status=302, text_data="redirect"),
        ]))

        result = await main.hermes_chat(JsonRequest({"message": "run create redirect"}))
        status, data = self.decode_result(result)

        self.assertEqual(status, 400)
        self.assertIn("redirect blocked", data["error"])
        self.assertEqual(runs_create_session.posts[0]["url"], "http://127.0.0.1:8642/v1/runs")
        self.assertFalse(runs_create_session.posts[0]["allow_redirects"])
        self.assertEqual(len(runs_create_session.posts), 1)
        self.assertEqual(runs_create_session.gets, [])

        self.enable_hermes(api_mode=main.HERMES_API_MODE_RUNS)
        runs_events_session = self.patch_session(FakeHermesSession(
            post_responses=[
                FakeHermesResponse(json_data={"run_id": "run-redirect"}),
                FakeHermesResponse(json_data={"stopped": True}),
            ],
            get_response=FakeHermesResponse(status=302, text_data="redirect"),
        ))

        result = await main.hermes_chat(JsonRequest({"message": "run events redirect"}))
        status, data = self.decode_result(result)

        self.assertEqual(status, 400)
        self.assertIn("redirect blocked", data["error"])
        self.assertEqual(runs_events_session.posts[0]["url"], "http://127.0.0.1:8642/v1/runs")
        self.assertEqual(runs_events_session.gets[0]["url"], "http://127.0.0.1:8642/v1/runs/run-redirect/events")
        self.assertFalse(runs_events_session.gets[0]["allow_redirects"])
        self.assertEqual(runs_events_session.posts[1]["url"], "http://127.0.0.1:8642/v1/runs/run-redirect/stop")
        self.assertFalse(runs_events_session.posts[1]["allow_redirects"])

    async def test_proxy_still_rejects_localhost_and_private_networks(self):
        rejected_urls = [
            "http://localhost:8642/v1/models",
            "http://127.0.0.1:8642/v1/models",
            "http://[::1]:8642/v1/models",
            "http://0.0.0.0:8642/v1/models",
            "http://10.0.0.2:8642/v1/models",
            "http://172.16.0.5:8642/v1/models",
            "http://192.168.1.10:8642/v1/models",
        ]
        for url in rejected_urls:
            with self.subTest(url=url):
                result = await main.proxy_request(main.ProxyRequest(
                    service_id="hermes",
                    url=url,
                ))
                status, data = self.decode_result(result)
                self.assertEqual(status, 400)
                self.assertFalse(data["success"])
                self.assertIn("internal networks", data["error"])

    async def test_hermes_routes_are_not_rate_limit_exempt(self):
        middleware = main.RateLimitMiddleware(lambda scope, receive, send: None, requests_per_window=1, window_seconds=60)

        async def call_next(_request):
            return main.JSONResponse({"ok": True})

        first = await middleware.dispatch(FakeRateRequest("/api/hermes/chat"), call_next)
        second = await middleware.dispatch(FakeRateRequest("/api/hermes/chat"), call_next)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)

        middleware = main.RateLimitMiddleware(lambda scope, receive, send: None, requests_per_window=1, window_seconds=60)
        first = await middleware.dispatch(FakeRateRequest("/api/hermes/health"), call_next)
        second = await middleware.dispatch(FakeRateRequest("/api/hermes/health"), call_next)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)


if __name__ == "__main__":
    unittest.main()
