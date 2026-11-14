"""Single-process Runner ledger. Transactions are short and never span awaits."""

import json
import os
import sqlite3
import fcntl
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .adapters.base import TERMINAL_STATUSES


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def identifier():
    return uuid4().hex


def encode(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


class RunnerError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


class Store:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock_file = (self.directory / "runner.lock").open("a")
        try:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock_file.close()
            raise RuntimeError("Another Runner owns this data directory") from None
        self.db = sqlite3.connect(self.directory / "runner.db")
        os.chmod(self.directory / "runner.db", 0o600)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA foreign_keys=ON")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1, 2):
            raise RuntimeError("Unsupported Runner database version")
        if version == 1:
            backup = self.directory / "runner.pre-v2.bak"
            if not backup.exists():
                with sqlite3.connect(backup) as destination:
                    self.db.backup(destination)
                backup.chmod(0o600)
            with self.db:
                self.db.execute(
                    "ALTER TABLE sessions ADD COLUMN base_config TEXT NOT NULL DEFAULT '{}'"
                )
                self.db.execute("UPDATE sessions SET base_config=config")
                self.db.execute("PRAGMA user_version=2")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, agent_id TEXT NOT NULL,
                workspace TEXT NOT NULL, workspace_public TEXT NOT NULL,
                binding TEXT, config TEXT NOT NULL, created_at TEXT NOT NULL,
                base_config TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0,
                settings TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
                chat_id TEXT NOT NULL, client_request_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL, request TEXT NOT NULL, kind TEXT NOT NULL,
                status TEXT NOT NULL, last_seq INTEGER NOT NULL DEFAULT 0,
                final_text TEXT, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(chat_id, client_request_id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_run ON runs(session_id)
                WHERE status NOT IN ('completed','failed','cancelled','interrupted');
            CREATE TABLE IF NOT EXISTS events (
                run_id TEXT NOT NULL REFERENCES runs(id), seq INTEGER NOT NULL,
                envelope TEXT NOT NULL, PRIMARY KEY(run_id, seq)
            );
            CREATE TABLE IF NOT EXISTS interactions (
                id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
                native_key TEXT NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL,
                reply TEXT, receipt TEXT, UNIQUE(run_id, native_key)
            );
            CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
                chat_id TEXT NOT NULL, run_id TEXT, kind TEXT NOT NULL,
                name TEXT NOT NULL, mime_type TEXT NOT NULL, size INTEGER NOT NULL
            );
            PRAGMA user_version=2;
        """
        )

    def close(self):
        self.db.close()
        self.lock_file.close()

    def session(self, session_id):
        row = self.db.execute(
            "SELECT * FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
        if row is None:
            raise RunnerError("session_not_found", "Session not found", 404)
        value = dict(row)
        for key in ("binding", "config", "workspace_public", "base_config"):
            value[key] = json.loads(value[key]) if value[key] else None
        return value

    def run(self, run_id):
        row = self.db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise RunnerError("run_not_found", "Run not found", 404)
        return dict(row)

    def active(self, session_id=None):
        sql = "SELECT * FROM runs WHERE status NOT IN ('completed','failed','cancelled','interrupted')"
        args = ()
        if session_id is not None:
            sql += " AND session_id=?"
            args = (session_id,)
        return [dict(row) for row in self.db.execute(sql, args)]

    def lookup(self, chat_id, client_request_id):
        row = self.db.execute(
            "SELECT id FROM runs WHERE chat_id=? AND client_request_id=?",
            (chat_id, client_request_id),
        ).fetchone()
        return self.snapshot(row["id"]) if row else None

    def snapshot(self, run_id):
        row = self.run(run_id)
        result = {
            key: row[key] for key in ("chat_id", "session_id", "status", "last_seq")
        }
        result["run_id"] = row["id"]
        result["interactions"] = [
            {**json.loads(i["payload"]), "interaction_id": i["id"]}
            for i in self.db.execute(
                "SELECT * FROM interactions WHERE run_id=? AND state='pending'",
                (run_id,),
            )
        ]
        if row["error"]:
            result["error"] = json.loads(row["error"])
        if row["final_text"] is not None:
            result["final_text"] = row["final_text"]
        return result

    def event(self, run_id, event_type, data):
        """Caller owns transaction; event and state must commit together."""
        row = self.run(run_id)
        seq = row["last_seq"] + 1
        envelope = {
            "schema_version": 1,
            "run_id": run_id,
            "session_id": row["session_id"],
            "seq": seq,
            "timestamp": now(),
            "type": event_type,
            "data": data,
        }
        self.db.execute(
            "INSERT INTO events VALUES (?,?,?)", (run_id, seq, encode(envelope))
        )
        self.db.execute(
            "UPDATE runs SET last_seq=?,updated_at=? WHERE id=?", (seq, now(), run_id)
        )
        return envelope

    def events(self, run_id, after=0, limit=256):
        return [
            json.loads(row[0])
            for row in self.db.execute(
                "SELECT envelope FROM events WHERE run_id=? AND seq>? ORDER BY seq LIMIT ?",
                (run_id, after, limit),
            )
        ]

    def status(self, run_id, status, reason=None):
        self.db.execute(
            "UPDATE runs SET status=?,updated_at=? WHERE id=?", (status, now(), run_id)
        )
        self.event(
            run_id,
            "status",
            {"status": status, **({"reason": reason} if reason else {})},
        )

    def invalidate(self, run_id, outcome="invalidated"):
        for row in self.db.execute(
            "SELECT id FROM interactions WHERE run_id=? AND state IN ('pending','dispatching','accepted','unknown')",
            (run_id,),
        ).fetchall():
            self.db.execute(
                "UPDATE interactions SET state=? WHERE id=?", (outcome, row["id"])
            )
            self.event(
                run_id,
                "interaction_resolved",
                {"interaction_id": row["id"], "outcome": outcome},
            )

    def settle(self, run_id, result):
        if self.run(run_id)["status"] in TERMINAL_STATUSES:
            return
        status = result["status"]
        self.invalidate(run_id)
        error = result.get("error")
        self.db.execute(
            "UPDATE runs SET error=? WHERE id=?",
            (encode(error) if error else None, run_id),
        )
        self.status(run_id, status)
        if status in TERMINAL_STATUSES:
            self.db.execute(
                "UPDATE runs SET final_text=? WHERE id=?",
                (result["final_text"], run_id),
            )
            self.event(run_id, "done", result)
