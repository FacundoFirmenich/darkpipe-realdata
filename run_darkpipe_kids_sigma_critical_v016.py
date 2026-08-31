#!/usr/bin/env python3
"""Build the real KiDS Eq. 10 effective critical-density lookup."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from darkpipe.kids_pair_estimator import effective_sigma_critical_lookup, load_som_nz
from darkpipe.object_lensing import FlatLambdaCDM


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nz-dir", type=Path, default=Path("data/third_party/SOM_N_of_Z"))
    parser.add_argument("--output-dir", type=Path, default=Path("evidence/kids_sigma_critical_v016"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(args.nz_dir.glob("*TOMO*_Nz.asc"))
    nz = load_som_nz(args.nz_dir)
    lens_grid = np.linspace(0.1, 0.5, 81)
    lookup = effective_sigma_critical_lookup(
        lens_grid,
        nz,
        cosmology=FlatLambdaCDM(h0_km_s_mpc=73.0, omega_m=0.2793),
    )
    table_path = args.output_dir / "effective_sigma_critical_lookup.csv"
    sigma = np.asarray(lookup["sigma_critical_msun_mpc2"])
    inverse = np.asarray(lookup["inverse_sigma_critical_mpc2_msun"])
    with table_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["lens_redshift"] + [f"sigma_crit_tomo{i}_msun_mpc2" for i in range(1, 6)] + [f"inverse_sigma_crit_tomo{i}_mpc2_msun" for i in range(1, 6)])
        for row, lens_z in enumerate(lens_grid):
            writer.writerow([f"{lens_z:.8f}"] + [f"{value:.12e}" for value in sigma[row]] + [f"{value:.12e}" for value in inverse[row]])
    receipt = {
        "schema": "darkpipe.kids-effective-sigma-critical.v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "method": "MISTELE2024_EQ10_LENS_GAUSSIAN_AND_RENORMALIZED_SOM_NZ",
        "cosmology": {"H0_km_s_Mpc": 73.0, "Omega_m": 0.2793, "flat": True},
        "lens_photoz_sigma": "0.02*(1+z_ANN)",
        "lens_grid": {"minimum": 0.1, "maximum": 0.5, "count": 81},
        "source_tarball_url": "https://kids.strw.leidenuniv.nl/DR4/data_files/KiDS1000_SOM_N_of_Z.tar.gz",
        "source_files": [{"name": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)} for path in files],
        "lookup_csv": {"path": table_path.as_posix(), "bytes": table_path.stat().st_size, "sha256": sha256(table_path)},
        "sigma_critical_range_msun_mpc2": {"minimum": float(np.min(sigma)), "maximum": float(np.max(sigma))},
        "finite": bool(np.all(np.isfinite(sigma))),
        "positive": bool(np.all(sigma > 0)),
        "pair_cut_for_use": "Z_B_source > z_ANN_lens + 0.2",
        "authority": lookup["authority"],
        "scientific_result": False,
        "next_gate": "OBJECT_LEVEL_PAIR_ACCUMULATION_RANDOM_SUBTRACTION_CROSS_NULL_COVARIANCE",
    }
    receipt_path = args.output_dir / "run_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
