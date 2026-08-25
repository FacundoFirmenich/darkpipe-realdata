"""Deterministic artifact helpers."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path

def utc_now(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def sha256_bytes(data): return hashlib.sha256(data).hexdigest()
def sha256_file(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda:handle.read(1024*1024),b""): digest.update(block)
    return digest.hexdigest()
def write_bytes(path,data):
    target=Path(path);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    return {"path":target.as_posix(),"byte_count":len(data),"sha256":sha256_bytes(data)}
def write_json(path,value): return write_bytes(path,(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode())
def file_record(path,root=None):
    p=Path(path);label=p.relative_to(root).as_posix() if root else p.as_posix()
    return {"path":label,"byte_count":p.stat().st_size,"sha256":sha256_file(p)}
