"""Exact row-run index for the remote KiDS DR4.1 source catalogue.

The index records only contiguous ``THELI_NAME`` row intervals.  It is a
transport/geometry aid for bounded random-coordinate controls; it contains no
lensing signal and has no scientific adjudication authority.
"""

from __future__ import annotations

import hashlib
import json
from typing import Iterable, Mapping

import numpy as np


SOURCE_TILE_INDEX_AUTHORITY = "REMOTE_ROW_GEOMETRY_INDEX_NO_SCIENTIFIC_RESULT"


def extend_tile_runs(
    runs: list[dict[str, object]], names: np.ndarray, first_row: int
) -> None:
    """Append exact contiguous name runs, coalescing across chunk boundaries."""

    values = np.asarray(names)
    if values.ndim != 1:
        raise ValueError("THELI_NAME must be one-dimensional")
    if first_row < 0:
        raise ValueError("first_row must be non-negative")
    if len(values) == 0:
        return
    decoded = np.char.strip(values.astype("U"))
    if np.any(decoded == ""):
        raise ValueError("THELI_NAME contains an empty value")
    changes = np.flatnonzero(decoded[1:] != decoded[:-1]) + 1
    starts = np.concatenate(([0], changes))
    stops = np.concatenate((changes, [len(decoded)]))
    for local_start, local_stop in zip(starts, stops, strict=True):
        tile = str(decoded[int(local_start)])
        start = first_row + int(local_start)
        stop = first_row + int(local_stop)
        if runs and runs[-1]["tile"] == tile and int(runs[-1]["stop_row"]) == start:
            runs[-1]["stop_row"] = stop
        else:
            if runs and int(runs[-1]["stop_row"]) != start:
                raise ValueError("tile-run stream is not row-contiguous")
            runs.append({"tile": tile, "start_row": start, "stop_row": stop})


def merge_partition_runs(
    partitions: Iterable[Mapping[str, object]],
) -> tuple[list[dict[str, object]], list[tuple[int, int]]]:
    """Validate ordered partitions and merge adjacent equal-tile runs."""

    ordered = sorted(partitions, key=lambda item: int(item["start_row"]))
    if not ordered:
        raise ValueError("at least one tile-index partition is required")
    merged: list[dict[str, object]] = []
    intervals: list[tuple[int, int]] = []
    expected_start = int(ordered[0]["start_row"])
    for partition in ordered:
        start = int(partition["start_row"])
        stop = int(partition["stop_row"])
        if start != expected_start or stop <= start:
            raise ValueError("tile-index partitions contain a gap, overlap, or empty interval")
        if not bool(partition.get("complete")):
            raise ValueError("tile-index partition is incomplete")
        intervals.append((start, stop))
        expected_start = stop
        for run in partition.get("runs", []):
            tile = str(run["tile"])
            run_start = int(run["start_row"])
            run_stop = int(run["stop_row"])
            if run_stop <= run_start:
                raise ValueError("tile run is empty or reversed")
            if merged and int(merged[-1]["stop_row"]) != run_start:
                raise ValueError("tile runs do not cover the partition surface exactly")
            if merged and merged[-1]["tile"] == tile:
                merged[-1]["stop_row"] = run_stop
            else:
                merged.append(
                    {"tile": tile, "start_row": run_start, "stop_row": run_stop}
                )
    if int(merged[0]["start_row"]) != intervals[0][0] or int(merged[-1]["stop_row"]) != intervals[-1][1]:
        raise ValueError("merged tile runs do not span the partition surface")
    return merged, intervals


def tile_run_counts(runs: Iterable[Mapping[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for run in runs:
        tile = str(run["tile"])
        counts[tile] = counts.get(tile, 0) + int(run["stop_row"]) - int(run["start_row"])
    return counts


def tile_runs_sha256(runs: Iterable[Mapping[str, object]]) -> str:
    payload = json.dumps(list(runs), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "SOURCE_TILE_INDEX_AUTHORITY",
    "extend_tile_runs",
    "merge_partition_runs",
    "tile_run_counts",
    "tile_runs_sha256",
]
