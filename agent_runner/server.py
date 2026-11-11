"""Authenticated loopback HTTP transport. Browsers use the ChatRaw gateway."""

import asyncio
import hmac
import json

from aiohttp import web

from .adapters.base import ADAPTER_CONTRACT_VERSION, AdapterError
from .files import FileStore
from .runtime import AGENT_IDS
from .store import RunnerError, encode
from . import validation as check


def create_app(runtime, token):
    if not isinstance(token, str) or len(token) < 32:
        raise ValueError("Runner requires a dedicated token of at least 32 characters")

    @web.middleware
    async def authenticated(request, handler):
        header = request.headers.get("Authorization", "")
        if not hmac.compare_digest(header, "Bearer " + token):
            return web.json_response(
                {
                    "error": {
                        "code": "unauthorized",
                        "message": "Runner authentication required",
                    }
                },
                status=401,
            )
        try:
            return await handler(request)
        except RunnerError as error:
            return web.json_response(
                {"error": {"code": error.code, "message": error.message}},
                status=error.status,
            )
        except AdapterError as error:
            return web.json_response({"error": error.as_data()}, status=400)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return web.json_response(
                {"error": {"code": "invalid_json", "message": "Invalid JSON body"}},
                status=400,
            )

    app = web.Application(middlewares=[authenticated], client_max_size=26 * 1024 * 1024)
    if runtime.file_store is None:
        runtime.file_store = FileStore(runtime.store)

    async def owner(request, run_id=None, session_id=None):
        if run_id is not None:
            session_id = runtime.store.run(run_id)["session_id"]
        check.text(session_id, "session ID", 200)
        session = runtime.store.session(session_id)
        if request.headers.get("X-ChatRaw-Chat-Id") != session["chat_id"]:
            raise RunnerError(
                "ownership_mismatch", "Chat does not own this resource", 403
            )
        return session

    async def health(request):
        return web.json_response(
            {
                "service": "chatraw-agent-runner",
                "schema_version": ADAPTER_CONTRACT_VERSION,
            }
        )

    async def agents(request):
        entries = []
        for agent_id in AGENT_IDS:
            probe = await runtime.probe(agent_id)
            entries.append(
                {
                    **probe,
                    "id": agent_id,
                    "enabled": runtime.enabled(agent_id),
                    "settings_schema": (
                        runtime.factory(agent_id)().settings_schema
                        if agent_id in runtime.factories
                        else None
                    ),
                }
            )
        return web.json_response({"agents": entries})

    async def probe(request):
        agent_id = request.match_info["agent_id"]
        if agent_id not in AGENT_IDS:
            raise RunnerError("agent_not_found", "Unknown Agent", 404)
        return web.json_response(await runtime.probe(agent_id))

    async def configure(request):
        body = await request.json()
        check.object_fields(body, {"enabled"}, {"settings"})
        if type(body["enabled"]) is not bool:
            raise RunnerError("invalid_enabled", "enabled must be boolean")
        agent_id = request.match_info["agent_id"]
        if "settings" in body:
            runtime.set_settings(agent_id, body["settings"])
        await runtime.set_enabled(agent_id, body["enabled"])
        return web.json_response({"agent_id": agent_id, "enabled": body["enabled"]})

    async def workspaces(request):
        return web.json_response(
            {
                "workspaces": [
                    {"id": key, "label": value["label"]}
                    for key, value in runtime.config.get("workspaces", {}).items()
                ]
            }
        )

    async def create_session(request):
        body = await request.json()
        check.object_fields(body, {"session_id", "chat_id", "agent_id", "workspace"})
        if request.headers.get("X-ChatRaw-Chat-Id") != body["chat_id"]:
            raise RunnerError(
                "ownership_mismatch", "Chat ownership header is required", 403
            )
        check.object_fields(body["workspace"], {"kind"}, {"id"})
        result = await runtime.create_session(
            **{key: body[key] for key in ("session_id", "chat_id", "agent_id")},
            selection=body["workspace"]
        )
        return web.json_response(result, status=201)

    async def session_snapshot(request):
        session = await owner(request, session_id=request.match_info["session_id"])
        return web.json_response(runtime.session_snapshot(session["id"]))

    async def submit(request):
        body = await request.json()
        check.object_fields(
            body,
            {"session_id", "chat_id", "client_request_id", "message", "attachments"},
        )
        await owner(request, session_id=body["session_id"])
        result = await runtime.submit(**body)
        return web.json_response(result, status=202)

    async def compact(request):
        body = await request.json()
        check.object_fields(body, {"client_request_id"})
        session = await owner(request, session_id=request.match_info["session_id"])
        result = await runtime.submit(
            session["id"], session["chat_id"], body["client_request_id"], kind="compact"
        )
        return web.json_response(result, status=202)

    async def lookup(request):
        chat_id = request.query.get("chat_id", "")
        if request.headers.get("X-ChatRaw-Chat-Id") != chat_id:
            raise RunnerError(
                "ownership_mismatch", "Chat ownership header is required", 403
            )
        check.text(chat_id, "chat ID", 200)
        key = check.text(
            request.query.get("client_request_id"), "client_request_id", 200
        )
        run = runtime.store.lookup(chat_id, key)
        return web.json_response(
            {"run": run, "admission": "accepted" if run else "not_found"}
        )

    async def snapshot(request):
        run_id = request.match_info["run_id"]
        await owner(request, run_id=run_id)
        return web.json_response(runtime.store.snapshot(run_id))

    async def events(request):
        run_id = request.match_info["run_id"]
        await owner(request, run_id=run_id)
        try:
            after = int(request.query.get("after", "0"))
        except ValueError:
            raise RunnerError(
                "invalid_cursor", "Event cursor must be nonnegative"
            ) from None
        if after < 0 or after > runtime.store.run(run_id)["last_seq"]:
            raise RunnerError("invalid_cursor", "Event cursor is outside the run", 409)
        response = web.StreamResponse(
            headers={
                "Content-Type": "application/x-ndjson",
                "Cache-Control": "no-store",
                "X-Accel-Buffering": "no",
            }
        )
        await response.prepare(request)
        iterator = runtime.events(run_id, after)
        pending = None
        try:
            while True:
                if pending is None:
                    pending = asyncio.create_task(anext(iterator))
                try:
                    event = await asyncio.wait_for(asyncio.shield(pending), 15)
                except asyncio.TimeoutError:
                    await response.write(b"\n")  # NDJSON heartbeat, no event sequence.
                    continue
                except StopAsyncIteration:
                    break
                pending = None
                await response.write((encode(event) + "\n").encode())
        except (ConnectionError, asyncio.CancelledError):
            # The independent runtime task is not a child of this subscription.
            pass
        finally:
            if pending is not None:
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            await iterator.aclose()
        return response

    async def cancel(request):
        run_id = request.match_info["run_id"]
        await owner(request, run_id=run_id)
        return web.json_response(await runtime.cancel(run_id))

    async def respond(request):
        run_id = request.match_info["run_id"]
        await owner(request, run_id=run_id)
        body = await request.json()
        return web.json_response(
            await runtime.respond(run_id, request.match_info["interaction_id"], body)
        )

    async def attachment(request):
        session_id = request.query.get("session_id")
        session = await owner(request, session_id=session_id)
        runtime.require_enabled(session["agent_id"])
        # The gateway sends raw bytes and metadata headers, avoiding multipart
        # temp files at the host transport boundary. Public API remains multipart.
        data = await request.read()
        import io

        name = request.headers.get("X-Filename", "attachment")
        mime = request.headers.get("Content-Type", "application/octet-stream")
        await runtime.instance(session)
        capabilities = runtime.capabilities[session_id]
        if not capabilities["images" if mime.startswith("image/") else "files"]:
            raise RunnerError(
                "unsupported_attachment", "Agent does not support this attachment type"
            )
        runtime.require_enabled(session["agent_id"])
        with runtime.store.db:
            result = runtime.file_store.save(session, io.BytesIO(data), name, mime)
        return web.json_response(result, status=201)

    async def artifact(request):
        artifact_id = request.match_info["artifact_id"]
        record = runtime.file_store.get(artifact_id, kind="artifact")
        await owner(request, session_id=record["session_id"])
        # Snapshot belongs to the runner's private files directory, not cwd.
        response = web.FileResponse(runtime.file_store.path(artifact_id))
        response.headers["Content-Type"] = "application/octet-stream"
        response.headers["X-Content-Type-Options"] = "nosniff"
        from urllib.parse import quote

        response.headers["Content-Disposition"] = (
            "attachment; filename*=UTF-8''" + quote(record["name"], safe="")
        )
        return response

    app.router.add_get("/v1/health", health)
    app.router.add_get("/v1/agents", agents)
    app.router.add_get("/v1/workspaces", workspaces)
    app.router.add_get("/v1/agents/{agent_id}/health", probe)
    app.router.add_put("/v1/agents/{agent_id}", configure)
    app.router.add_post("/v1/sessions", create_session)
    app.router.add_get("/v1/sessions/{session_id}", session_snapshot)
    app.router.add_post("/v1/sessions/{session_id}/compact", compact)
    app.router.add_post("/v1/runs", submit)
    app.router.add_get("/v1/runs", lookup)
    app.router.add_get("/v1/runs/{run_id}", snapshot)
    app.router.add_get("/v1/runs/{run_id}/events", events)
    app.router.add_post("/v1/runs/{run_id}/cancel", cancel)
    app.router.add_post(
        "/v1/runs/{run_id}/interactions/{interaction_id}/reply", respond
    )
    app.router.add_post("/v1/attachments", attachment)
    app.router.add_get("/v1/artifacts/{artifact_id}", artifact)

    async def lifecycle(app):
        await runtime.recover()
        yield
        await runtime.close()

    app.cleanup_ctx.append(lifecycle)
    return app
