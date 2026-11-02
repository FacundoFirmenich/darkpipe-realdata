#!/usr/bin/env python3
"""Bounded concurrent official-source acquisition; SHADOW only."""
import concurrent.futures,datetime as dt,hashlib,json,re
from pathlib import Path
import requests
from bs4 import BeautifulSoup

ROOT=Path("research/tarifa_abierta/audit/watch_20261102_november_fast")
RAW=ROOT/"raw"
RAW.mkdir(parents=True,exist_ok=True)
UTC=lambda:dt.datetime.now(dt.timezone.utc).isoformat()
URL_SUM="https://www.argentina.gob.ar/normativa/buscar-boletin?fecha_publicacion=30-10-2026&s=1"
URL_ANN="https://www.argentina.gob.ar/noticias/el-gobierno-nacional-prorrogo-las-bonificaciones-de-electricidad-y-gas-ante-el-contexto"

def task(spec):
    tag,n,url,kind=spec
    record={"id":tag,"number":n,"requested_url":url,"checked_at_utc":UTC(),"kind":kind,"success":False}
    try:
        r=requests.get(url,timeout=(8,22),headers={"User-Agent":"TarifaAbierta-SHADOW-ByteAudit-20261102/1.0","Cache-Control":"no-cache"},allow_redirects=True)
        record.update({"http_status":r.status_code,"final_url":r.url,"mime":r.headers.get("Content-Type"),"http_date":r.headers.get("Date"),"last_modified":r.headers.get("Last-Modified"),"etag":r.headers.get("ETag")})
        r.raise_for_status()
        data=r.content
        record.update({"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()})
        record["magic_ok"]=data.startswith(b"%PDF") if kind=="pdf" else (b"<html" in data[:8192].lower() or b"<!doctype html" in data[:8192].lower())
        if not record["magic_ok"]: raise ValueError(f"Unrecognized {kind} magic")
        filename=(f"res{n}-1.pdf" if kind=="pdf" else (f"norma-{n}.html" if n else "sumario.html"))
        if tag=="government_announcement": filename="government_announcement.html"
        (RAW/filename).write_bytes(data)
        record["raw_file"]=str((RAW/filename).relative_to(ROOT))
        record["success"]=True
        if kind=="html" and n:
            text=BeautifulSoup(data,"html.parser").get_text(" ",strip=True)
            record["norm_number_confirmed"]=bool(re.search(rf"Resoluci[oó]n\s+{n}/2026",text,re.I))
            record["regulator_confirmed"]=bool(re.search(r"ENTE NACIONAL REGULADOR DEL GAS Y LA ELECTRICIDAD",text,re.I))
            record["tariff_scope_confirmed"]=bool(re.search(r"CUADROS? TARIFARIOS?",text,re.I))
            record["sancion"]=next(iter(re.findall(r"Sanci[oó]n:\s*(\d{2}-\d{2}-\d{4})",text,re.I)),None)
            record["publicacion"]=next(iter(re.findall(r"Publicada en el Bolet[ií]n Oficial:\s*(\d{2}-\d{2}-\d{4})",text,re.I)),None)
    except Exception as e:
        record["error"]=f"{type(e).__name__}: {str(e)[:250]}"
    return record

specs=[("boletin_20261030",None,URL_SUM,"html"),("government_announcement",None,URL_ANN,"html")]
for n in range(841,860):
    siteid=430980+n
    specs.append((f"norma_{n}",n,f"https://www.argentina.gob.ar/normativa/nacional/norma-{siteid}","html"))
    specs.append((f"annex_{n}",n,f"https://www.argentina.gob.ar/sites/default/files/infoleg/{siteid}/res{n}-1.pdf","pdf"))

rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
    for row in concurrent.futures.as_completed([pool.submit(task,s) for s in specs]):
        r=row.result(); rows.append(r)
        print(json.dumps({"id":r["id"],"status":r.get("http_status"),"bytes":r.get("bytes"),"sha256":r.get("sha256"),"success":r["success"],"error":r.get("error")},ensure_ascii=False),flush=True)
rows.sort(key=lambda x:x["id"])
officials=[r["number"] for r in rows if r["id"].startswith("norma_") and r["success"] and r.get("norm_number_confirmed") and r.get("regulator_confirmed") and r.get("tariff_scope_confirmed")]
pdfs=[r["number"] for r in rows if r["id"].startswith("annex_") and r["success"]]
sumario=next((r for r in rows if r["id"]=="boletin_20261030"),{})
sumario_text=BeautifulSoup((RAW/"sumario.html").read_bytes(),"html.parser").get_text(" ",strip=True) if sumario.get("success") else ""
sumario_numbers=[n for n in range(841,860) if re.search(rf"Resoluci[oó]n\s+{n}/2026\s+ENTE NACIONAL REGULADOR DEL GAS Y LA ELECTRICIDAD",sumario_text,re.I)]
index={
 "run_type":"SHADOW_OFFICIAL_NEW_REGULATIONS_GET_AUDIT",
 "verified_at_utc":UTC(),
 "baseline":"2026-10-31 annex 816-822 and 48 spot checks already notified; no November 841-859 notified",
 "material_new_regulations":bool(officials or sumario_numbers),
 "official_individual_norms":sorted(officials),
 "official_sumario_norms":sorted(sumario_numbers),
 "new_pdf_annexes_acquired":sorted(pdfs),
 "records":rows,
 "legal_dates_separated_from_http_last_modified":True,
 "tarifa_abierta_rebuild":False,
 "full_annex_reconciliation":False,
 "merge":False,
 "publication":False,
 "causal_claims":False
}
(ROOT/"audit_fast.json").write_text(json.dumps(index,ensure_ascii=False,indent=2)+"\n")
(ROOT/"SUMMARY.txt").write_text(f"MATERIAL {index['material_new_regulations']}\nOFFICIAL_NORMS {officials}\nSUMARIO {sumario_numbers}\nPDFS {pdfs}\n")
print("FINAL_NOV_AUDIT",json.dumps({k:index[k] for k in ("material_new_regulations","official_individual_norms","official_sumario_norms","new_pdf_annexes_acquired")}),flush=True)
if not index["material_new_regulations"]: raise SystemExit(2)
