"""Same-origin gateway to the host Runner; no native Agent execution here."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import quote, urlparse
from uuid import uuid4

import aiohttp
from fastapi import APIRouter, HTTPException, Request
from fastapi.routing import APIRoute
from starlette.responses import JSONResponse, StreamingResponse

if __package__:
    from .agent_storage import AgentStorage
else:
    from agent_storage import AgentStorage


AGENTS = ("hermes", "codex", "claude", "pi", "deepseek")
TERMINAL = {"completed", "failed", "cancelled", "interrupted"}


class GatewayError(Exception):
    def __init__(self, code, message, status=400, retryable=False):
        self.code, self.message, self.status, self.retryable = (
            code,
            message,
            status,
            retryable,
        )

    def payload(self):
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "retryable": self.retryable,
            }
        }


def fields(body, required, optional=()):
    if (
        not isinstance(body, dict)
        or not set(required) <= body.keys()
        or body.keys() - set(required) - set(optional)
    ):
        raise GatewayError("invalid_request", "Unexpected or missing request fields")
    return body


def text(value, name, maximum=200, empty=False):
    if (
        not isinstance(value, str)
        or len(value) > maximum
        or (not empty and not value.strip())
    ):
        raise GatewayError("invalid_request", f"Invalid {name}")
    return value


class AgentRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def checked(request):
            try:
                return await handler(request)
            except GatewayError as error:
                return JSONResponse(error.payload(), status_code=error.status)
            except HTTPException as error:
                return JSONResponse(
                    GatewayError(
                        "request_rejected", str(error.detail), error.status_code
                    ).payload(),
                    status_code=error.status_code,
                )
            except (json.JSONDecodeError, UnicodeDecodeError):
                return JSONResponse(
                    GatewayError("invalid_json", "Invalid JSON request").payload(),
                    status_code=400,
                )
            except (aiohttp.ClientError, asyncio.TimeoutError):
                return JSONResponse(
                    GatewayError(
                        "runner_unavailable", "Runner connection is unavailable", 503
                    ).payload(),
                    status_code=503,
                )
            except Exception:
                return JSONResponse(
                    GatewayError(
                        "agent_internal_error",
                        "Agent request could not be completed; inspect the existing run before retrying",
                        500,
                    ).payload(),
                    status_code=500,
                )

        return checked


class RunnerClient:
    def __init__(self, base_url=None, token=None):
        self.base_url = (
            base_url or os.environ.get("CHATRAW_RUNNER_URL", "http://127.0.0.1:51112")
        ).rstrip("/")
        parsed = urlparse(self.base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in ("127.0.0.1", "::1", "localhost")
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path
        ):
            raise ValueError(
                "CHATRAW_RUNNER_URL must name the host loopback HTTP service"
            )
        self.token = token
        self.session = None

    def headers(self, chat_id=None):
        token = self.token
        if token is None:
            path = os.environ.get("CHATRAW_RUNNER_TOKEN_FILE")
            if not path:
                raise GatewayError(
                    "runner_unconfigured",
                    "Configure the host Runner connection first",
                    503,
                )
            try:
                token = Path(path).read_text().strip()
            except OSError:
                raise GatewayError(
                    "runner_unconfigured", "Runner credential file is unavailable", 503
                ) from None
        if len(token) < 32:
            raise GatewayError(
                "runner_unconfigured", "Runner credential is not configured", 503
            )
        headers = {"Authorization": "Bearer " + token}
        if chat_id is not None:
            headers["X-ChatRaw-Chat-Id"] = chat_id
        return headers

    async def http(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=20, connect=5)
            )
        return self.session

    async def request(
        self, method, path, *, chat_id=None, body=None, data=None, headers=None
    ):
        request_headers = {**self.headers(chat_id), **(headers or {})}
        try:
            session = await self.http()
            async with session.request(
                method,
                self.base_url + path,
                headers=request_headers,
                json=body,
                data=data,
                allow_redirects=False,
            ) as response:
                value = await response.json(content_type=None)
                if response.status >= 300:
                    error = value.get("error", {}) if isinstance(value, dict) else {}
                    # Runner is a trusted service, but never echo arbitrary HTML
                    # or transport diagnostics from a different localhost service.
                    if not isinstance(error, dict) or not isinstance(
                        error.get("message"), str
                    ):
                        raise GatewayError(
                            "runner_protocol",
                            "Runner returned an invalid response",
                            502,
                        )
                    raise GatewayError(
                        error.get("code", "runner_error"),
                        error["message"],
                        response.status,
                        bool(error.get("retryable", False)),
                    )
                return value
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            raise GatewayError(
                "runner_unavailable",
                "Runner connection failed; check the existing request before submitting again",
                503,
            ) from None

    async def close(self):
        if self.session is not None:
            await self.session.close()
            self.session = None


class AgentGateway:
    def __init__(self, main, client=None):
        self.main = main
        self.client = client or RunnerClient()
        self.locks = {}
        self.agent_locks = {}
        self.worker = None
        self.router = APIRouter(route_class=AgentRoute)
        self._routes()

    @property
    def storage(self):
        return AgentStorage(self.main.db)

    def lock(self, chat_id):
        return self.locks.setdefault(chat_id, asyncio.Lock())

    def origin(self, request):
        self.main.validate_agent_request_origin(request)

    def chat(self, chat_id):
        text(chat_id, "chat_id")
        if not self.main.db.chat_exists(chat_id):
            raise GatewayError("chat_not_found", "Chat not found", 404)

    def installed(self, agent_id):
        return (
            agent_id in AGENTS
            and (
                Path(self.main.PLUGINS_INSTALLED_DIR) / agent_id / "manifest.json"
            ).is_file()
        )

    def enabled(self, agent_id):
        config = self.main.load_plugin_config()
        return self.installed(agent_id) and bool(
            config.get("plugins", {}).get(agent_id, {}).get("enabled", False)
        )

    def require_enabled(self, agent_id):
        if not self.enabled(agent_id):
            raise GatewayError(
                "agent_disabled", "Install and enable this Agent plugin first", 403
            )

    def safe_settings(self, plugin_id, settings):
        if plugin_id not in AGENTS:
            return settings
        secret_names = {
            "apikey",
            "sessionkey",
            "token",
            "accesstoken",
            "refreshtoken",
            "password",
            "secret",
            "credentials",
            "authorization",
            "headers",
            "env",
            "environment",
            "auth",
            "baseurl",
        }

        def safe(value):
            if isinstance(value, dict):
                return {
                    key: safe(item)
                    for key, item in value.items()
                    if str(key).lower().replace("_", "").replace("-", "")
                    not in secret_names
                }
            if isinstance(value, list):
                return [safe(item) for item in value]
            return value

        return safe(settings)

    async def synchronize(self, agent_id, *, enabled=None, settings=None):
        body = {"enabled": self.enabled(agent_id) if enabled is None else enabled}
        if settings is not None:
            body["settings"] = settings
        return await self.client.request("PUT", f"/v1/agents/{agent_id}", body=body)

    def agent_lock(self, agent_id):
        return self.agent_locks.setdefault(agent_id, asyncio.Lock())

    async def prepare_agent(self, agent_id, include_settings=False):
        async with self.agent_lock(agent_id):
            self.require_enabled(agent_id)
            settings = None
            if include_settings:
                settings = (
                    self.main.load_plugin_config()
                    .get("plugins", {})
                    .get(agent_id, {})
                    .get("settings_values", {})
                )
            return await self.synchronize(agent_id, settings=settings)

    async def change_plugin(
        self, agent_id, *, enabled=None, settings=None, remove=False
    ):
        async with self.agent_lock(agent_id):
            config = self.main.load_plugin_config()
            plugin = config.setdefault("plugins", {}).setdefault(agent_id, {})
            target_enabled = (
                False
                if remove
                else plugin.get("enabled", False) if enabled is None else enabled
            )
            if not target_enabled:
                # A failed remote stop still closes the browser admission gate.
                plugin["enabled"] = False
                self.main.save_plugin_config(config)
            await self.synchronize(agent_id, enabled=target_enabled, settings=settings)
            # Other Agents may have committed settings while this request was
            # waiting on Runner. Merge only this Agent into the latest document.
            config = self.main.load_plugin_config()
            plugin = config.setdefault("plugins", {}).setdefault(agent_id, {})
            if settings is not None:
                plugin["settings_values"] = settings
            plugin["enabled"] = target_enabled
            if remove:
                import shutil

                shutil.rmtree(Path(self.main.PLUGINS_INSTALLED_DIR) / agent_id)
                del config["plugins"][agent_id]
            self.main.save_plugin_config(config)
            return {"success": True, "enabled": target_enabled}

    async def start(self):
        self.worker = asyncio.create_task(self.reconcile_forever())

    async def close(self):
        if self.worker is not None:
            self.worker.cancel()
            await asyncio.gather(self.worker, return_exceptions=True)
        # Closing ChatRaw drops no tasks at the host Runner.
        await self.client.close()

    async def reconcile_one(self, submission):
        if submission["run_id"]:
            snapshot = await self.client.request(
                "GET",
                f"/v1/runs/{quote(submission['run_id'], safe='')}",
                chat_id=submission["chat_id"],
            )
        else:
            result = await self.client.request(
                "GET",
                "/v1/runs?chat_id="
                + quote(submission["chat_id"], safe="")
                + "&client_request_id="
                + quote(submission["client_request_id"], safe=""),
                chat_id=submission["chat_id"],
            )
            snapshot = result.get("run")
        if snapshot is not None:
            self.storage.project(submission, snapshot)
            await self.project_events(submission, snapshot)
        return snapshot

    def record_artifact(self, submission, event):
        if (
            event.get("run_id") != submission["run_id"]
            or event.get("session_id") != submission["session_id"]
        ):
            raise GatewayError(
                "runner_protocol", "Runner event ownership does not match", 502
            )
        if event.get("type") == "artifact":
            with self.storage.db:
                self.storage.db.execute(
                    "INSERT OR IGNORE INTO agent_artifacts VALUES (?,?,?)",
                    (
                        event["data"]["artifact_id"],
                        submission["chat_id"],
                        submission["run_id"],
                    ),
                )

    async def project_events(self, submission, snapshot):
        run_id = snapshot["run_id"]
        submission = {**submission, "run_id": run_id}
        row = self.storage.db.execute(
            "SELECT last_seq FROM agent_projection WHERE run_id=?", (run_id,)
        ).fetchone()
        after = row[0] if row else 0
        watermark = snapshot["last_seq"]
        if after >= watermark:
            return
        try:
            session = await self.client.http()
            async with session.get(
                self.client.base_url
                + f"/v1/runs/{quote(run_id, safe='')}/events?after={after}",
                headers=self.client.headers(submission["chat_id"]),
                allow_redirects=False,
            ) as response:
                if response.status != 200:
                    raise GatewayError(
                        "runner_protocol", "Runner events could not be reconciled", 502
                    )
                async for line in response.content:
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    self.record_artifact(submission, event)
                    with self.storage.db:
                        self.storage.db.execute(
                            "INSERT INTO agent_projection VALUES (?,?) ON CONFLICT(run_id) DO UPDATE SET last_seq=max(last_seq,excluded.last_seq)",
                            (run_id, event["seq"]),
                        )
                    if event["seq"] >= watermark:
                        break
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            raise GatewayError(
                "runner_unavailable", "Runner event reconciliation needs retry", 503
            ) from None

    async def reconcile_forever(self):
        for agent_id in AGENTS:
            try:
                async with self.agent_lock(agent_id):
                    await self.synchronize(agent_id)
            except GatewayError:
                pass
        while True:
            for submission in self.storage.pending():
                try:
                    await self.reconcile_one(submission)
                except GatewayError:
                    pass  # Keep uncertainty; never replace it with local not_found.
            await asyncio.sleep(1)

    async def bound_snapshot(self, chat_id):
        self.chat(chat_id)
        binding = self.storage.binding(chat_id)
        if not binding or binding["agent_id"] is None:
            return {
                "chat_id": chat_id,
                "agent_id": None,
                "session_id": None,
                "workspace": None,
                "active_run_id": None,
                "last_run_id": None,
            }
        return await self.client.request(
            "GET", f"/v1/sessions/{binding['session_id']}", chat_id=chat_id
        )

    def assert_ordinary(self, chat_id):
        binding = self.storage.binding(chat_id) if chat_id else None
        if binding and binding["agent_id"] is not None:
            raise HTTPException(
                status_code=409,
                detail="This chat is bound to an Agent; use the Agent run API or create a new chat",
            )

    async def before_delete(self, chat_id):
        binding = self.storage.binding(chat_id)
        if binding and binding["agent_id"] is not None:
            if not binding["confirmed"]:
                raise HTTPException(
                    status_code=409,
                    detail="Agent binding needs verification before deleting this chat",
                )
            snapshot = await self.bound_snapshot(chat_id)
            if snapshot["active_run_id"]:
                raise HTTPException(
                    status_code=409,
                    detail="Stop or verify the active Agent run before deleting this chat",
                )
            if any(row["chat_id"] == chat_id for row in self.storage.pending()):
                raise HTTPException(
                    status_code=409,
                    detail="Agent submission needs verification before deleting this chat",
                )

    def enrich_messages(self, messages):
        result = []
        for message in messages:
            value = message.model_dump()
            row = self.storage.db.execute(
                "SELECT run_id FROM agent_messages WHERE message_id=?", (message.id,)
            ).fetchone()
            if row:
                value["run_id"] = row[0]
            result.append(value)
        return result

    async def _submit(self, chat_id, body, kind):
        self.chat(chat_id)
        key = text(body.get("client_request_id"), "client_request_id")
        async with self.lock(chat_id):
            binding = self.storage.binding(chat_id)
            if not binding or not binding["agent_id"] or not binding["confirmed"]:
                raise GatewayError(
                    "agent_binding_required",
                    "Bind this chat to a ready Agent first",
                    409,
                )
            serialized = json.dumps(
                body, sort_keys=True, ensure_ascii=False, separators=(",", ":")
            )
            previous = self.storage.submission(chat_id, key)
            if previous:
                if (
                    previous["body"] != serialized
                    or previous["kind"] != kind
                    or previous["session_id"] != binding["session_id"]
                ):
                    raise GatewayError(
                        "idempotency_conflict",
                        "Request key already has different content",
                        409,
                    )
                snapshot = await self.reconcile_one(previous)
                if snapshot is not None:
                    return snapshot
                raise GatewayError(
                    "admission_unknown",
                    "This submission still needs verification; do not submit it under a new key",
                    409,
                )
            await self.prepare_agent(binding["agent_id"])
            self.storage.reserve(chat_id, key, binding["session_id"], kind, serialized)
            submission = self.storage.submission(chat_id, key)
            try:
                if kind == "compact":
                    result = await self.client.request(
                        "POST",
                        f"/v1/sessions/{binding['session_id']}/compact",
                        chat_id=chat_id,
                        body={"client_request_id": key},
                    )
                else:
                    result = await self.client.request(
                        "POST",
                        "/v1/runs",
                        chat_id=chat_id,
                        body={**body, "session_id": binding["session_id"]},
                    )
            except GatewayError as error:
                if 400 <= error.status < 500:
                    # A definitive rejection did not admit native work. Keep no
                    # user display row, but the key is available for a corrected retry.
                    with self.storage.db:
                        self.storage.db.execute(
                            "DELETE FROM agent_submissions WHERE chat_id=? AND client_request_id=? AND run_id IS NULL",
                            (chat_id, key),
                        )
                raise
            self.storage.project(submission, result)
            return result

    def _routes(self):
        router = self.router

        @router.get("/api/agents")
        async def agents(request: Request):
            self.origin(request)
            config = self.main.load_plugin_config()
            try:
                remote = {
                    item["id"]: item
                    for item in (await self.client.request("GET", "/v1/agents"))[
                        "agents"
                    ]
                }
            except GatewayError as error:
                remote = {
                    key: {
                        "availability": "unavailable",
                        "reason": error.message,
                        "capabilities": {},
                        "settings_schema": None,
                    }
                    for key in AGENTS
                }
            entries = []
            for agent_id in AGENTS:
                settings = (
                    config.get("plugins", {})
                    .get(agent_id, {})
                    .get("settings_values", {})
                )
                entries.append(
                    {
                        **remote.get(agent_id, {}),
                        "id": agent_id,
                        "name": agent_id,
                        "installed": self.installed(agent_id),
                        "enabled": self.enabled(agent_id),
                        "settings_revision": hashlib.sha256(
                            json.dumps(settings, sort_keys=True).encode()
                        ).hexdigest()[:16],
                    }
                )
            return {"agents": entries}

        @router.get("/api/agents/workspaces")
        async def workspaces(request: Request):
            self.origin(request)
            return await self.client.request("GET", "/v1/workspaces")

        @router.get("/api/agents/{agent_id}/health")
        async def health(agent_id: str, request: Request):
            self.origin(request)
            if agent_id not in AGENTS:
                raise GatewayError("agent_not_found", "Unknown Agent", 404)
            return await self.client.request("GET", f"/v1/agents/{agent_id}/health")

        @router.get("/api/chats/{chat_id}/agent")
        async def binding_get(chat_id: str, request: Request):
            self.origin(request)
            return await self.bound_snapshot(chat_id)

        @router.put("/api/chats/{chat_id}/agent")
        async def binding_set(chat_id: str, request: Request):
            self.origin(request)
            body = fields(await request.json(), {"agent_id", "workspace"})
            if body["agent_id"] is not None and body["agent_id"] not in AGENTS:
                raise GatewayError("agent_not_found", "Unknown Agent", 404)
            selection = fields(body["workspace"], {"kind"}, {"id"})
            if (
                selection["kind"] not in ("managed", "project")
                or (selection["kind"] == "managed" and "id" in selection)
                or (
                    selection["kind"] == "project"
                    and not isinstance(selection.get("id"), str)
                )
            ):
                raise GatewayError(
                    "invalid_workspace",
                    "Choose a managed workspace or an allowed project",
                )
            self.chat(chat_id)
            async with self.lock(chat_id):
                old = self.storage.binding(chat_id)
                if self.main.db.get_messages(chat_id) or any(
                    row["chat_id"] == chat_id for row in self.storage.pending()
                ):
                    raise GatewayError(
                        "chat_already_started",
                        "Create a new chat to change the Agent or workspace",
                        409,
                    )
                if old and old["agent_id"] is not None:
                    if (
                        old["agent_id"] == body["agent_id"]
                        and not old["confirmed"]
                        and old["workspace"] == selection
                    ):
                        session_id = old["session_id"]
                    else:
                        current = await self.bound_snapshot(chat_id)
                        if current["active_run_id"]:
                            raise GatewayError(
                                "session_busy",
                                "An active run prevents changing this binding",
                                409,
                            )
                        session_id = uuid4().hex
                else:
                    session_id = uuid4().hex
                if body["agent_id"] is None:
                    self.storage.bind(chat_id, None, None, None, True)
                    return await self.bound_snapshot(chat_id)
                await self.prepare_agent(body["agent_id"], include_settings=True)
                self.storage.bind(chat_id, body["agent_id"], session_id, selection)
                result = await self.client.request(
                    "POST",
                    "/v1/sessions",
                    chat_id=chat_id,
                    body={"session_id": session_id, "chat_id": chat_id, **body},
                )
                self.storage.bind(
                    chat_id, body["agent_id"], session_id, result["workspace"], True
                )
                return result

        @router.post("/api/agents/runs", status_code=202)
        async def submit(request: Request):
            self.origin(request)
            body = fields(
                await request.json(),
                {"chat_id", "client_request_id", "message", "attachments"},
            )
            text(body["message"], "message", 1000000)
            if (
                not isinstance(body["attachments"], list)
                or len(body["attachments"]) > 20
            ):
                raise GatewayError("invalid_attachments", "Invalid attachments")
            for item in body["attachments"]:
                fields(item, {"attachment_id"})
                text(item["attachment_id"], "attachment_id")
            return await self._submit(body["chat_id"], body, "run")

        @router.get("/api/agents/runs")
        async def lookup(request: Request):
            self.origin(request)
            chat_id = text(request.query_params.get("chat_id"), "chat_id")
            key = text(
                request.query_params.get("client_request_id"), "client_request_id"
            )
            self.chat(chat_id)
            local = self.storage.submission(chat_id, key)
            result = await self.client.request(
                "GET",
                "/v1/runs?chat_id="
                + quote(chat_id, safe="")
                + "&client_request_id="
                + quote(key, safe=""),
                chat_id=chat_id,
            )
            if local and result.get("run"):
                self.storage.project(local, result["run"])
            if local and not result.get("run"):
                result["admission"] = "unknown"
            return result

        async def own_run(run_id):
            local = self.storage.run(run_id)
            if local is None:
                raise GatewayError("run_not_found", "Run not found in ChatRaw", 404)
            return local

        @router.get("/api/agents/runs/{run_id}")
        async def snapshot(run_id: str, request: Request):
            self.origin(request)
            return await self.reconcile_one(await own_run(run_id))

        @router.get("/api/agents/runs/{run_id}/events")
        async def events(run_id: str, request: Request):
            self.origin(request)
            local = await own_run(run_id)
            raw_after = request.query_params.get("after", "0")
            if not raw_after.isdigit():
                raise GatewayError(
                    "invalid_cursor", "after must be a nonnegative integer"
                )
            path = f"/v1/runs/{quote(run_id, safe='')}/events?after={raw_after}"
            try:
                session = await self.client.http()
                upstream = await session.get(
                    self.client.base_url + path,
                    headers=self.client.headers(local["chat_id"]),
                    timeout=aiohttp.ClientTimeout(total=None, connect=5, sock_read=45),
                    allow_redirects=False,
                )
            except (aiohttp.ClientError, asyncio.TimeoutError):
                raise GatewayError(
                    "runner_unavailable", "Runner event stream is unavailable", 503
                ) from None
            if upstream.status != 200:
                upstream.close()
                raise GatewayError(
                    "events_unavailable", "Run events or cursor are unavailable", 409
                )

            async def stream():
                try:
                    async for line in upstream.content:
                        if line.strip():
                            self.record_artifact(local, json.loads(line))
                        yield line
                finally:
                    upstream.close()

            return StreamingResponse(
                stream(),
                media_type="application/x-ndjson",
                headers={
                    "Cache-Control": "no-store",
                    "X-Accel-Buffering": "no",
                    "Content-Encoding": "identity",
                },
            )

        @router.post("/api/agents/runs/{run_id}/cancel")
        async def cancel(run_id: str, request: Request):
            self.origin(request)
            local = await own_run(run_id)
            result = await self.client.request(
                "POST",
                f"/v1/runs/{quote(run_id, safe='')}/cancel",
                chat_id=local["chat_id"],
            )
            if result["status"] == "unknown":
                raise GatewayError(
                    "stop_unconfirmed",
                    "Stop could not be confirmed; inspect the run state",
                    409,
                )
            return result

        @router.post("/api/agents/runs/{run_id}/interactions/{interaction_id}/reply")
        async def respond(run_id: str, interaction_id: str, request: Request):
            self.origin(request)
            local = await own_run(run_id)
            binding = self.storage.binding(local["chat_id"])
            self.require_enabled(binding["agent_id"])
            return await self.client.request(
                "POST",
                f"/v1/runs/{quote(run_id, safe='')}/interactions/{quote(interaction_id, safe='')}/reply",
                chat_id=local["chat_id"],
                body=await request.json(),
            )

        @router.post("/api/agents/sessions/{session_id}/compact", status_code=202)
        async def compact(session_id: str, request: Request):
            self.origin(request)
            body = fields(await request.json(), {"client_request_id"})
            row = self.storage.db.execute(
                "SELECT chat_id FROM agent_bindings WHERE session_id=?", (session_id,)
            ).fetchone()
            if row is None:
                raise GatewayError(
                    "session_not_found", "Session not found in ChatRaw", 404
                )
            return await self._submit(row[0], body, "compact")

        @router.post("/api/agents/attachments")
        async def attachment(request: Request):
            self.origin(request)
            async with request.form(max_files=1, max_fields=1) as form:
                if set(form) != {"file", "chat_id"} or len(form.multi_items()) != 2:
                    raise GatewayError(
                        "invalid_attachment", "Expected file and chat_id"
                    )
                chat_id = text(form["chat_id"], "chat_id")
                self.chat(chat_id)
                binding = self.storage.binding(chat_id)
                if not binding or not binding["agent_id"] or not binding["confirmed"]:
                    raise GatewayError(
                        "agent_binding_required",
                        "Bind a ready Agent before uploading",
                        409,
                    )
                self.require_enabled(binding["agent_id"])
                upload = form["file"]
                if not hasattr(upload, "read"):
                    raise GatewayError(
                        "invalid_attachment", "Expected an uploaded file"
                    )
                data = await upload.read(25 * 1024 * 1024 + 1)
                if len(data) > 25 * 1024 * 1024:
                    raise GatewayError(
                        "attachment_too_large", "Attachment exceeds 25 MiB", 413
                    )
                return await self.client.request(
                    "POST",
                    f"/v1/attachments?session_id={binding['session_id']}",
                    chat_id=chat_id,
                    data=data,
                    headers={
                        "X-Filename": upload.filename or "attachment",
                        "Content-Type": upload.content_type
                        or "application/octet-stream",
                    },
                )

        @router.get("/api/agents/artifacts/{artifact_id}")
        async def artifact(artifact_id: str, request: Request):
            self.origin(request)
            # Resolve ownership via recorded artifact events, never accept a path
            # or arbitrary chat ID from the download caller.
            row = self.storage.db.execute(
                "SELECT chat_id FROM agent_artifacts WHERE artifact_id=?",
                (artifact_id,),
            ).fetchone()
            if row is None:
                raise GatewayError("artifact_not_found", "Artifact not found", 404)
            self.chat(row[0])
            session = await self.client.http()
            upstream = await session.get(
                self.client.base_url + f"/v1/artifacts/{quote(artifact_id, safe='')}",
                headers=self.client.headers(row[0]),
                allow_redirects=False,
            )
            if upstream.status != 200:
                upstream.close()
                raise GatewayError(
                    "artifact_unavailable", "Artifact is unavailable", 404
                )

            async def chunks():
                try:
                    async for chunk in upstream.content.iter_chunked(65536):
                        yield chunk
                finally:
                    upstream.close()

            return StreamingResponse(
                chunks(),
                media_type="application/octet-stream",
                headers={
                    "Content-Disposition": upstream.headers.get(
                        "Content-Disposition", "attachment"
                    ),
                    "X-Content-Type-Options": "nosniff",
                },
            )

        async def retired(request: Request):
            self.origin(request)
            return JSONResponse(
                {
                    "success": False,
                    "error": "Hermes now uses the unified Agent Runner. Existing chats and HTTP settings are retained; create a new Agent chat after configuring the native Gateway.",
                },
                status_code=410,
            )

        router.add_api_route("/api/hermes/chat", retired, methods=["POST"])
        router.add_api_route("/api/hermes/health", retired, methods=["GET"])
        router.add_api_route(
            "/api/hermes/runs/{run_id:path}/approval", retired, methods=["POST"]
        )
