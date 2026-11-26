#!/usr/bin/env python3
"""Local browser launcher for the ChatRaw macOS WebView."""

import argparse
import json
import os
import secrets
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

PLUGIN_ID = "html-renderer"
MAX_HTML_BYTES = 8 * 1024 * 1024
MAX_PREVIEWS = 8
PREVIEW_LIFETIME = 30 * 60
DEFAULT_PORT = 38479
CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config.json"
DOCUMENT_PREFIX = (
    '<!doctype html><meta http-equiv="Content-Security-Policy" '
    'content="connect-src &#39;none&#39;; form-action &#39;none&#39;; '
    'object-src &#39;none&#39;; base-uri &#39;none&#39;">'
)


def trusted_origin(origin):
    try:
        url = urlsplit(origin or "")
        if url.scheme != "http" or url.hostname != "127.0.0.1" or not url.port:
            return False
        if origin != f"http://127.0.0.1:{url.port}":
            return False
        listeners = subprocess.run(
            [
                "/usr/sbin/lsof",
                "-nP",
                f"-iTCP@127.0.0.1:{url.port}",
                "-sTCP:LISTEN",
                "-t",
            ],
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.splitlines()
        suffix = "/Contents/Resources/ChatRawBackend/ChatRawBackend"
        for pid in listeners:
            if not pid.isdigit():
                continue
            backend = (
                subprocess.run(
                    ["/bin/ps", "-p", pid, "-o", "uid=,ppid=,comm="],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                .stdout.strip()
                .split(None, 2)
            )
            if (
                len(backend) != 3
                or backend[0] != str(os.getuid())
                or not backend[2].endswith(suffix)
            ):
                continue
            app_path = backend[2][: -len(suffix)]
            if not app_path.endswith(".app"):
                continue
            parent = (
                subprocess.run(
                    ["/bin/ps", "-p", backend[1], "-o", "uid=,comm="],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                .stdout.strip()
                .split(None, 1)
            )
            if parent == [str(os.getuid()), app_path + "/Contents/MacOS/ChatRawMac"]:
                return True
    except (OSError, ValueError, subprocess.SubprocessError):
        return False
    return False


def plugin_enabled():
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return config["plugins"][PLUGIN_ID]["enabled"] is True
    except (OSError, ValueError, KeyError, TypeError):
        return False


class PreviewServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address):
        super().__init__(address, Handler)
        self.previews = {}
        self.lock = threading.Lock()

    def store(self, html):
        now = time.monotonic()
        with self.lock:
            self.previews = {
                token: item
                for token, item in self.previews.items()
                if now - item[0] < PREVIEW_LIFETIME
            }
            if len(self.previews) >= MAX_PREVIEWS:
                oldest = min(self.previews, key=lambda token: self.previews[token][0])
                del self.previews[oldest]
            token = secrets.token_urlsafe(32)
            self.previews[token] = (now, html)
            return token

    def get_preview(self, token):
        with self.lock:
            item = self.previews.get(token)
            if not item or time.monotonic() - item[0] >= PREVIEW_LIFETIME:
                self.previews.pop(token, None)
                return None
            return item[1]


class Handler(BaseHTTPRequestHandler):
    server_version = "ChatRawHTMLRenderer"
    sys_version = ""

    def log_message(self, _format, *_args):
        pass

    def authorized(self):
        return plugin_enabled() and trusted_origin(self.headers.get("Origin"))

    def send_bytes(self, status, body, content_type, cors=False, preview=False):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        if preview:
            self.send_header(
                "Content-Security-Policy",
                "frame-src about:; connect-src 'none'; form-action 'none'; "
                "object-src 'none'; base-uri 'none'",
            )
        if cors:
            self.send_header("Access-Control-Allow-Origin", self.headers["Origin"])
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        if self.path != "/open" or not self.authorized():
            self.send_bytes(403, b"Forbidden", "text/plain")
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", self.headers["Origin"])
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Vary", "Origin")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        if self.path != "/open" or not self.authorized():
            self.send_bytes(403, b"Forbidden", "text/plain")
            return
        if self.headers.get_content_type() != "application/json":
            self.send_bytes(415, b"JSON required", "text/plain", cors=True)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_HTML_BYTES:
                self.send_bytes(413, b"HTML too large", "text/plain", cors=True)
                return
            payload = json.loads(self.rfile.read(length))
            html = payload["html"]
            if not isinstance(html, str) or not html.strip():
                raise ValueError("Empty HTML")
        except (ValueError, KeyError, TypeError):
            self.send_bytes(400, b"Invalid request", "text/plain", cors=True)
            return

        token = self.server.store(html)
        preview_url = f"http://127.0.0.1:{self.server.server_port}/preview/{token}"
        try:
            subprocess.run(["/usr/bin/open", preview_url], check=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            with self.server.lock:
                self.server.previews.pop(token, None)
            self.send_bytes(500, b"Could not open the browser", "text/plain", cors=True)
            return
        self.send_bytes(200, b'{"success":true}', "application/json", cors=True)

    def do_GET(self):
        if self.path == "/health":
            health = json.dumps(
                {"service": "chatraw-html-renderer", "pid": os.getpid()},
                separators=(",", ":"),
            ).encode("utf-8")
            self.send_bytes(200, health, "application/json")
            return
        prefix = "/preview/"
        token = self.path[len(prefix) :] if self.path.startswith(prefix) else ""
        html = self.server.get_preview(token) if token else None
        if html is None:
            self.send_bytes(404, b"Preview not found or expired", "text/plain")
            return
        data = json.dumps(DOCUMENT_PREFIX + html, ensure_ascii=True).replace(
            "<", "\\u003c"
        )
        page = (
            '<!doctype html><html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            "<title>HTML Preview</title><style>html,body{height:100%;margin:0;overflow:hidden}"
            "iframe{display:block;width:100%;height:100%;border:0}</style></head>"
            '<body><iframe id="preview" title="HTML Preview" '
            'sandbox="allow-scripts allow-forms allow-pointer-lock" referrerpolicy="no-referrer"></iframe>'
            '<script>const frame=document.getElementById("preview");'
            'frame.addEventListener("load",()=>frame.focus(),{once:true});'
            f"frame.srcdoc={data};</script></body></html>"
        ).encode("utf-8")
        self.send_bytes(200, page, "text/html; charset=utf-8", preview=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    if sys.platform != "darwin":
        raise SystemExit("The browser helper is for macOS.")
    server = PreviewServer(("127.0.0.1", args.port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
