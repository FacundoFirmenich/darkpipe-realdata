from __future__ import annotations

import unittest

from noncollapse_engine import (
    DIMENSIONS,
    DimensionState,
    ForbiddenAggregationError,
    Relation,
    binding_constraints,
    pareto_relation,
    scalar_score,
    scenario_projection,
)


def state(value: float | None) -> DimensionState:
    return DimensionState(value, value, value, value, value)


def profile(values: dict[str, float | None]):
    return {dimension: state(values[dimension]) for dimension in DIMENSIONS}


class NonCollapseTests(unittest.TestCase):
    def test_no_default_scalar(self) -> None:
        with self.assertRaises(ForbiddenAggregationError):
            scalar_score(profile({d: 0.8 for d in DIMENSIONS}))

    def test_credit_cannot_erase_food_constraint(self) -> None:
        p = profile({d: 0.8 for d in DIMENSIONS})
        p["food"] = state(0.25)
        p["credit"] = state(1.0)
        thresholds = {d: 0.5 for d in DIMENSIONS}
        self.assertEqual({"food": "BINDING"}, binding_constraints(p, thresholds))

    def test_missing_food_blocks_scenario(self) -> None:
        p = profile({d: 0.8 for d in DIMENSIONS})
        p["food"] = state(None)
        result = scenario_projection(p, {d: 1.0 for d in DIMENSIONS}, "sensitivity only")
        self.assertEqual("BLOCKED_MISSING_DIMENSION", result["status"])
        self.assertEqual("NONE", result["authority"])

    def test_tradeoffs_are_incomparable(self) -> None:
        a = profile({d: 0.7 for d in DIMENSIONS})
        b = profile({d: 0.7 for d in DIMENSIONS})
        a["food"] = state(0.9); a["housing"] = state(0.4)
        b["food"] = state(0.5); b["housing"] = state(0.8)
        self.assertEqual(Relation.INCOMPARABLE, pareto_relation(a, b))

    def test_dominance_requires_no_worse_facet(self) -> None:
        a = profile({d: 0.8 for d in DIMENSIONS})
        b = profile({d: 0.7 for d in DIMENSIONS})
        self.assertEqual(Relation.DOMINATES, pareto_relation(a, b))

    def test_weighted_view_has_no_authority(self) -> None:
        p = profile({d: 0.8 for d in DIMENSIONS})
        result = scenario_projection(p, {d: 1.0 for d in DIMENSIONS}, "transparent sensitivity")
        self.assertEqual("EXPLORATORY_SCENARIO_ONLY", result["status"])
        self.assertEqual("NONE", result["authority"])


if __name__ == "__main__":
    unittest.main()
