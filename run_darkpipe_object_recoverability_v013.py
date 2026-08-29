#!/usr/bin/env python3
"""Run the DarkPipe 0.13 bounded object-level recoverability gate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from darkpipe.object_recoverability import probe_default_inputs


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _closure(summary: dict[str, object]) -> str:
    ready = bool(summary["all_public_inputs_verified"])
    position = "mejor posicionado" if ready else "peor posicionado"
    observed = (
        "Los cuatro insumos públicos respondieron por rangos HTTP y sus tamaños, "
        "filas y campos mínimos coincidieron con el contrato congelado."
        if ready
        else "Al menos un insumo público no respondió o se apartó del contrato congelado."
    )
    return f"""# Cierre sustantivo — DarkPipe 0.13, puerta de recuperabilidad

El proyecto queda **{position}** que en v0.12. {observed}

Esto significa que la abstención anterior ya no se interpreta como ausencia de
datos de base. La reconstrucción objeto a objeto es viable en principio, pero
requiere ejecución remota y recalcular pares lente–fuente; no puede obtenerse
reordenando los 60 puntos ya apilados. La superficie cruda prevista ocupa
{summary['expected_raw_input_gib']:.3f} GiB, por lo que la política queda fijada
como `{summary['local_execution_policy']}`.

El resultado sigue siendo una puerta precomputacional, no una detección ni una
adjudicación entre Lambda-CDM, MOND o la conjetura morfotopológica plásmica. La
reproducción byte a byte tampoco está establecida: el bundle público de
resultados no contiene el catálogo aleatorio exacto ni un código GGL operativo
enlazado. Sí es posible una reproducción científica independiente con nuevas
coordenadas aleatorias prerregistradas.

El próximo paso crítico es
`{summary['next_gate']}` en almacenamiento remoto, seguido por la puerta de firma
diferencial. Mientras la conjetura no declare signo, escala, amplitud o relación
de orden frente a trazadores plásmicos y controles bariónico-ambientales, su
comparación queda `NOT_ESTIMABLE_MODEL_NOT_YET_DIFFERENTIALLY_PREDICTIVE`.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evidence/object_recoverability_v013"),
    )
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    probes, summary = probe_default_inputs(timeout=args.timeout)
    generated_at = datetime.now(timezone.utc).isoformat()

    probe_path = args.output_dir / "dataset_probe.json"
    summary_path = args.output_dir / "summary.json"
    closure_path = args.output_dir / "SUBSTANTIVE_CLOSURE_ES.md"
    manifest_path = args.output_dir / "manifest.json"

    probe_path.write_text(
        json.dumps({"generated_at_utc": generated_at, "datasets": probes}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps({"generated_at_utc": generated_at, **summary}, indent=2) + "\n",
        encoding="utf-8",
    )
    closure_path.write_text(_closure(summary), encoding="utf-8")

    artifacts = []
    for path in (probe_path, summary_path, closure_path):
        artifacts.append(
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    manifest_path.write_text(
        json.dumps(
            {
                "campaign": "DP-OBJREC-0.13-20260829",
                "generated_at_utc": generated_at,
                "authority": summary["scientific_authority"],
                "artifacts": artifacts,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))
    return 0 if summary["all_public_inputs_verified"] else 2


if __name__ == "__main__":
    sys.exit(main())
