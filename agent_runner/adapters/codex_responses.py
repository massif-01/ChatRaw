"""Private Responses compatibility endpoint for one owned Codex app-server."""

import hmac
import json
from secrets import token_urlsafe
from urllib.parse import urlsplit

from .base import AdapterError


PROVIDER = "chatraw-responses-compat"
TOKEN_ENV = "CHATRAW_CODEX_RESPONSES_TOKEN"
UPSTREAM_SETTING = "responses_compat_upstream"
_PATH = "/v1/responses"
_MAX_REQUEST_BYTES = 64 * 1024 * 1024


def validate_upstream(value: object) -> str:
    error = AdapterError(
        "invalid_config",
        "Codex Responses compatibility requires a host HTTP(S) /v1/responses URL.",
    )
    if (
        not isinstance(value, str)
        or not value
        or any(char.isspace() or ord(char) < 32 for char in value)
    ):
        raise error
    try:
        url = urlsplit(value)
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or url.path != _PATH
            or "?" in value
            or "#" in value
            or url.port == 0
        ):
            raise error
    except ValueError:
        raise error from None
    return value


def normalize_instructions(payload: dict) -> None:
    """Fold only textual instruction items into the provider's leading system message."""
    instructions = payload.get("instructions")
    if instructions is not None and not isinstance(instructions, str):
        raise ValueError("Responses instructions must be text.")
    items = payload.get("input")
    if not isinstance(items, list):
        return

    remaining = []
    text = [instructions] if instructions else []
    for item in items:
        if not isinstance(item, dict) or item.get("role") not in (
            "system",
            "developer",
        ):
            remaining.append(item)
            continue
        if (
            item.get("type", "message") != "message"
            or item.keys() - {"type", "id", "role", "content"}
            or ("id" in item and not isinstance(item["id"], str))
        ):
            raise ValueError("Unsupported Responses instruction item.")
        content = item.get("content")
        if isinstance(content, str):
            text.append(content)
        elif isinstance(content, list) and all(
            isinstance(part, dict)
            and part.keys() == {"type", "text"}
            and part["type"] == "input_text"
            and isinstance(part["text"], str)
            for part in content
        ):
            text.append("\n".join(part["text"] for part in content))
        else:
            raise ValueError(
                "Responses system and developer messages must contain only input text."
            )
    if len(remaining) != len(items):
        payload["instructions"] = "\n\n".join(text)
        payload["input"] = remaining


class ResponsesEndpoint:
    @classmethod
    async def open(cls, upstream: str):
        # aiohttp is already a Runner dependency. Keep ordinary Codex importable
        # without it, since the compatibility listener is opt-in.
        from aiohttp import ClientSession, ClientTimeout, DummyCookieJar, web

        endpoint = cls()
        endpoint.upstream = upstream
        endpoint.token = token_urlsafe(32)
        endpoint.client = ClientSession(
            timeout=ClientTimeout(total=None, connect=10, sock_read=300),
            trust_env=False,
            auto_decompress=False,
            cookie_jar=DummyCookieJar(),
        )
        app = web.Application(client_max_size=_MAX_REQUEST_BYTES)
        app.router.add_post(_PATH, endpoint.forward)
        endpoint.runner = web.AppRunner(
            app,
            access_log=None,
            handler_cancellation=True,
            shutdown_timeout=0.1,
        )
        try:
            await endpoint.runner.setup()
            await web.TCPSite(endpoint.runner, "127.0.0.1", 0).start()
            endpoint.base_url = f"http://127.0.0.1:{endpoint.runner.addresses[0][1]}/v1"
        except BaseException:
            await endpoint.close()
            raise
        return endpoint

    async def close(self) -> None:
        try:
            await self.runner.cleanup()
        finally:
            await self.client.close()

    async def forward(self, request):
        from aiohttp import ClientError, web

        if request.raw_path != _PATH:
            raise web.HTTPNotFound()
        expected = f"Bearer {self.token}".encode()
        actual = request.headers.get("Authorization", "").encode(
            "utf-8", errors="replace"
        )
        if not hmac.compare_digest(actual, expected):
            raise web.HTTPUnauthorized()

        try:
            payload = await request.json()
        except (ValueError, RecursionError):
            return web.json_response(
                {"error": {"message": "Invalid Responses JSON."}}, status=400
            )
        if not isinstance(payload, dict):
            return web.json_response(
                {"error": {"message": "Expected a Responses object."}}, status=400
            )
        try:
            normalize_instructions(payload)
            body = json.dumps(payload, allow_nan=False).encode()
        except (ValueError, TypeError, RecursionError) as error:
            message = (
                str(error)
                if type(error) is ValueError
                else "Invalid Responses payload."
            )
            return web.json_response({"error": {"message": message}}, status=400)

        try:
            upstream = await self.client.post(
                self.upstream,
                data=body,
                allow_redirects=False,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream, application/json",
                },
            )
        except (ClientError, TimeoutError):
            return web.json_response(
                {"error": {"message": "Codex Responses upstream is unavailable."}},
                status=502,
            )
        async with upstream:
            if 300 <= upstream.status < 400:
                return web.json_response(
                    {
                        "error": {
                            "message": "Codex Responses upstream redirects are disabled."
                        }
                    },
                    status=502,
                )
            headers = {
                name: upstream.headers[name]
                for name in (
                    "Content-Type",
                    "Content-Encoding",
                    "Retry-After",
                    "x-request-id",
                )
                if name in upstream.headers
            }
            response = web.StreamResponse(status=upstream.status, headers=headers)
            await response.prepare(request)
            try:
                async for chunk in upstream.content.iter_any():
                    await response.write(chunk)
                await response.write_eof()
            except (ClientError, TimeoutError, ConnectionError):
                # A broken upstream stream must not look like a successful EOF.
                if request.transport is not None:
                    request.transport.abort()
            return response
