"""Run one RM-01 Agent acceptance case after the inference window is handed over."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import struct
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import uuid4
import zlib


AGENTS = ("codex", "claude", "pi", "deepseek", "hermes")
CASES = ("compact", "image", "stop")
TERMINAL = {"completed", "failed", "cancelled", "interrupted"}
WORKSPACE_ROOT = PurePosixPath("/var/lib/chatraw-runner/workspaces")
HOLD_SECONDS = 30
DIGITS = {
    "0": "0111111",
    "1": "0000110",
    "2": "1011011",
    "3": "1001111",
    "4": "1100110",
    "5": "1101101",
    "6": "1111101",
    "7": "0000111",
    "8": "1111111",
    "9": "1101111",
}
SSH = [
    "ssh",
    "-S",
    "/tmp/chatraw-rm01-control.sock",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=5",
    "rm01@10.10.99.99",
]


class Unverified(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ApiError(RuntimeError):
    def __init__(self, status, code):
        self.status = status
        self.code = code
        super().__init__(f"HTTP {status}: {code}")


class Api:
    def __init__(self, base):
        parsed = urlsplit(base)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username is not None
        ):
            raise ValueError("Use the ChatRaw origin without a path or credentials.")
        self.base = base
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def open(self, method, path, data=None, content_type="application/json"):
        request = Request(
            self.base + path,
            data=data,
            method=method,
            headers={
                "Origin": self.base,
                "Content-Type": content_type,
            },
        )
        try:
            return self.opener.open(request, timeout=25)
        except HTTPError as error:
            try:
                response = json.load(error)
                detail = response.get("detail", response)
                code = detail.get("code") if isinstance(detail, dict) else None
            except (ValueError, AttributeError):
                code = None
            raise ApiError(error.code, code) from None

    def json(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        with self.open(method, path, data) as response:
            return json.load(response)

    def png(self, chat_id, data):
        boundary = uuid4().hex
        form = (
            (
                f'--{boundary}\r\nContent-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="D-vision.png"\r\n'
                "Content-Type: image/png\r\n\r\n"
            ).encode()
            + data
            + f"\r\n--{boundary}--\r\n".encode()
        )
        with self.open(
            "POST",
            "/api/agents/attachments",
            form,
            f"multipart/form-data; boundary={boundary}",
        ) as response:
            return json.load(response)


def png(digits):
    # Large seven-segment glyphs keep the random answer entirely in the pixel data.
    width, height = 44 * len(digits) + 20, 80
    rows = [bytearray(b"\xff" * width) for _ in range(height)]
    segments = [
        (7, 31, 10, 17),
        (31, 38, 17, 37),
        (31, 38, 43, 63),
        (7, 31, 63, 70),
        (0, 7, 43, 63),
        (0, 7, 17, 37),
        (7, 31, 37, 44),
    ]
    for index, digit in enumerate(digits):
        for active, (x0, x1, y0, y1) in zip(reversed(DIGITS[digit]), segments):
            if active == "1":
                left = 10 + index * 44
                for row in rows[y0:y1]:
                    row[left + x0 : left + x1] = b"\x00" * (x1 - x0)

    def chunk(kind, payload):
        body = kind + payload
        return (
            struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))
        )

    pixels = b"".join(b"\x00" + row for row in rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(pixels))
        + chunk(b"IEND", b"")
    )


def workspace_path(binding):
    session_id = binding["session_id"]
    if (
        not re.fullmatch(r"[0-9a-f]{32}", session_id)
        or binding["workspace"]["kind"] != "managed"
        or binding["workspace"]["id"] != session_id
    ):
        raise Unverified("ChatRaw did not confirm the managed session workspace")
    return WORKSPACE_ROOT / session_id


def markers(workspace, token):
    # All remote arguments are fixed paths plus locally validated hex identifiers.
    if workspace.parent != WORKSPACE_ROOT or not re.fullmatch(
        r"[0-9a-f]{32}", workspace.name
    ):
        raise Unverified("Invalid managed workspace path")
    if not re.fullmatch(r"[0-9a-f]{32}", token):
        raise Unverified("Invalid marker token")
    program = """
import json, os, stat, sys
from pathlib import Path
root = Path(sys.argv[1])
if root.resolve(strict=True) != root or not root.is_dir() or root.stat().st_uid != os.getuid():
    raise SystemExit("Managed workspace ownership or path could not be verified")
result = {}
for stage in ("started", "late"):
    path = root / ("d-" + sys.argv[2] + "." + stage)
    try:
        info = path.lstat()
    except FileNotFoundError:
        result[stage] = "missing"
        continue
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > 80:
        result[stage] = "unexpected"
        continue
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        data = stream.read(81)
    result[stage] = "matched" if data == (sys.argv[2] + "\\n").encode() else "unexpected"
print(json.dumps(result))
"""
    reply = subprocess.run(
        [*SSH, shlex.join(["python3", "-c", program, str(workspace), token])],
        check=True,
        capture_output=True,
        text=True,
        timeout=8,
    )
    return json.loads(reply.stdout)


def stop_command(workspace, token):
    target = workspace / f"d-{token}"
    return (
        f"test \"$(pwd -P)\" = '{workspace}' && set -C "
        f"&& printf '%s\\n' '{token}' > '{target}.started' "
        f"&& sleep {HOLD_SECONDS} && printf '%s\\n' '{token}' > '{target}.late'"
    )


def reviewed_once(agent, interaction, command, workspace):
    if interaction.get("kind") != "approval" or interaction.get("presentation"):
        return None
    operation = interaction.get("operation") or {}
    if set(operation) - {"tool", "command", "cwd_label"}:
        return None
    allowed_tools = {
        "codex": {"commandExecution"},
        "claude": {"Bash"},
        "pi": {"bash"},
        "hermes": {None, "terminal"},
        "deepseek": {"bash"},
    }
    if operation.get("tool") not in allowed_tools[agent]:
        return None
    if operation.get("cwd_label", str(workspace)) != str(workspace):
        return None
    native = operation.get("command")
    if native != command:
        # Codex may expose the command inside an explicit bash -lc argv wrapper.
        if agent != "codex" or not isinstance(native, str):
            return None
        try:
            argv = shlex.split(native)
        except ValueError:
            return None
        if argv not in (["/bin/bash", "-lc", command], ["/bin/bash", "-c", command]):
            return None
    for decision in interaction.get("decisions", []):
        if decision.get("label") in {"Allow once", "once"} and decision.get(
            "scope"
        ) in {None, "once"}:
            return decision["id"]
    return None


class Case:
    def __init__(self, api, agent, kind, output, timeout):
        self.api = api
        self.agent = agent
        self.kind = kind
        self.output = output
        self.timeout = timeout
        self.report = {"agent": agent, "case": kind, "steps": []}
        self.save()

    def save(self):
        pending = self.output / "result.tmp"
        pending.write_text(json.dumps(self.report, ensure_ascii=False, indent=2) + "\n")
        pending.replace(self.output / "result.json")

    def run(self):
        health = self.api.json("GET", f"/api/agents/{self.agent}/health")
        capabilities = health.get("capabilities") or {}
        self.report["health"] = {
            key: health.get(key)
            for key in ("availability", "version", "reason", "capabilities")
        }
        self.save()
        if health["availability"] != "ready":
            raise Unverified("Agent health is not ready")
        required = {"compact": "compact", "image": "images", "stop": "cancel"}
        if capabilities.get(required[self.kind]) is not True:
            return "unsupported"
        self.chat_id = self.api.json("POST", "/api/chats")["id"]
        self.report["chat_id"] = self.chat_id
        self.save()
        self.binding = self.api.json(
            "PUT",
            f"/api/chats/{self.chat_id}/agent",
            {
                "agent_id": self.agent,
                "workspace": {"kind": "managed"},
            },
        )
        self.report["binding"] = self.binding
        self.save()
        if (
            self.binding["chat_id"] != self.chat_id
            or self.binding["agent_id"] != self.agent
        ):
            raise Unverified("ChatRaw bound a different chat or Agent")
        self.workspace = workspace_path(self.binding)
        return {"compact": self.compact, "image": self.image, "stop": self.stop}[
            self.kind
        ]()

    def submit(self, label, message=None, attachment=None):
        key = uuid4().hex
        if message is None:
            route = f"/api/agents/sessions/{self.binding['session_id']}/compact"
            body = {"client_request_id": key}
        else:
            route = "/api/agents/runs"
            body = {
                "chat_id": self.chat_id,
                "client_request_id": key,
                "message": message,
                "attachments": [{"attachment_id": attachment}] if attachment else [],
            }
        step = {"label": label, "client_request_id": key, "submission": "pending"}
        self.report["steps"].append(step)
        self.save()
        try:
            accepted = self.api.json("POST", route, body)
        except (OSError, ApiError, ValueError):
            query = urlencode({"chat_id": self.chat_id, "client_request_id": key})
            lookup = self.api.json("GET", f"/api/agents/runs?{query}")
            step["lookup"] = lookup
            self.save()
            if lookup["admission"] != "accepted" or not lookup.get("run"):
                raise
            accepted = lookup["run"]
        step["submission"] = "accepted"
        step["accepted"] = accepted
        self.save()
        if (
            accepted["session_id"] != self.binding["session_id"]
            or accepted["chat_id"] != self.chat_id
        ):
            raise Unverified("Run was associated with a different chat or session")
        return step

    def snapshot(self, step):
        run_id = step["accepted"]["run_id"]
        snapshot = self.api.json("GET", f"/api/agents/runs/{run_id}")
        if (
            snapshot["run_id"] != run_id
            or snapshot["session_id"] != self.binding["session_id"]
        ):
            raise Unverified("Run snapshot identity mismatch")
        step["snapshot"] = snapshot
        self.save()
        return snapshot

    def events(self, step):
        run_id = step["accepted"]["run_id"]
        path = f"/api/agents/runs/{run_id}/events?after=0"
        snapshot = step["snapshot"]
        with self.api.open("GET", path) as stream:
            events = []
            for _ in range(snapshot["last_seq"]):
                line = stream.readline()
                if not line:
                    break
                events.append(json.loads(line))
        target = self.output / f"{step['label']}-{run_id}.ndjson"
        target.write_text(
            "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events)
        )
        done = [event for event in events if event["type"] == "done"]
        if [event["seq"] for event in events] != list(
            range(1, snapshot["last_seq"] + 1)
        ):
            raise Unverified("Run event replay did not reach the snapshot cursor")
        if snapshot["status"] == "unknown":
            return events
        if len(done) != 1 or done[0]["data"]["status"] != snapshot["status"]:
            raise Unverified("Run event log lacks one matching terminal event")
        return events

    def cancel(self, step):
        run_id = step["accepted"]["run_id"]
        step["cancel_requested_at"] = datetime.now(timezone.utc).isoformat()
        self.save()
        try:
            step["cancel_receipt"] = self.api.json(
                "POST", f"/api/agents/runs/{run_id}/cancel", {}
            )
        except (OSError, ApiError) as error:
            step["cancel_error"] = str(error)
        self.save()

    def wait(self, step, cancelling=False):
        deadline = time.monotonic() + (45 if cancelling else self.timeout)
        while time.monotonic() < deadline:
            snap = self.snapshot(step)
            if snap["status"] in TERMINAL:
                return snap, self.events(step)
            if snap["status"] == "unknown":
                self.events(step)
                detail = snap.get("error", {}).get("code")
                raise Unverified(f"Native execution state is unknown ({detail})")
            if snap["interactions"] and not cancelling:
                self.cancel(step)
                self.wait(step, cancelling=True)
                raise Unverified("Unexpected interaction during a no-tool test")
            time.sleep(2)
        if not cancelling:
            self.cancel(step)
            self.wait(step, cancelling=True)
        raise Unverified("No terminal result within the observation window")

    def text_run(self, label, prompt, attachment=None):
        snap, events = self.wait(self.submit(label, prompt, attachment))
        if snap["status"] != "completed":
            raise Unverified(f"{label} settled as {snap['status']}")
        if any(event["type"].startswith("tool_") for event in events):
            raise Unverified(f"{label} used a tool despite the test prompt")
        return snap.get("final_text", "")

    def compact(self):
        token = "D-" + uuid4().hex[:10].upper()
        self.report["continuity"] = {"expected_code": token}
        self.save()
        self.text_run(
            "seed",
            (
                f"D验收 {self.agent} compact. Keep the continuity code {token} available for a later question. "
                "Do not call tools. Reply only OK."
            ),
        )
        count = 4 if self.agent == "hermes" else 2
        # Pi preserves ~20k estimated tokens by default. Keep its tail over
        # that threshold with benign text instead of changing native settings.
        padding = (
            "Harbor inventories are checked against the shift log. " * 850
            if self.agent == "pi"
            else ""
        )
        for number in range(1, count + 1):
            self.text_run(
                f"history-{number}",
                (
                    f"D验收 background note {number}. Do not call tools. Reply only OK.\n{padding}"
                ),
            )
        snap, _ = self.wait(self.submit("compact"))
        if snap["status"] != "completed":
            raise Unverified(f"Compact settled as {snap['status']}")
        answer = self.text_run(
            "continuity",
            (
                "D验收 continuity check. What was the continuity code supplied in the earlier messages? "
                "Do not call tools. Return only the code."
            ),
        )
        current = self.api.json("GET", f"/api/chats/{self.chat_id}/agent")
        self.report["continuity"].update(
            same_chatraw_session=current["session_id"] == self.binding["session_id"],
            code_matched=answer.strip().strip("`") == token,
        )
        if not self.report["continuity"]["same_chatraw_session"]:
            raise Unverified("ChatRaw changed the bound session")
        if not self.report["continuity"]["code_matched"]:
            raise Unverified("The continuity answer did not match the earlier token")
        return "native_evidence_pending"

    def image(self):
        code = str(int.from_bytes(os.urandom(4)) % 900_000 + 100_000)
        data = png(code)
        (self.output / "D-vision.png").write_bytes(data)
        upload = self.api.png(self.chat_id, data)
        self.report["image"] = {
            "expected_code": code,
            "sha256": hashlib.sha256(data).hexdigest(),
            "upload": upload,
        }
        self.save()
        if upload["size"] != len(data) or upload["mime_type"] != "image/png":
            raise Unverified("ChatRaw did not confirm the PNG upload")
        answer = self.text_run(
            "image",
            (
                f"D验收 {self.agent} PNG. Read the six black digits in the attached image, left to right. "
                "Use only the attached image, do not call tools, and return only the six digits."
            ),
            upload["attachment_id"],
        )
        match = re.fullmatch(r"(?:`{1,3}\s*)?(\d{6})(?:\s*`{1,3})?", answer.strip())
        self.report["image"]["answer_matched"] = bool(match and match[1] == code)
        if not self.report["image"]["answer_matched"]:
            raise Unverified("The image-only random challenge answer did not match")
        return "native_evidence_pending"

    def stop(self):
        token = uuid4().hex
        command = stop_command(self.workspace, token)
        self.report["markers"] = {
            "token": token,
            "workspace": str(self.workspace),
            "command": command,
        }
        before = markers(self.workspace, token)
        self.report["markers"]["before"] = before
        self.save()
        if before != {"started": "missing", "late": "missing"}:
            raise Unverified("The test markers already exist")
        step = self.submit(
            "stop",
            (
                f"D验收 {self.agent} tool stop. Call your foreground terminal tool exactly once with the literal "
                f"shell command below. This ChatRaw session's assigned managed working directory is {self.workspace}. "
                f"The command checks it before writing. Use a foreground timeout of at least {HOLD_SECONDS + 15} seconds if the "
                "tool allows it. Preserve the entire command, do not use background mode, make no additional "
                "tool calls, and do not write any other files.\n\n" + command
            ),
        )
        approved = False
        started_at = None
        deadline = time.monotonic() + self.timeout
        try:
            while time.monotonic() < deadline:
                snap = self.snapshot(step)
                if snap["status"] in TERMINAL | {"unknown"}:
                    self.events(step)
                    raise Unverified(
                        f"Run reached {snap['status']} before mid-tool stop"
                    )
                for interaction in snap["interactions"]:
                    decision = reviewed_once(
                        self.agent, interaction, command, self.workspace
                    )
                    if not decision or approved or len(snap["interactions"]) != 1:
                        raise Unverified(
                            "No reviewable one-time approval for the exact fixture command"
                        )
                    run_id = step["accepted"]["run_id"]
                    iid = interaction["interaction_id"]
                    step["approval"] = self.api.json(
                        "POST",
                        f"/api/agents/runs/{run_id}/interactions/{iid}/reply",
                        {"decision_id": decision},
                    )
                    self.save()
                    if step["approval"].get("status") != "accepted":
                        raise Unverified("Native approval reply was not confirmed")
                    approved = True
                observed = markers(self.workspace, token)
                if observed == {"started": "matched", "late": "missing"}:
                    started_at = time.monotonic()
                    self.report["markers"]["during"] = observed
                    self.report["markers"]["observed_at"] = datetime.now(
                        timezone.utc
                    ).isoformat()
                    self.save()
                    break
                if observed != before:
                    raise Unverified(
                        "Marker state does not prove execution was in progress"
                    )
                time.sleep(2)
            if started_at is None:
                raise Unverified("No started marker was observed during the run")
        finally:
            try:
                if step.get("snapshot", {}).get("status") not in TERMINAL | {"unknown"}:
                    self.cancel(step)
                    snap, events = self.wait(step, cancelling=True)
            finally:
                if started_at is not None:
                    time.sleep(max(0, started_at + HOLD_SECONDS + 2 - time.monotonic()))
                    after = markers(self.workspace, token)
                    self.report["markers"]["after"] = after
                    self.report["markers"]["checked_at"] = datetime.now(
                        timezone.utc
                    ).isoformat()
                    self.save()
        if snap["status"] not in {"cancelled", "interrupted"}:
            raise Unverified(f"Stop settled as {snap['status']}")
        if after != {"started": "matched", "late": "missing"}:
            raise Unverified(
                "The delayed marker exists or the started marker changed after stop"
            )
        if not any(event["type"] == "tool_started" for event in events):
            raise Unverified("No native tool-start event was retained")
        return "passed"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("agent", choices=AGENTS)
    parser.add_argument("case", choices=CASES)
    parser.add_argument("--base", default="http://10.10.99.99:51111")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Use only after inference window handoff.",
    )
    args = parser.parse_args()
    if not args.execute:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "agent": args.agent,
                    "case": args.case,
                    "base": args.base,
                }
            )
        )
        return
    if args.output is None or args.timeout < 10:
        parser.error(
            "Execution requires a new --output directory and a timeout of at least 10 seconds"
        )
    api = Api(args.base)
    args.output.mkdir(parents=True, exist_ok=False)
    case = Case(api, args.agent, args.case, args.output, args.timeout)
    try:
        case.report["outcome"] = case.run()
    except (
        ApiError,
        OSError,
        ValueError,
        Unverified,
        subprocess.SubprocessError,
    ) as error:
        case.report["outcome"] = "unverified"
        case.report["reason"] = str(error)
    finally:
        case.save()
    print(
        json.dumps(
            {
                "outcome": case.report.get("outcome"),
                "report": str(args.output / "result.json"),
            }
        )
    )
    return int(case.report["outcome"] == "unverified")


if __name__ == "__main__":
    raise SystemExit(main())
