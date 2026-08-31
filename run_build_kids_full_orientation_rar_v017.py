#!/usr/bin/env python3
"""Adjudicate the full authentic KiDS orientation-basis surface."""

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

from darkpipe.kids_exact_deprojection import (
    deproject_individual_profiles,
    stack_inverse_variance,
)
from darkpipe.kids_external_rar import (
    ESD_TO_SIS_GOBS,
    load_mistele2024_table1,
    mistele_reproduction_diagnostic,
    stack_interpolated_profile,
)
from darkpipe.kids_streaming_pairs import (
    ORIENTATION_BASIS_KEYS,
    ORIENTATION_CONVENTIONS,
    RADIAL_EDGES_MPC_H70,
    finalize_orientation_conventions,
    pair_sums_sha256,
)
from darkpipe.object_lensing import fixed_gbar_radius_kpc


BASE_KEYS = (
    "sum_pair_weight",
    "sum_tangential",
    "sum_cross",
    "sum_shape_variance",
    "pair_count",
)
FULL_KEYS = BASE_KEYS + ORIENTATION_BASIS_KEYS
AUTHORITY = "FULL_AUTHENTIC_ORIENTATION_LOCALIZATION_NO_FINAL_RAR_ADJUDICATION"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_basis_surface(path: Path) -> tuple[dict[str, np.ndarray], dict[str, object], str]:
    with np.load(path, allow_pickle=False) as values:
        sums = {key: np.asarray(values[key]).copy() for key in FULL_KEYS}
        metadata = json.loads(str(values["metadata_json"]))
        content_hash = str(values["content_sha256"])
    if pair_sums_sha256(sums) != content_hash:
        raise RuntimeError("full orientation-basis content hash mismatch")
    if (
        not metadata.get("complete")
        or not metadata.get("orientation_basis_included")
        or metadata.get("source_total_rows") != 21_262_011
        or metadata.get("lens_count") != 106_843
    ):
        raise RuntimeError("full orientation-basis authority gate failed")
    return sums, metadata, content_hash


def effective_lens_range(exact_stack: dict[str, np.ndarray]) -> tuple[int, int]:
    """Summarize the public ``stack_inverse_variance`` result contract."""

    effective = np.asarray(exact_stack["effective_lenses"], dtype=np.int64)
    if effective.ndim != 1 or effective.size == 0:
        raise ValueError("effective_lenses must be a non-empty one-dimensional array")
    return int(np.min(effective)), int(np.max(effective))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--basis-pairs", type=Path, required=True)
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
        "--preregistration",
        type=Path,
        default=Path("docs/V017_ORIENTATION_DIAGNOSTIC_PREREGISTRATION_2026-08-31.md"),
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("evidence/kids_full_orientation_rar_v017")
    )
    args = parser.parse_args()

    sums, pair_metadata, pair_hash = load_basis_surface(args.basis_pairs)
    with np.load(args.lens_payload, allow_pickle=False) as values:
        masses = np.asarray(values["baryonic_mass_msun"], dtype=float)
    if len(masses) != 106_843 or sha256(args.lens_payload) != pair_metadata["lens_payload_sha256"]:
        raise RuntimeError("lens payload differs from the basis scan")
    reference = load_mistele2024_table1(args.mistele_table)
    gbar = np.asarray(reference["gbar_m_s2"], dtype=float)
    target_radius = fixed_gbar_radius_kpc(masses[:, None], gbar[None, :]) / 1000.0
    centers = np.sqrt(RADIAL_EDGES_MPC_H70[:-1] * RADIAL_EDGES_MPC_H70[1:])
    conventions = finalize_orientation_conventions(sums)
    del sums

    rows: list[dict[str, object]] = []
    results: dict[str, dict[str, object]] = {}
    exact_curves: dict[str, np.ndarray] = {}
    for name, profile in conventions.items():
        esd = np.asarray(profile["esd_msun_mpc2"])
        cross_esd = np.asarray(profile["cross_esd_msun_mpc2"])
        variance = np.asarray(profile["variance_esd"])
        pair_weight = np.asarray(profile["pair_weight_sum"])
        sis = stack_interpolated_profile(
            centers, esd, variance, pair_weight, target_radius
        )
        sis_cross = stack_interpolated_profile(
            centers, cross_esd, variance, pair_weight, target_radius
        )
        sis_gobs = ESD_TO_SIS_GOBS * np.asarray(sis["stacked"])
        sis_cross_gobs = ESD_TO_SIS_GOBS * np.asarray(sis_cross["stacked"])

        exact = deproject_individual_profiles(
            centers,
            RADIAL_EDGES_MPC_H70,
            esd,
            variance,
            target_radius,
            outer_tail="sis",
        )
        exact_cross = deproject_individual_profiles(
            centers,
            RADIAL_EDGES_MPC_H70,
            cross_esd,
            variance,
            target_radius,
            outer_tail="zero",
        )
        exact_stack = stack_inverse_variance(
            np.asarray(exact["gobs_m_s2"]), np.asarray(exact["variance_gobs"])
        )
        exact_cross_stack = stack_inverse_variance(
            np.asarray(exact_cross["gobs_m_s2"]),
            np.asarray(exact_cross["variance_gobs"]),
        )
        exact_gobs = np.asarray(exact_stack["stacked"])
        exact_std = np.sqrt(np.asarray(exact_stack["variance"]))
        exact_cross_gobs = np.asarray(exact_cross_stack["stacked"])
        exact_cross_std = np.sqrt(np.asarray(exact_cross_stack["variance"]))
        cross_z = np.divide(
            exact_cross_gobs,
            exact_cross_std,
            out=np.full_like(exact_cross_gobs, np.nan),
            where=exact_cross_std > 0,
        )
        exact_diagnostic = mistele_reproduction_diagnostic(exact_gobs, reference)
        sis_diagnostic = mistele_reproduction_diagnostic(sis_gobs, reference)
        effective_min, effective_max = effective_lens_range(exact_stack)
        results[name] = {
            "definition": ORIENTATION_CONVENTIONS[name],
            "exact_reproduction_diagnostic": exact_diagnostic,
            "raw_sis_reproduction_diagnostic": sis_diagnostic,
            "exact_cross_max_abs_diagonal_z": float(np.nanmax(np.abs(cross_z))),
            "exact_effective_lenses_min": effective_min,
            "exact_effective_lenses_max": effective_max,
        }
        exact_curves[name] = exact_gobs
        for index, acceleration in enumerate(gbar):
            rows.append(
                {
                    "convention": name,
                    "gbar_m_s2": float(acceleration),
                    "exact_gobs_m_s2": float(exact_gobs[index]),
                    "exact_gobs_std_diagonal": float(exact_std[index]),
                    "exact_cross_gobs_m_s2": float(exact_cross_gobs[index]),
                    "exact_cross_std_diagonal": float(exact_cross_std[index]),
                    "raw_sis_gobs_m_s2": float(sis_gobs[index]),
                    "raw_sis_cross_gobs_m_s2": float(sis_cross_gobs[index]),
                    "mistele2024_gobs_m_s2": float(reference["gobs_m_s2"][index]),
                }
            )
        del exact, exact_cross, exact_stack, exact_cross_stack

    current = results["east_ccw_catalog_e2_as_math"]["exact_reproduction_diagnostic"]
    current_median = current["median_absolute_log10_difference_dex"]
    for name, item in results.items():
        diagnostic = item["exact_reproduction_diagnostic"]
        median = diagnostic["median_absolute_log10_difference_dex"]
        improvement = (
            float(current_median - median)
            if current_median is not None and median is not None
            else None
        )
        item["median_absolute_log10_improvement_vs_current_dex"] = improvement
        item["preregistered_repair_candidate"] = bool(
            name != "east_ccw_catalog_e2_as_math"
            and improvement is not None
            and improvement >= 0.30
            and diagnostic["positive_estimable_bins"] >= 13
            and item["exact_cross_max_abs_diagonal_z"] < 3.0
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "full_orientation_rar.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=tuple(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    metadata = {
        "schema": "darkpipe.kids-full-orientation-rar.v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "complete": True,
        "source_rows": pair_metadata["source_total_rows"],
        "accepted_pairs": pair_metadata["diagnostics"]["accepted_pairs"],
        "lens_count": pair_metadata["lens_count"],
        "basis_pair_content_sha256": pair_hash,
        "lens_payload_sha256": pair_metadata["lens_payload_sha256"],
        "preregistration_sha256": sha256(args.preregistration),
        "results": results,
        "repair_candidates": [
            name for name, item in results.items() if item["preregistered_repair_candidate"]
        ],
        "authority": AUTHORITY,
        "scientific_result": False,
        "model_or_ontology_adjudication": False,
        "next_gate": "IF_REPAIR_CANDIDATE_PATCH_ESTIMATOR_ELSE_AUDIT_SIGMA_CRITICAL_AND_LENS_IDENTITY",
    }
    (args.output_dir / "full_orientation_metrics.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    figure, axis = plt.subplots(figsize=(7.5, 5.4), constrained_layout=True)
    axis.plot(gbar, reference["gobs_m_s2"], "ko-", linewidth=2, label="Mistele 2024")
    for name, values in exact_curves.items():
        axis.plot(gbar, values, marker=".", label=name)
    axis.set_xscale("log")
    axis.set_yscale("symlog", linthresh=1e-14)
    axis.set_xlabel("g_bar [m s^-2]")
    axis.set_ylabel("raw exact g_obs [m s^-2]")
    axis.set_title("Full authentic KiDS orientation-basis adjudication")
    axis.grid(True, which="both", alpha=0.25)
    axis.legend(fontsize=7)
    figure.savefig(args.output_dir / "full_orientation_rar.png", dpi=180)
    plt.close(figure)
    print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
