#!/usr/bin/env python3
"""Official ENReGE material-diff watch. Strictly SHADOW, no recalculation."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

STAMP = dt.datetime.now(dt.timezone.utc).isoformat()
OUT = Path("research/tarifa_abierta/audit/watch_20261101")
RAW = OUT / "raw"
RAW.mkdir(parents=True, exist_ok=True)
BASE_XLSX = {
    "bytes": 653597,
    "sha256": "fefe75fd5a1e9fa747e4871165b4a1e046743f050343d73a4b7eefaee91540b6",
}
PDF_BASE = {
    816: (438058,"0000cde9f7696b34ab347c6fb9f0dd4fdedd87e1ef516a5a2ea45a3906648c90","431702"),
    817: (433879,"82daa462a69969f74261957a8a18064afc273704867c31bcbce5444048804d97","431703"),
    818: (411883,"8f3f4067a98c33d2e8dd2d9a2978db892f703285d42c5fd401eb97a196122ffb","431704"),
    819: (441883,"a4e50cb0b6ffc149d27f218db8b84b1372a86c70b684405387af3fe51a3d2acd","431705"),
    820: (453109,"a256195c813fa3b9a0d26bd341712287d6058f3a8ee545608021103fc4e98277","431706"),
    821: (513423,"7984543b193aa740865b0fa494d704437a745951fb61ccd0dfec4b3573c4a67f","431707"),
    822: (529227,"85c8b86982022ef7ea1b3ecb8bd99ed78dd478457b48b98b81c451afef52c6f0","431708"),
}
URL_BASE = "https://www.enargas.gob.ar/secciones/precios-y-tarifas/"
SOURCES = [
    {"id":"xlsx", "url":URL_BASE+"descargas/tarifas-gn-20261001.xlsx", "file":"tarifas-gn-20261001.xlsx", "kind":"xlsx"},
    {"id":"current", "url":URL_BASE+"cuadros-tarifarios.php", "file":"cuadros-tarifarios.html", "kind":"html"},
    {"id":"history", "url":URL_BASE+"cuadros-tarifarios-serie-historica.php", "file":"serie-historica.html", "kind":"html"},
    {"id":"resolutions", "url":URL_BASE+"resoluciones-tarifas-vigentes.php", "file":"resoluciones-vigentes.html", "kind":"html"},
]
for no, (size, h, fileid) in PDF_BASE.items():
    SOURCES.append({"id":"annex_"+str(no), "url":f"https://www.argentina.gob.ar/sites/default/files/infoleg/{fileid}/res{no}-1.pdf", "file":f"res{no}-1.pdf", "kind":"pdf"})

session = requests.Session()
session.headers.update({"User-Agent":"TarifaAbierta-Official-Source-Audit/1.0 (research shadow)"})
records = []
data_map = {}
for source in SOURCES:
    record = dict(source)
    record["requested_url"] = source["url"]
    record["checked_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    record["download_completed"] = False
    for attempt in range(1,4):
        try:
            with session.get(source["url"], timeout=(15,75), allow_redirects=True) as response:
                record.update({
                    "http_status": response.status_code,
                    "final_url": response.url,
                    "mime": response.headers.get("Content-Type"),
                    "http_date": response.headers.get("Date"),
                    "http_last_modified": response.headers.get("Last-Modified"),
                    "etag": response.headers.get("ETag"),
                })
                response.raise_for_status()
                body=response.content
            record["bytes"]=len(body)
            record["sha256"]=hashlib.sha256(body).hexdigest()
            record["bytes_validated"]=(body[:4]==b"PK\\x03\\x04" if source["kind"]=="xlsx" else body.startswith(b"%PDF") if source["kind"]=="pdf" else True)
            # XLSX header is checked with explicit byte sequence below.
            if source["kind"]=="xlsx":
                record["bytes_validated"]=body.startswith(bytes([0x50,0x4b,0x03,0x04]))
            if not record["bytes_validated"]:
                raise ValueError("Unexpected downloaded file magic")
            (RAW/source["file"]).write_bytes(body)
            data_map[source["id"]]=body
            record["download_completed"]=True
            record["attempts"]=attempt
            break
        except Exception as exc:
            record["error"]=f"{type(exc).__name__}: {str(exc)[:260]}"
            record["attempts"]=attempt
            if attempt<3:
                time.sleep(attempt)
    records.append(record)
    print(json.dumps({"id":record["id"],"http":record.get("http_status"),"bytes":record.get("bytes"),"sha256":record.get("sha256"),"error":record.get("error")},ensure_ascii=False),flush=True)

byid={record["id"]: record for record in records}
events=[]
if "xlsx" in data_map:
    r=byid["xlsx"]
    r["baseline_bytes"]=BASE_XLSX["bytes"]
    r["baseline_sha256"]=BASE_XLSX["sha256"]
    r["unchanged"]=(r["sha256"]==BASE_XLSX["sha256"] and r["bytes"]==BASE_XLSX["bytes"])
    if not r["unchanged"]:
        events.append({"kind":"OFFICIAL_XLSX_BYTES_CHANGED","source":"xlsx","old":BASE_XLSX,"new":{"sha256":r["sha256"],"bytes":r["bytes"]}})
for no,(size,h,fileid) in PDF_BASE.items():
    id="annex_"+str(no)
    if id in data_map:
        r=byid[id]
        r["baseline_bytes"]=size
        r["baseline_sha256"]=h
        r["unchanged"]=(r["sha256"]==h and r["bytes"]==size)
        if not r["unchanged"]:
            events.append({"kind":"OFFICIAL_ANNEX_BYTES_CHANGED","source":id,"old":{"sha256":h,"bytes":size},"new":{"sha256":r["sha256"],"bytes":r["bytes"]}})

semantics={}
for id in ("current","history","resolutions"):
    if id not in data_map:
        continue
    soup=BeautifulSoup(data_map[id],"html.parser")
    txt=soup.get_text(" ",strip=True)
    if id=="current":
        displayed=re.findall(r"Gas Natural\\s*[-–]\\s*Vigentes desde el\\s*(\\d{2}/\\d{2}/\\d{4})",txt,re.I)
        # Regex in source has literal backslash sequences for raw Python expression; normalized below.
        displayed=re.findall("Gas Natural\\s*[-–]\\s*Vigentes desde el\\s*(\\d{2}/\\d{2}/\\d{4})",txt,re.I)
        semantics[id]={"gas_natural_displayed_vigencia":displayed}
        if displayed and any(s!="01/10/2026" for s in displayed):
            events.append({"kind":"NEW_GAS_NATURAL_CURRENT_PERIOD","displayed_vigencia":displayed,"source":id})
    elif id=="history":
        historical_october=bool(re.search("Gas Natural\\s*[-–]\\s*Per[ií]odo\\s*01/10/2026",txt,re.I))
        semantics[id]={"october_2026_in_gas_natural_history":historical_october,"first_200_chars":txt[:200]}
        if historical_october:
            events.append({"kind":"OCTOBER_ADDED_TO_HISTORICAL_SERIES","source":id})
    else:
        found=sorted({int(n) for n in re.findall("RESFC\\s*[-–]?\\s*2026\\s*[-–]?\\s*0*(\\d{3,4})",txt,re.I)})
        baseline=set(range(710,729))|set(range(816,823))
        new=sorted(set(found)-baseline)
        semantics[id]={"resolution_numbers_2026":found,"new_numbers_not_in_baseline":new}
        if new:
            events.append({"kind":"NEW_OFFICIAL_GAS_TARIFF_RESOLUTION_IN_INDEX","source":id,"new_numbers":new})
    print("INDEX",id,semantics[id],flush=True)

complete=all(x["download_completed"] for x in records)
result={
    "run_type":"OFFICIAL_MATERIAL_DELTA_CHECK_ONLY",
    "checked_at_utc":STAMP,
    "baseline_xlsx_date":"2026-10-23",
    "baseline_resolutions_announced":"2026-10-30",
    "baseline_annex_acquired":"2026-10-31",
    "legal_dates":{"resolutions_816_822_sanctioned":"2026-10-27","published":"2026-10-28","october_workbook_displayed_vigencia":"2026-10-01"},
    "sources":records,
    "index_semantics":semantics,
    "material_changes":events,
    "material_change_confirmed":bool(events),
    "verification_complete":complete,
    "rebuild_performed":False,
    "rebuild_prior_baseline":"Tarifa Abierta v1.6 SHADOW, 585 cells, 585 September-October comparisons",
    "prior_annex_spot_checks":"48/48 R1 Plenas/SinSEF on 24 subzones verified 2026-10-31, NOT an integral reconciliation",
    "merge_performed":False,
    "publication_performed":False,
    "causal_inferences":False,
    "state":"MATERIAL_CHANGE_CONFIRMED" if events else "NO_CHANGE_VERIFIED" if complete else "INCOMPLETE_VERIFICATION_NO_CHANGE_DEMONSTRATED"
}
(OUT/"audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
(OUT/"SUMMARY.txt").write_text(f"STATUS {result['state']}\nCOMPLETE {complete}\nEVENTS {len(events)}\n"+ "\n".join(json.dumps(event) for event in events)+"\n",encoding="utf-8")
print("FINAL_RESULT",json.dumps({"state":result["state"],"complete":complete,"events":events},ensure_ascii=False),flush=True)
sys.exit(0 if complete else 2)
