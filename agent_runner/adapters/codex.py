"""Codex app-server adapter using an owned, session-local stdio transport."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from .base import (
    AdapterConfig,
    AdapterError,
    AgentAdapter,
    Capabilities,
    CompactRequest,
    Emit,
    InteractionReply,
    ProbeResult,
    RecoveryRequest,
    RunRequest,
    RunResult,
    SessionBinding,
    UnsupportedCapability,
)


_RPC_TIMEOUT = 15
_STOP_RPC_TIMEOUT = 5
_STOP_TIMEOUT = 30
_APPROVAL_TEXT_LIMIT = 100_000  # Runner operation field limit.
_INLINE_CREDENTIAL = re.compile(
    r"(?i)(\b(?:[\w-]*(?:token|secret|password|api[_-]?key)[\w-]*)"
    r'(?:\s*[:=]\s*|\s+)|\bBearer\s+)(?:"[^"]*"|\x27[^\x27]*\x27|[^\s]+)'
)
_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
_TOOL_TYPES = {
    "commandExecution",
    "fileChange",
    "mcpToolCall",
    "dynamicToolCall",
    "collabAgentToolCall",
    "webSearch",
    "imageView",
    "imageGeneration",
    "contextCompaction",
}
_DECISIONS = {
    "accept": ("Allow once", "once"),
    "acceptForSession": ("Allow for this session", "session"),
    "decline": ("Deny", "once"),
    "cancel": ("Cancel", "once"),
}


class _Disconnected(Exception):
    pass


class _Rejected(Exception):
    """An explicit JSON-RPC error, with the native payload discarded."""


class _AppServer:
    def __init__(self, process: asyncio.subprocess.Process):
        self.process = process
        self.events: asyncio.Queue = asyncio.Queue(maxsize=512)
        self.calls: dict[int, asyncio.Future] = {}
        self.next_id = 0
        self.broken = False
        self.reader = asyncio.create_task(self._read())

    @classmethod
    async def open(cls, cwd: Path | None = None) -> _AppServer:
        process = await asyncio.create_subprocess_exec(
            "codex",
            "app-server",
            "--listen",
            "stdio://",
            cwd=cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            limit=16 * 1024 * 1024,
        )
        server = cls(process)
        try:
            await server.call(
                "initialize",
                {
                    "clientInfo": {
                        "name": "chatraw",
                        "title": "ChatRaw",
                        "version": "1",
                    },
                    "capabilities": {"experimentalApi": True},
                },
            )
            await server.send({"method": "initialized", "params": {}})
        except BaseException:
            await server.close()
            raise
        return server

    async def _read(self) -> None:
        try:
            while line := await self.process.stdout.readline():
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError("Invalid JSON-RPC message")
                if "method" in message:
                    # Never block RPC replies behind the notification consumer.
                    # An overrun fences the run instead of dropping its events.
                    self.events.put_nowait(message)
                elif type(message.get("id")) is int:
                    future = self.calls.get(message["id"])
                    if future is not None and not future.done():
                        if "error" in message:
                            future.set_exception(_Rejected())
                        elif isinstance(message.get("result"), dict):
                            future.set_result(message["result"])
                        else:
                            future.set_exception(_Disconnected())
        except (OSError, ValueError, RecursionError, asyncio.QueueFull):
            self.broken = True
            while not self.events.empty():
                self.events.get_nowait()
        finally:
            for future in self.calls.values():
                if not future.done():
                    future.set_exception(_Disconnected())
            if self.events.full():
                # With a full queue there is no safe way to add EOF without
                # losing data, so fence the stream and discard the backlog.
                while not self.events.empty():
                    self.events.get_nowait()
            self.events.put_nowait(None)
        if self.broken:
            while await self.process.stdout.read(65536):
                pass

    async def send(self, message: dict) -> None:
        if self.broken or self.reader.done():
            raise _Disconnected()
        try:
            self.process.stdin.write(
                json.dumps(message, ensure_ascii=False).encode() + b"\n"
            )
            await asyncio.wait_for(self.process.stdin.drain(), _RPC_TIMEOUT)
        except (OSError, TimeoutError) as exc:
            raise _Disconnected() from exc

    async def call(self, method: str, params: dict) -> dict:
        self.next_id += 1
        request_id = self.next_id
        future = asyncio.get_running_loop().create_future()
        self.calls[request_id] = future
        try:
            await self.send({"id": request_id, "method": method, "params": params})
            return await asyncio.wait_for(future, _RPC_TIMEOUT)
        except TimeoutError as exc:
            raise _Disconnected() from exc
        finally:
            self.calls.pop(request_id)
            if future.done() and not future.cancelled():
                future.exception()
            else:
                future.cancel()

    async def close(self) -> None:
        if self.process.returncode is None:
            self.process.stdin.close()
            try:
                await asyncio.wait_for(self.process.wait(), 2)
            except TimeoutError:
                if self.process.returncode is None:
                    self.process.kill()
                await self.process.wait()
        await self.reader


@dataclass
class _Interaction:
    request_id: int | str
    turn_id: str
    decisions: dict[str, str] = field(default_factory=dict)
    questions: dict = field(default_factory=dict)
    deadline: float | None = None
    sent_outcome: str | None = None
    approval_item_id: str | None = None


@dataclass
class _Turn:
    binding: SessionBinding
    run_id: str
    emit: Emit
    server: _AppServer | None = None
    thread_id: str | None = None
    turn_id: str | None = None
    stopping: bool = False
    interrupt_sent: bool = False
    stop_timeout: asyncio.Timeout | None = None
    pending: dict[str, _Interaction] = field(default_factory=dict)
    request_keys: dict[int | str, str] = field(default_factory=dict)
    texts: dict[str, str] = field(default_factory=dict)
    tools: dict[str, dict] = field(default_factory=dict)
    command_items: set[str] = field(default_factory=set)
    yielded_commands: set[str] = field(default_factory=set)
    approval_gates: dict[str, bool] = field(default_factory=dict)


def _preview(text: str) -> str:
    return _INLINE_CREDENTIAL.sub(r"\1[redacted]", text)[:2048]


def _result(status: str, text: str = "") -> RunResult:
    if status in {"completed", "cancelled", "interrupted"}:
        return {"status": status, "final_text": text}
    error = (
        AdapterError("codex_native_failed", "Codex reported that the turn failed.")
        if status == "failed"
        else AdapterError(
            "codex_turn_unverified", "Codex did not confirm how the turn ended."
        )
    )
    return {"status": status, "final_text": text, "error": error.as_data()}


class CodexAdapter(AgentAdapter):
    agent_id = "codex"
    settings_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "title": "Model", "maxLength": 128},
            "reasoning": {
                "type": "string",
                "title": "Reasoning effort",
                "maxLength": 32,
            },
            "mode": {"type": "string", "title": "Mode", "enum": ["default", "plan"]},
        },
        "additionalProperties": False,
    }
    capabilities: Capabilities = {
        "streaming_text": True,
        "tools": True,
        "questions": True,
        "approvals": True,
        "cancel": True,
        "cancel_mode": "native",
        "resume": True,
        "compact": True,
        "images": True,
        "files": False,
        "steer": False,
        "queue": False,
        "limits": {
            "image_mime_types": sorted(_IMAGE_TYPES),
            "questions": "Native request_user_input, typically available in Plan mode. Secret inputs are unavailable.",
            "approvals": "Command, file change and managed network prompts; no permission overlays or policy amendments.",
        },
    }

    def __init__(self):
        self._config: AdapterConfig = {}
        self._active: _Turn | None = None
        self._server: _AppServer | None = None
        self._thread_id: str | None = None
        self._model: str | None = None

    def validate_config(self, config: AdapterConfig) -> AdapterConfig:
        normalized = {}
        for key, value in config.items():
            schema = self.settings_schema["properties"].get(key)
            if schema is None or not isinstance(value, str):
                raise AdapterError("invalid_config", "Invalid Codex settings.")
            if value.strip():
                if len(value) > schema.get("maxLength", 128) or (
                    key == "mode" and value.strip() not in schema["enum"]
                ):
                    raise AdapterError("invalid_config", "Invalid Codex settings.")
                normalized[key] = value.strip()
        return normalized

    async def probe(self, config: AdapterConfig) -> ProbeResult:
        self.validate_config(config)
        result: ProbeResult = {
            "availability": "unavailable",
            "reason": "Codex CLI was not found.",
            "version": None,
            "capabilities": self.capabilities,
            "checks": dict.fromkeys(
                ("program", "protocol", "authentication", "model_request"),
                "not_checked",
            ),
        }
        if shutil.which("codex") is None:
            result["checks"]["program"] = "failed"
            return result
        result["checks"]["program"] = "passed"
        server = None
        try:
            process = await asyncio.create_subprocess_exec(
                "codex",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                output, _ = await asyncio.wait_for(process.communicate(), _RPC_TIMEOUT)
            except TimeoutError:
                process.kill()
                await process.wait()
                raise
            if match := re.fullmatch(rb"codex-cli ([\w.\-+]+)\s*", output):
                result["version"] = match[1].decode()
            server = await _AppServer.open()
            result["checks"]["protocol"] = "passed"
            result.update(
                availability="unknown",
                reason="Codex account state could not be verified.",
            )
            account = await server.call("account/read", {"refreshToken": False})
            if account.get("account"):
                result["checks"]["authentication"] = "unknown"
                result.update(
                    availability="ready",
                    reason="Codex reports a configured account. Model request untested.",
                )
            elif account.get("requiresOpenaiAuth") is True:
                result["checks"]["authentication"] = "failed"
                result.update(
                    availability="unconfigured",
                    reason="Configure Codex authentication for the Runner account.",
                )
            elif account.get("requiresOpenaiAuth") is False:
                result["checks"]["authentication"] = "unknown"
                result.update(
                    availability="ready",
                    reason="Codex provider is configured. Provider authentication and model request untested.",
                )
            try:
                page = await server.call("model/list", {"limit": 100})
                result["models"] = [
                    {
                        "id": row["model"],
                        "label": row.get("displayName") or row["model"],
                        "is_default": row.get("isDefault") is True,
                        "reasoning": [
                            option["reasoningEffort"]
                            for option in row.get("supportedReasoningEfforts", [])
                        ],
                        "input_modalities": row.get("inputModalities", []),
                    }
                    for row in page["data"]
                    if not row.get("hidden")
                ]
            except (_Rejected, _Disconnected, KeyError, TypeError):
                pass
        except (OSError, TimeoutError, _Disconnected, _Rejected):
            if result["checks"]["protocol"] != "passed":
                result["checks"]["protocol"] = "failed"
                result["reason"] = "Codex app-server initialization failed."
        finally:
            if server is not None:
                await server.close()
        return result

    async def create_session(
        self, session_id: str, workspace: Path, config: AdapterConfig
    ) -> SessionBinding:
        self._config = self.validate_config(config)
        return {
            "session_id": session_id,
            "agent_id": self.agent_id,
            "workspace": str(workspace),
            "native": {},
        }

    async def resume_session(
        self, binding: SessionBinding, config: AdapterConfig
    ) -> SessionBinding:
        normalized = self.validate_config(config)
        thread_id = binding["native"].get("thread_id")
        if thread_id and (
            self._server is None
            or self._server.broken
            or self._server.reader.done()
            or self._config != normalized
        ):
            if self._server is not None:
                await self.close(binding)
            try:
                await self._load_thread(binding, normalized)
            except (OSError, _Disconnected, _Rejected, KeyError, TypeError):
                raise AdapterError(
                    "codex_resume_failed",
                    "The saved Codex thread could not be resumed.",
                ) from None
        self._config = normalized
        return binding

    async def _load_thread(self, binding: SessionBinding, config: AdapterConfig) -> str:
        thread_id = binding["native"].get("thread_id")
        if (
            self._server is not None
            and not self._server.broken
            and not self._server.reader.done()
        ):
            if thread_id == self._thread_id or not thread_id:
                return self._thread_id
            raise _Disconnected()
        if self._server is not None:
            await self.close(binding)
        server = await _AppServer.open(Path(binding["workspace"]))
        params = {
            "cwd": binding["workspace"],
            "approvalPolicy": "on-request",
            "approvalsReviewer": "user",
        }
        if config.get("model"):
            params["model"] = config["model"]
        method = "thread/start"
        if thread_id:
            method = "thread/resume"
            params.update(threadId=thread_id, excludeTurns=True)
        try:
            response = await server.call(method, params)
            thread = response["thread"]
            loaded = thread["id"]
            if (
                not isinstance(loaded, str)
                or not loaded
                or (thread_id and loaded != thread_id)
            ):
                raise _Disconnected()
        except BaseException:
            await server.close()
            raise
        self._server, self._thread_id = server, loaded
        self._model = response.get("model")
        return loaded

    async def run(
        self, binding: SessionBinding, request: RunRequest, emit: Emit
    ) -> RunResult:
        if request["message"].strip() == "/compact" and not request["attachments"]:
            return await self.compact(binding, {"run_id": request["run_id"]}, emit)
        content = []
        if request["message"]:
            content.append(
                {"type": "text", "text": request["message"], "text_elements": []}
            )
        for attachment in request["attachments"]:
            if attachment["mime_type"] not in _IMAGE_TYPES:
                error = UnsupportedCapability(
                    "Codex accepts PNG, JPEG, WebP and GIF attachments"
                )
                return {"status": "failed", "final_text": "", "error": error.as_data()}
            content.append({"type": "localImage", "path": str(attachment["path"])})
        params = {"input": content}
        if self._config.get("reasoning"):
            params["effort"] = self._config["reasoning"]
        return await self._execute(
            binding, request["run_id"], emit, "turn/start", params
        )

    async def compact(
        self, binding: SessionBinding, request: CompactRequest, emit: Emit
    ) -> RunResult:
        if not binding["native"].get("thread_id"):
            error = AdapterError(
                "no_native_history", "Start a Codex turn before compacting."
            )
            return {"status": "failed", "final_text": "", "error": error.as_data()}
        return await self._execute(
            binding, request["run_id"], emit, "thread/compact/start", {}
        )

    async def _execute(
        self,
        binding: SessionBinding,
        run_id: str,
        emit: Emit,
        method: str,
        params: dict,
    ) -> RunResult:
        turn = _Turn(binding, run_id, emit)
        self._active = turn
        dispatched = False
        try:
            thread_id = await self._load_thread(binding, self._config)
            turn.server = self._server
            turn.thread_id = thread_id
            if thread_id != binding["native"].get("thread_id"):
                await emit(
                    {
                        "type": "binding_updated",
                        "data": {
                            **binding,
                            "native": {"thread_id": thread_id},
                        },
                    }
                )
            if turn.stopping:
                return _result("cancelled")
            if method == "turn/start" and self._config.get("mode"):
                if not self._model:
                    error = AdapterError(
                        "codex_mode_unavailable",
                        "Codex did not report a model for the requested mode.",
                    )
                    return {
                        "status": "failed",
                        "final_text": "",
                        "error": error.as_data(),
                    }
                params["collaborationMode"] = {
                    "mode": self._config["mode"],
                    "settings": {
                        "model": self._model,
                        "reasoning_effort": params.get("effort"),
                        "developer_instructions": None,
                    },
                }
            dispatched = True
            response = await turn.server.call(method, {"threadId": thread_id, **params})
            async with asyncio.timeout(None) as timeout:
                turn.stop_timeout = timeout
                if method == "turn/start":
                    await self._set_turn(turn, response["turn"]["id"])
                elif turn.stopping:
                    timeout.reschedule(
                        asyncio.get_running_loop().time() + _STOP_TIMEOUT
                    )
                while True:
                    message = await self._next_event(turn, emit)
                    if message is None:
                        raise _Disconnected()
                    result = await self._event(
                        turn, message, emit, compact=method != "turn/start"
                    )
                    if result is not None:
                        return result
        except _Rejected:
            return _result("failed", "".join(turn.texts.values()))
        except (OSError, _Disconnected, TimeoutError, KeyError, TypeError, ValueError):
            return _result(
                "unknown" if dispatched else "failed", "".join(turn.texts.values())
            )
        finally:
            turn.stop_timeout = None
            self._active = None

    async def _next_event(self, turn: _Turn, emit: Emit) -> dict | None:
        while True:
            deadlines = [
                (pending.deadline, key)
                for key, pending in turn.pending.items()
                if pending.deadline is not None and pending.sent_outcome is None
            ]
            if not deadlines:
                return await turn.server.events.get()
            deadline, key = min(deadlines)
            delay = deadline - asyncio.get_running_loop().time()
            if delay > 0:
                try:
                    return await asyncio.wait_for(turn.server.events.get(), delay)
                except TimeoutError:
                    pass
            pending = turn.pending.get(key)
            if pending is not None and pending.sent_outcome is None:
                del turn.pending[key]
                await turn.server.send(
                    {"id": pending.request_id, "result": {"answers": {}}}
                )
                await emit(
                    {
                        "type": "interaction_resolved",
                        "native_key": key,
                        "data": {"outcome": "expired"},
                    }
                )

    async def _set_turn(self, turn: _Turn, turn_id: str) -> None:
        if not isinstance(turn_id, str) or not turn_id:
            raise _Disconnected()
        turn.turn_id = turn_id
        await self._checkpoint_turn(turn)
        if turn.stopping:
            await self._interrupt(turn)

    @staticmethod
    async def _checkpoint_turn(turn: _Turn) -> None:
        native = {
            "thread_id": turn.thread_id,
            "turn_id": turn.turn_id,
            "run_id": turn.run_id,
        }
        if turn.stopping:
            native["stop_requested"] = True
        await turn.emit(
            {
                "type": "binding_updated",
                "data": {**turn.binding, "native": native},
            }
        )

    async def _event(
        self, turn: _Turn, message: dict, emit: Emit, *, compact: bool
    ) -> RunResult | None:
        method, params = message["method"], message.get("params", {})
        request_id = message.get("id")
        if params.get("threadId") != self._thread_id:
            if request_id is not None:
                await self._reject_request(turn.server, request_id)
            return None
        if method == "serverRequest/resolved":
            key = turn.request_keys.get(params.get("requestId"))
            pending = turn.pending.pop(key, None)
            if pending is not None:
                outcome = pending.sent_outcome or (
                    "expired"
                    if pending.deadline is not None
                    and asyncio.get_running_loop().time() >= pending.deadline
                    else "invalidated"
                )
                await emit(
                    {
                        "type": "interaction_resolved",
                        "native_key": key,
                        "data": {"outcome": outcome},
                    }
                )
            return None
        turn_id = params.get("turnId")
        if method in {"turn/started", "turn/completed"}:
            turn_id = params["turn"]["id"]
        if compact and turn.turn_id is None and method == "turn/started":
            await self._set_turn(turn, turn_id)
        if turn.turn_id is None or turn_id != turn.turn_id:
            if request_id is not None:
                await self._reject_request(turn.server, request_id)
            return None
        if request_id is not None:
            await self._request(turn, request_id, method, params, emit)
        elif method == "turn/completed":
            status = params["turn"]["status"]
            if status in {"completed", "failed", "interrupted"}:
                for item in params["turn"].get("items", []):
                    if item["type"] in {"agentMessage", "plan"}:
                        turn.texts[item["id"]] = item["text"]
                text = "".join(turn.texts.values())
                if turn.stopping or status == "interrupted":
                    if not await self._confirm_tool_stop(turn):
                        error = AdapterError(
                            "codex_tool_stop_unverified",
                            "Codex ended the turn, but an owned tool could not be confirmed stopped.",
                        )
                        return {
                            "status": "unknown",
                            "final_text": text,
                            "error": error.as_data(),
                        }
                    if status == "interrupted" and turn.stopping:
                        status = "cancelled"
                return _result(status, text)
        elif method in {"item/agentMessage/delta", "item/plan/delta"}:
            item_id, delta = params["itemId"], params["delta"]
            turn.texts[item_id] = turn.texts.get(item_id, "") + delta
            await emit(
                {"type": "text_delta", "data": {"text": delta, "message_id": item_id}}
            )
        elif method == "item/reasoning/summaryTextDelta":
            await emit(
                {
                    "type": "reasoning_delta",
                    "data": {
                        "text": params["delta"],
                        "message_id": params["itemId"],
                    },
                }
            )
        elif method in {"item/started", "item/completed"}:
            await self._item(turn, method, params["item"], emit)
        return None

    async def _item(self, turn: _Turn, method: str, item: dict, emit: Emit) -> None:
        kind, item_id = item["type"], item["id"]
        completed = method == "item/completed"
        if kind in {"agentMessage", "plan"} and completed:
            text = item["text"]
            previous = turn.texts.get(item_id, "")
            turn.texts[item_id] = text
            if text.startswith(previous) and len(text) > len(previous):
                await emit(
                    {
                        "type": "text_delta",
                        "data": {
                            "text": text[len(previous) :],
                            "message_id": item_id,
                        },
                    }
                )
        elif kind in _TOOL_TYPES:
            turn.tools[item_id] = item
            if kind == "commandExecution":
                turn.command_items.add(item_id)
                if completed:
                    if item.get("processId") and item.get("exitCode") is None:
                        turn.yielded_commands.add(item_id)
                    else:
                        turn.yielded_commands.discard(item_id)
            data = {
                "tool_call_id": item_id,
                "name": str(item.get("tool") or kind)[:128],
            }
            if isinstance(item.get("status"), str):
                data["status"] = item["status"]
            if type(item.get("durationMs")) is int:
                data["duration_ms"] = item["durationMs"]
            await emit(
                {
                    "type": "tool_completed" if completed else "tool_started",
                    "data": data,
                }
            )
            if completed:
                turn.tools.pop(item_id, None)

    @staticmethod
    async def _reject_request(
        server: _AppServer,
        request_id: int | str,
        message: str = "This request is unavailable in ChatRaw.",
    ) -> None:
        await server.send(
            {
                "id": request_id,
                "error": {
                    "code": -32602,
                    "message": message,
                },
            }
        )

    async def _request(
        self, turn: _Turn, request_id: int | str, method: str, params: dict, emit: Emit
    ) -> None:
        if type(request_id) not in {str, int}:
            raise _Disconnected()
        if request_id in turn.request_keys:
            return
        approval_item_id = None
        # Only the initial approval can prove that a command has not started.
        # Stdin, subcommand and network prompts can belong to running tools.
        if method == "item/fileChange/requestApproval" or (
            method == "item/commandExecution/requestApproval"
            and params.get("kind", "command") == "command"
            and params.get("approvalId") is None
            and not params.get("networkApprovalContext")
        ):
            approval_item_id = params["itemId"]
            turn.approval_gates.setdefault(approval_item_id, False)
        if turn.stopping:
            await self._reject_request(turn.server, request_id)
            return
        pending = _Interaction(
            request_id, turn.turn_id, approval_item_id=approval_item_id
        )
        if method == "item/tool/requestUserInput":
            data = self._question(params, pending)
            delay = params.get("autoResolutionMs")
            if (
                type(delay) is int
                and delay >= 0
                and params.get("isBlocking") is not True
            ):
                pending.deadline = asyncio.get_running_loop().time() + delay / 1000
                data["expires_at"] = (
                    datetime.now(UTC) + timedelta(milliseconds=delay)
                ).isoformat()
        elif method in {
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
        }:
            try:
                data = self._approval(turn, method, params, pending)
            except AdapterError as error:
                await self._reject_request(turn.server, request_id, error.message)
                await emit({"type": "error", "data": error.as_data()})
                return
        else:
            await self._reject_request(turn.server, request_id)
            return
        if not data:
            await self._reject_request(turn.server, request_id)
            return
        key = uuid4().hex
        turn.request_keys[request_id] = key
        turn.pending[key] = pending
        try:
            await emit(
                {"type": "interaction_requested", "native_key": key, "data": data}
            )
        except Exception:
            # Runner can fence a request while its native delivery is in flight.
            # Decline that callback and keep reading for terminal evidence.
            turn.pending.pop(key, None)
            await self._reject_request(turn.server, request_id)

    @staticmethod
    def _question(params: dict, pending: _Interaction) -> dict | None:
        questions = []
        for question in params["questions"]:
            qid = question["id"]
            if question.get("isSecret") or qid in pending.questions:
                return None
            options = [
                {
                    "id": str(index),
                    "label": option["label"],
                    "description": option["description"],
                }
                for index, option in enumerate(question.get("options") or [])
            ]
            data = {
                "id": qid,
                "text": question["question"],
                "type": "single" if options else "text",
                "options": options,
                "allow_custom": not options or question.get("isOther") is True,
                "required": True,
            }
            questions.append(data)
            pending.questions[qid] = data
        if not questions:
            return None
        return {
            "kind": "question",
            "title": "Codex needs input",
            "questions": questions,
            "allow_cancel": True,
        }

    @staticmethod
    def _approval(
        turn: _Turn, method: str, params: dict, pending: _Interaction
    ) -> dict | None:
        file_change = method.startswith("item/fileChange/")
        network = params.get("networkApprovalContext")
        extra_permissions = params.get("additionalPermissions") or {}
        if any(value is not None for value in extra_permissions.values()):
            return None
        operation = {"tool": "fileChange" if file_change else "commandExecution"}
        if network:
            operation = {
                "tool": f"network ({network['protocol']})",
                "host_label": network["host"],
            }
        elif file_change:
            item = turn.tools.get(params["itemId"], {})
            operation["paths"] = [change["path"] for change in item.get("changes", [])]
            if params.get("grantRoot"):
                operation["paths"].append(params["grantRoot"])
            if (
                not operation["paths"]
                or len(operation["paths"]) > 200
                or any(len(path) > 4000 for path in operation["paths"])
            ):
                raise AdapterError(
                    "approval_unreviewable",
                    "Codex file approval denied because its paths cannot be shown in full.",
                )
        else:
            command = params.get("command")
            if (
                params.get("kind", "command") != "command"
                or not isinstance(command, str)
                or not command.strip()
                or len(command) > _APPROVAL_TEXT_LIMIT
                or _INLINE_CREDENTIAL.search(command)
            ):
                raise AdapterError(
                    "approval_unreviewable",
                    "Codex command approval denied because the command cannot be shown in full.",
                )
            operation["command"] = command
        if params.get("cwd"):
            operation["cwd_label"] = str(params["cwd"])
        native = params.get("availableDecisions")
        if native is None:
            native = ["accept", "decline", "cancel"]
        decisions = []
        for value in native:
            if isinstance(value, str) and value in _DECISIONS:
                label, scope = _DECISIONS[value]
                pending.decisions[value] = value
                decisions.append({"id": value, "label": label, "scope": scope})
        if not decisions:
            return None
        data = {
            "kind": "approval",
            "title": "Codex requests approval",
            "operation": operation,
            "decisions": decisions,
            "allow_cancel": "cancel" in pending.decisions,
        }
        if params.get("reason"):
            data["detail"] = _preview(params["reason"])
        return data

    async def respond(
        self, binding: SessionBinding, interaction_key: str, reply: InteractionReply
    ) -> None:
        turn = self._active
        pending = turn.pending.get(interaction_key) if turn else None
        if (
            turn is None
            or pending is None
            or pending.sent_outcome is not None
            or turn.stopping
            or pending.turn_id != turn.turn_id
            or binding["session_id"] != turn.binding["session_id"]
            or (
                pending.deadline is not None
                and asyncio.get_running_loop().time() >= pending.deadline
            )
        ):
            raise AdapterError(
                "interaction_inactive", "This Codex request is no longer active."
            )
        if pending.questions:
            result = {"answers": self._answers(pending.questions, reply)}
        else:
            decision = "cancel" if reply.get("cancelled") else reply.get("decision_id")
            if decision not in pending.decisions:
                raise AdapterError(
                    "invalid_reply", "Choose an available Codex decision."
                )
            result = {"decision": pending.decisions[decision]}
            if pending.approval_item_id is not None and decision in {
                "accept",
                "acceptForSession",
            }:
                turn.approval_gates[pending.approval_item_id] = True
        pending.sent_outcome = "cancelled" if reply.get("cancelled") else "answered"
        try:
            await turn.server.send({"id": pending.request_id, "result": result})
        except _Disconnected:
            raise AdapterError(
                "interaction_delivery_unknown",
                "Codex response delivery could not be confirmed.",
            ) from None

    @staticmethod
    def _answers(questions: dict, reply: InteractionReply) -> dict:
        if reply.get("cancelled"):
            return {}
        result = {}
        for answer in reply.get("answers", []):
            qid = answer["question_id"]
            question = questions.get(qid)
            selected, custom = answer["option_ids"], answer.get("text", "")
            choices = (
                {option["id"]: option["label"] for option in question["options"]}
                if question
                else {}
            )
            if (
                question is None
                or qid in result
                or len(selected) > 1
                or any(choice not in choices for choice in selected)
                or bool(selected) == bool(custom.strip())
                or (custom and not question["allow_custom"])
            ):
                raise AdapterError(
                    "invalid_reply",
                    "Answer each Codex question using its available options.",
                )
            result[qid] = {"answers": [choices[selected[0]] if selected else custom]}
        if result.keys() != questions.keys():
            raise AdapterError(
                "invalid_reply", "Answer each Codex question before submitting."
            )
        return result

    async def cancel(self, binding: SessionBinding, run_id: str) -> None:
        turn = self._active
        if (
            turn is None
            or turn.run_id != run_id
            or turn.stopping
            or binding["session_id"] != turn.binding["session_id"]
        ):
            return
        turn.stopping = True
        turn.pending.clear()
        if turn.turn_id is not None and turn.stop_timeout is not None:
            await self._interrupt(turn)

    async def _interrupt(self, turn: _Turn) -> None:
        if turn.interrupt_sent:
            return
        turn.interrupt_sent = True
        turn.stop_timeout.reschedule(asyncio.get_running_loop().time() + _STOP_TIMEOUT)
        try:
            # Recovery on a new transport cannot inspect this server's tools.
            await self._checkpoint_turn(turn)
        finally:
            try:
                await asyncio.wait_for(
                    turn.server.call(
                        "turn/interrupt",
                        {"threadId": turn.thread_id, "turnId": turn.turn_id},
                    ),
                    _STOP_RPC_TIMEOUT,
                )
            except (_Disconnected, _Rejected, TimeoutError):
                # The terminal notification may have raced the interrupt response.
                pass

    @staticmethod
    async def _owned_background(turn: _Turn) -> dict[str, str]:
        params = {"threadId": turn.thread_id}
        processes = {}
        while True:
            page = await turn.server.call("thread/backgroundTerminals/list", params)
            for row in page["data"]:
                if row["itemId"] in turn.command_items:
                    processes[row["processId"]] = row["itemId"]
            if not (cursor := page.get("nextCursor")):
                return processes
            params["cursor"] = cursor

    async def _confirm_tool_stop(self, turn: _Turn) -> bool:
        gated = {item for item, approved in turn.approval_gates.items() if not approved}
        unsettled = (turn.tools.keys() | turn.yielded_commands) - gated
        if not (turn.command_items - gated):
            return not unsettled

        try:
            async with asyncio.timeout(_STOP_RPC_TIMEOUT):
                terminated = set()
                for attempt in range(3):
                    owned = await self._owned_background(turn)
                    if not owned and not unsettled:
                        return True
                    for process_id, item_id in owned.items():
                        if process_id in terminated:
                            continue
                        reply = await turn.server.call(
                            "thread/backgroundTerminals/terminate",
                            {"threadId": turn.thread_id, "processId": process_id},
                        )
                        if reply.get("terminated") is not True:
                            return False
                        terminated.add(process_id)
                        unsettled.discard(item_id)
                    if not owned and attempt < 2:
                        # An exec session can become visible just after the turn ends.
                        await asyncio.sleep(0.1)
        except (_Disconnected, _Rejected, TimeoutError, KeyError, TypeError):
            pass
        return False

    async def recover_run(
        self,
        binding: SessionBinding,
        request: RecoveryRequest,
        config: AdapterConfig,
        emit: Emit,
    ) -> RunResult:
        self.validate_config(config)
        native = binding["native"]
        if (
            native.get("run_id") != request["run_id"]
            or not native.get("turn_id")
            or native.get("stop_requested")
        ):
            return await super().recover_run(binding, request, config, emit)
        server = None
        try:
            server = await _AppServer.open(Path(binding["workspace"]))
            page = await server.call(
                "thread/turns/list",
                {
                    "threadId": native["thread_id"],
                    "limit": 1,
                    "itemsView": "full",
                },
            )
            latest = next(iter(page["data"]), None)
            if (
                latest
                and latest["id"] == native["turn_id"]
                and latest["status"] in {"completed", "failed"}
            ):
                return _result(
                    latest["status"],
                    "".join(
                        item["text"]
                        for item in latest["items"]
                        if item["type"] in {"agentMessage", "plan"}
                    ),
                )
        except (OSError, _Disconnected, _Rejected, KeyError, TypeError):
            pass
        finally:
            if server is not None:
                await server.close()
        return await super().recover_run(binding, request, config, emit)

    async def close(self, binding: SessionBinding) -> None:
        server, self._server = self._server, None
        self._thread_id = None
        self._model = None
        if server is not None:
            await server.close()
