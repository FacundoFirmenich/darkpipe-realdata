#!/usr/bin/env python3
"""Gate 010 identity harmonization and longitudinal support audit.

Preserves every raw value, adds explicit canonical identities, and replaces the v1
longitudinal key with two typed keys:
- structural key: invariant to vintage date and policy-layer label (CUADRO)
- policy-cell key: invariant to vintage date but retains CUADRO

No value is imputed; no missing cell is converted to zero.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

OPERATOR_CANONICAL = {
    "Gasnor S.A.": "Naturgy NOA S.A.",
    "Naturgy NOA S.A.": "Naturgy NOA S.A.",
}
TARIFF_TYPE_CANONICAL = {
    "Plena": "Plenas",
    "Plenas": "Plenas",
    "Diferencial": "Diferencial_sin_porcentaje_publicado",
}

STRUCTURAL_FIELDS = [
    "EMPRESA_CANONICAL", "TIPODESUMINISTRO", "SUBZONACODIGO", "SUBZONA",
    "TIPOTARIFA_CANONICAL", "SERVICIO", "CATEGORIA", "CARGOTIPO",
    "CONSUMOM3INICIO_KEY", "CONSUMOM3FIN_KEY",
]
POLICY_FIELDS = STRUCTURAL_FIELDS + ["CUADRO"]


def stable_hash(obj: Any) -> str:
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonicalize(row: dict[str, str]) -> dict[str, str]:
    out = dict(row)
    raw_op = row.get("EMPRESA", "")
    raw_tariff = row.get("TIPOTARIFA", "")
    out["EMPRESA_RAW"] = raw_op
    out["EMPRESA_CANONICAL"] = OPERATOR_CANONICAL.get(raw_op, raw_op)
    out["TIPOTARIFA_RAW"] = raw_tariff
    out["TIPOTARIFA_CANONICAL"] = TARIFF_TYPE_CANONICAL.get(raw_tariff, raw_tariff)
    out["CONSUMOM3INICIO_KEY"] = row.get("CONSUMOM3INICIO_NUMERIC") or row.get("CONSUMOM3INICIO_RAW", "")
    out["CONSUMOM3FIN_KEY"] = row.get("CONSUMOM3FIN_NUMERIC") or row.get("CONSUMOM3FIN_RAW", "")
    out["stable_key_sha256_v1"] = row.get("stable_key_sha256", "")
    out["structural_key_sha256"] = stable_hash({f: out.get(f, "") for f in STRUCTURAL_FIELDS})
    out["policy_cell_key_sha256"] = stable_hash({f: out.get(f, "") for f in POLICY_FIELDS})
    out["longitudinal_key_version"] = "v2_date_excluded_operator_canonicalized"
    return out


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as fh:
        if fields:
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            w.writeheader(); w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()
    root = args.root
    output = root / "output"
    source = output / "historical_tariff_dose_long.csv"
    temp = output / "historical_tariff_dose_long.v2.tmp.csv"

    raw_ops = Counter(); canon_ops = Counter(); raw_tariffs = Counter(); canon_tariffs = Counter()
    by_period_structural: dict[str, set[str]] = defaultdict(set)
    by_period_policy: dict[str, set[str]] = defaultdict(set)
    rows_by_period = Counter(); duplicate_policy = Counter(); duplicate_structural = Counter()
    periods_in_order: list[str] = []
    seen_periods = set()
    output_fields: list[str] | None = None

    with source.open(encoding="utf-8", newline="") as src, temp.open("w", encoding="utf-8", newline="") as dst:
        reader = csv.DictReader(src)
        output_fields = [f for f in (reader.fieldnames or []) if f != "stable_key_sha256"] + [
            "EMPRESA_RAW", "EMPRESA_CANONICAL", "TIPOTARIFA_RAW", "TIPOTARIFA_CANONICAL",
            "CONSUMOM3INICIO_KEY", "CONSUMOM3FIN_KEY", "stable_key_sha256_v1",
            "structural_key_sha256", "policy_cell_key_sha256", "longitudinal_key_version",
        ]
        writer = csv.DictWriter(dst, fieldnames=output_fields, extrasaction="ignore")
        writer.writeheader()
        for row in reader:
            out = canonicalize(row)
            writer.writerow(out)
            pid = out["period_id"]
            if pid not in seen_periods:
                seen_periods.add(pid); periods_in_order.append(pid)
            raw_ops[out["EMPRESA_RAW"]] += 1; canon_ops[out["EMPRESA_CANONICAL"]] += 1
            raw_tariffs[out["TIPOTARIFA_RAW"]] += 1; canon_tariffs[out["TIPOTARIFA_CANONICAL"]] += 1
            rows_by_period[pid] += 1
            if out["structural_key_sha256"] in by_period_structural[pid]: duplicate_structural[pid] += 1
            if out["policy_cell_key_sha256"] in by_period_policy[pid]: duplicate_policy[pid] += 1
            by_period_structural[pid].add(out["structural_key_sha256"])
            by_period_policy[pid].add(out["policy_cell_key_sha256"])
    os.replace(temp, source)

    crosswalk = []
    for raw, count in sorted(raw_ops.items()):
        canonical = OPERATOR_CANONICAL.get(raw, raw)
        crosswalk.append({"EMPRESA_RAW": raw, "EMPRESA_CANONICAL": canonical, "row_count": count,
                          "identity_action": "ALIAS_MERGE" if raw != canonical else "UNCHANGED",
                          "evidence_basis": "documented corporate name continuity; raw value preserved"})
    write_csv(output / "operator_identity_crosswalk.csv", crosswalk)

    support = []
    for a, b in zip(periods_in_order, periods_in_order[1:]):
        sa, sb = by_period_structural[a], by_period_structural[b]
        pa, pb = by_period_policy[a], by_period_policy[b]
        si, su = sa & sb, sa | sb
        pi, pu = pa & pb, pa | pb
        support.append({
            "from_period_id": a, "to_period_id": b,
            "from_rows": rows_by_period[a], "to_rows": rows_by_period[b],
            "from_structural_keys": len(sa), "to_structural_keys": len(sb),
            "structural_intersection": len(si), "structural_union": len(su),
            "structural_jaccard": f"{len(si)/len(su):.12f}" if su else "",
            "from_policy_keys": len(pa), "to_policy_keys": len(pb),
            "policy_intersection": len(pi), "policy_union": len(pu),
            "policy_jaccard": f"{len(pi)/len(pu):.12f}" if pu else "",
            "support_status": "STRUCTURAL_OVERLAP_OBSERVED" if si else "NO_STRUCTURAL_OVERLAP",
            "effect_estimation_authorized": False,
        })
    write_csv(output / "consecutive_period_support_v2.csv", support)

    identity_audit = {
        "raw_operator_count": len(raw_ops), "canonical_operator_count": len(canon_ops),
        "raw_operators": dict(sorted(raw_ops.items())), "canonical_operators": dict(sorted(canon_ops.items())),
        "raw_tariff_type_count": len(raw_tariffs), "canonical_tariff_type_count": len(canon_tariffs),
        "raw_tariff_types": dict(sorted(raw_tariffs.items())),
        "canonical_tariff_types": dict(sorted(canon_tariffs.items())),
        "periods": len(periods_in_order), "rows": sum(rows_by_period.values()),
        "periods_with_structural_overlap": sum(1 for r in support if r["support_status"] == "STRUCTURAL_OVERLAP_OBSERVED"),
        "transitions_total": len(support),
        "duplicate_policy_keys_by_period": dict(duplicate_policy),
        "duplicate_structural_keys_by_period": dict(duplicate_structural),
        "key_semantics": {
            "v1": "deprecated: included vintage-dependent fields and raw operator label",
            "structural_v2": STRUCTURAL_FIELDS,
            "policy_cell_v2": POLICY_FIELDS,
        },
        "effect_estimation_authorized": False,
    }
    (output / "identity_harmonization_audit.json").write_text(json.dumps(identity_audit, indent=2, ensure_ascii=False), encoding="utf-8")

    status_path = output / "gate010A_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status.update({
        "raw_operator_labels": len(raw_ops), "canonical_operator_entities": len(canon_ops),
        "identity_harmonization": "PASS_RAW_AND_CANONICAL_PRESERVED",
        "longitudinal_key_v1": "DEPRECATED_INCLUDED_VINTAGE_DATE",
        "longitudinal_key_v2": "PASS_TYPED_STRUCTURAL_AND_POLICY_KEYS",
        "transitions_with_structural_overlap": identity_audit["periods_with_structural_overlap"],
        "transitions_total": identity_audit["transitions_total"],
    })
    status_path.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")

    # Rebuild manifest after every mutation.
    manifest = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != "MANIFEST.sha256":
            manifest.append(f"{sha256_file(p)}  {p.relative_to(root).as_posix()}")
    (root / "MANIFEST.sha256").write_text("\n".join(manifest) + "\n", encoding="utf-8")

    print(json.dumps({
        "rows": identity_audit["rows"], "raw_operator_count": len(raw_ops),
        "canonical_operator_count": len(canon_ops),
        "transitions_with_structural_overlap": identity_audit["periods_with_structural_overlap"],
        "transitions_total": identity_audit["transitions_total"],
    }, indent=2, ensure_ascii=False))
    if len(canon_ops) != 10:
        raise SystemExit(f"Expected 10 canonical operator entities, found {len(canon_ops)}")
    if identity_audit["periods_with_structural_overlap"] == 0:
        raise SystemExit("No structural overlap after corrected key construction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
