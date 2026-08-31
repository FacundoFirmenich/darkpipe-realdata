#!/usr/bin/env python3
"""Derive and plot the real published KiDS RAR inobservable shadow."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from darkpipe.kids_rar_shadow import derive_rar_shadows, descriptive_summary


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/mistele2024_weak_lensing_rar_table1.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("evidence/kids_rar_shadow_v016"))
    args = parser.parse_args()
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    source = pd.read_csv(args.input)
    shadows = derive_rar_shadows(source)
    table_path = output / "derived_rar_shadows.csv"
    shadows.to_csv(table_path, index=False)
    summary = descriptive_summary(shadows)

    x = shadows["log10_gbar_m_s2"].to_numpy(float)
    eta = shadows["eta_log10_gobs_over_gbar"].to_numpy(float)
    sigma = shadows["sigma_measurement_log10_gobs"].to_numpy(float)
    mond = shadows["residual_to_mond_log10"].to_numpy(float)
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    axes[0].errorbar(x, eta, yerr=sigma, fmt="o", color="#252422", ecolor="#eb5e28", capsize=2)
    axes[0].axhline(0.0, color="0.5", lw=1)
    axes[0].set(xlabel=r"$\log_{10} g_{bar}$ [m s$^{-2}$]", ylabel=r"$\eta=\log_{10}(g_{obs}/g_{bar})$", title="Effective inobservable shadow")
    axes[1].errorbar(x, mond, yerr=sigma, fmt="o", color="#403d39", ecolor="#eb5e28", capsize=2)
    axes[1].axhline(0.0, color="0.5", lw=1)
    axes[1].set(xlabel=r"$\log_{10} g_{bar}$ [m s$^{-2}$]", ylabel="Residual to reference RAR [dex]", title="Reference MOND-shaped mapping")
    for axis in axes:
        axis.grid(alpha=0.2)
    figure_path = output / "kids_rar_shadow.png"
    figure.savefig(figure_path, dpi=180)
    plt.close(figure)

    receipt = {
        "schema": "darkpipe.kids-rar-shadow.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_file": str(args.input),
        "source_sha256": sha256(args.input),
        "derived_table_sha256": sha256(table_path),
        "figure_sha256": sha256(figure_path),
        "summary": summary,
        "scientific_result": "REAL_PUBLISHED_BIN_LEVEL_DERIVED_INOBSERVABLE",
        "model_identity": "NOT_ESTIMABLE",
        "plasma_hyperstate_claim": "NOT_TESTED",
    }
    receipt_path = output / "run_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
