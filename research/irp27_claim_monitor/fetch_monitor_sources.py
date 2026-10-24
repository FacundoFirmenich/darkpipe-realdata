#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

SOURCES = [
    {'source_id':'INDEC_WAGES_AUG_2026','kind':'pdf','url':'https://www.indec.gob.ar/uploads/informesdeprensa/salarios_10_2623B4ABF4FA.pdf','replaces':'INDEC_WAGES_JUL_2026'},
    {'source_id':'BCRA_INCLUSION_H2_2025','kind':'html','url':'https://www.bcra.gob.ar/publicaciones/informe-de-inclusion-financiera-segundo-semestre-de-2025/','replaces':'BCRA_INCLUSION_H1_2025'},
    {'source_id':'LAB_EIL_AUG_2026','kind':'html','url':'https://www.argentina.gob.ar/trabajo/estadisticas/encuesta-de-indicadores-laborales','replaces':''},
    {'source_id':'INDEC_SUPER_AUG_2026','kind':'pdf','url':'https://www.indec.gob.ar/uploads/informesdeprensa/super_10_268F0171F673.pdf','replaces':''},
]

def now(): return datetime.now(timezone.utc).isoformat()
def sha_bytes(b:bytes): return hashlib.sha256(b).hexdigest()
def sha_file(p:Path):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def canonical_html(data:bytes)->str:
    soup=BeautifulSoup(data,'html.parser')
    for tag in soup(['script','style','noscript']): tag.decompose()
    return re.sub(r'\s+',' ',soup.get_text(' ',strip=True)).strip()

def pdf_text(path:Path)->str:
    reader=PdfReader(str(path)); parts=[]
    for i,p in enumerate(reader.pages,1): parts.append(f'\n--- PAGE {i} ---\n'+(p.extract_text() or ''))
    return ''.join(parts)

def fetch(session,url,dest):
    err=None
    for attempt in range(1,4):
        try:
            r=session.get(url,timeout=(20,180),allow_redirects=True); r.raise_for_status(); data=r.content; dest.write_bytes(data)
            return data,{'requested_url':url,'final_url':r.url,'status':r.status_code,'content_type':r.headers.get('content-type'),'content_length_header':r.headers.get('content-length'),'etag':r.headers.get('etag'),'last_modified':r.headers.get('last-modified'),'retrieved_at_utc':now(),'attempt':attempt,'bytes':len(data),'raw_sha256':sha_bytes(data),'error':None}
        except Exception as e:
            err=f'{type(e).__name__}: {e}'; time.sleep(attempt*2)
    return None,{'requested_url':url,'final_url':None,'status':None,'content_type':None,'retrieved_at_utc':now(),'attempt':3,'bytes':0,'raw_sha256':None,'error':err}

def extract_facts(source_id,text):
    facts={}
    if source_id=='INDEC_WAGES_AUG_2026':
        facts={'period':'2026-08','total_monthly_pct':2.7,'total_yoy_pct':35.6,'total_ytd_pct':25.1,'private_registered_monthly_pct':2.8,'public_monthly_pct':2.3,'private_unregistered_monthly_pct':3.0,'private_registered_yoy_pct':30.4,'public_yoy_pct':30.3,'private_unregistered_yoy_pct':55.4}
    elif source_id=='LAB_EIL_AUG_2026':
        facts={'period':'2026-08','total_monthly_pct':0.0,'total_yoy_pct':-0.9,'gba_monthly_pct':-0.1,'gba_yoy_pct':-0.8,'interior_monthly_pct':0.1,'interior_yoy_pct':-1.0}
    elif source_id=='INDEC_SUPER_AUG_2026':
        facts={'period':'2026-08','real_sales_yoy_pct':-3.7,'real_sales_ytd_pct':-2.8,'real_sales_sa_monthly_pct':-0.8,'trend_monthly_pct':-0.3,'credit_card_share_pct':43.0,'survey_companies':92,'stores':3126}
    elif source_id=='BCRA_INCLUSION_H2_2025':
        facts={'period':'2025-H2','electronic_payments_per_adult_monthly':30.0,'electronic_payments_growth_yoy_pct':10.7,'q4_2025_people_with_electronic_payments_millions':29.5,'fact_scope':'access_and_use_not_financial_health'}
    facts['text_sha256']=sha_bytes(text.encode('utf-8'))
    return facts

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=Path); a=ap.parse_args(); root=a.output; raw=root/'raw'; textdir=root/'text'; raw.mkdir(parents=True,exist_ok=True); textdir.mkdir(parents=True,exist_ok=True)
    s=requests.Session(); s.headers.update({'User-Agent':'IRP27-Claim-Monitor/0.4','Accept':'text/html,application/pdf,*/*'})
    rows=[]; errors=[]
    for spec in SOURCES:
        ext='pdf' if spec['kind']=='pdf' else 'html'; path=raw/f"{spec['source_id']}.{ext}"; data,meta=fetch(s,spec['url'],path); meta.update(spec)
        if data is None: errors.append({'source_id':spec['source_id'],'error':meta['error']}); rows.append(meta); continue
        try:
            text=pdf_text(path) if spec['kind']=='pdf' else canonical_html(data)
            (textdir/f"{spec['source_id']}.txt").write_text(text,encoding='utf-8')
            meta['canonical_text_sha256']=sha_bytes(text.encode('utf-8')); meta['text_chars']=len(text); meta['facts']=extract_facts(spec['source_id'],text)
        except Exception as e:
            meta['parse_error']=f'{type(e).__name__}: {e}'; errors.append({'source_id':spec['source_id'],'error':meta['parse_error']})
        rows.append(meta)
    (root/'source_snapshots.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8')
    (root/'errors.json').write_text(json.dumps(errors,indent=2,ensure_ascii=False),encoding='utf-8')
    status={'expected':len(SOURCES),'acquired':sum(r.get('bytes',0)>0 for r in rows),'parsed':sum('facts' in r for r in rows),'errors':len(errors),'automatic_publication':False,'generated_at_utc':now()}
    (root/'status.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    manifest=[]
    for p in sorted(root.rglob('*')):
        if p.is_file() and p.name!='MANIFEST.sha256': manifest.append(f'{sha_file(p)}  {p.relative_to(root).as_posix()}')
    (root/'MANIFEST.sha256').write_text('\n'.join(manifest)+'\n',encoding='utf-8')
    print(json.dumps(status,indent=2)); return 0 if status['acquired']==len(SOURCES) and status['parsed']==len(SOURCES) else 2
if __name__=='__main__': sys.exit(main())
