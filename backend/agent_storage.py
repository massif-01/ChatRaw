"""ChatRaw owns bindings/outbox/display projections, never Runner state transitions."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path


def stamp():
    # Match the existing ChatRaw display-table timestamps. Runner event time is UTC.
    return datetime.now().isoformat()


def initialize_agent_schema(connection, database_path):
    existing = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_schema'"
    ).fetchone()
    if existing:
        if connection.execute("SELECT version FROM agent_schema").fetchone()[0] != 1:
            raise RuntimeError("Unsupported ChatRaw Agent schema version")
        return
    connection.commit()
    # Back up an existing chat database before the first additive migration.
    if connection.execute("SELECT 1 FROM chats LIMIT 1").fetchone():
        backup = Path(str(database_path) + ".pre-agent-v1.bak")
        if backup.exists():
            raise RuntimeError(
                "Agent migration backup already exists; inspect before migrating"
            )
        with sqlite3.connect(backup) as destination:
            connection.backup(destination)
        backup.chmod(0o600)
    connection.executescript(
        """
        BEGIN IMMEDIATE;
        CREATE TABLE agent_schema (version INTEGER NOT NULL);
        INSERT INTO agent_schema VALUES (1);
        CREATE TABLE agent_bindings (
            chat_id TEXT PRIMARY KEY, agent_id TEXT, session_id TEXT,
            workspace TEXT, confirmed INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE agent_submissions (
            chat_id TEXT NOT NULL, client_request_id TEXT NOT NULL,
            session_id TEXT NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL,
            run_id TEXT, admission TEXT NOT NULL, snapshot TEXT,
            created_at TEXT NOT NULL,
            PRIMARY KEY(chat_id,client_request_id), UNIQUE(run_id)
        );
        CREATE TABLE agent_messages (
            run_id TEXT NOT NULL, role TEXT NOT NULL, message_id TEXT NOT NULL UNIQUE,
            PRIMARY KEY(run_id,role)
        );
        CREATE TABLE agent_projection (run_id TEXT PRIMARY KEY, last_seq INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE agent_artifacts (artifact_id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, run_id TEXT NOT NULL);
        COMMIT;
    """
    )


class AgentStorage:
    def __init__(self, database):
        self.database = database

    @property
    def db(self):
        return self.database.get_conn()

    def binding(self, chat_id):
        row = self.db.execute(
            "SELECT * FROM agent_bindings WHERE chat_id=?", (chat_id,)
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["workspace"] = (
            json.loads(result["workspace"]) if result["workspace"] else None
        )
        return result

    def bind(self, chat_id, agent_id, session_id, workspace, confirmed=False):
        with self.db:
            self.db.execute(
                "INSERT INTO agent_bindings VALUES (?,?,?,?,?) ON CONFLICT(chat_id) DO UPDATE SET agent_id=excluded.agent_id, session_id=excluded.session_id, workspace=excluded.workspace, confirmed=excluded.confirmed",
                (chat_id, agent_id, session_id, json.dumps(workspace), int(confirmed)),
            )

    def submission(self, chat_id, key):
        row = self.db.execute(
            "SELECT * FROM agent_submissions WHERE chat_id=? AND client_request_id=?",
            (chat_id, key),
        ).fetchone()
        return dict(row) if row else None

    def run(self, run_id):
        row = self.db.execute(
            "SELECT * FROM agent_submissions WHERE run_id=?", (run_id,)
        ).fetchone()
        return dict(row) if row else None

    def reserve(self, chat_id, key, session_id, kind, body):
        with self.db:
            self.db.execute(
                "INSERT INTO agent_submissions VALUES (?,?,?,?,?,NULL,'unknown',NULL,?)",
                (chat_id, key, session_id, kind, body, stamp()),
            )

    def project(self, submission, snapshot):
        """One idempotent local transaction for user/final assistant display rows."""
        run_id = snapshot["run_id"]
        if (
            snapshot["chat_id"] != submission["chat_id"]
            or snapshot["session_id"] != submission["session_id"]
        ):
            raise ValueError("Runner snapshot ownership mismatch")
        with self.db:
            self.db.execute(
                "UPDATE agent_submissions SET run_id=?,admission='accepted',snapshot=? WHERE chat_id=? AND client_request_id=?",
                (
                    run_id,
                    json.dumps(snapshot, ensure_ascii=False),
                    submission["chat_id"],
                    submission["client_request_id"],
                ),
            )
            if not self.database.chat_exists(submission["chat_id"]):
                return  # Deleted settled chat must never be recreated by reconciliation.
            if submission["kind"] == "run":
                body = json.loads(submission["body"])
                self._message(
                    run_id,
                    submission["chat_id"],
                    "user",
                    body["message"],
                    submission["created_at"],
                )
            if (
                snapshot["status"]
                in ("completed", "failed", "cancelled", "interrupted")
                and "final_text" in snapshot
            ):
                self._message(
                    run_id,
                    submission["chat_id"],
                    "assistant",
                    snapshot["final_text"],
                    stamp(),
                )

    def _message(self, run_id, chat_id, role, content, created_at):
        message_id = f"agent-{run_id}-{role}"
        self.db.execute(
            "INSERT OR IGNORE INTO agent_messages VALUES (?,?,?)",
            (run_id, role, message_id),
        )
        self.db.execute(
            "INSERT INTO messages (id,chat_id,role,content,created_at) VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET content=excluded.content",
            (message_id, chat_id, role, content, created_at),
        )
        self.db.execute("UPDATE chats SET updated_at=? WHERE id=?", (stamp(), chat_id))

    def pending(self):
        result = []
        for row in self.db.execute("SELECT * FROM agent_submissions"):
            row = dict(row)
            snapshot = json.loads(row["snapshot"]) if row["snapshot"] else {}
            projection = self.db.execute(
                "SELECT last_seq FROM agent_projection WHERE run_id=?", (row["run_id"],)
            ).fetchone()
            incomplete_events = snapshot.get("last_seq", 0) > (
                projection[0] if projection else 0
            )
            if (
                row["admission"] == "unknown"
                or incomplete_events
                or (
                    row["admission"] == "accepted"
                    and snapshot.get("status")
                    not in ("completed", "failed", "cancelled", "interrupted")
                )
            ):
                result.append(row)
        return result
