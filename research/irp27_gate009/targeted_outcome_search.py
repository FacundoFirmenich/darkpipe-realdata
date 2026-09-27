#!/usr/bin/env python3
"""Directed search for a gas-specific consumer-price outcome in official APIs.

This is a discovery and compatibility audit. String classification creates
candidates, never causal authority. Candidate series are archived verbatim.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests

SEARCH = "https://apis.datos.gob.ar/series/api/search/"
SERIES = "https://apis.datos.gob.ar/series/api/series/"
QUERIES = [
    "gas por red", "gas de red", "gas natural por red", "gas natural",
    "gas domiciliario", "precio gas natural", "ipc gas natural",
    "ipc-gba gas", "gas en garrafa", "combustibles para la vivienda gas",
]


def utcnow(): return datetime.now(timezone.utc).isoformat()
def sha256_bytes(b: bytes): return hashlib.sha256(b).hexdigest()

def classify(field, dataset):
    desc = str(field.get("description") or "")
    title = str(field.get("title") or "")
    dtitle = str(dataset.get("title") or "")
    source = str(dataset.get("source") or "")
    theme = str(dataset.get("theme") or "")
    text = " ".join([desc, title, dtitle]).casefold()
    has_gas = bool(re.search(r"\bgas\b|gaseoso", text))
    false_friend = "agua sin gas" in text
    broad = any(x in text for x in [
        "electricidad y gas", "electricidad, gas", "gas y agua",
        "vivienda y servicios", "otros combustibles", "suministro de electricidad",
        "valor agregado", "producción y consumo", "fabricacion de gas",
    ])
    indec = "indec" in source.casefold() or "instituto nacional de estad" in source.casefold()
    ipc = "ipc" in text or "precios al consumidor" in text
    monthly = field.get("frequency") == "R/P1M"
    prices = theme.casefold() == "precios" or "precio" in text
    if has_gas and not false_friend and indec and ipc and prices and monthly and not broad:
        return "GAS_SPECIFIC_MONTHLY_CONSUMER_PRICE_CANDIDATE"
    if has_gas and not false_friend and indec and ipc and prices and monthly and broad:
        return "BROAD_MONTHLY_IPC_BUNDLE"
    if false_friend:
        return "FALSE_FRIEND_WATER_WITHOUT_GAS"
    if has_gas and indec and prices:
        return "OTHER_OFFICIAL_PRICE_RELATED_GAS_SERIES"
    if has_gas:
        return "NON_OUTCOME_GAS_SERIES"
    return "NOT_GAS"


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--root",required=True,type=Path); args=ap.parse_args()
    root=args.root; out=root/"outcome_search"; out.mkdir(parents=True,exist_ok=True)
    s=requests.Session(); s.headers["User-Agent"]="IRP27-Gate009/0.2"
    all_items={}; query_log=[]
    for q in QUERIES:
        start=0; total=None
        while total is None or start < total:
            url=SEARCH+"?"+urlencode({"q":q,"limit":500,"start":start})
            try:
                r=s.get(url,timeout=(20,120)); body=r.content; r.raise_for_status(); payload=r.json()
                total=int(payload.get("count",0)); data=payload.get("data",[])
                query_log.append({"query":q,"start":start,"count":total,"returned":len(data),"url":r.url,"http_status":r.status_code,"sha256":sha256_bytes(body),"error":None})
                for item in data:
                    fid=(item.get("field") or {}).get("id")
                    if fid: all_items[fid]=item
                if not data: break
                start += len(data)
                if start >= 5000: break
            except Exception as exc:
                query_log.append({"query":q,"start":start,"count":total,"returned":0,"url":url,"http_status":None,"sha256":None,"error":f"{type(exc).__name__}: {exc}"})
                break
    with (out/"query_log.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["query","start","count","returned","url","http_status","sha256","error"]);w.writeheader();w.writerows(query_log)

    rows=[]; candidates=[]
    for fid,item in sorted(all_items.items()):
        field=item.get("field") or {}; dataset=item.get("dataset") or {}
        cls=classify(field,dataset)
        row={
            "series_id":fid,"classification":cls,"description":field.get("description"),"title":field.get("title"),
            "frequency":field.get("frequency"),"time_index_start":field.get("time_index_start"),"time_index_end":field.get("time_index_end"),
            "units":field.get("units"),"dataset_title":dataset.get("title"),"source":dataset.get("source"),"publisher":(dataset.get("publisher") or {}).get("name"),"theme":dataset.get("theme")
        }
        rows.append(row)
        if cls in {"GAS_SPECIFIC_MONTHLY_CONSUMER_PRICE_CANDIDATE","BROAD_MONTHLY_IPC_BUNDLE"}: candidates.append(row)
    fields=list(rows[0].keys()) if rows else ["series_id","classification"]
    with (out/"all_gas_search_results.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    with (out/"outcome_candidates.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(candidates)

    series_registry=[]
    for row in candidates[:50]:
        fid=row["series_id"]
        params={"ids":fid,"format":"json","metadata":"full","limit":1000}
        url=SERIES+"?"+urlencode(params)
        rec={"series_id":fid,"classification":row["classification"],"url":url}
        try:
            r=s.get(url,timeout=(20,120)); body=r.content; r.raise_for_status()
            (out/f"series_{re.sub(r'[^A-Za-z0-9_.-]','_',fid)}.json").write_bytes(body)
            payload=r.json(); data=payload.get("data",[])
            rec.update({"http_status":r.status_code,"sha256":sha256_bytes(body),"rows":len(data),"first_date":data[0][0] if data else None,"last_date":data[-1][0] if data else None,"error":None})
        except Exception as exc:
            rec.update({"http_status":None,"sha256":None,"rows":0,"first_date":None,"last_date":None,"error":f"{type(exc).__name__}: {exc}"})
        series_registry.append(rec)
    with (out/"candidate_series_registry.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["series_id","classification","url","http_status","sha256","rows","first_date","last_date","error"]);w.writeheader();w.writerows(series_registry)

    summary={
        "gate":"IRP27-GATE-OUTCOME-ACQUISITION-AND-PRETREND-FEASIBILITY-009",
        "phase":"TARGETED_OFFICIAL_OUTCOME_SEARCH","generated_at_utc":utcnow(),
        "queries":len(QUERIES),"unique_series_returned":len(rows),"candidate_count":len(candidates),
        "gas_specific_candidate_count":sum(r["classification"]=="GAS_SPECIFIC_MONTHLY_CONSUMER_PRICE_CANDIDATE" for r in candidates),
        "broad_bundle_candidate_count":sum(r["classification"]=="BROAD_MONTHLY_IPC_BUNDLE" for r in candidates),
        "series_archived":sum(r.get("http_status")==200 for r in series_registry),
        "classification_is_discovery_only":True,"effect_estimates_produced":0,"causal_authority":"BLOCKED"
    }
    (out/"outcome_search_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__": sys.exit(main())
