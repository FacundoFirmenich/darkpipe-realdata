#!/usr/bin/env python3
"""Build a real, non-gold Argentine public-claim inventory from Chequeado.

This acquisition pass intentionally does not fabricate a balanced gold set. It
archives all Chequeado WordPress posts that match one of six preregistered domains,
records source links and domain gaps, and prepares a blind screening queue. Page
titles are candidate claim strings, not adjudicated atomic claims. ClaimReview
verdicts, when present, remain provenance metadata and are hidden from screeners.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

DOMAINS = {
    "fiscal": ["presupuesto", "déficit", "deficit", "superávit", "superavit", "gasto público", "impuesto", "recaudación", "tesoro", "fiscal", "jubilaciones", "coparticipación"],
    "laboral": ["empleo", "desempleo", "trabajo", "trabajador", "salario", "sueldo", "paritaria", "informalidad", "registrado", "despidos", "ocupación"],
    "social": ["pobreza", "indigencia", "salud", "educación", "vivienda", "alimentación", "niñez", "jubilados", "seguridad social", "universidad", "hospital"],
    "energia": ["energía", "energia", "gas", "electricidad", "tarifa", "petróleo", "petroleo", "vaca muerta", "combustible", "nafta", "enargas", "subsidio energético"],
    "credito_finanzas": ["crédito", "credito", "banco", "bcra", "tasa de interés", "morosidad", "deuda familiar", "financiamiento", "préstamo", "tarjeta", "dólar", "riesgo país"],
    "macro_productivo": ["inflación", "inflacion", "pbi", "pib", "actividad económica", "industria", "producción", "exportación", "importación", "comercio exterior", "crecimiento", "recesión"],
}
TARGET_PER_DOMAIN = 40
USER_AGENT = "IRP27-SOTA009-Inventory/1.8 research"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def clean_text(value: object) -> str:
    return re.sub(
        r"\s+",
        " ",
        BeautifulSoup(html.unescape(str(value or "")), "html.parser").get_text(" ", strip=True),
    ).strip()


def host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().split(":")[0]
    except Exception:
        return ""


def fetch(session: requests.Session, url: str, timeout: int = 180):
    error = None
    for attempt in range(1, 4):
        try:
            response = session.get(url, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            return response.content, {
                "requested_url": url,
                "final_url": response.url,
                "status": response.status_code,
                "content_type": response.headers.get("content-type"),
                "bytes": len(response.content),
                "sha256": sha256(response.content),
                "retrieved_at_utc": now(),
                "attempt": attempt,
                "error": None,
            }
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            time.sleep(attempt * 2)
    return None, {
        "requested_url": url,
        "final_url": None,
        "status": None,
        "content_type": None,
        "bytes": 0,
        "sha256": None,
        "retrieved_at_utc": now(),
        "attempt": 3,
        "error": error,
    }


def classify_domain(text: str):
    folded = text.casefold()
    scores = {
        domain: sum(2 if " " in term else 1 for term in terms if term in folded)
        for domain, terms in DOMAINS.items()
    }
    domain = max(scores, key=scores.get)
    return domain, scores[domain], scores


def external_links(content_html: str, base_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(content_html, "html.parser")
    article_host = host(base_url)
    seen: set[str] = set()
    rows: list[dict[str, str]] = []
    for anchor in soup.find_all("a", href=True):
        url = urljoin(base_url, anchor["href"]).split("#")[0]
        domain = host(url)
        if not url.startswith(("http://", "https://")) or not domain or domain == article_host:
            continue
        if any(blocked in domain for blocked in ("facebook.com", "twitter.com", "x.com", "instagram.com", "whatsapp.com", "youtube.com", "tiktok.com")):
            continue
        if url in seen:
            continue
        seen.add(url)
        rows.append({"url": url, "host": domain, "anchor": clean_text(anchor.get_text(" ", strip=True))[:220]})
    return rows[:12]


def get_posts(session: requests.Session, max_pages: int):
    endpoint = "https://chequeado.com/wp-json/wp/v2/posts"
    posts: list[dict] = []
    metadata: list[dict] = []
    for page in range(1, max_pages + 1):
        url = f"{endpoint}?per_page=100&page={page}&_fields=id,date,link,slug,title,excerpt,content,categories,tags"
        data, meta = fetch(session, url)
        metadata.append(meta)
        if data is None:
            break
        try:
            chunk = json.loads(data)
        except Exception:
            break
        if not isinstance(chunk, list) or not chunk:
            break
        posts.extend(chunk)
        if len(chunk) < 100:
            break
    return posts, metadata


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def make_screening_studio(rows: list[dict], path: Path):
    payload = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    page = f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>IRP-27 Argentine Claim Screening</title><style>body{{font-family:system-ui;margin:0;background:#0f131a;color:#edf2fa}}header{{position:sticky;top:0;background:#171d27;padding:12px;z-index:2}}main{{max-width:1000px;margin:auto;padding:18px}}.card{{background:#171d27;border:1px solid #303a4e;border-radius:12px;padding:16px}}select,textarea,button{{font:inherit;background:#222a38;color:#fff;border:1px solid #4a566f;border-radius:8px;padding:8px}}textarea{{width:100%;min-height:90px}}small{{color:#aab5ca}}a{{color:#9dc1ff}}</style></head><body><header><b>IRP‑27 · Inventario argentino · Cribado ciego</b> <button onclick="exportData()">Exportar</button></header><main id="app"></main><script>const DATA={payload};let i=0;const state={{}};function render(){{const x=DATA[i],k=x.inventory_id,s=state[k]||{{inventory_id:k}};state[k]=s;document.getElementById('app').innerHTML=`<div class=card><small>${{i+1}}/${{DATA.length}} · dominio automático ${{x.domain_auto}} · ${{x.date||''}}</small><h2>${{x.claim_candidate_es}}</h2><p><a target=_blank href="${{x.source_url}}">Abrir fuente</a> · ${{x.external_link_count}} enlaces externos</p><label>Elegibilidad <select onchange="state['${{k}}'].eligibility=this.value"><option></option><option>INCLUDE</option><option>EXCLUDE</option><option>UNCERTAIN</option></select></label><label>Dominio humano <select onchange="state['${{k}}'].domain=this.value"><option></option>${{Object.keys(x.domain_scores).map(d=>`<option>${{d}}</option>`).join('')}}</select></label><label>¿Es claim atómico? <select onchange="state['${{k}}'].atomicity=this.value"><option></option><option>ATOMIC</option><option>COMPOSITE</option><option>NOT_A_CLAIM</option></select></label><label>Claim normalizado<textarea oninput="state['${{k}}'].normalized_claim=this.value"></textarea></label><label>Notas<textarea oninput="state['${{k}}'].notes=this.value"></textarea></label><p><button onclick="i=Math.max(0,i-1);render()">←</button> <button onclick="i=Math.min(DATA.length-1,i+1);render()">→</button></p></div>`}}function exportData(){{const blob=new Blob([JSON.stringify({{schema_version:'1.8',exported_at:new Date().toISOString(),screening:Object.values(state)}},null,2)],{{type:'application/json'}});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='irp27_argentine_inventory_screening.json';a.click()}}render();</script></body></html>'''
    path.write_text(page, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-pages", type=int, default=100)
    args = parser.parse_args()
    root = args.output
    root.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json,text/html,*/*"})
    posts, metadata = get_posts(session, args.max_pages)
    inventory: list[dict] = []
    for post in posts:
        title = clean_text((post.get("title") or {}).get("rendered", ""))
        excerpt = clean_text((post.get("excerpt") or {}).get("rendered", ""))
        content_html = (post.get("content") or {}).get("rendered", "")
        content_text = clean_text(content_html)
        domain, score, scores = classify_domain(" ".join((title, excerpt, content_text[:7000])))
        if score <= 0 or len(title) < 20:
            continue
        links = external_links(content_html, post.get("link", ""))
        inventory.append({
            "inventory_id": f"ARG-INV-{post.get('id')}",
            "claim_candidate_es": title,
            "candidate_status": "TITLE_DERIVED_REAL_PUBLIC_POST_NOT_GOLD",
            "source_url": post.get("link"),
            "date": post.get("date"),
            "domain_auto": domain,
            "domain_score": score,
            "domain_scores": scores,
            "external_link_count": len(links),
            "candidate_links": links,
            "gold_label": None,
            "translation_status": "NOT_GENERATED_BEFORE_INCLUSION",
            "human_screening_required": True,
            "automatic_publication": False,
        })
    distribution = Counter(row["domain_auto"] for row in inventory)
    gaps = {domain: max(0, TARGET_PER_DOMAIN - distribution.get(domain, 0)) for domain in DOMAINS}
    inventory.sort(key=lambda row: (row["domain_auto"], -row["domain_score"], row["inventory_id"]))
    (root / "argentine_real_claim_inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    flat = [{key: value for key, value in row.items() if key not in {"candidate_links", "domain_scores"}} for row in inventory]
    write_csv(root / "argentine_real_claim_inventory.csv", flat)
    queue = [{"domain": domain, "observed": distribution.get(domain, 0), "target": TARGET_PER_DOMAIN, "gap": gap, "status": "ACQUISITION_REQUIRED" if gap else "INVENTORY_TARGET_MET"} for domain, gap in gaps.items()]
    write_csv(root / "acquisition_gap_queue.csv", queue)
    make_screening_studio(inventory, root / "IRP27_ARGENTINE_INVENTORY_SCREENING_STUDIO_v1.8.html")
    status = {
        "gate": "SOTA-009",
        "source": "CHEQUEADO_WORDPRESS_REAL_PUBLIC_POSTS",
        "posts_discovered": len(posts),
        "inventory_candidates": len(inventory),
        "domain_distribution": dict(distribution),
        "target_per_domain": TARGET_PER_DOMAIN,
        "domain_gaps": gaps,
        "balanced_240_gold_completed": False,
        "gold_labels_completed": 0,
        "human_screening_completed": 0,
        "translations_generated": 0,
        "source_titles_are_not_adjudicated_claims": True,
        "automatic_publication": False,
        "generated_at_utc": now(),
    }
    (root / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "api_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
