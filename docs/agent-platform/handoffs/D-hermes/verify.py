"""Exercise ChatRaw's Hermes adapter against the official Gateway on loopback."""

import argparse
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from uuid import uuid4


MODEL = "chatraw-loopback"
SEED = "CHATRAW_HERMES_SEED"
RESUME = "CHATRAW_HERMES_RESUME"
HOLD = "CHATRAW_HERMES_HOLD"
IMAGE = "CHATRAW_HERMES_IMAGE"
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
)


class LoopbackModel(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        if self.path != "/v1/models":
            self.send_error(404)
            return
        data = json.dumps(
            {"object": "list", "data": [{"id": MODEL, "object": "model"}]}
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data.encode())

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        inputs = [
            item["content"] for item in body["messages"] if item["role"] == "user"
        ]
        last_input = inputs[-1] if inputs else None
        if isinstance(last_input, list) and any(
            IMAGE in part.get("text", "")
            for part in last_input
            if part["type"] == "text"
        ):
            self.server.image_urls.extend(
                part["image_url"]["url"]
                for part in last_input
                if part["type"] == "image_url"
            )
        is_history = SEED in inputs[:-1]
        self.server.requests.append((last_input, is_history, bool(body.get("stream"))))
        text = (
            "history kept"
            if last_input == RESUME and is_history
            else "history missing"
            if last_input == RESUME
            else "gateway fixture response"
        )
        response = {"id": "loopback", "created": 1, "model": MODEL}
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/event-stream" if body.get("stream") else "application/json",
        )
        self.end_headers()
        try:
            if body.get("stream"):
                response["object"] = "chat.completion.chunk"
                self.chunk(response, {"role": "assistant", "content": text[:8]})
                if last_input == HOLD:
                    self.server.holding.set()
                    self.server.release.wait(timeout=45)
                else:
                    # Keep the receipt nonterminal long enough to observe a native delta.
                    threading.Event().wait(0.2)
                self.chunk(response, {"content": text[8:]})
                self.chunk(response, {}, "stop")
                self.wfile.write(b"data: [DONE]\n\n")
            else:
                if last_input == HOLD:
                    self.server.holding.set()
                    self.server.release.wait(timeout=45)
                response["object"] = "chat.completion"
                response["choices"] = [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": text},
                        "finish_reason": "stop",
                    }
                ]
                self.wfile.write(json.dumps(response).encode())
        except (BrokenPipeError, ConnectionResetError):
            pass

    def chunk(self, response, delta, finish=None):
        data = {
            **response,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        }
        self.wfile.write(("data: " + json.dumps(data) + "\n\n").encode())
        self.wfile.flush()


def record(stage, **data):
    print(json.dumps({"stage": stage, **data}), flush=True)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


async def verify_image(adapter, binding, root, home, server, wire):
    upload_dir = root / "runner-uploads"
    upload_dir.mkdir()
    image = upload_dir / "one-pixel.png"
    image.write_bytes(PNG)
    events = []

    async def emit(event):
        events.append(event)

    result = await asyncio.wait_for(
        adapter.run(
            binding,
            {
                "run_id": uuid4().hex,
                "message": IMAGE,
                "attachments": [
                    {
                        "attachment_id": uuid4().hex,
                        "path": image,
                        "name": image.name,
                        "mime_type": "image/png",
                        "size": len(PNG),
                    }
                ],
            },
            emit,
        ),
        35,
    )
    require(result["status"] == "completed", f"Image turn did not settle: {result}")
    require(
        [stage for stage, _ in wire]
        == ["attach_request", "attach_reply", "prompt_submit"],
        "Expected a native upload and reply before submitting the prompt",
    )
    uploaded, submitted = wire[1][1], wire[2][1]
    require(
        uploaded.get("attached") is True, "Gateway did not acknowledge image staging"
    )
    cache = Path(uploaded["path"])
    require(
        cache.parent.resolve() == (home / "cache" / "images").resolve(),
        "Gateway did not return its profile image cache path",
    )
    require(
        cache != image and cache.read_bytes() == PNG,
        "Native cache bytes differ from the Runner upload",
    )
    require(
        submitted == [{"path": str(cache), "mime": "image/png"}]
        and uploaded["mime"] == "image/png",
        "Prompt did not reference exactly the native path and MIME",
    )
    require(wire[0][1] == PNG, "Adapter uploaded different bytes")
    require(
        any(
            event["type"] == "binding_updated"
            and event["data"]["native"].get("admission_id")
            for event in events
        ),
        "Image prompt admission was not checkpointed",
    )
    record(
        "image_admitted",
        status=result["status"],
        bytes=len(PNG),
        sha256=hashlib.sha256(PNG).hexdigest(),
        native_upload=True,
        profile_cache_verified=True,
        native_reference_submitted=True,
        admission_checkpointed=True,
    )
    expected_url = "data:image/png;base64," + base64.b64encode(PNG).decode("ascii")
    require(
        server.image_urls == [expected_url],
        f"Model requests={len(server.requests)}, image parts={len(server.image_urls)}, "
        f"matching parts={server.image_urls.count(expected_url)}",
    )
    record(
        "image_model",
        model_image_part="image_url",
        model_bytes_matched=True,
    )


async def verify(adapter_class, executable, root, server, image_only, wire):
    home = root / "state"
    user = root / "user"
    workspace = root / "project"
    for directory in (home, user, workspace):
        directory.mkdir(mode=0o700)
    endpoint = f"http://127.0.0.1:{server.server_port}/v1"
    (home / "config.yaml").write_text(
        json.dumps(
            {
                "model": {
                    "provider": "custom",
                    "default": MODEL,
                    "base_url": endpoint,
                    **({"supports_vision": True} if image_only else {}),
                },
                **({"agent": {"image_input_mode": "native"}} if image_only else {}),
                "auxiliary": {"title_generation": {"enabled": False}},
                "platform_toolsets": {"cli": [], "tui": []},
                "plugins": {"auto_update_check_hours": 0},
            }
        ),
        encoding="utf-8",
    )

    # Clear provider credentials and isolate both the profile and host rendezvous.
    env = {
        key: os.environ[key]
        for key in ("PATH", "LANG", "LC_ALL", "TZ")
        if key in os.environ
    }
    env.update(
        HOME=str(user),
        USERPROFILE=str(user),
        HERMES_HOME=str(home),
        HERMES_GATEWAY_LOCK_DIR=str(root / "locks"),
        XDG_CACHE_HOME=str(root / "cache"),
        XDG_CONFIG_HOME=str(root / "config"),
        XDG_STATE_HOME=str(root / "xdg-state"),
        TMPDIR=str(root),
        OPENAI_API_KEY="loopback-only",
        OPENAI_BASE_URL=endpoint,
        PYTHONUNBUFFERED="1",
        NO_COLOR="1",
    )
    os.environ.clear()
    os.environ.update(env)
    config = {"executable": str(executable), "home": str(home)}

    initial = await adapter_class().probe(config)
    require(
        initial["availability"] == "unavailable",
        "A Gateway was already discoverable before launch",
    )
    record(
        "before_start", availability=initial["availability"], checks=initial["checks"]
    )

    first, second = adapter_class(), adapter_class()
    tasks = []
    with (root / "gateway.log").open("wb") as log:
        process = await asyncio.create_subprocess_exec(
            str(executable),
            "gateway",
            "run",
            cwd=root,
            env=env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
        try:
            async with asyncio.timeout(45):
                while process.returncode is None:
                    probe = await adapter_class().probe(config)
                    if probe["availability"] == "ready":
                        break
                    await asyncio.sleep(0.5)
                else:
                    raise RuntimeError(
                        f"Gateway exited during startup ({process.returncode})"
                    )
            require(
                probe["checks"]["protocol"] == "passed",
                "Protocol handshake not confirmed",
            )
            record("attach", checks=probe["checks"])

            binding = await first.create_session(uuid4().hex, workspace, config)
            native_id = binding["native"]["session_id"]
            require(
                first.ws.protocol == "hermes-gateway-v1",
                "Unexpected WebSocket subprotocol",
            )
            require(
                binding["workspace"] == str(workspace),
                "Workspace differs from the native acknowledgement",
            )
            record("create", protocol=first.ws.protocol, cwd_confirmed=True)
            if image_only:
                capabilities = probe["capabilities"]
                require(
                    capabilities["images"] is True and capabilities["files"] is False,
                    "Hermes must advertise image support and files=false",
                )
                record("image_capabilities", images=True, files=False)
                await verify_image(first, binding, root, home, server, wire)
                return
            reattached = await second.resume_session(binding, config)
            require(
                reattached == binding, "Fresh adapter did not recover the empty binding"
            )
            await second.close(reattached)
            record("resume_empty", same_native_session=True, cwd_confirmed=True)

            async def run(adapter, binding, text):
                run_id = uuid4().hex
                events = []

                async def emit(event):
                    events.append(event)

                task = asyncio.create_task(
                    adapter.run(
                        binding,
                        {"run_id": run_id, "message": text, "attachments": []},
                        emit,
                    )
                )
                tasks.append(task)
                return run_id, events, task

            _, events, turn = await run(first, binding, SEED)
            result = await asyncio.wait_for(turn, 35)
            require(
                result
                == {"status": "completed", "final_text": "gateway fixture response"},
                f"Unexpected text run result: {result}",
            )
            deltas = "".join(
                item["data"]["text"] for item in events if item["type"] == "text_delta"
            )
            require(
                deltas == result["final_text"], f"Unexpected delta text: {deltas!r}"
            )
            require(
                any(
                    item["type"] == "binding_updated"
                    and item["data"]["native"].get("admission_id")
                    for item in events
                ),
                "Native admission was not checkpointed",
            )
            record(
                "text",
                status=result["status"],
                delta_matched=True,
                admission_checkpointed=True,
            )

            await first.close(binding)
            require(
                process.returncode is None, "Closing the adapter stopped the Gateway"
            )
            resumed = await second.resume_session(binding, config)
            require(
                resumed["native"]["session_id"] == native_id,
                "Original native session was replaced",
            )
            _, _, turn = await run(second, resumed, RESUME)
            result = await asyncio.wait_for(turn, 35)
            require(
                result == {"status": "completed", "final_text": "history kept"},
                f"Unexpected resumed turn result: {result}",
            )
            require(
                (RESUME, True, True) in server.requests,
                "Provider did not receive retained native history",
            )
            record(
                "resume",
                same_native_session=True,
                prior_prompt_received=True,
                owner_alive=True,
            )

            run_id, _, turn = await run(second, resumed, HOLD)
            require(
                await asyncio.to_thread(server.holding.wait, 20),
                "Provider did not reach the held call",
            )
            await asyncio.wait_for(second.cancel(resumed, run_id), 15)
            try:
                result = await asyncio.wait_for(asyncio.shield(turn), 10)
                needed_provider_release = False
            except TimeoutError:
                server.release.set()
                result = await asyncio.wait_for(turn, 15)
                needed_provider_release = True
            require(
                result["status"] in {"cancelled", "interrupted"},
                f"No confirmed stop: {result}",
            )
            require(process.returncode is None, "Run cancellation stopped the Gateway")
            receipt = await second._rpc(
                "prompt.receipt",
                {
                    "session_id": native_id,
                    "admission_id": second.binding["native"]["admission_id"],
                },
            )
            require(
                receipt["status"] == "terminal",
                "Gateway did not record a terminal receipt",
            )
            record(
                "cancel",
                status=result["status"],
                native_outcome=receipt.get("outcome"),
                owner_alive=True,
                before_provider_release=not needed_provider_release,
            )

            final = await first.resume_session(binding, config)
            require(
                final["native"]["session_id"] == native_id,
                "Cancellation changed the session",
            )
            _, _, turn = await run(first, final, RESUME)
            result = await asyncio.wait_for(turn, 35)
            require(
                result == {"status": "completed", "final_text": "history kept"},
                f"Session unavailable after cancellation: {result}",
            )
            record("reuse_after_cancel", status=result["status"])
        except Exception:
            log.flush()
            for path in (root / "gateway.log", home / "logs" / "errors.log"):
                if path.exists():
                    print(f"--- {path.name} ---", file=sys.stderr)
                    print(path.read_text(errors="replace")[-4000:], file=sys.stderr)
            raise
        finally:
            server.release.set()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await first.close(None)
            await second.close(None)
            if process.returncode is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    await asyncio.wait_for(process.wait(), 8)
                except TimeoutError:
                    os.killpg(process.pid, signal.SIGKILL)
                    await process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chatraw", required=True, type=Path)
    parser.add_argument("--hermes", required=True, type=Path)
    parser.add_argument("--omit-empty-attachments-for-diagnosis", action="store_true")
    parser.add_argument("--image-only", action="store_true")
    args_config = parser.parse_args()
    if args_config.image_only and args_config.omit_empty_attachments_for_diagnosis:
        parser.error("--image-only uses the adapter's original outbound messages")
    chatraw = args_config.chatraw.resolve(strict=True)
    executable = args_config.hermes.resolve(strict=True)
    sys.path.insert(0, str(chatraw))
    from agent_runner.adapters.hermes import HermesAdapter
    from aiohttp import ClientWebSocketResponse, WSMsgType

    send_json = ClientWebSocketResponse.send_json
    receive = ClientWebSocketResponse.receive
    submitted = {}
    image_uploads = set()
    image_wire = []

    async def watch_submit(ws, frame, *args, **kwargs):
        if args_config.image_only and frame.get("method") == "image.attach_bytes":
            image_uploads.add((ws, frame["id"]))
            image_wire.append(
                (
                    "attach_request",
                    base64.b64decode(frame["params"]["content_base64"], validate=True),
                )
            )
        if frame.get("method") == "prompt.submit":
            params = frame["params"]
            if args_config.image_only:
                image_wire.append(("prompt_submit", params.get("attachments")))
            empty = params.get("attachments") == []
            if empty and args_config.omit_empty_attachments_for_diagnosis:
                frame = {
                    **frame,
                    "params": {
                        key: value
                        for key, value in params.items()
                        if key != "attachments"
                    },
                }
                record(
                    "diagnostic_wire_change",
                    field="attachments",
                    original="empty list",
                    sent="absent",
                )
            submitted[(ws, frame["id"])] = empty and "attachments" in frame["params"]
        return await send_json(ws, frame, *args, **kwargs)

    async def watch_reply(ws, *args, **kwargs):
        message = await receive(ws, *args, **kwargs)
        if message.type == WSMsgType.TEXT:
            frame = message.json()
            key = (ws, frame.get("id"))
            if key in image_uploads:
                image_uploads.remove(key)
                if "error" in frame:
                    record(
                        "native_image_error",
                        code=frame["error"].get("code"),
                        message=frame["error"].get("message"),
                    )
                image_wire.append(("attach_reply", frame.get("result")))
            if key in submitted:
                empty = submitted.pop(key)
                error = frame.get("error")
                if error is not None:
                    record(
                        "native_submit_error",
                        sent_empty_attachments=empty,
                        code=error.get("code"),
                        message=error.get("message"),
                    )
        return message

    adapter_file = chatraw / "agent_runner" / "adapters" / "hermes.py"
    record(
        "inputs",
        adapter_sha256=hashlib.sha256(adapter_file.read_bytes()).hexdigest(),
        python=sys.version.split()[0],
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), LoopbackModel)
    server.requests = []
    server.image_urls = []
    server.holding, server.release = threading.Event(), threading.Event()
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with (
            tempfile.TemporaryDirectory(prefix="chatraw-hermes-") as temp,
            patch.object(ClientWebSocketResponse, "send_json", watch_submit),
            patch.object(ClientWebSocketResponse, "receive", watch_reply),
        ):
            asyncio.run(
                verify(
                    HermesAdapter,
                    executable,
                    Path(temp).resolve(),
                    server,
                    args_config.image_only,
                    image_wire,
                )
            )
    finally:
        server.release.set()
        server.shutdown()
        server.server_close()
        worker.join()


if __name__ == "__main__":
    main()
