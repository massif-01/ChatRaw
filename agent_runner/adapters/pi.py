"""Pi RPC adapter. Each adapter owns one process and one persistent transcript."""

import asyncio
import base64
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .base import (
    AdapterError,
    AgentAdapter,
    Capabilities,
    Emit,
    InteractionReply,
    ProbeResult,
    RunResult,
    SessionBinding,
    UnsupportedCapability,
)


_EXTENSION = Path(__file__).with_name("pi_extensions") / "chatraw.ts"
_VERSION = "1.5.2"
_IMAGES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
_IMAGE_LIMIT = 8 * 1024 * 1024
_DIALOGS = {"select", "input", "editor", "confirm"}
_ASK = "ChatRaw:questions:"
_APPROVAL = "ChatRaw:tool-approval"
_BRIDGE_COMMAND = "chatraw-bridge-v1"
_THINKING = ["off", "minimal", "low", "medium", "high", "xhigh", "max"]
_RPC_TIMEOUT = 15
_EOF = {"type": "_eof"}
_STOP_TIMEOUT = {"type": "_stop_timeout"}


@dataclass
class _Dialog:
    native_id: str
    method: str
    data: dict
    values: dict = field(default_factory=dict)
    deadline: float | None = None
    timer: asyncio.TimerHandle | None = None


@dataclass
class _Run:
    id: str
    emit: Emit
    records: asyncio.Queue = field(default_factory=asyncio.Queue)
    dialogs: dict[str, _Dialog] = field(default_factory=dict)
    stopping: bool = False
    dispatched: bool = False
    admitted: bool = False
    abort_sent: bool = False
    stop_timer: asyncio.TimerHandle | None = None
    text: str = ""
    stop_reason: str | None = None
    compact_aborted: bool = False


class PiAdapter(AgentAdapter):
    agent_id = "pi"
    settings_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "model": {"type": "string", "minLength": 1},
            "provider": {"type": "string", "minLength": 1},
            "thinking": {"type": "string", "enum": _THINKING},
        },
    }

    def __init__(self):
        self._process: asyncio.subprocess.Process | None = None
        self._reader: asyncio.Task | None = None
        self._responses: dict[str, asyncio.Future] = {}
        self._active: _Run | None = None
        self._binding: SessionBinding | None = None
        self._fenced = False

    def validate_config(self, config: dict) -> dict:
        if set(config) - {
            "executable",
            "session_root",
            "extensions",
            "model",
            "provider",
            "thinking",
        }:
            raise AdapterError("invalid_config", "Unknown Pi configuration field")
        executable = config.get("executable")
        root = config.get("session_root")
        extensions = config.get("extensions", [])
        if (
            not _absolute(executable)
            or not _absolute(root)
            or not isinstance(extensions, list)
            or not all(map(_absolute, extensions))
        ):
            raise AdapterError(
                "invalid_config",
                "Pi requires absolute executable and session_root paths",
            )
        for key in ("model", "provider"):
            if key in config and (not _text(config[key]) or "\0" in config[key]):
                raise AdapterError("invalid_config", f"Invalid Pi {key}")
        if "thinking" in config and config["thinking"] not in _THINKING:
            raise AdapterError("invalid_config", "Invalid Pi thinking level")
        if "provider" in config and "model" not in config:
            raise AdapterError(
                "invalid_config", "Selecting a Pi provider requires a model"
            )
        return {**config, "extensions": list(extensions)}

    @staticmethod
    def _capabilities() -> Capabilities:
        return {
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
                "image_mime_types": sorted(_IMAGES),
                "image_total_bytes": _IMAGE_LIMIT,
            },
        }

    async def probe(self, config: dict) -> ProbeResult:
        checks = dict.fromkeys(
            ("program", "protocol", "authentication", "model_request"), "not_checked"
        )
        result = {
            "availability": "unconfigured",
            "reason": "Pi host configuration is incomplete",
            "version": None,
            "capabilities": self._capabilities(),
            "checks": checks,
        }
        try:
            config = self.validate_config(config)
        except AdapterError:
            return result
        try:
            version = await self._program_version(config)
        except AdapterError:
            checks["program"] = "failed"
            return {
                **result,
                "availability": "unavailable",
                "reason": "Pi version command failed",
            }
        checks["program"] = "passed"
        if version != _VERSION:
            return {
                **result,
                "availability": "unavailable",
                "reason": f"Pi RPC requires tested version {_VERSION}",
            }
        result["version"] = version

        # Probe uses no transcript and loads only the shipped extension.
        probe = PiAdapter()
        try:
            await probe._spawn(
                config, Path(config["session_root"]), None, probe_only=True
            )
            state = await probe._get_state()
            await probe._verify_extension()
            model_list = await probe._rpc("get_available_models")
        except (AdapterError, OSError, ValueError):
            checks["protocol"] = "failed"
            return {
                **result,
                "availability": "unavailable",
                "reason": "Pi RPC handshake failed",
            }
        finally:
            await probe._shutdown()
        checks["protocol"] = "passed"
        models = [
            {key: model[key] for key in ("provider", "id")}
            for model in model_list.get("models", [])
            if isinstance(model, dict)
            and _text(model.get("provider"))
            and _text(model.get("id"))
        ]
        result["models"] = models
        model = state.get("model") or {}
        if {"provider": model.get("provider"), "id": model.get("id")} not in models:
            return {
                **result,
                "reason": "Pi RPC is reachable; no available active model is configured",
            }
        return {
            **result,
            "availability": "ready",
            "reason": "Pi RPC and model configuration are ready; model request unverified",
        }

    async def create_session(
        self, session_id: str, workspace: Path, config: dict
    ) -> SessionBinding:
        config = self.validate_config(config)
        await self._require_version(config)
        root = Path(config["session_root"]).resolve(strict=True)
        directory = root / uuid4().hex
        directory.mkdir(mode=0o700)
        transcript = directory / "session.jsonl"
        # Pi initializes an explicitly supplied, empty session file with its own header.
        transcript.touch(mode=0o600, exist_ok=False)
        try:
            await self._spawn(config, workspace, transcript)
            state = await self._get_state()
            native_id = state["sessionId"]
            binding: SessionBinding = {
                "session_id": session_id,
                "agent_id": "pi",
                "workspace": str(workspace),
                "native": {"session_id": native_id, "transcript": str(transcript)},
            }
            self._verify_state(binding, state)
            self._verify_transcript(binding, root)
            await self._verify_extension()
        except (AdapterError, OSError, ValueError):
            await self._shutdown()
            raise AdapterError(
                "pi_session_create_failed",
                "Pi could not initialize a persistent session",
            ) from None
        self._binding = binding
        return binding

    async def resume_session(
        self, binding: SessionBinding, config: dict
    ) -> SessionBinding:
        if self._active or self._fenced:
            raise AdapterError(
                "pi_session_busy", "Pi session still has an unresolved run"
            )
        config = self.validate_config(config)
        await self._require_version(config)
        await self._shutdown()
        try:
            transcript = self._verify_transcript(
                binding, Path(config["session_root"]).resolve(strict=True)
            )
            await self._spawn(config, Path(binding["workspace"]), transcript)
            self._verify_state(binding, await self._get_state())
            await self._verify_extension()
        except (AdapterError, OSError, ValueError):
            await self._shutdown()
            raise AdapterError(
                "pi_session_missing",
                "Pi could not reopen its original transcript. Check the session store or start a new chat",
            ) from None
        self._binding = binding
        return binding

    @staticmethod
    async def _program_version(config):
        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                config["executable"],
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            output, _ = await asyncio.wait_for(process.communicate(), _RPC_TIMEOUT)
            version = output.decode("utf-8", errors="replace").strip()
            if process.returncode or not version:
                raise OSError
            return version
        except (OSError, TimeoutError, ValueError):
            raise AdapterError(
                "pi_program_failed", "Pi version command failed"
            ) from None
        finally:
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()

    async def _require_version(self, config):
        if await self._program_version(config) != _VERSION:
            raise AdapterError(
                "pi_version", f"Pi RPC requires tested version {_VERSION}"
            )

    @staticmethod
    def _verify_transcript(binding, root):
        native = binding["native"]
        try:
            path = Path(native["transcript"])
            if (
                binding["agent_id"] != "pi"
                or path.resolve(strict=True) != path
                or path.parent.parent != root
                or path.name != "session.jsonl"
            ):
                raise ValueError
            with path.open("rb") as stream:
                header = json.loads(stream.readline(65536))
            if (
                header.get("type") != "session"
                or header.get("id") != native["session_id"]
                or Path(header["cwd"]).resolve() != Path(binding["workspace"]).resolve()
            ):
                raise ValueError
        except (AttributeError, KeyError, TypeError, OSError, ValueError):
            raise AdapterError(
                "pi_transcript_invalid", "Pi transcript identity could not be verified"
            ) from None
        return path

    @staticmethod
    def _verify_state(binding, state):
        native = binding["native"]
        if (
            state["sessionId"] != native["session_id"]
            or state.get("sessionFile") != native["transcript"]
            or state.get("isStreaming")
            or state.get("isCompacting")
            or state.get("pendingMessageCount")
        ):
            raise AdapterError(
                "pi_session_mismatch", "Pi returned an unexpected or busy session"
            )

    async def _spawn(self, config, workspace, transcript, *, probe_only=False):
        argv = [
            config["executable"],
            "--mode",
            "rpc",
            "--no-extensions",
            "--extension",
            str(_EXTENSION),
        ]
        if probe_only:
            argv.extend(
                ("--no-session", "--no-mcp", "--no-skills", "--no-prompt-templates")
            )
        else:
            argv.extend(
                ("--session", str(transcript), "--session-dir", str(transcript.parent))
            )
            for extension in config["extensions"]:
                argv.extend(("--extension", str(extension)))
        for key in ("model", "provider", "thinking"):
            if key in config:
                argv.extend((f"--{key}", config[key]))
        self._process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=workspace,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            limit=32 * 1024 * 1024,
        )
        self._reader = asyncio.create_task(self._read(self._process))

    async def _read(self, process):
        try:
            while line := await process.stdout.readline():
                record = json.loads(line)
                if not isinstance(record, dict):
                    break
                if (
                    record.get("type") == "response"
                    and record.get("id") in self._responses
                ):
                    future = self._responses[record["id"]]
                    if not future.done():
                        future.set_result(record)
                elif self._active:
                    await self._active.records.put(record)
                elif (
                    record.get("type") == "extension_ui_request"
                    and record.get("method") in _DIALOGS
                ):
                    await self._write(
                        {
                            "type": "extension_ui_response",
                            "id": record["id"],
                            "cancelled": True,
                        }
                    )
        except (AdapterError, KeyError, TypeError, ValueError, OSError):
            pass
        finally:
            for future in self._responses.values():
                if not future.done():
                    future.set_result(_EOF)
            if self._active:
                self._active.records.put_nowait(_EOF)

    async def _write(self, record):
        process = self._process
        if process is None or process.returncode is not None:
            raise AdapterError("pi_disconnected", "Pi RPC connection closed")
        try:
            process.stdin.write(json.dumps(record, ensure_ascii=True).encode() + b"\n")
            await asyncio.wait_for(process.stdin.drain(), _RPC_TIMEOUT)
        except (OSError, TimeoutError):
            raise AdapterError("pi_disconnected", "Pi RPC connection closed") from None

    async def _get_state(self):
        data = await self._rpc("get_state")
        if not _text(data.get("sessionId")):
            raise AdapterError(
                "pi_protocol_failed", "Pi returned invalid RPC session state"
            )
        return data

    async def _verify_extension(self):
        data = await self._rpc("get_commands")
        if not any(
            command.get("name") == _BRIDGE_COMMAND
            and command.get("source") == "extension"
            and command.get("sourceInfo", {}).get("path") == str(_EXTENSION)
            for command in data.get("commands", [])
        ):
            raise AdapterError(
                "pi_extension_missing", "Pi did not load the ChatRaw approval extension"
            )

    async def _rpc(self, command):
        key = uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self._responses[key] = future
        try:
            await self._write({"type": command, "id": key})
            response = await asyncio.wait_for(future, _RPC_TIMEOUT)
            data = response.get("data")
            if (
                response.get("command") != command
                or response.get("success") is not True
                or not isinstance(data, dict)
            ):
                raise AdapterError(
                    "pi_protocol_failed", "Pi returned an invalid RPC response"
                )
            return data
        except TimeoutError:
            raise AdapterError(
                "pi_protocol_failed", "Pi RPC did not report session state"
            ) from None
        finally:
            self._responses.pop(key, None)

    async def run(self, binding, request, emit):
        return await self._execute(
            binding,
            request["run_id"],
            emit,
            {"type": "prompt", "message": request["message"]},
            request["attachments"],
        )

    async def compact(self, binding, request, emit):
        return await self._execute(
            binding, request["run_id"], emit, {"type": "compact"}
        )

    async def _execute(self, binding, run_id, emit, command, attachments=()):
        if self._active or self._fenced or self._binding != binding:
            raise AdapterError(
                "pi_session_busy", "Pi session is unavailable for a new run"
            )
        active = self._active = _Run(run_id, emit)
        command_id = uuid4().hex
        command_type = command["type"]
        response = None
        settled = None
        try:
            if attachments:
                try:
                    command["images"] = await asyncio.to_thread(
                        _encode_images, attachments
                    )
                    state = await self._get_state()
                    if "image" not in (state.get("model") or {}).get("input", []):
                        raise UnsupportedCapability("images with the selected Pi model")
                except AdapterError as error:
                    return {
                        "status": "failed",
                        "final_text": "",
                        "error": error.as_data(),
                    }
            if active.stopping:
                return _result("cancelled", "")
            active.dispatched = True
            await self._write({**command, "id": command_id})
            while True:
                record = await active.records.get()
                kind = record.get("type")
                if record in (_EOF, _STOP_TIMEOUT):
                    return self._unknown(active)
                if kind == "response" and record.get("id") == command_id:
                    response = record
                    if record.get("success") is not True:
                        if command_type == "compact" and active.compact_aborted:
                            return _result(
                                "cancelled" if active.stopping else "interrupted",
                                active.text,
                            )
                        return _result("failed", active.text, "Pi rejected the command")
                    if command_type == "compact":
                        return _result("completed", active.text)
                    disposition = record.get("data", {}).get("disposition")
                    if disposition == "handled":
                        self._verify_state(binding, await self._get_state())
                        return _result("completed", active.text)
                    if disposition != "started":
                        return self._unknown(active)
                    active.admitted = True
                elif kind == "agent_settled" and command_type == "prompt":
                    if not isinstance(record.get("aborted"), bool):
                        return self._unknown(active)
                    settled = record
                elif kind == "compaction_start" and command_type == "compact":
                    active.admitted = True
                elif kind == "compaction_end" and record.get("reason") == "manual":
                    active.compact_aborted = record.get("aborted") is True
                else:
                    await self._event(active, record)
                if settled is not None and response is not None:
                    if settled["aborted"]:
                        return _result(
                            "cancelled" if active.stopping else "interrupted",
                            active.text,
                        )
                    if active.stop_reason == "error":
                        return _result(
                            "failed",
                            active.text,
                            "Pi reported a provider or execution error",
                        )
                    if active.stop_reason == "aborted":
                        return _result("interrupted", active.text)
                    return _result("completed", active.text)
                if active.stopping and active.admitted:
                    await self._abort(active)
        except (AdapterError, AttributeError, KeyError, TypeError, ValueError):
            if not active.dispatched:
                raise
            return self._unknown(active)
        finally:
            if active.stop_timer:
                active.stop_timer.cancel()
            self._active = None
            await self._invalidate(active)

    def _unknown(self, active):
        self._fenced = True
        return _result("unknown", active.text, "Pi did not confirm settlement")

    async def _event(self, active, record):
        kind = record.get("type")
        if kind == "extension_ui_request" and record.get("method") in _DIALOGS:
            await self._request_dialog(active, record)
        elif kind == "_dialog_expired":
            key = record["key"]
            if active.dialogs.pop(key, None):
                await self._resolved(active, key, "expired")
        elif (
            kind == "message_start"
            and record.get("message", {}).get("role") == "assistant"
        ):
            active.text = ""
            active.stop_reason = None
        elif kind == "message_update":
            update = record.get("assistantMessageEvent", {})
            delta = update.get("delta")
            if isinstance(delta, str) and update.get("type") in {
                "text_delta",
                "thinking_delta",
            }:
                event_type = (
                    "text_delta"
                    if update["type"] == "text_delta"
                    else "reasoning_delta"
                )
                if event_type == "text_delta":
                    active.text += delta
                await active.emit({"type": event_type, "data": {"text": delta}})
        elif (
            kind == "message_end"
            and (message := record.get("message", {})).get("role") == "assistant"
        ):
            active.stop_reason = message.get("stopReason")
            active.text = "".join(
                block["text"]
                for block in message.get("content", [])
                if block.get("type") == "text"
            )
            usage = message.get("usage", {})
            counts = {
                target: usage[source]
                for source, target in (
                    ("input", "input_tokens"),
                    ("output", "output_tokens"),
                )
                if type(usage.get(source)) is int and usage[source] >= 0
            }
            if "input_tokens" in counts:
                counts["input_tokens"] += sum(
                    usage[key]
                    for key in ("cacheRead", "cacheWrite")
                    if type(usage.get(key)) is int
                )
            if counts:
                await active.emit({"type": "usage", "data": counts})
        elif kind in {
            "tool_execution_start",
            "tool_execution_update",
            "tool_execution_end",
        }:
            event_type = {
                "tool_execution_start": "tool_started",
                "tool_execution_update": "tool_updated",
                "tool_execution_end": "tool_completed",
            }[kind]
            data = {
                "tool_call_id": record["toolCallId"],
                "name": record["toolName"][:128],
            }
            if kind == "tool_execution_end":
                data["status"] = "failed" if record.get("isError") else "completed"
                if type(record.get("durationMs")) in (int, float):
                    data["duration_ms"] = record["durationMs"]
            await active.emit({"type": event_type, "data": data})

    async def _request_dialog(self, active, record):
        native_id = record["id"]
        if active.stopping:
            await self._write(
                {"type": "extension_ui_response", "id": native_id, "cancelled": True}
            )
            return
        if any(dialog.native_id == native_id for dialog in active.dialogs.values()):
            return
        try:
            dialog = _make_dialog(record)
        except (KeyError, TypeError, ValueError):
            await self._write(
                {"type": "extension_ui_response", "id": native_id, "cancelled": True}
            )
            return
        key = uuid4().hex
        timeout = record.get("timeout")
        if type(timeout) in (int, float) and timeout > 0:
            loop = asyncio.get_running_loop()
            dialog.deadline = loop.time() + timeout / 1000
            dialog.data["expires_at"] = datetime.fromtimestamp(
                time.time() + timeout / 1000,
                timezone.utc,
            ).isoformat()
            dialog.timer = loop.call_at(
                dialog.deadline,
                active.records.put_nowait,
                {
                    "type": "_dialog_expired",
                    "key": key,
                },
            )
        active.dialogs[key] = dialog
        try:
            await active.emit(
                {
                    "type": "interaction_requested",
                    "native_key": key,
                    "data": dialog.data,
                }
            )
        except Exception:
            active.dialogs.pop(key, None)
            if dialog.timer:
                dialog.timer.cancel()
            await self._write(
                {"type": "extension_ui_response", "id": native_id, "cancelled": True}
            )

    async def respond(self, binding, interaction_key: str, reply: InteractionReply):
        active = self._active
        if binding != self._binding or not active or active.stopping:
            raise AdapterError(
                "interaction_inactive", "Pi interaction is no longer active"
            )
        dialog = active.dialogs.get(interaction_key)
        if dialog is None or (
            dialog.deadline is not None
            and asyncio.get_running_loop().time() >= dialog.deadline
        ):
            raise AdapterError(
                "interaction_inactive", "Pi interaction is no longer active"
            )
        try:
            native = _dialog_reply(dialog, reply)
        except (KeyError, TypeError, ValueError):
            raise AdapterError(
                "invalid_interaction_reply", "Reply does not match the Pi dialog"
            ) from None
        del active.dialogs[interaction_key]
        if dialog.timer:
            dialog.timer.cancel()
        try:
            await self._write(
                {"type": "extension_ui_response", "id": dialog.native_id, **native}
            )
        except AdapterError:
            await self._resolved(active, interaction_key, "invalidated")
            raise
        await self._resolved(
            active,
            interaction_key,
            "cancelled" if reply == {"cancelled": True} else "answered",
        )

    async def cancel(self, binding, run_id):
        active = self._active
        if (
            binding != self._binding
            or not active
            or active.id != run_id
            or active.stopping
        ):
            return
        active.stopping = True
        active.stop_timer = asyncio.get_running_loop().call_later(
            _RPC_TIMEOUT,
            active.records.put_nowait,
            _STOP_TIMEOUT,
        )
        # Send abort before dismissing dialogs so cancellation cannot resume a tool.
        if active.admitted:
            await self._abort(active)
        for dialog in list(active.dialogs.values()):
            await self._write(
                {
                    "type": "extension_ui_response",
                    "id": dialog.native_id,
                    "cancelled": True,
                }
            )
        await self._invalidate(active)

    async def _abort(self, active):
        if active.abort_sent:
            return
        active.abort_sent = True
        await self._write({"type": "clear_queue", "id": uuid4().hex})
        await self._write({"type": "abort", "id": uuid4().hex})

    @staticmethod
    async def _resolved(active, key, outcome):
        await active.emit(
            {
                "type": "interaction_resolved",
                "native_key": key,
                "data": {"outcome": outcome},
            }
        )

    async def _invalidate(self, active):
        pending, active.dialogs = active.dialogs, {}
        for key, dialog in pending.items():
            if dialog.timer:
                dialog.timer.cancel()
            await self._resolved(active, key, "invalidated")

    async def _shutdown(self):
        process = self._process
        if process is None:
            return
        if process.returncode is None:
            process.stdin.close()
            try:
                await asyncio.wait_for(process.wait(), 5)
            except TimeoutError:
                if process.returncode is None:
                    process.kill()
                await process.wait()
        if self._reader:
            await self._reader
        self._process = self._reader = None

    async def close(self, binding):
        if binding == self._binding and self._active is None:
            await self._shutdown()
            self._binding = None


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _absolute(value):
    return _text(value) and "\0" not in value and Path(value).is_absolute()


def _result(status, text, error=None) -> RunResult:
    result = {"status": status, "final_text": text}
    if error:
        result["error"] = {
            "code": "pi_settlement_unknown" if status == "unknown" else "pi_run_failed",
            "message": error,
            "retryable": False,
        }
    return result


def _encode_images(attachments):
    if sum(item["size"] for item in attachments) > _IMAGE_LIMIT:
        raise AdapterError(
            "attachment_too_large", "Pi supports up to 8 MiB of images per run"
        )
    images = []
    remaining = _IMAGE_LIMIT
    for item in attachments:
        if item["mime_type"] not in _IMAGES:
            raise UnsupportedCapability("Pi attachment format")
        try:
            with item["path"].open("rb") as stream:
                data = stream.read(remaining + 1)
        except OSError:
            raise AdapterError(
                "attachment_unavailable", "Pi attachment could not be read"
            ) from None
        if not data or len(data) != item["size"] or len(data) > remaining:
            raise AdapterError(
                "invalid_attachment", "Pi attachment size changed or is invalid"
            )
        remaining -= len(data)
        images.append(
            {
                "type": "image",
                "mimeType": item["mime_type"],
                "data": base64.b64encode(data).decode(),
            }
        )
    return images


def _make_dialog(record):
    method, title = record["method"], record["title"]
    if not _text(title):
        raise ValueError
    if method == "confirm" and title == _APPROVAL:
        operation = json.loads(record["message"])
        if not isinstance(operation, dict) or set(operation) - {
            "tool",
            "command",
            "paths",
        }:
            raise ValueError
        data = {
            "kind": "approval",
            "title": "Allow Pi tool call?",
            "operation": operation,
            "decisions": [
                {"id": "allow", "label": "Allow once"},
                {"id": "deny", "label": "Deny"},
            ],
            "allow_cancel": True,
        }
        return _Dialog(record["id"], method, data)
    if method == "input" and title.startswith(_ASK):
        data = json.loads(title[len(_ASK) :])
        questions = data["questions"]
        if not _text(data["title"]) or not questions or len(questions) > 8:
            raise ValueError
        for question in questions:
            if question["type"] not in {"single", "multi", "text"} or not _text(
                question["text"]
            ):
                raise ValueError
        return _Dialog(
            record["id"],
            "batch",
            {
                "kind": "question",
                "title": data["title"],
                "questions": questions,
                "allow_cancel": True,
            },
        )

    values = {}
    detail = ""
    if method == "select":
        options = record["options"]
        if not isinstance(options, list) or not options or not all(map(_text, options)):
            raise ValueError
        values = {str(index): label for index, label in enumerate(options, start=1)}
    elif method == "confirm":
        values = {"yes": "Yes", "no": "No"}
        detail = record.get("message", "")
    guidance = record.get({"input": "placeholder", "editor": "prefill"}.get(method))
    question = {
        "id": "answer",
        "text": detail or title,
        "type": "single" if values else "text",
        "allow_custom": not values,
        "required": True,
        "options": [{"id": key, "label": label} for key, label in values.items()],
    }
    return _Dialog(
        record["id"],
        method,
        {
            "kind": "question",
            "title": title,
            "questions": [question],
            "allow_cancel": True,
            **({"detail": guidance} if _text(guidance) else {}),
        },
        values,
    )


def _dialog_reply(dialog, reply):
    if reply == {"cancelled": True}:
        return {"cancelled": True}
    if dialog.data["kind"] == "approval":
        if set(reply) != {"decision_id"} or reply["decision_id"] not in {
            "allow",
            "deny",
        }:
            raise ValueError
        return {"confirmed": reply["decision_id"] == "allow"}
    answers = _checked_answers(dialog.data["questions"], reply)
    if dialog.method == "batch":
        return {"value": json.dumps(answers, ensure_ascii=False)}
    answer = answers[0]
    if dialog.method == "confirm":
        return {"confirmed": answer["option_ids"] == ["yes"]}
    if dialog.method == "select":
        return {"value": dialog.values[answer["option_ids"][0]]}
    return {"value": answer["text"]}


def _checked_answers(questions, reply):
    if set(reply) != {"answers"} or len(reply["answers"]) != len(questions):
        raise ValueError
    answers = {answer["question_id"]: answer for answer in reply["answers"]}
    validated = []
    for question in questions:
        answer = answers[question["id"]]
        selected = answer["option_ids"]
        text = answer.get("text")
        options = {option["id"] for option in question["options"]}
        if (
            set(answer) - {"question_id", "option_ids", "text"}
            or not isinstance(selected, list)
            or len(set(selected)) != len(selected)
            or set(selected) - options
            or (question["type"] != "multi" and len(selected) + ("text" in answer) != 1)
            or ("text" in answer and (not question["allow_custom"] or not _text(text)))
            or (question["required"] and not selected and text is None)
        ):
            raise ValueError
        validated.append(answer)
    return validated
