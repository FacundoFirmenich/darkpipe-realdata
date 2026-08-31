from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "kids_native_lens_v016_complete"


def test_native_gaap_successor_closes_published_lens_count() -> None:
    receipt = json.loads((EVIDENCE / "run_receipt.json").read_text(encoding="utf-8"))
    assert receipt["authority"] == (
        "NATIVE_GAAP_RECOVERY_AND_LENS_SELECTION_RECONSTRUCTION_NO_LENSING_RESULT"
    )
    assert receipt["bright_rows"] == 1_239_422
    assert receipt["matched_rows"] == receipt["bright_rows"]
    assert receipt["valid_native_gaap_rows"] == receipt["bright_rows"]
    assert receipt["matched_fraction"] == 1.0
    assert receipt["hybrid_reconstructed_fallback_rows"] == 0
    assert receipt["angular_diameter_cartesian_geometry_count"] == 106_843
    assert receipt["published_target_count"] == 106_843
    assert receipt["angular_geometry_delta"] == 0
    assert receipt["scientific_result"] is False
