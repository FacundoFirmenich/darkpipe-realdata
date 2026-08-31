#!/usr/bin/env python3
"""Stream one source partition into the v0.17 stratified random pilot."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from darkpipe.fits_range_table import iter_remote_numeric_columns
from darkpipe.kids_random_catalogue import RANDOM_PILOT_AUTHORITY
from darkpipe.kids_streaming_pairs import (
    LensPayload,
    RADIAL_EDGES_MPC_H70,
    RADIAL_EDGES_SHA256,
    STREAMING_PAIR_AUTHORITY,
    accumulate_source_chunk,
    empty_pair_sums,
    save_pair_partition,
)
from run_darkpipe_kids_pairs_v017 import (
    SOURCE_COLUMNS,
    SOURCE_TOTAL_BYTES,
    SOURCE_TOTAL_ROWS,
    SOURCE_URL,
    load_checkpoint,
    load_sigma_grid,
    sha256,
)


def load_random_pilot(payload_path: Path, receipt_path: Path) -> tuple[LensPayload, dict[str, object]]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("authority") != RANDOM_PILOT_AUTHORITY:
        raise RuntimeError("random pilot authority mismatch")
    if receipt.get("pilot_random_count") != 10_060:
        raise RuntimeError("random pilot must contain exactly 10 points per 1006 tiles")
    if receipt.get("payload_sha256") != sha256(payload_path):
        raise RuntimeError("random pilot payload hash mismatch")
    with np.load(payload_path, allow_pickle=False) as values:
        payload = LensPayload(
            ra_deg=np.asarray(values["ra_deg"], dtype=float),
            dec_deg=np.asarray(values["dec_deg"], dtype=float),
            redshift=np.asarray(values["redshift"], dtype=float),
            baryonic_mass_msun=np.asarray(values["baryonic_mass_msun"], dtype=float),
            source_row=np.asarray(values["source_row"], dtype=np.int64),
        )
    return payload, receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-row", type=int, required=True)
    parser.add_argument("--stop-row", type=int, required=True)
    parser.add_argument("--chunk-mib", type=int, default=32)
    parser.add_argument(
        "--pilot-payload",
        type=Path,
        default=Path("evidence/kids_random_pilot_v017/random_pair_payload.npz"),
    )
    parser.add_argument(
        "--pilot-receipt",
        type=Path,
        default=Path("evidence/kids_random_pilot_v017/build_receipt.json"),
    )
    parser.add_argument(
        "--sigma-lookup",
        type=Path,
        default=Path("evidence/kids_sigma_critical_v016/effective_sigma_critical_lookup.csv"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 0 <= args.start_row < args.stop_row <= SOURCE_TOTAL_ROWS:
        raise ValueError("invalid source row partition")
    randoms, pilot_receipt = load_random_pilot(args.pilot_payload, args.pilot_receipt)
    sigma_grid = load_sigma_grid(args.sigma_lookup, randoms.redshift)
    started = datetime.now(timezone.utc).isoformat()
    sums = empty_pair_sums(randoms.count, len(RADIAL_EDGES_MPC_H70) - 1)
    next_row = args.start_row
    chunks = 0
    diagnostics = {key: 0 for key in ("source_rows", "selected_source_rows", "candidate_pairs", "accepted_pairs")}
    seen_tiles: set[str] = set()
    if args.output.exists():
        sums, previous = load_checkpoint(args.output, args.start_row)
        if int(previous["stop_row"]) != args.stop_row:
            raise RuntimeError("checkpoint stop row mismatch")
        next_row = int(previous["next_row"])
        chunks = int(previous["chunks"])
        started = str(previous["started_at"])
        diagnostics = {key: int(previous["diagnostics"][key]) for key in diagnostics}
        seen_tiles = set(previous.get("source_tiles", []))

    for first_row, source_chunk in iter_remote_numeric_columns(
        SOURCE_URL,
        total_bytes=SOURCE_TOTAL_BYTES,
        names=SOURCE_COLUMNS,
        target_chunk_bytes=args.chunk_mib * 1024 * 1024,
        start_row=next_row,
        stop_row=args.stop_row,
    ):
        seen_tiles.update(raw.decode("ascii", "strict").strip() for raw in np.asarray(source_chunk["THELI_NAME"]))
        chunk_sums, chunk_diagnostics = accumulate_source_chunk(randoms, source_chunk, sigma_grid)
        for key in sums:
            sums[key] += chunk_sums[key]
        next_row = first_row + int(chunk_diagnostics["source_rows"])
        chunks += 1
        for key in diagnostics:
            diagnostics[key] += int(chunk_diagnostics[key])
        metadata = {
            "schema": "darkpipe.kids-random-pilot-pair-partition.v1",
            "started_at": started,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "complete": next_row == args.stop_row,
            "source_url": SOURCE_URL,
            "source_total_bytes": SOURCE_TOTAL_BYTES,
            "start_row": args.start_row,
            "next_row": next_row,
            "stop_row": args.stop_row,
            "chunks": chunks,
            "diagnostics": diagnostics,
            "source_tile_count": len(seen_tiles),
            "source_tiles": sorted(seen_tiles),
            "lens_count": randoms.count,
            "lens_payload_sha256": pilot_receipt["payload_sha256"],
            "sigma_lookup_sha256": sha256(args.sigma_lookup),
            "radial_edges_mpc_h70": RADIAL_EDGES_MPC_H70.tolist(),
            "radial_edges_sha256": RADIAL_EDGES_SHA256,
            "authority": STREAMING_PAIR_AUTHORITY,
            "pilot_authority": RANDOM_PILOT_AUTHORITY,
            "full_random_target": 45_038_900,
            "scientific_result": False,
            "next_gate": "MERGE_PILOT_REDUCE_RANDOM_NULL_AND_MEASURE_SCALING",
        }
        save_pair_partition(args.output, sums, metadata)
        print(json.dumps({key: metadata[key] for key in metadata if key != "source_tiles"}, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
