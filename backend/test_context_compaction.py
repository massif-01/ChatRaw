import os
import shutil
import sys
import tempfile
import unittest

TEST_DATA_DIR = tempfile.mkdtemp(prefix="chatraw-context-test-")
os.environ["DATA_DIR"] = TEST_DATA_DIR

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend import main  # noqa: E402


def tearDownModule():
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)


class FakeLLMService(main.LLMService):
    def __init__(self, db):
        super().__init__(db)
        self.raw_calls = []

    async def _call_chat_completion_raw(self, config, messages, max_tokens, temperature=0.2):
        self.raw_calls.append({
            "config": config,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        })
        return f"summary-{len(self.raw_calls)}"


class EmptySummaryLLMService(FakeLLMService):
    async def _call_chat_completion_raw(self, config, messages, max_tokens, temperature=0.2):
        self.raw_calls.append({
            "config": config,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        })
        return ""


class ContextCompactionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="chatraw-context-db-")
        self.db_path = os.path.join(self.tmpdir, "chatraw.db")
        self.db = main.Database(self.db_path)
        self.db.save_model_config(main.ModelConfig(
            id="default-chat",
            name="Fake Chat Model",
            api_url="http://example.test/v1",
            model_id="fake-chat",
            context_length=4096,
            max_output=1024,
            type="chat",
        ))
        self.service = FakeLLMService(self.db)
        main._context_compaction_locks.clear()

    def tearDown(self):
        try:
            self.db.get_conn().close()
        finally:
            shutil.rmtree(self.tmpdir, ignore_errors=True)
            main._context_compaction_locks.clear()

    def create_chat_with_messages(self, count, content_size=100):
        chat = self.db.create_chat("Compaction Test")
        for idx in range(count):
            role = "user" if idx % 2 == 0 else "assistant"
            content = f"{role}-{idx} " + ("x" * content_size)
            self.db.add_message(chat.id, role, content)
        return chat

    async def test_short_history_is_noop(self):
        chat = self.create_chat_with_messages(4)

        result = await self.service.compact_chat_history(chat.id)

        self.assertTrue(result["success"])
        self.assertFalse(result["compressed"])
        self.assertEqual(result["reason"], "not_enough_history")
        self.assertIsNone(self.db.get_chat_compaction(chat.id))
        self.assertEqual(self.service.raw_calls, [])

    async def test_short_history_is_noop_without_model_config(self):
        self.db.save_model_config(main.ModelConfig(
            id="default-chat",
            name="Unconfigured Chat Model",
            type="chat",
        ))
        chat = self.create_chat_with_messages(4)

        result = await self.service.compact_chat_history(chat.id)

        self.assertTrue(result["success"])
        self.assertFalse(result["compressed"])
        self.assertEqual(result["reason"], "not_enough_history")

    async def test_manual_compaction_saves_summary_and_keeps_recent_messages(self):
        chat = self.create_chat_with_messages(10)

        result = await self.service.compact_chat_history(chat.id)

        self.assertTrue(result["compressed"])
        self.assertEqual(result["compressed_message_count"], 4)
        self.assertEqual(len(self.db.get_messages(chat.id)), 10)
        record = self.db.get_chat_compaction(chat.id)
        self.assertEqual(record["summary"], "summary-1")
        self.assertEqual(record["compressed_message_count"], 4)

        model_messages = self.service.build_history_messages(chat.id, use_compaction=True)
        self.assertEqual(len(model_messages), 7)
        self.assertEqual(model_messages[0]["role"], "system")
        self.assertIn("summary-1", model_messages[0]["content"])
        self.assertEqual(model_messages[1]["content"].split()[0], "user-4")

    async def test_system_prompt_and_summary_are_combined_into_one_system_message(self):
        chat = self.create_chat_with_messages(10)
        await self.service.compact_chat_history(chat.id)

        model_messages = self.service.build_history_messages(
            chat.id,
            use_compaction=True,
            system_prompt="You are precise.",
        )

        system_messages = [message for message in model_messages if message["role"] == "system"]
        self.assertEqual(len(system_messages), 1)
        self.assertIn("You are precise.", system_messages[0]["content"])
        self.assertIn("summary-1", system_messages[0]["content"])

    async def test_existing_summary_is_used_even_when_auto_compress_is_off(self):
        chat = self.create_chat_with_messages(10)
        await self.service.compact_chat_history(chat.id)

        # autoCompress only controls updates; enabled plugins with a summary still use it.
        model_messages = self.service.build_history_messages(chat.id, use_compaction=True)

        self.assertEqual(model_messages[0]["role"], "system")
        self.assertIn("summary-1", model_messages[0]["content"])
        self.assertEqual(len(model_messages), 7)

    async def test_existing_summary_is_merged_and_boundary_advances(self):
        chat = self.create_chat_with_messages(10)
        first = await self.service.compact_chat_history(chat.id)
        self.assertEqual(first["compressed_message_count"], 4)

        for idx in range(10, 14):
            role = "user" if idx % 2 == 0 else "assistant"
            self.db.add_message(chat.id, role, f"{role}-{idx} " + ("y" * 20))

        second = await self.service.compact_chat_history(chat.id)

        self.assertTrue(second["compressed"])
        self.assertEqual(second["compressed_message_count"], 8)
        self.assertEqual(len(self.service.raw_calls), 2)
        second_prompt = self.service.raw_calls[1]["messages"][1]["content"]
        self.assertIn("Existing summary:\nsummary-1", second_prompt)
        self.assertEqual(self.db.get_chat_compaction(chat.id)["summary"], "summary-2")

        model_messages = self.service.build_history_messages(chat.id, use_compaction=True)
        self.assertEqual(len(model_messages), 7)
        self.assertEqual(model_messages[1]["content"].split()[0], "user-8")

    async def test_auto_compaction_below_threshold_skips(self):
        chat = self.create_chat_with_messages(6)

        result = await self.service.maybe_auto_compact(
            chat.id,
            current_user_content="short message",
            threshold_percent=95,
            system_prompt="",
        )

        self.assertTrue(result["success"])
        self.assertFalse(result["compressed"])
        self.assertEqual(result["reason"], "below_threshold")
        self.assertIsNone(self.db.get_chat_compaction(chat.id))

    async def test_auto_compaction_uses_saved_web_content_for_estimate(self):
        chat = self.create_chat_with_messages(7, content_size=600)
        message_to_save = main.build_message_to_save(
            "Summarize this page",
            web_content="网页内容" * 800,
            web_url="https://example.test/page",
        )

        result = await self.service.maybe_auto_compact(
            chat.id,
            current_user_content=message_to_save,
            threshold_percent=30,
            system_prompt="",
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["compressed"])
        self.assertIsNotNone(self.db.get_chat_compaction(chat.id))

    async def test_raw_completion_does_not_write_messages(self):
        chat = self.create_chat_with_messages(10)
        before = len(self.db.get_messages(chat.id))

        await self.service.compact_chat_history(chat.id)

        after = len(self.db.get_messages(chat.id))
        self.assertEqual(before, after)
        self.assertEqual(len(self.service.raw_calls), 1)

    async def test_empty_summary_is_noop_without_writing_compaction(self):
        service = EmptySummaryLLMService(self.db)
        chat = self.create_chat_with_messages(10)

        result = await service.compact_chat_history(chat.id)

        self.assertTrue(result["success"])
        self.assertFalse(result["compressed"])
        self.assertEqual(result["reason"], "summary_unavailable")
        self.assertEqual(result["compressed_message_count"], 0)
        self.assertIsNone(self.db.get_chat_compaction(chat.id))
        self.assertEqual(len(service.raw_calls), 1)

    async def test_chain_summary_batches_for_small_context_window(self):
        self.db.save_model_config(main.ModelConfig(
            id="default-chat",
            name="Small Fake Chat Model",
            api_url="http://example.test/v1",
            model_id="fake-chat",
            context_length=2600,
            max_output=1024,
            type="chat",
        ))
        chat = self.create_chat_with_messages(12, content_size=1800)

        result = await self.service.compact_chat_history(chat.id)

        self.assertTrue(result["compressed"])
        self.assertGreater(len(self.service.raw_calls), 1)
        self.assertEqual(self.service.raw_calls[-1]["max_tokens"], 1024)

    async def test_existing_summary_reduces_rolling_batch_budget(self):
        self.db.save_model_config(main.ModelConfig(
            id="default-chat",
            name="Budgeted Fake Chat Model",
            api_url="http://example.test/v1",
            model_id="fake-chat",
            context_length=3600,
            max_output=1024,
            type="chat",
        ))
        chat = self.create_chat_with_messages(14, content_size=1600)
        history = self.db.get_messages(chat.id)
        long_summary = "已有摘要 " + ("重要约束" * 350)
        self.db.save_chat_compaction(
            chat.id,
            long_summary,
            history[3],
            original_token_estimate=2000,
            summary_token_estimate=main.estimate_text_tokens(long_summary),
            compressed_message_count=4,
        )

        result = await self.service.compact_chat_history(chat.id)

        self.assertTrue(result["compressed"])
        config = self.db.get_model_by_type("chat")
        input_budget = self.service._get_input_budget(config)
        for call in self.service.raw_calls:
            self.assertLessEqual(main.estimate_messages_tokens(call["messages"]), input_budget)

    async def test_invalid_context_configuration_blocks_manual_compaction(self):
        self.db.save_model_config(main.ModelConfig(
            id="default-chat",
            name="Invalid Fake Chat Model",
            api_url="http://example.test/v1",
            model_id="fake-chat",
            context_length=1024,
            max_output=1024,
            type="chat",
        ))
        chat = self.create_chat_with_messages(10)

        with self.assertRaisesRegex(ValueError, "context length"):
            await self.service.compact_chat_history(chat.id)

    async def test_invalid_context_configuration_blocks_auto_compaction(self):
        self.db.save_model_config(main.ModelConfig(
            id="default-chat",
            name="Invalid Fake Chat Model",
            api_url="http://example.test/v1",
            model_id="fake-chat",
            context_length=1024,
            max_output=1024,
            type="chat",
        ))
        chat = self.create_chat_with_messages(10)

        result = await self.service.maybe_auto_compact(
            chat.id,
            current_user_content="current message",
            threshold_percent=30,
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "invalid_context_configuration")

    async def test_delete_chat_clears_compaction_lock(self):
        chat = self.create_chat_with_messages(10)
        await self.service.compact_chat_history(chat.id)
        self.assertIn(chat.id, main._context_compaction_locks)

        self.db.delete_chat(chat.id)

        self.assertNotIn(chat.id, main._context_compaction_locks)

    async def test_create_chat_cleanup_clears_stale_compaction_locks(self):
        chats = [self.create_chat_with_messages(10) for _ in range(10)]
        stale_chat = chats[0]
        await self.service.compact_chat_history(stale_chat.id)
        self.assertIn(stale_chat.id, main._context_compaction_locks)

        self.db.create_chat("Newest")

        self.assertNotIn(stale_chat.id, main._context_compaction_locks)
        self.assertIsNone(self.db.get_chat_compaction(stale_chat.id))

    def test_threshold_is_clamped(self):
        self.assertEqual(main.clamp_context_threshold(1), 30)
        self.assertEqual(main.clamp_context_threshold(101), 95)
        self.assertEqual(main.clamp_context_threshold("bad"), 70)

    async def test_candidates_too_short_skips_compression(self):
        chat = self.create_chat_with_messages(8, content_size=5)

        result = await self.service.compact_chat_history(chat.id)

        self.assertTrue(result["success"])
        self.assertFalse(result["compressed"])
        self.assertEqual(result["reason"], "candidates_too_short")
        self.assertIsNone(self.db.get_chat_compaction(chat.id))
        self.assertEqual(self.service.raw_calls, [])

    async def test_summary_longer_than_original_is_discarded(self):
        class VerboseSummaryService(main.LLMService):
            async def _call_chat_completion_raw(self, config, messages, max_tokens, temperature=0.2):
                return "This is a very verbose summary that is much longer than the original short messages " * 5

        service = VerboseSummaryService(self.db)
        chat = self.create_chat_with_messages(10, content_size=30)

        result = await service.compact_chat_history(chat.id)

        self.assertTrue(result["success"])
        self.assertFalse(result["compressed"])
        self.assertEqual(result["reason"], "summary_not_shorter")
        self.assertIsNone(self.db.get_chat_compaction(chat.id))

    def test_extract_openai_message_text_variants(self):
        self.assertEqual(main.extract_openai_message_text({}), "")
        self.assertEqual(main.extract_openai_message_text({"content": "  hi  "}), "hi")
        self.assertEqual(
            main.extract_openai_message_text(
                {"content": [{"type": "text", "text": "from array"}]}
            ),
            "from array",
        )
        self.assertEqual(
            main.extract_openai_message_text(
                {"content": "", "reasoning_content": "  chain  "}
            ),
            "chain",
        )


if __name__ == "__main__":
    unittest.main()
