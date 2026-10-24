#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,re,time
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from live_claim_engine import fold,process,summary

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def fetch(s,url):
    err=None
    for attempt in range(1,4):
        try:
            r=s.get(url,timeout=(20,180),allow_redirects=True);r.raise_for_status();return r.content,{'final_url':r.url,'status':r.status_code,'content_type':r.headers.get('content-type'),'bytes':len(r.content),'raw_sha256':sha(r.content),'attempt':attempt,'error':None}
        except Exception as e:err=f'{type(e).__name__}: {e}';time.sleep(attempt*2)
    return None,{'final_url':None,'status':None,'content_type':None,'bytes':0,'raw_sha256':None,'attempt':3,'error':err}
def text_from(kind,path,data):
    if kind=='pdf':
        r=PdfReader(str(path));return '\n'.join((p.extract_text() or '') for p in r.pages)
    soup=BeautifulSoup(data,'html.parser')
    for t in soup(['script','style','noscript']):t.decompose()
    return re.sub(r'\s+',' ',soup.get_text(' ',strip=True)).strip()
def write_csv(path,rows):
    if not rows:return
    fields=[]
    for r in rows:
        for k in r:
            if k not in fields:fields.append(k)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--registry',required=True,type=Path);ap.add_argument('--atlas',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True);raw=a.output/'raw';texts=a.output/'text';raw.mkdir(exist_ok=True);texts.mkdir(exist_ok=True)
    registry=json.loads(a.registry.read_text(encoding='utf-8'));atlas=json.loads(a.atlas.read_text(encoding='utf-8'));s=requests.Session();s.headers.update({'User-Agent':'IRP27-Live-Claim-Ingestion/0.5','Accept':'text/html,application/pdf,*/*'})
    sources=[];events=[];errors=[]
    for source in registry:
        ext='pdf' if source['kind']=='pdf' else 'html';path=raw/f"{source['source_id']}.{ext}";data,meta=fetch(s,source['url']);meta.update({k:source[k] for k in ['source_id','actor','publisher_type','date','url','kind']});sources.append(meta)
        if data is None:errors.append({'source_id':source['source_id'],'error':meta['error']});continue
        path.write_bytes(data)
        try:text=text_from(source['kind'],path,data);(texts/f"{source['source_id']}.txt").write_text(text,encoding='utf-8')
        except Exception as e:errors.append({'source_id':source['source_id'],'error':repr(e)});continue
        ft=fold(text)
        for claim in source['claims']:
            verified=fold(claim['source_fragment']) in ft
            if not verified:errors.append({'source_id':source['source_id'],'live_claim_id':claim['live_claim_id'],'error':'SOURCE_FRAGMENT_NOT_VERIFIED'})
            events.append(process(source,claim,atlas,verified,meta['raw_sha256']))
    write_csv(a.output/'live_claims.csv',events);write_csv(a.output/'human_review_queue.csv',[e for e in events if e['notification_class'] in {'HUMAN_REVIEW_ALERT','INTERNAL_ALERT'}])
    (a.output/'live_claim_events.jsonl').write_text('\n'.join(json.dumps(e,ensure_ascii=False) for e in events)+'\n',encoding='utf-8')
    (a.output/'source_snapshots.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2),encoding='utf-8');(a.output/'errors.json').write_text(json.dumps(errors,ensure_ascii=False,indent=2),encoding='utf-8')
    status=summary(events);status.update({'sources_expected':len(registry),'sources_acquired':sum(x['bytes']>0 for x in sources),'errors':len(errors)});(a.output/'status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest=[]
    for p in sorted(a.output.rglob('*')):
        if p.is_file() and p.name!='MANIFEST.sha256':manifest.append(f'{sha(p.read_bytes())}  {p.relative_to(a.output).as_posix()}')
    (a.output/'MANIFEST.sha256').write_text('\n'.join(manifest)+'\n',encoding='utf-8');print(json.dumps(status,ensure_ascii=False,indent=2));return 0 if status['sources_acquired']==status['sources_expected'] and status['verified_fragments']==status['events'] else 2
if __name__=='__main__':raise SystemExit(main())
