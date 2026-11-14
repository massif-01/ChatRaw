"""python -m agent_runner --config /etc/chatraw-runner/config.json"""

import argparse
import json
import os
from pathlib import Path

from aiohttp import web

from .registry import factories
from .runtime import Runtime
from .server import create_app


def main():
    parser = argparse.ArgumentParser(description="ChatRaw host Agent runner")
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    host = config.get("host", "127.0.0.1")
    if host not in ("127.0.0.1", "::1"):
        parser.error(
            "Runner must listen on loopback; use the ChatRaw same-origin gateway"
        )
    token_file = os.environ.get("CHATRAW_RUNNER_TOKEN_FILE") or config.get("token_file")
    if not token_file:
        parser.error("Set CHATRAW_RUNNER_TOKEN_FILE or token_file")
    token = Path(token_file).read_text().strip()
    runtime = Runtime(config["data_dir"], factories(), config)
    app = create_app(runtime, token)
    web.run_app(
        app,
        host=host,
        port=config.get("port", 51112),
        handler_cancellation=True,
        access_log=None,
        shutdown_timeout=20,
    )


if __name__ == "__main__":
    main()
