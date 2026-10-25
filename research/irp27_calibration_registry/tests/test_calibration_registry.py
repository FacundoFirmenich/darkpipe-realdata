from __future__ import annotations

from calibration_registry import (
    calibration_key,
    expected_calibration_error,
    js_divergence,
    key_id,
    receipt_chain,
    validate_no_cross_cell_transport,
)


def test_key_changes_with_language():
    base = dict(contract_hash="a", provider="p", provider_version="1", checkpoint="c", primitive="choice", domain="d", language="es", hardware="cpu", data_vintage="v", evaluation_mode="shadow")
    es = calibration_key(**base)
    en = calibration_key(**{**base, "language": "en"})
    assert key_id(es) != key_id(en)


def test_perfect_ece():
    assert expected_calibration_error([1.0, 1.0], [1, 1]) == 0.0


def test_js_zero_for_identical_distributions():
    assert js_divergence({"a": 0.7, "b": 0.3}, {"a": 0.7, "b": 0.3}) < 1e-12


def test_receipt_chain_links():
    key = calibration_key(contract_hash="a", provider="p", provider_version="1", checkpoint="c", primitive="choice", domain="d", language="es", hardware="cpu", data_vintage="v", evaluation_mode="shadow")
    cell = {"calibration_id": key_id(key), "key": key, "n": 1, "gold_status": "x", "metrics": {}, "validity": "x", "promotion_status": "BLOCKED", "blockers": ["x"], "automatic_execution": False, "automatic_publication": False}
    receipts = receipt_chain([cell, {**cell, "calibration_id": key_id({**key, "language": "en"}), "key": {**key, "language": "en"}}])
    assert receipts[1]["previous_receipt_hash"] == receipts[0]["receipt_hash"]


def test_unauthorized_promotion_fails_validation():
    key = calibration_key(contract_hash="a", provider="p", provider_version="1", checkpoint="c", primitive="choice", domain="d", language="es", hardware="cpu", data_vintage="v", evaluation_mode="shadow")
    cell = {"calibration_id": key_id(key), "key": key, "n": 1, "gold_status": "x", "metrics": {}, "validity": "x", "promotion_status": "PROMOTED", "blockers": ["x"], "automatic_execution": False, "automatic_publication": False}
    assert any("UNAUTHORIZED_PROMOTION" in error for error in validate_no_cross_cell_transport([cell]))
