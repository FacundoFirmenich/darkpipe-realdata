#!/usr/bin/env python3
"""Run the preregistered authentic KiDS e2/orientation diagnostic."""

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

from darkpipe.fits_range_table import iter_remote_numeric_columns
from darkpipe.kids_external_rar import (
    ESD_TO_SIS_GOBS,
    load_mistele2024_table1,
    mistele_reproduction_diagnostic,
    stack_interpolated_profile,
)
from darkpipe.kids_streaming_pairs import (
    LensPayload,
    ORIENTATION_CONVENTIONS,
    RADIAL_EDGES_MPC_H70,
    accumulate_source_chunk,
    finalize_orientation_conventions,
)
from darkpipe.object_lensing import fixed_gbar_radius_kpc


SOURCE_URL = (
    "https://kids.strw.leidenuniv.nl/DR4/data_files/"
    "KiDS_DR4.1_ugriZYJHKs_SOM_gold_WL_cat.fits"
)
SOURCE_TOTAL_BYTES = 17_712_469_440
SOURCE_TOTAL_ROWS = 21_262_011
SOURCE_COLUMNS = (
    "ALPHA_J2000",
    "DELTA_J2000",
    "Z_B",
    "e1",
    "e2",
    "weight",
    "SG_FLAG",
    "SG2DPHOT",
    "CLASS_STAR",
    "IMAFLAGS_ISO",
    "MASK",
    "THELI_NAME",
)
DIAGNOSTIC_AUTHORITY = (
    "PREREGISTERED_BOUNDED_ORIENTATION_DIAGNOSTIC_NO_SCIENTIFIC_ADJUDICATION"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_lenses(payload_path: Path, receipt_path: Path) -> LensPayload:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    expected = receipt["selected_lens_pair_payload"]
    if expected["count"] != 106_843 or expected["sha256"] != sha256(payload_path):
        raise RuntimeError("authoritative lens payload gate failed")
    with np.load(payload_path, allow_pickle=False) as values:
        return LensPayload(
            ra_deg=np.asarray(values["ra_deg"], dtype=float),
            dec_deg=np.asarray(values["dec_deg"], dtype=float),
            redshift=np.asarray(values["redshift"], dtype=float),
            baryonic_mass_msun=np.asarray(values["baryonic_mass_msun"], dtype=float),
            source_row=np.asarray(values["source_row"], dtype=np.int64),
        )


def load_sigma_grid(path: Path, lens_redshift: np.ndarray) -> np.ndarray:
    table = np.genfromtxt(path, delimiter=",", names=True, dtype=float)
    grid_redshift = np.asarray(table["lens_redshift"], dtype=float)
    if np.any(np.diff(grid_redshift) <= 0):
        raise RuntimeError("Sigma-critical lookup grid is not increasing")
    result = np.column_stack(
        [
            np.interp(
                lens_redshift,
                grid_redshift,
                np.asarray(table[f"sigma_crit_tomo{index}_msun_mpc2"], dtype=float),
                left=np.nan,
                right=np.nan,
            )
            for index in range(1, 6)
        ]
    )
    if np.any(~np.isfinite(result)) or np.any(result <= 0):
        raise RuntimeError("Sigma-critical interpolation failed")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-url", default=SOURCE_URL)
    parser.add_argument("--source-total-bytes", type=int, default=SOURCE_TOTAL_BYTES)
    parser.add_argument("--rows-per-stratum", type=int, default=12_500)
    parser.add_argument("--strata", type=int, default=8)
    parser.add_argument(
        "--lens-payload",
        type=Path,
        default=Path("evidence/kids_native_lens_v016_complete/selected_lens_pair_payload.npz"),
    )
    parser.add_argument(
        "--lens-receipt",
        type=Path,
        default=Path("evidence/kids_native_lens_v016_complete/run_receipt.json"),
    )
    parser.add_argument(
        "--sigma-lookup",
        type=Path,
        default=Path("evidence/kids_sigma_critical_v016/effective_sigma_critical_lookup.csv"),
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
        "--output-dir",
        type=Path,
        default=Path("evidence/kids_orientation_pilot_v017"),
    )
    args = parser.parse_args()
    if args.strata != 8 or args.rows_per_stratum != 12_500:
        raise ValueError("the frozen diagnostic requires 8 strata x 12500 rows")

    lenses = load_lenses(args.lens_payload, args.lens_receipt)
    sigma_grid = load_sigma_grid(args.sigma_lookup, lenses.redshift)
    reference = load_mistele2024_table1(args.mistele_table)
    gbar = np.asarray(reference["gbar_m_s2"], dtype=float)
    target_radius = (
        fixed_gbar_radius_kpc(lenses.baryonic_mass_msun[:, None], gbar[None, :])
        / 1000.0
    )
    starts = [int(index * SOURCE_TOTAL_ROWS // args.strata) for index in range(args.strata)]
    intervals = [(start, start + args.rows_per_stratum) for start in starts]
    combined: dict[str, np.ndarray] | None = None
    diagnostics = {
        "source_rows": 0,
        "selected_source_rows": 0,
        "candidate_pairs": 0,
        "accepted_pairs": 0,
    }
    tiles: set[str] = set()
    for start, stop in intervals:
        for first_row, chunk in iter_remote_numeric_columns(
            args.source_url,
            total_bytes=args.source_total_bytes,
            names=SOURCE_COLUMNS,
            target_chunk_bytes=16 * 1024 * 1024,
            start_row=start,
            stop_row=stop,
        ):
            if first_row != start:
                raise RuntimeError("unexpected row split in frozen interval")
            tiles.update(
                raw.decode("ascii", "strict").strip()
                for raw in np.asarray(chunk["THELI_NAME"])
            )
            sums, observed = accumulate_source_chunk(
                lenses,
                chunk,
                sigma_grid,
                include_orientation_basis=True,
            )
            if combined is None:
                combined = {key: np.asarray(value).copy() for key, value in sums.items()}
            else:
                for key in combined:
                    combined[key] += sums[key]
            for key in diagnostics:
                diagnostics[key] += int(observed[key])
    if combined is None or diagnostics["source_rows"] != 100_000:
        raise RuntimeError("frozen source-row surface is incomplete")

    centers = np.sqrt(RADIAL_EDGES_MPC_H70[:-1] * RADIAL_EDGES_MPC_H70[1:])
    conventions = finalize_orientation_conventions(combined)
    rows: list[dict[str, object]] = []
    results: dict[str, dict[str, object]] = {}
    curves: dict[str, np.ndarray] = {}
    for name, profile in conventions.items():
        tangential = stack_interpolated_profile(
            centers,
            np.asarray(profile["esd_msun_mpc2"]),
            np.asarray(profile["variance_esd"]),
            np.asarray(profile["pair_weight_sum"]),
            target_radius,
        )
        cross = stack_interpolated_profile(
            centers,
            np.asarray(profile["cross_esd_msun_mpc2"]),
            np.asarray(profile["variance_esd"]),
            np.asarray(profile["pair_weight_sum"]),
            target_radius,
        )
        gobs = ESD_TO_SIS_GOBS * np.asarray(tangential["stacked"])
        cross_gobs = ESD_TO_SIS_GOBS * np.asarray(cross["stacked"])
        gobs_std = ESD_TO_SIS_GOBS * np.sqrt(np.asarray(tangential["variance"]))
        cross_std = ESD_TO_SIS_GOBS * np.sqrt(np.asarray(cross["variance"]))
        cross_z = np.divide(
            cross_gobs,
            cross_std,
            out=np.full_like(cross_gobs, np.nan),
            where=cross_std > 0,
        )
        diagnostic = mistele_reproduction_diagnostic(gobs, reference)
        results[name] = {
            "definition": ORIENTATION_CONVENTIONS[name],
            "mistele2024_reproduction_diagnostic": diagnostic,
            "cross_max_abs_diagonal_z": float(np.nanmax(np.abs(cross_z))),
            "effective_lenses_min": int(np.min(tangential["effective_lenses"])),
            "effective_lenses_max": int(np.max(tangential["effective_lenses"])),
        }
        curves[name] = gobs
        for index, acceleration in enumerate(gbar):
            rows.append(
                {
                    "convention": name,
                    "gbar_m_s2": float(acceleration),
                    "sis_gobs_m_s2": float(gobs[index]),
                    "sis_gobs_std_diagonal": float(gobs_std[index]),
                    "cross_gobs_m_s2": float(cross_gobs[index]),
                    "cross_gobs_std_diagonal": float(cross_std[index]),
                    "mistele2024_gobs_m_s2": float(reference["gobs_m_s2"][index]),
                    "effective_lenses": int(tangential["effective_lenses"][index]),
                }
            )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    table_path = args.output_dir / "orientation_convention_rar.csv"
    with table_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=tuple(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    current_metric = results["east_ccw_catalog_e2_as_math"][
        "mistele2024_reproduction_diagnostic"
    ]["median_absolute_log10_difference_dex"]
    flipped_metric = results["east_ccw_catalog_e2_sign_flipped"][
        "mistele2024_reproduction_diagnostic"
    ]["median_absolute_log10_difference_dex"]
    metadata = {
        "schema": "darkpipe.kids-orientation-diagnostic.v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "complete": True,
        "source_url": args.source_url,
        "source_total_bytes": args.source_total_bytes,
        "source_intervals": intervals,
        "diagnostics": diagnostics,
        "unique_source_tiles": len(tiles),
        "lens_count": lenses.count,
        "preregistration_sha256": sha256(args.preregistration),
        "lens_payload_sha256": sha256(args.lens_payload),
        "sigma_lookup_sha256": sha256(args.sigma_lookup),
        "results": results,
        "e2_flip_reduces_median_absolute_log_difference": bool(
            current_metric is not None
            and flipped_metric is not None
            and flipped_metric < current_metric
        ),
        "authority": DIAGNOSTIC_AUTHORITY,
        "scientific_result": False,
        "model_or_ontology_adjudication": False,
        "next_gate": "REPAIR_OR_REJECT_ORIENTATION_THEN_REBUILD_FULL_PAIR_SURFACE",
    }
    (args.output_dir / "orientation_diagnostic_metrics.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    figure, axis = plt.subplots(figsize=(7.4, 5.4), constrained_layout=True)
    axis.plot(gbar, reference["gobs_m_s2"], "ko-", label="Mistele 2024 target")
    for name, values in curves.items():
        axis.plot(gbar, values, marker=".", label=name)
    axis.set_xscale("log")
    axis.set_yscale("symlog", linthresh=1e-13)
    axis.set_xlabel("g_bar [m s^-2]")
    axis.set_ylabel("raw SIS g_obs [m s^-2]")
    axis.set_title("Preregistered KiDS orientation diagnostic — authentic 100k rows")
    axis.grid(True, which="both", alpha=0.25)
    axis.legend(fontsize=7)
    figure.savefig(args.output_dir / "orientation_convention_rar.png", dpi=180)
    plt.close(figure)
    print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
