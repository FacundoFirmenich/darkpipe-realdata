#!/usr/bin/env python3
"""Build a 1006-tile authentic subset of the frozen 45M random catalogue."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from darkpipe.kids_random_catalogue import (
    RANDOM_PILOT_AUTHORITY,
    RANDOM_SEED,
    allocate_redshift_counts,
    generate_tile_randoms,
    select_frozen_tile_subset,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--random-config",
        type=Path,
        default=Path("evidence/kids_randoms_v017/frozen_random_configuration.json"),
    )
    parser.add_argument("--per-tile", type=int, default=10)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/kids_random_pilot_v017/random_pair_payload.npz"),
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        default=Path("evidence/kids_random_pilot_v017/build_receipt.json"),
    )
    args = parser.parse_args()
    config = json.loads(args.random_config.read_text(encoding="utf-8"))
    tiles = config.get("exact_source_tiles", [])
    if len(tiles) != 1006 or config.get("requested_random_count") != 45_038_900:
        raise RuntimeError("sealed 1006-tile 45M random configuration required")
    parent_counts = np.asarray(config["parent_redshift_bin_counts"], dtype=np.int64)
    allocation = allocate_redshift_counts(parent_counts, tile_count=len(tiles))
    columns = {"ra_deg": [], "dec_deg": [], "redshift": []}
    full_tile_counts: list[int] = []
    for tile_index, tile in enumerate(tiles):
        full = generate_tile_randoms(
            tile_index=tile_index,
            tile_ra_deg=float(tile["ra_deg"]),
            tile_dec_deg=float(tile["dec_deg"]),
            redshift_allocation=allocation[:, tile_index],
        )
        selected = select_frozen_tile_subset(
            full, tile_index=tile_index, count=args.per_tile
        )
        full_tile_counts.append(len(full["redshift"]))
        for key in columns:
            columns[key].append(selected[key])
    payload = {key: np.concatenate(parts) for key, parts in columns.items()}
    count = len(payload["redshift"])
    if count != len(tiles) * args.per_tile:
        raise RuntimeError("pilot random count conservation failed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary.open("wb") as stream:
        np.savez_compressed(
            stream,
            **payload,
            baryonic_mass_msun=np.ones(count, dtype=np.float64),
            source_row=np.arange(count, dtype=np.int64),
        )
    temporary.replace(args.output)
    receipt = {
        "schema": "darkpipe.kids-random-pilot-payload.v1",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "random_config_sha256": sha256(args.random_config),
        "frozen_seed": RANDOM_SEED,
        "full_random_count": int(sum(full_tile_counts)),
        "official_tile_count": len(tiles),
        "per_tile": args.per_tile,
        "pilot_random_count": count,
        "selection_rule": "10_UNIFORM_WITHOUT_REPLACEMENT_FROM_EACH_FROZEN_TILE_BATCH",
        "payload_path": args.output.as_posix(),
        "payload_bytes": args.output.stat().st_size,
        "payload_sha256": sha256(args.output),
        "authority": RANDOM_PILOT_AUTHORITY,
        "scientific_result": False,
        "next_gate": "EIGHT_PART_AUTHENTIC_SOURCE_PAIR_SCAN_AND_RANDOM_NULL_REDUCTION",
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
