import hashlib
from pathlib import Path

import numpy as np
import pytest

from darkpipe.aion import INJECTIONS
from darkpipe.aion_blind import (
    CALIBRATION_SEED,
    DEVELOPMENT_FRACTION,
    FAMILY_ALPHA,
    INJECTION_AMPLITUDE_RAD,
    NULL_SURROGATES,
    _challenge_plan,
    _circular_correlations,
    seed_commitment,
)

ROOT = Path(__file__).parents[1]


def test_seed_commitment_requires_exactly_256_bits():
    seed = "01" * 32
    assert seed_commitment(seed) == hashlib.sha256(bytes.fromhex(seed)).hexdigest()
    with pytest.raises(ValueError):
        seed_commitment("01")
    with pytest.raises(ValueError):
        seed_commitment("not-hex")


def test_challenge_plan_is_deterministic_complete_and_opaque():
    frequencies = {name: float(index + 1) for index, name in enumerate(INJECTIONS)}
    plan = _challenge_plan("02" * 32, frequencies)
    assert plan == _challenge_plan("02" * 32, frequencies)
    assert {item["label"] for item in plan} == {"null", *INJECTIONS}
    assert len({item["case_id"] for item in plan}) == 8
    assert all(len(item["case_id"]) == 16 for item in plan)


def test_fft_circular_correlations_match_explicit_rolls():
    residual = np.array([0.2, -0.4, 1.1, 0.7, -0.1])
    z = np.column_stack([np.arange(5.0), np.array([1.0, 0.0, -1.0, 2.0, 0.5])])
    observed = _circular_correlations(z, residual)
    expected_sets = [
        np.array([[column @ np.roll(residual, shift) for column in z.T] for shift in range(5)]),
        np.array([[column @ np.roll(residual, -shift) for column in z.T] for shift in range(5)]),
    ]
    assert any(np.allclose(observed, expected) for expected in expected_sets)


def test_preregistered_constants_are_frozen():
    assert DEVELOPMENT_FRACTION == 0.40
    assert INJECTION_AMPLITUDE_RAD == 0.60
    assert NULL_SURROGATES == 4095
    assert FAMILY_ALPHA == 0.05
    assert CALIBRATION_SEED == 2026082506
    prereg = (ROOT / "docs" / "PREREGISTRATION_AION_BLIND_HOLDOUT_0.6.md").read_text(encoding="utf-8")
    assert "0a1ad503b576ba7ec553d43da1199d2f05c3eb4d8e577e36be8a38d457eb382d" in prereg
    assert "independent repeated-instrument false-positive rate" in prereg
