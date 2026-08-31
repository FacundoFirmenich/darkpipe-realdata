#!/usr/bin/env python3
"""Measure the exact request/byte frontier for the v0.17 random control."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from darkpipe.kids_random_catalogue import source_tile_to_observation_name
from darkpipe.kids_source_tile_index import (
    coalesce_selected_tile_runs,
    read_json_document,
    spherical_separation_deg,
    write_json_document,
)
from darkpipe.object_lensing import FlatLambdaCDM


SOURCE_ROW_BYTES = 833
DEFAULT_GAPS = (0, 128, 512, 2048, 8192, 32768)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-index",
        type=Path,
        default=Path("evidence/kids_source_tile_index_v017/source_tile_index.json.gz"),
    )
    parser.add_argument(
        "--random-config",
        type=Path,
        default=Path("evidence/kids_randoms_v017/frozen_random_configuration.json"),
    )
    parser.add_argument("--gaps", default=",".join(map(str, DEFAULT_GAPS)))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/kids_randoms_v017/random_transport_frontier.json.gz"),
    )
    args = parser.parse_args()
    gaps = tuple(int(value) for value in args.gaps.split(","))
    if not gaps or any(value < 0 for value in gaps):
        raise ValueError("non-negative gap candidates are required")
    source = read_json_document(args.source_index)
    random_config = json.loads(args.random_config.read_text(encoding="utf-8"))
    if not source.get("complete") or source.get("unique_tile_count") != 988:
        raise RuntimeError("complete 988-THELI source index required")
    official = random_config.get("exact_source_tiles", [])
    if len(official) != 1006:
        raise RuntimeError("sealed 1006-tile random footprint required")

    centers = {
        str(item["observation_tile"]): (float(item["ra_deg"]), float(item["dec_deg"]))
        for item in official
    }
    source_tiles = sorted({str(run["tile"]) for run in source["runs"]})
    runs_by_tile: dict[str, list[dict[str, object]]] = {tile: [] for tile in source_tiles}
    for run in source["runs"]:
        runs_by_tile[str(run["tile"])].append(run)
    source_observation_names = [source_tile_to_observation_name(tile) for tile in source_tiles]
    missing_centers = [name for name in source_observation_names if name not in centers]
    if missing_centers:
        raise RuntimeError(f"source THELI centers absent from official footprint: {missing_centers[:5]}")
    source_ra = np.asarray([centers[name][0] for name in source_observation_names])
    source_dec = np.asarray([centers[name][1] for name in source_observation_names])

    distance_h70 = FlatLambdaCDM(73.0, 0.2793).angular_diameter_distance_mpc(0.1) * (73.0 / 70.0)
    maximum_pair_angle_deg = math.degrees(11.94 / distance_h70)
    # One half-diagonal for the random tile plus one for the source tile.
    conservative_center_radius_deg = maximum_pair_angle_deg + math.sqrt(2.0)
    totals = {
        gap: {"requests": 0, "selected_rows": 0, "fetched_rows": 0}
        for gap in gaps
    }
    tile_summaries: list[dict[str, object]] = []
    for tile in official:
        separation = spherical_separation_deg(
            float(tile["ra_deg"]), float(tile["dec_deg"]), source_ra, source_dec
        )
        selected = {
            source_tiles[index]
            for index in np.flatnonzero(separation <= conservative_center_radius_deg)
        }
        selected_runs = [run for name in selected for run in runs_by_tile[name]]
        per_gap: dict[str, object] = {}
        for gap in gaps:
            intervals = coalesce_selected_tile_runs(
                selected_runs, selected, max_gap_rows=gap
            )
            selected_rows = sum(item["selected_rows"] for item in intervals)
            fetched_rows = sum(item["fetched_rows"] for item in intervals)
            totals[gap]["requests"] += len(intervals)
            totals[gap]["selected_rows"] += selected_rows
            totals[gap]["fetched_rows"] += fetched_rows
            per_gap[str(gap)] = {
                "requests": len(intervals),
                "selected_rows": selected_rows,
                "fetched_rows": fetched_rows,
                "fetched_bytes": fetched_rows * SOURCE_ROW_BYTES,
                "overhead_fraction": (
                    (fetched_rows - selected_rows) / fetched_rows
                    if fetched_rows
                    else None
                ),
            }
        tile_summaries.append(
            {
                "observation_tile": tile["observation_tile"],
                "nearby_theli_tiles": len(selected),
                "frontier": per_gap,
            }
        )

    payload = {
        "schema": "darkpipe.kids-random-transport-frontier.v1",
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "source_index_runs_sha256": source["runs_sha256"],
        "official_tile_surface_sha256": random_config["exact_source_tiles_sha256"],
        "source_row_bytes": SOURCE_ROW_BYTES,
        "maximum_pair_angle_at_z0p1_deg": maximum_pair_angle_deg,
        "conservative_center_radius_deg": conservative_center_radius_deg,
        "tile_count": len(official),
        "tiles_without_nearby_theli_surface": sum(
            item["nearby_theli_tiles"] == 0 for item in tile_summaries
        ),
        "frontier_totals": {
            str(gap): {
                **values,
                "fetched_bytes": values["fetched_rows"] * SOURCE_ROW_BYTES,
                "overhead_fraction": (
                    values["fetched_rows"] - values["selected_rows"]
                )
                / values["fetched_rows"],
            }
            for gap, values in totals.items()
        },
        "tiles": tile_summaries,
        "authority": "EXACT_TRANSPORT_COST_PROJECTION_NO_SCIENTIFIC_RESULT",
        "scientific_result": False,
    }
    write_json_document(args.output, payload)
    print(json.dumps(payload["frontier_totals"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
