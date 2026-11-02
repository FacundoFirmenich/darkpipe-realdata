#!/usr/bin/env python3
"""SHADOW: verify 2026-10-30 official gas tariff acts 841-859 and original annex bytes.
No recalculation, no publication, no merge, no conclusions about bill impacts.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

OUT=Path("research/tarifa_abierta/audit/watch_20261102_november_acts")
RAW=OUT/"raw"
RAW.mkdir(parents=True,exist_ok=True)
NOW=lambda:dt.datetime.now(dt.timezone.utc).isoformat()
session=requests.Session()
session.headers.update({"User-Agent":"TarifaAbierta-Official-SHADOW-20261102/1.0","Cache-Control":"no-cache","Pragma":"no-cache"})
records=[]
acts=[]
summary_url="https://www.argentina.gob.ar/normativa/buscar-boletin?fecha_publicacion=30-10-2026&s=1"
announcement_url="https://www.argentina.gob.ar/noticias/el-gobierno-nacional-prorrogo-las-bonificaciones-de-electricidad-y-gas-ante-el-contexto"

def fetch(source_id,url,path,kind,attempts=3):
    record={"id":source_id,"requested_url":url,"checked_at_utc":NOW(),"kind":kind,"download_completed":False}
    for attempt in range(1,attempts+1):
        try:
            with session.get(url,timeout=(20,75),allow_redirects=True) as r:
                record.update({"http_status":r.status_code,"final_url":r.url,"mime":r.headers.get("Content-Type"),"http_date":r.headers.get("Date"),"last_modified":r.headers.get("Last-Modified"),"etag":r.headers.get("ETag"),"attempt":attempt})
                r.raise_for_status()
                payload=r.content
            record["bytes"]=len(payload)
            record["sha256"]=hashlib.sha256(payload).hexdigest()
            record["magic_verified"]=((payload.startswith(b"%PDF")) if kind=="pdf" else (b"<html" in payload[:8192].lower() or b"<!doctype html" in payload[:8192].lower()))
            if not record["magic_verified"]: raise ValueError(f"unexpected {kind} file signature")
            (RAW/path).write_bytes(payload)
            record["raw_file"]=str((RAW/path).relative_to(OUT))
            record["download_completed"]=True
            record.pop("error",None)
            records.append(record)
            print(json.dumps({"id":source_id,"http":record["http_status"],"bytes":record["bytes"],"sha256":record["sha256"],"url":record["final_url"]}),flush=True)
            return payload,record
        except Exception as exc:
            record["error"]=f"{type(exc).__name__}: {str(exc)[:300]}"
            if attempt<attempts:time.sleep(attempt)
    records.append(record)
    print(json.dumps({"id":source_id,"http":record.get("http_status"),"error":record.get("error")}),flush=True)
    return None,record

sum_data,sum_meta=fetch("boletin_20261030_sumario",summary_url,"boletin_20261030_sumario.html","html")
press_data,press_meta=fetch("government_november_notice",announcement_url,"government_november_notice.html","html")
sum_text=BeautifulSoup(sum_data,"html.parser").get_text(" ",strip=True) if sum_data else ""
for number in range(841,860):
    siteid=430980+number
    url=f"https://www.argentina.gob.ar/normativa/nacional/norma-{siteid}"
    html,meta=fetch(f"resolution_{number}_official_summary",url,f"resolution_{number}_official_summary.html","html")
    text=BeautifulSoup(html,"html.parser").get_text(" ",strip=True) if html else ""
    title_ok=bool(re.search(rf"Resoluci[oó]n\s+{number}/2026",text,re.I))
    regulator_ok=bool(re.search(r"ENTE NACIONAL REGULADOR DEL GAS Y LA ELECTRICIDAD",text,re.I))
    tariffs_ok=bool(re.search(r"CUADROS? TARIFARIOS?",text,re.I))
    sanction=re.search(r"Sanci[oó]n:\s*(\d{2}-\d{2}-\d{4})",text,re.I)
    publication=re.search(r"Publicada en el Bolet[ií]n Oficial:\s*(\d{2}-\d{2}-\d{4})",text,re.I)
    annex_if=re.findall(r"IF-2026-\d+-APN-[A-Z0-9]+#ENREGE",text,re.I)
    confirmed=bool(meta["download_completed"] and title_ok and regulator_ok and tariffs_ok)
    meta.update({"norm_number":number,"norma_site_id":siteid,"norm_title_verified":title_ok,"regulator_verified":regulator_ok,"gas_tariff_subject_verified":tariffs_ok,"legal_sanction_date":sanction.group(1) if sanction else None,"legal_publication_date":publication.group(1) if publication else None,"annex_if_references":sorted(set(annex_if)),"norm_confirmed":confirmed})
    act={"number":number,"norma_site_id":siteid,"official_summary_url":meta.get("final_url"),"norm_confirmed":confirmed,"sanction":meta["legal_sanction_date"],"publication":meta["legal_publication_date"],"annex_if_references":meta["annex_if_references"]}
    acts.append(act)
    # Attempt official Infoleg annex URLs independently; never assume they exist.
    pdfurl=f"https://www.argentina.gob.ar/sites/default/files/infoleg/{siteid}/res{number}-1.pdf"
    blob,pmeta=fetch(f"resolution_{number}_annex_candidate",pdfurl,f"res{number}-1.pdf","pdf",attempts=2)
    act.update({"annex_http":pmeta.get("http_status"),"annex_acquired":bool(blob),"annex_url":pmeta.get("final_url"),"annex_sha256":pmeta.get("sha256"),"annex_bytes":pmeta.get("bytes"),"annex_mime":pmeta.get("mime")})
    
# The sumario is the independent primary source when an individual summary
# might be temporarily unavailable.
sumario_confirmed=[]
for number in range(841,860):
    if re.search(rf"Resoluci[oó]n\s+{number}/2026\s+ENTE NACIONAL REGULADOR DEL GAS Y LA ELECTRICIDAD",sum_text,re.I):
        sumario_confirmed.append(number)
confirmed_individual=[a["number"] for a in acts if a["norm_confirmed"]]
acquired_annexes=[a["number"] for a in acts if a["annex_acquired"]]
result={
    "run_type":"NEW_MATERIAL_ACTS_OFFICIAL_GET_AUDIT_ONLY",
    "checked_at_utc":NOW(),
    "baseline":"2026-10-31: resolutions 816-822 + seven annexes already notified; Nov acts 841-859 NOT in previous reported baseline",
    "legal_dates_policy":"Act signing / BORA publication / effective tariff date are distinct from HTTP Last-Modified and download timestamp.",
    "source_scope":"Official Argentina.gob.ar Infoleg summaries and BORA sumario 2026-10-30; PDF candidate URLs tested, not presumed.",
    "sumario_confirmed_norm_numbers":sumario_confirmed,
    "individual_official_summary_confirmed_norm_numbers":confirmed_individual,
    "official_pdf_annexes_newly_acquired_norm_numbers":acquired_annexes,
    "new_material_regulatory_acts_confirmed":bool(sumario_confirmed or confirmed_individual),
    "acts":acts,
    "sources":records,
    "official_november_tariff_announcement_present":bool(press_data and "1 de noviembre" in BeautifulSoup(press_data,"html.parser").get_text(" ",strip=True)),
    "xls_v1_6_shadow_rebuild_performed":False,
    "integral_annex_reconciliation_performed":False,
    "automatic_merge":False,
    "automatic_publication":False,
    "causal_attribution":False
}
(OUT/"audit_november_acts.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
(OUT/"SUMMARY.txt").write_text(f"NEW_MATERIAL_REGULATORY_ACTS {result['new_material_regulatory_acts_confirmed']}\nSUMARIO_CONFIRMED {len(sumario_confirmed)}\nINDIVIDUAL_NORMS_CONFIRMED {len(confirmed_individual)}\nNEW_ANNEXES_DOWNLOADED {len(acquired_annexes)}\n",encoding="utf-8")
print("FINAL_NEW_NOV_ACTS",json.dumps({"material":result["new_material_regulatory_acts_confirmed"],"sumario":sumario_confirmed,"individual":confirmed_individual,"annexes":acquired_annexes},ensure_ascii=False),flush=True)
if not result["new_material_regulatory_acts_confirmed"]: raise SystemExit("No primary source confirmed new regulatory acts")
