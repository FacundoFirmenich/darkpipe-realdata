import inspect
from pathlib import Path

import numpy as np

from darkpipe.aion_blind import (
    _build_design,
    _fit_development_models,
    _load_controls,
    _scan,
)
from darkpipe.aion_continuous import (
    CALIBRATION_SEED,
    ENVIRONMENT_BLOCKS,
    ENVIRONMENT_PERMUTATIONS,
    ENGINEERING_PROBE_FREQUENCIES_HZ,
    EXCLUSION_RAYLEIGH_CELLS,
    FAMILY_ALPHA,
    FREQUENCY_MAX_HZ,
    FREQUENCY_MIN_HZ,
    GRID_OVERSAMPLING,
    MAX_CANDIDATES,
    NULL_SURROGATES,
    _coherence,
    _development_cadence,
    _select_candidates,
    score_frequency_family,
)
from darkpipe.sources import fetch_hapi

ROOT = Path(__file__).parents[1]
EVIDENCE = ROOT / "evidence" / "aion_sensor_validation_2026-08-25"


def test_batched_continuous_score_matches_explicit_profiled_design():
    controls = _load_controls(EVIDENCE)
    models = _fit_development_models(controls)
    frequencies = np.array(ENGINEERING_PROBE_FREQUENCIES_HZ)
    observed = score_frequency_family(
        controls, models, "development", frequencies, batch_size=2
    )
    family = {f"f{index}": float(value) for index, value in enumerate(frequencies)}
    design = _build_design(controls, models, "development", family)
    explicit = {
        item["dataset_id"]: item["statistic"]
        for item in _scan(design["base_y"], design)
    }
    expected = np.array([explicit[f"f{index}"] for index in range(len(frequencies))])
    assert np.allclose(observed, expected, rtol=2.0e-10, atol=2.0e-8)


def test_candidate_selection_is_bounded_separated_and_deterministic():
    rayleigh = 1.0e-5
    frequencies = 5.0e-3 + np.arange(10, dtype=float) * rayleigh
    statistics = np.array([0.0, 9.0, 1.0, 8.0, 0.0, 7.0, 0.0, 6.0, 0.0, 0.0])
    first = _select_candidates(frequencies, statistics, rayleigh_hz=rayleigh)
    second = _select_candidates(frequencies, statistics, rayleigh_hz=rayleigh)
    assert first == second
    assert [item["frequency_hz"] for item in first] == [
        float(frequencies[i]) for i in (1, 3, 5, 7)
    ]
    assert len(first) <= MAX_CANDIDATES
    assert all(
        abs(a["frequency_hz"] - b["frequency_hz"])
        >= EXCLUSION_RAYLEIGH_CELLS * rayleigh
        for index, a in enumerate(first)
        for b in first[index + 1 :]
    )


def test_candidate_selection_excludes_pre_freeze_engineering_probes():
    rayleigh = 1.0e-5
    frequencies = np.array([7.0e-5, 8.0e-5, 9.0e-5, 1.0e-4, 1.1e-4, 1.2e-4, 2.0e-4])
    statistics = np.array([0.0, 1.0, 2.0, 20.0, 2.0, 1.0, 0.0])
    selected = _select_candidates(frequencies, statistics, rayleigh_hz=rayleigh)
    assert selected == []


def test_block_coherence_has_expected_bounds_and_missingness_gate():
    phase = np.exp(1j * np.arange(ENVIRONMENT_BLOCKS))
    assert np.isclose(_coherence(phase, 2.0 * phase), 1.0)
    orthogonal = np.exp(1j * np.arange(ENVIRONMENT_BLOCKS) * 2.0)
    value = _coherence(phase, orthogonal)
    assert 0.0 <= value <= 1.0
    sparse = phase.copy()
    sparse[:3] = complex(np.nan, np.nan)
    assert np.isnan(_coherence(sparse, phase))


def test_v07_protocol_constants_and_hapi_bound_are_frozen():
    assert FREQUENCY_MIN_HZ == 1.0e-4
    assert FREQUENCY_MAX_HZ == 7.5e-2
    cadence = _development_cadence(_load_controls(EVIDENCE))
    nominal_nyquist = min(
        item["nominal_median_nyquist_hz"] for item in cadence.values()
    )
    assert FREQUENCY_MAX_HZ < nominal_nyquist
    assert GRID_OVERSAMPLING == 1
    assert MAX_CANDIDATES == 8
    assert NULL_SURROGATES == 4095
    assert ENVIRONMENT_PERMUTATIONS == 4095
    assert FAMILY_ALPHA == 0.05
    assert CALIBRATION_SEED == 2026082507
    assert "max_bytes" in inspect.signature(fetch_hapi).parameters
    prereg = (
        ROOT / "docs" / "PREREGISTRATION_AION_CONTINUOUS_ENVIRONMENT_0.7.md"
    ).read_text(encoding="utf-8")
    assert "development-only continuous" in prereg
    assert "dark-plasma, dark-matter" in prereg
    assert "OMNI never acts as a causal veto" in prereg
