import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from run_darkpipe_kids_pairs_v017 import (
    load_authoritative_lenses,
    load_checkpoint,
    load_sigma_grid,
)
from darkpipe.kids_streaming_pairs import empty_pair_sums, save_pair_partition


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_lens_payload_gate_and_sigma_interpolation(tmp_path: Path) -> None:
    payload = tmp_path / "lenses.npz"
    arrays = {
        "ra_deg": np.arange(106_843, dtype=float) / 1000,
        "dec_deg": np.zeros(106_843),
        "redshift": np.full(106_843, 0.2),
        "baryonic_mass_msun": np.full(106_843, 1e10),
        "source_row": np.arange(106_843),
    }
    np.savez_compressed(payload, **arrays)
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "valid_native_gaap_rows": 1,
                "bright_rows": 1,
                "angular_geometry_delta": 0,
                "selected_lens_pair_payload": {
                    "count": 106_843,
                    "sha256": _sha256(payload),
                },
            }
        ),
        encoding="utf-8",
    )
    lenses = load_authoritative_lenses(payload, receipt)
    assert lenses.count == 106_843

    lookup = tmp_path / "sigma.csv"
    lookup.write_text(
        "lens_redshift," + ",".join(f"sigma_crit_tomo{i}_msun_mpc2" for i in range(1, 6)) + "\n"
        "0.1,10,20,30,40,50\n0.3,30,40,50,60,70\n",
        encoding="utf-8",
    )
    grid = load_sigma_grid(lookup, np.asarray([0.1, 0.2, 0.3]))
    np.testing.assert_allclose(grid[:, 0], [10, 20, 30])


def test_checkpoint_rejects_content_tampering(tmp_path: Path) -> None:
    target = tmp_path / "part.npz"
    sums = empty_pair_sums(2, 3)
    save_pair_partition(
        target,
        sums,
        {"start_row": 0, "next_row": 1, "stop_row": 2, "chunks": 1, "started_at": "t", "diagnostics": {}},
    )
    restored, metadata = load_checkpoint(target, 0)
    assert metadata["next_row"] == 1
    np.testing.assert_array_equal(restored["pair_count"], sums["pair_count"])

    with np.load(target, allow_pickle=False) as values:
        content = {key: np.asarray(values[key]) for key in values.files}
    content["pair_count"] = content["pair_count"].copy()
    content["pair_count"][0, 0] = 1
    np.savez_compressed(target, **content)
    with pytest.raises(RuntimeError, match="content hash mismatch"):
        load_checkpoint(target, 0)
