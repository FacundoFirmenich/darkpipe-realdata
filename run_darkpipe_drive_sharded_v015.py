from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from darkpipe.drive_sharded_acquisition import (
    DEFAULT_DRIVE_SAFETY_MARGIN_BYTES,
    DEFAULT_DRIVE_SHARD_BYTES,
    DRIVE_SHARDED_JURISDICTION,
    acquire_default_inputs_to_drive,
    assert_drive_quota,
    declared_completed_bytes,
)
from darkpipe.object_recoverability import DEFAULT_DATASETS


def main() -> int:
    parser = argparse.ArgumentParser(
        description="DarkPipe v0.15 resumable KiDS acquisition into Google Drive shards"
    )
    parser.add_argument("--drive-root", type=Path, required=True)
    parser.add_argument(
        "--execution-jurisdiction",
        choices=[DRIVE_SHARDED_JURISDICTION],
        required=True,
    )
    parser.add_argument("--observed-drive-free-bytes", type=int, required=True)
    parser.add_argument(
        "--acknowledge-upstream-terms",
        action="store_true",
        help="Records acknowledgement; it does not relicense KiDS data.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Without this flag only the Drive quota gate is evaluated.",
    )
    parser.add_argument(
        "--shard-mib",
        type=int,
        default=DEFAULT_DRIVE_SHARD_BYTES // 1024**2,
    )
    parser.add_argument(
        "--safety-margin-gib",
        type=float,
        default=DEFAULT_DRIVE_SAFETY_MARGIN_BYTES / 1024**3,
    )
    args = parser.parse_args()

    if args.shard_mib <= 0 or args.safety_margin_gib < 0:
        parser.error("shard size must be positive and safety margin non-negative")
    shard_bytes = args.shard_mib * 1024**2
    safety_bytes = int(args.safety_margin_gib * 1024**3)
    expected = sum(item.expected_total_bytes for item in DEFAULT_DATASETS)
    existing = declared_completed_bytes(
        args.drive_root,
        datasets=DEFAULT_DATASETS,
        shard_bytes=shard_bytes,
    )
    quota = assert_drive_quota(
        expected_remaining_bytes=expected - existing,
        observed_drive_free_bytes=args.observed_drive_free_bytes,
        safety_margin_bytes=safety_bytes,
    )

    if not args.execute:
        print(
            json.dumps(
                {
                    "campaign": "DP-DRIVE-SHARDS-0.15",
                    "quota_gate": quota,
                    "expected_total_bytes": expected,
                    "declared_existing_bytes": existing,
                    "execution": "NOT_STARTED_EXPLICIT_EXECUTE_FLAG_REQUIRED",
                    "authority": "PREFLIGHT_ONLY_NO_BYTE_CUSTODY_NO_SCIENTIFIC_RESULT",
                },
                indent=2,
            )
        )
        return 0

    if not args.acknowledge_upstream_terms:
        parser.error("--execute requires --acknowledge-upstream-terms")
    result = acquire_default_inputs_to_drive(
        args.drive_root,
        observed_drive_free_bytes=args.observed_drive_free_bytes,
        acknowledge_upstream_terms=True,
        execution_jurisdiction=args.execution_jurisdiction,
        shard_bytes=shard_bytes,
        safety_margin_bytes=safety_bytes,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["all_inputs_complete"] else 2


if __name__ == "__main__":
    sys.exit(main())
