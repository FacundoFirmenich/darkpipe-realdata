from __future__ import annotations

from calibration_registry import (
    expected_calibration_error,
    js_divergence,
    key_id,
    receipt_chain,
    validate_no_cross_cell_transport,
)
from calibration_registry_v2 import calibration_key


def base_key() -> dict[str, str]:
    return dict(
        contract_hash="a",
        provider="p",
        provider_version="1",
        checkpoint="c",
        question_id="relation",
        primitive="choice",
        domain="d",
        language="es",
        hardware="cpu",
        data_vintage="v",
        evaluation_mode="shadow",
    )


def test_key_changes_with_language():
    base = base_key()
    es = calibration_key(**base)
    en = calibration_key(**{**base, "language": "en"})
    assert key_id(es) != key_id(en)


def test_key_changes_with_question_estimand():
    base = base_key()
    supports = calibration_key(**{**base, "question_id": "supports", "primitive": "noul"})
    refutes = calibration_key(**{**base, "question_id": "refutes", "primitive": "noul"})
    assert key_id(supports) != key_id(refutes)


def test_perfect_ece():
    assert expected_calibration_error([1.0, 1.0], [1, 1]) == 0.0


def test_js_zero_for_identical_distributions():
    assert js_divergence({"a": 0.7, "b": 0.3}, {"a": 0.7, "b": 0.3}) < 1e-12


def test_receipt_chain_links():
    key = calibration_key(**base_key())
    cell = {"calibration_id": key_id(key), "key": key, "n": 1, "gold_status": "x", "metrics": {}, "validity": "x", "promotion_status": "BLOCKED", "blockers": ["x"], "automatic_execution": False, "automatic_publication": False}
    en_key = {**key, "language": "en"}
    receipts = receipt_chain([cell, {**cell, "calibration_id": key_id(en_key), "key": en_key}])
    assert receipts[1]["previous_receipt_hash"] == receipts[0]["receipt_hash"]


def test_unauthorized_promotion_fails_validation():
    key = calibration_key(**base_key())
    cell = {"calibration_id": key_id(key), "key": key, "n": 1, "gold_status": "x", "metrics": {}, "validity": "x", "promotion_status": "PROMOTED", "blockers": ["x"], "automatic_execution": False, "automatic_publication": False}
    assert any("UNAUTHORIZED_PROMOTION" in error for error in validate_no_cross_cell_transport([cell]))
