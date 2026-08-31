#!/usr/bin/env python3
"""Match native SOM-gold GAAP photometry back to KiDS-bright lens IDs.

This is a full real-catalogue identity join executed by HTTP ranges.  It is a
diagnostic recovery surface: SOM-gold is a source-selected subset and therefore
cannot be silently treated as the complete bright-lens photometry table.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from darkpipe.fits_range_table import iter_remote_numeric_columns
from darkpipe.kids_lens_sample import BRIGHT_BYTES, BRIGHT_URL
from run_darkpipe_kids_source_selection_v016 import SOURCE_BYTES, SOURCE_ROWS, SOURCE_URL


def atomic_json(path: Path, payload: object) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


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


def load_bright_coordinates() -> tuple[np.ndarray, np.ndarray]:
    ra_chunks = []
    dec_chunks = []
    for _, data in iter_remote_numeric_columns(
        BRIGHT_URL,
        total_bytes=BRIGHT_BYTES,
        names=("RAJ2000", "DECJ2000"),
        target_chunk_bytes=32 * 1024 * 1024,
    ):
        ra_chunks.append(data["RAJ2000"])
        dec_chunks.append(data["DECJ2000"])
    return np.concatenate(ra_chunks), np.concatenate(dec_chunks)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("evidence/kids_gaap_match_v016"))
    parser.add_argument("--chunk-mib", type=int, default=128)
    args = parser.parse_args()
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output / "checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8")) if checkpoint_path.exists() else {
        "schema": "darkpipe.kids-gaap-coordinate-match-checkpoint.v1",
        "next_row": 0,
        "chunks": 0,
        "source_matches": 0,
        "duplicate_source_matches": 0,
        "maximum_matched_separation_arcsec": 0.0,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    bright_ra, bright_dec = load_bright_coordinates()
    bright_xyz = unit_xyz(bright_ra, bright_dec)
    tree = cKDTree(bright_xyz)
    n_lens = len(bright_ra)
    tolerance_arcsec = 0.5
    chord_tolerance = 2.0 * np.sin(np.deg2rad(tolerance_arcsec / 3600.0) / 2.0)
    matched_path = output / "matched.npy"
    u_path = output / "mag_gaap_u.npy"
    r_path = output / "mag_gaap_r.npy"
    if int(checkpoint["next_row"]) == 0:
        matched = np.lib.format.open_memmap(matched_path, mode="w+", dtype=np.bool_, shape=(n_lens,))
        mag_u = np.lib.format.open_memmap(u_path, mode="w+", dtype=np.float32, shape=(n_lens,))
        mag_r = np.lib.format.open_memmap(r_path, mode="w+", dtype=np.float32, shape=(n_lens,))
        matched[:] = False
        mag_u[:] = np.nan
        mag_r[:] = np.nan
    else:
        matched = np.load(matched_path, mmap_mode="r+")
        mag_u = np.load(u_path, mmap_mode="r+")
        mag_r = np.load(r_path, mmap_mode="r+")

    for first, data in iter_remote_numeric_columns(
        SOURCE_URL,
        total_bytes=SOURCE_BYTES,
        names=("RAJ2000", "DECJ2000", "MAG_GAAP_u", "MAG_GAAP_r"),
        target_chunk_bytes=args.chunk_mib * 1024 * 1024,
        start_row=int(checkpoint["next_row"]),
    ):
        source_xyz = unit_xyz(data["RAJ2000"], data["DECJ2000"])
        distance, lens_rows_all = tree.query(
            source_xyz, k=1, distance_upper_bound=chord_tolerance, workers=-1
        )
        same = np.isfinite(distance) & (lens_rows_all < n_lens)
        lens_rows = lens_rows_all[same]
        duplicate = matched[lens_rows]
        checkpoint["duplicate_source_matches"] += int(np.count_nonzero(duplicate))
        if np.any(duplicate):
            raise RuntimeError("a KiDS-bright ID matched more than one SOM-gold source row")
        matched[lens_rows] = True
        mag_u[lens_rows] = data["MAG_GAAP_u"][same]
        mag_r[lens_rows] = data["MAG_GAAP_r"][same]
        if np.any(same):
            angle_arcsec = np.rad2deg(2.0 * np.arcsin(np.minimum(1.0, distance[same] / 2.0))) * 3600.0
            checkpoint["maximum_matched_separation_arcsec"] = max(
                float(checkpoint["maximum_matched_separation_arcsec"]), float(np.max(angle_arcsec))
            )
        matched.flush(); mag_u.flush(); mag_r.flush()
        rows = len(data["RAJ2000"])
        checkpoint["source_matches"] += int(np.count_nonzero(same))
        checkpoint["next_row"] = first + rows
        checkpoint["chunks"] += 1
        checkpoint["updated_at"] = datetime.now(timezone.utc).isoformat()
        atomic_json(checkpoint_path, checkpoint)
        print(f"rows={checkpoint['next_row']}/{SOURCE_ROWS} lens_matches={checkpoint['source_matches']}", flush=True)

    if int(checkpoint["next_row"]) != SOURCE_ROWS:
        raise RuntimeError("incomplete SOM-gold identity scan")
    compact = np.load("evidence/kids_isolation_scan_v016/compact_isolation_inputs.npz")
    base = np.asarray(compact["base"], dtype=bool)
    initial_selected = np.load("evidence/kids_lens_sample_v016/selected_lens_row_indices.npy")
    initial_mask = np.zeros(n_lens, dtype=bool)
    initial_mask[initial_selected] = True
    valid_native = matched & np.isfinite(mag_u) & np.isfinite(mag_r) & (mag_u < 90) & (mag_r < 90)
    native_etg = np.zeros(n_lens, dtype=bool)
    native_etg[valid_native] = (mag_u[valid_native] - mag_r[valid_native]) > 2.5
    old_etg = np.asarray(compact["is_etg"], dtype=bool)
    receipt = {
        **checkpoint,
        "schema": "darkpipe.kids-gaap-coordinate-match.v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "bright_lens_rows": n_lens,
        "coordinate_match_tolerance_arcsec": tolerance_arcsec,
        "matched_lens_rows": int(np.count_nonzero(matched)),
        "matched_fraction_all": float(np.mean(matched)),
        "valid_native_gaap_rows": int(np.count_nonzero(valid_native)),
        "base_rows": int(np.count_nonzero(base)),
        "valid_native_gaap_base_rows": int(np.count_nonzero(valid_native & base)),
        "valid_native_gaap_base_fraction": float(np.count_nonzero(valid_native & base) / np.count_nonzero(base)),
        "initial_selected_rows": int(np.count_nonzero(initial_mask)),
        "valid_native_gaap_initial_selected_rows": int(np.count_nonzero(valid_native & initial_mask)),
        "native_vs_reconstructed_type_disagreements_on_valid_base": int(np.count_nonzero(valid_native & base & (native_etg != old_etg))),
        "native_vs_reconstructed_type_disagreement_fraction_on_valid_base": float(np.mean((native_etg != old_etg)[valid_native & base])) if np.any(valid_native & base) else None,
        "artifacts": [
            {"path": path.as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in (matched_path, u_path, r_path)
        ],
        "authority": "BOUNDED_COORDINATE_JOIN_TO_SOURCE_SELECTED_SOM_GOLD_NOT_COMPLETE_LENS_PHOTOMETRY",
        "scientific_result": False,
        "next_gate": "RECOVER_COMPLETE_NATIVE_BRIGHT_GAAP_OR_AUTHOR_SAMPLE_RECEIPT",
    }
    atomic_json(output / "run_receipt.json", receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
