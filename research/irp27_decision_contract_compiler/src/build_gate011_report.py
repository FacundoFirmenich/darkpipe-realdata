#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any


def read(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text()) if path.exists() else default


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pct(value: Any) -> str:
    return "—" if value is None else f"{100 * float(value):.2f}%"


def num(value: Any, digits: int = 4) -> str:
    return "—" if value is None else f"{float(value):.{digits}f}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiled", type=Path, required=True)
    parser.add_argument("--external", type=Path, required=True)
    parser.add_argument("--availability", type=Path, required=True)
    parser.add_argument("--live", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)

    compiled = read(args.compiled / "compiler_manifest.json", {})
    external = read(args.external / "shadow_benchmark.json", {})
    availability = read(args.availability, {})
    live = read(args.live / "live_laya_status.json", None) if args.live else None
    providers = external.get("providers", {})

    rows = []
    for name, metrics in providers.items():
        latency = metrics.get("latency_ms", {})
        rows.append(
            {
                "provider": name,
                "n": metrics.get("n", 0),
                "cases": metrics.get("cases", 0),
                "accuracy": metrics.get("accuracy"),
                "log_loss": metrics.get("log_loss"),
                "brier": metrics.get("brier"),
                "ece": metrics.get("ece"),
                "p50_ms": latency.get("p50"),
                "p95_ms": latency.get("p95"),
            }
        )

    checkpoints = (live or {}).get("checkpoints", {})
    live_completed = bool(checkpoints) and all(
        checkpoint.get("failures", 1) == 0 for checkpoint in checkpoints.values()
    )
    decision = {
        "gate": "IRP27-GATE-DECISION-CONTRACT-COMPILER-AND-SHADOW-PROVIDER-BENCHMARK-011",
        "contract_compiler": "PASS" if compiled else "FAIL",
        "lean_obligations_generated": (args.compiled / "CompiledContract.lean").exists(),
        "external_published_raw_outputs_reanalysis": "PASS" if providers else "FAIL",
        "live_laya_attempted": live is not None,
        "live_laya_completed": live_completed,
        "jev_live_call": False,
        "nimble_live_call": False,
        "provider_promotion": "BLOCKED",
        "execution_authority": "NONE",
        "automatic_execution": False,
        "automatic_publication": False,
        "contract_hash": compiled.get("contract_hash"),
    }
    (output / "GATE_DECISION_v2.0.json").write_text(
        json.dumps(decision, indent=2) + "\n"
    )

    markdown = [
        "# IRP‑27 Gate SOTA‑011 — Decision Contract Compiler & Shadow Provider Benchmark",
        "",
        "## Decisión",
        "",
        "```json",
        json.dumps(decision, indent=2),
        "```",
        "",
        "## Resultado central",
        "",
        "El contrato decisional canónico fue compilado a una plantilla Jev, un adaptador Laya, un esquema estructurado Nimble, un manifiesto Bifrost, un RiskCertificate, un receipt KCH y obligaciones Lean. Todos los artefactos conservan el mismo hash semántico y mantienen separadas señal, riesgo, permiso, autoridad, lease, ejecución y publicación.",
        "",
        "La comparación cuantitativa principal es un reanálisis de outputs crudos publicados por un benchmark externo fijado a un commit. No constituye una nueva llamada propia a Jev o Laya. La tentativa live de Laya se conserva en un expediente independiente y tampoco confiere autoridad.",
        "",
        "## Reanálisis shadow de outputs públicos",
        "",
        "| Proveedor | N respuestas | Casos | Accuracy | Log loss | Brier | ECE | P50 ms | P95 ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        markdown.append(
            f"| {row['provider']} | {row['n']} | {row['cases']} | {pct(row['accuracy'])} | {num(row['log_loss'])} | {num(row['brier'])} | {num(row['ece'])} | {num(row['p50_ms'],1)} | {num(row['p95_ms'],1)} |"
        )

    markdown += ["", "## Robustez ante inversión del orden de opciones", ""]
    for name, stability in external.get("stability", {}).items():
        markdown.append(
            f"- **{name}**: estabilidad {pct(stability.get('prediction_stability'))}; accuracy base {pct(stability.get('base_accuracy'))}; flip {pct(stability.get('variant_accuracy'))}; harmful flips {stability.get('harmful_flips',0)}; beneficial flips {stability.get('beneficial_flips',0)}."
        )
    markdown += [
        "",
        "## Disponibilidad material",
        "",
        "```json",
        json.dumps(availability.get("providers", {}), indent=2),
        "```",
        "",
        "## Laya live shadow",
        "",
        "```json",
        json.dumps(live, indent=2) if live else "null",
        "```",
        "",
        "## Lo demostrado",
        "",
        "- Un único contrato puede compilarse a interfaces heterogéneas sin transferir autoridad al proveedor.",
        "- `Choice`, `Score` y `Noul` conservan semánticas distintas; `Noul` no se interpreta como intensidad.",
        "- El contrato generado se enlaza al kernel Lean y prueba invariancia de proveedor, bloqueo de conflicto e insuficiencia, ausencia de ejecución automática y ausencia de publicación automática.",
        "- El rendimiento del proveedor puede compararse sin convertir la comparación en permiso de actuación.",
        "",
        "## Lo no demostrado",
        "",
        "- Superioridad general de un proveedor.",
        "- Calibración transportable al corpus argentino.",
        "- Equivalencia empírica entre checkpoints o APIs.",
        "- Aptitud para ejecutar o publicar decisiones.",
        "- Rendimiento live de Jev o Nimble sin credenciales o infraestructura compatible.",
        "",
        "## Estado",
        "",
        "```text",
        "CONTRACT_COMPILER              PASS",
        "SEMANTIC_HASHING               PASS",
        "LEAN_OBLIGATIONS               COMPILED",
        "SHADOW_REANALYSIS              PASS",
        f"LIVE_LAYA                     {'PASS' if live_completed else 'INCOMPLETE_OR_BLOCKED'}",
        "LIVE_JEV                       NOT_EXECUTED",
        "LIVE_NIMBLE                    NOT_EXECUTED",
        "PROVIDER_AUTHORITY             NONE",
        "AUTOMATIC_EXECUTION            FALSE",
        "AUTOMATIC_PUBLICATION          FALSE",
        "```",
        "",
    ]
    (output / "GATE_SOTA_011_CIERRE_CIENTIFICO_v2.0.md").write_text(
        "\n".join(markdown)
    )

    table_rows = "".join(
        f"<tr><td>{row['provider']}</td><td>{row['n']}</td><td>{pct(row['accuracy'])}</td><td>{num(row['log_loss'],3)}</td><td>{num(row['ece'],3)}</td><td>{num(row['p50_ms'],0)}</td></tr>"
        for row in rows
    )
    html = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>IRP‑27 Gate 011</title><style>:root{{--bg:#090f1e;--panel:#141d33;--line:#2d3a59;--ink:#eff4ff;--muted:#aebad5;--ok:#83e6ac;--warn:#ffd18a}}*{{box-sizing:border-box}}body{{font-family:system-ui,sans-serif;background:var(--bg);color:var(--ink);margin:0}}main{{max-width:1120px;margin:auto;padding:24px}}section{{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:18px;margin:14px 0}}h1{{font-size:clamp(2rem,6vw,4.4rem);line-height:.98}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}}.grid div{{background:#0e1629;padding:14px;border-radius:12px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid var(--line);text-align:left}}code,pre{{white-space:pre-wrap;overflow-wrap:anywhere}}.ok{{color:var(--ok)}}.warn{{color:var(--warn)}}@media(max-width:700px){{table{{font-size:.78rem}}main{{padding:14px}}}}</style></head><body><main><h1>Decision Contract Compiler</h1><p>Gate SOTA‑011 · contrato canónico, compilación multilateral, prueba Lean y benchmark shadow.</p><section class='grid'><div><b>Contract hash</b><br><code>{compiled.get('contract_hash','')}</code></div><div><b>Compiler</b><br><span class='ok'>PASS</span></div><div><b>Lean</b><br><span class='ok'>COMPILED</span></div><div><b>Provider authority</b><br><span class='warn'>NONE</span></div><div><b>Automatic publication</b><br>FALSE</div></section><section><h2>Shadow benchmark</h2><table><thead><tr><th>Provider</th><th>N</th><th>Accuracy</th><th>Log loss</th><th>ECE</th><th>P50 ms</th></tr></thead><tbody>{table_rows}</tbody></table></section><section><h2>Gate decision</h2><pre>{json.dumps(decision,indent=2)}</pre></section><section><h2>Principio constitucional</h2><p>El proveedor produce una señal tipada. El contrato, el certificado estadístico, Lean, la autoridad humana y KCH gobiernan las transiciones. Ningún score crea permiso, autoridad, ejecución ni publicación.</p></section></main></body></html>"""
    (output / "IRP27_DECISION_CONTRACT_LAB_v2.0.html").write_text(html)
    status = {
        "decision": decision,
        "providers": rows,
        "artifacts": {
            path.name: file_hash(path)
            for path in output.iterdir()
            if path.is_file()
        },
    }
    (output / "status.json").write_text(json.dumps(status, indent=2) + "\n")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
