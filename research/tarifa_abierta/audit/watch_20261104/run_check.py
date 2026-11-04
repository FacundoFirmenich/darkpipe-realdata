#!/usr/bin/env python3
"""Tarifa Abierta / ENReGE: 2026-11-04 official raw-byte material-diff audit. SHADOW ONLY."""
import concurrent.futures, datetime as dt, hashlib, json, re, time
from pathlib import Path
import requests
from bs4 import BeautifulSoup

UTC=dt.timezone.utc
HERE=Path("research/tarifa_abierta/audit/watch_20261104")
HERE.mkdir(parents=True,exist_ok=True)
BASE="https://www.enargas.gob.ar/secciones/precios-y-tarifas/"
BASE_HASH="fefe75fd5a1e9fa747e4871165b4a1e046743f050343d73a4b7eefaee91540b6"
OLD_ANNEX={
816:(438058,"0000cde9f7696b34ab347c6fb9f0dd4fdedd87e1ef516a5a2ea45a3906648c90","431702"),
817:(433879,"82daa462a69969f74261957a8a18064afc273704867c31bcbce5444048804d97","431703"),
818:(411883,"8f3f4067a98c33d2e8dd2d9a2978db892f703285d42c5fd401eb97a196122ffb","431704"),
819:(441883,"a4e50cb0b6ffc149d27f218db8b84b1372a86c70b684405387af3fe51a3d2acd","431705"),
820:(453109,"a256195c813fa3b9a0d26bd341712287d6058f3a8ee545608021103fc4e98277","431706"),
821:(513423,"7984543b193aa740865b0fa494d704437a745951fb61ccd0dfec4b3573c4a67f","431707"),
822:(529227,"85c8b86982022ef7ea1b3ec4b8bd99ed78dd478457b48b98b81c451afef52c6f0","431708"),
}
prior=json.loads(Path("research/tarifa_abierta/audit/ENREGE_MATERIAL_NEW_NOVEMBER_841_859_20261102.json").read_text())
new_annex={int(x["resolution"]):(int(x["bytes"]),x["sha256"],x["requested_url"]) for x in prior["new_annexes"]}
assert set(new_annex)==set(range(841,860))
SOURCES=[
("xlsx_oct",BASE+"descargas/tarifas-gn-20261001.xlsx","xlsx"),
("index_current",BASE+"cuadros-tarifarios.php","html"),
("index_history",BASE+"cuadros-tarifarios-serie-historica.php","html"),
("index_resolutions",BASE+"resoluciones-tarifas-vigentes.php","html"),
]
for num,(size,sha,id_) in OLD_ANNEX.items():
 SOURCES.append((f"annex_{num}",f"https://www.argentina.gob.ar/sites/default/files/infoleg/{id_}/res{num}-1.pdf","pdf"))
for num,(size,sha,url) in new_annex.items():
 SOURCES.append((f"annex_{num}",url,"pdf"))
for day in ("30-10-2026","02-11-2026","03-11-2026","04-11-2026"):
 SOURCES.append(("bo_summary_"+day,"https://www.argentina.gob.ar/normativa/buscar-boletin?fecha_publicacion="+day+"&s=1","html"))
# This is a request for the source, not a claim that the daily issue exists.
SOURCES.append(("bo_first_section","https://www.boletinoficial.gob.ar/seccion/primera","html"))

def get(item):
 ident,url,kind=item
 r={"id":ident,"requested_url":url,"kind":kind,"verified":False,"checked_at_utc":dt.datetime.now(UTC).isoformat()}
 for n in range(1,3):
  try:
   with requests.get(url,timeout=(12,60),headers={"User-Agent":"TarifaAbiertaResearch/20261104 (official byte audit)"},allow_redirects=True) as resp:
    b=resp.content
    r.update({"http_status":resp.status_code,"final_url":resp.url,
      "mime":resp.headers.get("Content-Type"),
      "http_date":resp.headers.get("Date"),
      "last_modified_http":resp.headers.get("Last-Modified"),
      "size_bytes":len(b),"sha256":hashlib.sha256(b).hexdigest(),
      "download_completed_at_utc":dt.datetime.now(UTC).isoformat(),"attempts":n})
    if not resp.ok: raise ValueError("HTTP "+str(resp.status_code))
    if kind=="pdf" and not b.startswith(b"%PDF"): raise ValueError("PDF signature missing")
    if kind=="xlsx" and not b.startswith(bytes([0x50,0x4b,0x03,0x04])): raise ValueError("XLSX magic missing")
   r["verified"]=True
   if kind=="html":
    soup=BeautifulSoup(b,"html.parser")
    text=soup.get_text(" ",strip=True)
    r["extracted_text"]=text[:65000]
    r["links"]=[{"text":a.get_text(" ",strip=True)[:140],"href":a.get("href","")} for a in soup.find_all("a",href=True)]
   return r,b
  except Exception as exc:
   r["error"]=f"{type(exc).__name__}: {str(exc)[:240]}"
   if n==1:time.sleep(1.0)
 return r,None

records=[];bodies={}
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
 for rec,body in pool.map(get,SOURCES):
  records.append(rec)
  if body is not None: bodies[rec["id"]]=body
  print(json.dumps({k:rec.get(k) for k in ("id","http_status","verified","size_bytes","sha256","error")},ensure_ascii=False),flush=True)
lookup={r["id"]:r for r in records}
events=[];unverified=[r["id"] for r in records if not r["verified"]]
if lookup["xlsx_oct"]["verified"]:
 r=lookup["xlsx_oct"];r["baseline_sha256"]=BASE_HASH;r["baseline_size_bytes"]=653597
 if (r["sha256"],r["size_bytes"])!=(BASE_HASH,653597):
  events.append({"kind":"OFFICIAL_OCTOBER_WORKBOOK_CHANGED","id":"xlsx_oct","new_sha256":r["sha256"],"new_size":r["size_bytes"]})
for num in sorted(set(OLD_ANNEX)|set(new_annex)):
 r=lookup["annex_"+str(num)]
 if not r["verified"]: continue
 old_size,old_sha= (OLD_ANNEX[num][:2] if num in OLD_ANNEX else new_annex[num][:2])
 r["baseline_sha256"]=old_sha;r["baseline_size_bytes"]=old_size
 if (r["sha256"],r["size_bytes"])!=(old_sha,old_size):
  events.append({"kind":"OFFICIAL_PDF_ANNEX_CHANGED","resolution":num,"new_sha256":r["sha256"],"new_size":r["size_bytes"],"old_sha256":old_sha})
# Historical 1–12 October is already notified on 2026-11-03.
if lookup["index_history"]["verified"]:
 r=lookup["index_history"]
 history=[a["text"] for a in r["links"] if re.search(r"Gas Natural\s*[-–]?\s*Per[ií]odo",a["text"],re.I)]
 r["periods_gn"]=history[:100]
 later=[p for p in history if re.search(r"13/10/2026|(?:\d{2}/11/2026)",p)]
 if later:events.append({"kind":"NEW_GAS_HISTORICAL_PERIOD_AFTER_BASELINE_20261103","periods":later})
if lookup["index_current"]["verified"]:
 r=lookup["index_current"]
 gaslinks=[x for x in r["links"] if (".xlsx" in x["href"].lower() and ("tarifas" in x["href"].lower() or "gas" in x["text"].lower()))]
 r["gas_workbook_links"]=gaslinks
 for link in gaslinks:
  url=requests.compat.urljoin(r["final_url"],link["href"])
  if not url.endswith("tarifas-gn-20261001.xlsx"):
   cid="xlsx_discovered_"+str(len([x for x in records if x["id"].startswith("xlsx_discovered")]))
   x,b=get((cid,url,"xlsx"));records.append(x);lookup[cid]=x
   if x["verified"]:
    events.append({"kind":"NEW_OFFICIAL_WORKBOOK_GET_VERIFIED","id":cid,"sha256":x["sha256"],"size_bytes":x["size_bytes"],"url":x["final_url"]})
   else:unverified.append(cid)
if lookup["index_resolutions"]["verified"]:
 r=lookup["index_resolutions"]
 nums=sorted(set(int(n) for n in re.findall(r"RESFC\s*[-–]?\s*2026\s*[-–]?\s*0*(\d{3,4})",r["extracted_text"],re.I)))
 r["resolutions_2026"]=nums
 unexpected=[n for n in nums if n>859]
 if unexpected:events.append({"kind":"NEW_RESOLUTION_IN_REGULATOR_INDEX","numbers":unexpected})
# Scan BO/Infoleg summaries directly; do not use a stale ENReGE index as legal authority.
bo_findings=[]
for rec in records:
 if not rec["id"].startswith("bo_") or not rec["verified"]:continue
 t=rec.get("extracted_text","")
 rec["page_semantically_usable"]=bool(re.search(r"Sumario N[º°]|Fecha de publicaci[oó]n|ENTE NACIONAL REGULADOR|SECCI[ÓO]N",t,re.I))
 if not rec["page_semantically_usable"]:
  unverified.append(rec["id"]+"_semantics")
 # Analyze row/block text where possible; do not treat generic word 'gas' as a material price change.
 rows=re.split(r"(?=Resoluci[oó]n\s+\d+/\d{4})",t,flags=re.I)
 for row in rows:
  if re.search(r"ENTE NACIONAL REGULADOR DEL GAS|ENREGE|ENARGAS",row,re.I) and re.search(r"CUADROS?\s+TARIFARI|CORRECCI[ÓO]N|RECTIF[IÍ]C",row,re.I):
   n=re.search(r"Resoluci[oó]n\s+(\d+)/2026",row,re.I)
   number=int(n.group(1)) if n else None
   finding={"source":rec["id"],"number":number,"extract":row[:420]}
   bo_findings.append(finding)
   if number is not None and number>859:
    events.append({"kind":"NEW_GAS_TARIFF_NORM_IN_OFFICIAL_BO","number":number,"source":rec["id"],"extract":row[:300]})
# Note: if a new summary reports an act without number, manual review is needed.
events=list({json.dumps(e,sort_keys=True,ensure_ascii=False):e for e in events}.values())
semantics={"bo_findings":bo_findings,"history_index_baseline":"01/10/2026–12/10/2026 notified 2026-11-03","new_resolution_threshold":859}
# Keep the core metadata small. Raw bytes retained only for material changes in output artifact.
for rec in records:
 rec.pop("extracted_text",None)
 rec.pop("links",None)
 if rec["id"].startswith("bo_"):rec.pop("page_semantically_usable",None)
status={
 "run":"2026-11-04","checked_at_utc":dt.datetime.now(UTC).isoformat(),
 "policy":"SHADOW_ONLY_NO_MERGE_NO_PUBLICATION_NO_AUTO_REBUILD",
 "legal_dates_prior":{"zone_fria_816_822_sanctioned":"2026-10-27","published":"2026-10-28","november_841_859_sanctioned":"2026-10-29","published":"2026-10-30","november_announced_vigencia":"2026-11-01"},
 "material_changes":events,"unverified_sources":sorted(set(unverified)),
 "material_change_confirmed":bool(events),
 "all_raw_bytes_verified":not any(not r["verified"] for r in records),
 "rebuild_new":False,"merge":False,"publication":False,
 "semantic_check":semantics,"records":records,
 "state":"MATERIAL_CHANGE_VERIFIED" if events else "NO_MATERIAL_CHANGE_DETECTED_PARTIAL_VERIFICATION" if unverified else "NO_CHANGE_VERIFIED"}
(HERE/"AUDIT_20261104.json").write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n")
(HERE/"SUMMARY.txt").write_text(json.dumps({"state":status["state"],"events":events,"unverified":sorted(set(unverified)),"sources":len(records)},ensure_ascii=False,indent=2)+"\n")
print("FINAL_RESULT",json.dumps({"state":status["state"],"events":events,"unverified":sorted(set(unverified))},ensure_ascii=False),flush=True)
