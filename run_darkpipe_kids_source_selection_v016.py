#!/usr/bin/env python3
"""Stream all 21,262,011 KiDS SOM-gold rows and audit source selection."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from darkpipe.fits_range_table import iter_remote_numeric_columns
from darkpipe.kids_lens_sample import LENS_SAMPLE_AUTHORITY


SOURCE_URL = "https://kids.strw.leidenuniv.nl/DR4/data_files/KiDS_DR4.1_ugriZYJHKs_SOM_gold_WL_cat.fits"
SOURCE_BYTES = 17_712_469_440
SOURCE_ROWS = 21_262_011
NAMES = (
    "SG_FLAG",
    "SG2DPHOT",
    "CLASS_STAR",
    "IMAFLAGS_ISO",
    "MASK",
    "Z_B",
    "e1",
    "e2",
    "weight",
)


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def empty_state() -> dict[str, object]:
    return {
        "schema": "darkpipe.kids-source-selection-checkpoint.v1",
        "source_url": SOURCE_URL,
        "next_row": 0,
        "chunks": 0,
        "attrition": {
            "rows": 0,
            "sg_flag": 0,
            "sg2dphot": 0,
            "class_star": 0,
            "imaflags_iso": 0,
            "recommended_mask": 0,
            "finite_positive_shape_weight": 0,
        },
        "tomographic_best_fit_counts": {"0.1_0.3": 0, "0.3_0.5": 0, "0.5_0.7": 0, "0.7_0.9": 0, "0.9_1.2": 0},
        "weighted_sums": {"weight": 0.0, "e1_weight": 0.0, "e2_weight": 0.0},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("evidence/kids_source_selection_v016"))
    parser.add_argument("--chunk-mib", type=int, default=128)
    args = parser.parse_args()
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output / "checkpoint.json"
    state = json.loads(checkpoint_path.read_text(encoding="utf-8")) if checkpoint_path.exists() else empty_state()
    started = state.get("started_at") or datetime.now(timezone.utc).isoformat()
    state["started_at"] = started
    attrition = state["attrition"]
    tomo = state["tomographic_best_fit_counts"]
    sums = state["weighted_sums"]
    start_row = int(state["next_row"])
    for first, data in iter_remote_numeric_columns(
        SOURCE_URL,
        total_bytes=SOURCE_BYTES,
        names=NAMES,
        target_chunk_bytes=args.chunk_mib * 1024 * 1024,
        start_row=start_row,
    ):
        rows = len(data["Z_B"])
        if first != int(state["next_row"]):
            raise RuntimeError(f"restart discontinuity: {first} != {state['next_row']}")
        cut = np.ones(rows, dtype=bool)
        attrition["rows"] += rows
        cut &= data["SG_FLAG"] == 1
        attrition["sg_flag"] += int(np.count_nonzero(cut))
        cut &= data["SG2DPHOT"] == 0
        attrition["sg2dphot"] += int(np.count_nonzero(cut))
        cut &= data["CLASS_STAR"] < 0.5
        attrition["class_star"] += int(np.count_nonzero(cut))
        cut &= data["IMAFLAGS_ISO"] == 0
        attrition["imaflags_iso"] += int(np.count_nonzero(cut))
        cut &= (data["MASK"].astype(np.int64) & 28668) == 0
        attrition["recommended_mask"] += int(np.count_nonzero(cut))
        cut &= (
            np.isfinite(data["Z_B"])
            & np.isfinite(data["e1"])
            & np.isfinite(data["e2"])
            & np.isfinite(data["weight"])
            & (data["weight"] > 0.0)
        )
        attrition["finite_positive_shape_weight"] += int(np.count_nonzero(cut))
        z = data["Z_B"]
        for label, low, high in (
            ("0.1_0.3", 0.1, 0.3),
            ("0.3_0.5", 0.3, 0.5),
            ("0.5_0.7", 0.5, 0.7),
            ("0.7_0.9", 0.7, 0.9),
            ("0.9_1.2", 0.9, 1.2),
        ):
            tomo[label] += int(np.count_nonzero(cut & (z > low) & (z <= high)))
        w = data["weight"][cut].astype(float)
        sums["weight"] += float(np.sum(w))
        sums["e1_weight"] += float(np.sum(w * data["e1"][cut]))
        sums["e2_weight"] += float(np.sum(w * data["e2"][cut]))
        state["next_row"] = first + rows
        state["chunks"] += 1
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        atomic_json(checkpoint_path, state)
        print(f"rows={state['next_row']}/{SOURCE_ROWS} selected={attrition['finite_positive_shape_weight']}", flush=True)
    if int(state["next_row"]) != SOURCE_ROWS:
        raise RuntimeError(f"incomplete source stream: {state['next_row']} != {SOURCE_ROWS}")
    weight = float(sums["weight"])
    report = {
        **state,
        "schema": "darkpipe.kids-source-selection.v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "weighted_mean_e1": float(sums["e1_weight"]) / weight,
        "weighted_mean_e2": float(sums["e2_weight"]) / weight,
        "authority": "FULL_PUBLIC_SOURCE_TABLE_SELECTION_AUDIT_NO_LENSING_RESULT",
        "scientific_result": False,
        "next_gate": "LENS_SOURCE_PAIR_ESTIMATOR_RANDOM_SUBTRACTION_AND_COVARIANCE",
    }
    atomic_json(output / "run_receipt.json", report)
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
