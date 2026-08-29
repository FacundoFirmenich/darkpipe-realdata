"""Run the frozen v0.11 galaxy-scale weak-lensing multi-shadow derivation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from darkpipe.multishadow import (
    MISTELE_ARTICLE_DOI,
    MISTELE_SOURCE_URL,
    MultiShadowConfig,
    build_cross_shadow_atlas,
    derive_lensing_inobservables,
    load_checked_sparc_profiles,
    load_lensing_rar_table,
    summarize_multishadow,
)
from darkpipe.provenance import write_json

EXPECTED_LENSING_TABLE_SHA256 = (
    "624c19f5f0edd2fca78bc94d108863a5f4b8f516ff15fe0ca65d7854b6ea55d0"
)
EXPECTED_SPARC_V010_SHA256 = (
    "aee55c110eb5dbe593a37e173633383c77f46251527678fc188d8ff4ce6e0977"
)


def _file_receipt(path: Path, *, role: str, license_id: str) -> dict:
    payload = path.read_bytes()
    return {
        "role": role,
        "path": path.as_posix(),
        "byte_count": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "license": license_id,
    }


def _plot(lensing, sparc, atlas, target: Path) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    valid = (
        np.isfinite(sparc["g_baryonic_p50_m_s2"])
        & np.isfinite(sparc["g_observed_p50_m_s2"])
        & (sparc["g_baryonic_p50_m_s2"] > 0.0)
        & (sparc["g_observed_p50_m_s2"] > 0.0)
    )
    sparc_valid = sparc.loc[valid]
    x_sparc = np.log10(sparc_valid["g_baryonic_p50_m_s2"])
    y_sparc = np.log10(sparc_valid["g_observed_p50_m_s2"])
    axes[0].scatter(
        x_sparc, y_sparc, s=5, alpha=0.16, color="0.35", label="SPARC v0.10"
    )
    x = lensing["log10_gbar_m_s2"].to_numpy()
    y = lensing["log10_gobs_m_s2"].to_numpy()
    yerr = lensing["sigma_combined_sensitivity_log10_gobs"].to_numpy()
    axes[0].errorbar(
        x, y, yerr=yerr, fmt="o", color="#b2182b", capsize=2, label="KiDS lensing"
    )
    limits = [-15.2, -9.0]
    axes[0].plot(
        limits, limits, ls="--", lw=1, color="black", label="g_obs = g_bar"
    )
    axes[0].set_xlim(limits)
    axes[0].set_ylim(limits)
    axes[0].set_xlabel("log10 g_bar [m/s^2]")
    axes[0].set_ylabel("log10 g_obs [m/s^2]")
    axes[0].legend(loc="upper left", fontsize=8)

    eta_sparc = y_sparc - x_sparc
    axes[1].scatter(x_sparc, eta_sparc, s=5, alpha=0.14, color="0.35")
    axes[1].errorbar(
        x,
        lensing["eta_log10_gobs_over_gbar"],
        yerr=yerr,
        fmt="o",
        color="#2166ac",
        capsize=2,
    )
    estimable = (
        atlas["comparison_status"]
        == "DESCRIPTIVE_OVERLAP_NO_JOINT_LIKELIHOOD"
    )
    axes[1].plot(
        atlas.loc[estimable, "log10_gbar_m_s2"],
        atlas.loc[estimable, "sparc_galaxy_equal_weight_eta_median"],
        color="#1b7837",
        marker="s",
        ms=4,
        lw=1,
        label="SPARC galaxy-equal median",
    )
    axes[1].axvspan(
        -15.2,
        -14.0,
        color="#fddbc7",
        alpha=0.5,
        label="lensing tail: systematics dominant",
    )
    axes[1].axhline(0.0, color="black", ls="--", lw=1)
    axes[1].set_xlim(limits)
    axes[1].set_xlabel("log10 g_bar [m/s^2]")
    axes[1].set_ylabel("eta = log10(g_obs/g_bar)")
    axes[1].legend(loc="upper right", fontsize=8)
    target.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(target, dpi=180)
    plt.close(figure)


def _report(summary: dict) -> str:
    counts = summary["status_counts"]
    return f"""# DarkPipe 0.11 - segundo shadow observacional por lente debil

La decision terminal es **{summary['decision']}**. Se derivaron
{summary['lensing_bins']} bins poblacionales de lente gravitatoria debil. Bajo
la envolvente de sensibilidad declarada, hay
{counts.get('POSITIVE_CONDITIONAL_SENSITIVITY_ENVELOPE_95', 0)} bins positivos,
{counts.get('SIGN_AMBIGUOUS_CONDITIONAL_SENSITIVITY_ENVELOPE_95', 0)} ambiguos y
{counts.get('NEGATIVE_CONDITIONAL_SENSITIVITY_ENVELOPE_95', 0)} negativos.

El avance real es metodologico y observacional: la discrepancia efectiva que
v0.10 obtuvo de cinematica SPARC reaparece ahora en un canal independiente de
lente debil y se extiende a aceleraciones menores. No es una replicacion
objeto-a-objeto: KiDS es una poblacion apilada distinta. Los
{summary['descriptive_overlap_bins']} bins con soporte SPARC forman solo un
atlas descriptivo; no existe una verosimilitud conjunta ni covarianza cruzada.

La cola por debajo de 10^-14 m/s^2 se conserva como sistematica dominante. La
derivacion no identifica particulas, un perfil tridimensional, Lambda-CDM,
MOND, el mecanismo gravitatorio ni una ontologia de hiperestados plasmicos. El
siguiente salto que puede aumentar autoridad es obtener ESD/covarianza
reutilizable o un segundo canal con correspondencia individual, no volver a
contar estos mismos bins como una nueva confirmacion.
"""


def run(
    output: Path,
    lensing_table: Path,
    sparc_profiles_path: Path,
    config: MultiShadowConfig,
) -> dict:
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True)
    lensing_table = Path(lensing_table)
    sparc_profiles_path = Path(sparc_profiles_path)
    source_receipts = {
        "mistele2024_table1": {
            **_file_receipt(
                lensing_table,
                role="CC-BY-4.0 curated transcription of published Table 1",
                license_id="CC-BY-4.0",
            ),
            "source_url": MISTELE_SOURCE_URL,
            "doi": MISTELE_ARTICLE_DOI,
            "raw_survey_data": False,
        },
        "sparc_v010_checked_profiles": _file_receipt(
            sparc_profiles_path,
            role="immutable checked v0.10 derived profile surface",
            license_id=(
                "GPL-3.0-or-later plus upstream CC-BY-4.0 attribution"
            ),
        ),
    }
    if (
        source_receipts["mistele2024_table1"]["sha256"]
        != EXPECTED_LENSING_TABLE_SHA256
    ):
        raise ValueError("lensing table SHA-256 mismatch")
    if (
        source_receipts["sparc_v010_checked_profiles"]["sha256"]
        != EXPECTED_SPARC_V010_SHA256
    ):
        raise ValueError("checked SPARC v0.10 SHA-256 mismatch")
    source = load_lensing_rar_table(lensing_table)
    sparc = load_checked_sparc_profiles(sparc_profiles_path)
    lensing = derive_lensing_inobservables(source, config)
    atlas = build_cross_shadow_atlas(lensing, sparc, config)
    summary = summarize_multishadow(lensing, atlas, config, source_receipts)
    lensing.to_csv(output / "lensing_derived_inobservables.csv", index=False)
    atlas.to_csv(output / "cross_shadow_atlas.csv", index=False)
    write_json(output / "multishadow_summary.json", summary)
    (output / "SUBSTANTIVE_CLOSURE_ES.md").write_text(
        _report(summary), encoding="utf-8", newline="\n"
    )
    _plot(lensing, sparc, atlas, output / "multishadow_atlas.png")
    write_json(
        output / "manifest.json",
        {
            "schema": "darkpipe.v011.output_manifest.v1",
            "files": sorted(path.name for path in output.iterdir()),
            "raw_survey_data_retained": False,
            "individual_object_fusion": False,
        },
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--lensing-table",
        type=Path,
        default=Path("data/mistele2024_weak_lensing_rar_table1.csv"),
    )
    parser.add_argument(
        "--sparc-profiles",
        type=Path,
        default=Path(
            "evidence/v010_shadow_inobservable/derived_inobservable_profiles.csv"
        ),
    )
    args = parser.parse_args()
    summary = run(
        args.output,
        args.lensing_table,
        args.sparc_profiles,
        MultiShadowConfig(),
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
