from __future__ import annotations

import unittest

import numpy as np

from question_set_sufficiency_benchmark import (
    evidence_state,
    is_answerable,
    jaccard,
    search_query,
    verification_question,
)


class QuestionSetSufficiencyTests(unittest.TestCase):
    def test_answerable_question(self) -> None:
        question = {
            "answers": [
                {"answer": "A documented value", "answer_type": "Extractive"}
            ]
        }
        self.assertTrue(is_answerable(question))

    def test_unanswerable_question(self) -> None:
        question = {
            "answers": [
                {
                    "answer": "No answer could be found.",
                    "answer_type": "Unanswerable",
                }
            ]
        }
        self.assertFalse(is_answerable(question))

    def test_questions_are_presupposition_free(self) -> None:
        item = {
            "claim": "All voters received a benefit in 2026.",
            "speaker": "A Minister",
            "claim_date": "2026-10-01",
        }
        question = verification_question("EVENT_EXISTENCE", item)
        self.assertIn("if any", question)
        self.assertIn(item["claim"], question)

    def test_search_query_preserves_claim_numbers(self) -> None:
        item = {
            "claim": "Credit grew 170% in Argentina in 2026.",
            "speaker": None,
            "claim_date": "2026-10-16",
        }
        query = search_query("NUMERIC", item)
        self.assertIn("170%", query)
        self.assertIn("2026", query)

    def test_evidence_state_blocks_false_support(self) -> None:
        item = {"label": "Supported"}
        state = evidence_state(
            item,
            question_coverage=0.0,
            exact_any=False,
            predicted_false_attachment=True,
            answerable_count=2,
        )
        self.assertEqual("FALSE_SUPPORT", state)

    def test_jaccard(self) -> None:
        self.assertAlmostEqual(jaccard({1, 2}, {2, 3}), 1 / 3)


if __name__ == "__main__":
    unittest.main()
