from pathlib import Path

import h5py
import numpy as np
import pytest

import darkpipe.aion_independent_search as search


def _write_source(path: Path, *, poison_holdout: bool) -> None:
    rows = 4000
    condition = np.tile(np.array([0, 2]), rows // 2)
    phi = (np.arange(rows) % 100) / 99.0
    timestamp = 1_734_123_000.0 + 8.0 * np.arange(rows)
    forward = 0.5 + 0.35 * np.cos(2.0 * np.pi * phi)
    backward = 0.5 + 0.35 * np.cos(
        2.0 * np.pi * phi + 0.08
    )
    if poison_holdout:
        for value in (0, 2):
            indices = np.flatnonzero(condition == value)
            split = int(0.4 * len(indices))
            forward[indices[split:]] = np.nan
            backward[indices[split:]] = np.nan
    vectors = {
        search.PATHS["phi_turns"]: phi,
        search.PATHS["condition"]: condition,
        search.PATHS["timestamp"]: timestamp,
        search.PATHS["excitation_fraction_forward"]: forward,
        search.PATHS["excitation_fraction_backward"]: backward,
        search.PATHS["atom_number_forward"]: np.full(
            rows, 1_000_000.0
        ),
        search.PATHS["atom_number_backward"]: np.full(
            rows, 800_000.0
        ),
    }
    vectors.update(
        {
            path_name: np.full(
                rows,
                365_344_300.0 if "rigol" in name else 0,
            )
            for name, path_name in search.MONITORS.items()
        }
    )
    with h5py.File(path, "w") as handle:
        handle.create_group("datasets")
        for name, value in vectors.items():
            handle.create_dataset(name, data=value)


def test_development_stage_does_not_read_poisoned_holdout(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(search, "EXPECTED_ROWS", 4000)
    monkeypatch.setattr(search, "MIN_SUBSET_ROWS", 100)
    source = tmp_path / "source.h5"
    _write_source(source, poison_holdout=True)
    controls, quality = search.load_controls(
        source, include_holdout=False
    )
    assert not quality["holdout_excitation_values_accessed"]
    assert all(
        len(controls[condition]["development"]) == 800
        for condition in search.CONDITIONS
    )
    with pytest.raises(ValueError, match="insufficient subset"):
        search.load_controls(source, include_holdout=True)


def test_complete_source_builds_adaptive_safe_grid(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(search, "EXPECTED_ROWS", 4000)
    monkeypatch.setattr(search, "MIN_SUBSET_ROWS", 100)
    source = tmp_path / "source.h5"
    _write_source(source, poison_holdout=False)
    controls, quality = search.load_controls(
        source, include_holdout=True
    )
    frequencies, grid = search.adaptive_grid(
        controls, "development"
    )
    assert quality["holdout_excitation_values_accessed"]
    assert len(frequencies) == grid["count"]
    assert grid["frequency_min_hz"] >= search.FREQUENCY_FLOOR_HZ
    assert grid["frequency_max_hz"] <= min(
        search.FREQUENCY_CEILING_HZ,
        search.NYQUIST_SAFETY_FACTOR
        * min(grid["nominal_median_nyquist_hz"].values()),
    )


def test_candidate_selection_is_bounded_and_separated():
    rayleigh = 1.0e-5
    frequencies = 1.0e-3 + rayleigh * np.arange(12)
    statistics = np.array(
        [0, 9, 0, 8, 0, 7, 0, 6, 0, 5, 0, 0],
        dtype=float,
    )
    candidates = search.select_candidates(
        frequencies, statistics, rayleigh
    )
    assert len(candidates) <= search.MAX_CANDIDATES
    assert [
        item["grid_index"] for item in candidates
    ] == [1, 3, 5, 7, 9]
    assert all(
        abs(a["grid_index"] - b["grid_index"])
        >= search.SEPARATION_RAYLEIGH_CELLS
        for index, a in enumerate(candidates)
        for b in candidates[index + 1 :]
    )


def test_v08_protocol_constants_and_claim_ceiling():
    assert search.NULL_SURROGATES == 4095
    assert search.FAMILY_ALPHA == 0.05
    assert search.POWER_AMPLITUDES_RAD == (0.3, 0.6, 1.2)
    assert search.POWER_PHASES == 16
    prereg = (
        Path(__file__).parents[1]
        / "docs"
        / "PREREGISTRATION_AION_INDEPENDENT_EPOCH_0.8.md"
    ).read_text(encoding="utf-8")
    assert "NO_MACHINE_READABLE_REUSE_LICENSE_DECLARED" in prereg
    assert "no es una detección física" in prereg.lower()
    assert "dos épocas" in prereg
    assert "GPL-3.0-or-later" in prereg
