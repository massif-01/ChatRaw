"""DeepSeek Harness Python SDK adapter with an owned runtime per session."""

import asyncio
import base64
from concurrent.futures import CancelledError as ThreadCancelled
from dataclasses import dataclass, field
from functools import partial
from importlib.metadata import PackageNotFoundError, version
from os import getenv
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from uuid import uuid4

from .base import (
    AdapterError,
    AgentAdapter,
    Capabilities,
    Emit,
    RunResult,
    UnsupportedCapability,
)


_SDK_VERSION = "0.2.2rc2"
_IMAGES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
_IMAGE_LIMIT = 8 * 1024 * 1024
_APPROVAL_CHOICES = {"allowed-once": "Allow once", "rejected": "Deny"}


@dataclass
class _Interaction:
    data: dict
    reply: asyncio.Future
    encode: object
    cancelled: object = None
    dispatch: object = None


@dataclass
class _Run:
    id: str
    emit: Emit
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    pending: dict[str, _Interaction] = field(default_factory=dict)
    started: bool = False
    stop: asyncio.Task | None = None
    text: str = ""
    last_turn: str | None = None
    tools: dict = field(default_factory=dict)


class DeepSeekAdapter(AgentAdapter):
    agent_id = "deepseek"
    settings_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "model": {"type": "string", "minLength": 1},
            "reasoning_effort": {"type": "string", "minLength": 1},
        },
    }

    def __init__(self):
        self._binding = None
        self._config = None
        self._harness = None
        self._session = None
        self._active: _Run | None = None
        self._fenced = False
        self._loop = None

    def validate_config(self, config):
        if set(config) - {"dsh_home", "model", "reasoning_effort"}:
            raise AdapterError("invalid_config", "Unknown DeepSeek configuration field")
        home = config.get("dsh_home")
        if not _text(home) or "\0" in home or not Path(home).is_absolute():
            raise AdapterError(
                "invalid_config", "DeepSeek requires an absolute host dsh_home root"
            )
        if any(
            not _text(config[key])
            for key in ("model", "reasoning_effort")
            if key in config
        ):
            raise AdapterError("invalid_config", "Invalid DeepSeek model settings")
        return dict(config)

    @staticmethod
    def _capabilities() -> Capabilities:
        return {
            "streaming_text": False,
            "tools": True,
            "questions": True,
            "approvals": True,
            "cancel": True,
            "cancel_mode": "process_stop",
            "resume": True,
            "compact": True,
            "images": True,
            "files": False,
            "steer": False,
            "queue": False,
            "limits": {
                "text_delivery": "committed_message",
                "image_mime_types": sorted(_IMAGES),
                "image_total_bytes": _IMAGE_LIMIT,
                "images_require_model_support": True,
            },
        }

    @staticmethod
    def _sdk_version():
        installed = version("deepseek-harness-sdk")
        if (
            installed != _SDK_VERSION
            or version("deepseek-harness-runtime-bin") != _SDK_VERSION
        ):
            raise AdapterError(
                "deepseek_sdk_version",
                f"DeepSeek requires matching SDK and runtime {_SDK_VERSION}",
            )
        return installed

    async def probe(self, config):
        checks = dict.fromkeys(
            ("program", "protocol", "authentication", "model_request"), "not_checked"
        )
        result = {
            "availability": "unconfigured",
            "reason": "DeepSeek host configuration is incomplete",
            "version": None,
            "capabilities": self._capabilities(),
            "checks": checks,
        }
        try:
            config = self.validate_config(config)
            if not Path(config["dsh_home"]).is_dir():
                return result
        except AdapterError:
            return result
        try:
            installed = self._sdk_version()
        except (PackageNotFoundError, AdapterError):
            checks["program"] = "failed"
            return {
                **result,
                "availability": "unavailable",
                "reason": f"Install DeepSeek SDK and bundled runtime {_SDK_VERSION} in the Runner environment",
            }
        checks["program"] = "passed"
        result["version"] = installed
        probe = DeepSeekAdapter()
        try:
            with TemporaryDirectory(prefix="chatraw-dsh-probe-") as root:
                harness = probe._make_harness(config, root, root, interactive=False)
                try:
                    await asyncio.to_thread(harness.start)
                finally:
                    await asyncio.to_thread(harness.close)
        except Exception:
            checks["protocol"] = "failed"
            return {
                **result,
                "availability": "unavailable",
                "reason": "DeepSeek SDK initialization failed",
            }
        checks["protocol"] = "passed"
        if not _text(getenv("DEEPSEEK_API_KEY")):
            return {
                **result,
                "reason": "DeepSeek SDK initialized; configure the Runner service credential",
            }
        return {
            **result,
            "availability": "ready",
            "reason": "DeepSeek SDK and credential configuration are ready; model request unverified",
        }

    def _make_harness(self, config, workspace, home, *, interactive=True):
        from deepseek_harness import DeepSeekHarness

        settings = {
            key: config[key] for key in ("model", "reasoning_effort") if key in config
        }
        return DeepSeekHarness(
            profile="sdk",
            cwd=str(workspace),
            dsh_home=str(home),
            shutdown_timeout_seconds=5,
            on_user_question=self._question_callback if interactive else None,
            approval_requests=interactive,
            **settings,
        )

    async def create_session(self, session_id, workspace, config):
        config = self.validate_config(config)
        try:
            native_id = f"session-{uuid4().hex}"
            home = Path(config["dsh_home"]).resolve(strict=True) / native_id
            home.mkdir(mode=0o700)
            binding = {
                "agent_id": "deepseek",
                "session_id": session_id,
                "workspace": str(workspace),
                "native": {"session_id": native_id, "dsh_home": str(home)},
            }
            await self._open(binding, config, resume=False)
        except OSError:
            raise AdapterError(
                "deepseek_home_invalid",
                "Could not create the DeepSeek session directory",
            ) from None
        return binding

    async def resume_session(self, binding, config):
        if self._active or self._fenced:
            raise AdapterError(
                "deepseek_session_busy", "DeepSeek session still has an unresolved run"
            )
        config = self.validate_config(config)
        if self._harness is not None:
            await self.close(self._binding)
        await self._open(binding, config, resume=True)
        return binding

    async def _open(self, binding, config, *, resume):
        self._loop = asyncio.get_running_loop()
        harness = None
        try:
            self._sdk_version()
            native_id = binding["native"]["session_id"]
            home = Path(binding["native"]["dsh_home"])
            if (
                binding["agent_id"] != "deepseek"
                or not _text(native_id)
                or home.name != native_id
                or home.resolve(strict=True) != home
                or home.parent != Path(config["dsh_home"]).resolve(strict=True)
            ):
                raise ValueError
            harness = self._make_harness(config, binding["workspace"], home)

            def open_session():
                if resume:
                    return harness.resume_session(native_id)
                session = harness.start_session(native_id)
                # The public SDK handle is lazy. This native call materializes its
                # persistent session without sending a prompt or billing a model.
                session.get_working_directory()
                return session

            session = await asyncio.to_thread(open_session)
            if session.id != native_id:
                raise ValueError
        except Exception:
            if harness is not None:
                await asyncio.to_thread(harness.close)
            action = (
                "reopen the original session"
                if resume
                else "create a persistent session"
            )
            raise AdapterError(
                "deepseek_session_unavailable", f"DeepSeek could not {action}"
            ) from None
        self._binding, self._config = binding, config
        self._harness, self._session = harness, session
        Thread(target=self._read_approvals, args=(harness,), daemon=True).start()

    async def run(self, binding, request, emit):
        return await self._execute(
            binding, request["run_id"], emit, request["message"], request["attachments"]
        )

    async def compact(self, binding, request, emit):
        return await self._execute(binding, request["run_id"], emit, "/compact", [])

    async def _execute(self, binding, run_id, emit, message, attachments):
        if self._active or self._fenced or self._binding != binding:
            raise AdapterError(
                "deepseek_session_busy", "DeepSeek session is unavailable for a new run"
            )
        active = self._active = _Run(run_id, emit)
        try:
            try:
                inputs = (
                    await asyncio.to_thread(_input, message, attachments)
                    if attachments
                    else message
                )
            except AdapterError as error:
                return {"status": "failed", "final_text": "", "error": error.as_data()}
            if active.stop:
                # Cancellation won before SDK dispatch. The idle runtime is still reusable.
                return _result("cancelled", "")
            if self._harness is None:
                try:
                    await self._open(binding, self._config, resume=True)
                except AdapterError:
                    return _result(
                        "failed", "", "DeepSeek could not reopen the original session"
                    )
                if active.stop:
                    return _result("cancelled", "")
            harness, session = self._harness, self._session
            execution = asyncio.create_task(
                asyncio.to_thread(self._run_sdk, active, harness, session, inputs)
            )
            active.started = True
            execution.add_done_callback(
                lambda task: active.queue.put_nowait(("result", task))
            )
            while True:
                kind, value = await active.queue.get()
                if kind == "notification":
                    await self._project(active, session.id, value)
                elif kind == "result":
                    try:
                        result = value.result()
                    except Exception:
                        if active.stop and await active.stop:
                            return _result("cancelled", active.text)
                        self._fenced = True
                        return _result(
                            "unknown",
                            active.text,
                            "DeepSeek did not confirm settlement",
                        )
                    if result.session_id != session.id:
                        self._fenced = True
                        return _result(
                            "unknown",
                            active.text,
                            "DeepSeek returned an unexpected session",
                        )
                    native_command = any(
                        event.get("type") == "command/run" for event in result.events
                    )
                    reason = (
                        result.finish_reason
                        if native_command
                        else active.last_turn or result.finish_reason
                    )
                    if reason == "aborted":
                        return _result(
                            "cancelled" if active.stop else "interrupted", active.text
                        )
                    if reason in {"completed", "max-tokens"} or reason is None:
                        return _result(
                            "completed",
                            result.final_response if native_command else active.text,
                        )
                    return _result(
                        "failed",
                        active.text,
                        "DeepSeek reported a failed or blocked operation",
                    )
        except (AttributeError, KeyError, TypeError, ValueError):
            self._fenced = True
            return _result(
                "unknown", active.text, "DeepSeek returned invalid protocol events"
            )
        finally:
            if active.stop:
                await active.stop
            self._active = None
            pending_interactions, active.pending = active.pending, {}
            for key, pending in pending_interactions.items():
                if not pending.reply.done():
                    pending.reply.cancel()
                await self._resolve(active, key, "invalidated")

    def _run_sdk(self, active, harness, session, inputs):
        from pydantic import RootModel

        def publish(notification):
            self._loop.call_soon_threadsafe(
                active.queue.put_nowait, ("notification", notification)
            )

        # The high-level query owns prompt receipts and native slash commands.
        # Its ordinary prompt interval stops at root idle. Wait for owned
        # descendants and trailing summary work before releasing Runner's slot.
        with harness.client.subscribe_session_notifications(session.id) as trailing:
            seen = {}

            def event_position(notification):
                if notification.method != "session.event":
                    return None
                return notification.payload["sessionId"], notification.payload["event"][
                    "seq"
                ]

            def observe(notification):
                position = event_position(notification)
                if position:
                    native_id, seq = position
                    seen[native_id] = seq
                publish(notification)

            def observe_tail(notification):
                position = event_position(notification)
                if position and position[1] > seen.get(position[0], -1):
                    publish(notification)

            result = session.run(inputs, on_notification=observe)
            harness.client.request(
                "session/wait",
                {"sessionId": session.id},
                response_model=RootModel[dict],
                on_notification=observe_tail,
                notification_subscription=trailing,
            )
            return result

    async def _project(self, active, session_id, notification):
        if notification.method != "session.event":
            return
        native_session = notification.payload.get("sessionId")
        event = notification.payload.get("event", {})
        kind, data = event.get("type"), event.get("data", {})
        if kind == "assistant/message" and native_session == session_id:
            active.text = ""
            for block in data["message"]["content"]:
                text = block.get("text")
                if not isinstance(text, str) or not text:
                    continue
                if block["type"] == "text":
                    active.text += text
                    await active.emit({"type": "text_delta", "data": {"text": text}})
                elif block["type"] == "reasoning":
                    await active.emit(
                        {"type": "reasoning_delta", "data": {"text": text}}
                    )
            usage = data.get("usage", {})
            counts = {}
            if type(usage.get("inputTokens")) is int:
                counts["input_tokens"] = sum(
                    usage.get(key, 0)
                    for key in (
                        "inputTokens",
                        "cacheReadTokens",
                        "cacheWriteTokens",
                    )
                )
            if type(usage.get("outputTokens")) is int:
                counts["output_tokens"] = usage["outputTokens"]
            if counts:
                await active.emit({"type": "usage", "data": counts})
        elif kind == "turn/end" and native_session == session_id:
            active.last_turn = data["reason"]["kind"]
        elif kind == "tool/call":
            key = (native_session, data["callId"])
            info = {"tool_call_id": uuid4().hex, "name": data["name"][:128]}
            active.tools[key] = info
            await active.emit({"type": "tool_started", "data": info})
        elif kind == "tool/result":
            message = data["message"]
            info = active.tools.pop((native_session, message["toolCallId"]), None)
            if info:
                await active.emit(
                    {
                        "type": "tool_completed",
                        "data": {
                            **info,
                            "status": "failed"
                            if message.get("isError")
                            else "completed",
                        },
                    }
                )

    def _question_callback(self, request, cancelled):
        # The SDK calls this on a worker, never on its stdio reader.
        coroutine = self._question_request(self._active, request, cancelled)
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        while not cancelled.is_set():
            try:
                return future.result(timeout=0.1)
            except TimeoutError:
                continue
            except ThreadCancelled:
                break
        future.cancel()
        return {"cancelled": True}

    async def _question_request(self, active, request, cancelled):
        if (
            active is None
            or active is not self._active
            or active.stop
            or cancelled.is_set()
            or request.session_id != self._binding["native"]["session_id"]
        ):
            return {"cancelled": True}
        data, encode = _question(request.questions)
        return await self._ask(active, data, encode, cancelled.is_set)

    def _read_approvals(self, harness):
        # next_request is blocking. The dedicated reader keeps draining even if
        # several approval requests are waiting on Runner concurrently.
        try:
            while True:
                request = harness.client.next_request()
                asyncio.run_coroutine_threadsafe(
                    self._approval_request(self._active, harness, request),
                    self._loop,
                )
        except Exception:
            return

    async def _approval_request(self, active, harness, request):
        if harness is not self._harness:
            return
        try:
            if request.method == "approval/request":
                if active is not None and active is self._active and not active.stop:
                    name = request.payload.get("toolName")
                    reason = request.payload.get("reason", "")
                    if _text(name) and isinstance(reason, str) and len(reason) <= 8000:
                        data = _approval(
                            "Allow DeepSeek tool call?", reason, _APPROVAL_CHOICES
                        )
                        data["operation"] = {"tool": name[:128]}
                        try:
                            await self._ask(
                                active,
                                data,
                                _approval_reply,
                                dispatch=partial(harness.client.respond, request.id),
                            )
                            return
                        except Exception:
                            pass
                await asyncio.to_thread(
                    harness.client.respond, request.id, {"outcome": "cancelled"}
                )
            else:
                await asyncio.to_thread(
                    harness.client.respond_error,
                    request.id,
                    code=-32601,
                    message="Unsupported host request",
                )
        except Exception:
            # The SDK discards late replies after a cancelled or closed transport.
            return

    async def _ask(self, active, data, encode, cancelled=None, dispatch=None):
        key = uuid4().hex
        future = self._loop.create_future()
        active.pending[key] = _Interaction(data, future, encode, cancelled, dispatch)
        try:
            await active.emit(
                {"type": "interaction_requested", "native_key": key, "data": data}
            )
            return await future
        finally:
            if active.pending.pop(key, None):
                await self._resolve(active, key, "invalidated")

    async def respond(self, binding, interaction_key, reply):
        active = self._active
        if binding != self._binding or not active or active.stop:
            raise AdapterError(
                "interaction_inactive", "DeepSeek interaction is no longer active"
            )
        pending = active.pending.get(interaction_key)
        if (
            pending is None
            or pending.reply.done()
            or (pending.cancelled and pending.cancelled())
        ):
            raise AdapterError(
                "interaction_inactive", "DeepSeek interaction is no longer active"
            )
        try:
            answer = pending.encode(reply)
        except (KeyError, TypeError, ValueError):
            raise AdapterError(
                "invalid_interaction_reply", "Reply does not match the DeepSeek request"
            ) from None
        del active.pending[interaction_key]
        if pending.dispatch:
            try:
                await asyncio.to_thread(pending.dispatch, answer)
            except Exception:
                await self._resolve(active, interaction_key, "invalidated")
                raise AdapterError(
                    "deepseek_reply_unknown", "DeepSeek did not confirm reply dispatch"
                ) from None
            finally:
                if not pending.reply.done():
                    pending.reply.set_result(None)
        else:
            pending.reply.set_result(answer)
        if active is self._active:
            await self._resolve(
                active,
                interaction_key,
                "cancelled" if reply == {"cancelled": True} else "answered",
            )

    @staticmethod
    async def _resolve(active, key, outcome):
        await active.emit(
            {
                "type": "interaction_resolved",
                "native_key": key,
                "data": {"outcome": outcome},
            }
        )

    async def cancel(self, binding, run_id):
        active = self._active
        if binding != self._binding or not active or active.id != run_id or active.stop:
            return
        active.stop = asyncio.create_task(
            self._stop_runtime(self._harness if active.started else None)
        )

    async def _stop_runtime(self, harness):
        if harness is None:
            return True

        def stop():
            from pydantic import RootModel

            try:
                harness.client.request(
                    "shutdown", None, response_model=RootModel[dict], timeout_seconds=10
                )
                graceful = True
            except Exception:
                graceful = False
            # SDK close reaps its owned subprocess. If the shutdown request
            # failed, a forced process exit alone cannot certify its tool scope.
            # Keep this discarded Harness handle initialized so a worker that
            # entered Session.run concurrently cannot lazily launch it again.
            harness.client.close()
            return graceful

        try:
            return await asyncio.to_thread(stop)
        except Exception:
            return False
        finally:
            self._harness = self._session = None

    async def close(self, binding):
        if binding != self._binding or self._active is not None:
            return
        if self._harness is not None:
            await asyncio.to_thread(self._harness.close)
        self._harness = self._session = self._binding = self._config = None


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _input(message, attachments):
    if sum(item["size"] for item in attachments) > _IMAGE_LIMIT:
        raise AdapterError(
            "attachment_too_large", "DeepSeek supports up to 8 MiB of images per run"
        )
    blocks = [{"type": "text", "text": message}]
    remaining = _IMAGE_LIMIT
    for item in attachments:
        if item["mime_type"] not in _IMAGES:
            raise UnsupportedCapability("DeepSeek attachment format")
        try:
            with item["path"].open("rb") as stream:
                data = stream.read(remaining + 1)
        except OSError:
            raise AdapterError(
                "attachment_unavailable", "DeepSeek attachment could not be read"
            ) from None
        if not data or len(data) != item["size"] or len(data) > remaining:
            raise AdapterError(
                "invalid_attachment", "DeepSeek attachment size changed or is invalid"
            )
        remaining -= len(data)
        blocks.append(
            {
                "type": "image",
                "mimeType": item["mime_type"],
                "data": base64.b64encode(data).decode(),
            }
        )
    return blocks


def _result(status, text, error=None) -> RunResult:
    result = {"status": status, "final_text": text}
    if error:
        result["error"] = {
            "code": "deepseek_settlement_unknown"
            if status == "unknown"
            else "deepseek_run_failed",
            "message": error,
            "retryable": False,
        }
    return result


def _approval(title, detail, choices):
    return {
        "kind": "approval",
        "title": title,
        "detail": detail,
        "decisions": [{"id": key, "label": label} for key, label in choices.items()],
        "allow_cancel": True,
    }


def _approval_reply(reply):
    if reply == {"cancelled": True}:
        return {"outcome": "cancelled"}
    if set(reply) != {"decision_id"} or reply["decision_id"] not in _APPROVAL_CHOICES:
        raise ValueError
    return {"outcome": reply["decision_id"]}


def _question(native):
    first = native[0]
    intent = first.get("intent") or {}
    if len(native) == 1 and intent.get("kind") == "approval":
        labels = [option["label"] for option in first["options"]]
        choices = {str(index): label for index, label in enumerate(labels, start=1)}

        def encode(reply):
            if reply == {"cancelled": True}:
                return reply
            if set(reply) != {"decision_id"}:
                raise ValueError
            return {
                "answers": [
                    {"id": first["id"], "selected": [choices[reply["decision_id"]]]}
                ]
            }

        return _approval(first["question"], first["detail"], choices), encode

    questions = []
    for item in native:
        options = [
            {
                "id": str(index),
                **{
                    key: option[key]
                    for key in ("label", "description")
                    if key in option
                },
            }
            for index, option in enumerate(item.get("options") or [], start=1)
        ]
        questions.append(
            {
                "id": item["id"],
                "text": item["question"],
                "type": ("multi" if item.get("multiSelect") else "single")
                if options
                else "text",
                "options": options,
                "allow_custom": True,
                "required": True,
            }
        )
    data = {
        "kind": "question",
        "title": first.get("header") or "DeepSeek question",
        "questions": questions,
        "allow_cancel": True,
    }
    if intent.get("kind") == "plan-review":
        data["presentation"] = "plan"
    details = [item["detail"] for item in native if item.get("detail")]
    if details:
        data["detail"] = "\n\n".join(details)

    def encode(reply):
        if reply == {"cancelled": True}:
            return reply
        if set(reply) != {"answers"} or len(reply["answers"]) != len(questions):
            raise ValueError
        indexed = {answer["question_id"]: answer for answer in reply["answers"]}
        answers = []
        for question in questions:
            answer = indexed[question["id"]]
            ids = answer["option_ids"]
            custom = answer.get("text")
            if (
                set(answer) - {"question_id", "option_ids", "text"}
                or not isinstance(ids, list)
                or len(ids) != len(set(ids))
                or ("text" in answer and not _text(custom))
                or not (ids or custom)
                or (
                    question["type"] != "multi" and len(ids) + (custom is not None) != 1
                )
            ):
                raise ValueError
            labels = {option["id"]: option["label"] for option in question["options"]}
            item = {"id": question["id"], "selected": [labels[key] for key in ids]}
            if custom is not None:
                item["custom"] = custom
            answers.append(item)
        return {"answers": answers}

    return data, encode
