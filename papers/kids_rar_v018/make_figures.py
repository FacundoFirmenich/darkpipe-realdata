#!/usr/bin/env python3
"""Generate manuscript figures from the sealed DarkPipe v0.17 CSV products."""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence" if (ROOT / "evidence").is_dir() else ROOT / "evidence_upstream"
FIGURES = ROOT / "paper" / "figures" if (ROOT / "paper").is_dir() else ROOT / "figures"
FIGURES.mkdir(parents=True, exist_ok=True)


def orientation_figure() -> None:
    frame = pd.read_csv(EVIDENCE / "full_orientation_rar.csv")
    corrected = frame[frame["convention"] == "east_ccw_catalog_e2_sign_flipped"].copy()
    current = frame[frame["convention"] == "east_ccw_catalog_e2_as_math"].copy()

    fig, ax = plt.subplots(figsize=(6.4, 4.7))
    ax.errorbar(
        corrected["gbar_m_s2"], corrected["exact_gobs_m_s2"],
        yerr=corrected["exact_gobs_std_diagonal"], fmt="o", ms=4.5,
        color="#1769aa", ecolor="#1769aa", capsize=2,
        label="Corrected KiDS spin-2 convention",
    )
    ax.plot(
        corrected["gbar_m_s2"], corrected["mistele2024_gobs_m_s2"],
        "s-", ms=4, lw=1.2, color="#d1495b", label="Published reference",
    )
    positive = current["exact_gobs_m_s2"] > 0
    ax.plot(
        current.loc[positive, "gbar_m_s2"], current.loc[positive, "exact_gobs_m_s2"],
        "^", ms=4, color="#6c757d", alpha=0.8, label="Pre-repair convention (positive bins)",
    )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"$g_{\rm bar}$ [m s$^{-2}$]")
    ax.set_ylabel(r"$g_{\rm obs}$ [m s$^{-2}$]")
    ax.grid(True, which="both", alpha=0.18)
    ax.legend(frameon=False, fontsize=8.5)
    ax.set_title("Orientation repair localizes a dominant estimator error")
    fig.tight_layout()
    fig.savefig(FIGURES / "darkpipe_orientation_repair.pdf")
    fig.savefig(FIGURES / "darkpipe_orientation_repair.png", dpi=220)
    plt.close(fig)


def random_control_figure() -> None:
    frame = pd.read_csv(EVIDENCE / "signal_random_comparison.csv")
    fig, ax = plt.subplots(figsize=(6.4, 4.7))
    series = [
        ("signal_gobs", "signal_gobs_std", "Signal", "#1769aa", "o"),
        ("pilot_random_gobs", "pilot_random_gobs_std", "10-per-tile random pilot", "#d1495b", "s"),
        ("pilot_corrected_gobs", "pilot_corrected_gobs_std_independent_diagonal", "Signal - pilot", "#2a9d8f", "^"),
    ]
    for y, err, label, color, marker in series:
        valid = np.isfinite(frame[y]) & np.isfinite(frame[err])
        ax.errorbar(
            frame.loc[valid, "radius_mpc_h70"], frame.loc[valid, y],
            yerr=frame.loc[valid, err], fmt=marker, ms=3.5, capsize=1.5,
            lw=0.8, color=color, ecolor=color, alpha=0.86, label=label,
        )
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xscale("log")
    ax.set_yscale("symlog", linthresh=3e-14)
    ax.set_xlabel(r"Projected radius [$h_{70}^{-1}$ Mpc]")
    ax.set_ylabel(r"deproject-first $g_{\rm obs}$ [m s$^{-2}$]")
    ax.grid(True, which="both", alpha=0.18)
    ax.legend(frameon=False, fontsize=8.2)
    ax.set_title("The measured random surface is a material estimator term")
    fig.tight_layout()
    fig.savefig(FIGURES / "darkpipe_random_control.pdf")
    fig.savefig(FIGURES / "darkpipe_random_control.png", dpi=220)
    plt.close(fig)


if __name__ == "__main__":
    orientation_figure()
    random_control_figure()
    print("generated", *(p.name for p in sorted(FIGURES.glob("darkpipe_*"))))
