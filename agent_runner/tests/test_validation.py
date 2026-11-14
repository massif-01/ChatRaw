import copy
import unittest

from agent_runner import validation
from agent_runner.store import RunnerError


class InteractionValidationTests(unittest.TestCase):
    def setUp(self):
        self.batch = {
            "kind": "question",
            "title": "Confirm details",
            "allow_cancel": True,
            "questions": [
                {
                    "id": "single",
                    "text": "One",
                    "type": "single",
                    "required": True,
                    "allow_custom": False,
                    "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                },
                {
                    "id": "multi",
                    "text": "Many",
                    "type": "multi",
                    "required": True,
                    "allow_custom": True,
                    "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                },
                {
                    "id": "text",
                    "text": "Explain",
                    "type": "text",
                    "required": True,
                    "allow_custom": False,
                    "options": [],
                },
            ],
        }
        self.answer = {
            "answers": [
                {"question_id": "single", "option_ids": ["a"]},
                {"question_id": "multi", "option_ids": ["a", "b"], "text": "Custom"},
                {"question_id": "text", "option_ids": [], "text": "Details"},
            ]
        }

    def test_complete_batch_preserves_selected_options_and_free_text(self):
        validation.interaction(self.batch)
        self.assertEqual(validation.reply(self.batch, self.answer), self.answer)

    def test_invalid_batch_variants_rejected(self):
        variants = []
        for index, field, value in [
            (0, "option_ids", ["a", "b"]),
            (0, "option_ids", ["unknown"]),
            (1, "option_ids", ["a", "a"]),
            (0, "text", "not allowed"),
            (2, "text", ""),
            (1, "question_id", "single"),
        ]:
            response = copy.deepcopy(self.answer)
            response["answers"][index][field] = value
            variants.append(response)
        variants.append({"answers": self.answer["answers"][:-1]})
        variants.append({**self.answer, "decision_id": "allow"})
        for response in variants:
            with self.subTest(response=response), self.assertRaises(RunnerError):
                validation.reply(self.batch, response)

    def test_cancel_is_exact_and_must_be_declared(self):
        self.assertEqual(
            validation.reply(self.batch, {"cancelled": True}), {"cancelled": True}
        )
        for response in (
            {"cancelled": False},
            {"cancelled": 1},
            {"cancelled": True, "answers": []},
        ):
            with self.assertRaises(RunnerError):
                validation.reply(self.batch, response)
        self.batch["allow_cancel"] = False
        with self.assertRaises(RunnerError):
            validation.reply(self.batch, {"cancelled": True})

    def test_duplicate_native_ids_and_naive_expiry_are_not_admitted(self):
        self.batch["questions"][1]["id"] = "single"
        with self.assertRaises(RunnerError):
            validation.interaction(self.batch)
        with self.assertRaises(RunnerError):
            validation.expiry("2026-11-12T12:00:00")
        self.assertTrue(validation.expired({"expires_at": "2000-01-01T00:00:00Z"}))


if __name__ == "__main__":
    unittest.main()
