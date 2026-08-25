import json
from pathlib import Path

import numpy as np
import pytest

from darkpipe.aion import run_aion_validation, validate_aion_evidence
from darkpipe.provenance import sha256_file

ROOT = Path(__file__).parents[1]
EVIDENCE = ROOT / "evidence" / "aion_sensor_validation_2026-08-25"
CHECKED_RUN = EVIDENCE / "run"


@pytest.fixture(scope="session")
def reproduced(tmp_path_factory):
    return run_aion_validation(EVIDENCE, tmp_path_factory.mktemp("aion") / "run")


def test_aion_gate_validates_all_frozen_bytes_and_schemas():
    gate = validate_aion_evidence(EVIDENCE)
    assert gate["passed"], gate["failures"]
    assert len(gate["diagnostics"]["files"]) == 27
    assert all(item["status"] == "ok" for item in gate["diagnostics"]["files"])


def test_aion_preregistered_receipt_reproduces(reproduced):
    checked = json.loads((CHECKED_RUN / "report.json").read_text(encoding="utf-8"))
    assert reproduced["decision"] == checked["decision"] == "PASS_BOUNDED"
    assert reproduced["endpoint_e1"]["passed_count"] == 7
    assert reproduced["endpoint_e2"]["passed"]
    observed = [item["resolution_normalized_error"] for item in reproduced["endpoint_e1"]["datasets"]]
    expected = [item["resolution_normalized_error"] for item in checked["endpoint_e1"]["datasets"]]
    assert np.allclose(observed, expected, rtol=0, atol=1e-15)
    assert np.isclose(
        reproduced["endpoint_e2"]["difference_rad"],
        checked["endpoint_e2"]["difference_rad"],
        rtol=0,
        atol=1e-15,
    )


def test_aion_adverse_and_abstaining_boundaries_are_preserved(reproduced):
    assert "not a dark-matter or gravitational-wave detection" in reproduced["claim_ceiling"]
    assert set(reproduced["not_estimable"]) == {
        "blind-search false-positive rate",
        "global dark-matter or gravitational-wave significance",
        "transfer to AION-10 or AION-km sensitivity",
        "independent full raw-HDF5 marginal-likelihood reproduction",
    }
    assert sum(item["timestamp_nonmonotonic_steps"] for item in reproduced["endpoint_e1"]["datasets"]) > 0


def test_aion_checked_run_manifest_hashes_outputs():
    manifest = json.loads((CHECKED_RUN / "manifest.json").read_text(encoding="utf-8"))
    assert {item["path"] for item in manifest["files"]} == {"report.json", "report.md", "validation.png"}
    for item in manifest["files"]:
        path = CHECKED_RUN / item["path"]
        assert path.stat().st_size == item["byte_count"]
        assert sha256_file(path) == item["sha256"]


def test_license_boundaries_are_explicit():
    project_notice = (ROOT / "LICENSE-NOTICE").read_text(encoding="utf-8")
    assert "SPDX-License-Identifier: GPL-3.0-or-later" in project_notice
    assert "any later version" in project_notice
    notice = (EVIDENCE / "UPSTREAM_NOTICE.md").read_text(encoding="utf-8")
    assert "CC-BY-4.0" in notice
    assert "MIT" in notice
    assert "not relicensed" in notice
