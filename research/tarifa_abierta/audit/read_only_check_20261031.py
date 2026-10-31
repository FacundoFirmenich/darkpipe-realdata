#!/usr/bin/env python3
"""Read-only official ENReGE October 2026 material-change check.
Never merges, publishes, edits the frozen source workbook or infers tariff changes.
"""
from __future__ import annotations
import hashlib, html, io, json, re, sys, time, zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

BASE_DIR = "https://www.enargas.gob.ar/secciones/precios-y-tarifas/"
URLS = {
 "workbook": BASE_DIR + "descargas/tarifas-gn-20261001.xlsx",
 "current": BASE_DIR + "cuadros-tarifarios.php",
 "historical": BASE_DIR + "cuadros-tarifarios-serie-historica.php",
 "resolutions": BASE_DIR + "resoluciones-tarifas-vigentes.php",
}
BASE_SHA = "fefe75fd5a1e9fa747e4871165b4a1e046743f050343d73a4b7eefaee91540b6"
BASE_SIZE = 653597
BASE_RESOLUTIONS = set(range(710,729)) | set(range(816,823))
RESOLUTION_IDS={n:431702+n-816 for n in range(816,823)}
OUTPUT=Path("official_check_20261031")
PDF_DIR=OUTPUT/"annexes"
OUTPUT.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; TarifaAbiertaShadowAudit/20261031)","Accept":"*/*"}

class Links(HTMLParser):
 def __init__(self):
  super().__init__()
  self.href=None; self.parts=[]; self.links=[]
 def handle_starttag(self,tag,attrs):
  if tag=="a":
   self.href=dict(attrs).get("href"); self.parts=[]
 def handle_data(self,data):
  if self.href is not None:self.parts.append(data)
 def handle_endtag(self,tag):
  if tag=="a" and self.href is not None:
   self.links.append({"text":" ".join(html.unescape(" ".join(self.parts)).split()),"href":self.href})
   self.href=None; self.parts=[]

def capture(url, maxbytes=35000000):
 req=Request(url,headers=HEADERS)
 with urlopen(req,timeout=80) as response:
  raw=response.read(maxbytes+1)
  if len(raw)>maxbytes: raise ValueError("FILE_EXCEEDS_SAFETY_LIMIT")
  md={"requested_url":url,"final_url":response.geturl(),"http_status":response.status,
   "mime":response.headers.get("Content-Type"),"last_modified":response.headers.get("Last-Modified"),
   "etag":response.headers.get("ETag"),"bytes":len(raw),
   "sha256":hashlib.sha256(raw).hexdigest()}
 return raw,md

def safe_fetch(url):
 for i in range(2):
  try:return capture(url),None
  except Exception as e:
   error=f"{type(e).__name__}: {str(e)[:240]}"
   if i==0:time.sleep(2)
 return None,error

report={
 "checked_at_utc":datetime.now(timezone.utc).isoformat(),
 "baseline":{"workbook_sha256":BASE_SHA,"workbook_bytes":BASE_SIZE,
   "reported_on":"2026-10-23","baseline_resolutions_notified_on":"2026-10-30",
   "baseline_new_resolutions":list(range(816,823)),
   "baseline_annex_pdf_bytes_acquired":False,"baseline_shadow_reconstruction":"v1.6 585+585"},
 "sources":{},"annexes":[],"material_changes":[],"errors":[],
 "additional_shadow_reconstruction":{"executed":False,"reason":"No annex-to-workbook reconciled schema / no verified full reconstruction"},
 "merge":False,"automatic_publication":False,"numeric_tariff_delta_computed":False,
 "causal_conclusions":False
}
page_links={}
for name,url in URLS.items():
 fetched,err=safe_fetch(url)
 if err:
  report["errors"].append({"source":name,"error":err})
  continue
 raw,meta=fetched
 if name=="workbook":
  meta["valid_ooxml"]=zipfile.is_zipfile(io.BytesIO(raw))
  meta["matches_baseline_hash"]=meta["sha256"]==BASE_SHA
  meta["matches_baseline_size"]=meta["bytes"]==BASE_SIZE
  if not meta["valid_ooxml"]:report["errors"].append({"source":name,"error":"NOT_VALID_OOXML"})
  elif not meta["matches_baseline_hash"]:
   report["material_changes"].append("OFFICIAL_OCT_XLSX_RAW_BYTES_CHANGED")
   (OUTPUT/"CHANGED_OFFICIAL_OCTOBER.xlsx").write_bytes(raw)
 else:
  decoded=raw.decode("utf-8",errors="replace")
  p=Links();p.feed(decoded);page_links[name]=p.links
  if name=="current":
   gn=[x for x in p.links if "gas natural" in x["text"].lower()]
   meta["natural_gas_links"]=gn
   if not gn:report["errors"].append({"source":name,"error":"GN_LINK_NOT_FOUND"})
   else:
    meta["october_1_link"]=any("01/10/2026" in x["text"] for x in gn)
    meta["october_1_workbook_url_preserved"]=any("tarifas-gn-20261001.xlsx" in x["href"] for x in gn)
    if not (meta["october_1_link"] and meta["october_1_workbook_url_preserved"]):
     report["material_changes"].append("CURRENT_NATURAL_GAS_TARIFF_LINK_OR_EFFECTIVE_DATE_CHANGED")
  elif name=="historical":
   starts=[x for x in p.links if "gas natural" in x["text"].lower()]
   meta["latest_gas_period"]=starts[0]["text"] if starts else None
   meta["october_2026_in_history"]=any("01/10/2026" in x["text"] or "octubre 2026" in x["text"].lower() for x in starts)
   if meta["october_2026_in_history"]:
    report["material_changes"].append("OCTOBER_2026_ENTERED_GN_HISTORICAL_SERIES")
   if not starts:report["errors"].append({"source":name,"error":"GN_HISTORICAL_NOT_FOUND"})
  elif name=="resolutions":
   codes=sorted(set(int(x) for x in re.findall(r"RESFC2026-0?(\d{3,4})",html.unescape(decoded))))
   meta["codes"]=codes
   meta["new_since_20261030"]=[x for x in codes if x not in BASE_RESOLUTIONS]
   if meta["new_since_20261030"]:
    report["material_changes"].append("NEW_POST_BASELINE_RESOLUTIONS_ON_INDEX")
 report["sources"][name]=meta

# Only the official annex PDFs, not the already-audited normative HTML texts, count as new material acquisition.
for number,norm_id in RESOLUTION_IDS.items():
 row={"resolution":number,"source_norm_url":f"https://www.argentina.gob.ar/normativa/nacional/norma-{norm_id}/texto","acquired":False}
 got,err=safe_fetch(row["source_norm_url"])
 if err:
  row["source_error"]=err;report["annexes"].append(row);continue
 normbytes,normmeta=got
 row["source_norm_meta"]=normmeta
 parser=Links();parser.feed(normbytes.decode("utf-8",errors="replace"))
 candidates=[x for x in parser.links if "anexos (pdf)" in x["text"].lower()]
 if not candidates:
  row["source_error"]="OFFICIAL_ANNEX_PDF_LINK_NOT_FOUND";report["annexes"].append(row);continue
 pdfurl=urljoin(normmeta["final_url"],candidates[0]["href"])
 row["pdf_link"]=pdfurl
 got,err=safe_fetch(pdfurl)
 if err:
  row["pdf_error"]=err;report["annexes"].append(row);continue
 pdf,meta=got
 row["pdf_meta"]=meta
 if not pdf.startswith(b"%PDF-"):
  row["pdf_error"]="NOT_PDF_MAGIC_HEADER";report["annexes"].append(row);continue
 path=PDF_DIR/f"ENREGE_RESFC_2026_{number}_annex.pdf"
 path.write_bytes(pdf)
 row["acquired"]=True;row["stored_at"]=str(path)
 try:
  from pypdf import PdfReader
  obj=PdfReader(io.BytesIO(pdf),strict=False)
  row["pages"]=len(obj.pages)
  texts=[page.extract_text(extraction_mode="layout") or "" for page in obj.pages]
  text="\n".join(texts)
  row["text_extracted_chars"]=len(text)
  row["numeric_table_line_candidates"]=sum(bool(re.search(r"\d[.,]\d+.*\d[.,]\d+",ln)) for ln in text.splitlines())
  row["pdf_contains_tariff_terms"]=bool(re.search(r"RESIDENCIAL|TARIFA|R1|R2|R3",text,re.I))
  (PDF_DIR/f"ENREGE_RESFC_2026_{number}_annex.txt").write_text(text,encoding="utf-8")
 except Exception as exc:
  row["pdf_inspection_error"]=type(exc).__name__+": "+str(exc)[:180]
 report["annexes"].append(row)

if all(x.get("acquired") for x in report["annexes"]) and len(report["annexes"])==7:
 report["material_changes"].append("SEVEN_OFFICIAL_ANNEX_PDFS_NEWLY_ACQUIRED_AND_HASHED")
elif any(x.get("acquired") for x in report["annexes"]):
 report["material_changes"].append("PARTIAL_OFFICIAL_ANNEX_PDF_ACQUISITION_NEW")
report["annex_acquired_count"]=sum(bool(a.get("acquired")) for a in report["annexes"])
report["numeric_tariff_table_contrasted"]=False
report["material_changes"]=sorted(set(report["material_changes"]))
report["status"]="MATERIAL_CHANGE_VERIFIED" if report["material_changes"] and not report["errors"] else ("MATERIAL_CHANGE_PARTIAL" if report["material_changes"] else ("NO_CHANGE_VERIFIED" if not report["errors"] else "PARTIAL_UNCONFIRMED"))
(OUTPUT/"audit_20261031.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({
 "status":report["status"],"changes":report["material_changes"],"errors":report["errors"],
 "workbook":report["sources"].get("workbook"),
 "resolution_codes":report["sources"].get("resolutions",{}).get("codes"),
 "history_latest":report["sources"].get("historical",{}).get("latest_gas_period"),
 "annex_count":report["annex_acquired_count"],
 "annexes":[{"resolution":x["resolution"],"acquired":x.get("acquired"),"pdf":x.get("pdf_meta"),"pages":x.get("pages"),"error":x.get("pdf_error") or x.get("source_error")} for x in report["annexes"]]
},ensure_ascii=False,indent=2))
