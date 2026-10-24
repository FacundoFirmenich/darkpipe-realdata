#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from typing import Any
import hashlib, json, re, unicodedata

EVENT_TYPES={"NEW_CLAIM","KNOWN_CLAIM","REFRAMED_VARIANT","NUMERIC_UPDATE","SOURCE_REVISION","ESTIMAND_SHIFT","RHETORICAL_EXPANSION","NEW_SENTINEL","NEW_INDEPENDENT_LINEAGE"}
CAUSAL_MARKERS=("porque","demuestra","prueba","genera","crea","fortalece","produce","condición necesaria","materia prima")
UNIVERSAL_MARKERS=("todos","siempre","garantizado","veinte años","definitivamente","inequívocamente")
FORECAST_MARKERS=("tendrá","se van a venir","vamos a tener","proyecta","prevé")

def fold(text:str)->str:
    text=unicodedata.normalize('NFKD',text.casefold())
    text=''.join(c for c in text if not unicodedata.combining(c))
    return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9%$.,:+-]+',' ',text)).strip()

def tokens(text:str)->set[str]:
    stop={'el','la','los','las','de','del','y','en','un','una','que','se','por','para','con','es','al','su','a','the','of','and','is','to'}
    return {x for x in re.findall(r'[a-z0-9]+',fold(text)) if len(x)>2 and x not in stop}

def jaccard(a:str,b:str)->float:
    x,y=tokens(a),tokens(b)
    return len(x&y)/len(x|y) if x|y else 0.0

def stable_id(*parts:str)->str:
    return hashlib.sha256('||'.join(parts).encode()).hexdigest()

def lexical_flags(text:str)->dict[str,bool]:
    f=fold(text)
    return {
        'causal':any(m in f for m in CAUSAL_MARKERS),
        'universal':any(m in f for m in UNIVERSAL_MARKERS),
        'forecast':any(m in f for m in FORECAST_MARKERS),
        'numeric':bool(re.search(r'\d',text)),
    }

def match_atlas(claim:dict[str,Any], atlas:list[dict[str,Any]])->dict[str,Any]:
    hint=claim.get('atlas_hint')
    candidates=[]
    for row in atlas:
        sim=max(jaccard(claim['normalized_claim'],row['claim']),jaccard(claim['estimand'],row['estimand']))
        if row['claim_id']==hint: sim=max(sim,0.88)
        candidates.append((sim,row))
    candidates.sort(key=lambda x:x[0],reverse=True)
    best_sim,best=candidates[0]
    second_sim=candidates[1][0] if len(candidates)>1 else 0.0
    return {'claim_id':best['claim_id'],'similarity':round(best_sim,4),'margin':round(best_sim-second_sim,4),'classification':best['classification'],'public_language':best['public_language'],'max_authority':best['max_authority']}

def infer_event(claim:dict[str,Any], match:dict[str,Any])->str:
    hint=claim.get('event_hint')
    if hint in EVENT_TYPES:return hint
    flags=lexical_flags(claim['normalized_claim'])
    if flags['causal'] or flags['universal']:return 'RHETORICAL_EXPANSION'
    if flags['forecast']:return 'NEW_CLAIM'
    if flags['numeric'] and match['similarity']>=0.65:return 'NUMERIC_UPDATE'
    if match['similarity']>=0.80:return 'KNOWN_CLAIM'
    if match['similarity']>=0.35:return 'REFRAMED_VARIANT'
    return 'NEW_CLAIM'

def materiality(event_type:str,claim_mode:str,flags:dict[str,bool],independent:bool)->int:
    w={'NUMERIC_UPDATE':5,'SOURCE_REVISION':6,'NEW_SENTINEL':6,'NEW_INDEPENDENT_LINEAGE':8,'KNOWN_CLAIM':3,'REFRAMED_VARIANT':7,'NEW_CLAIM':8,'ESTIMAND_SHIFT':11,'RHETORICAL_EXPANSION':12}
    score=w.get(event_type,5)+(3 if flags['causal'] else 0)+(2 if flags['universal'] else 0)+(2 if flags['forecast'] else 0)+(3 if independent else 0)
    if 'FORECAST' in claim_mode:score+=2
    return min(score,20)

def route(score:int,event_type:str)->str:
    if event_type in {'ESTIMAND_SHIFT','RHETORICAL_EXPANSION'} or score>=15:return 'HUMAN_REVIEW_ALERT'
    if score>=10:return 'INTERNAL_ALERT'
    if score>=6:return 'BRIEF'
    return 'SILENT_LOG'

def process(source:dict[str,Any],claim:dict[str,Any],atlas:list[dict[str,Any]],verified:bool,raw_sha256:str|None)->dict[str,Any]:
    match=match_atlas(claim,atlas);event=infer_event(claim,match);flags=lexical_flags(claim['normalized_claim'])
    independent=event=='NEW_INDEPENDENT_LINEAGE' or source['publisher_type'] in {'legislative_budget_office'}
    score=materiality(event,claim['claim_mode'],flags,independent)
    return {
      'event_id':'EVT-'+stable_id(source['source_id'],claim['live_claim_id'],raw_sha256 or '')[:16],
      'live_claim_id':claim['live_claim_id'],'source_id':source['source_id'],'source_date':source['date'],'actor':source['actor'],'publisher_type':source['publisher_type'],'source_url':source['url'],'source_fragment':claim['source_fragment'],'normalized_claim':claim['normalized_claim'],'claim_mode':claim['claim_mode'],'fragment_verified':verified,'raw_sha256':raw_sha256,'event_type':event,'atlas_match':match['claim_id'],'atlas_similarity':match['similarity'],'atlas_margin':match['margin'],'estimand':claim['estimand'],'observed_narrow':claim['observed_narrow'],'not_established':claim['not_established'],'safe_wording':claim['safe_wording'],'blocked_wording':claim['blocked_wording'],'orientations':claim['orientations'],'lexical_flags':flags,'independent_lineage':independent,'materiality_score':score,'notification_class':route(score,event),'max_authority':match['max_authority'],'status':'AWAITING_HUMAN_TRIAGE','automatic_publication':False,
      'review_roles':['data_steward','domain_reviewer','statistical_reviewer','publication_authority']
    }

def summary(events:list[dict[str,Any]])->dict[str,Any]:
    from collections import Counter
    return {'events':len(events),'verified_fragments':sum(e['fragment_verified'] for e in events),'event_types':dict(Counter(e['event_type'] for e in events)),'routes':dict(Counter(e['notification_class'] for e in events)),'atlas_claims_touched':len({e['atlas_match'] for e in events}),'automatic_publication':False,'causal_authority':False,'programmatic_authority':False}
