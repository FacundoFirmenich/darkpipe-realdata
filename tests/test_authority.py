import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from darkpipe.aion import run_aion_validation
from darkpipe.provenance import sha256_file
from darkpipe.authority import (
    AuthorityError,
    ClaimKind,
    ClaimLedger,
    ClaimStatus,
    ConducenceVector,
    ObservationEnvelope,
    ObservedDecoupling,
)

ROOT = Path(__file__).parents[1]
EVIDENCE = ROOT / "evidence" / "aion_sensor_validation_2026-08-25"


def test_observation_envelope_declares_regime_and_time_basis():
    envelope = ObservationEnvelope(
        envelope_id="window",
        source="provider",
        observable="field",
        time_start="2026-08-25T00:00:00Z",
        time_stop="2026-08-25T01:00:00Z",
        time_basis="UTC",
        scale="one minute",
        layer="environment",
        resolution="60 s",
        preprocessing=("alignment",),
        provenance_refs=("sha256:abc",),
    )
    payload = envelope.to_dict()
    assert payload["time_basis"] == "UTC"
    assert payload["preprocessing"] == ["alignment"]
    with pytest.raises(ValueError, match="must not follow"):
        ObservationEnvelope(
            envelope_id="bad",
            source="provider",
            observable="field",
            time_start="2026-08-26",
            time_stop="2026-08-25",
            time_basis="UTC",
            scale="minute",
            layer="environment",
            resolution="60 s",
        )


def test_observed_decoupling_cannot_encode_unobserved_interpretation():
    observed = ObservedDecoupling(
        decoupling_id="d1",
        left="A",
        right="B",
        statistic="difference",
        value=1.5,
        unit="rad",
        envelope_refs=("window",),
    ).to_dict()
    assert set(observed).isdisjoint(
        {"cause", "duration", "meaning", "intent", "provisionality"}
    )


@pytest.mark.parametrize(
    "kind",
    [
        ClaimKind.CAUSAL,
        ClaimKind.DETECTION,
        ClaimKind.GENERALIZATION,
        ClaimKind.INTERVENTION,
    ],
)
def test_observational_receipt_refuses_non_observational_promotion(kind):
    ledger = ClaimLedger("bounded window")
    with pytest.raises(AuthorityError, match="cannot automatically promote"):
        ledger.observational_promotion(
            claim_id=f"forbidden.{kind.value.lower()}",
            statement="unsupported promotion",
            kind=kind,
            status=ClaimStatus.SUPPORTED,
            evidence_refs=("statistic",),
        )


def test_unresolved_claim_is_retained_not_deleted_or_promoted():
    ledger = ClaimLedger("bounded window")
    claim = ledger.retain_unresolved(
        claim_id="future.claim",
        statement="A future claim remains available for later testing.",
        kind=ClaimKind.DETECTION,
        blocking_reasons=("blind null campaign absent",),
        evidence_refs=("current-window",),
    )
    assert claim.status is ClaimStatus.NOT_ESTIMABLE
    assert claim.future_only
    assert ledger.to_dict()["automatic_promotion"] is False


def test_conducence_is_contextual_vector_not_scalar():
    vector = ConducenceVector(
        context={"campaign": "test", "site": "BOU"},
        axes={
            "integrity": ClaimStatus.SUPPORTED,
            "detection": ClaimStatus.NOT_ESTIMABLE,
        },
    )
    assert vector.to_dict()["scalar_summary"] is None
    with pytest.raises(AuthorityError, match="scalar collapse"):
        vector.scalar_score()


def test_aion_v05_adds_authority_without_changing_v04_endpoint_values(tmp_path):
    report = run_aion_validation(EVIDENCE, tmp_path / "run")
    checked = json.loads(
        (EVIDENCE / "run" / "report.json").read_text(encoding="utf-8")
    )
    assert report["software_version"] == "0.5.0"
    assert report["decision"] == checked["decision"] == "PASS_BOUNDED"
    assert report["endpoint_e1"] == checked["endpoint_e1"]
    assert report["endpoint_e2"] == checked["endpoint_e2"]

    authority = report["authority"]
    records = {
        item["claim_id"]: item for item in authority["claim_ledger"]["records"]
    }
    assert records["aion.injected_frequency_recovery"]["status"] == "SUPPORTED"
    assert records["aion.hln_lln_interval"]["status"] == "OBSERVED"
    assert records["aion.added_laser_noise_no_effect"]["status"] == "NOT_ESTIMABLE"
    assert records["aion.dark_sector_detection"]["kind"] == "DETECTION"
    assert records["aion.dark_sector_detection"]["status"] == "NOT_ESTIMABLE"
    assert authority["claim_ledger"]["automatic_promotion"] is False
    assert "provisionality" in authority["forbidden_automatic_inferences"]


def test_native_thread_manifest_is_valid_and_does_not_overclaim_transport():
    manifest = json.loads(
        (ROOT / "evidence" / "native_thread_trace_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["transport"]["page_count"] == 13
    assert manifest["transport"]["unique_turn_count"] == 116
    assert manifest["transport"]["message_item_count"] == 221
    assert manifest["transport"]["truncated_item_count"] == 1
    assert manifest["transport"]["complete_transport"] is False
    adverse = manifest["transport"]["adverse_records"]
    assert adverse[0]["retained_characters"] == 20000
    assert "conversation_id_sha256" in manifest["sources"][0]
    assert "conversation_id" not in manifest["sources"][0]
    assert manifest["publication_policy"]["raw_conversation_pages"].startswith(
        "private local custody"
    )


def test_project_license_remains_gpl_v3_or_later_not_only():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    notice = (ROOT / "LICENSE-NOTICE").read_text(encoding="utf-8")
    assert 'license = "GPL-3.0-or-later"' in pyproject
    assert "SPDX-License-Identifier: GPL-3.0-or-later" in notice
    assert "GPL-3.0-only" not in pyproject


def test_repository_manifest_hashes_every_published_file():
    manifest = json.loads(
        (ROOT / "evidence" / "repository_file_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["file_count"] == len(manifest["files"])
    assert manifest["file_count"] >= 90
    assert manifest["total_bytes"] == sum(
        item["byte_count"] for item in manifest["files"]
    )
    assert all(not item["path"].startswith("evidence/native_threads/") for item in manifest["files"])
    assert manifest["byte_domain"].startswith("exact Git index blobs")
    for item in manifest["files"]:
        payload = subprocess.check_output(
            ["git", "show", f":{item['path']}"], cwd=ROOT
        )
        assert len(payload) == item["byte_count"]
        assert hashlib.sha256(payload).hexdigest() == item["sha256"]
