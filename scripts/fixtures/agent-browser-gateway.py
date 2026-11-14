import asyncio
import os
import secrets
import socket
from pathlib import Path

import uvicorn
from aiohttp import web
from agent_runner.runtime import Runtime
from agent_runner.server import create_app
from agent_runner.tests.test_runtime import ControlledAdapter


class BrowserFixture(ControlledAdapter):
    async def probe(self, config):
        result = await super().probe(config)
        result["version"] = "controlled-adapter"
        result["capabilities"]["approvals"] = True
        return result

    async def respond(self, binding, interaction_key, reply):
        await super().respond(binding, interaction_key, reply)
        self.finish.set()


async def main():
    state = Path(os.environ["CHATRAW_GATEWAY_TEST_STATE"]).resolve()
    token = secrets.token_urlsafe(48)
    token_path = state / "runner-token"
    token_path.write_text(token)
    token_path.chmod(0o600)
    os.environ["CHATRAW_RUNNER_TOKEN_FILE"] = str(token_path)
    os.environ["DATA_DIR"] = str(state / "data")
    runtime = Runtime(state / "runner", {"hermes": BrowserFixture})
    runner = web.AppRunner(create_app(runtime, token), handler_cancellation=True)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    runner_port = site._server.sockets[0].getsockname()[1]
    os.environ["CHATRAW_RUNNER_URL"] = f"http://127.0.0.1:{runner_port}"
    from backend.main import app

    try:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            print(f"PORT {listener.getsockname()[1]}", flush=True)
            server = uvicorn.Server(uvicorn.Config(app, access_log=False))
            await server.serve(sockets=[listener])
    finally:
        await runner.cleanup()


asyncio.run(main())
