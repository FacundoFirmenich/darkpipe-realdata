import copy

import numpy as np
import pytest

from darkpipe.kids_source_tile_index import (
    extend_tile_runs,
    merge_partition_runs,
    tile_run_counts,
    tile_runs_sha256,
)


def test_extend_tile_runs_coalesces_across_chunks() -> None:
    runs: list[dict[str, object]] = []
    extend_tile_runs(runs, np.asarray([b"A ", b"A ", b"B "]), 10)
    extend_tile_runs(runs, np.asarray([b"B ", b"C "]), 13)
    assert runs == [
        {"tile": "A", "start_row": 10, "stop_row": 12},
        {"tile": "B", "start_row": 12, "stop_row": 14},
        {"tile": "C", "start_row": 14, "stop_row": 15},
    ]
    assert tile_run_counts(runs) == {"A": 2, "B": 2, "C": 1}


def test_merge_partition_runs_coalesces_partition_boundary() -> None:
    first = {
        "start_row": 0,
        "stop_row": 3,
        "complete": True,
        "runs": [
            {"tile": "A", "start_row": 0, "stop_row": 2},
            {"tile": "B", "start_row": 2, "stop_row": 3},
        ],
    }
    second = {
        "start_row": 3,
        "stop_row": 5,
        "complete": True,
        "runs": [
            {"tile": "B", "start_row": 3, "stop_row": 4},
            {"tile": "C", "start_row": 4, "stop_row": 5},
        ],
    }
    merged, intervals = merge_partition_runs([second, first])
    assert intervals == [(0, 3), (3, 5)]
    assert merged[1] == {"tile": "B", "start_row": 2, "stop_row": 4}


def test_hash_and_gap_validation_are_sensitive() -> None:
    runs = [{"tile": "A", "start_row": 0, "stop_row": 2}]
    changed = copy.deepcopy(runs)
    changed[0]["stop_row"] = 3
    assert tile_runs_sha256(runs) != tile_runs_sha256(changed)
    with pytest.raises(ValueError, match="gap"):
        merge_partition_runs(
            [
                {"start_row": 0, "stop_row": 2, "complete": True, "runs": runs},
                {
                    "start_row": 3,
                    "stop_row": 4,
                    "complete": True,
                    "runs": [{"tile": "B", "start_row": 3, "stop_row": 4}],
                },
            ]
        )
