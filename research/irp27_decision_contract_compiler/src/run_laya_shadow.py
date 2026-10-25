#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, time
from pathlib import Path

def read_jsonl(path): return [json.loads(x) for x in Path(path).read_text(encoding='utf-8-sig').splitlines() if x.strip()]
def normalise(res):
    out={}
    for k,v in (res.get('answers') or {}).items():
        t=v.get('type')
        if t=='choice': out[k]={'type':'choice','choice':v.get('choice'),'confidence':v.get('confidence'),'probabilities':v.get('probabilities')}
        elif t=='noul': out[k]={'type':'noul','noul':v.get('noul'),'confidence':v.get('confidence')}
        elif t=='score': out[k]={'type':'score','score':v.get('score'),'confidence':v.get('confidence'),'probabilities':v.get('probabilities'),'legend':v.get('legend')}
        else: out[k]=v
    return out

def run_cases(router,cases,checkpoint,out):
    rows=[]
    for c in cases:
        t=time.perf_counter(); err=None; res=None
        try: res=router.predict(c['state'],c['questions'],model=checkpoint)
        except Exception as e: err=f'{type(e).__name__}: {e}'[:500]
        rows.append({'id':c['id'],'track':c.get('track'),'dataset':c.get('dataset'),'lang':c.get('lang'),'option_count':c.get('option_count'),'ok':err is None,'ms':round((time.perf_counter()-t)*1000,2),'model':checkpoint,'answers':normalise(res) if res else None,'error':err})
        out.write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in rows)+'\n')
    return rows

def main():
    p=argparse.ArgumentParser(); p.add_argument('--cases',required=True); p.add_argument('--flip-cases',required=True); p.add_argument('--output',type=Path,required=True); p.add_argument('--limit',type=int,default=60); p.add_argument('--checkpoints',nargs='+',default=['english','multilingual','typed-decisions']); a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=True)
    import torch
    from laya import Router
    device='cuda' if torch.cuda.is_available() else 'cpu'; router=Router(device=device); t0=time.perf_counter(); router.preload(a.checkpoints); load_ms=(time.perf_counter()-t0)*1000
    base=read_jsonl(a.cases)[:a.limit]; flip=read_jsonl(a.flip_cases)[:a.limit]
    status={'device':device,'load_ms':round(load_ms,2),'loaded':list(router.loaded),'limit':a.limit,'checkpoints':{},'provider_has_authority':False,'automatic_execution':False,'automatic_publication':False}
    for cp in a.checkpoints:
        br=run_cases(router,base,cp,a.output/f'laya_{cp}_base.jsonl'); fr=run_cases(router,flip,cp,a.output/f'laya_{cp}_flip.jsonl')
        ok=[r for r in br+fr if r['ok']]; status['checkpoints'][cp]={'base_ok':sum(r['ok'] for r in br),'flip_ok':sum(r['ok'] for r in fr),'failures':sum(not r['ok'] for r in br+fr),'mean_ms':sum(r['ms'] for r in ok)/len(ok) if ok else None}
    (a.output/'live_laya_status.json').write_text(json.dumps(status,indent=2)+'\n'); print(json.dumps(status,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
