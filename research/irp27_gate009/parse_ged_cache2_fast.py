#!/usr/bin/env python3
"""Linear-time extraction of the official ENARGAS GED pivot cache.

Reads the OOXML cache directly, preserving monthly customer counts and delivered
volumes by distributor, subzone, service and client type. Produces descriptive
weights only; no causal effect or political comparison is authorized.
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
EXPECTED_FIELDS = [
    "Periodo", "Distribuidor", "Subzona", "TipoDeServicio",
    "TipoDeCliente", "Variable", "Cantidad",
]
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


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_definition(zf: zipfile.ZipFile) -> tuple[list[str], list[list[str | None]], int]:
    root = ET.fromstring(zf.read(DEF_PATH))
    cache_fields = root.find(f"{{{NS}}}cacheFields")
    if cache_fields is None:
        raise ValueError("pivot cache has no cacheFields")
    fields: list[str] = []
    shared: list[list[str | None]] = []
    for cache_field in list(cache_fields):
        fields.append(cache_field.attrib.get("name", ""))
        items: list[str | None] = []
        shared_items = cache_field.find(f"{{{NS}}}sharedItems")
        if shared_items is not None:
            for item in list(shared_items):
                items.append(item.attrib.get("v"))
        shared.append(items)
    return fields, shared, int(root.attrib.get("recordCount", "0"))


def decode_record(record: ET.Element, shared: list[list[str | None]]) -> list[object]:
    values: list[object] = []
    children = list(record)
    if len(children) != len(shared):
        raise ValueError(f"record has {len(children)} fields; expected {len(shared)}")
    for index, child in enumerate(children):
        kind = local(child.tag)
        raw = child.attrib.get("v")
        if kind == "x":
            if raw is None:
                raise ValueError("shared-item index is absent")
            values.append(shared[index][int(raw)])
        elif kind in {"n", "d", "s", "e"}:
            values.append(raw)
        elif kind == "b":
            values.append(raw == "1")
        elif kind == "m":
            values.append(None)
        else:
            values.append(raw)
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()

    root: Path = args.root
    source = root / "raw" / "GED.xlsx"
    output = root / "weights"
    output.mkdir(parents=True, exist_ok=True)
    if not source.exists() or not zipfile.is_zipfile(source):
        raise SystemExit("GED.xlsx is absent or is not a valid XLSX container")

    source_sha = file_sha256(source)
    long_path = output / "ged_weights_long.csv"
    recent_path = output / "ged_weights_2024_2026.csv"
    wide_path = output / "ged_weights_wide.csv"
    latest_path = output / "ged_weights_latest_period.csv"
    coverage_path = output / "ged_weights_coverage.csv"

    wide: dict[tuple[str, str, str, str, str, str], dict[str, str | None]] = {}
    dimensions: dict[str, set[str]] = defaultdict(set)
    periods: set[str] = set()
    parsed_records = 0
    malformed_records = 0

    long_fields = [
        "period", "distributor_raw", "operator_id", "subzone", "service_type",
        "client_type", "variable", "value_raw", "source_sha256", "causal_use",
    ]

    with zipfile.ZipFile(source) as zf:
        fields, shared, expected_records = parse_definition(zf)
        if fields != EXPECTED_FIELDS:
            raise SystemExit(f"unexpected cache schema: {fields!r}")

        with long_path.open("w", newline="", encoding="utf-8") as all_fh, recent_path.open(
            "w", newline="", encoding="utf-8"
        ) as recent_fh:
            all_writer = csv.DictWriter(all_fh, fieldnames=long_fields)
            recent_writer = csv.DictWriter(recent_fh, fieldnames=long_fields)
            all_writer.writeheader()
            recent_writer.writeheader()

            with zf.open(REC_PATH) as records_stream:
                for _event, element in ET.iterparse(records_stream, events=("end",)):
                    if local(element.tag) != "r":
                        continue
                    try:
                        values = decode_record(element, shared)
                        period, distributor, subzone, service, client, variable, amount = values
                        period_text = str(period)[:10]
                        distributor_text = str(distributor)
                        operator_id = DISTRIBUTOR_MAP.get(distributor_text, "UNMAPPED")
                        row = {
                            "period": period_text,
                            "distributor_raw": distributor_text,
                            "operator_id": operator_id,
                            "subzone": subzone,
                            "service_type": service,
                            "client_type": client,
                            "variable": variable,
                            "value_raw": amount,
                            "source_sha256": source_sha,
                            "causal_use": "DESCRIPTIVE_WEIGHT_SOURCE_ONLY",
                        }
                        all_writer.writerow(row)
                        if period_text >= "2024-01-01":
                            recent_writer.writerow(row)

                        key = (
                            period_text, distributor_text, operator_id, str(subzone),
                            str(service), str(client),
                        )
                        slot = wide.setdefault(key, {"NroClientes": None, "Volumen": None})
                        variable_text = str(variable)
                        if variable_text not in slot:
                            raise ValueError(f"unexpected variable {variable_text!r}")
                        if slot[variable_text] is not None:
                            raise ValueError(f"duplicate variable {variable_text!r} for {key!r}")
                        slot[variable_text] = None if amount is None else str(amount)

                        periods.add(period_text)
                        dimensions["distributor"].add(distributor_text)
                        dimensions["subzone"].add(str(subzone))
                        dimensions["service_type"].add(str(service))
                        dimensions["client_type"].add(str(client))
                        dimensions["variable"].add(variable_text)
                        parsed_records += 1
                    except Exception:
                        malformed_records += 1
                        raise
                    finally:
                        element.clear()

    latest_period = max(periods)
    wide_fields = [
        "period", "distributor_raw", "operator_id", "subzone", "service_type",
        "client_type", "n_customers_raw", "delivered_volume_raw", "weight_scope",
        "source_sha256",
    ]
    with wide_path.open("w", newline="", encoding="utf-8") as wide_fh, latest_path.open(
        "w", newline="", encoding="utf-8"
    ) as latest_fh:
        wide_writer = csv.DictWriter(wide_fh, fieldnames=wide_fields)
        latest_writer = csv.DictWriter(latest_fh, fieldnames=wide_fields)
        wide_writer.writeheader()
        latest_writer.writeheader()
        for key in sorted(wide):
            period, distributor, operator_id, subzone, service, client = key
            row = {
                "period": period,
                "distributor_raw": distributor,
                "operator_id": operator_id,
                "subzone": subzone,
                "service_type": service,
                "client_type": client,
                "n_customers_raw": wide[key]["NroClientes"],
                "delivered_volume_raw": wide[key]["Volumen"],
                "weight_scope": "MONTH_DISTRIBUTOR_SUBZONE_SERVICE_CLIENT_TYPE",
                "source_sha256": source_sha,
            }
            wide_writer.writerow(row)
            if period == latest_period:
                latest_writer.writerow(row)

    with coverage_path.open("w", newline="", encoding="utf-8") as coverage_fh:
        writer = csv.DictWriter(coverage_fh, fieldnames=["dimension", "value"])
        writer.writeheader()
        for dimension, values in sorted(dimensions.items()):
            for value in sorted(values):
                writer.writerow({"dimension": dimension, "value": value})

    summary = {
        "gate": "IRP27-GATE-OUTCOME-ACQUISITION-AND-PRETREND-FEASIBILITY-009",
        "phase": "GED_OOXML_WEIGHT_EXTRACTION",
        "generated_at_utc": utcnow(),
        "source_file": source.as_posix(),
        "source_sha256": source_sha,
        "pivot_cache_definition": DEF_PATH,
        "pivot_cache_records": REC_PATH,
        "schema": fields,
        "expected_records": expected_records,
        "parsed_records": parsed_records,
        "malformed_records": malformed_records,
        "wide_rows": len(wide),
        "period_min": min(periods),
        "period_max": latest_period,
        "period_count": len(periods),
        "distributors": sorted(dimensions["distributor"]),
        "subzones": sorted(dimensions["subzone"]),
        "service_types": sorted(dimensions["service_type"]),
        "client_types": sorted(dimensions["client_type"]),
        "variables": sorted(dimensions["variable"]),
        "redengas_separately_observed": False,
        "category_band_weights_observed": False,
        "effect_estimates_produced": 0,
        "causal_authority": "BLOCKED",
    }
    (output / "ged_weights_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if parsed_records == expected_records and malformed_records == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
