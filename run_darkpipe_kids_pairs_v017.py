#!/usr/bin/env python3
"""Stream the public KiDS source FITS into per-lens pair sufficient statistics."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from darkpipe.fits_range_table import iter_remote_numeric_columns
from darkpipe.kids_streaming_pairs import (
    LensPayload,
    ORIENTATION_BASIS_KEYS,
    RADIAL_EDGES_MPC_H70,
    RADIAL_EDGES_SHA256,
    STREAMING_PAIR_AUTHORITY,
    accumulate_source_chunk,
    empty_pair_sums,
    pair_sums_sha256,
    save_pair_partition,
)


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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_authoritative_lenses(payload_path: Path, receipt_path: Path) -> LensPayload:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload_receipt = receipt.get("selected_lens_pair_payload", {})
    errors = []
    if receipt.get("valid_native_gaap_rows") != receipt.get("bright_rows"):
        errors.append("native GAAP coverage is incomplete")
    if receipt.get("angular_geometry_delta") != 0:
        errors.append("native angular selection diverges from the published count")
    if payload_receipt.get("count") != 106_843:
        errors.append("pair payload does not contain exactly 106843 lenses")
    observed_hash = sha256(payload_path)
    if payload_receipt.get("sha256") != observed_hash:
        errors.append("pair payload SHA-256 does not match its reconstruction receipt")
    if errors:
        raise RuntimeError("LENS_PAYLOAD_AUTHORITY_GATE_FAILED: " + "; ".join(errors))
    with np.load(payload_path, allow_pickle=False) as values:
        lenses = LensPayload(
            ra_deg=np.asarray(values["ra_deg"], dtype=float),
            dec_deg=np.asarray(values["dec_deg"], dtype=float),
            redshift=np.asarray(values["redshift"], dtype=float),
            baryonic_mass_msun=np.asarray(values["baryonic_mass_msun"], dtype=float),
            source_row=np.asarray(values["source_row"], dtype=np.int64),
        )
    if lenses.count != 106_843:
        raise RuntimeError("decoded pair payload does not contain exactly 106843 lenses")
    return lenses


def load_sigma_grid(path: Path, lens_redshift: np.ndarray) -> np.ndarray:
    table = np.genfromtxt(path, delimiter=",", names=True, dtype=float)
    grid_redshift = np.asarray(table["lens_redshift"], dtype=float)
    if (
        grid_redshift.ndim != 1
        or np.any(~np.isfinite(grid_redshift))
        or np.any(np.diff(grid_redshift) <= 0)
    ):
        raise RuntimeError("invalid effective Sigma_critical lookup redshift grid")
    if np.min(lens_redshift) < grid_redshift[0] or np.max(lens_redshift) > grid_redshift[-1]:
        raise RuntimeError("lens redshift lies outside effective Sigma_critical lookup")
    columns = []
    for tomo in range(1, 6):
        sigma = np.asarray(table[f"sigma_crit_tomo{tomo}_msun_mpc2"], dtype=float)
        columns.append(np.interp(lens_redshift, grid_redshift, sigma))
    result = np.column_stack(columns)
    if np.any(~np.isfinite(result)) or np.any(result <= 0):
        raise RuntimeError("interpolated effective Sigma_critical grid is invalid")
    return result


def load_checkpoint(
    path: Path,
    expected_start: int,
    keys: tuple[str, ...] = (
        "sum_pair_weight",
        "sum_tangential",
        "sum_cross",
        "sum_shape_variance",
        "pair_count",
    ),
) -> tuple[dict[str, np.ndarray], dict[str, object]]:
    with np.load(path, allow_pickle=False) as values:
        metadata = json.loads(str(values["metadata_json"]))
        sums = {key: np.asarray(values[key]).copy() for key in keys}
        stored_hash = str(values["content_sha256"])
    if metadata.get("start_row") != expected_start:
        raise RuntimeError("checkpoint start row does not match requested partition")
    if pair_sums_sha256(sums) != stored_hash:
        raise RuntimeError("checkpoint pair-sum content hash mismatch")
    return sums, metadata


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-url", default=SOURCE_URL)
    parser.add_argument("--source-total-bytes", type=int, default=SOURCE_TOTAL_BYTES)
    parser.add_argument("--start-row", type=int, default=0)
    parser.add_argument("--stop-row", type=int, default=SOURCE_TOTAL_ROWS)
    parser.add_argument("--chunk-mib", type=int, default=32)
    parser.add_argument(
        "--include-orientation-basis",
        action="store_true",
        help="retain the four exact e1/e2 x cos/sin(2phi) basis sums",
    )
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
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 0 <= args.start_row < args.stop_row <= SOURCE_TOTAL_ROWS:
        raise ValueError("row partition must satisfy 0 <= start < stop <= 21262011")
    if args.chunk_mib <= 0:
        raise ValueError("chunk-mib must be positive")

    lenses = load_authoritative_lenses(args.lens_payload, args.lens_receipt)
    sigma_grid = load_sigma_grid(args.sigma_lookup, lenses.redshift)
    started = datetime.now(timezone.utc).isoformat()
    pair_sums = empty_pair_sums(lenses.count, len(RADIAL_EDGES_MPC_H70) - 1)
    if args.include_orientation_basis:
        pair_sums.update(
            {
                key: np.zeros_like(pair_sums["sum_pair_weight"])
                for key in ORIENTATION_BASIS_KEYS
            }
        )
    pair_keys = tuple(pair_sums)
    next_row = args.start_row
    chunks = 0
    diagnostics = {
        "source_rows": 0,
        "selected_source_rows": 0,
        "candidate_pairs": 0,
        "accepted_pairs": 0,
    }
    seen_tiles: set[str] = set()
    if args.output.exists():
        pair_sums, previous = load_checkpoint(args.output, args.start_row, pair_keys)
        next_row = int(previous["next_row"])
        chunks = int(previous["chunks"])
        started = str(previous["started_at"])
        diagnostics = {key: int(previous["diagnostics"][key]) for key in diagnostics}
        seen_tiles = set(previous.get("source_tiles", []))
        if int(previous["stop_row"]) != args.stop_row:
            raise RuntimeError("checkpoint stop row does not match requested partition")

    for first_row, source_chunk in iter_remote_numeric_columns(
        args.source_url,
        total_bytes=args.source_total_bytes,
        names=SOURCE_COLUMNS,
        target_chunk_bytes=args.chunk_mib * 1024 * 1024,
        start_row=next_row,
        stop_row=args.stop_row,
    ):
        seen_tiles.update(
            raw.decode("ascii", "strict").strip()
            for raw in np.asarray(source_chunk["THELI_NAME"])
        )
        chunk_sums, chunk_diagnostics = accumulate_source_chunk(
            lenses,
            source_chunk,
            sigma_grid,
            include_orientation_basis=args.include_orientation_basis,
        )
        for key in pair_sums:
            pair_sums[key] += chunk_sums[key]
        chunk_rows = int(chunk_diagnostics["source_rows"])
        next_row = int(first_row + chunk_rows)
        chunks += 1
        for key in diagnostics:
            diagnostics[key] += int(chunk_diagnostics[key])
        metadata = {
            "schema": "darkpipe.kids-pair-partition.v1",
            "started_at": started,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "complete": next_row == args.stop_row,
            "source_url": args.source_url,
            "source_total_bytes": args.source_total_bytes,
            "start_row": args.start_row,
            "next_row": next_row,
            "stop_row": args.stop_row,
            "chunks": chunks,
            "diagnostics": diagnostics,
            "source_tile_count": len(seen_tiles),
            "source_tiles": sorted(seen_tiles),
            "lens_count": lenses.count,
            "radial_edges_mpc_h70": RADIAL_EDGES_MPC_H70.tolist(),
            "radial_edges_sha256": RADIAL_EDGES_SHA256,
            "lens_payload_sha256": sha256(args.lens_payload),
            "sigma_lookup_sha256": sha256(args.sigma_lookup),
            "orientation_basis_included": args.include_orientation_basis,
            "authority": STREAMING_PAIR_AUTHORITY,
            "scientific_result": False,
            "next_gate": "RANDOM_SUBTRACTION_COVARIANCE_AND_DEPROJECT_FIRST_RAR",
        }
        save_pair_partition(args.output, pair_sums, metadata)
        print(json.dumps(metadata, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
