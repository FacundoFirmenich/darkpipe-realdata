from __future__ import annotations

import unittest

from adjudicate_annotations import nominal_krippendorff, recommendation


class AdjudicationTests(unittest.TestCase):
    def test_unanimous_recommendation_is_not_gold(self) -> None:
        result = recommendation(["SUPPORT", "SUPPORT", "SUPPORT"])
        self.assertEqual("SUPPORT", result["recommended"])
        self.assertEqual("UNANIMOUS", result["agreement"])

    def test_two_of_three_is_majority_only(self) -> None:
        result = recommendation(["SUPPORT", "SUPPORT", "CONTEXT"])
        self.assertEqual("SUPPORT", result["recommended"])
        self.assertEqual("MAJORITY_2_OF_3", result["agreement"])

    def test_three_way_disagreement_has_no_recommendation(self) -> None:
        result = recommendation(["SUPPORT", "REFUTE", "CONTEXT"])
        self.assertIsNone(result["recommended"])
        self.assertEqual("THREE_WAY_DISAGREEMENT", result["agreement"])

    def test_perfect_nominal_agreement(self) -> None:
        report = nominal_krippendorff(
            [["A", "A", "A"], ["B", "B", "B"], ["A", "A", "A"]]
        )
        self.assertAlmostEqual(1.0, report["alpha"])

    def test_missing_values_are_ignored(self) -> None:
        report = nominal_krippendorff([["A", "A", None], ["B", None, "B"]])
        self.assertAlmostEqual(1.0, report["alpha"])


if __name__ == "__main__":
    unittest.main()
