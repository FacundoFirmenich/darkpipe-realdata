#!/usr/bin/env python3
"""Reduce the complete v0.17 random pilot to compact null profiles."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from darkpipe.kids_random_catalogue import RANDOM_PILOT_AUTHORITY
from darkpipe.kids_random_control import (
    RANDOM_CONTROL_AUTHORITY,
    finalize_random_control,
    reduce_random_pair_batch,
    save_random_control,
)
from darkpipe.kids_streaming_pairs import (
    RADIAL_EDGES_MPC_H70,
    STREAMING_PAIR_AUTHORITY,
    pair_sums_sha256,
)


PAIR_KEYS = (
    "sum_pair_weight",
    "sum_tangential",
    "sum_cross",
    "sum_shape_variance",
    "pair_count",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--merged-pairs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--table", type=Path, required=True)
    args = parser.parse_args()
    with np.load(args.merged_pairs, allow_pickle=False) as values:
        metadata = json.loads(str(values["metadata_json"]))
        stored_hash = str(values["content_sha256"])
        pair_sums = {key: np.asarray(values[key]).copy() for key in PAIR_KEYS}
    if pair_sums_sha256(pair_sums) != stored_hash:
        raise RuntimeError("merged random-pilot pair hash mismatch")
    if (
        not metadata.get("complete")
        or metadata.get("lens_count") != 10_060
        or metadata.get("source_total_rows") != 21_262_011
        or metadata.get("source_tile_count") != 988
        or metadata.get("authority") != STREAMING_PAIR_AUTHORITY
    ):
        raise RuntimeError("merged random pilot does not satisfy the full source-surface gate")

    reduced = reduce_random_pair_batch(pair_sums, RADIAL_EDGES_MPC_H70)
    final = finalize_random_control(reduced)
    centers = np.sqrt(RADIAL_EDGES_MPC_H70[:-1] * RADIAL_EDGES_MPC_H70[1:])
    output_metadata = {
        "schema": "darkpipe.kids-random-pilot-control.v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "complete": True,
        "pilot_random_count": 10_060,
        "full_random_target": 45_038_900,
        "official_tile_count": 1006,
        "source_theli_tile_count": 988,
        "source_total_rows": 21_262_011,
        "candidate_pairs": metadata["diagnostics"]["candidate_pairs"],
        "accepted_pairs": metadata["diagnostics"]["accepted_pairs"],
        "merged_pair_content_sha256": stored_hash,
        "pilot_authority": RANDOM_PILOT_AUTHORITY,
        "authority": RANDOM_CONTROL_AUTHORITY,
        "scientific_result": False,
        "jurisdiction": "ENGINEERING_AND_NULL_PILOT_NOT_50X_ADDITIVE_BIAS_ESTIMATE",
        "next_gate": "MEASURE_RUNTIME_AND_SCALE_OR_AUTHORIZE_REMOTE_DARKPIPE_SCRATCH",
    }
    save_random_control(args.output, reduced, output_metadata)
    args.table.parent.mkdir(parents=True, exist_ok=True)
    with args.table.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            (
                "radius_mpc_h70",
                "random_esd_msun_mpc2",
                "random_cross_esd_msun_mpc2",
                "random_esd_std",
                "random_gobs_m_s2",
                "random_cross_gobs_m_s2",
                "random_gobs_std",
                "random_cross_gobs_std",
                "esd_effective_randoms",
                "gobs_effective_randoms",
                "cross_gobs_effective_randoms",
                "pair_count",
            )
        )
        for index, radius in enumerate(centers):
            writer.writerow(
                (
                    float(radius),
                    float(final["random_esd_msun_mpc2"][index]),
                    float(final["random_cross_esd_msun_mpc2"][index]),
                    float(np.sqrt(final["random_esd_variance"][index])),
                    float(final["random_gobs_m_s2"][index]),
                    float(final["random_cross_gobs_m_s2"][index]),
                    float(np.sqrt(final["random_gobs_variance"][index])),
                    float(np.sqrt(final["random_cross_gobs_variance"][index])),
                    int(reduced["esd_effective_randoms"][index]),
                    int(reduced["gobs_effective_randoms_tangential"][index]),
                    int(reduced["gobs_effective_randoms_cross"][index]),
                    int(reduced["pair_count"][index]),
                )
            )
    print(json.dumps(output_metadata, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
