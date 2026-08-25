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


@pytest.fixture(scope="session")
def reproduced_blind(tmp_path_factory):
    import json

    from darkpipe.aion_blind import (
        analyze_blind_challenge,
        prepare_blind_challenge,
        reveal_blind_challenge,
    )

    checked = ROOT / "evidence" / "aion_blind_holdout_2026-08-25"
    evidence = ROOT / "evidence" / "aion_sensor_validation_2026-08-25"
    seed = json.loads((checked / "seed_reveal.json").read_text(encoding="utf-8"))["seed_hex"]
    target = tmp_path_factory.mktemp("aion_blind") / "campaign"
    prepare_blind_challenge(evidence, target, seed, "dbd2da7")
    analyze_blind_challenge(evidence, target)
    return reveal_blind_challenge(target, seed)


def test_checked_blind_campaign_reproduces(reproduced_blind):
    import json

    checked = json.loads(
        (ROOT / "evidence" / "aion_blind_holdout_2026-08-25" / "report.json").read_text(
            encoding="utf-8"
        )
    )
    assert reproduced_blind["decision"] == checked["decision"] == "PASS_BOUNDED"
    assert reproduced_blind["gates"] == checked["gates"]
    observed = [
        (
            item["label"],
            item["prediction"]["peak_dataset_id"],
            item["prediction"]["global_p"],
            item["passed"],
        )
        for item in reproduced_blind["cases"]
    ]
    expected = [
        (
            item["label"],
            item["prediction"]["peak_dataset_id"],
            item["prediction"]["global_p"],
            item["passed"],
        )
        for item in checked["cases"]
    ]
    assert observed == expected


def test_checked_blind_manifest_hashes_every_material_file():
    import json

    from darkpipe.provenance import sha256_file

    checked = ROOT / "evidence" / "aion_blind_holdout_2026-08-25"
    manifest = json.loads((checked / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["files"]) == 7
    for item in manifest["files"]:
        path = checked / item["path"]
        assert path.stat().st_size == item["byte_count"]
        assert sha256_file(path) == item["sha256"]


def test_blind_temporal_and_authority_boundaries_are_preserved():
    import json

    checked = ROOT / "evidence" / "aion_blind_holdout_2026-08-25"
    sealed = json.loads((checked / "sealed_manifest.json").read_text(encoding="utf-8"))
    predictions = json.loads((checked / "blind_predictions.json").read_text(encoding="utf-8"))
    report = json.loads((checked / "report.json").read_text(encoding="utf-8"))
    assert sealed["preregistration_commit"] == "dbd2da7"
    assert sealed["mapping_disclosed"] is False
    assert predictions["mapping_accessed"] is False
    statuses = {item["claim_id"]: item["status"] for item in report["claim_ledger"]}
    assert statuses["fixed_grid_signal_identification_0p6rad"] == "SUPPORTED"
    assert statuses["continuous_band_blind_search"] == "NOT_ESTIMABLE"
    assert statuses["dark_matter_or_gravitational_wave_detection"] == "NOT_ESTIMABLE"
