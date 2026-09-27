#!/usr/bin/env python3
"""IRP-27 Gate 010A: freeze, acquire, hash and harmonize historical ENARGAS GN tariff workbooks.

The script is intentionally fail-closed for source integrity and fail-open for schema drift:
all raw files and exact parse failures are preserved, while no absent field is coerced to zero.
It produces no causal effect estimate and no political comparison.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
import unicodedata
import urllib.request
import zipfile
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET

BASE = "https://www.enargas.gob.ar/secciones/precios-y-tarifas/descargas"
GATE_ID = "IRP27-GATE-HISTORICAL-DOSE-EXPANSION-AND-OFFICIAL-OUTCOME-REQUEST-010"

# Frozen before value inspection. Together these periods cover every day from 2023-01-01 through 2026-03-31.
PERIODS = [
    ("P20221231_20230228", "2022-12-31", "2023-02-28", "tarifas-gn-20221231-20230228.xlsx"),
    ("P20230301_20230428", "2023-03-01", "2023-04-28", "tarifas-gn-20230301.xlsx"),
    ("P20230429_20230430", "2023-04-29", "2023-04-30", "tarifas-gn-20230429-20230430.xlsx"),
    ("P20230501_20240402", "2023-05-01", "2024-04-02", "tarifas-gn-20230501.xlsx"),
    ("P20240403_20240605", "2024-04-03", "2024-06-05", "tarifas-gn-20240403.xlsx"),
    ("P20240606_20240801", "2024-06-06", "2024-08-01", "tarifas-gn-20240606.xlsx"),
    ("P20240802_20240901", "2024-08-02", "2024-09-01", "tarifas-gn-20240802.xlsx"),
    ("P20240902_20240930", "2024-09-02", "2024-09-30", "tarifas-gn-20240902.xlsx"),
    ("P20241001_20241103", "2024-10-01", "2024-11-03", "tarifas-gn-20241001.xlsx"),
    ("P20241104_20241203", "2024-11-04", "2024-12-03", "tarifas-gn-20241104.xlsx"),
    ("P20241204_20241231", "2024-12-04", "2024-12-31", "tarifas-gn-20241204.xlsx"),
    ("P20250101_20250131", "2025-01-01", "2025-01-31", "tarifas-gn-20250101.xlsx"),
    ("P20250201_20250305", "2025-02-01", "2025-03-05", "tarifas-gn-20250201.xlsx"),
    ("P20250306_20250402", "2025-03-06", "2025-04-02", "tarifas-gn-20250306.xlsx"),
    ("P20250403_20250430", "2025-04-03", "2025-04-30", "tarifas-gn-20250403.xlsx"),
    ("P20250501_20250605", "2025-05-01", "2025-06-05", "tarifas-gn-20250501.xlsx"),
    ("P20250606_20250630", "2025-06-06", "2025-06-30", "tarifas-gn-20250606.xlsx"),
    ("P20250701_20250731", "2025-07-01", "2025-07-31", "tarifas-gn-20250701.xlsx"),
    ("P20250801_20250831", "2025-08-01", "2025-08-31", "tarifas-gn-20250801.xlsx"),
    ("P20250901_20250930", "2025-09-01", "2025-09-30", "tarifas-gn-20250901.xlsx"),
    ("P20251001_20251031", "2025-10-01", "2025-10-31", "tarifas-gn-20251001.xlsx"),
    ("P20251101_20251130", "2025-11-01", "2025-11-30", "tarifas-gn-20251101.xlsx"),
    ("P20251201_20251231", "2025-12-01", "2025-12-31", "tarifas-gn-20251201.xlsx"),
    ("P20260101_20260131", "2026-01-01", "2026-01-31", "tarifas-gn-20260101.xlsx"),
    ("P20260201_20260228", "2026-02-01", "2026-02-28", "tarifas-gn-20260201.xlsx"),
    ("P20260301_20260331", "2026-03-01", "2026-03-31", "tarifas-gn-20260301.xlsx"),
]

CANONICAL_HEADERS = [
    "EMPRESA", "TIPODESUMINISTRO", "SUBZONACODIGO", "SUBZONA", "TIPOTARIFA",
    "CUADRO", "SERVICIO", "CATEGORIA", "CARGOTIPO", "CARGO",
    "CONSUMOM3INICIO", "CONSUMOM3FIN", "VIGENCIADESDE",
]

HEADER_ALIASES = {
    "EMPRESA": {"EMPRESA", "DISTRIBUIDORA", "LICENCIATARIA"},
    "TIPODESUMINISTRO": {"TIPODESUMINISTRO", "TIPOSUMINISTRO", "SUMINISTRO"},
    "SUBZONACODIGO": {"SUBZONACODIGO", "CODIGOSUBZONA", "CODSUBZONA"},
    "SUBZONA": {"SUBZONA", "ZONA", "REGIONTARIFARIA"},
    "TIPOTARIFA": {"TIPOTARIFA", "TARIFA", "TIPODETARIFA"},
    "CUADRO": {"CUADRO", "CUADROTARIFARIO", "CODIGOCUADRO"},
    "SERVICIO": {"SERVICIO", "TIPODESERVICIO"},
    "CATEGORIA": {"CATEGORIA", "CATEGORIATARIFARIA"},
    "CARGOTIPO": {"CARGOTIPO", "TIPODECARGO", "CONCEPTO"},
    "CARGO": {"CARGO", "VALOR", "IMPORTE"},
    "CONSUMOM3INICIO": {"CONSUMOM3INICIO", "CONSUMOINICIO", "M3INICIO", "DESDE"},
    "CONSUMOM3FIN": {"CONSUMOM3FIN", "CONSUMOFIN", "M3FIN", "HASTA"},
    "VIGENCIADESDE": {"VIGENCIADESDE", "VIGENCIA", "FECHAVIGENCIA", "DESDEVIGENCIA"},
}

NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
OFFICE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(s: str) -> date:
    return date.fromisoformat(s)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_hash(obj: Any) -> str:
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def fold(value: Any) -> str:
    s = unicodedata.normalize("NFKD", str(value or ""))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^A-Z0-9]+", "", s.upper())


def col_index(ref: str) -> int:
    m = re.match(r"([A-Z]+)", ref)
    if not m:
        raise ValueError(f"Invalid cell reference: {ref}")
    n = 0
    for ch in m.group(1):
        n = n * 26 + ord(ch) - 64
    return n - 1


def parse_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    s = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def decimal_text(value: Decimal | None) -> str:
    return "" if value is None else format(value, "f")


def excel_serial_to_iso(value: Any) -> str:
    d = parse_decimal(value)
    if d is None:
        return ""
    whole = int(d)
    if whole < 1 or whole > 80000:
        return ""
    return (date(1899, 12, 30) + timedelta(days=whole)).isoformat()


def parse_date_any(value: Any) -> str:
    if value in (None, ""):
        return ""
    s = str(value).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return excel_serial_to_iso(s)


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str] | None = None) -> int:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as fh:
        if fields:
            writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    return len(rows)


def fetch(url: str, dest: Path) -> dict[str, Any]:
    last_error = None
    for attempt in range(1, 4):
        req = urllib.request.Request(url, headers={
            "User-Agent": "IRP27-Gate010/1.1 reproducible-public-data-acquisition",
            "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/octet-stream,*/*",
        })
        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                data = response.read()
                dest.write_bytes(data)
                return {
                    "requested_url": url, "final_url": response.geturl(),
                    "http_status": getattr(response, "status", 200),
                    "content_type": response.headers.get("Content-Type"),
                    "content_length_header": response.headers.get("Content-Length"),
                    "etag": response.headers.get("ETag"),
                    "last_modified": response.headers.get("Last-Modified"),
                    "attempt": attempt, "retrieved_at_utc": utcnow(),
                    "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                    "xlsx_zip_valid": zipfile.is_zipfile(dest), "error": None,
                }
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(attempt * 2)
    return {
        "requested_url": url, "final_url": None, "http_status": None,
        "content_type": None, "content_length_header": None, "etag": None,
        "last_modified": None, "attempt": 3, "retrieved_at_utc": utcnow(),
        "bytes": 0, "sha256": None, "xlsx_zip_valid": False, "error": last_error,
    }


def load_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in si.findall(".//a:t", NS)) for si in root.findall("a:si", NS)]


def workbook_sheet_paths(zf: zipfile.ZipFile) -> list[tuple[str, str]]:
    if "xl/workbook.xml" not in zf.namelist():
        return []
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = {}
    rel_path = "xl/_rels/workbook.xml.rels"
    if rel_path in zf.namelist():
        rel_root = ET.fromstring(zf.read(rel_path))
        for rel in rel_root.findall("r:Relationship", REL_NS):
            rels[rel.attrib.get("Id", "")] = rel.attrib.get("Target", "")
    out = []
    sheets = wb.find("a:sheets", NS)
    if sheets is not None:
        for s in sheets.findall("a:sheet", NS):
            name = s.attrib.get("name", "")
            rid = s.attrib.get(f"{{{OFFICE_REL}}}id", "")
            target = rels.get(rid, "")
            if target:
                if target.startswith("/"):
                    target = target.lstrip("/")
                elif not target.startswith("xl/"):
                    target = "xl/" + target
                target = re.sub(r"/\./", "/", target)
                out.append((name, target))
    if not out:
        for n in sorted(x for x in zf.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", x)):
            out.append((Path(n).stem, n))
    return out


def cell_value(cell: ET.Element, shared: list[str]) -> Any:
    t = cell.attrib.get("t")
    if t == "inlineStr":
        return "".join(x.text or "" for x in cell.findall(".//a:t", NS))
    v = cell.find("a:v", NS)
    if v is None:
        return None
    raw = v.text
    if t == "s" and raw is not None:
        idx = int(raw)
        return shared[idx] if 0 <= idx < len(shared) else raw
    if t == "b":
        return raw == "1"
    return raw


def read_sheet_rows(zf: zipfile.ZipFile, sheet_path: str, shared: list[str]) -> list[list[Any]]:
    root = ET.fromstring(zf.read(sheet_path))
    rows: list[list[Any]] = []
    for row in root.findall(".//a:sheetData/a:row", NS):
        by_col: dict[int, Any] = {}
        max_idx = -1
        for cell in row.findall("a:c", NS):
            idx = col_index(cell.attrib.get("r", "A1"))
            by_col[idx] = cell_value(cell, shared)
            max_idx = max(max_idx, idx)
        vals = [None] * (max_idx + 1 if max_idx >= 0 else 0)
        for idx, value in by_col.items():
            vals[idx] = value
        rows.append(vals)
    return rows


def canonical_header(value: Any) -> str | None:
    f = fold(value)
    for canonical, aliases in HEADER_ALIASES.items():
        if f in aliases:
            return canonical
    return None


def detect_header(rows: list[list[Any]]) -> tuple[int | None, dict[int, str], int]:
    best_idx = None
    best_map: dict[int, str] = {}
    best_score = 0
    for i, row in enumerate(rows[:80]):
        mapping: dict[int, str] = {}
        for j, value in enumerate(row):
            c = canonical_header(value)
            if c and c not in mapping.values():
                mapping[j] = c
        score = len(mapping)
        if score > best_score and {"EMPRESA", "CARGO", "CARGOTIPO"}.issubset(set(mapping.values())):
            best_idx, best_map, best_score = i, mapping, score
    return best_idx, best_map, best_score


def parse_workbook(path: Path, period: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    source_hash = sha256_file(path)
    all_rows: list[dict[str, Any]] = []
    sheet_audits: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as zf:
        shared = load_shared_strings(zf)
        for sheet_name, sheet_path in workbook_sheet_paths(zf):
            try:
                rows = read_sheet_rows(zf, sheet_path, shared)
            except Exception as exc:
                sheet_audits.append({"period_id": period["period_id"], "sheet": sheet_name, "sheet_path": sheet_path,
                                     "parse_status": "SHEET_XML_PARSE_FAILED", "error": f"{type(exc).__name__}: {exc}"})
                continue
            header_idx, header_map, score = detect_header(rows)
            if header_idx is None:
                sheet_audits.append({"period_id": period["period_id"], "sheet": sheet_name, "sheet_path": sheet_path,
                                     "parse_status": "NO_CANONICAL_HEADER_DETECTED", "row_count": len(rows),
                                     "header_score": score, "detected_headers": "", "error": ""})
                continue
            header_row = rows[header_idx]
            source_headers = {i: str(v or "") for i, v in enumerate(header_row)}
            extra_cols = {i: h for i, h in source_headers.items() if i not in header_map and h.strip()}
            data_count = 0
            blank_rows = 0
            numeric_failures = 0
            for source_row_idx, row in enumerate(rows[header_idx + 1 :], start=header_idx + 2):
                canonical = {h: None for h in CANONICAL_HEADERS}
                for idx, h in header_map.items():
                    canonical[h] = row[idx] if idx < len(row) else None
                if all(v in (None, "") for v in canonical.values()):
                    blank_rows += 1
                    continue
                charge_num = parse_decimal(canonical.get("CARGO"))
                if canonical.get("CARGO") not in (None, "") and charge_num is None:
                    numeric_failures += 1
                extra = {name: row[idx] for idx, name in extra_cols.items() if idx < len(row) and row[idx] not in (None, "")}
                identity = {k: canonical.get(k) for k in CANONICAL_HEADERS if k != "CARGO"}
                record = {
                    "period_id": period["period_id"], "period_start": period["period_start"],
                    "period_end": period["period_end"], "source_filename": path.name,
                    "source_sha256": source_hash, "source_sheet": sheet_name,
                    "source_row_number": source_row_idx, "schema_score": score,
                    "EMPRESA": canonical.get("EMPRESA") or "", "TIPODESUMINISTRO": canonical.get("TIPODESUMINISTRO") or "",
                    "SUBZONACODIGO": canonical.get("SUBZONACODIGO") or "", "SUBZONA": canonical.get("SUBZONA") or "",
                    "TIPOTARIFA": canonical.get("TIPOTARIFA") or "", "CUADRO": canonical.get("CUADRO") or "",
                    "SERVICIO": canonical.get("SERVICIO") or "", "CATEGORIA": canonical.get("CATEGORIA") or "",
                    "CARGOTIPO": canonical.get("CARGOTIPO") or "", "CARGO_RAW": canonical.get("CARGO") or "",
                    "CARGO_NUMERIC": decimal_text(charge_num),
                    "CONSUMOM3INICIO_RAW": canonical.get("CONSUMOM3INICIO") or "",
                    "CONSUMOM3INICIO_NUMERIC": decimal_text(parse_decimal(canonical.get("CONSUMOM3INICIO"))),
                    "CONSUMOM3FIN_RAW": canonical.get("CONSUMOM3FIN") or "",
                    "CONSUMOM3FIN_NUMERIC": decimal_text(parse_decimal(canonical.get("CONSUMOM3FIN"))),
                    "VIGENCIADESDE_RAW": canonical.get("VIGENCIADESDE") or "",
                    "VIGENCIADESDE_ISO": parse_date_any(canonical.get("VIGENCIADESDE")),
                    "EXTRA_COLUMNS_JSON": json.dumps(extra, ensure_ascii=False, sort_keys=True) if extra else "",
                    "stable_key_sha256": stable_hash(identity), "causal_authority": "BLOCKED",
                }
                record["row_sha256"] = stable_hash(record)
                all_rows.append(record)
                data_count += 1
            sheet_audits.append({
                "period_id": period["period_id"], "sheet": sheet_name, "sheet_path": sheet_path,
                "parse_status": "CANONICAL_ROWS_PARSED", "row_count": len(rows),
                "header_row_1based": header_idx + 1, "header_score": score,
                "detected_headers": " | ".join(f"{i}:{h}" for i, h in sorted(header_map.items())),
                "missing_canonical_headers": " | ".join(h for h in CANONICAL_HEADERS if h not in header_map.values()),
                "extra_headers": " | ".join(extra_cols.values()), "parsed_data_rows": data_count,
                "blank_rows_skipped": blank_rows, "charge_numeric_failures": numeric_failures, "error": "",
            })
    audit = {
        "period_id": period["period_id"], "filename": path.name, "sha256": source_hash,
        "sheets": len(sheet_audits), "parsed_rows": len(all_rows),
        "parsed_sheets": sum(x.get("parse_status") == "CANONICAL_ROWS_PARSED" for x in sheet_audits),
        "max_header_score": max((int(x.get("header_score") or 0) for x in sheet_audits), default=0),
        "schema_status": "PASS_CANONICAL_13" if any(int(x.get("header_score") or 0) == 13 for x in sheet_audits) else (
            "PARTIAL_CANONICAL_SCHEMA" if all_rows else "UNRESOLVED_SCHEMA"),
        "operators": len({r["EMPRESA"] for r in all_rows if r["EMPRESA"]}),
        "subzones": len({(r["SUBZONACODIGO"], r["SUBZONA"]) for r in all_rows if r["SUBZONA"] or r["SUBZONACODIGO"]}),
        "charge_types": len({r["CARGOTIPO"] for r in all_rows if r["CARGOTIPO"]}),
        "duplicate_stable_keys": len(all_rows) - len({r["stable_key_sha256"] for r in all_rows}),
        "charge_numeric_failures": sum(1 for r in all_rows if r["CARGO_RAW"] and not r["CARGO_NUMERIC"]),
    }
    return all_rows, audit, sheet_audits


def iter_months(start: date, end: date):
    cur = date(start.year, start.month, 1)
    while cur <= end:
        yield cur
        cur = date(cur.year + (cur.month == 12), 1 if cur.month == 12 else cur.month + 1, 1)


def validate_frozen_periods() -> dict[str, Any]:
    periods = [(pid, parse_iso(s), parse_iso(e), fn) for pid, s, e, fn in PERIODS]
    issues = []
    for i, (pid, s, e, _) in enumerate(periods):
        if e < s:
            issues.append(f"negative period {pid}")
        if i and s != periods[i - 1][2] + timedelta(days=1):
            issues.append(f"gap/overlap {periods[i-1][0]} -> {pid}: {periods[i-1][2]} / {s}")
    target_start, target_end = date(2023, 1, 1), date(2026, 3, 31)
    return {"period_count": len(periods), "target_start": target_start.isoformat(), "target_end": target_end.isoformat(),
            "first_period_start": periods[0][1].isoformat(), "last_period_end": periods[-1][2].isoformat(),
            "continuity_issues": issues,
            "covers_target": periods[0][1] <= target_start and periods[-1][2] >= target_end and not issues}


def build_month_crosswalk() -> list[dict[str, Any]]:
    out = []
    for month_start in iter_months(date(2023, 1, 1), date(2026, 3, 31)):
        month_end = date(month_start.year, month_start.month, monthrange(month_start.year, month_start.month)[1])
        for pid, s0, e0, filename in PERIODS:
            s, e = parse_iso(s0), parse_iso(e0)
            overlap_start, overlap_end = max(month_start, s), min(month_end, e)
            if overlap_start <= overlap_end:
                days = (overlap_end - overlap_start).days + 1
                out.append({"month": month_start.strftime("%Y-%m"), "month_start": month_start.isoformat(),
                            "month_end": month_end.isoformat(), "days_in_month": month_end.day,
                            "period_id": pid, "period_start": s0, "period_end": e0, "filename": filename,
                            "overlap_start": overlap_start.isoformat(), "overlap_end": overlap_end.isoformat(),
                            "covered_days": days, "month_share_days": f"{days / month_end.day:.12f}",
                            "aggregation_rule": "DAY_WEIGHT_AVAILABLE_BUT_NOT_AUTOMATICALLY_APPLIED"})
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root, raw_dir, out_dir = args.output, args.output / "raw", args.output / "output"
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    continuity = validate_frozen_periods()
    (out_dir / "frozen_period_continuity.json").write_text(json.dumps(continuity, indent=2), encoding="utf-8")
    source_rows, period_rows, all_normalized, workbook_audits, sheet_audits, errors = [], [], [], [], [], []

    for period_id, start, end, filename in PERIODS:
        period = {"period_id": period_id, "period_start": start, "period_end": end, "filename": filename}
        url, path = f"{BASE}/{filename}", raw_dir / filename
        acquisition = fetch(url, path)
        acquisition.update(period)
        source_rows.append(acquisition)
        period_rows.append({**period, "official_url": url, "days": (parse_iso(end) - parse_iso(start)).days + 1,
                            "frozen_before_value_inspection": True})
        if not acquisition.get("xlsx_zip_valid"):
            errors.append({"period_id": period_id, "stage": "DOWNLOAD_OR_XLSX_VALIDATION",
                           "error": acquisition.get("error") or "invalid xlsx"})
            continue
        try:
            rows, audit, sheets = parse_workbook(path, period)
            all_normalized.extend(rows)
            workbook_audits.append(audit)
            sheet_audits.extend(sheets)
        except Exception as exc:
            errors.append({"period_id": period_id, "stage": "WORKBOOK_PARSE", "error": f"{type(exc).__name__}: {exc}"})

    write_csv(out_dir / "raw_source_manifest.csv", source_rows, [
        "period_id", "period_start", "period_end", "filename", "requested_url", "final_url", "http_status",
        "content_type", "content_length_header", "bytes", "sha256", "xlsx_zip_valid", "etag", "last_modified",
        "attempt", "retrieved_at_utc", "error"])
    (out_dir / "raw_source_manifest.json").write_text(json.dumps(source_rows, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(out_dir / "frozen_period_registry.csv", period_rows)
    month_crosswalk = build_month_crosswalk()
    write_csv(out_dir / "month_period_crosswalk.csv", month_crosswalk)
    write_csv(out_dir / "workbook_schema_audit.csv", workbook_audits)
    write_csv(out_dir / "sheet_schema_audit.csv", sheet_audits)
    write_csv(out_dir / "historical_tariff_dose_long.csv", all_normalized)
    write_csv(out_dir / "errors.csv", errors, ["period_id", "stage", "error"])

    by_period = defaultdict(list)
    for row in all_normalized:
        by_period[row["period_id"]].append(row)
    operator_universe = sorted({row["EMPRESA"] for row in all_normalized if row["EMPRESA"]})
    coverage = []
    for pid, start, end, _ in PERIODS:
        rows = by_period.get(pid, [])
        by_op = defaultdict(list)
        for r in rows:
            by_op[r["EMPRESA"]].append(r)
        for op in operator_universe:
            rr = by_op.get(op, [])
            coverage.append({"period_id": pid, "period_start": start, "period_end": end, "operator": op,
                             "present": bool(rr), "row_count": len(rr),
                             "subzones": len({(r["SUBZONACODIGO"], r["SUBZONA"]) for r in rr}),
                             "categories": len({r["CATEGORIA"] for r in rr if r["CATEGORIA"]}),
                             "charge_types": len({r["CARGOTIPO"] for r in rr if r["CARGOTIPO"]}),
                             "interpretation": "SOURCE_COVERAGE_ONLY"})
    write_csv(out_dir / "operator_period_coverage.csv", coverage)

    support, previous_pid, previous_keys = [], None, set()
    for pid, _, _, _ in PERIODS:
        current_keys = {r["stable_key_sha256"] for r in by_period.get(pid, [])}
        if previous_pid is not None:
            inter, union = previous_keys & current_keys, previous_keys | current_keys
            support.append({"from_period_id": previous_pid, "to_period_id": pid,
                            "from_keys": len(previous_keys), "to_keys": len(current_keys),
                            "intersection_keys": len(inter), "union_keys": len(union),
                            "jaccard": f"{len(inter) / len(union):.12f}" if union else "",
                            "continuity_status": "OVERLAP_OBSERVED" if inter else "NO_STABLE_KEY_OVERLAP",
                            "effect_estimation_authorized": False})
        previous_pid, previous_keys = pid, current_keys
    write_csv(out_dir / "consecutive_period_support.csv", support)

    acquired = sum(1 for r in source_rows if int(r.get("bytes") or 0) > 0)
    valid = sum(1 for r in source_rows if r.get("xlsx_zip_valid"))
    parsed = sum(1 for r in workbook_audits if int(r.get("parsed_rows") or 0) > 0)
    unresolved = sum(1 for r in workbook_audits if r.get("schema_status") == "UNRESOLVED_SCHEMA")
    full_schema = sum(1 for r in workbook_audits if r.get("schema_status") == "PASS_CANONICAL_13")
    source_complete = acquired == len(PERIODS) and valid == len(PERIODS)
    schema_ready = parsed == len(PERIODS) and unresolved == 0
    decision = "HISTORICAL_DOSE_PANEL_READY" if source_complete and schema_ready else (
        "HISTORICAL_DOSE_SCHEMA_UNRESOLVED" if source_complete else "HISTORICAL_SOURCE_INCOMPLETE")
    status = {
        "gate_id": GATE_ID, "generated_at_utc": utcnow(), "decision_010A": decision,
        "expected_workbooks": len(PERIODS), "acquired_workbooks": acquired,
        "valid_xlsx_workbooks": valid, "parsed_workbooks": parsed,
        "full_canonical_schema_workbooks": full_schema, "unresolved_schema_workbooks": unresolved,
        "normalized_rows": len(all_normalized), "operator_universe_count": len(operator_universe),
        "covered_calendar_months": len({r["month"] for r in month_crosswalk}), "target_calendar_months": 39,
        "continuous_daily_coverage": continuity["covers_target"], "errors": len(errors),
        "effect_estimates": 0, "causal_authority": "BLOCKED",
        "political_comparison": "BLOCKED", "automatic_publication": "BLOCKED",
    }
    (out_dir / "gate010A_status.json").write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")

    manifest = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != "MANIFEST.sha256":
            manifest.append(f"{sha256_file(p)}  {p.relative_to(root).as_posix()}")
    (root / "MANIFEST.sha256").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2, ensure_ascii=False))
    return 0 if source_complete else 2


if __name__ == "__main__":
    sys.exit(main())
