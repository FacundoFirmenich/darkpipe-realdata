#!/usr/bin/env python3
"""Build one restartable exact THELI_NAME row-run index partition."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from darkpipe.fits_range_table import iter_remote_numeric_columns
from darkpipe.kids_source_tile_index import (
    SOURCE_TILE_INDEX_AUTHORITY,
    extend_tile_runs,
    tile_run_counts,
    tile_runs_sha256,
)
from run_darkpipe_kids_pairs_v017 import SOURCE_TOTAL_BYTES, SOURCE_TOTAL_ROWS, SOURCE_URL


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-url", default=SOURCE_URL)
    parser.add_argument("--source-total-bytes", type=int, default=SOURCE_TOTAL_BYTES)
    parser.add_argument("--start-row", type=int, default=0)
    parser.add_argument("--stop-row", type=int, default=SOURCE_TOTAL_ROWS)
    parser.add_argument("--chunk-mib", type=int, default=64)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 0 <= args.start_row < args.stop_row <= SOURCE_TOTAL_ROWS:
        raise ValueError("invalid source row partition")

    started_at = datetime.now(timezone.utc).isoformat()
    next_row = args.start_row
    runs: list[dict[str, object]] = []
    chunks = 0
    if args.output.exists():
        previous = json.loads(args.output.read_text(encoding="utf-8"))
        if int(previous["start_row"]) != args.start_row or int(previous["stop_row"]) != args.stop_row:
            raise RuntimeError("tile-index checkpoint partition mismatch")
        if previous.get("source_url") != args.source_url:
            raise RuntimeError("tile-index checkpoint source URL mismatch")
        runs = list(previous["runs"])
        if tile_runs_sha256(runs) != previous.get("runs_sha256"):
            raise RuntimeError("tile-index checkpoint hash mismatch")
        next_row = int(previous["next_row"])
        chunks = int(previous["chunks"])
        started_at = str(previous["started_at"])

    for first_row, columns in iter_remote_numeric_columns(
        args.source_url,
        total_bytes=args.source_total_bytes,
        names=("THELI_NAME",),
        target_chunk_bytes=args.chunk_mib * 1024 * 1024,
        start_row=next_row,
        stop_row=args.stop_row,
    ):
        extend_tile_runs(runs, columns["THELI_NAME"], first_row)
        next_row = first_row + len(columns["THELI_NAME"])
        chunks += 1
        counts = tile_run_counts(runs)
        payload: dict[str, object] = {
            "schema": "darkpipe.kids-source-tile-index-partition.v1",
            "started_at": started_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "complete": next_row == args.stop_row,
            "source_url": args.source_url,
            "source_total_bytes": args.source_total_bytes,
            "source_total_rows": SOURCE_TOTAL_ROWS,
            "start_row": args.start_row,
            "next_row": next_row,
            "stop_row": args.stop_row,
            "chunks": chunks,
            "run_count": len(runs),
            "unique_tile_count": len(counts),
            "indexed_row_count": sum(counts.values()),
            "runs_sha256": tile_runs_sha256(runs),
            "runs": runs,
            "authority": SOURCE_TILE_INDEX_AUTHORITY,
            "scientific_result": False,
            "next_gate": "MERGE_EXACT_INDEX_THEN_BOUNDED_RANDOM_TILE_CONTROL",
        }
        write_json(args.output, payload)
        print(json.dumps({key: payload[key] for key in payload if key != "runs"}, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
