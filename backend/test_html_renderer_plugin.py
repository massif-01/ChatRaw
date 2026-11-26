"""Behavioral tests for the HTML Renderer's local macOS helper."""

import importlib.util
import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit

PLUGIN = Path(__file__).resolve().parents[1] / "Plugins/Plugin_market/html-renderer"
SPEC = importlib.util.spec_from_file_location(
    "html_renderer_bridge", PLUGIN / "bridge.py"
)
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


class OriginValidationTest(unittest.TestCase):
    def test_accepts_only_same_user_chatraw_listener(self):
        uid = str(os.getuid())
        suffix = "/Contents/Resources/ChatRawBackend/ChatRawBackend"
        cases = {
            "4111": ("21", "/Applications/ChatRaw.app", uid),
            "4222": ("22", "/Applications/ChatRaw v2.3.app", uid),
            "4333": ("23", "/Applications/Unrelated.app", str(os.getuid() + 1)),
            "4444": ("24", "/Applications/NotChatRaw.app", uid),
        }

        def fake_run(args, **_kwargs):
            if args[0] == "/usr/sbin/lsof":
                port = args[2].rsplit(":", 1)[-1]
                return SimpleNamespace(stdout=port + "\n" if port in cases else "")
            pid = args[2]
            if pid in cases:
                parent, app, owner = cases[pid]
                return SimpleNamespace(stdout=f"{owner} {parent} {app}{suffix}\n")
            for key, (parent, app, owner) in cases.items():
                if parent == pid:
                    executable = "OtherApp" if key == "4444" else "ChatRawMac"
                    return SimpleNamespace(
                        stdout=f"{owner} {app}/Contents/MacOS/{executable}\n"
                    )
            return SimpleNamespace(stdout="")

        with patch.object(bridge.subprocess, "run", side_effect=fake_run):
            self.assertTrue(bridge.trusted_origin("http://127.0.0.1:4111"))
            self.assertTrue(bridge.trusted_origin("http://127.0.0.1:4222"))
            self.assertFalse(bridge.trusted_origin("http://127.0.0.1:4333"))
            self.assertFalse(bridge.trusted_origin("http://127.0.0.1:4444"))
            self.assertFalse(bridge.trusted_origin("http://127.0.0.1:4555"))
            self.assertFalse(bridge.trusted_origin("https://127.0.0.1:4111"))
            self.assertFalse(bridge.trusted_origin("http://127.0.0.1:4111/path"))
            self.assertFalse(bridge.trusted_origin(None))


class HelperHttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = bridge.PreviewServer(("127.0.0.1", 0))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path, method="GET", data=None, origin=None, headers=None):
        request_headers = dict(headers or {})
        if origin is not None:
            request_headers["Origin"] = origin
        req = urllib.request.Request(
            self.url + path, method=method, data=data, headers=request_headers
        )
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            response = opener.open(req, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return SimpleNamespace(
                status=response.status, headers=response.headers, body=response.read()
            )

    def test_preflight_requires_enabled_plugin_and_trusted_origin(self):
        trusted = "http://127.0.0.1:4111"
        headers = {"Access-Control-Request-Method": "POST"}
        with patch.object(bridge, "plugin_enabled", return_value=True), patch.object(
            bridge, "trusted_origin", side_effect=lambda origin: origin == trusted
        ):
            self.assertEqual(
                self.request(
                    "/open", "OPTIONS", origin=trusted, headers=headers
                ).status,
                204,
            )
            self.assertEqual(
                self.request(
                    "/open", "OPTIONS", origin="https://example.org", headers=headers
                ).status,
                403,
            )
            self.assertEqual(
                self.request("/open", "OPTIONS", headers=headers).status, 403
            )
        with patch.object(bridge, "plugin_enabled", return_value=False):
            self.assertEqual(
                self.request(
                    "/open", "OPTIONS", origin=trusted, headers=headers
                ).status,
                403,
            )

    def test_opened_preview_is_escaped_sandboxed_and_expires(self):
        origin = "http://127.0.0.1:4111"
        html = '<h1>中文</h1><script>window.test = "</script><script>bad()</script>"</script>'
        body = json.dumps({"html": html}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        with patch.object(bridge, "plugin_enabled", return_value=True), patch.object(
            bridge, "trusted_origin", return_value=True
        ), patch.object(bridge.subprocess, "run") as open_browser:
            response = self.request("/open", "POST", body, origin, headers)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], origin)
        url = open_browser.call_args.args[0][1]
        path = urlsplit(url).path
        preview = self.request(path)
        text = preview.body.decode("utf-8")
        self.assertEqual(preview.status, 200)
        self.assertIn("frame-src about:", preview.headers["Content-Security-Policy"])
        self.assertIn("connect-src 'none'", preview.headers["Content-Security-Policy"])
        self.assertIn('sandbox="allow-scripts allow-forms allow-pointer-lock"', text)
        self.assertEqual(text.count("<script>"), 1)
        self.assertIn(r"\u003c/script", text)
        token = path.rsplit("/", 1)[1]
        with self.server.lock:
            self.server.previews[token] = (0, html)
        self.assertEqual(self.request(path).status, 404)

    def test_rejects_oversized_request(self):
        headers = {
            "Content-Type": "application/json",
            "Content-Length": str(bridge.MAX_HTML_BYTES + 1),
        }
        with patch.object(bridge, "plugin_enabled", return_value=True), patch.object(
            bridge, "trusted_origin", return_value=True
        ), patch.object(bridge.subprocess, "run") as open_browser:
            response = self.request(
                "/open", "POST", b"{}", "http://127.0.0.1:4111", headers
            )
        self.assertEqual(response.status, 413)
        open_browser.assert_not_called()


if __name__ == "__main__":
    unittest.main()
