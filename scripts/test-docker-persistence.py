"""Verify the built image offline and recreate it against the same named volume."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid


def docker(*args):
    return subprocess.check_output(["docker", *args], stderr=subprocess.PIPE)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="chatraw-agent-integration:local")
    parser.add_argument(
        "--report", default="outputs/agent-platform/docker-persistence.json"
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    suffix = uuid.uuid4().hex[:12]
    container = "chatraw-test-" + suffix
    volume = container + "-data"
    installed = {"hermes", "codex", "claude", "pi", "deepseek", "markdown-enhancer"}

    def request(path, body=None):
        code = """
import json, sys, urllib.request
url = 'http://127.0.0.1:51111' + sys.argv[1]
data = sys.argv[2].encode() if len(sys.argv) > 2 else None
req = urllib.request.Request(url, data=data, headers={
    'Content-Type': 'application/json', 'Origin': 'http://127.0.0.1:51111'})
with urllib.request.urlopen(req, timeout=5) as response:
    sys.stdout.buffer.write(response.read())
"""
        call = ["exec", container, "python", "-c", code, path]
        if body is not None:
            call.append(json.dumps(body))
        return docker(*call)

    def start():
        docker(
            "run",
            "-d",
            "--name",
            container,
            "--network",
            "none",
            "-v",
            volume + ":/app/data",
            args.image,
        )
        deadline = time.monotonic() + 30
        while True:
            try:
                request("/ready")
                return
            except subprocess.CalledProcessError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Container did not become ready") from None
                time.sleep(0.2)

    def remove():
        subprocess.run(
            ["docker", "rm", "-f", container],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    docker("volume", "create", volume)
    try:
        start()
        assert b"agents.js" in request("/")
        assets = ["app.min.js", "styles.min.css", "agents.js", "stream-markdown.js"]
        for asset in assets:
            assert (
                request("/" + asset) == (root / "backend/static" / asset).read_bytes()
            ), asset
        chat = json.loads(request("/api/chats", {}))
        for plugin_id in sorted(installed):
            result = json.loads(
                request("/api/plugins/install-bundled", {"plugin_id": plugin_id})
            )
            assert result["success"], result
        font_path = "markdown-enhancer/lib/fonts/KaTeX_Main-Regular.woff2"
        font = request("/api/plugins/" + font_path)
        assert font == (root / "Plugins/Plugin_market" / font_path).read_bytes()
        remove()
        start()
        chats = json.loads(request("/api/chats"))
        assert sum(row["id"] == chat["id"] for row in chats) == 1
        plugins = json.loads(request("/api/plugins"))
        assert installed <= {row["id"] for row in plugins}
        assert request("/api/plugins/" + font_path) == font
        agents = json.loads(request("/api/agents"))["agents"]
        assert len(agents) == 5 and all(row["installed"] for row in agents)
        assert all(row["availability"] != "ready" for row in agents)
        absent = json.loads(
            docker(
                "exec",
                container,
                "python",
                "-c",
                "import json,shutil; print(json.dumps({n:shutil.which(n) for n in ['hermes','codex','claude','pi','dsh']}))",
            )
        )
        assert not any(absent.values()), absent
        report = {
            "source_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip(),
            "image_id": docker("image", "inspect", "--format", "{{.Id}}", args.image)
            .decode()
            .strip(),
            "image_platform": docker(
                "image", "inspect", "--format", "{{.Os}}/{{.Architecture}}", args.image
            )
            .decode()
            .strip(),
            "network": "none",
            "runner": "not configured",
            "passed": [
                "ordinary startup without Runner",
                "built frontend bytes",
                "six complete local bundles",
                "nested font bytes",
                "chat and plugins survive container replacement",
                "native CLIs absent",
            ],
            "frontend_sha256": {
                asset: hashlib.sha256(
                    (root / "backend/static" / asset).read_bytes()
                ).hexdigest()
                for asset in assets
            },
            "boundary": "Local Docker image and named-volume replacement; not RM-01 or machine reboot.",
        }
        target = root / args.report
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(report, ensure_ascii=False))
    finally:
        remove()
        subprocess.run(
            ["docker", "volume", "rm", volume],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


if __name__ == "__main__":
    main()
