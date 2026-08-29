"""Run the preregistered DarkPipe v0.12 covariance/operator shadow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from darkpipe.covariance_operator_shadow import (
    CAMPAIGN_ID,
    CovarianceOperatorConfig,
    derive_operator_shadow,
    load_corrected_covariance,
    load_profile_family,
    sha256_file,
    summarize_operator_shadow,
)


MASS_BIN_MINIMA = [8.5, 10.3, 10.6, 10.8]
PROFILE_NAMES = [
    f"Fig-3_Lensing-rotation-curves_Massbin-{index}.txt"
    for index in range(1, 5)
]
COVARIANCE_NAME = "Fig-3_Lensing-rotation-curves_Massbins_covmatrix.txt"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/third_party/kids_brouwer2021"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("darkpipe_v012_covariance_operator"),
    )
    parser.add_argument("--quadrature-nodes", type=int, default=512)
    return parser


def _write_figure(result, path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), sharex=True, sharey=True)
    for mass_bin, axis in enumerate(axes.flat, start=1):
        selected = result[result["mass_bin"] == mass_bin].sort_values("radius_mpc")
        radius = selected["radius_mpc"].to_numpy(dtype=float)
        ratio = selected["exact_over_sis_ratio"].to_numpy(dtype=float)
        tail_low = (
            selected["tail_envelope_low_m_s2"].to_numpy(dtype=float)
            / selected["g_sis_m_s2"].to_numpy(dtype=float)
        )
        tail_high = (
            selected["tail_envelope_high_m_s2"].to_numpy(dtype=float)
            / selected["g_sis_m_s2"].to_numpy(dtype=float)
        )
        exact_sigma = selected["g_exact_sigma_stat_m_s2"].to_numpy(dtype=float)
        sis = selected["g_sis_m_s2"].to_numpy(dtype=float)
        axis.fill_between(radius, tail_low, tail_high, color="#f2b84b", alpha=0.28)
        axis.errorbar(
            radius,
            ratio,
            yerr=exact_sigma / sis,
            fmt="o-",
            color="#235789",
            markersize=3,
            linewidth=1,
            capsize=2,
        )
        axis.axhline(1.0, color="black", linestyle="--", linewidth=0.8)
        axis.set_xscale("log")
        axis.set_title(f"Stellar-mass bin {mass_bin}")
        axis.grid(alpha=0.2)
    fig.supxlabel("Projected radius [Mpc]")
    fig.supylabel("stack-first exact / published SIS acceleration")
    fig.suptitle(
        "DarkPipe v0.12: covariance-aware operator shadow\n"
        "band: zero/SIS/flat tail envelope; bars: propagated statistical sigma"
    )
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _write_closure(summary: dict, path: Path) -> None:
    counts = summary["status_counts"]
    resolved = counts.get("OPERATOR_DIFFERENCE_RESOLVED_CONDITIONAL_95", 0)
    statistical = counts.get(
        "OPERATOR_DIFFERENCE_STATISTICALLY_UNRESOLVED_95", 0
    )
    systematics = counts.get("OPERATOR_DIFFERENCE_UNRESOLVED_SYSTEMATICS", 0)
    text = f"""# Cierre sustantivo — DarkPipe v0.12

La campaña queda **mejor posicionada metodológicamente, pero no promociona la conjetura física**. Se incorporaron cuatro perfiles radiales ESD de KiDS-1000 y su covarianza conjunta 60×60; se comparó la conversión SIS publicada con una aplicación *stack-first* del operador esférico exacto y se propagó la covarianza de la diferencia pareada. El cociente exacto/SIS mediano es `{summary['median_exact_over_sis_ratio']:.6f}` y el máximo desplazamiento absoluto es `{summary['maximum_absolute_log10_exact_over_sis_dex']:.6f}` dex. De 60 bins, `{resolved}` muestran una diferencia condicional resuelta al 95 %, `{statistical}` no resuelven diferencia estadística y `{systematics}` quedan dominados por la elección de cola o interpolación.

Esto significa que SIS funciona razonablemente como aproximación global, pero no es intercambiable con la deproyección integral en todos los radios y masas. El resultado cuantifica una sombra del operador; **no vuelve a estimar la RAR apilada en g_bar** y no autoriza transferir estos cambios al inobservable de v0.11, porque faltan los perfiles por lente y los pesos dependientes del radio. El componente cruzado conserva autoridad descriptiva solamente: mediana `|z|={summary['descriptive_cross_abs_z_median']:.3f}`, máximo `|z|={summary['descriptive_cross_abs_z_maximum']:.3f}` y `{summary['descriptive_cross_abs_z_gt_2_count']}` de 60 valores por encima de 2 usando el error tangencial, sin inventar una covarianza cruzada no publicada. El próximo salto decisivo es conseguir o reconstruir los pesos/perfiles por lente para deproyectar antes de apilar; hasta entonces la transferencia a RAR permanece `{summary['rar_transfer_authority']}`.
"""
    path.write_text(text, encoding="utf-8")


def main() -> int:
    args = build_parser().parse_args()
    data_dir = args.data_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    profile_paths = [data_dir / name for name in PROFILE_NAMES]
    profiles = load_profile_family(profile_paths, MASS_BIN_MINIMA)
    covariance_path = data_dir / COVARIANCE_NAME
    covariance, _, covariance_diagnostics = load_corrected_covariance(
        covariance_path, profiles
    )
    config = CovarianceOperatorConfig(quadrature_nodes=args.quadrature_nodes)
    result, matrices = derive_operator_shadow(profiles, covariance, config)

    source_paths = [data_dir / "README.txt", *profile_paths, covariance_path]
    source_receipts = [
        {
            "path": str(path.relative_to(Path.cwd()))
            if path.is_relative_to(Path.cwd())
            else str(path),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in source_paths
    ]
    summary = summarize_operator_shadow(
        result, config, covariance_diagnostics, source_receipts
    )

    result_path = output_dir / "covariance_operator_shadow.csv"
    matrix_path = output_dir / "covariance_operator_matrices.npz"
    summary_path = output_dir / "summary.json"
    figure_path = output_dir / "covariance_operator_shadow.png"
    closure_path = output_dir / "SUBSTANTIVE_CLOSURE_ES.md"
    result.to_csv(result_path, index=False)
    np.savez_compressed(matrix_path, **matrices)
    _write_figure(result, figure_path)
    _write_closure(summary, closure_path)
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    artifact_paths = [
        result_path,
        matrix_path,
        summary_path,
        figure_path,
        closure_path,
    ]
    manifest = {
        "schema": "darkpipe.run_manifest.v1",
        "campaign_id": CAMPAIGN_ID,
        "artifacts": [
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in artifact_paths
        ],
        "source_receipts": source_receipts,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
