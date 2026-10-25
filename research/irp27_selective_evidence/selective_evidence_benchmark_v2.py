#!/usr/bin/env python3
"""Compatibility wrapper for scikit-learn >=1.8.

The core benchmark used the removed `multi_class` constructor argument and a
solver that no longer accepts native multiclass fitting. This wrapper replaces
only the model factory; all splits, calibration, metrics and scientific
boundaries remain unchanged.
"""
from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

import selective_evidence_benchmark as benchmark


def build_model(evidence_only: bool = False) -> Pipeline:
    return Pipeline(
        [
            (
                "features",
                FeatureUnion(
                    [
                        (
                            "word",
                            TfidfVectorizer(
                                ngram_range=(1, 2),
                                min_df=2,
                                max_features=70_000,
                                sublinear_tf=True,
                                strip_accents="unicode",
                            ),
                        ),
                        (
                            "char",
                            TfidfVectorizer(
                                analyzer="char_wb",
                                ngram_range=(3, 5),
                                min_df=3,
                                max_features=70_000,
                                sublinear_tf=True,
                                strip_accents="unicode",
                            ),
                        ),
                    ]
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    max_iter=2_500,
                    class_weight="balanced",
                    solver="lbfgs",
                    random_state=benchmark.SEED,
                ),
            ),
        ]
    )


benchmark.build_model = build_model


if __name__ == "__main__":
    raise SystemExit(benchmark.main())
