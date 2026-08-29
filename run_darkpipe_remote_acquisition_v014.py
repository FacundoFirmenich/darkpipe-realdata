from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from darkpipe.object_recoverability import DEFAULT_DATASETS
from darkpipe.remote_acquisition import (
    DEFAULT_CHUNK_BYTES,
    REMOTE_JURISDICTION,
    acquire_default_inputs,
    assert_remote_capacity,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="DarkPipe v0.14 remote-only, resumable KiDS acquisition"
    )
    parser.add_argument("--remote-root", type=Path, required=True)
    parser.add_argument(
        "--execution-jurisdiction",
        choices=[REMOTE_JURISDICTION],
        required=True,
    )
    parser.add_argument(
        "--acknowledge-upstream-terms",
        action="store_true",
        help="Record acknowledgement; this does not relicense upstream data.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Without this flag only the remote capacity gate is evaluated.",
    )
    parser.add_argument("--chunk-mib", type=int, default=DEFAULT_CHUNK_BYTES // 1024**2)
    args = parser.parse_args()

    expected = sum(item.expected_total_bytes for item in DEFAULT_DATASETS)
    capacity = assert_remote_capacity(
        args.remote_root,
        expected_input_bytes=expected,
        execution_jurisdiction=args.execution_jurisdiction,
    )
    if not args.execute:
        print(
            json.dumps(
                {
                    "campaign": "DP-REMOTE-OBJ-0.14",
                    "capacity_gate": capacity,
                    "expected_input_bytes": expected,
                    "execution": "NOT_STARTED_EXPLICIT_EXECUTE_FLAG_REQUIRED",
                    "authority": "PREFLIGHT_ONLY_NO_BYTE_CUSTODY_NO_SCIENTIFIC_RESULT",
                },
                indent=2,
            )
        )
        return 0

    if not args.acknowledge_upstream_terms:
        parser.error("--execute requires --acknowledge-upstream-terms")
    result = acquire_default_inputs(
        args.remote_root,
        acknowledge_upstream_terms=True,
        execution_jurisdiction=args.execution_jurisdiction,
        chunk_bytes=args.chunk_mib * 1024**2,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["all_inputs_complete"] else 2


if __name__ == "__main__":
    sys.exit(main())
