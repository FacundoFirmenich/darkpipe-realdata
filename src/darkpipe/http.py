"""Bounded HTTP acquisition with retries and byte provenance."""
from dataclasses import dataclass
from datetime import datetime,timezone
import hashlib,json
from typing import Any,Mapping
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

@dataclass(frozen=True)
class FetchArtifact:
    url:str; retrieved_at_utc:str; status_code:int; content_type:str; sha256:str; byte_count:int; payload:Any; content:bytes
    def provenance(self): return {k:getattr(self,k) for k in ("url","retrieved_at_utc","status_code","content_type","sha256","byte_count")}

def _session():
    retry=Retry(total=4,connect=4,read=4,backoff_factor=.6,status_forcelist=(429,500,502,503,504),allowed_methods=frozenset({"GET"}),respect_retry_after_header=True)
    session=requests.Session();session.headers["User-Agent"]="DarkPipe/0.3.0 (+https://github.com/FacundoFirmenich/darkpipe-realdata)"
    session.mount("https://",HTTPAdapter(max_retries=retry));return session

def fetch_json(url:str,*,params:Mapping[str,Any]|None=None,timeout_seconds:float=45,max_bytes:int=10_000_000)->FetchArtifact:
    with _session() as session:
        with session.get(url,params=params,timeout=timeout_seconds,stream=True) as response:
            response.raise_for_status();chunks=[];size=0
            for chunk in response.iter_content(65536):
                if not chunk: continue
                size+=len(chunk)
                if size>max_bytes: raise ValueError(f"response exceeded max_bytes={max_bytes}: {response.url}")
                chunks.append(chunk)
            content=b"".join(chunks);final_url=response.url;status=response.status_code;ctype=response.headers.get("Content-Type","")
    try: payload=json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError,json.JSONDecodeError) as exc: raise ValueError(f"invalid JSON from {final_url}") from exc
    return FetchArtifact(final_url,datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),status,ctype,hashlib.sha256(content).hexdigest(),len(content),payload,content)
