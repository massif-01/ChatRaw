import argparse
import asyncio
import contextlib
import json
from typing import Any, Dict, List, Optional

from aiohttp import web


def _input_text(payload: dict) -> str:
    value = payload.get("input", "")
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                content = item.get("content", "")
                if isinstance(content, str):
                    parts.append(content)
                elif isinstance(content, list):
                    parts.extend(str(part.get("text") or "") for part in content if isinstance(part, dict))
        return "\n".join(part for part in parts if part)
    return str(value or "")


async def _write_sse(resp: web.StreamResponse, event: str, data: dict):
    await resp.write(f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8"))


class FakeHermesServer:
    """Hermes API Server test double for local smoke tests.

    This app is intentionally not mounted by ChatRaw and is not a production
    Hermes replacement. It only models the narrow HTTP/SSE and approval paths
    needed by backend smoke tests and manual UI validation.
    """

    def __init__(self):
        self.runs: Dict[str, dict] = {}
        self.model_requests: List[dict] = []
        self.chat_requests: List[dict] = []
        self.run_requests: List[dict] = []
        self.event_requests: List[dict] = []
        self.approval_requests: List[dict] = []
        self.stop_requests: List[dict] = []
        self.session_allowed: set[str] = set()
        self._counter = 0

    def create_app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/v1/models", self.handle_models)
        app.router.add_post("/v1/chat/completions", self.handle_chat_completions)
        app.router.add_post("/v1/runs", self.handle_create_run)
        app.router.add_get("/v1/runs/{run_id}/events", self.handle_run_events)
        app.router.add_post("/v1/runs/{run_id}/approval", self.handle_run_approval)
        app.router.add_post("/v1/runs/{run_id}/stop", self.handle_run_stop)
        return app

    def latest_run_id(self) -> Optional[str]:
        if not self.run_requests:
            return None
        return self.run_requests[-1]["run_id"]

    async def _json_body(self, request: web.Request) -> dict:
        try:
            data = await request.json()
        except Exception:
            data = {}
        return data if isinstance(data, dict) else {}

    def _headers(self, request: web.Request) -> dict:
        return {key: value for key, value in request.headers.items()}

    def _scenario_for_payload(self, payload: dict, headers: dict) -> str:
        text = _input_text(payload).lower()
        session_id = headers.get("X-Hermes-Session-Id", "")
        if "session followup" in text:
            return "session_followup_allowed" if session_id in self.session_allowed else "session_followup_blocked"
        if "session" in text:
            return "approval_session"
        if "deny" in text:
            return "approval_deny"
        if "once" in text:
            return "approval_once"
        if "non stream" in text or "non-stream" in text:
            return "approval_once"
        if "snapshot" in text:
            return "snapshot_final"
        if "quiet stop" in text:
            return "quiet_stop"
        if "stopped" in text:
            return "stopped"
        if "stop" in text or "abort" in text:
            return "stop"
        if "eof" in text:
            return "eof"
        return "complete"

    async def handle_models(self, request: web.Request) -> web.Response:
        self.model_requests.append({"headers": self._headers(request)})
        return web.json_response({"data": [{"id": "hermes-agent", "object": "model"}]})

    async def handle_chat_completions(self, request: web.Request) -> web.Response:
        payload = await self._json_body(request)
        self.chat_requests.append({"headers": self._headers(request), "json": payload})
        return web.json_response({"choices": [{"message": {"content": "fake chat completion"}}]})

    async def handle_create_run(self, request: web.Request) -> web.Response:
        payload = await self._json_body(request)
        headers = self._headers(request)
        self._counter += 1
        scenario = self._scenario_for_payload(payload, headers)
        run_id = f"fake-run-{self._counter}-{scenario}"
        run = {
            "run_id": run_id,
            "scenario": scenario,
            "payload": payload,
            "headers": headers,
            "approval_event": asyncio.Event(),
            "stop_event": asyncio.Event(),
            "approval_choice": "",
            "approval_body": None,
            "stopped": False,
        }
        self.runs[run_id] = run
        self.run_requests.append({
            "run_id": run_id,
            "scenario": scenario,
            "headers": headers,
            "json": payload,
        })
        return web.json_response({"id": run_id, "status": "running"})

    async def handle_run_events(self, request: web.Request) -> web.StreamResponse:
        run_id = request.match_info["run_id"]
        run = self.runs.get(run_id)
        self.event_requests.append({"run_id": run_id, "headers": self._headers(request)})
        if not run:
            return web.Response(status=404, text="run not found")

        resp = web.StreamResponse(
            status=200,
            headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache"},
        )
        await resp.prepare(request)
        scenario = run["scenario"]

        try:
            if scenario in {"approval_deny", "approval_once", "approval_session", "session_followup_blocked"}:
                await _write_sse(resp, "approval.request", {
                    "approval": {
                        "command": "dangerous command",
                        "description": "Fake Hermes needs explicit approval",
                        "pattern_keys": ["shell:dangerous-command"],
                    }
                })
                await self._wait_for_approval_or_stop(run)
                if run["stopped"]:
                    return resp
                choice = run["approval_choice"]
                await _write_sse(resp, "approval.responded", {"choice": choice, "resolved": True})
                if choice == "deny":
                    await _write_sse(resp, "run.failed", {
                        "error": {"message": "BLOCKED by fake Hermes approval deny"}
                    })
                    return resp
                await _write_sse(resp, "tool.completed", {
                    "tool": "shell",
                    "preview": "dangerous command",
                    "status": "completed",
                    "duration_ms": 0,
                })
                answer = "approved session answer" if choice == "session" else "approved once answer"
                await _write_sse(resp, "message.delta", {"delta": {"content": answer}})
                await _write_sse(resp, "run.completed", {"usage": {"output_tokens": 3}})
                return resp

            if scenario == "session_followup_allowed":
                await _write_sse(resp, "tool.completed", {
                    "tool": "shell",
                    "preview": "session reused command",
                    "status": "completed",
                    "duration_ms": 1,
                })
                await _write_sse(resp, "message.delta", {"delta": {"content": "session reused answer"}})
                await _write_sse(resp, "run.completed", {})
                return resp

            if scenario == "snapshot_final":
                await _write_sse(resp, "message.delta", {"delta": {"content": "Fake "}})
                await _write_sse(resp, "message", {"output_text": "Fake snapshot"})
                await _write_sse(resp, "run.completed", {"output_text": "Fake snapshot"})
                return resp

            if scenario == "stop":
                await _write_sse(resp, "message.delta", {"delta": {"content": "late after stop"}})
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(run["stop_event"].wait(), timeout=5)
                return resp

            if scenario == "quiet_stop":
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(run["stop_event"].wait(), timeout=5)
                return resp

            if scenario == "stopped":
                await _write_sse(resp, "run.stopped", {"status": "stopped"})
                return resp

            if scenario == "eof":
                await _write_sse(resp, "message.delta", {"delta": {"content": "partial before eof"}})
                return resp

            await _write_sse(resp, "tool.started", {"tool": "shell", "preview": "safe command"})
            await _write_sse(resp, "message.delta", {"delta": {"reasoning_content": "fake reasoning"}})
            await _write_sse(resp, "message.delta", {"delta": {"content": "fake run answer"}})
            await _write_sse(resp, "run.completed", {})
            return resp
        finally:
            with contextlib.suppress(ConnectionResetError, RuntimeError):
                await resp.write_eof()

    async def _wait_for_approval_or_stop(self, run: dict):
        approval_task = asyncio.create_task(run["approval_event"].wait())
        stop_task = asyncio.create_task(run["stop_event"].wait())
        try:
            done, pending = await asyncio.wait(
                {approval_task, stop_task},
                timeout=10,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                run["stopped"] = True
            elif stop_task in done:
                run["stopped"] = True
        finally:
            for task in (approval_task, stop_task):
                if not task.done():
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

    async def handle_run_approval(self, request: web.Request) -> web.Response:
        run_id = request.match_info["run_id"]
        run = self.runs.get(run_id)
        body = await self._json_body(request)
        record = {"run_id": run_id, "headers": self._headers(request), "json": body}
        self.approval_requests.append(record)
        if not run:
            return web.json_response({"error": "run not found"}, status=404)
        if run["approval_event"].is_set():
            return web.json_response({"error": "approval already resolved"}, status=409)

        choice = str(body.get("choice") or "").lower()
        run["approval_choice"] = choice
        run["approval_body"] = body
        if choice == "session":
            session_id = run["headers"].get("X-Hermes-Session-Id", "")
            if session_id:
                self.session_allowed.add(session_id)
        run["approval_event"].set()
        status = "blocked" if choice == "deny" else "running"
        return web.json_response({"success": True, "status": status})

    async def handle_run_stop(self, request: web.Request) -> web.Response:
        run_id = request.match_info["run_id"]
        run = self.runs.get(run_id)
        self.stop_requests.append({"run_id": run_id, "headers": self._headers(request)})
        if run:
            run["stopped"] = True
            run["stop_event"].set()
        return web.json_response({"success": True, "status": "stopped"})


async def run_fake_hermes_server(host: str, port: int):
    fake = FakeHermesServer()
    runner = web.AppRunner(fake.create_app())
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    sockets = getattr(site, "_server", None).sockets if getattr(site, "_server", None) else []
    bound_port = sockets[0].getsockname()[1] if sockets else port
    print(f"Fake Hermes API Server listening at http://{host}:{bound_port}/v1", flush=True)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


def main():
    parser = argparse.ArgumentParser(description="Run the ChatRaw fake Hermes API Server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8642)
    args = parser.parse_args()
    asyncio.run(run_fake_hermes_server(args.host, args.port))


if __name__ == "__main__":
    main()
