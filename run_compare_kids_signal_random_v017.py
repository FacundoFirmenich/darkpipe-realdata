#!/usr/bin/env python3
"""Compare the complete KiDS signal with the stratified random-control pilot.

The corrected columns are exploratory because the random surface is a
10-per-tile pilot, not the frozen 50x random catalogue required for the final
additive-bias estimate.  Signal and random variances are combined assuming
independence; no full radial covariance is claimed.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from darkpipe.kids_random_control import (
    finalize_random_control,
    random_control_sha256,
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


def _read_signal(path: Path) -> tuple[dict[str, np.ndarray], dict[str, object], str]:
    with np.load(path, allow_pickle=False) as values:
        metadata = json.loads(str(values["metadata_json"]))
        stored_hash = str(values["content_sha256"])
        sums = {key: np.asarray(values[key]).copy() for key in PAIR_KEYS}
    if pair_sums_sha256(sums) != stored_hash:
        raise RuntimeError("signal pair hash mismatch")
    if (
        not metadata.get("complete")
        or metadata.get("lens_count") != 106_843
        or metadata.get("source_total_rows") != 21_262_011
        or metadata.get("source_tile_count") != 988
        or metadata.get("authority") != STREAMING_PAIR_AUTHORITY
    ):
        raise RuntimeError("signal payload does not satisfy the complete-surface gate")
    return sums, metadata, stored_hash


def _read_random_sums(path: Path) -> tuple[dict[str, np.ndarray], dict[str, object], str]:
    with np.load(path, allow_pickle=False) as values:
        metadata = json.loads(str(values["metadata_json"]))
        stored_hash = str(values["content_sha256"])
        sums = {
            key: np.asarray(values[key]).copy()
            for key in values.files
            if key not in {"metadata_json", "content_sha256"}
        }
    if random_control_sha256(sums) != stored_hash:
        raise RuntimeError("random-control hash mismatch")
    if not metadata.get("complete") or metadata.get("pilot_random_count") != 10_060:
        raise RuntimeError("random control is not the sealed stratified pilot")
    return sums, metadata, stored_hash


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signal-pairs", type=Path, required=True)
    parser.add_argument("--random-sums", type=Path, required=True)
    parser.add_argument("--signal-sums", type=Path, required=True)
    parser.add_argument("--table", type=Path, required=True)
    args = parser.parse_args()

    signal_pairs, signal_metadata, signal_pair_hash = _read_signal(args.signal_pairs)
    random_sums, random_metadata, random_hash = _read_random_sums(args.random_sums)
    signal_sums = reduce_random_pair_batch(signal_pairs, RADIAL_EDGES_MPC_H70)
    signal = finalize_random_control(signal_sums)
    random = finalize_random_control(random_sums)
    centers = np.sqrt(RADIAL_EDGES_MPC_H70[:-1] * RADIAL_EDGES_MPC_H70[1:])

    output_metadata = {
        "schema": "darkpipe.kids-signal-random-pilot-comparison.v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "complete": True,
        "signal_lens_count": 106_843,
        "pilot_random_count": 10_060,
        "source_total_rows": 21_262_011,
        "signal_candidate_pairs": signal_metadata["diagnostics"]["candidate_pairs"],
        "signal_accepted_pairs": signal_metadata["diagnostics"]["accepted_pairs"],
        "signal_pair_content_sha256": signal_pair_hash,
        "random_control_content_sha256": random_hash,
        "random_control_jurisdiction": random_metadata["jurisdiction"],
        "scientific_result": False,
        "jurisdiction": "EXPLORATORY_SIGNAL_MINUS_STRATIFIED_RANDOM_PILOT_NO_FULL_COVARIANCE",
        "next_gate": "REPLACE_PILOT_WITH_FROZEN_50X_RANDOM_CONTROL_AND_ESTIMATE_COVARIANCE",
    }
    save_random_control(args.signal_sums, signal_sums, output_metadata)

    def variance(surface: dict[str, np.ndarray | str], name: str) -> np.ndarray:
        return np.asarray(surface[name], dtype=np.float64)

    fields = (
        ("esd", "random_esd_msun_mpc2", "random_esd_variance"),
        ("cross_esd", "random_cross_esd_msun_mpc2", "random_esd_variance"),
        ("gobs", "random_gobs_m_s2", "random_gobs_variance"),
        ("cross_gobs", "random_cross_gobs_m_s2", "random_cross_gobs_variance"),
    )
    args.table.parent.mkdir(parents=True, exist_ok=True)
    with args.table.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        header = ["radius_mpc_h70"]
        for label, _, _ in fields:
            header.extend(
                (
                    f"signal_{label}",
                    f"signal_{label}_std",
                    f"pilot_random_{label}",
                    f"pilot_random_{label}_std",
                    f"pilot_corrected_{label}",
                    f"pilot_corrected_{label}_std_independent_diagonal",
                )
            )
        writer.writerow(header)
        for index, radius in enumerate(centers):
            row: list[float] = [float(radius)]
            for _, value_name, variance_name in fields:
                signal_value = variance(signal, value_name)[index]
                random_value = variance(random, value_name)[index]
                signal_variance = variance(signal, variance_name)[index]
                random_variance = variance(random, variance_name)[index]
                row.extend(
                    (
                        float(signal_value),
                        float(np.sqrt(signal_variance)),
                        float(random_value),
                        float(np.sqrt(random_variance)),
                        float(signal_value - random_value),
                        float(np.sqrt(signal_variance + random_variance)),
                    )
                )
            writer.writerow(row)
    print(json.dumps(output_metadata, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
