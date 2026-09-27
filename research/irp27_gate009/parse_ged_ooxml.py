#!/usr/bin/env python3
"""Extract ENARGAS GED weights directly from XLSX pivot-cache OOXML.

No effect is estimated. The output is a versioned descriptive panel of customer
counts and delivered gas by month, distributor, subzone, service and client type.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DEF_PATH = "xl/pivotCache/pivotCacheDefinition2.xml"
REC_PATH = "xl/pivotCache/pivotCacheRecords2.xml"
DISTRIBUTOR_MAP = {
    "Ban": "NATURGY_BAN",
    "Centro": "DIST_GAS_CENTRO",
    "Cuyana": "DIST_GAS_CUYANA",
    "Litoral": "LITORAL_GAS",
    "Metrogas": "METROGAS",
    "Noroeste": "NATURGY_NOA",
    "Pampeana": "CAMUZZI_PAMPEANA",
    "Sur": "CAMUZZI_SUR",
    "GasNea": "GASNEA",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_definition(zf: zipfile.ZipFile):
    root = ET.fromstring(zf.read(DEF_PATH))
    fields = []
    shared = []
    for cf in root.find(f"{{{NS}}}cacheFields"):
        fields.append(cf.attrib.get("name"))
        si = cf.find(f"{{{NS}}}sharedItems")
        vals = []
        if si is not None:
            for item in list(si):
                vals.append(item.attrib.get("v"))
        shared.append(vals)
    return fields, shared, int(root.attrib.get("recordCount", "0"))


def decode_record(elem, shared):
    out = []
    for idx, child in enumerate(list(elem)):
        kind = local(child.tag)
        raw = child.attrib.get("v")
        if kind == "x":
            out.append(shared[idx][int(raw)])
        elif kind in {"n", "d", "s", "e"}:
            out.append(raw)
        elif kind == "b":
            out.append(raw == "1")
        elif kind == "m":
            out.append(None)
        else:
            out.append(raw)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    args = ap.parse_args()
    root = args.root
    xlsx = root / "raw" / "GED.xlsx"
    out = root / "weights"
    out.mkdir(parents=True, exist_ok=True)
    if not xlsx.exists() or not zipfile.is_zipfile(xlsx):
        raise SystemExit("GED.xlsx is absent or not a valid XLSX container")

    long_path = out / "ged_weights_long.csv"
    recent_path = out / "ged_weights_2024_2026.csv"
    latest_path = out / "ged_weights_latest_period.csv"
    coverage_path = out / "ged_weights_coverage.csv"

    wide = {}
    distributions = defaultdict(set)
    periods = set()
    record_count = 0
    malformed = 0

    with zipfile.ZipFile(xlsx) as zf:
        fields, shared, expected = parse_definition(zf)
        expected_fields = ["Periodo", "Distribuidor", "Subzona", "TipoDeServicio", "TipoDeCliente", "Variable", "Cantidad"]
        if fields != expected_fields:
            raise SystemExit(f"Unexpected cache schema: {fields!r}")
        with long_path.open("w", newline="", encoding="utf-8") as fh_all, recent_path.open("w", newline="", encoding="utf-8") as fh_recent:
            header = ["period", "distributor_raw", "operator_id", "subzone", "service_type", "client_type", "variable", "value_raw", "source_sha256", "causal_use"]
            wa = csv.DictWriter(fh_all, fieldnames=header); wa.writeheader()
            wr = csv.DictWriter(fh_recent, fieldnames=header); wr.writeheader()
            with zf.open(REC_PATH) as stream:
                for event, elem in ET.iterparse(stream, events=("end",)):
                    if local(elem.tag) != "r":
                        continue
                    vals = decode_record(elem, shared)
                    if len(vals) != 7:
                        malformed += 1
                        elem.clear(); continue
                    period, distributor, subzone, service, client, variable, value = vals
                    period = str(period)[:10]
                    row = {
                        "period": period,
                        "distributor_raw": distributor,
                        "operator_id": DISTRIBUTOR_MAP.get(distributor, "UNMAPPED"),
                        "subzone": subzone,
                        "service_type": service,
                        "client_type": client,
                        "variable": variable,
                        "value_raw": value,
                        "source_sha256": sha256(xlsx),
                        "causal_use": "DESCRIPTIVE_WEIGHT_SOURCE_ONLY",
                    }
                    wa.writerow(row)
                    if period >= "2024-01-01":
                        wr.writerow(row)
                    key = (period, distributor, DISTRIBUTOR_MAP.get(distributor, "UNMAPPED"), subzone, service, client)
                    if key not in wide:
                        wide[key] = {"NroClientes": None, "Volumen": None}
                    if variable in wide[key] and wide[key][variable] is not None:
                        raise SystemExit(f"Duplicate variable for key: {key!r} {variable!r}")
                    wide[key][variable] = value
                    periods.add(period)
                    distributions["distributor"].add(distributor)
                    distributions["subzone"].add(subzone)
                    distributions["service_type"].add(service)
                    distributions["client_type"].add(client)
                    record_count += 1
                    elem.clear()

    wide_header = ["period", "distributor_raw", "operator_id", "subzone", "service_type", "client_type", "n_customers_raw", "delivered_volume_raw", "weight_scope", "source_sha256"]
    latest = max(periods)
    with (out / "ged_weights_wide.csv").open("w", newline="", encoding="utf-8") as fw, latest_path.open("w", newline="", encoding="utf-8") as fl:
        ww = csv.DictWriter(fw, fieldnames=wide_header); ww.writeheader()
        wl = csv.DictWriter(fl, fieldnames=wide_header); wl.writeheader()
        for key in sorted(wide):
            period, distributor, operator_id, subzone, service, client = key
            row = {
                "period": period, "distributor_raw": distributor, "operator_id": operator_id,
                "subzone": subzone, "service_type": service, "client_type": client,
                "n_customers_raw": wide[key]["NroClientes"],
                "delivered_volume_raw": wide[key]["Volumen"],
                "weight_scope": "MONTH_DISTRIBUTOR_SUBZONE_SERVICE_CLIENT_TYPE",
                "source_sha256": sha256(xlsx),
            }
            ww.writerow(row)
            if period == latest:
                wl.writerow(row)

    coverage_rows = []
    for dimension, values in distributions.items():
        for value in sorted(values):
            coverage_rows.append({"dimension": dimension, "value": value})
    with coverage_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["dimension", "value"]); w.writeheader(); w.writerows(coverage_rows)

    summary = {
        "gate": "IRP27-GATE-OUTCOME-ACQUISITION-AND-PRETREND-FEASIBILITY-009",
        "phase": "GED_OOXML_WEIGHT_EXTRACTION",
        "generated_at_utc": utcnow(),
        "source_file": str(xlsx),
        "source_sha256": sha256(xlsx),
        "pivot_cache_definition": DEF_PATH,
        "pivot_cache_records": REC_PATH,
        "expected_records": expected,
        "parsed_records": record_count,
        "malformed_records": malformed,
        "wide_rows": len(wide),
        "period_min": min(periods),
        "period_max": max(periods),
        "period_count": len(periods),
        "distributors": sorted(distributions["distributor"]),
        "subzones": sorted(distributions["subzone"]),
        "service_types": sorted(distributions["service_type"]),
        "client_types": sorted(distributions["client_type"]),
        "redengas_separately_observed": False,
        "category_band_weights_observed": False,
        "effect_estimates_produced": 0,
        "causal_authority": "BLOCKED",
    }
    (out / "ged_weights_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if record_count == expected and malformed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
