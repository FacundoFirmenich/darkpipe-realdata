#!/usr/bin/env python3
from pathlib import Path
import requests

urls=[
 'https://www.enargas.gob.ar/secciones/transparencia/includes/funciones.js',
 'https://www.enargas.gob.ar/secciones/transparencia/includes/funciones.php',
 'https://www.enargas.gob.ar/secciones/transparencia/funciones.js',
]
out=Path(__import__('sys').argv[1]); out.mkdir(parents=True,exist_ok=True)
s=requests.Session(); s.headers['User-Agent']='IRP27-Gate012/2.0'
for i,url in enumerate(urls):
 try:
  r=s.get(url,timeout=60,allow_redirects=True)
  (out/f'response_{i}_{r.status_code}.txt').write_bytes(r.content)
  print(url,r.status_code,r.url,r.headers.get('content-type'),len(r.content))
 except Exception as e:
  (out/f'error_{i}.txt').write_text(repr(e))
  print(url,'ERROR',repr(e))
