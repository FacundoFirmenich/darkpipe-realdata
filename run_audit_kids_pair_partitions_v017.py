#!/usr/bin/env python3
"""Audit the eight authentic KiDS pair partitions and their exact merge."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from darkpipe.kids_external_rar import (
    ESD_TO_SIS_GOBS,
    load_mistele2024_table1,
    mistele_reproduction_diagnostic,
    stack_interpolated_profile,
)
from darkpipe.kids_streaming_pairs import (
    RADIAL_EDGES_MPC_H70,
    finalize_individual_esd,
    pair_sums_sha256,
)
from darkpipe.object_lensing import fixed_gbar_radius_kpc


PAIR_KEYS = (
    "sum_pair_weight",
    "sum_tangential",
    "sum_cross",
    "sum_shape_variance",
    "pair_count",
)
AUDIT_AUTHORITY = "PARTITION_AND_MERGE_AUDIT_NO_SCIENTIFIC_OR_MODEL_ADJUDICATION"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_pair_file(path: Path) -> tuple[dict[str, np.ndarray], dict[str, object], str]:
    with np.load(path, allow_pickle=False) as values:
        sums = {key: np.asarray(values[key]).copy() for key in PAIR_KEYS}
        metadata = json.loads(str(values["metadata_json"]))
        stored_hash = str(values["content_sha256"])
    if pair_sums_sha256(sums) != stored_hash:
        raise RuntimeError(f"pair content hash mismatch: {path}")
    return sums, metadata, stored_hash


def stack_sis(
    sums: dict[str, np.ndarray],
    target_radius: np.ndarray,
    reference: dict[str, np.ndarray | str],
) -> tuple[np.ndarray, dict[str, object], float]:
    centers = np.sqrt(RADIAL_EDGES_MPC_H70[:-1] * RADIAL_EDGES_MPC_H70[1:])
    profiles = finalize_individual_esd(sums)
    signal = stack_interpolated_profile(
        centers,
        np.asarray(profiles["esd_msun_mpc2"]),
        np.asarray(profiles["variance_esd"]),
        np.asarray(profiles["pair_weight_sum"]),
        target_radius,
    )
    cross = stack_interpolated_profile(
        centers,
        np.asarray(profiles["cross_esd_msun_mpc2"]),
        np.asarray(profiles["variance_esd"]),
        np.asarray(profiles["pair_weight_sum"]),
        target_radius,
    )
    gobs = ESD_TO_SIS_GOBS * np.asarray(signal["stacked"])
    cross_gobs = ESD_TO_SIS_GOBS * np.asarray(cross["stacked"])
    cross_std = ESD_TO_SIS_GOBS * np.sqrt(np.asarray(cross["variance"]))
    cross_z = np.divide(
        cross_gobs,
        cross_std,
        out=np.full_like(cross_gobs, np.nan),
        where=cross_std > 0,
    )
    return (
        gobs,
        mistele_reproduction_diagnostic(gobs, reference),
        float(np.nanmax(np.abs(cross_z))),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, default=Path("tmp/pair_parts_audit"))
    parser.add_argument(
        "--custody",
        type=Path,
        default=Path("evidence/kids_pairs_v017_full/partition_artifact_custody.json"),
    )
    parser.add_argument(
        "--merged",
        type=Path,
        default=Path("evidence/kids_pairs_v017_full/kids_pairs_v017_full_merged.npz"),
    )
    parser.add_argument(
        "--lens-payload",
        type=Path,
        default=Path("evidence/kids_native_lens_v016_complete/selected_lens_pair_payload.npz"),
    )
    parser.add_argument(
        "--mistele-table",
        type=Path,
        default=Path(
            "evidence/kids_brouwer2021_external_validation/official_source/"
            "mistele2024_table1_rar.csv"
        ),
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("evidence/kids_partition_audit_v017")
    )
    args = parser.parse_args()

    custody = json.loads(args.custody.read_text(encoding="utf-8"))
    if custody.get("artifact_count") != 8 or int(custody.get("github_actions_run_id", -1)) != 33398418711:
        raise RuntimeError("partition custody gate failed")
    with np.load(args.lens_payload, allow_pickle=False) as values:
        masses = np.asarray(values["baryonic_mass_msun"], dtype=float)
    if len(masses) != 106_843:
        raise RuntimeError("lens payload count differs")
    reference = load_mistele2024_table1(args.mistele_table)
    gbar = np.asarray(reference["gbar_m_s2"], dtype=float)
    target_radius = fixed_gbar_radius_kpc(masses[:, None], gbar[None, :]) / 1000.0

    accumulated: dict[str, np.ndarray] | None = None
    partition_results: list[dict[str, object]] = []
    curves: dict[str, np.ndarray] = {}
    table_rows: list[dict[str, object]] = []
    for item in sorted(custody["artifacts"], key=lambda value: value["start_row"]):
        path = args.artifact_root / item["path"]
        if not path.exists() or sha256(path) != item["file_sha256"]:
            raise RuntimeError(f"partition file custody failed: {path}")
        sums, metadata, content_hash = load_pair_file(path)
        if content_hash != item["content_sha256"] or not metadata.get("complete"):
            raise RuntimeError(f"partition metadata custody failed: {path}")
        if accumulated is None:
            accumulated = {
                key: np.zeros_like(value, dtype=np.int64 if key == "pair_count" else np.float64)
                for key, value in sums.items()
            }
        for key in accumulated:
            accumulated[key] += sums[key]
        gobs, diagnostic, cross_max = stack_sis(sums, target_radius, reference)
        name = path.parent.name
        curves[name] = gobs
        partition_results.append(
            {
                "partition": name,
                "start_row": item["start_row"],
                "stop_row": item["stop_row"],
                "accepted_pairs": item["diagnostics"]["accepted_pairs"],
                "cross_max_abs_diagonal_z": cross_max,
                "mistele2024_reproduction_diagnostic": diagnostic,
            }
        )
        for index, acceleration in enumerate(gbar):
            table_rows.append(
                {
                    "partition": name,
                    "gbar_m_s2": float(acceleration),
                    "raw_sis_gobs_m_s2": float(gobs[index]),
                    "mistele2024_gobs_m_s2": float(reference["gobs_m_s2"][index]),
                }
            )
        del sums
    if accumulated is None:
        raise RuntimeError("no partitions were audited")

    stored_merged, merged_metadata, merged_content_hash = load_pair_file(args.merged)
    exact_keys = {key: bool(np.array_equal(accumulated[key], stored_merged[key])) for key in PAIR_KEYS}
    exact_merge = bool(all(exact_keys.values()))
    accumulated_hash = pair_sums_sha256(accumulated)
    if accumulated_hash != merged_content_hash or not exact_merge:
        raise RuntimeError("merged pair surface is not the exact sum of its partitions")
    merged_gobs, merged_diagnostic, merged_cross_max = stack_sis(
        accumulated, target_radius, reference
    )
    curves["exact_merged"] = merged_gobs
    for index, acceleration in enumerate(gbar):
        table_rows.append(
            {
                "partition": "exact_merged",
                "gbar_m_s2": float(acceleration),
                "raw_sis_gobs_m_s2": float(merged_gobs[index]),
                "mistele2024_gobs_m_s2": float(reference["gobs_m_s2"][index]),
            }
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "partition_rar.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=tuple(table_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(table_rows)
    metrics = {
        "schema": "darkpipe.kids-pair-partition-audit.v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "complete": True,
        "github_actions_run_id": 33398418711,
        "partition_count": 8,
        "partition_results": partition_results,
        "exact_merge": exact_merge,
        "exact_merge_by_key": exact_keys,
        "recomputed_merged_content_sha256": accumulated_hash,
        "stored_merged_content_sha256": merged_content_hash,
        "merged_metadata_complete": bool(merged_metadata.get("complete")),
        "merged_mistele2024_reproduction_diagnostic": merged_diagnostic,
        "merged_cross_max_abs_diagonal_z": merged_cross_max,
        "authority": AUDIT_AUTHORITY,
        "scientific_result": False,
        "model_or_ontology_adjudication": False,
        "next_gate": "ADJUDICATE_PARTITION_HETEROGENEITY_AND_SIGMA_CRITICAL",
    }
    (args.output_dir / "partition_audit_metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    figure, axis = plt.subplots(figsize=(7.6, 5.5), constrained_layout=True)
    axis.plot(gbar, reference["gobs_m_s2"], "ko-", linewidth=2, label="Mistele 2024")
    for name, values in curves.items():
        if name == "exact_merged":
            axis.plot(gbar, values, "s-", linewidth=2, label=name)
        else:
            axis.plot(gbar, values, marker=".", alpha=0.55, linewidth=0.8, label=name)
    axis.set_xscale("log")
    axis.set_yscale("symlog", linthresh=1e-13)
    axis.set_xlabel("g_bar [m s^-2]")
    axis.set_ylabel("raw SIS g_obs [m s^-2]")
    axis.set_title("KiDS v0.17 partition and exact-merge audit")
    axis.grid(True, which="both", alpha=0.25)
    axis.legend(fontsize=7, ncol=2)
    figure.savefig(args.output_dir / "partition_rar.png", dpi=180)
    plt.close(figure)
    print(json.dumps(metrics, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
