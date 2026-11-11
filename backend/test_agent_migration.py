import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.agent_storage import initialize_agent_schema
from script.agent_db_backup import backup


class AgentMigrationTests(unittest.TestCase):
    def test_additive_migration_and_restorable_backup_preserve_existing_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "chatraw.db"
            with sqlite3.connect(path) as connection:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.executescript(
                    "CREATE TABLE chats(id TEXT PRIMARY KEY,title TEXT); CREATE TABLE messages(id TEXT,content TEXT);"
                )
                connection.execute(
                    "INSERT INTO chats VALUES ('old','Old conversation')"
                )
                connection.execute(
                    "INSERT INTO messages VALUES ('m1','Historical answer')"
                )
                connection.commit()
                initialize_agent_schema(connection, path)
                initialize_agent_schema(connection, path)
                self.assertEqual(
                    connection.execute("SELECT content FROM messages").fetchone()[0],
                    "Historical answer",
                )
                self.assertEqual(
                    connection.execute("SELECT version FROM agent_schema").fetchone()[
                        0
                    ],
                    1,
                )
            original_backup = Path(str(path) + ".pre-agent-v1.bak")
            restored = Path(directory) / "restored.db"
            backup(original_backup, restored)
            with sqlite3.connect(restored) as old:
                self.assertEqual(
                    old.execute("SELECT title FROM chats").fetchone()[0],
                    "Old conversation",
                )
                self.assertIsNone(
                    old.execute(
                        "SELECT name FROM sqlite_master WHERE name='agent_schema'"
                    ).fetchone()
                )
            with self.assertRaises(FileExistsError):
                backup(original_backup, restored)


if __name__ == "__main__":
    unittest.main()
