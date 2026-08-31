#!/usr/bin/env python3
"""Freeze the pre-signal parts of the v0.17 KiDS random-coordinate contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from darkpipe.kids_random_catalogue import (
    EXPECTED_SOURCE_TILE_COUNT,
    RANDOM_AUTHORITY,
    RANDOM_MULTIPLIER,
    RANDOM_SEED,
    REDSHIFT_EDGES,
    source_tile_to_observation_name,
)
from darkpipe.kids_streaming_pairs import STREAMING_PAIR_AUTHORITY, pair_sums_sha256


PAIR_KEYS = (
    "sum_pair_weight",
    "sum_tangential",
    "sum_cross",
    "sum_shape_variance",
    "pair_count",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--lens-cache",
        type=Path,
        default=Path("evidence/kids_native_lens_v016/lens_catalogue_cache.npz"),
    )
    parser.add_argument(
        "--observations",
        type=Path,
        default=Path("evidence/kids_randoms_v017/KiDS_DR4_observations_table.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/kids_randoms_v017/frozen_random_configuration.json"),
    )
    parser.add_argument(
        "--complete-pair-payload",
        type=Path,
        help="Completed merged pair NPZ whose metadata seals the exact 1006 source tiles",
    )
    args = parser.parse_args()
    with np.load(args.lens_cache, allow_pickle=False) as values:
        redshift = np.asarray(values["zphot_ANNz2"], dtype=float)
        masked = np.asarray(values["masked"])
    parent = (
        (masked == 0)
        & np.isfinite(redshift)
        & (redshift > REDSHIFT_EDGES[0])
        & (redshift < REDSHIFT_EDGES[-1])
    )
    histogram = np.histogram(redshift[parent], bins=REDSHIFT_EDGES)[0]
    observations = pd.read_csv(
        args.observations,
        comment="#",
        header=None,
        names=("tile", "ra_deg", "dec_deg", "band", "date", "seeing", "ellipticity", "depth"),
    )
    tiles = observations[["tile", "ra_deg", "dec_deg"]].drop_duplicates()
    if tiles["tile"].duplicated().any():
        raise RuntimeError("official observations table has inconsistent tile centers")
    exact_tile_surface: dict[str, object]
    if args.complete_pair_payload is None:
        exact_tile_surface = {
            "exact_source_tile_list_state": "PENDING_BLIND_METADATA_UNION_FROM_FULL_SCAN",
        }
    else:
        with np.load(args.complete_pair_payload, allow_pickle=False) as values:
            pair_metadata = json.loads(str(values["metadata_json"]))
            pair_content_sha256 = str(values["content_sha256"])
            pair_sums = {key: np.asarray(values[key]).copy() for key in PAIR_KEYS}
        if pair_sums_sha256(pair_sums) != pair_content_sha256:
            raise RuntimeError("complete pair payload content hash mismatch")
        source_tiles = sorted(set(pair_metadata.get("source_tiles", [])))
        if not pair_metadata.get("complete") or pair_metadata.get("source_tile_count") != EXPECTED_SOURCE_TILE_COUNT:
            raise RuntimeError("pair payload is not the complete 1006-tile surface")
        if pair_metadata.get("authority") != STREAMING_PAIR_AUTHORITY:
            raise RuntimeError("complete pair payload has unexpected authority")
        if len(source_tiles) != EXPECTED_SOURCE_TILE_COUNT:
            raise RuntimeError("pair metadata does not contain 1006 unique source tiles")
        centers = tiles.set_index("tile")
        exact_tiles = []
        missing = []
        for source_tile in source_tiles:
            observation_tile = source_tile_to_observation_name(str(source_tile))
            if observation_tile not in centers.index:
                missing.append(observation_tile)
                continue
            row = centers.loc[observation_tile]
            exact_tiles.append(
                {
                    "source_tile": str(source_tile),
                    "observation_tile": observation_tile,
                    "ra_deg": float(row["ra_deg"]),
                    "dec_deg": float(row["dec_deg"]),
                }
            )
        if missing:
            raise RuntimeError(f"source tiles absent from official observations: {missing[:5]}")
        canonical_tiles = json.dumps(
            exact_tiles, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        exact_tile_surface = {
            "exact_source_tile_list_state": "SEALED_FROM_COMPLETE_BLIND_METADATA_UNION",
            "exact_source_tile_count": len(exact_tiles),
            "exact_source_tiles_sha256": hashlib.sha256(canonical_tiles).hexdigest(),
            "exact_source_tiles": exact_tiles,
            "pair_surface": {
                "content_sha256": pair_content_sha256,
                "partition_count": pair_metadata.get("partition_count"),
                "source_total_rows": pair_metadata.get("source_total_rows"),
            },
        }
    payload = {
        "schema": "darkpipe.kids-random-configuration.v1",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "seed": RANDOM_SEED,
        "multiplier": RANDOM_MULTIPLIER,
        "parent_definition": "masked=0 AND 0.1<zphot_ANNz2<0.5 BEFORE MASS_AND_ISOLATION",
        "parent_count": int(parent.sum()),
        "requested_random_count": int(parent.sum() * RANDOM_MULTIPLIER),
        "redshift_edges": REDSHIFT_EDGES.tolist(),
        "parent_redshift_bin_counts": histogram.tolist(),
        "requested_random_redshift_bin_counts": (histogram * RANDOM_MULTIPLIER).tolist(),
        "coordinate_rule": "UNIFORM_SOLID_ANGLE_IN_1_DEG_SOURCE_THELI_NAME_TILE",
        "tile_rule": "SOURCE_FITS_THELI_NAME_INTERSECTION_OFFICIAL_DR4_OBSERVATIONS",
        "expected_source_tile_count": EXPECTED_SOURCE_TILE_COUNT,
        "official_observations_unique_tile_count": int(len(tiles)),
        "observations_table": {
            "path": args.observations.as_posix(),
            "bytes": args.observations.stat().st_size,
            "sha256": sha256(args.observations),
        },
        "lens_cache_sha256": sha256(args.lens_cache),
        "authority": RANDOM_AUTHORITY,
        "scientific_result": False,
        **exact_tile_surface,
    }
    if payload["parent_count"] != 900_778 or payload["requested_random_count"] != 45_038_900:
        raise RuntimeError("frozen KiDS-bright parent/random count changed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
