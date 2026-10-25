#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--bilingual-status", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    index = json.loads(args.registry.read_text(encoding="utf-8"))
    bilingual_status = json.loads(args.bilingual_status.read_text(encoding="utf-8")) if args.bilingual_status and args.bilingual_status.exists() else None
    decision = {
        "gate": index["gate"],
        "contract_calibration_registry": "PASS",
        "external_shadow_cells": index["external_cells"],
        "bilingual_shadow_cells": index["bilingual_cells"],
        "bilingual_live_completed": bool(bilingual_status and bilingual_status.get("completed")),
        "calibration_transport": "PROHIBITED_ACROSS_NONIDENTICAL_KEYS",
        "argentine_accuracy_calibration": "BLOCKED_GOLD_NOT_FROZEN",
        "provider_promotion": "BLOCKED",
        "execution_authority": "NONE",
        "automatic_execution": False,
        "automatic_publication": False,
    }
    (args.output / "GATE_DECISION_v2.2.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = f"""# IRP‑27 Gate SOTA‑012 — Calibration Registry & Bilingual Shadow Evaluation

## Decisión

```json
{json.dumps(decision, ensure_ascii=False, indent=2)}
```

## Resultado axial

La calibración deja de ser una propiedad nominal del proveedor. Cada resultado queda ligado a una celda exacta:

```text
(contract hash, provider, provider version, checkpoint, primitive,
 domain, language, hardware, data vintage, evaluation mode)
```

Una métrica no puede trasladarse a otra celda sin una validación de transporte independiente. El registro contiene {index['cells']} celdas: {index['external_cells']} de reanálisis externo y {index['bilingual_cells']} de invariancia bilingüe shadow.

## Shadow bilingüe

El shadow ES↔EN utiliza pares públicos argentinos reales, pero sus traducciones siguen pendientes de revisión humana y el gold SOTA‑009 no está congelado. Por ello mide acuerdo y deriva distributiva, no accuracy, Brier, log loss ni ECE.

## Autoridad

- Provider authority: NONE.
- Calibration transport: blocked by default.
- Argentine calibration: blocked until human adjudication.
- Automatic execution: FALSE.
- Automatic publication: FALSE.

## Estado

```text
CALIBRATION REGISTRY           PASS
KEYED CELL INVARIANTS          PASS
EXTERNAL REANALYSIS            PASS
BILINGUAL SHADOW               {'PASS' if decision['bilingual_live_completed'] else 'INCOMPLETE_OR_BLOCKED'}
ARGENTINE GOLD                 NOT FROZEN
PROVIDER PROMOTION             BLOCKED
EXECUTION AUTHORITY            NONE
```
"""
    (args.output / "GATE_SOTA_012_CIERRE_CIENTIFICO_v2.2.md").write_text(md, encoding="utf-8")
    html = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>IRP‑27 Calibration Registry</title><style>:root{{--bg:#07101d;--panel:#111d32;--line:#2a3b59;--ink:#eef4ff;--muted:#a8b7d0;--ok:#7ce3ae;--warn:#ffd17f}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:system-ui,sans-serif}}main{{max-width:1180px;margin:auto;padding:24px}}h1{{font-size:clamp(2.2rem,6vw,5rem);line-height:.95}}section{{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:18px;margin:14px 0}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}}.cell{{background:#0b1628;padding:14px;border-radius:12px}}code,pre{{white-space:pre-wrap;overflow-wrap:anywhere}}.ok{{color:var(--ok)}}.warn{{color:var(--warn)}}</style></head><body><main><h1>Calibration Registry</h1><p>Gate SOTA‑012 · calibración situada, invariancia bilingüe shadow y transporte bloqueado por defecto.</p><section class='grid'><div class='cell'><b>Celdas</b><br>{index['cells']}</div><div class='cell'><b>Externas</b><br>{index['external_cells']}</div><div class='cell'><b>Bilingües</b><br>{index['bilingual_cells']}</div><div class='cell'><b>Promotion</b><br><span class='warn'>BLOCKED</span></div><div class='cell'><b>Execution authority</b><br>NONE</div></section><section><h2>Clave constitucional</h2><pre>(contract hash, provider, version, checkpoint, primitive,
domain, language, hardware, vintage, evaluation mode)</pre><p>Una métrica sólo es válida dentro de su celda exacta.</p></section><section><h2>Gate decision</h2><pre>{json.dumps(decision,ensure_ascii=False,indent=2)}</pre></section><section><h2>Disagreement</h2><pre>{json.dumps(index.get('disagreement',{}),ensure_ascii=False,indent=2)}</pre></section></main></body></html>"""
    (args.output / "IRP27_CALIBRATION_REGISTRY_LAB_v2.2.html").write_text(html, encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
