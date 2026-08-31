#!/usr/bin/env python3
"""Merge and validate the eight exact KiDS source tile-index partitions."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from darkpipe.kids_random_catalogue import EXPECTED_SOURCE_THELI_TILE_COUNT
from darkpipe.kids_source_tile_index import (
    SOURCE_TILE_INDEX_AUTHORITY,
    merge_partition_runs,
    read_json_document,
    tile_run_counts,
    tile_runs_sha256,
    write_json_document,
)
from run_darkpipe_kids_pairs_v017 import SOURCE_TOTAL_BYTES, SOURCE_TOTAL_ROWS, SOURCE_URL


FROZEN_INTERVALS = [
    (0, 2_657_751),
    (2_657_751, 5_315_502),
    (5_315_502, 7_973_254),
    (7_973_254, 10_631_005),
    (10_631_005, 13_288_756),
    (13_288_756, 15_946_508),
    (15_946_508, 18_604_259),
    (18_604_259, SOURCE_TOTAL_ROWS),
]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def merge_index_payloads(payloads: list[dict[str, object]]) -> dict[str, object]:
    for payload in payloads:
        if payload.get("authority") != SOURCE_TILE_INDEX_AUTHORITY:
            raise RuntimeError("unexpected tile-index authority")
        if payload.get("source_url") != SOURCE_URL or int(payload.get("source_total_bytes", -1)) != SOURCE_TOTAL_BYTES:
            raise RuntimeError("tile-index source identity mismatch")
        if tile_runs_sha256(payload.get("runs", [])) != payload.get("runs_sha256"):
            raise RuntimeError("tile-index partition content hash mismatch")
    runs, intervals = merge_partition_runs(payloads)
    if intervals != FROZEN_INTERVALS:
        raise RuntimeError("tile index is not the frozen eight-part full surface")
    counts = tile_run_counts(runs)
    if sum(counts.values()) != SOURCE_TOTAL_ROWS:
        raise RuntimeError("tile index does not cover all source rows exactly")
    if len(counts) != EXPECTED_SOURCE_THELI_TILE_COUNT:
        raise RuntimeError(
            f"tile index contains {len(counts)} THELI names; expected {EXPECTED_SOURCE_THELI_TILE_COUNT}"
        )
    return {
        "schema": "darkpipe.kids-source-tile-index.v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "complete": True,
        "source_url": SOURCE_URL,
        "source_total_bytes": SOURCE_TOTAL_BYTES,
        "source_total_rows": SOURCE_TOTAL_ROWS,
        "partition_intervals": intervals,
        "partition_count": len(intervals),
        "run_count": len(runs),
        "unique_tile_count": len(counts),
        "tile_row_counts": counts,
        "runs_sha256": tile_runs_sha256(runs),
        "runs": runs,
        "authority": SOURCE_TILE_INDEX_AUTHORITY,
        "scientific_result": False,
        "next_gate": "BOUNDED_AUTHENTIC_RANDOM_TILE_CONTROL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("partitions", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    partition_payloads = [
        read_json_document(path) for path in args.partitions
    ]
    payload = merge_index_payloads(partition_payloads)
    payload["partition_artifacts"] = sorted(
        (
            {
                "name": path.name,
                "bytes": path.stat().st_size,
                "file_sha256": file_sha256(path),
                "runs_sha256": partition["runs_sha256"],
                "start_row": int(partition["start_row"]),
                "stop_row": int(partition["stop_row"]),
            }
            for path, partition in zip(args.partitions, partition_payloads, strict=True)
        ),
        key=lambda item: int(item["start_row"]),
    )
    write_json_document(args.output, payload)
    print(json.dumps({key: payload[key] for key in payload if key not in {"runs", "tile_row_counts"}}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
