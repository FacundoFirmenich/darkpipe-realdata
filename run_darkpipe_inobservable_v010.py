"""Run the preregistered observable-shadow to inobservable SPARC derivation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

import matplotlib.pyplot as plt
import numpy as np

from darkpipe.inobservable import (
    DerivationConfig,
    derive_shadow_inobservables,
    fetch_sparc_sources,
    parse_sparc_mass_models,
    parse_sparc_sample,
    select_observable_points,
    summarize_derivation,
)
from darkpipe.provenance import write_json


def _plot(profiles, target: Path) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    gbar = profiles["g_baryonic_p50_m_s2"].to_numpy()
    gobs = profiles["g_observed_p50_m_s2"].to_numpy()
    support = profiles["shadow_sign_probability_positive"].to_numpy()
    positive = (gbar > 0.0) & (gobs > 0.0)
    if not np.any(positive):
        raise ValueError("no positive accelerations available for logarithmic plot")
    scatter = axes[0].scatter(
        gbar[positive],
        gobs[positive],
        c=support[positive],
        cmap="coolwarm",
        s=8,
        alpha=0.7,
        vmin=0,
        vmax=1,
    )
    lower = min(gbar[positive].min(), gobs[positive].min())
    upper = max(gbar[positive].max(), gobs[positive].max())
    axes[0].plot([lower, upper], [lower, upper], color="black", lw=1, ls="--")
    axes[0].set_xscale("log")
    axes[0].set_yscale("log")
    axes[0].set_xlabel("baryonic observable projection g_bar [m/s^2]")
    axes[0].set_ylabel("kinematic observable g_obs [m/s^2]")
    figure.colorbar(scatter, ax=axes[0], label="P(g_inobservable > 0)")

    radius = profiles["radius_nominal_kpc"].to_numpy()
    shadow = profiles["g_inobservable_p50_m_s2"].to_numpy()
    axes[1].scatter(radius, shadow, s=8, alpha=0.6)
    axes[1].axhline(0.0, color="black", lw=1, ls="--")
    axes[1].set_xscale("log")
    axes[1].set_yscale("symlog", linthresh=1.0e-13)
    axes[1].set_xlabel("nominal radius [kpc]")
    axes[1].set_ylabel("derived signed g_inobservable [m/s^2]")
    target.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(target, dpi=180)
    plt.close(figure)


def _report(summary: dict) -> str:
    counts = summary["status_counts"]
    return f"""# DarkPipe 0.10 - observable shadows e inobservables derivados

Decision: **{summary['decision']}**.

Se conservaron {summary['selection']['points']} puntos reales de
{summary['selection']['galaxies']} galaxias SPARC despues de los cortes
prerregistrados. La shadow no se identifica con una entidad: contiene la
discrepancia cinematica firmada, soporte de signo, coste evidencial y un coste
de transformacion a cierre barionico con nuisances fijos.

Perfiles positivos al 95%: {counts.get('POSITIVE_SIGNED_PROFILE_SUPPORTED_95', 0)}.
Perfiles negativos al 95%: {counts.get('NEGATIVE_SIGNED_PROFILE_SUPPORTED_95', 0)}.
Perfiles de signo ambiguo: {counts.get('SIGN_AMBIGUOUS_95', 0)}.

El inobservable derivado es un perfil efectivo de aceleracion y masa encerrada
esferico-equivalente, condicionado por la proyeccion newtoniana y por los
priors declarados. No es una deteccion de particulas, una densidad tridimensional,
una adjudicacion MOND/Lambda-CDM ni una validacion de hiperestados plasmicos.
"""


def run(output: Path, scratch: Path, config: DerivationConfig) -> dict:
    output = Path(output)
    scratch = Path(scratch)
    output.mkdir(parents=True, exist_ok=False)
    try:
        paths, receipts = fetch_sparc_sources(scratch)
        galaxies = parse_sparc_sample(
            paths["SPARC_Lelli2016c.mrt"].read_text(encoding="ascii")
        )
        mass_models = parse_sparc_mass_models(
            paths["MassModels_Lelli2016c.mrt"].read_text(encoding="ascii")
        )
        selected = select_observable_points(mass_models, galaxies, config)
        profiles = derive_shadow_inobservables(selected, config)
        summary = summarize_derivation(
            profiles,
            selected,
            config,
            receipts,
            points_before_selection=len(mass_models),
        )
        profiles.to_csv(output / "derived_inobservable_profiles.csv", index=False)
        write_json(output / "inobservable_summary.json", summary)
        (output / "SUBSTANTIVE_CLOSURE_ES.md").write_text(
            _report(summary), encoding="utf-8", newline="\n"
        )
        _plot(profiles, output / "observable_shadow_inobservable.png")
        write_json(
            output / "manifest.json",
            {
                "schema": "darkpipe.v010.output_manifest.v1",
                "files": sorted(path.name for path in output.iterdir()),
                "raw_source_retained": False,
            },
        )
        return summary
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--draws", type=int, default=4096)
    parser.add_argument("--seed", type=int, default=20260826010)
    args = parser.parse_args()
    summary = run(
        args.output,
        args.scratch,
        DerivationConfig(draws=args.draws, seed=args.seed),
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
