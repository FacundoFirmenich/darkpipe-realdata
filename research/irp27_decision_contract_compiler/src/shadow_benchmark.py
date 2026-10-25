#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json, math, statistics
from collections import Counter
from pathlib import Path
from typing import Any
import numpy as np

EPS=1e-15

def read_jsonl(path: Path)->list[dict[str,Any]]:
    return [json.loads(x) for x in path.read_text(encoding='utf-8-sig').splitlines() if x.strip()]

def answer_payload(row:dict[str,Any], qid:str)->dict[str,Any]|None:
    a=row.get('answers') or {}; return a.get(qid)

def extract_distribution(ans:dict[str,Any], criteria:list[str])->dict[str,float]:
    typ=ans.get('type')
    if typ=='choice' or typ=='score':
        p=ans.get('probabilities') or {}; return {k:float(p.get(k,0.0)) for k in criteria}
    if typ=='noul':
        v=ans.get('noul')
        if isinstance(v,bool): yes=1.0 if v else 0.0
        elif isinstance(v,(int,float)): yes=float(v)
        else: yes=float(ans.get('probability',ans.get('confidence',0.5)))
        yes=max(0.0,min(1.0,yes)); return {'true':yes,'false':1-yes}
    return {k:0.0 for k in criteria}

def predicted(ans:dict[str,Any])->Any:
    typ=ans.get('type')
    if typ=='choice': return ans.get('choice')
    if typ=='score': return ans.get('score')
    if typ=='noul':
        v=ans.get('noul')
        if isinstance(v,bool): return v
        if isinstance(v,(int,float)): return bool(v>=0.5)
    return None

def gold_key(gold:Any)->str:
    if isinstance(gold,bool): return 'true' if gold else 'false'
    return str(gold)

def ece(conf:list[float], correct:list[int], bins:int=10)->float:
    if not conf: return float('nan')
    total=len(conf); out=0.0
    for b in range(bins):
        lo=b/bins; hi=(b+1)/bins
        idx=[i for i,c in enumerate(conf) if (lo<=c<(hi if b<bins-1 else hi+1e-12))]
        if idx: out += len(idx)/total*abs(sum(conf[i] for i in idx)/len(idx)-sum(correct[i] for i in idx)/len(idx))
    return out

def score_provider(cases:list[dict[str,Any]], rows:list[dict[str,Any]], provider:str)->tuple[dict[str,Any],list[dict[str,Any]]]:
    byid={r['id']:r for r in rows}; records=[]
    for c in cases:
        r=byid.get(c['id'])
        if not r or not r.get('ok'): continue
        for qid,q in c['questions'].items():
            ans=answer_payload(r,qid)
            if not ans or qid not in c.get('gold',{}): continue
            typ=q['type']; gold=c['gold'][qid]; pred=predicted(ans)
            criteria=list(q.get('criteria',{})) if typ!='noul' else ['true','false']
            dist=extract_distribution(ans,criteria)
            g=gold_key(gold); p=max(EPS,float(dist.get(g,0.0)))
            confidence=max(dist.values()) if dist else 0.0
            is_correct=int((pred==gold) or (str(pred).lower()==str(gold).lower()))
            onehot=np.array([1.0 if k==g else 0.0 for k in criteria]); pv=np.array([dist.get(k,0.0) for k in criteria],dtype=float)
            if pv.sum()>0: pv=pv/pv.sum()
            records.append({'provider':provider,'id':c['id'],'track':c.get('track'),'dataset':c.get('dataset'),'lang':c.get('lang'),'primitive':typ,'question_id':qid,'gold':gold,'predicted':pred,'correct':is_correct,'confidence':confidence,'log_loss':-math.log(p),'brier':float(np.sum((pv-onehot)**2)),'ms':float(r.get('ms') or 0.0),'model':r.get('model')})
    if not records: return {'provider':provider,'n':0},[]
    byprim={}
    for prim in sorted(set(x['primitive'] for x in records)):
        rr=[x for x in records if x['primitive']==prim]; byprim[prim]={'n':len(rr),'accuracy':sum(x['correct'] for x in rr)/len(rr),'log_loss':statistics.fmean(x['log_loss'] for x in rr),'brier':statistics.fmean(x['brier'] for x in rr),'ece':ece([x['confidence'] for x in rr],[x['correct'] for x in rr])}
    m={'provider':provider,'n':len(records),'cases':len(set(x['id'] for x in records)),'accuracy':sum(x['correct'] for x in records)/len(records),'log_loss':statistics.fmean(x['log_loss'] for x in records),'brier':statistics.fmean(x['brier'] for x in records),'ece':ece([x['confidence'] for x in records],[x['correct'] for x in records]),'latency_ms':{'mean':statistics.fmean(x['ms'] for x in records),'p50':float(np.quantile([x['ms'] for x in records],.5)),'p95':float(np.quantile([x['ms'] for x in records],.95))},'by_primitive':byprim,'models':dict(Counter(str(x['model']) for x in records))}
    return m,records

def stability(base:list[dict[str,Any]],variant:list[dict[str,Any]],name:str)->dict[str,Any]:
    def key(r): return (r['id'],r['question_id'])
    a={key(x):x for x in base}; b={key(x):x for x in variant}; common=sorted(set(a)&set(b))
    if not common:return {'name':name,'n':0}
    same=sum(str(a[k]['predicted'])==str(b[k]['predicted']) for k in common)
    baseok=sum(a[k]['correct'] for k in common); varok=sum(b[k]['correct'] for k in common)
    harmful=sum(a[k]['correct']==1 and b[k]['correct']==0 for k in common); beneficial=sum(a[k]['correct']==0 and b[k]['correct']==1 for k in common)
    return {'name':name,'n':len(common),'prediction_stability':same/len(common),'base_accuracy':baseok/len(common),'variant_accuracy':varok/len(common),'harmful_flips':harmful,'beneficial_flips':beneficial}

def disagreement(records_by_provider:dict[str,list[dict[str,Any]]])->dict[str,Any]:
    providers=sorted(records_by_provider); maps={p:{(r['id'],r['question_id']):r for r in records_by_provider[p]} for p in providers}; out={}
    for i,p in enumerate(providers):
        for q in providers[i+1:]:
            keys=set(maps[p])&set(maps[q])
            if not keys: continue
            disagree=sum(str(maps[p][k]['predicted'])!=str(maps[q][k]['predicted']) for k in keys)
            p_only=sum(maps[p][k]['correct']>maps[q][k]['correct'] for k in keys); q_only=sum(maps[q][k]['correct']>maps[p][k]['correct'] for k in keys)
            out[f'{p}__{q}']={'n':len(keys),'disagreement_rate':disagree/len(keys),'p_correct_q_wrong':p_only,'q_correct_p_wrong':q_only}
    return out

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--cases',type=Path,required=True); ap.add_argument('--providers',type=Path,nargs='+',required=True); ap.add_argument('--provider-names',nargs='+',required=True); ap.add_argument('--variant-cases',type=Path); ap.add_argument('--variant-providers',type=Path,nargs='*'); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args()
    cases=read_jsonl(a.cases); out=a.output; out.mkdir(parents=True,exist_ok=True); results={}; recs={}
    for name,path in zip(a.provider_names,a.providers):
        m,r=score_provider(cases,read_jsonl(path),name); results[name]=m; recs[name]=r
    st={}
    if a.variant_cases and a.variant_providers:
        vc=read_jsonl(a.variant_cases)
        for name,path in zip(a.provider_names,a.variant_providers):
            _,vr=score_provider(vc,read_jsonl(path),name); st[name]=stability(recs[name],vr,'option_order_flip')
    status={'source':'EXTERNAL_PUBLISHED_RAW_OUTPUTS_REANALYSIS','providers':results,'stability':st,'disagreement':disagreement(recs),'provider_results_are_not_new_live_calls':True,'automatic_execution':False,'automatic_publication':False}
    (out/'shadow_benchmark.json').write_text(json.dumps(status,indent=2)+'\n')
    allr=[r for p in recs.values() for r in p]
    if allr:
        with (out/'scored_predictions.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(allr[0])); w.writeheader(); w.writerows(allr)
    print(json.dumps(status,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
