#!/usr/bin/env python3
"""Audit the next KiDS gate without downloading survey data or launching compute.

SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from darkpipe.kids_random_catalogue import allocate_redshift_counts
from darkpipe.kids_source_tile_index import tile_runs_sha256


FROZEN = {
    "evidence/kids_randoms_v017/frozen_random_configuration.json":
        "b8dbd23db187a8daf289f81624e068d630d007b67c03dce585956965ed6e199f",
    "evidence/kids_source_tile_index_v017/source_tile_index.json.gz":
        "9caea1a33b9d3816e69163b0343ab562398ec969a948ad44b8c6cad50938c700",
    "evidence/kids_sigma_critical_v016/effective_sigma_critical_lookup.csv":
        "02700c57c9affa47630881b4f2f23023fd632ca4cd0a42c82c89ee78b9bd3da1",
    "evidence/kids_full_orientation_rar_v017/full_orientation_metrics.json":
        "19547845fb4afb2ef6e3fec5cccb717fe91d8d894c02bc0db444e02b6db7ae12",
}


def audit(root: Path) -> dict:
    records, payloads, failures = [], {}, []
    for name, expected in FROZEN.items():
        path = root / name
        if not path.is_file():
            failures.append(f"missing: {name}")
            continue
        body = path.read_bytes()
        digest = hashlib.sha256(body).hexdigest()
        records.append({"path": name, "bytes": len(body), "sha256": digest,
                        "passed": digest == expected})
        if digest != expected:
            failures.append(f"frozen hash differs: {name}")
        payloads[name] = body
    if not failures:
        config = json.loads(payloads[next(iter(FROZEN))])
        index = json.loads(gzip.decompress(payloads[list(FROZEN)[1]]))
        orientation = json.loads(payloads[list(FROZEN)[3]])
        allocation = allocate_redshift_counts(config["parent_redshift_bin_counts"], tile_count=1006)
        if (config["seed"] != 20260831017 or config["multiplier"] != 50
                or len(config["exact_source_tiles"]) != 1006
                or int(allocation.sum()) != 45038900):
            failures.append("frozen random population/seed/multiplier differs")
        runs = index["runs"]
        cursor = 0
        for run in runs:
            if run["start_row"] != cursor or run["stop_row"] <= cursor:
                failures.append("source index has a gap, overlap or empty run")
                break
            cursor = run["stop_row"]
        if cursor != 21262011 or len({run["tile"] for run in runs}) != 988:
            failures.append("source index coverage differs")
        if tile_runs_sha256(runs) != index["runs_sha256"]:
            failures.append("source index inner run hash differs")
        repaired = orientation["results"]["east_ccw_catalog_e2_sign_flipped"]
        if not repaired["preregistered_repair_candidate"]:
            failures.append("orientation repair evidence not established")
        if repaired["exact_reproduction_diagnostic"]["reproduction_gate"]:
            failures.append("historical adverse reproduction gate unexpectedly changed")
    blockers = [
        "FULL_45038900_RANDOM_CONTROL_NOT_EXECUTED",
        "PAIRED_SIGNAL_RANDOM_SPATIAL_REPLICATES_NOT_AVAILABLE",
        "REMOTE_DARKPIPE_RESOURCE_AND_FINITE_COMPUTE_BUDGET_NOT_BOUND",
    ]
    return {
        "schema": "darkpipe.kids-next-gate-readiness.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "gate": "ABSTAIN_INPUT_INTEGRITY" if failures else "BLOCKED_EXECUTION_AND_PAIRED_COVARIANCE",
        "input_integrity_passed": not failures,
        "failures": failures, "files": records, "blockers": blockers,
        "scientific_result": False, "reproduction_established": False,
        "covariance_contract": "Cs + Cr - Csr - Csr.T from matched spatial exclusions",
        "covariance_boundary": "empirical spatial covariance, conditional on map/deletion policy; not total systematics",
        "next_gate": "SIGNAL_MINUS_FULL_RANDOM_CONTROL_WITH_PAIRED_SPATIAL_COVARIANCE",
        "remote_resource_proposal": {
            "scratch_minimum_bytes": 40000000000,
            "raw_source_bytes": 17712469440,
            "raw_source_local_workstation": False,
            "initial_benchmark_max_wall_minutes": 30,
            "full_campaign_automatic_launch": False,
            "required_before_full_campaign": ["benchmark receipt", "finite CPU-hour cap", "authorized DarkPipe node"],
            "prior_linear_projection_cpu_context": "231-417 hours per original partition; eight partitions; not a benchmark of tile-local code",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: result[k] for k in ("gate", "input_integrity_passed", "failures", "blockers")}))
    return 2 if result["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
