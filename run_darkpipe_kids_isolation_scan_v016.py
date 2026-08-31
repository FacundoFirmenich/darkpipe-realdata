#!/usr/bin/env python3
"""Build a compact real-data cache and adjudicate the KiDS isolation geometry."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from darkpipe.kids_lens_sample import (
    comoving_xyz_mpc_h70,
    derive_masses,
    load_aligned_catalogues,
    nearest_qualifying_neighbor_proper_distance,
)


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("evidence/kids_isolation_scan_v016"))
    parser.add_argument("--chunk-mib", type=int, default=128)
    args = parser.parse_args()
    started = datetime.now(timezone.utc).isoformat()
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    cache_path = output / "compact_isolation_inputs.npz"
    if cache_path.exists():
        with np.load(cache_path, allow_pickle=False) as cache:
            xyz = cache["xyz_comoving_mpc_h70"].astype(float)
            z = cache["redshift"].astype(float)
            log_m_kids = cache["log_m_kids_h70_1"].astype(float)
            log_m_star = cache["log_m_star_mistele"].astype(float)
            is_etg = cache["is_etg"]
            base = cache["base"]
    else:
        catalogue = load_aligned_catalogues(target_chunk_bytes=args.chunk_mib * 1024 * 1024)
        masses = derive_masses(catalogue)
        z = np.asarray(catalogue["zphot_ANNz2"], dtype=float)
        log_m_kids = masses["log_m_kids_h70_1"]
        log_m_star = masses["log_m_star_mistele"]
        is_etg = masses["is_etg"]
        base = (
            (np.asarray(catalogue["masked"]) == 0)
            & np.isfinite(z)
            & (z > 0.1)
            & (z < 0.5)
            & np.isfinite(log_m_star)
            & (log_m_star < 11.1)
        )
        xyz = comoving_xyz_mpc_h70(
            np.asarray(catalogue["RAJ2000"], dtype=float),
            np.asarray(catalogue["DECJ2000"], dtype=float),
            z,
        )
        np.savez_compressed(
            cache_path,
            xyz_comoving_mpc_h70=xyz.astype(np.float32),
            redshift=z.astype(np.float32),
            log_m_kids_h70_1=log_m_kids.astype(np.float32),
            log_m_star_mistele=log_m_star.astype(np.float32),
            is_etg=is_etg,
            base=base,
        )
    nearest = nearest_qualifying_neighbor_proper_distance(
        xyz, z, log_m_kids, base, max_proper_radius_mpc_h70=5.5, batch_size=5_000
    )
    radii = np.arange(2.5, 5.51, 0.25)
    counts = {f"{radius:.2f}": int(np.count_nonzero(base & (nearest > radius))) for radius in radii}
    np.save(output / "nearest_qualifying_neighbor_proper_mpc_h70.npy", nearest.astype(np.float32))
    target = 106_843
    nearest_radius = min(counts, key=lambda key: abs(counts[key] - target))
    report = {
        "schema": "darkpipe.kids-isolation-geometry-scan.v1",
        "started_at": started,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "rows": int(len(z)),
        "base_before_isolation": int(np.count_nonzero(base)),
        "preregistered_radius_mpc_h70": 4.0,
        "count_at_preregistered_radius": counts["4.00"],
        "published_count": target,
        "count_delta_at_preregistered_radius": counts["4.00"] - target,
        "radius_scan_counts": counts,
        "nearest_scan_radius_to_published_count": nearest_radius,
        "nearest_scan_count": counts[nearest_radius],
        "interpretation": "DIAGNOSTIC_ONLY_NO_RADIUS_TUNING_AUTHORIZED",
        "authority": "LENS_ISOLATION_GEOMETRY_DIAGNOSTIC_NO_LENSING_RESULT",
    }
    atomic_json(output / "run_receipt.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
