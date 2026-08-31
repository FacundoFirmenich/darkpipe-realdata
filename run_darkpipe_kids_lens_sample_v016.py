#!/usr/bin/env python3
"""Execute the real KiDS-bright lens-sample reconstruction."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from darkpipe.kids_lens_sample import load_aligned_catalogues, reconstruct_lens_sample


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("evidence/kids_lens_sample_v016"))
    parser.add_argument("--chunk-mib", type=int, default=32)
    args = parser.parse_args()
    started = datetime.now(timezone.utc).isoformat()
    catalogue = load_aligned_catalogues(target_chunk_bytes=args.chunk_mib * 1024 * 1024)
    result = reconstruct_lens_sample(catalogue)
    selected = np.asarray(result["selected"])
    selected_rows = np.flatnonzero(selected).astype(np.int32)
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    rows_path = output / "selected_lens_row_indices.npy"
    np.save(rows_path, selected_rows, allow_pickle=False)
    rows_sha = hashlib.sha256(rows_path.read_bytes()).hexdigest()
    report = {
        "schema": "darkpipe.kids-lens-sample.v1",
        "started_at": started,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "diagnostics": result["diagnostics"],
        "selected_rows_file": rows_path.name,
        "selected_rows_sha256": rows_sha,
        "selected_rows_dtype": str(selected_rows.dtype),
        "scientific_result": False,
        "next_gate": "SOURCE_PAIR_ESTIMATOR_AND_RANDOM_SUBTRACTION",
    }
    atomic_json(output / "run_receipt.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
