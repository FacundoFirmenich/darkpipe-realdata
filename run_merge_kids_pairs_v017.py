#!/usr/bin/env python3
"""Validate and merge v0.17 KiDS pair partitions without raw-catalogue custody."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from darkpipe.kids_random_catalogue import EXPECTED_SOURCE_THELI_TILE_COUNT
from darkpipe.kids_streaming_pairs import (
    STREAMING_PAIR_AUTHORITY,
    merge_pair_sums,
    pair_sums_sha256,
    save_pair_partition,
)
from run_darkpipe_kids_pairs_v017 import SOURCE_TOTAL_ROWS


PAIR_KEYS = (
    "sum_pair_weight",
    "sum_tangential",
    "sum_cross",
    "sum_shape_variance",
    "pair_count",
)


def load_partition_metadata(path: Path) -> dict[str, object]:
    with np.load(path, allow_pickle=False) as values:
        metadata = json.loads(str(values["metadata_json"]))
    if not metadata.get("complete"):
        raise RuntimeError(f"incomplete partition: {path}")
    if metadata.get("authority") != STREAMING_PAIR_AUTHORITY:
        raise RuntimeError(f"unexpected partition authority: {path}")
    return metadata


def load_partition_sums(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as values:
        sums = {key: np.asarray(values[key]).copy() for key in PAIR_KEYS}
        stored_hash = str(values["content_sha256"])
    if pair_sums_sha256(sums) != stored_hash:
        raise RuntimeError(f"pair-sum hash mismatch: {path}")
    return sums


def load_partition(path: Path) -> tuple[dict[str, np.ndarray], dict[str, object]]:
    """Compatibility entry point; metadata authority is checked before arrays."""

    metadata = load_partition_metadata(path)
    return load_partition_sums(path), metadata


def merge_partitions(
    paths: list[Path], *, require_complete_surface: bool = True
) -> tuple[dict[str, np.ndarray], dict[str, object]]:
    if not paths:
        raise ValueError("at least one partition is required")
    metadata_only = [(path, load_partition_metadata(path)) for path in paths]
    metadata_only.sort(key=lambda item: int(item[1]["start_row"]))
    intervals = [
        (int(metadata["start_row"]), int(metadata["stop_row"]))
        for _, metadata in metadata_only
    ]
    for previous, current in zip(intervals, intervals[1:], strict=False):
        if previous[1] != current[0]:
            raise RuntimeError(f"partition gap or overlap: {previous} then {current}")
    if require_complete_surface and intervals != [
        (0, 2_657_751),
        (2_657_751, 5_315_502),
        (5_315_502, 7_973_254),
        (7_973_254, 10_631_005),
        (10_631_005, 13_288_756),
        (13_288_756, 15_946_508),
        (15_946_508, 18_604_259),
        (18_604_259, SOURCE_TOTAL_ROWS),
    ]:
        raise RuntimeError("partition set is not the frozen eight-part full surface")
    reference = metadata_only[0][1]
    invariant_keys = (
        "source_url",
        "source_total_bytes",
        "lens_count",
        "lens_payload_sha256",
        "sigma_lookup_sha256",
        "radial_edges_mpc_h70",
        "radial_edges_sha256",
    )
    for _, metadata in metadata_only[1:]:
        for key in invariant_keys:
            if metadata.get(key) != reference.get(key):
                raise RuntimeError(f"partition invariant differs: {key}")
    tiles = sorted(
        {tile for _, metadata in metadata_only for tile in metadata.get("source_tiles", [])}
    )
    if require_complete_surface and len(tiles) != EXPECTED_SOURCE_THELI_TILE_COUNT:
        raise RuntimeError(
            f"full THELI source-tile union is {len(tiles)}, "
            f"expected {EXPECTED_SOURCE_THELI_TILE_COUNT}"
        )
    diagnostics = {
        key: sum(int(metadata["diagnostics"][key]) for _, metadata in metadata_only)
        for key in reference["diagnostics"]
    }
    # Signal arrays are opened only after the complete blind metadata surface
    # and every cross-partition invariant have passed.
    merged = merge_pair_sums([load_partition_sums(path) for path, _ in metadata_only])
    metadata = {
        "schema": "darkpipe.kids-pair-merged.v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "complete": require_complete_surface,
        "partition_intervals": intervals,
        "partition_count": len(intervals),
        "source_url": reference["source_url"],
        "source_total_bytes": reference["source_total_bytes"],
        "source_total_rows": sum(stop - start for start, stop in intervals),
        "diagnostics": diagnostics,
        "source_tile_count": len(tiles),
        "source_tiles": tiles,
        "lens_count": reference["lens_count"],
        "lens_payload_sha256": reference["lens_payload_sha256"],
        "sigma_lookup_sha256": reference["sigma_lookup_sha256"],
        "radial_edges_mpc_h70": reference["radial_edges_mpc_h70"],
        "radial_edges_sha256": reference["radial_edges_sha256"],
        "authority": STREAMING_PAIR_AUTHORITY,
        "scientific_result": False,
        "next_gate": "SEAL_1006_TILE_RANDOMS_THEN_RANDOM_COVARIANCE_DEPROJECT_FIRST_RAR",
    }
    return merged, metadata


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("partitions", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    sums, metadata = merge_partitions(args.partitions)
    save_pair_partition(args.output, sums, metadata)
    print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
