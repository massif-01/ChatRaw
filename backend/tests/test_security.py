import os
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import unittest
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

        os.environ["CHATRAW_AUTH_TOKEN"] = "test-token"
        self.db = main.Database(os.path.join(self.tmpdir, "chatraw.db"))
        main.db = self.db
        main.llm_service = main.LLMService(main.db)
        main.rag_service = main.RAGService(main.db, main.llm_service)
        self.client = TestClient(main.app)

    def tearDown(self):
        try:
            self.db.get_conn().close()
        finally:
            main.BACKEND_DIR = self.old_backend_dir
            main.db = self.old_db
            main.llm_service = self.old_llm_service
            main.rag_service = self.old_rag_service
            if self.old_auth_token is None:
                os.environ.pop("CHATRAW_AUTH_TOKEN", None)
            else:
                os.environ["CHATRAW_AUTH_TOKEN"] = self.old_auth_token
            shutil.rmtree(self.tmpdir, ignore_errors=True)

    def auth_headers(self):
        return {"Authorization": "Bearer test-token"}

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

    def test_models_require_auth_when_token_is_configured(self):
        unauthenticated = self.client.get("/api/models")
        self.assertEqual(unauthenticated.status_code, 401)

        authenticated = self.client.get("/api/models", headers=self.auth_headers())
        self.assertEqual(authenticated.status_code, 200)

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

    def test_model_verify_uses_existing_secret_when_key_is_omitted(self):
        self.save_secret_model()

        class FakeResponse:
            status = 200

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def text(self):
                return ""

        class FakeSession:
            def __init__(self):
                self.headers = None
                self.url = None

            def post(self, url, json, headers):
                self.url = url
                self.headers = headers
                return FakeResponse()

        fake_session = FakeSession()

        async def get_fake_session():
            return fake_session

        with patch.object(main, "get_http_session", get_fake_session):
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
                        "api_url": "http://127.0.0.1:11434/v1",
                        "model_id": "chat-model",
                        "type": "chat",
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(
            fake_session.url,
            "http://127.0.0.1:11434/v1/chat/completions",
        )
        self.assertEqual(fake_session.headers["Authorization"], "Bearer sk-secret")

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

    def test_parse_url_rejects_internal_targets_without_network(self):
        async def fail_if_called():
            raise AssertionError("get_http_session should not be called")

        blocked_urls = [
            "http://127.0.0.1:51111",
            "http://localhost:51111",
            "http://169.254.169.254/latest/meta-data",
            "http://192.168.1.1",
        ]
        with patch.object(main, "get_http_session", fail_if_called):
            for url in blocked_urls:
                with self.subTest(url=url):
                    response = self.client.post("/api/parse-url", json={"url": url})
                    self.assertEqual(response.status_code, 400)

    def test_parse_url_blocks_private_ip_at_connection_resolution(self):
        async def fail_if_called():
            raise AssertionError("get_http_session should not be called")

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

        with patch.object(main, "get_http_session", fail_if_called):
            with patch.object(
                main.aiohttp, "DefaultResolver", lambda: PrivateResolver()
            ):
                response = self.client.post(
                    "/api/parse-url",
                    json={"url": "http://rebind.example"},
                )

        self.assertEqual(response.status_code, 400)
        self.assertIn("internal networks", response.text)

    def test_proxy_request_rejects_literal_internal_targets_without_network(self):
        async def fail_if_called():
            raise AssertionError("get_http_session should not be called")

        blocked_urls = [
            "http://127.0.0.1:51111",
            "http://localhost:51111",
            "http://169.254.169.254/latest/meta-data",
            "http://192.168.1.1",
            "http://[::1]/",
        ]
        with patch.object(main, "get_http_session", fail_if_called):
            for url in blocked_urls:
                with self.subTest(url=url):
                    response = self.client.post(
                        "/api/proxy/request",
                        json={"service_id": "test", "url": url},
                    )
                    self.assertEqual(response.status_code, 400)

    def test_proxy_request_blocks_private_ip_at_connection_resolution(self):
        async def fail_if_called():
            raise AssertionError("get_http_session should not be called")

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

        with patch.object(main, "get_http_session", fail_if_called):
            with patch.object(
                main.aiohttp, "DefaultResolver", lambda: PrivateResolver()
            ):
                response = self.client.post(
                    "/api/proxy/request",
                    json={"service_id": "test", "url": "http://rebind.example"},
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
