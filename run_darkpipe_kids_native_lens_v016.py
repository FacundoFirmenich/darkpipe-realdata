#!/usr/bin/env python3
"""Reconstruct KiDS-bright lens masses with native DR4 GAAP photometry."""

from __future__ import annotations

import argparse
import hashlib
import json
import mmap
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from darkpipe.fits_range_table import decode_columns, parse_bintable_layout
from darkpipe.kids_lens_sample import (
    FlatCosmology,
    comoving_xyz_mpc_h70,
    isolation_mask,
    load_aligned_catalogues,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def unit_xyz(ra_deg: np.ndarray, dec_deg: np.ndarray) -> np.ndarray:
    ra = np.deg2rad(np.asarray(ra_deg, dtype=float))
    dec = np.deg2rad(np.asarray(dec_deg, dtype=float))
    return np.column_stack((np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)))


def decode_local_fits(path: Path) -> tuple[dict[str, np.ndarray], int, int]:
    with path.open("rb") as stream:
        mapped = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            layout = parse_bintable_layout(mapped[:262_144])
            data = decode_columns(
                mapped[layout.data_start : layout.data_start + layout.rows * layout.row_bytes],
                layout,
                ("RAJ2000", "DECJ2000", "MAG_GAAP_u", "MAG_GAAP_r", "MAG_AUTO"),
            )
            return data, layout.rows, layout.row_bytes
        finally:
            mapped.close()


def fixed_radius_isolation(
    xyz: np.ndarray,
    mass: np.ndarray,
    candidates: np.ndarray,
    pool: np.ndarray,
    *,
    radius: float,
) -> np.ndarray:
    pool_rows = np.flatnonzero(pool & np.isfinite(mass) & np.isfinite(xyz).all(axis=1))
    tree = cKDTree(xyz[pool_rows])
    result = np.zeros(len(mass), dtype=bool)
    candidate_rows = np.flatnonzero(candidates)
    for start in range(0, len(candidate_rows), 5000):
        batch = candidate_rows[start : start + 5000]
        lists = tree.query_ball_point(xyz[batch], radius, workers=-1)
        for lens, local in zip(batch, lists, strict=True):
            neighbours = pool_rows[np.asarray(local, dtype=np.int64)]
            neighbours = neighbours[neighbours != lens]
            result[lens] = not np.any(mass[neighbours] >= mass[lens] - 1.0)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tap-fits", type=Path, default=Path("evidence/kids_eso_tap_gaap_bright.fits"))
    parser.add_argument("--tap-mag-limit", type=float, default=20.0)
    parser.add_argument("--supplement-glob", action="append", default=[])
    parser.add_argument("--output-dir", type=Path, default=Path("evidence/kids_native_lens_v016"))
    parser.add_argument("--chunk-mib", type=int, default=128)
    args = parser.parse_args()
    started = datetime.now(timezone.utc).isoformat()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    tap, tap_rows, tap_row_bytes = decode_local_fits(args.tap_fits)
    primary_tap_rows = tap_rows
    supplement_receipts = []
    if args.supplement_glob:
        supplement_paths = sorted(
            {path for pattern in args.supplement_glob for path in Path().glob(pattern)}
        )
        supplement_tables = []
        for path in supplement_paths:
            table, rows, row_bytes = decode_local_fits(path)
            supplement_tables.append(table)
            supplement_receipts.append(
                {"path": path.as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path), "rows": rows, "row_bytes": row_bytes}
            )
        if supplement_tables:
            tap = {
                name: np.concatenate([tap[name]] + [table[name] for table in supplement_tables])
                for name in tap
            }
            tap_rows = len(tap["RAJ2000"])
    cache_path = Path("evidence/kids_native_lens_v016/lens_catalogue_cache.npz")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        with np.load(cache_path, allow_pickle=False) as cached:
            catalogue = {name: cached[name] for name in cached.files}
    else:
        full_catalogue = load_aligned_catalogues(target_chunk_bytes=args.chunk_mib * 1024 * 1024)
        catalogue = {
            name: np.asarray(full_catalogue[name])
            for name in ("RAJ2000", "DECJ2000", "zphot_ANNz2", "masked", "MASS_BEST", "MAG_AUTO_CALIB")
        }
        np.savez_compressed(cache_path, **catalogue)
    lens_xyz_unit = unit_xyz(catalogue["RAJ2000"], catalogue["DECJ2000"])
    tap_tree = cKDTree(unit_xyz(tap["RAJ2000"], tap["DECJ2000"]))
    tolerance_arcsec = 0.5
    chord = 2.0 * np.sin(np.deg2rad(tolerance_arcsec / 3600.0) / 2.0)
    distances, indices = tap_tree.query(lens_xyz_unit, k=2, distance_upper_bound=chord, workers=-1)
    matched = np.isfinite(distances[:, 0]) & (indices[:, 0] < tap_rows)
    ambiguous = matched & np.isfinite(distances[:, 1]) & (indices[:, 1] < tap_rows)
    mag_u = np.full(len(matched), np.nan)
    mag_r = np.full(len(matched), np.nan)
    mag_auto_tap = np.full(len(matched), np.nan)
    mag_u[matched] = tap["MAG_GAAP_u"][indices[matched, 0]]
    mag_r[matched] = tap["MAG_GAAP_r"][indices[matched, 0]]
    mag_auto_tap[matched] = tap["MAG_AUTO"][indices[matched, 0]]
    valid_native = matched & np.isfinite(mag_u) & np.isfinite(mag_r) & (mag_u < 90) & (mag_r < 90)

    colour = mag_u - mag_r
    is_etg = colour > 2.5
    h70 = 73.0 / 70.0
    log_m_kids = (
        np.asarray(catalogue["MASS_BEST"], dtype=float)
        + (mag_r - np.asarray(catalogue["MAG_AUTO_CALIB"], dtype=float)) / 2.5
        + 0.056
    )
    log_m_kids_h73 = log_m_kids - 2.0 * np.log10(h70)
    log_m_star = log_m_kids_h73 + np.where(is_etg, np.log10(1.4), 0.0)
    z = np.asarray(catalogue["zphot_ANNz2"], dtype=float)
    candidates = (
        valid_native
        & (np.asarray(catalogue["masked"]) == 0)
        & np.isfinite(z) & (z > 0.1) & (z < 0.5)
        & np.isfinite(log_m_star) & (log_m_star < 11.1)
    )

    xyz_comoving = comoving_xyz_mpc_h70(catalogue["RAJ2000"], catalogue["DECJ2000"], z)
    isolated_concurrent = isolation_mask(xyz_comoving, z, log_m_kids, candidates, proper_radius_mpc_h70=4.0)
    chi = np.full(len(z), np.nan)
    valid_z = np.isfinite(z) & (z >= 0.0) & (z <= 1.5)
    chi[valid_z] = FlatCosmology(h0=70.0, omega_m=0.2793).comoving_distance_mpc(z[valid_z])
    xyz_angular = unit_xyz(catalogue["RAJ2000"], catalogue["DECJ2000"]) * (chi / (1.0 + z))[:, None]
    isolated_angular = fixed_radius_isolation(
        xyz_angular, log_m_kids, candidates, valid_native, radius=4.0
    )
    selected_concurrent = candidates & isolated_concurrent
    selected_angular = candidates & isolated_angular

    with np.load("evidence/kids_isolation_scan_v016/compact_isolation_inputs.npz", allow_pickle=False) as fallback:
        fallback_log_m_kids = np.asarray(fallback["log_m_kids_h70_1"], dtype=float)
        fallback_log_m_star = np.asarray(fallback["log_m_star_mistele"], dtype=float)
    hybrid_log_m_kids = np.where(valid_native, log_m_kids, fallback_log_m_kids)
    hybrid_log_m_star = np.where(valid_native, log_m_star, fallback_log_m_star)
    hybrid_candidates = (
        (np.asarray(catalogue["masked"]) == 0)
        & np.isfinite(z) & (z > 0.1) & (z < 0.5)
        & np.isfinite(hybrid_log_m_star) & (hybrid_log_m_star < 11.1)
    )
    hybrid_pool = np.isfinite(hybrid_log_m_kids)
    hybrid_isolated_angular = fixed_radius_isolation(
        xyz_angular, hybrid_log_m_kids, hybrid_candidates, hybrid_pool, radius=4.0
    )
    hybrid_selected_angular = hybrid_candidates & hybrid_isolated_angular

    selected_path = args.output_dir / "selected_angular_native_rows.npy"
    hybrid_selected_path = args.output_dir / "selected_angular_hybrid_rows.npy"
    unmatched_hybrid_selected_path = args.output_dir / "unmatched_hybrid_selected_rows.npy"
    unmatched_path = args.output_dir / "unmatched_rows.npy"
    np.save(selected_path, np.flatnonzero(selected_angular).astype(np.int32))
    np.save(hybrid_selected_path, np.flatnonzero(hybrid_selected_angular).astype(np.int32))
    np.save(
        unmatched_hybrid_selected_path,
        np.flatnonzero(hybrid_selected_angular & ~valid_native).astype(np.int32),
    )
    np.save(unmatched_path, np.flatnonzero(~valid_native).astype(np.int32))
    max_sep = float(
        np.rad2deg(2.0 * np.arcsin(np.minimum(1.0, distances[matched, 0] / 2.0))).max()
        * 3600.0
    )
    receipt = {
        "schema": "darkpipe.kids-native-lens-reconstruction.v1",
        "started_at": started,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "tap_query": (
            "SELECT RAJ2000,DECJ2000,MAG_GAAP_u,MAG_GAAP_r,MAG_AUTO "
            "FROM KiDS_DR4_0_ugriZYJHKs_cat_fits_V3 "
            f"WHERE MAG_AUTO < {args.tap_mag_limit:g}"
        ),
        "tap_source": "https://archive.eso.org/tap_cat/sync",
        "tap_fits": {"bytes": args.tap_fits.stat().st_size, "sha256": sha256(args.tap_fits), "rows": primary_tap_rows, "row_bytes": tap_row_bytes},
        "supplement_fits": supplement_receipts,
        "bright_rows": int(len(matched)),
        "matched_rows": int(np.count_nonzero(matched)),
        "matched_fraction": float(np.mean(matched)),
        "valid_native_gaap_rows": int(np.count_nonzero(valid_native)),
        "ambiguous_two_matches_within_tolerance": int(np.count_nonzero(ambiguous)),
        "coordinate_tolerance_arcsec": tolerance_arcsec,
        "maximum_selected_match_separation_arcsec": max_sep,
        "candidate_rows_before_isolation": int(np.count_nonzero(candidates)),
        "concurrent_comoving_geometry_count": int(np.count_nonzero(selected_concurrent)),
        "angular_diameter_cartesian_geometry_count": int(np.count_nonzero(selected_angular)),
        "published_target_count": 106843,
        "angular_geometry_delta": int(np.count_nonzero(selected_angular) - 106843),
        "hybrid_reconstructed_fallback_rows": int(np.count_nonzero(~valid_native)),
        "hybrid_angular_diameter_cartesian_geometry_count": int(np.count_nonzero(hybrid_selected_angular)),
        "hybrid_angular_geometry_delta": int(np.count_nonzero(hybrid_selected_angular) - 106843),
        "hybrid_authority": "SENSITIVITY_ONLY_NATIVE_GAAP_WITH_LEPHARE_RECONSTRUCTION_FOR_UNMATCHED_ROWS",
        "hybrid_selected_rows": {"path": hybrid_selected_path.as_posix(), "sha256": sha256(hybrid_selected_path), "count": int(np.count_nonzero(hybrid_selected_angular))},
        "unmatched_hybrid_selected_rows": {"path": unmatched_hybrid_selected_path.as_posix(), "sha256": sha256(unmatched_hybrid_selected_path), "count": int(np.count_nonzero(hybrid_selected_angular & ~valid_native))},
        "unmatched_rows": {"path": unmatched_path.as_posix(), "sha256": sha256(unmatched_path), "count": int(np.count_nonzero(~valid_native))},
        "tap_vs_bright_mag_auto_delta_quantiles": {
            str(q): float(np.nanquantile(mag_auto_tap - np.asarray(catalogue["MAG_AUTO_CALIB"], dtype=float), q)) for q in (0.01, 0.5, 0.99)
        },
        "selected_rows": {"path": selected_path.as_posix(), "sha256": sha256(selected_path), "count": int(np.count_nonzero(selected_angular))},
        "authority": "NATIVE_GAAP_RECOVERY_AND_LENS_SELECTION_RECONSTRUCTION_NO_LENSING_RESULT",
        "scientific_result": False,
        "next_gate": "FULL_PAIR_ACCUMULATION_WITH_RANDOMS_AND_COVARIANCE",
    }
    receipt_path = args.output_dir / "run_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
