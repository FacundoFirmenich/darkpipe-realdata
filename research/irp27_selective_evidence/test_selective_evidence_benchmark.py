from __future__ import annotations

import unittest

import numpy as np

from selective_evidence_benchmark import (
    Pair,
    Threshold,
    aggregate_claim_predictions,
    conformal_prediction_sets,
    lower_precision_bound,
    selective_predictions,
)


class SelectiveEvidenceTests(unittest.TestCase):
    def test_lower_bound_is_conservative(self) -> None:
        self.assertLess(lower_precision_bound(19, 20), 0.95)
        self.assertGreater(lower_precision_bound(100, 100), 0.95)

    def test_selective_threshold_abstains(self) -> None:
        probabilities = np.asarray(
            [
                [0.10, 0.20, 0.70],
                [0.05, 0.92, 0.03],
                [0.80, 0.10, 0.10],
            ]
        )
        classes = ["NEUTRAL", "REFUTE", "SUPPORT"]
        thresholds = {
            "SUPPORT": Threshold("SUPPORT", 0.85, 0.20, 10, 0.95, 0.90, 0.1, 0.90),
            "REFUTE": Threshold("REFUTE", 0.90, 0.20, 10, 0.95, 0.90, 0.1, 0.90),
        }
        self.assertEqual(
            ["ABSTAIN", "REFUTE", "ABSTAIN"],
            selective_predictions(probabilities, classes, thresholds),
        )

    def test_claim_aggregation_preserves_conflict(self) -> None:
        pairs = [
            Pair("X", "1", "claim", "a", "evidence a", "SUPPORT", "CONFLICTING", "g"),
            Pair("X", "1", "claim", "b", "evidence b", "REFUTE", "CONFLICTING", "g"),
        ]
        predicted, gold, _ = aggregate_claim_predictions(
            pairs, ["SUPPORT", "REFUTE"]
        )
        self.assertEqual("CONFLICTING", predicted["1"])
        self.assertEqual("CONFLICTING", gold["1"])

    def test_no_directional_evidence_means_insufficient(self) -> None:
        pairs = [
            Pair("X", "1", "claim", "a", "context", "NEUTRAL", "INSUFFICIENT", "g")
        ]
        predicted, _, _ = aggregate_claim_predictions(pairs, ["ABSTAIN"])
        self.assertEqual("INSUFFICIENT", predicted["1"])

    def test_conformal_sets_include_true_label_on_easy_cases(self) -> None:
        calibration = np.asarray(
            [
                [0.90, 0.05, 0.05],
                [0.05, 0.90, 0.05],
                [0.05, 0.05, 0.90],
            ]
        )
        heldout = np.asarray([[0.95, 0.03, 0.02]])
        classes = ["NEUTRAL", "REFUTE", "SUPPORT"]
        sets, _ = conformal_prediction_sets(
            calibration,
            ["NEUTRAL", "REFUTE", "SUPPORT"],
            heldout,
            classes,
            alpha=0.10,
        )
        self.assertIn("NEUTRAL", sets[0])


if __name__ == "__main__":
    unittest.main()
