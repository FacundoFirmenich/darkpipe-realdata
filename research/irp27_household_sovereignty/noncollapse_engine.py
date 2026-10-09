"""Non-compensatory household material sovereignty engine.

The engine preserves seven autonomous dimensions: real disposable income, food,
energy, housing, care, debt burden and access to useful credit. It provides
Pareto comparison, binding-constraint detection and explicit scenario analysis.
It deliberately refuses to manufacture a default scalar household score.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

DIMENSIONS = ("real_income", "food", "energy", "housing", "care", "debt", "credit")
FACETS = ("affordability", "adequacy", "access", "stability", "agency")


class ForbiddenAggregationError(ValueError):
    pass


class Relation(str, Enum):
    DOMINATES = "DOMINATES"
    DOMINATED = "DOMINATED"
    EQUIVALENT = "EQUIVALENT"
    INCOMPARABLE = "INCOMPARABLE"
    UNDETERMINED = "UNDETERMINED"


@dataclass(frozen=True)
class DimensionState:
    affordability: float | None
    adequacy: float | None
    access: float | None
    stability: float | None
    agency: float | None
    uncertainty: float = 0.0

    def known(self) -> bool:
        return all(getattr(self, facet) is not None for facet in FACETS)

    def minimum(self) -> float | None:
        vals = [getattr(self, facet) for facet in FACETS]
        return min(vals) if self.known() else None


Profile = Mapping[str, DimensionState]


def validate_profile(profile: Profile) -> None:
    missing = [name for name in DIMENSIONS if name not in profile]
    if missing:
        raise ValueError(f"missing dimensions: {','.join(missing)}")
    for name, state in profile.items():
        if name not in DIMENSIONS:
            raise ValueError(f"unknown dimension: {name}")
        for facet in FACETS:
            value = getattr(state, facet)
            if value is not None and not 0.0 <= value <= 1.0:
                raise ValueError(f"{name}.{facet} outside [0,1]")
        if not 0.0 <= state.uncertainty <= 1.0:
            raise ValueError(f"{name}.uncertainty outside [0,1]")


def binding_constraints(profile: Profile, thresholds: Mapping[str, float]) -> dict[str, str]:
    """Return unknown or threshold-breaching dimensions; no compensation allowed."""
    validate_profile(profile)
    result: dict[str, str] = {}
    for dimension in DIMENSIONS:
        minimum = profile[dimension].minimum()
        if minimum is None:
            result[dimension] = "UNKNOWN"
        elif minimum < thresholds[dimension]:
            result[dimension] = "BINDING"
    return result


def pareto_relation(a: Profile, b: Profile, tolerance: float = 1e-12) -> Relation:
    """Compare complete profiles without weights or compensation."""
    validate_profile(a); validate_profile(b)
    pairs: list[tuple[float, float]] = []
    for dimension in DIMENSIONS:
        for facet in FACETS:
            av = getattr(a[dimension], facet)
            bv = getattr(b[dimension], facet)
            if av is None or bv is None:
                return Relation.UNDETERMINED
            pairs.append((av, bv))
    a_ge = all(av + tolerance >= bv for av, bv in pairs)
    b_ge = all(bv + tolerance >= av for av, bv in pairs)
    a_gt = any(av > bv + tolerance for av, bv in pairs)
    b_gt = any(bv > av + tolerance for av, bv in pairs)
    if a_ge and a_gt: return Relation.DOMINATES
    if b_ge and b_gt: return Relation.DOMINATED
    if a_ge and b_ge: return Relation.EQUIVALENT
    return Relation.INCOMPARABLE


def scalar_score(*_args, **_kwargs) -> float:
    raise ForbiddenAggregationError(
        "No default scalar score exists: food, care, housing, energy, debt, credit and income are non-compensatory."
    )


def scenario_projection(profile: Profile, explicit_weights: Mapping[str, float], rationale: str) -> dict:
    """Exploratory-only weighted view, never an authority-bearing household index."""
    validate_profile(profile)
    if not rationale.strip():
        raise ValueError("scenario rationale is required")
    if set(explicit_weights) != set(DIMENSIONS):
        raise ValueError("explicit weights required for all seven dimensions")
    if any(weight < 0 for weight in explicit_weights.values()):
        raise ValueError("weights must be non-negative")
    total = sum(explicit_weights.values())
    if total <= 0:
        raise ValueError("positive total weight required")
    values = {d: profile[d].minimum() for d in DIMENSIONS}
    if any(value is None for value in values.values()):
        return {"status": "BLOCKED_MISSING_DIMENSION", "authority": "NONE", "rationale": rationale}
    score = sum(explicit_weights[d] * float(values[d]) for d in DIMENSIONS) / total
    return {
        "status": "EXPLORATORY_SCENARIO_ONLY",
        "score": score,
        "authority": "NONE",
        "rationale": rationale,
        "weights": dict(explicit_weights),
        "warning": "This scenario cannot target households, rank policies or erase binding constraints.",
    }
