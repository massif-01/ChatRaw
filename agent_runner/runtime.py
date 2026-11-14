"""Runner execution owner: admission, durable events and native control calls."""

import asyncio
import hashlib
import json
import logging
from pathlib import Path

from .adapters.base import AdapterError, TERMINAL_STATUSES
from .store import RunnerError, Store, encode, identifier, now
from . import validation as check


logger = logging.getLogger(__name__)
AGENT_IDS = ("hermes", "codex", "claude", "pi", "deepseek")
EVENT_FIELDS = {
    "text_delta": {"text", "message_id"},
    "reasoning_delta": {"text", "message_id"},
    "tool_started": {
        "tool_call_id",
        "name",
        "title",
        "input_preview",
        "output_preview",
        "status",
        "duration_ms",
    },
    "tool_updated": {
        "tool_call_id",
        "name",
        "title",
        "input_preview",
        "output_preview",
        "status",
        "duration_ms",
    },
    "tool_completed": {
        "tool_call_id",
        "name",
        "title",
        "input_preview",
        "output_preview",
        "status",
        "duration_ms",
    },
    "usage": {"input_tokens", "output_tokens", "cost", "currency"},
    "error": {"code", "message", "retryable"},
}


def unavailable(reason):
    return {
        "availability": "unavailable",
        "reason": reason,
        "version": None,
        "capabilities": {
            **{
                key: False
                for key in (
                    "streaming_text",
                    "tools",
                    "questions",
                    "approvals",
                    "cancel",
                    "resume",
                    "compact",
                    "images",
                    "files",
                    "steer",
                    "queue",
                )
            },
            "cancel_mode": "none",
        },
        "checks": {
            key: "not_checked"
            for key in ("program", "protocol", "authentication", "model_request")
        },
    }


class Runtime:
    def __init__(self, directory, factories, config=None):
        self.store = Store(Path(directory))
        self.factories = factories
        self.config = config or {}
        self.max_concurrency = self.config.get("max_concurrency", 3)
        if type(self.max_concurrency) is not int or self.max_concurrency < 1:
            raise ValueError("max_concurrency must be a positive integer")
        self.instances = {}
        self.capabilities = {}
        self.tasks = {}
        self.signals = {}
        self.controls = {}
        self.initializers = {}
        self.admission = asyncio.Lock()
        self.closing = False
        self.file_store = (
            None  # Installed by the HTTP service; tests may use the core alone.
        )

    def signal(self, run_id):
        return self.signals.setdefault(run_id, asyncio.Event())

    def notify(self, run_id):
        self.signal(run_id).set()

    def control(self, run_id):
        return self.controls.setdefault(run_id, asyncio.Lock())

    def enabled(self, agent_id):
        row = self.store.db.execute(
            "SELECT enabled FROM agents WHERE id=?", (agent_id,)
        ).fetchone()
        return bool(row and row[0])

    def require_enabled(self, agent_id):
        if not self.enabled(agent_id):
            raise RunnerError("agent_disabled", "Agent is disabled", 403)

    def factory(self, agent_id):
        if agent_id not in AGENT_IDS or agent_id not in self.factories:
            raise RunnerError(
                "agent_unavailable", "Agent adapter is not installed on the host", 503
            )
        return self.factories[agent_id]

    def agent_config(self, agent_id):
        config = dict(self.config.get("agents", {}).get(agent_id, {}))
        row = self.store.db.execute(
            "SELECT settings FROM agents WHERE id=?", (agent_id,)
        ).fetchone()
        if row:
            config.update(json.loads(row[0]))
        return config

    def set_settings(self, agent_id, settings):
        from jsonschema import Draft202012Validator, ValidationError

        adapter = self.factory(agent_id)()
        try:
            Draft202012Validator(adapter.settings_schema).validate(settings)
        except ValidationError:
            raise RunnerError(
                "invalid_settings", "Agent settings do not match its declared schema"
            ) from None
        # Public settings remain editable before the host executable/account is
        # configured. Full private config is validated at session/run admission.
        with self.store.db:
            self.store.db.execute(
                "INSERT INTO agents(id,enabled,settings) VALUES (?,0,?) ON CONFLICT(id) DO UPDATE SET settings=excluded.settings",
                (agent_id, encode(settings)),
            )

    async def probe(self, agent_id):
        if agent_id not in self.factories:
            return {
                "agent_id": agent_id,
                **unavailable("Adapter is not installed on the host"),
            }
        adapter = self.factory(agent_id)()
        try:
            result = await adapter.probe(self.agent_config(agent_id))
            return {"agent_id": agent_id, **result}
        except AdapterError as error:
            return {"agent_id": agent_id, **unavailable(error.message)}

    async def set_enabled(self, agent_id, enabled):
        if agent_id not in AGENT_IDS or type(enabled) is not bool:
            raise RunnerError("invalid_agent", "Invalid Agent or enabled flag")
        # No await between the gate change and collecting affected runs. The
        # control locks below order native reply/cancel dispatch for each run.
        with self.store.db:
            self.store.db.execute(
                "INSERT INTO agents(id,enabled) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET enabled=excluded.enabled",
                (agent_id, int(enabled)),
            )
        if not enabled:
            affected = [
                run
                for run in self.store.active()
                if self.store.session(run["session_id"])["agent_id"] == agent_id
            ]
            if affected:
                # A dropped configuration request must not abandon cancellation
                # halfway through the sessions this Runner owns.
                await asyncio.shield(
                    asyncio.gather(*(self.cancel(run["id"]) for run in affected))
                )

    def workspace(self, session_id, selection):
        if selection == {"kind": "managed"}:
            path = self.store.directory / "workspaces" / session_id
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
            return path, {
                "kind": "managed",
                "id": session_id,
                "label": "Managed workspace",
            }
        check.object_fields(selection, {"kind", "id"})
        if selection["kind"] != "project":
            raise RunnerError("invalid_workspace", "Unknown workspace kind")
        project_id = check.text(selection["id"], "project ID", 200)
        project = self.config.get("workspaces", {}).get(project_id)
        if not project:
            raise RunnerError("invalid_workspace", "Project is not allowed", 403)
        path = Path(project["path"]).resolve(strict=True)
        if not path.is_dir():
            raise RunnerError("invalid_workspace", "Project directory is unavailable")
        return path, {"kind": "project", "id": project_id, "label": project["label"]}

    async def create_session(self, session_id, chat_id, agent_id, selection):
        check.text(session_id, "session ID", 200)
        # Session IDs become managed directory names, unlike opaque native IDs.
        if not session_id.isascii() or not session_id.isalnum():
            raise RunnerError(
                "invalid_session_id", "Session ID must be an opaque alphanumeric ID"
            )
        check.text(chat_id, "chat ID", 200)
        check.text(agent_id, "Agent ID", 50)
        async with self.admission:
            existing = self.store.db.execute(
                "SELECT id FROM sessions WHERE id=?", (session_id,)
            ).fetchone()
            if existing:
                session = self.store.session(session_id)
                public = session["workspace_public"]
                matches = public["kind"] == selection.get("kind") and (
                    public["kind"] == "managed" or public["id"] == selection.get("id")
                )
                if (
                    session["chat_id"] != chat_id
                    or session["agent_id"] != agent_id
                    or not matches
                ):
                    raise RunnerError(
                        "session_conflict",
                        "Session ID already has a different binding",
                        409,
                    )
                if session["binding"] is None:
                    raise RunnerError(
                        "session_unknown",
                        "Native session creation requires verification",
                        409,
                    )
                return self.session_snapshot(session_id)
            self.require_enabled(agent_id)
            adapter = self.factory(agent_id)()
            config = adapter.validate_config(self.agent_config(agent_id))
            probe = await adapter.probe(config)
            if probe["availability"] != "ready":
                raise RunnerError(
                    "agent_unavailable", probe["reason"] or "Agent is not ready", 503
                )
            self.require_enabled(agent_id)
            workspace, public = self.workspace(session_id, selection)
            with self.store.db:
                self.store.db.execute(
                    "INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        session_id,
                        chat_id,
                        agent_id,
                        str(workspace),
                        encode(public),
                        None,
                        encode(config),
                        now(),
                        encode(self.config.get("agents", {}).get(agent_id, {})),
                    ),
                )
            # Native creation can be ambiguous on transport failure: reservation
            # stays in place, and repeat create must not launch again.
            try:
                binding = await adapter.create_session(session_id, workspace, config)
                self.validate_binding(self.store.session(session_id), binding)
            except BaseException:
                try:
                    await adapter.close(
                        {
                            "session_id": session_id,
                            "agent_id": agent_id,
                            "workspace": str(workspace),
                            "native": {},
                        }
                    )
                except Exception:
                    logger.warning(
                        "Session creation cleanup incomplete for %s", session_id
                    )
                raise
            with self.store.db:
                self.store.db.execute(
                    "UPDATE sessions SET binding=? WHERE id=?",
                    (encode(binding), session_id),
                )
            self.instances[session_id] = adapter
            self.capabilities[session_id] = probe["capabilities"]
            return self.session_snapshot(session_id)

    @staticmethod
    def validate_binding(session, binding):
        check.object_fields(binding, {"session_id", "agent_id", "workspace", "native"})
        if (
            binding["session_id"] != session["id"]
            or binding["agent_id"] != session["agent_id"]
            or binding["workspace"] != session["workspace"]
            or not isinstance(binding["native"], dict)
        ):
            raise RunnerError(
                "invalid_binding", "Adapter changed the session identity", 502
            )
        encode(binding)

    def session_snapshot(self, session_id):
        session = self.store.session(session_id)
        active = self.store.active(session_id)
        last = self.store.db.execute(
            "SELECT id FROM runs WHERE session_id=? ORDER BY rowid DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        return {
            "chat_id": session["chat_id"],
            "session_id": session_id,
            "agent_id": session["agent_id"],
            "workspace": session["workspace_public"],
            "active_run_id": active[0]["id"] if active else None,
            "last_run_id": last[0] if last else None,
        }

    async def instance(self, session):
        async with self.initializers.setdefault(session["id"], asyncio.Lock()):
            return await self._instance(session)

    async def _instance(self, session):
        sid = session["id"]
        session = self.store.session(sid)
        active = bool(self.store.active(sid))
        adapter = self.instances.get(sid) or self.factory(session["agent_id"])()
        settings = self.store.db.execute(
            "SELECT settings FROM agents WHERE id=?", (session["agent_id"],)
        ).fetchone()
        config = adapter.validate_config(
            {**session["base_config"], **(json.loads(settings[0]) if settings else {})}
        )
        if not active and sid in self.instances and config != session["config"]:
            await adapter.close(session["binding"])
            del self.instances[sid]
            self.capabilities.pop(sid, None)
        if sid not in self.instances:
            if active:
                raise RunnerError(
                    "session_unknown",
                    "Active session requires run recovery, not resume",
                    409,
                )
            adapter = self.factory(session["agent_id"])()
            if session["binding"] is None:
                raise RunnerError(
                    "session_unknown",
                    "Native session creation requires verification",
                    409,
                )
            binding = await adapter.resume_session(session["binding"], config)
            self.validate_binding(session, binding)
            with self.store.db:
                self.store.db.execute(
                    "UPDATE sessions SET binding=?,config=? WHERE id=?",
                    (encode(binding), encode(config), sid),
                )
            self.instances[sid] = adapter
        if sid not in self.capabilities:
            self.capabilities[sid] = (
                await self.instances[sid].probe(self.store.session(sid)["config"])
            )["capabilities"]
        return self.instances[sid]

    async def submit(
        self,
        session_id,
        chat_id,
        client_request_id,
        message="",
        attachments=None,
        kind="run",
    ):
        check.text(session_id, "session ID", 200)
        check.text(chat_id, "chat ID", 200)
        check.text(client_request_id, "client_request_id", 200)
        if kind not in ("run", "compact"):
            raise RunnerError("invalid_operation", "Unknown operation")
        check.text(message, "message", empty=kind == "compact")
        attachments = [] if attachments is None else attachments
        if not isinstance(attachments, list) or len(attachments) > 20:
            raise RunnerError("invalid_attachments", "Invalid attachments")
        for attachment in attachments:
            check.object_fields(attachment, {"attachment_id"})
            check.text(attachment["attachment_id"], "attachment ID", 200)
        request = {"message": message, "attachments": attachments}
        fingerprint = hashlib.sha256(
            encode({"kind": kind, "session_id": session_id, **request}).encode()
        ).hexdigest()
        async with self.admission:
            session = self.store.session(session_id)
            if session["chat_id"] != chat_id:
                raise RunnerError(
                    "ownership_mismatch", "Chat does not own this session", 403
                )
            previous = self.store.lookup(chat_id, client_request_id)
            if previous:
                if self.store.run(previous["run_id"])["fingerprint"] != fingerprint:
                    raise RunnerError(
                        "idempotency_conflict", "Request key has different content", 409
                    )
                return previous
            if self.closing:
                raise RunnerError("runner_stopping", "Runner is shutting down", 503)
            self.require_enabled(session["agent_id"])
            if self.store.active(session_id):
                raise RunnerError(
                    "session_busy", "Session has an active or unverified run", 409
                )
            if len(self.store.active()) >= self.max_concurrency:
                raise RunnerError(
                    "runner_busy", "Runner concurrency limit reached", 429
                )
            adapter = await self.instance(session)
            self.require_enabled(session["agent_id"])
            capabilities = self.capabilities[session_id]
            if kind == "compact" and not capabilities["compact"]:
                raise RunnerError(
                    "unsupported_capability", "Native compaction is not supported", 400
                )
            if attachments:
                if self.file_store is None:
                    raise RunnerError(
                        "unsupported_capability", "Attachments are unavailable"
                    )
                self.file_store.attachments(session, attachments, capabilities)
            run_id = identifier()
            with self.store.db:
                self.store.db.execute(
                    "INSERT INTO runs (id,session_id,chat_id,client_request_id,fingerprint,request,kind,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        run_id,
                        session_id,
                        chat_id,
                        client_request_id,
                        fingerprint,
                        encode(request),
                        kind,
                        "queued",
                        now(),
                        now(),
                    ),
                )
                self.store.event(run_id, "status", {"status": "queued"})
            self.tasks[run_id] = asyncio.create_task(
                self.execute(run_id, adapter), name=f"agent-run-{run_id}"
            )
            return self.store.snapshot(run_id)

    async def execute(self, run_id, adapter, recovery=False):
        session = self.store.session(self.store.run(run_id)["session_id"])

        async def emit(event):
            await self.emit(run_id, event)

        try:
            run = self.store.run(run_id)
            if not recovery and run["status"] == "stopping":
                result = {"status": "cancelled", "final_text": ""}  # Never dispatched.
            elif recovery:
                result = await adapter.recover_run(
                    session["binding"], {"run_id": run_id}, session["config"], emit
                )
            else:
                with self.store.db:
                    self.store.status(run_id, "running")
                self.notify(run_id)
                request = json.loads(run["request"])
                if run["kind"] == "compact":
                    result = await adapter.compact(
                        session["binding"], {"run_id": run_id}, emit
                    )
                else:
                    files = (
                        self.file_store.attachments(
                            session,
                            request["attachments"],
                            self.capabilities[session["id"]],
                        )
                        if request["attachments"]
                        else []
                    )
                    result = await adapter.run(
                        session["binding"],
                        {
                            "run_id": run_id,
                            "message": request["message"],
                            "attachments": files,
                        },
                        emit,
                    )
            check.object_fields(result, {"status", "final_text"}, {"error"})
            if result["status"] not in TERMINAL_STATUSES | {
                "unknown"
            } or not isinstance(result["final_text"], str):
                raise ValueError("Invalid adapter result")
        except asyncio.CancelledError:
            result = {
                "status": "unknown",
                "final_text": "",
                "error": {
                    "code": "runner_interrupted",
                    "message": "Runner stopped before native state was confirmed",
                    "retryable": False,
                },
            }
        except Exception as error:
            # Raw exception details may contain native arguments or credentials.
            logger.warning(
                "Agent run %s lost confirmed state (%s)", run_id, type(error).__name__
            )
            result = {
                "status": "unknown",
                "final_text": "",
                "error": {
                    "code": "native_state_unknown",
                    "message": "Native execution state needs verification",
                    "retryable": False,
                },
            }
        with self.store.db:
            self.store.settle(run_id, result)
        self.notify(run_id)

    async def emit(self, run_id, event):
        run = self.store.run(run_id)
        if run["status"] in TERMINAL_STATUSES:
            raise RunnerError("run_finished", "Late native event after settlement", 409)
        event_type = event.get("type")
        data = event.get("data")
        with self.store.db:
            if event_type == "binding_updated":
                session = self.store.session(run["session_id"])
                self.validate_binding(session, data)
                self.store.db.execute(
                    "UPDATE sessions SET binding=? WHERE id=?",
                    (encode(data), session["id"]),
                )
            elif event_type == "interaction_requested":
                if run["status"] == "stopping" or not self.enabled(
                    self.store.session(run["session_id"])["agent_id"]
                ):
                    raise RunnerError(
                        "run_stopping", "Interaction arrived after stop", 409
                    )
                payload = check.interaction(data)
                key = check.text(event.get("native_key"), "native key", 1000)
                old = self.store.db.execute(
                    "SELECT * FROM interactions WHERE run_id=? AND native_key=?",
                    (run_id, key),
                ).fetchone()
                if old:
                    if old["payload"] != encode(payload) or old["state"] != "pending":
                        raise RunnerError(
                            "interaction_conflict",
                            "Native interaction key was reused",
                            409,
                        )
                    return
                iid = identifier()
                self.store.db.execute(
                    "INSERT INTO interactions VALUES (?,?,?,?,?,NULL,NULL)",
                    (iid, run_id, key, encode(payload), "pending"),
                )
                self.store.event(run_id, event_type, {**payload, "interaction_id": iid})
                self.store.status(
                    run_id,
                    (
                        "waiting_approval"
                        if payload["kind"] == "approval"
                        else "waiting_input"
                    ),
                )
            elif event_type == "interaction_resolved":
                key = check.text(event.get("native_key"), "native key", 1000)
                row = self.store.db.execute(
                    "SELECT * FROM interactions WHERE run_id=? AND native_key=?",
                    (run_id, key),
                ).fetchone()
                check.object_fields(data, {"outcome"}, {"answer_summary"})
                if data["outcome"] not in (
                    "answered",
                    "cancelled",
                    "expired",
                    "invalidated",
                ):
                    raise RunnerError("invalid_outcome", "Invalid interaction outcome")
                if row and row["state"] in (
                    "pending",
                    "dispatching",
                    "accepted",
                    "unknown",
                ):
                    self.store.db.execute(
                        "UPDATE interactions SET state=? WHERE id=?",
                        (data["outcome"], row["id"]),
                    )
                    self.store.event(
                        run_id, event_type, {**data, "interaction_id": row["id"]}
                    )
                    self.refresh_waiting(run_id)
            elif event_type == "status":
                check.object_fields(data, {"status"}, {"reason"})
                if data["status"] not in (
                    "running",
                    "waiting_input",
                    "waiting_approval",
                ):
                    raise RunnerError(
                        "invalid_status",
                        "Adapter cannot publish authoritative final status",
                    )
                if run["status"] not in ("stopping", "unknown"):
                    self.store.status(run_id, data["status"], data.get("reason"))
            elif event_type == "artifact":
                if self.file_store is None:
                    raise RunnerError(
                        "artifacts_unavailable", "Artifact store unavailable"
                    )
                artifact = self.file_store.artifact(
                    self.store.session(run["session_id"]), run_id, data
                )
                self.store.event(run_id, "artifact", artifact)
            elif event_type in EVENT_FIELDS:
                if not isinstance(data, dict) or data.keys() - EVENT_FIELDS[event_type]:
                    raise RunnerError("invalid_event", "Unexpected event fields")
                if event_type in ("text_delta", "reasoning_delta"):
                    check.text(data.get("text"), "delta", empty=True)
                if len(encode(data)) > 1000000:
                    raise RunnerError("event_too_large", "Native event exceeds limit")
                self.store.event(run_id, event_type, data)
            else:
                raise RunnerError("invalid_event", "Unsupported adapter event")
        self.notify(run_id)

    def refresh_waiting(self, run_id):
        if self.store.run(run_id)["status"] in ("stopping", "unknown"):
            return
        kinds = [
            json.loads(row[0])["kind"]
            for row in self.store.db.execute(
                "SELECT payload FROM interactions WHERE run_id=? AND state='pending'",
                (run_id,),
            )
        ]
        status = (
            "waiting_approval"
            if "approval" in kinds
            else "waiting_input" if kinds else "running"
        )
        self.store.status(run_id, status)

    async def respond(self, run_id, interaction_id, response):
        async with self.control(run_id):
            run = self.store.run(run_id)
            session = self.store.session(run["session_id"])
            row = self.store.db.execute(
                "SELECT * FROM interactions WHERE id=? AND run_id=?",
                (interaction_id, run_id),
            ).fetchone()
            if not row:
                raise RunnerError(
                    "interaction_not_found", "Interaction not found for this run", 404
                )
            payload = json.loads(row["payload"])
            check.reply(payload, response)
            serialized = encode(response)
            if row["reply"] is not None:
                if row["reply"] != serialized:
                    raise RunnerError(
                        "reply_conflict",
                        "Interaction already has a different reply",
                        409,
                    )
                return {"interaction_id": interaction_id, "status": row["receipt"]}
            if (
                row["state"] != "pending"
                or run["status"] in TERMINAL_STATUSES | {"stopping", "unknown"}
                or not self.enabled(session["agent_id"])
            ):
                raise RunnerError(
                    "interaction_stale",
                    "Interaction is no longer accepting replies",
                    409,
                )
            if check.expired(payload):
                with self.store.db:
                    self.store.db.execute(
                        "UPDATE interactions SET state='expired' WHERE id=?",
                        (interaction_id,),
                    )
                    self.store.event(
                        run_id,
                        "interaction_resolved",
                        {"interaction_id": interaction_id, "outcome": "expired"},
                    )
                self.notify(run_id)
                raise RunnerError("interaction_expired", "Interaction has expired", 409)
            with self.store.db:
                self.store.db.execute(
                    "UPDATE interactions SET state='dispatching',receipt='dispatching',reply=? WHERE id=?",
                    (serialized, interaction_id),
                )
            # A timeout does not authorize retransmission. Keep the reply receipt.
            try:
                await asyncio.wait_for(
                    self.instances[session["id"]].respond(
                        session["binding"], row["native_key"], response
                    ),
                    15,
                )
                state = "accepted"
            except Exception:
                state = "unknown"
            with self.store.db:
                self.store.db.execute(
                    "UPDATE interactions SET state=? WHERE id=? AND state='dispatching'",
                    (state, interaction_id),
                )
                self.store.db.execute(
                    "UPDATE interactions SET receipt=? WHERE id=?",
                    (state, interaction_id),
                )
            self.notify(run_id)
            return {"interaction_id": interaction_id, "status": state}

    async def cancel(self, run_id):
        async with self.control(run_id):
            run = self.store.run(run_id)
            if run["status"] in TERMINAL_STATUSES | {"stopping"}:
                return {"run_id": run_id, "status": run["status"]}
            session = self.store.session(run["session_id"])
            with self.store.db:
                self.store.status(run_id, "stopping")
                self.store.invalidate(run_id)
            self.notify(run_id)
            if run["status"] == "queued":
                return {"run_id": run_id, "status": "stopping"}
            try:
                adapter = self.instances.get(session["id"])
                if adapter is None:
                    raise RuntimeError("Native control is unavailable")
                await asyncio.wait_for(adapter.cancel(session["binding"], run_id), 15)
            except Exception:
                with self.store.db:
                    if self.store.run(run_id)["status"] not in TERMINAL_STATUSES:
                        self.store.status(
                            run_id,
                            "unknown",
                            "Stop could not be confirmed; verification required",
                        )
                self.notify(run_id)
            task = self.tasks.get(run_id)
            if (
                adapter is not None
                and (task is None or task.done())
                and self.store.run(run_id)["status"] not in TERMINAL_STATUSES
            ):
                self.tasks[run_id] = asyncio.create_task(
                    self.execute(run_id, adapter, recovery=True)
                )
            return {"run_id": run_id, "status": self.store.run(run_id)["status"]}

    async def events(self, run_id, after=0):
        if type(after) is not int or after < 0:
            raise RunnerError("invalid_cursor", "Event cursor must be nonnegative")
        run = self.store.run(run_id)
        if after > run["last_seq"]:
            raise RunnerError("invalid_cursor", "Event cursor is beyond the run", 409)
        while True:
            signal = self.signal(run_id)
            signal.clear()
            batch = self.store.events(run_id, after)
            for event in batch:
                after = event["seq"]
                yield event
            if batch:
                continue
            if self.store.run(run_id)["status"] in TERMINAL_STATUSES:
                return
            await signal.wait()

    async def recover(self):
        active = self.store.active()
        with self.store.db:
            self.store.db.execute(
                "UPDATE interactions SET receipt='unknown' WHERE receipt='dispatching'"
            )
            for run in active:
                self.store.invalidate(run["id"])
                if run["status"] == "queued":
                    self.store.settle(
                        run["id"], {"status": "interrupted", "final_text": ""}
                    )
                else:
                    self.store.status(
                        run["id"], "unknown", "Runner restarted; checking native state"
                    )
        for run in active:
            if run["status"] == "queued":
                continue
            session = self.store.session(run["session_id"])
            if session["binding"] is None or session["agent_id"] not in self.factories:
                continue
            adapter = self.factory(session["agent_id"])()
            self.instances[session["id"]] = adapter
            self.tasks[run["id"]] = asyncio.create_task(
                self.execute(run["id"], adapter, recovery=True)
            )

    async def close(self):
        self.closing = True
        for run in self.store.active():
            await self.cancel(run["id"])
        pending = [task for task in self.tasks.values() if not task.done()]
        if pending:
            _, remaining = await asyncio.wait(pending, timeout=5)
            for task in remaining:
                task.cancel()
            await asyncio.gather(*remaining, return_exceptions=True)
        for sid, adapter in self.instances.items():
            try:
                await asyncio.wait_for(
                    adapter.close(self.store.session(sid)["binding"]), 5
                )
            except Exception:
                logger.warning("Adapter cleanup incomplete for session %s", sid)
        self.store.close()
