#!/usr/bin/env python3
"""Precision-first correction for Gate SOTA-006.

The first sufficiency run calibrated question–passage compatibility for F1 and
therefore produced an inadmissibly high false-positive rate. This wrapper keeps
the retrieval and question-set design unchanged, but calibrates compatibility as
a high-cost evidence-promotion decision: among thresholds with calibration FPR
<= 5%, it chooses the one with highest recall (then precision). If none exists, it
chooses the lowest-FPR non-empty threshold. Answerability uses the original rule.
"""
from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import average_precision_score, precision_recall_fscore_support, roc_auc_score

import question_set_sufficiency_benchmark as benchmark

benchmark.fold = benchmark.core.fold
_ORIGINAL_EVALUATE = benchmark.evaluate_binary_model


def precision_first_evaluate(
    model: Any,
    examples: list[benchmark.PairExample],
    calibration_claims: set[int],
    heldout_claims: set[int],
) -> dict[str, Any]:
    if not examples or "\npassage:" not in examples[0].text:
        return _ORIGINAL_EVALUATE(
            model, examples, calibration_claims, heldout_claims
        )

    texts = [example.text for example in examples]
    labels = np.asarray([example.label for example in examples], dtype=int)
    claims = np.asarray([example.claim_index for example in examples], dtype=int)
    probabilities = model.predict_proba(texts)[:, 1]
    calibration_mask = np.asarray(
        [claim in calibration_claims for claim in claims]
    )
    heldout_mask = np.asarray([claim in heldout_claims for claim in claims])

    candidates: list[dict[str, float]] = []
    for threshold in np.linspace(0.20, 0.995, 160):
        y = labels[calibration_mask]
        p = probabilities[calibration_mask]
        predicted = p >= threshold
        precision, recall, f1, _ = precision_recall_fscore_support(
            y, predicted, average="binary", zero_division=0
        )
        fpr = float(
            np.mean(predicted[y == 0]) if np.any(y == 0) else 0.0
        )
        candidates.append(
            {
                "threshold": float(threshold),
                "precision": float(precision),
                "recall": float(recall),
                "f1": float(f1),
                "false_positive_rate": fpr,
                "predicted_positive_rate": float(predicted.mean()),
            }
        )

    admissible = [
        row
        for row in candidates
        if row["false_positive_rate"] <= 0.05
        and row["predicted_positive_rate"] > 0
    ]
    if admissible:
        choice = max(
            admissible,
            key=lambda row: (
                row["recall"],
                row["precision"],
                -row["threshold"],
            ),
        )
        policy = "CALIBRATION_FPR_LE_0_05_MAX_RECALL"
    else:
        nonempty = [
            row for row in candidates if row["predicted_positive_rate"] > 0
        ]
        choice = min(
            nonempty,
            key=lambda row: (
                row["false_positive_rate"],
                -row["precision"],
                -row["recall"],
            ),
        )
        policy = "LOWEST_AVAILABLE_FPR"
    threshold = choice["threshold"]

    def metrics(mask: np.ndarray) -> dict[str, float]:
        y = labels[mask]
        p = probabilities[mask]
        predicted = p >= threshold
        precision, recall, f1, _ = precision_recall_fscore_support(
            y, predicted, average="binary", zero_division=0
        )
        return {
            "n": int(mask.sum()),
            "prevalence": float(y.mean()),
            "threshold": float(threshold),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "average_precision": float(average_precision_score(y, p)),
            "roc_auc": float(roc_auc_score(y, p)),
            "false_positive_rate": float(
                np.mean(predicted[y == 0]) if np.any(y == 0) else 0.0
            ),
            "predicted_positive_rate": float(predicted.mean()),
        }

    choice = {**choice, "policy": policy, "target_max_fpr": 0.05}
    return {
        "calibration_choice": choice,
        "calibration": metrics(calibration_mask),
        "heldout": metrics(heldout_mask),
    }


benchmark.evaluate_binary_model = precision_first_evaluate


if __name__ == "__main__":
    raise SystemExit(benchmark.main())
