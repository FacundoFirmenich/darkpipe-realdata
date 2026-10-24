#!/usr/bin/env python3
"""Acquire exact ENARGAS AIP response objects via the official POST endpoint."""
from __future__ import annotations
import argparse,csv,hashlib,json,mimetypes,re,sys,time,zipfile
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
import openpyxl,requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

PAGE='https://www.enargas.gob.ar/secciones/transparencia/solicitar-informacion.php'
DOWNLOAD='https://www.enargas.gob.ar/secciones/transparencia/includes/DescargarArchivo.php'
TARGETS={
'AIP-2018-CATEGORY-LICENSEE':['4125/18','Usuarios Residenciales por Categoría'],
'AIP-2020-AMBA-CONSUMPTION-BANDS':['NO-2020-88456063','consumo promedio por segmento tarifario'],
'AIP-2021-JUJUY-TUCUMAN-CATEGORY-SUBZONE':['NO-2021-24551200','usuarios residenciales abiertos por categoría'],
'AIP-2022-PBA-MUNICIPAL-CATEGORY':['NO-2022-45174850','discriminados por categoría y municipio'],
'AIP-2022-DEMAND-BENEFIT-SUBZONE':['NO-2022-109180478','beneficiarios de tarifa social'],
'AIP-2022-MUNICIPAL-CATEGORY-VOLUME':['NO-2022-135121203','volumen facturado de los años 2018 a 2021'],
'AIP-2023-LOW-CONSUMPTION':['NO-2023-14236662','consumos inferiores a 30m3'],
'AIP-2024-AMBA-R-CATEGORIES':['NO-2024-47527596','categorías R1R21R22'],
'AIP-2024-GEOSPATIAL-LAYERS':['NO-2024-61552214','capas de información georreferenciada'],
}
S=requests.Session();S.headers.update({'User-Agent':'IRP27-Gate012/2.1 official-AIP-research'})

def now():return datetime.now(timezone.utc).isoformat()
def sha(b):return hashlib.sha256(b).hexdigest()
def safe(s):return re.sub(r'[^A-Za-z0-9_.-]+','_',s).strip('_')[:180] or 'object'
def filename(response,idx):
 d=response.headers.get('content-disposition','')
 m=re.search(r"filename\*?=(?:UTF-8''|\")?([^\";]+)",d,re.I)
 if m:return safe(m.group(1).strip())
 c=response.headers.get('content-type','').split(';')[0]
 return f'object_{idx:02d}{mimetypes.guess_extension(c) or ".bin"}'

def inspect(path,out):
 c=path.read_bytes()[:8]; suffix=path.suffix.lower()
 if suffix=='.pdf' or c.startswith(b'%PDF'):
  r=PdfReader(str(path)); texts=[]
  for i,p in enumerate(r.pages,1):texts.append(f'\n--- PAGE {i} ---\n'+(p.extract_text() or ''))
  txt=out/(path.stem+'.txt');txt.write_text(''.join(texts),encoding='utf-8')
  embedded=[]
  try:
   for name,payloads in r.attachments.items():
    if not isinstance(payloads,list):payloads=[payloads]
    for j,payload in enumerate(payloads,1):
     ep=out/safe(f'{path.stem}_embedded_{j}_{name}');ep.write_bytes(payload)
     embedded.append({'path':ep.name,'bytes':len(payload),'sha256':sha(payload)})
  except Exception as e:embedded.append({'error':repr(e)})
  return {'kind':'pdf','pages':len(r.pages),'text_path':txt.name,'embedded':embedded}
 if suffix in {'.xlsx','.xlsm'} or zipfile.is_zipfile(path):
  try:
   wb=openpyxl.load_workbook(path,read_only=True,data_only=True); sheets=[]
   for ws in wb.worksheets:
    rows=list(ws.iter_rows(values_only=True)); width=max((len(x) for x in rows),default=0)
    cp=out/safe(path.stem+'_'+ws.title+'.csv')
    with cp.open('w',newline='',encoding='utf-8') as f:
     fields=[f'col_{i+1}' for i in range(width)]+['source_row_number'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
     for rn,row in enumerate(rows,1):
      if any(v not in (None,'') for v in row):
       rec={f'col_{i+1}':row[i] if i<len(row) else None for i in range(width)};rec['source_row_number']=rn;w.writerow(rec)
    sheets.append({'sheet':ws.title,'rows':ws.max_row,'cols':ws.max_column,'csv':cp.name})
   return {'kind':'xlsx','sheets':sheets}
  except Exception as e:return {'kind':'zip_or_unparsed','error':repr(e)}
 return {'kind':'other'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path);a=ap.parse_args();root=a.output;root.mkdir(parents=True,exist_ok=True)
 page=S.get(PAGE,timeout=120);page.raise_for_status();(root/'source_page.html').write_bytes(page.content);soup=BeautifulSoup(page.content,'html.parser')
 records=[]; targets=[]; errors=[]
 for tid,needles in TARGETS.items():
  matches=[]
  for div in soup.select('div.aip'):
   text=div.get_text(' ',strip=True)
   if any(n.casefold() in text.casefold() for n in needles):matches.append(div)
  if not matches:errors.append({'target':tid,'stage':'match','error':'not found'});continue
  # exact smallest AIP record; deduplicate by text
  uniq={hashlib.sha256(x.get_text(' ',strip=True).encode()).hexdigest():x for x in matches}
  tdir=root/'targets'/tid;tdir.mkdir(parents=True,exist_ok=True)
  for ei,div in enumerate(uniq.values(),1):
   text=div.get_text('\n',strip=True);(tdir/f'entry_{ei}.txt').write_text(text,encoding='utf-8');(tdir/f'entry_{ei}.html').write_text(str(div),encoding='utf-8')
   objects=[]
   for anchor in div.select('a[onclick]'):
    onclick=anchor.get('onclick','');m=re.search(r'DescargarArchivo\("([^"]+)","([sr])"\)',onclick)
    if not m:continue
    aid,typ=m.groups(); label=anchor.get_text(' ',strip=True)
    try:
     r=S.post(DOWNLOAD,data={'archivo':aid,'tipo':typ},timeout=180,allow_redirects=True);r.raise_for_status();data=r.content
     fn=filename(r,len(objects)+1); path=tdir/fn;path.write_bytes(data)
     meta={'target_id':tid,'archivo':aid,'tipo':typ,'label':label,'requested_url':DOWNLOAD,'final_url':r.url,'status':r.status_code,'content_type':r.headers.get('content-type'),'content_disposition':r.headers.get('content-disposition'),'bytes':len(data),'sha256':sha(data),'retrieved_at_utc':now(),'filename':fn}
     meta['inspection']=inspect(path,tdir);records.append(meta);objects.append(meta)
    except Exception as e:errors.append({'target':tid,'archivo':aid,'tipo':typ,'stage':'download','error':repr(e)})
   targets.append({'target_id':tid,'entries':len(uniq),'objects':len(objects),'entry_text_sha256':sha(text.encode())})
 (root/'target_registry.json').write_text(json.dumps(targets,indent=2,ensure_ascii=False),encoding='utf-8');(root/'document_registry.json').write_text(json.dumps(records,indent=2,ensure_ascii=False),encoding='utf-8');(root/'errors.json').write_text(json.dumps(errors,indent=2,ensure_ascii=False),encoding='utf-8')
 status={'targets_expected':len(TARGETS),'targets_matched':len(targets),'objects_acquired':len(records),'pdf_objects':sum(x['inspection']['kind']=='pdf' for x in records),'xlsx_objects':sum(x['inspection']['kind']=='xlsx' for x in records),'embedded_objects':sum(len(x['inspection'].get('embedded',[])) for x in records),'exact_october_2026_weight_vector':'NOT_EXPECTED_FROM_HISTORICAL_ARCHIVE','automatic_publication':False,'generated_at_utc':now()};(root/'acquisition_status.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
 manifest=[]
 for p in sorted(root.rglob('*')):
  if p.is_file() and p.name!='MANIFEST.sha256':manifest.append(f'{sha(p.read_bytes())}  {p.relative_to(root).as_posix()}')
 (root/'MANIFEST.sha256').write_text('\n'.join(manifest)+'\n',encoding='utf-8');print(json.dumps(status,indent=2));return 0 if len(targets)>=7 and len(records)>=7 else 2
if __name__=='__main__':sys.exit(main())
