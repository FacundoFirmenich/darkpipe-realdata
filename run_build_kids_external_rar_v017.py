#!/usr/bin/env python3
"""Build the real DarkPipe object-level RAR and compare it to Brouwer 2021.

The DarkPipe surface remains exploratory until the frozen 50x random control
and radial covariance are available.  The Brouwer surface is an external
published reference built from overlapping KiDS data, not an independent
replication or a replacement random catalogue.
"""

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
    EXTERNAL_REFERENCE_AUTHORITY,
    load_brouwer_rar_reference,
    load_mistele2024_table1,
    mistele_reproduction_diagnostic,
    reference_residual_diagnostic,
    shared_random_corrected_stack,
    stack_interpolated_profile,
)
from darkpipe.kids_random_control import (
    finalize_random_control,
    random_control_sha256,
)
from darkpipe.kids_streaming_pairs import (
    RADIAL_EDGES_MPC_H70,
    STREAMING_PAIR_AUTHORITY,
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_signal(path: Path) -> tuple[dict[str, np.ndarray], dict[str, object], str]:
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


def read_random(path: Path) -> tuple[dict[str, np.ndarray | str], dict[str, object], str]:
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
    return finalize_random_control(sums), metadata, stored_hash


def json_number(value: float) -> float | None:
    return float(value) if np.isfinite(value) else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signal-pairs", type=Path, required=True)
    parser.add_argument("--lens-payload", type=Path, required=True)
    parser.add_argument("--random-sums", type=Path, required=True)
    parser.add_argument("--brouwer-profile", type=Path, required=True)
    parser.add_argument("--brouwer-covariance", type=Path, required=True)
    parser.add_argument("--brouwer-readme", type=Path, required=True)
    parser.add_argument("--mistele-table", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    pair_sums, pair_metadata, pair_hash = read_signal(args.signal_pairs)
    if sha256(args.lens_payload) != pair_metadata["lens_payload_sha256"]:
        raise RuntimeError("authoritative lens payload hash differs from pair metadata")
    with np.load(args.lens_payload, allow_pickle=False) as values:
        masses = np.asarray(values["baryonic_mass_msun"], dtype=np.float64).copy()
        source_rows = np.asarray(values["source_row"]).copy()
    if len(masses) != 106_843 or len(source_rows) != len(masses):
        raise RuntimeError("authoritative lens payload has the wrong length")

    random, random_metadata, random_hash = read_random(args.random_sums)
    reference = load_brouwer_rar_reference(
        args.brouwer_profile, args.brouwer_covariance
    )
    mistele = load_mistele2024_table1(args.mistele_table)
    gbar = np.asarray(mistele["gbar_m_s2"], dtype=np.float64)
    centers = np.sqrt(RADIAL_EDGES_MPC_H70[:-1] * RADIAL_EDGES_MPC_H70[1:])
    target_radius = fixed_gbar_radius_kpc(masses[:, None], gbar[None, :]) / 1000.0

    individual = finalize_individual_esd(pair_sums)
    sis_esd_stack = stack_interpolated_profile(
        centers,
        np.asarray(individual["esd_msun_mpc2"]),
        np.asarray(individual["variance_esd"]),
        np.asarray(individual["pair_weight_sum"]),
        target_radius,
    )
    sis_gobs = ESD_TO_SIS_GOBS * np.asarray(sis_esd_stack["stacked"])
    signal = deproject_individual_profiles(
        centers,
        RADIAL_EDGES_MPC_H70,
        np.asarray(individual["esd_msun_mpc2"]),
        np.asarray(individual["variance_esd"]),
        target_radius,
        outer_tail="sis",
    )
    cross = deproject_individual_profiles(
        centers,
        RADIAL_EDGES_MPC_H70,
        np.asarray(individual["cross_esd_msun_mpc2"]),
        np.asarray(individual["variance_esd"]),
        target_radius,
        outer_tail="zero",
    )
    del individual, pair_sums

    raw_stack = stack_inverse_variance(
        np.asarray(signal["gobs_m_s2"]), np.asarray(signal["variance_gobs"])
    )
    raw_cross_stack = stack_inverse_variance(
        np.asarray(cross["gobs_m_s2"]), np.asarray(cross["variance_gobs"])
    )
    corrected = shared_random_corrected_stack(
        np.asarray(signal["gobs_m_s2"]),
        np.asarray(signal["variance_gobs"]),
        target_radius,
        centers,
        np.asarray(random["random_gobs_m_s2"]),
        np.asarray(random["random_gobs_variance"]),
    )
    corrected_cross = shared_random_corrected_stack(
        np.asarray(cross["gobs_m_s2"]),
        np.asarray(cross["variance_gobs"]),
        target_radius,
        centers,
        np.asarray(random["random_cross_gobs_m_s2"]),
        np.asarray(random["random_cross_gobs_variance"]),
    )

    corrected_values = np.asarray(corrected["corrected"])
    corrected_variance = np.asarray(corrected["corrected_variance_diagonal"])
    diagnostic = reference_residual_diagnostic(
        corrected_values,
        corrected_variance,
        np.asarray(reference["gobs_m_s2"]),
        np.asarray(reference["covariance_gobs"]),
    )
    mistele_diagnostic = mistele_reproduction_diagnostic(corrected_values, mistele)
    sis_diagnostic = mistele_reproduction_diagnostic(sis_gobs, mistele)
    cross_values = np.asarray(corrected_cross["corrected"])
    cross_variance = np.asarray(corrected_cross["corrected_variance_diagonal"])
    cross_z = np.divide(
        cross_values,
        np.sqrt(cross_variance),
        out=np.full_like(cross_values, np.nan),
        where=cross_variance > 0,
    )
    pilot_shift_z = np.divide(
        np.asarray(corrected["random_correction"]),
        np.sqrt(np.asarray(corrected["random_variance_diagonal"])),
        out=np.full_like(corrected_values, np.nan),
        where=np.asarray(corrected["random_variance_diagonal"]) > 0,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    table_path = args.output_dir / "darkpipe_exploratory_rar.csv"
    fields = (
        "gbar_m_s2",
        "target_radius_mpc_p05",
        "target_radius_mpc_median",
        "target_radius_mpc_p95",
        "raw_signal_gobs_m_s2",
        "raw_signal_gobs_std",
        "raw_sis_stack_first_gobs_m_s2",
        "raw_sis_stack_first_gobs_std",
        "matched_signal_gobs_m_s2",
        "pilot_random_correction_gobs_m_s2",
        "pilot_corrected_gobs_m_s2",
        "pilot_corrected_gobs_std_diagonal",
        "pilot_corrected_effective_lenses",
        "raw_cross_gobs_m_s2",
        "pilot_corrected_cross_gobs_m_s2",
        "pilot_corrected_cross_gobs_std_diagonal",
        "brouwer2021_gobs_m_s2",
        "brouwer2021_gobs_std_full_covariance_diagonal",
        "brouwer2021_cross_gobs_m_s2",
        "mistele2024_gobs_m_s2",
        "mistele2024_sigma_statistical_dex",
        "mistele2024_sigma_systematic_dex",
    )
    with table_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for index, acceleration in enumerate(gbar):
            writer.writerow(
                {
                    "gbar_m_s2": float(acceleration),
                    "target_radius_mpc_p05": float(np.quantile(target_radius[:, index], 0.05)),
                    "target_radius_mpc_median": float(np.median(target_radius[:, index])),
                    "target_radius_mpc_p95": float(np.quantile(target_radius[:, index], 0.95)),
                    "raw_signal_gobs_m_s2": float(raw_stack["stacked"][index]),
                    "raw_signal_gobs_std": float(np.sqrt(raw_stack["variance"][index])),
                    "raw_sis_stack_first_gobs_m_s2": float(sis_gobs[index]),
                    "raw_sis_stack_first_gobs_std": float(
                        ESD_TO_SIS_GOBS * np.sqrt(sis_esd_stack["variance"][index])
                    ),
                    "matched_signal_gobs_m_s2": float(corrected["matched_signal"][index]),
                    "pilot_random_correction_gobs_m_s2": float(corrected["random_correction"][index]),
                    "pilot_corrected_gobs_m_s2": float(corrected_values[index]),
                    "pilot_corrected_gobs_std_diagonal": float(np.sqrt(corrected_variance[index])),
                    "pilot_corrected_effective_lenses": int(corrected["effective_lenses"][index]),
                    "raw_cross_gobs_m_s2": float(raw_cross_stack["stacked"][index]),
                    "pilot_corrected_cross_gobs_m_s2": float(cross_values[index]),
                    "pilot_corrected_cross_gobs_std_diagonal": float(np.sqrt(cross_variance[index])),
                    "brouwer2021_gobs_m_s2": float(reference["gobs_m_s2"][index]),
                    "brouwer2021_gobs_std_full_covariance_diagonal": float(
                        np.sqrt(reference["covariance_gobs"][index, index])
                    ),
                    "brouwer2021_cross_gobs_m_s2": float(reference["cross_gobs_m_s2"][index]),
                    "mistele2024_gobs_m_s2": float(mistele["gobs_m_s2"][index]),
                    "mistele2024_sigma_statistical_dex": float(
                        mistele["sigma_statistical_log10_gobs"][index]
                    ),
                    "mistele2024_sigma_systematic_dex": float(
                        mistele["sigma_systematic_log10_gobs"][index]
                    ),
                }
            )

    source_files = {
        "profile": {
            "path": args.brouwer_profile.name,
            "bytes": args.brouwer_profile.stat().st_size,
            "sha256": sha256(args.brouwer_profile),
        },
        "covariance": {
            "path": args.brouwer_covariance.name,
            "bytes": args.brouwer_covariance.stat().st_size,
            "sha256": sha256(args.brouwer_covariance),
        },
        "readme": {
            "path": args.brouwer_readme.name,
            "bytes": args.brouwer_readme.stat().st_size,
            "sha256": sha256(args.brouwer_readme),
        },
        "mistele_table1_transcription": {
            "path": args.mistele_table.name,
            "bytes": args.mistele_table.stat().st_size,
            "sha256": sha256(args.mistele_table),
            "primary_source": "https://arxiv.org/html/2310.15248",
            "doi": "https://doi.org/10.1088/1475-7516/2024/04/020",
        },
    }
    receipt = {
        "schema": "darkpipe.kids-brouwer2021-external-reference.v1",
        "retrieved_at_utc": "2026-08-31",
        "official_data_page": "https://kids.strw.leidenuniv.nl/sciencedata.php",
        "official_tar_url": "https://kids.strw.leidenuniv.nl/sci_data/brouwer2021_rar.tar",
        "official_tar_bytes": 2_430_464,
        "official_tar_sha256": "73adc2d4e848fa0a6a43187f7b5447e749b92eaec4a795b9902b0beaf8a78733",
        "files": source_files,
        "authority": EXTERNAL_REFERENCE_AUTHORITY,
        "limitation": "FINAL_RANDOM_SUBTRACTED_RAR_NO_RAW_RANDOM_PROFILE_OVERLAPPING_KIDS_DATA",
    }
    (args.output_dir / "source_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    metadata = {
        "schema": "darkpipe.kids-exploratory-object-rar.v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "complete": True,
        "signal_lens_count": 106_843,
        "signal_source_rows": 21_262_011,
        "signal_accepted_pairs": pair_metadata["diagnostics"]["accepted_pairs"],
        "signal_pair_content_sha256": pair_hash,
        "lens_payload_sha256": pair_metadata["lens_payload_sha256"],
        "pilot_random_count": random_metadata["pilot_random_count"],
        "full_random_target": random_metadata["full_random_target"],
        "random_control_content_sha256": random_hash,
        "gbar_bins": int(len(gbar)),
        "effective_lenses_min": int(np.min(corrected["effective_lenses"])),
        "effective_lenses_max": int(np.max(corrected["effective_lenses"])),
        "pilot_correction_max_abs_diagonal_z": float(np.nanmax(np.abs(pilot_shift_z))),
        "corrected_cross_max_abs_diagonal_z": float(np.nanmax(np.abs(cross_z))),
        "reference_diagnostic": diagnostic,
        "brouwer_to_mistele_gbar_max_fractional_grid_difference": float(
            np.max(
                np.abs(np.asarray(reference["gbar_m_s2"]) - gbar)
                / gbar
            )
        ),
        "mistele2024_reproduction_diagnostic": mistele_diagnostic,
        "raw_sis_stack_first_reproduction_diagnostic": sis_diagnostic,
        "upstream_localization": (
            "PAIR_ESD_OR_PRE_DEPROJECTION_SURFACE_REMAINS_SUSPECT"
            if not sis_diagnostic["reproduction_gate"]
            else "EXACT_DEPROJECTION_OR_DEPROJECT_FIRST_WEIGHTING_REMAINS_SUSPECT"
        ),
        "jurisdiction": "EXPLORATORY_OBJECT_RAR_WITH_10060_RANDOM_PILOT_AND_EXTERNAL_PUBLISHED_REFERENCE",
        "scientific_result": False,
        "model_or_ontology_adjudication": False,
        "not_estimated": [
            "frozen_50x_random_control",
            "random_radial_covariance",
            "field_to_field_covariance",
            "independent_replication",
        ],
        "next_gate": (
            "LOCALIZE_AND_REPAIR_PAIR_ESD_ORIENTATION_BEFORE_50X_RANDOM_CONTROL"
            if not sis_diagnostic["reproduction_gate"]
            else "EXECUTE_FROZEN_50X_RANDOM_CONTROL_THEN_REBUILD_RAR_WITH_FULL_COVARIANCE"
        ),
    }
    metrics_path = args.output_dir / "external_validation_metrics.json"
    metrics_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    figure_path = args.output_dir / "darkpipe_vs_brouwer2021_rar.png"
    figure, axis = plt.subplots(figsize=(7.2, 5.2), constrained_layout=True)
    reference_std = np.sqrt(np.diag(np.asarray(reference["covariance_gobs"])))
    axis.fill_between(
        gbar,
        np.asarray(reference["gobs_m_s2"]) - reference_std,
        np.asarray(reference["gobs_m_s2"]) + reference_std,
        color="#777777",
        alpha=0.2,
        label="Brouwer 2021 diag. 1 sigma",
    )
    axis.plot(gbar, reference["gobs_m_s2"], "o-", color="#777777", label="Brouwer 2021")
    axis.plot(gbar, mistele["gobs_m_s2"], "^-", color="#111111", label="Mistele 2024 target")
    axis.errorbar(
        gbar,
        corrected_values,
        yerr=np.sqrt(corrected_variance),
        fmt="s-",
        color="#b2182b",
        capsize=2,
        label="DarkPipe signal - random pilot",
    )
    axis.plot(gbar, raw_stack["stacked"], "--", color="#2166ac", label="DarkPipe signal, uncorrected")
    axis.plot(gbar, sis_gobs, "-.", color="#762a83", label="DarkPipe raw SIS diagnostic")
    axis.plot(gbar, cross_values, ":", color="#4d9221", label="DarkPipe corrected cross")
    axis.set_xscale("log")
    axis.set_yscale("symlog", linthresh=1e-14)
    axis.set_xlabel("g_bar [m s^-2]")
    axis.set_ylabel("g_obs [m s^-2]")
    axis.set_title("KiDS object-level RAR: exploratory DarkPipe vs published reference")
    axis.grid(True, which="both", alpha=0.25)
    axis.legend(fontsize=8)
    figure.savefig(figure_path, dpi=180)
    plt.close(figure)

    print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
