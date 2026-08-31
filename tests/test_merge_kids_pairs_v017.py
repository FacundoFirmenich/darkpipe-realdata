from pathlib import Path

import numpy as np
import pytest

from darkpipe.kids_streaming_pairs import empty_pair_sums, save_pair_partition
import run_merge_kids_pairs_v017 as merger
from run_merge_kids_pairs_v017 import merge_partitions


def _partition(path: Path, start: int, stop: int, value: float, tiles: list[str]) -> None:
    sums = empty_pair_sums(2, 3)
    sums["sum_pair_weight"][:] = value
    sums["pair_count"][:] = int(value)
    save_pair_partition(
        path,
        sums,
        {
            "complete": True,
            "start_row": start,
            "stop_row": stop,
            "source_url": "u",
            "source_total_bytes": 10,
            "lens_count": 2,
            "lens_payload_sha256": "l",
            "sigma_lookup_sha256": "s",
            "radial_edges_mpc_h70": [1, 2, 3, 4],
            "radial_edges_sha256": "r",
            "source_tiles": tiles,
            "diagnostics": {"source_rows": stop - start, "selected_source_rows": 1, "candidate_pairs": 2, "accepted_pairs": 1},
            "authority": "KIDS_OBJECT_PAIR_SUFFICIENT_STATISTICS_NO_MODEL_OR_ONTOLOGY_ADJUDICATION",
        },
    )


def test_partial_contiguous_merge_is_exact(tmp_path: Path) -> None:
    first, second = tmp_path / "a.npz", tmp_path / "b.npz"
    _partition(first, 0, 4, 1.0, ["A"])
    _partition(second, 4, 10, 2.0, ["B"])
    sums, metadata = merge_partitions(
        [second, first], require_complete_surface=False
    )
    np.testing.assert_array_equal(sums["sum_pair_weight"], np.full((2, 3), 3.0))
    assert metadata["source_total_rows"] == 10
    assert metadata["source_tiles"] == ["A", "B"]


def test_gap_is_rejected(tmp_path: Path) -> None:
    first, second = tmp_path / "a.npz", tmp_path / "b.npz"
    _partition(first, 0, 4, 1.0, ["A"])
    _partition(second, 5, 10, 2.0, ["B"])
    with pytest.raises(RuntimeError, match="gap or overlap"):
        merge_partitions([first, second], require_complete_surface=False)


def test_complete_surface_gate_precedes_signal_array_loading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    partition = tmp_path / "incomplete-surface.npz"
    _partition(partition, 0, 2_657_751, 1.0, ["one-tile"])

    def forbidden(_path: Path) -> dict[str, np.ndarray]:
        raise AssertionError("signal arrays were opened before the 988-THELI gate")

    monkeypatch.setattr(merger, "load_partition_sums", forbidden)
    with pytest.raises(RuntimeError, match="frozen eight-part full surface"):
        merger.merge_partitions([partition], require_complete_surface=True)
