"""Title initialization at the real SQLite display projection boundary."""

import json
import sqlite3
import unittest
from types import SimpleNamespace

from backend.agent_storage import AgentStorage, initialize_agent_schema


class AgentTitleTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            "CREATE TABLE chats(id TEXT PRIMARY KEY,title TEXT,updated_at TEXT);"
            "CREATE TABLE messages(id TEXT PRIMARY KEY,chat_id TEXT,role TEXT,content TEXT,created_at TEXT);"
        )
        initialize_agent_schema(self.connection, ":memory:")
        self.connection.execute("INSERT INTO chats VALUES ('chat','New Chat','')")
        self.connection.commit()
        self.storage = AgentStorage(
            SimpleNamespace(
                get_conn=lambda: self.connection,
                chat_exists=lambda chat_id: self.connection.execute(
                    "SELECT 1 FROM chats WHERE id=?", (chat_id,)
                ).fetchone()
                is not None,
            )
        )

    def tearDown(self):
        self.connection.close()

    def project(self, message, key="first", kind="run"):
        if self.storage.submission("chat", key) is None:
            self.storage.reserve(
                "chat", key, "session", kind, json.dumps({"message": message})
            )
        self.storage.project(
            self.storage.submission("chat", key),
            {
                "run_id": key,
                "chat_id": "chat",
                "session_id": "session",
                "status": "completed",
                "last_seq": 0,
                "final_text": "reply",
            },
        )

    def title(self):
        return self.connection.execute(
            "SELECT title FROM chats WHERE id='chat'"
        ).fetchone()[0]

    def test_first_user_message_uses_ordinary_length_and_ellipsis_rule(self):
        for message in ("Short title", "字" * 30, "字" * 31):
            with self.subTest(message=message):
                # Each subcase is a fresh chat projection.
                self.connection.execute("DELETE FROM agent_messages")
                self.connection.execute("DELETE FROM messages")
                self.connection.execute("DELETE FROM agent_submissions")
                self.connection.execute("UPDATE chats SET title='New Chat'")
                self.connection.commit()
                self.project(message)
                self.assertEqual(
                    self.title(), message[:30] + ("..." if len(message) > 30 else "")
                )

    def test_replay_and_later_turn_cannot_rename_first_message_title(self):
        self.project("New Chat")
        self.project("New Chat")
        self.project("A different later message", key="second")
        self.project("New Chat")
        self.assertEqual(self.title(), "New Chat")
        self.assertEqual(
            self.connection.execute("SELECT count(*) FROM messages").fetchone()[0], 4
        )

    def test_manual_title_survives_first_projection_and_replay(self):
        self.connection.execute("UPDATE chats SET title='My project'")
        self.connection.commit()
        self.project("First message")
        self.assertEqual(self.title(), "My project")
        self.connection.execute("UPDATE chats SET title='Renamed by user'")
        self.connection.commit()
        self.project("First message")
        self.project("Next message", key="second")
        self.assertEqual(self.title(), "Renamed by user")

    def test_compaction_does_not_name_a_chat(self):
        self.project("", kind="compact")
        self.assertEqual(self.title(), "New Chat")


if __name__ == "__main__":
    unittest.main()
