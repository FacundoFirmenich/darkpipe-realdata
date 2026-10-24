from __future__ import annotations

import unittest

from learned_question_benchmark import (
    LABELS,
    claim_type_labels,
    learned_queries,
    question_labels,
    query_contract,
    validate_query,
)


class LearnedQuestionTests(unittest.TestCase):
    def test_question_type_taxonomy(self) -> None:
        labels = question_labels("What percentage of households were affected in 2020?")
        self.assertIn("NUMERIC", labels)
        self.assertIn("TEMPORAL", labels)

    def test_quote_and_source(self) -> None:
        labels = question_labels("Who said this and where was the quote published?")
        self.assertIn("ATTRIBUTION", labels)
        self.assertIn("SOURCE_PROVENANCE", labels)

    def test_contract_preserves_exact_quantity(self) -> None:
        item = {"claim": "Credit grew 170% in Argentina in 2026.", "speaker": None, "claim_date": "2026-10-16"}
        contract = query_contract(item)
        self.assertIn("170%", contract["numbers"])

    def test_generator_does_not_invent_numbers(self) -> None:
        item = {"claim": "Credit grew 170% in Argentina in 2026.", "speaker": None, "claim_date": "2026-10-16"}
        probabilities = {label: (0.9 if label == "NUMERIC" else 0.0) for label in LABELS}
        queries = learned_queries(item, probabilities, 0.5, 2)
        for query in queries:
            self.assertEqual([], validate_query(query["text"], query_contract(item)))
        self.assertTrue(any("170%" in query["text"] for query in queries))

    def test_claim_labels_use_gold_questions(self) -> None:
        item = {
            "claim": "A claim",
            "questions": [
                {"question": "Who said it?"},
                {"question": "What percentage was reported?"},
            ],
        }
        labels = claim_type_labels(item)
        self.assertIn("ATTRIBUTION", labels)
        self.assertIn("NUMERIC", labels)


if __name__ == "__main__":
    unittest.main()
