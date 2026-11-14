"""Hermes canonical gateway client; native cwd, admission and control ownership.

Connects with `hermes gateway attach --json` (no --start/--recover). The shared
gateway is external: close detaches this socket, never kills its process.
Protocol evidence and unsupported surfaces are documented in hermes.md.
"""

import asyncio
import base64
import json
import os
import shutil
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import aiohttp

from .base import AgentAdapter, AdapterError


def capabilities():
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
            "questions": "Canonical clarification prompts; no secret/sudo input UI",
            "workspace": "Gateway and Runner must run on the same host and account",
            "image_mime_types": ["image/png", "image/jpeg", "image/webp", "image/gif"],
            "images_require_model_support": True,
            "max_image_bytes": 5 * 1024 * 1024,
            "max_images": 4,
        },
    }


def unknown(message="Hermes execution state needs verification"):
    return {
        "status": "unknown",
        "final_text": "",
        "error": {
            "code": "hermes_state_unknown",
            "message": message,
            "retryable": False,
        },
    }


class HermesAdapter(AgentAdapter):
    agent_id = "hermes"
    settings_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "model": {"type": "string", "maxLength": 200},
            "provider": {"type": "string", "maxLength": 100},
            "reasoning": {"type": "string", "maxLength": 100},
        },
    }

    def __init__(self):
        self.config = {}
        self.http = None
        self.ws = None
        self.reader = None
        self.pending = {}
        self.events = asyncio.Queue(maxsize=2048)
        self.sequence = 0
        self.description = None
        self.binding = None
        self.active_run = None
        self.admitted = asyncio.Event()
        self.controls = {}
        self.stopping = False
        self.final_text = ""

    def validate_config(self, config):
        if not isinstance(config, dict) or set(config) - {
            "executable",
            "home",
            "model",
            "provider",
            "reasoning",
        }:
            raise AdapterError(
                "hermes_config",
                "Hermes uses its native Gateway account; legacy HTTP settings require explicit migration",
            )
        result = {"executable": "hermes", **config}
        for key, value in result.items():
            if not isinstance(value, str) or "\x00" in value:
                raise AdapterError("hermes_config", f"Invalid Hermes {key}")
        if result.get("home") and not Path(result["home"]).is_absolute():
            raise AdapterError(
                "hermes_config", "Hermes home must be an absolute host path"
            )
        return result

    async def _ticket(self, config):
        executable = shutil.which(config["executable"])
        if executable is None:
            raise AdapterError(
                "hermes_not_installed",
                "Hermes executable is not installed for the Runner account",
            )
        environment = dict(os.environ)
        if config.get("home"):
            environment["HERMES_HOME"] = config["home"]
        process = await asyncio.create_subprocess_exec(
            executable,
            "gateway",
            "attach",
            "--json",
            env=environment,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), 15)
        except BaseException:
            if process.returncode is None:
                process.kill()  # Only this short-lived bootstrap helper is ours.
                await process.wait()
            raise
        if process.returncode != 0:
            raise AdapterError(
                "hermes_gateway_unavailable",
                "Start or authenticate the Hermes Gateway under the Runner account, then check again",
            )
        try:
            ticket = json.loads(stdout)
            parsed = urlparse(ticket["url"])
            if parsed.scheme not in ("ws", "wss") or parsed.hostname not in (
                "127.0.0.1",
                "::1",
                "localhost",
            ):
                raise ValueError()
            if "hermes-gateway-v1" not in ticket["protocols"]:
                raise ValueError()
            return ticket
        except (ValueError, KeyError, TypeError):
            raise AdapterError(
                "hermes_protocol",
                "Hermes did not provide a supported local canonical Gateway connection",
            ) from None

    async def _connect(self, config):
        if self.ws is not None and not self.ws.closed:
            return
        if self.http is not None:
            await self.close(None)
        self.config = self.validate_config(config)
        ticket = await self._ticket(self.config)
        self.http = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=None, connect=10)
        )
        try:
            self.ws = await self.http.ws_connect(
                ticket["url"],
                protocols=ticket["protocols"],
                heartbeat=20,
                max_msg_size=8 * 1024 * 1024,
            )
            self.reader = asyncio.create_task(self._read())
            self.description = await self._rpc("runtime.describe", {})
            contract = self.description.get("session_create", {})
            if "tui" not in contract.get("sources", []) or not {
                "cwd",
                "request_id",
                "source",
            } <= set(contract.get("parameters", [])):
                raise AdapterError(
                    "hermes_protocol",
                    "Hermes Gateway does not support persistent sessions with explicit cwd",
                )
        except BaseException:
            await self.close(None)
            raise

    async def _read(self):
        try:
            async for message in self.ws:
                if message.type != aiohttp.WSMsgType.TEXT:
                    if message.type in (
                        aiohttp.WSMsgType.ERROR,
                        aiohttp.WSMsgType.CLOSE,
                    ):
                        break
                    continue
                frame = json.loads(message.data)
                if "id" in frame and "method" not in frame:
                    future = self.pending.get(str(frame["id"]))
                    if future is not None and not future.done():
                        if "error" in frame:
                            future.set_exception(
                                AdapterError(
                                    "hermes_request_rejected",
                                    "Hermes rejected the native request; check its session and configuration",
                                )
                            )
                        else:
                            future.set_result(frame.get("result"))
                elif frame.get("method") == "event":
                    self.events.put_nowait(frame.get("params", {}))
                elif "id" in frame and "method" in frame:
                    # Canonical approvals are events + generation-fenced methods.
                    # Secret/sudo/desktop callbacks have no public UI in v1.
                    await self.ws.send_json(
                        {
                            "jsonrpc": "2.0",
                            "id": frame["id"],
                            "error": {
                                "code": -32601,
                                "message": "This client does not support that native request",
                            },
                        }
                    )
        except (aiohttp.ClientError, ValueError, asyncio.QueueFull):
            pass
        finally:
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(
                        AdapterError(
                            "hermes_disconnected", "Hermes Gateway connection was lost"
                        )
                    )
            if self.ws is not None and not self.ws.closed:
                await self.ws.close()
            # Wake the consumer; overflow itself invalidates the stream.
            if self.events.full():
                self.events.get_nowait()
            self.events.put_nowait({"type": "_disconnected"})

    async def _rpc(self, method, params, timeout=15):
        if self.ws is None or self.ws.closed:
            raise AdapterError("hermes_disconnected", "Hermes Gateway is not connected")
        self.sequence += 1
        key = str(self.sequence)
        future = asyncio.get_running_loop().create_future()
        self.pending[key] = future
        try:
            await self.ws.send_json(
                {"jsonrpc": "2.0", "id": key, "method": method, "params": params}
            )
            return (
                await asyncio.wait_for(future, timeout)
                if timeout is not None
                else await future
            )
        finally:
            self.pending.pop(key, None)

    async def probe(self, config):
        result = {
            "availability": "unavailable",
            "reason": "",
            "version": None,
            "capabilities": capabilities(),
            "checks": {
                key: "not_checked"
                for key in ("program", "protocol", "authentication", "model_request")
            },
        }
        probe = type(self)()
        try:
            config = self.validate_config(config)
            result["checks"]["program"] = (
                "passed" if shutil.which(config["executable"]) else "failed"
            )
            await probe._connect(config)
            result["availability"] = "ready"
            result["checks"].update(protocol="passed", authentication="unknown")
            result["reason"] = (
                "Gateway authenticated; provider/model request has not been tested"
            )
            models = await probe._rpc("model.options", {"include_unconfigured": False})
            result["models"] = [
                {"id": model, "provider": provider["slug"]}
                for provider in models.get("providers", [])
                if provider.get("authenticated") is True
                for model in provider.get("models", [])
                if isinstance(model, str)
            ]
        except (
            AdapterError,
            OSError,
            asyncio.TimeoutError,
            aiohttp.ClientError,
        ) as error:
            result["reason"] = (
                error.message
                if isinstance(error, AdapterError)
                else "Hermes Gateway is unavailable"
            )
        finally:
            await probe.close(None)
        return result

    async def create_session(self, session_id, workspace, config):
        await self._connect(config)
        params = {"request_id": session_id, "source": "tui", "cwd": str(workspace)}
        params.update(
            {
                key: config[key]
                for key in ("model", "provider", "reasoning")
                if config.get(key)
            }
        )
        supported = self.description["session_create"]["parameters"]
        if set(params) - set(supported):
            raise AdapterError(
                "hermes_protocol",
                "Hermes Gateway does not support the selected session settings",
            )
        snapshot = await self._rpc("session.create", params)
        native_id = snapshot.get("session_id")
        if not isinstance(native_id, str) or snapshot.get("info", {}).get("cwd") != str(
            workspace
        ):
            raise AdapterError(
                "hermes_workspace", "Hermes did not confirm the requested workspace"
            )
        self.binding = {
            "session_id": session_id,
            "agent_id": "hermes",
            "workspace": str(workspace),
            "native": {
                "session_id": native_id,
                "profile_id": self.description["profile_id"],
                "settings": {
                    key: config[key]
                    for key in ("model", "provider", "reasoning")
                    if config.get(key)
                },
            },
        }
        return self.binding

    async def _resume(self, binding, config):
        await self._connect(config)
        if self.description.get("profile_id") != binding["native"].get("profile_id"):
            raise AdapterError(
                "hermes_profile_changed",
                "The configured Hermes profile does not own this session",
            )
        snapshot = await self._rpc(
            "session.resume", {"session_id": binding["native"]["session_id"]}
        )
        if (
            snapshot.get("session_id") != binding["native"]["session_id"]
            or snapshot.get("info", {}).get("cwd") != binding["workspace"]
        ):
            raise AdapterError(
                "hermes_session_changed",
                "Hermes session identity or workspace no longer matches",
            )
        self.binding = binding
        return snapshot

    async def resume_session(self, binding, config):
        snapshot = await self._resume(binding, config)
        if snapshot.get("running") or snapshot.get("pending"):
            raise AdapterError(
                "hermes_session_busy", "Hermes still has active work in this session"
            )
        desired = {
            key: config[key]
            for key in ("model", "provider", "reasoning")
            if config.get(key)
        }
        previous = binding["native"].get("settings", {})
        changes = []
        if any(desired.get(key) != previous.get(key) for key in ("model", "provider")):
            model = desired.get("model")
            if not model and desired.get("provider"):
                defaults = await self._rpc(
                    "model.options", {"include_unconfigured": False}
                )
                model = defaults.get("model")
            payload = {"model": model or "reset"}
            if model and desired.get("provider"):
                payload["provider"] = desired["provider"]
            changes.append(("model", payload))
        if desired.get("reasoning") != previous.get("reasoning"):
            changes.append(("reasoning", {"effort": desired.get("reasoning")}))
        for operation, payload in changes:
            result = await self._rpc(
                "session.mutate",
                {
                    "session_id": binding["native"]["session_id"],
                    "request_id": uuid4().hex,
                    "expected_revision": snapshot["revision"],
                    "expected_generation": snapshot["execution_generation"],
                    "operation": operation,
                    "payload": payload,
                },
            )
            if result.get("status") == "confirmation_required" or result.get("error"):
                raise AdapterError(
                    "hermes_settings_confirmation",
                    "Hermes requires native confirmation for these settings; no new run was submitted",
                )
            snapshot = await self._rpc(
                "session.resume", {"session_id": binding["native"]["session_id"]}
            )
        self.binding = {**binding, "native": {**binding["native"], "settings": desired}}
        return self.binding

    async def _checkpoint(self, emit, **native):
        self.binding = {**self.binding, "native": {**self.binding["native"], **native}}
        await emit({"type": "binding_updated", "data": self.binding})

    def _start(self, binding, run_id, recovering=False):
        self.binding = (
            binding
            if recovering
            else {
                **binding,
                "native": {
                    key: value
                    for key, value in binding["native"].items()
                    if key
                    not in {
                        "run_id",
                        "operation",
                        "admission_id",
                        "execution_generation",
                    }
                },
            }
        )
        self.active_run = run_id
        self.stopping, self.final_text = False, ""
        self.controls.clear()
        self.admitted.clear()
        while not self.events.empty():
            self.events.get_nowait()

    async def run(self, binding, request, emit):
        self._start(binding, request["run_id"])
        await self._checkpoint(emit, run_id=request["run_id"], operation="run")
        text = request["message"]
        # Let Hermes resolve slash directives, including its native Skill logic.
        if text.startswith("/"):
            name, _, arg = text[1:].partition(" ")
            directive = await self._rpc(
                "command.dispatch",
                {
                    "session_id": binding["native"]["session_id"],
                    "name": name,
                    "arg": arg,
                },
            )
            if directive.get("type") in ("exec", "plugin"):
                return {
                    "status": "completed",
                    "final_text": directive.get("output") or "",
                }
            if directive.get("type") in ("send", "skill"):
                text = directive[
                    "message"
                ]  # Native expansion, never ChatRaw Skill injection.
            else:
                return {
                    "status": "failed",
                    "final_text": "",
                    "error": {
                        "code": "hermes_command_ui",
                        "message": "This native command requires an interactive Hermes client",
                        "retryable": False,
                    },
                }
        params = {
            "session_id": binding["native"]["session_id"],
            "input_id": request["run_id"],
            "text": text,
        }
        if request["attachments"]:
            params["attachments"] = []
            for item in request["attachments"]:
                with item["path"].open("rb") as source:
                    content = source.read(5 * 1024 * 1024 + 1)
                if len(content) > 5 * 1024 * 1024:
                    return {
                        "status": "failed",
                        "final_text": "",
                        "error": {
                            "code": "image_too_large",
                            "message": "Hermes image exceeds 5 MiB",
                            "retryable": False,
                        },
                    }
                # Canonical admission accepts images from its own profile cache,
                # not arbitrary Runner-local upload paths.
                uploaded = await self._rpc(
                    "image.attach_bytes",
                    {
                        "session_id": binding["native"]["session_id"],
                        "filename": item["name"],
                        "content_base64": base64.b64encode(content).decode("ascii"),
                    },
                )
                if not uploaded.get("attached") or not isinstance(
                    uploaded.get("path"), str
                ):
                    return {
                        "status": "failed",
                        "final_text": "",
                        "error": {
                            "code": "hermes_image_rejected",
                            "message": "Hermes did not accept the image",
                            "retryable": False,
                        },
                    }
                params["attachments"].append(
                    {"path": uploaded["path"], "mime": uploaded["mime"]}
                )
        result = await self._rpc("prompt.submit", params)
        admission_id = result.get("admission_id")
        if not isinstance(admission_id, str):
            return unknown("Hermes did not return an admission identity")
        await self._checkpoint(
            emit, run_id=request["run_id"], admission_id=admission_id, operation="run"
        )
        self.admitted.set()
        return await self._await_run(emit)

    async def _await_run(self, emit):
        next_poll = 0
        while True:
            if asyncio.get_running_loop().time() >= next_poll:
                try:
                    receipt = await self._rpc(
                        "prompt.receipt",
                        {
                            "session_id": self.binding["native"]["session_id"],
                            "admission_id": self.binding["native"]["admission_id"],
                            "include_result": True,
                        },
                    )
                except (AdapterError, aiohttp.ClientError, asyncio.TimeoutError):
                    return unknown()
                if receipt.get("status") == "unknown":
                    return unknown()
                if receipt.get("status") == "terminal":
                    outcome = receipt.get("outcome")
                    statuses = {
                        "completed": "completed",
                        "cancelled": "cancelled",
                        "interrupted": "interrupted",
                        "failed": "failed",
                    }
                    if outcome not in statuses:
                        return unknown(
                            "Hermes returned an unsupported terminal outcome"
                        )
                    native_result = receipt.get("result")
                    if isinstance(native_result, dict):
                        final = native_result.get(
                            "final_response", native_result.get("text", self.final_text)
                        )
                    elif isinstance(native_result, str):
                        final = native_result
                    else:
                        final = self.final_text
                    result = {
                        "status": (
                            "cancelled"
                            if self.stopping and outcome == "interrupted"
                            else statuses[outcome]
                        ),
                        "final_text": final if isinstance(final, str) else "",
                    }
                    if outcome == "failed":
                        result["error"] = {
                            "code": "hermes_run_failed",
                            "message": "Hermes reported that the run failed",
                            "retryable": False,
                        }
                    native_usage = receipt.get("usage") or {}
                    if isinstance(native_usage, dict):
                        usage = {
                            key: native_usage[key]
                            for key in ("input_tokens", "output_tokens")
                            if type(native_usage.get(key)) is int
                            and native_usage[key] >= 0
                        }
                        if usage:
                            await emit({"type": "usage", "data": usage})
                    return result
                next_poll = asyncio.get_running_loop().time() + 1
            try:
                event = await asyncio.wait_for(
                    self.events.get(),
                    max(0.01, next_poll - asyncio.get_running_loop().time()),
                )
            except asyncio.TimeoutError:
                continue
            if event.get("type") == "_disconnected":
                return unknown(
                    "Hermes connection closed before settlement was confirmed"
                )
            if event.get("session_id") != self.binding["native"]["session_id"]:
                continue
            if event.get("type") == "session.replay_gap":
                return unknown(
                    "Hermes event replay has a gap; native state must be checked"
                )
            if event.get("admission_id") != self.binding["native"]["admission_id"]:
                continue
            await self._event(event, emit)

    async def _event(self, event, emit):
        kind, payload = event.get("type"), event.get("payload", {})
        if kind == "message.delta" and isinstance(payload.get("text"), str):
            self.final_text += payload["text"]
            await emit({"type": "text_delta", "data": {"text": payload["text"]}})
        elif kind in ("reasoning.delta", "thinking.delta") and isinstance(
            payload.get("text"), str
        ):
            await emit({"type": "reasoning_delta", "data": {"text": payload["text"]}})
        elif kind == "message.complete" and isinstance(payload.get("text"), str):
            self.final_text = payload["text"]
        elif kind in ("tool.start", "tool.complete"):
            tool_id = payload.get("tool_id")
            if not isinstance(tool_id, str) or not tool_id:
                return  # A tool name is not a unique native call identity.
            data = {
                "tool_call_id": tool_id,
                "name": str(payload.get("name") or payload.get("tool") or "tool")[:200],
            }
            # Native argument/result previews may contain credentials. Keep
            # tool identity; approval detail is the owner's redacted projection.
            await emit(
                {
                    "type": {
                        "tool.start": "tool_started",
                        "tool.complete": "tool_completed",
                        "tool.generating": "tool_updated",
                    }[kind],
                    "data": data,
                }
            )
            image_path = payload.get("image_path") if kind == "tool.complete" else None
            if (
                isinstance(image_path, str)
                and Path(image_path).is_absolute()
                and Path(image_path).is_relative_to(Path(self.binding["workspace"]))
            ):
                import mimetypes

                await emit(
                    {
                        "type": "artifact",
                        "data": {
                            "path": Path(image_path),
                            "name": Path(image_path).name,
                            "mime_type": mimetypes.guess_type(image_path)[0]
                            or "application/octet-stream",
                        },
                    }
                )
        elif kind in ("approval.request", "clarify.request"):
            await self._interaction(payload, kind, emit)
        elif kind in ("approval.settled", "clarify.settled"):
            for key, control in list(self.controls.items()):
                if control["prompt_id"] == payload.get("prompt_id"):
                    await emit(
                        {
                            "type": "interaction_resolved",
                            "native_key": key,
                            "data": {
                                "outcome": (
                                    "answered" if control.get("sent") else "invalidated"
                                )
                            },
                        }
                    )
                    del self.controls[key]

    async def _interaction(self, payload, kind, emit):
        prompt_id, generation = payload.get("prompt_id"), payload.get(
            "execution_generation"
        )
        if not isinstance(prompt_id, str) or type(generation) is not int:
            raise AdapterError(
                "hermes_interaction",
                "Hermes interaction has no generation-bound identity",
            )
        if any(c["prompt_id"] == prompt_id for c in self.controls.values()):
            return
        key = uuid4().hex
        choices = payload.get("choices") or []
        if not isinstance(choices, list) or not all(
            isinstance(c, str) for c in choices
        ):
            raise AdapterError(
                "hermes_interaction", "Hermes interaction choices are invalid"
            )
        if kind == "approval.request":
            data = {
                "kind": "approval",
                "title": "Hermes approval",
                "detail": payload.get("description") or "",
                "operation": {"command": payload.get("command") or ""},
                "allow_cancel": "deny" in choices,
                "decisions": [
                    {"id": str(i), "label": choice, "scope": choice}
                    for i, choice in enumerate(choices)
                ],
            }
        else:
            data = {
                "kind": "question",
                "title": "Hermes question",
                "allow_cancel": True,
                "questions": [
                    {
                        "id": "answer",
                        "text": payload.get("question") or "Answer Hermes",
                        "type": (
                            "multi"
                            if payload.get("multi_select")
                            else "single" if choices else "text"
                        ),
                        "options": [
                            {"id": str(i), "label": choice}
                            for i, choice in enumerate(choices)
                        ],
                        "allow_custom": True,
                        "required": True,
                    }
                ],
            }
        self.controls[key] = {
            "prompt_id": prompt_id,
            "execution_generation": generation,
            "kind": kind,
            "choices": choices,
            "run_id": self.active_run,
        }
        await emit({"type": "interaction_requested", "native_key": key, "data": data})

    async def respond(self, binding, interaction_key, reply):
        control = self.controls.get(interaction_key)
        if control is None or control["run_id"] != self.active_run or self.stopping:
            raise AdapterError(
                "hermes_interaction_stale", "Hermes interaction is no longer live"
            )
        params = {
            "session_id": binding["native"]["session_id"],
            "prompt_id": control["prompt_id"],
            "execution_generation": control["execution_generation"],
        }
        if control["kind"] == "approval.request":
            choice = (
                "deny"
                if reply.get("cancelled")
                else control["choices"][int(reply["decision_id"])]
            )
            params["choice"] = choice
            method = "approval.respond"
        else:
            if reply.get("cancelled"):
                params["answer"] = ""
            else:
                answer = reply["answers"][0]
                values = [control["choices"][int(i)] for i in answer["option_ids"]]
                if answer.get("text"):
                    values.append(answer["text"])
                params["answer"] = ", ".join(values)
            method = "clarify.respond"
        control["sent"] = True
        result = await self._rpc(method, params)
        if result.get("status") not in ("resolved", "already_resolved"):
            raise AdapterError(
                "hermes_response_unknown",
                "Hermes did not confirm the interaction response",
            )

    async def cancel(self, binding, run_id):
        if self.active_run != run_id:
            raise AdapterError(
                "hermes_run_mismatch", "Hermes native run identity does not match"
            )
        self.stopping = True
        await asyncio.wait_for(self.admitted.wait(), 12)
        if self.binding["native"].get("operation") == "compact":
            await self._rpc(
                "session.interrupt",
                {
                    "session_id": binding["native"]["session_id"],
                    "execution_generation": self.binding["native"][
                        "execution_generation"
                    ],
                },
            )
        else:
            await self._rpc(
                "prompt.cancel",
                {
                    "session_id": binding["native"]["session_id"],
                    "admission_id": self.binding["native"]["admission_id"],
                },
            )

    async def compact(self, binding, request, emit):
        self._start(binding, request["run_id"])
        snapshot = await self._rpc(
            "session.resume", {"session_id": binding["native"]["session_id"]}
        )
        await self._checkpoint(
            emit,
            run_id=request["run_id"],
            operation="compact",
            execution_generation=snapshot["execution_generation"],
        )
        self.admitted.set()
        result = await self._rpc(
            "session.mutate",
            {
                "session_id": binding["native"]["session_id"],
                "request_id": request["run_id"],
                "expected_revision": snapshot["revision"],
                "expected_generation": snapshot["execution_generation"],
                "operation": "compress",
                "payload": {},
            },
            timeout=None,
        )
        if result.get("error"):
            return {
                "status": "failed",
                "final_text": "",
                "error": {
                    "code": "hermes_compaction_failed",
                    "message": "Hermes could not compact this session",
                    "retryable": False,
                },
            }
        if result.get("operation") != "compress" or not (
            type(result.get("revision")) is int
            or result.get("status") in ("noop", "preview")
        ):
            return unknown("Hermes did not confirm compaction settlement")
        return {"status": "completed", "final_text": ""}

    async def recover_run(self, binding, request, config, emit):
        snapshot = await self._resume(binding, config)
        self._start(binding, request["run_id"], recovering=True)
        native = binding["native"]
        if (
            native.get("run_id") != request["run_id"]
            or native.get("operation") != "run"
            or not native.get("admission_id")
        ):
            return unknown("No confirmed Hermes admission is available for recovery")
        self.admitted.set()
        receipt = await self._rpc(
            "prompt.receipt",
            {
                "session_id": native["session_id"],
                "admission_id": native["admission_id"],
                "include_result": True,
            },
        )
        if receipt.get("status") == "started" and receipt.get(
            "execution_generation"
        ) == snapshot.get("execution_generation"):
            for prompt in snapshot.get("prompts", []):
                if (
                    prompt.get("execution_generation")
                    == receipt["execution_generation"]
                ):
                    await self._interaction(prompt, prompt["kind"] + ".request", emit)
        return await self._await_run(emit)

    async def close(self, binding):
        if self.ws is not None:
            await self.ws.close()
        if self.reader is not None and self.reader is not asyncio.current_task():
            self.reader.cancel()
            await asyncio.gather(self.reader, return_exceptions=True)
        if self.http is not None:
            await self.http.close()
        self.ws = self.http = self.reader = None
