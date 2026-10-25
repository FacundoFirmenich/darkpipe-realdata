#!/usr/bin/env python3
"""Build the IRP-27 Argentine bilingual evidence-gold annotation pilot.

This pipeline materializes real public sources, extracts 240 Spanish claims
(40 per domain), constructs four real-passage candidates per claim, creates
machine translations explicitly pending human review, and freezes triple-blind
annotation assignments. It never labels candidates as gold evidence and never
uses model preannotations as adjudicated truth.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import random
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import numpy as np
import openpyxl
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DOMAINS = (
    "fiscal",
    "laboral",
    "social",
    "energia",
    "credito_finanzas",
    "macro_productivo",
)
DOMAIN_LABELS = {
    "fiscal": "Fiscal y presupuesto público",
    "laboral": "Trabajo, salarios e informalidad",
    "social": "Pobreza, alimentación, cuidados y condiciones de vida",
    "energia": "Energía y regulación tarifaria",
    "credito_finanzas": "Crédito, deuda y sistema financiero",
    "macro_productivo": "Macroeconomía, producción y sector externo",
}
DOMAIN_KEYWORDS = {
    "fiscal": "presupuesto crédito vigente devengado pagado gasto ingreso superávit déficit resultado financiero primario administración nacional sector público ejecución intereses transferencias".split(),
    "laboral": "empleo desempleo desocupación actividad ocupados asalariados registrados informalidad salario ingreso trabajo empresa contratación trabajadores".split(),
    "social": "pobreza indigencia hogar hogares canasta alimentos crianza niños niñas adolescentes ingresos gastos privación deuda social nutrición cuidados".split(),
    "energia": "tarifa gas cargo fijo variable consumo subsidio bonificación sef usuario distribuidora subzona cuadro energético energía factura".split(),
    "credito_finanzas": "crédito deuda financiamiento mora irregularidad bancos financiero préstamos tarjetas inclusión carga hogares entidades proveedores".split(),
    "macro_productivo": "actividad emae exportaciones importaciones comercio saldo industria producción construcción precios cantidades pib crecimiento maquinaria".split(),
}
MEASURE_TERMS = (
    "tasa porcentaje variación incidencia índice saldo superávit déficit valor monto cantidad precio costo cargo consumo ventas ingreso gasto empleo actividad deuda mora irregularidad facturación".split()
)
GEO_PATTERNS = (
    "argentina",
    "gran buenos aires",
    "gba",
    "31 aglomerados urbanos",
    "administración nacional",
    "sector público nacional",
    "capital federal",
    "buenos aires",
    "patagonia",
    "nea",
    "noa",
    "cuyo",
    "pampeana",
)
POPULATION_PATTERNS = (
    "hogares",
    "personas",
    "trabajadores",
    "usuarios",
    "empresas",
    "niñas",
    "niños",
    "adolescentes",
    "familias",
    "deudores",
    "asalariados",
    "ocupados",
)
DENOMINATOR_PATTERNS = (
    "sobre el total",
    "respecto del total",
    "interanual",
    "mensual",
    "acumulado",
    "por usuario",
    "por hogar",
    "por persona",
    "por ciento",
    "%",
    "puntos porcentuales",
)
NOISE_PATTERNS = (
    "javascript",
    "política de privacidad",
    "mapa del sitio",
    "compartir en",
    "descargar publicación",
    "issn",
    "copyright",
    "página ",
    "page ",
    "www.",
    "http://",
    "https://",
    "fuente:",
    "gráfico ",
    "cuadro ",
)
SEED = 27
RNG = random.Random(SEED)


@dataclass
class Segment:
    source_id: str
    domain: str
    source_role: str
    url: str
    locator: str
    order: int
    text: str
    score: float
    period_hint: str
    geography_hint: str


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize(text: str) -> str:
    text = text.replace("\u00ad", "").replace("\xa0", " ")
    text = re.sub(r"(?<=\w)-\s+(?=\w)", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \t\r\n•·-")


def canonical(text: str) -> str:
    text = normalize(text).lower()
    text = re.sub(r"[^a-záéíóúüñ0-9%$.,]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def sentence_split(text: str) -> list[str]:
    text = normalize(text)
    pieces = re.split(
        r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÜÑ0-9])|\s*[;]\s+(?=[A-ZÁÉÍÓÚÜÑ0-9])",
        text,
    )
    output: list[str] = []
    for piece in pieces:
        piece = normalize(piece)
        if 45 <= len(piece) <= 700:
            output.append(piece)
    return output


def segment_score(text: str, domain: str) -> float:
    folded = canonical(text)
    if not folded or any(pattern in folded for pattern in NOISE_PATTERNS):
        return -100.0
    length = len(text)
    score = 0.0
    if 70 <= length <= 360:
        score += 3.0
    elif 45 <= length <= 550:
        score += 1.0
    else:
        score -= 2.0
    numbers = re.findall(r"\d+(?:[.,]\d+)?%?", text)
    score += min(5, len(numbers)) * 1.8
    score += sum(1.1 for keyword in DOMAIN_KEYWORDS[domain] if keyword in folded)
    score += sum(0.7 for term in MEASURE_TERMS if term in folded)
    if re.search(r"\b(19|20)\d{2}\b", text):
        score += 1.0
    if re.search(r"\b(aument|disminu|cay|sub|alcanz|registr|represent|ubic|inform|establec|define|considera|equivale)", folded):
        score += 1.4
    if len(numbers) == 0 and not any(term in folded for term in ("define", "considera", "se entiende", "corresponde")):
        score -= 1.5
    return score


def fetch(session: requests.Session, source: dict[str, Any], raw_dir: Path) -> tuple[Path | None, dict[str, Any]]:
    extension = source["kind"]
    filename = f"{source['source_id']}.{extension}"
    path = raw_dir / filename
    error = None
    for attempt in range(1, 4):
        try:
            response = session.get(source["url"], timeout=(25, 240), allow_redirects=True)
            response.raise_for_status()
            data = response.content
            path.write_bytes(data)
            return path, {
                **source,
                "requested_url": source["url"],
                "final_url": response.url,
                "status": response.status_code,
                "content_type": response.headers.get("content-type"),
                "bytes": len(data),
                "sha256": sha256_bytes(data),
                "retrieved_at_utc": now(),
                "attempt": attempt,
                "error": None,
            }
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            time.sleep(attempt * 2)
    return None, {
        **source,
        "requested_url": source["url"],
        "final_url": None,
        "status": None,
        "content_type": None,
        "bytes": 0,
        "sha256": None,
        "retrieved_at_utc": now(),
        "attempt": 3,
        "error": error,
    }


def parse_pdf(path: Path, source: dict[str, Any]) -> list[Segment]:
    reader = PdfReader(str(path))
    segments: list[Segment] = []
    order = 0
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        for sentence in sentence_split(text):
            score = segment_score(sentence, source["domain"])
            if score <= 0:
                continue
            segments.append(
                Segment(
                    source["source_id"],
                    source["domain"],
                    source["source_role"],
                    source["url"],
                    f"page:{page_number}",
                    order,
                    sentence,
                    score,
                    source["period_hint"],
                    source["geography_hint"],
                )
            )
            order += 1
    return segments


def parse_html(path: Path, source: dict[str, Any]) -> list[Segment]:
    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "form"]):
        tag.decompose()
    segments: list[Segment] = []
    order = 0
    for element_index, element in enumerate(soup.find_all(["h1", "h2", "h3", "p", "li", "td"]), start=1):
        text = element.get_text(" ", strip=True)
        for sentence in sentence_split(text):
            score = segment_score(sentence, source["domain"])
            if score <= 0:
                continue
            segments.append(
                Segment(
                    source["source_id"],
                    source["domain"],
                    source["source_role"],
                    source["url"],
                    f"html-element:{element_index}",
                    order,
                    sentence,
                    score,
                    source["period_hint"],
                    source["geography_hint"],
                )
            )
            order += 1
    return segments


def parse_xlsx(path: Path, source: dict[str, Any]) -> list[Segment]:
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    segments: list[Segment] = []
    order = 0
    for sheet in workbook.worksheets:
        rows = sheet.iter_rows(values_only=True)
        try:
            headers = [normalize(str(value or f"col_{index+1}")) for index, value in enumerate(next(rows))]
        except StopIteration:
            continue
        for row_number, values in enumerate(rows, start=2):
            if not any(value not in (None, "") for value in values):
                continue
            record = {
                headers[index]: values[index] if index < len(values) else None
                for index in range(len(headers))
            }
            compact = [
                f"{key}={value}"
                for key, value in record.items()
                if value not in (None, "")
            ]
            joined = "; ".join(compact[:10])
            if not re.search(r"R[1234]|Residencial|CARGO|cargo|Tarifa|TARIFA", joined):
                continue
            sentence = (
                f"El registro oficial {source['period_hint']} de {source['source_id']} informa: {joined}."
            )
            score = segment_score(sentence, source["domain"]) + 4.0
            segments.append(
                Segment(
                    source["source_id"],
                    source["domain"],
                    source["source_role"],
                    source["url"],
                    f"sheet:{sheet.title};row:{row_number}",
                    order,
                    sentence,
                    score,
                    source["period_hint"],
                    source["geography_hint"],
                )
            )
            order += 1
            if order >= 120:
                break
    return segments


def parse_source(path: Path, source: dict[str, Any]) -> list[Segment]:
    if source["kind"] == "pdf":
        return parse_pdf(path, source)
    if source["kind"] == "html":
        return parse_html(path, source)
    if source["kind"] == "xlsx":
        return parse_xlsx(path, source)
    raise ValueError(source["kind"])


def select_claim_segments(segments: list[Segment], quota: int = 40) -> list[Segment]:
    by_source: dict[str, list[Segment]] = defaultdict(list)
    for segment in segments:
        by_source[segment.source_id].append(segment)
    for values in by_source.values():
        values.sort(key=lambda segment: (-segment.score, segment.order))

    selected: list[Segment] = []
    seen: set[str] = set()
    source_ids = sorted(by_source)
    round_index = 0
    while len(selected) < quota:
        progressed = False
        for source_id in source_ids:
            candidates = by_source[source_id]
            if round_index >= len(candidates):
                continue
            candidate = candidates[round_index]
            key = canonical(candidate.text)
            if key in seen:
                continue
            seen.add(key)
            selected.append(candidate)
            progressed = True
            if len(selected) >= quota:
                break
        if not progressed:
            break
        round_index += 1
    if len(selected) < quota:
        leftovers = sorted(segments, key=lambda segment: (-segment.score, segment.source_id, segment.order))
        for candidate in leftovers:
            key = canonical(candidate.text)
            if key in seen:
                continue
            seen.add(key)
            selected.append(candidate)
            if len(selected) >= quota:
                break
    if len(selected) < quota:
        raise RuntimeError(f"Only {len(selected)} claims available; required {quota}")
    return selected[:quota]


def facet_hints(text: str, source_role: str, period_hint: str, geography_hint: str) -> dict[str, Any]:
    folded = canonical(text)
    years = sorted(set(re.findall(r"\b(?:19|20)\d{2}\b", text)))
    geographies = [pattern for pattern in GEO_PATTERNS if pattern in folded]
    populations = [pattern for pattern in POPULATION_PATTERNS if pattern in folded]
    denominators = [pattern for pattern in DENOMINATOR_PATTERNS if pattern in folded]
    measures = [term for term in MEASURE_TERMS if term in folded]
    return {
        "entity_candidates": [],
        "time_candidates": years or ([period_hint] if period_hint else []),
        "geography_candidates": geographies or ([geography_hint] if geography_hint else []),
        "population_candidates": populations,
        "denominator_candidates": denominators,
        "measure_candidates": measures,
        "source_role": source_role,
    }


def mismatch_hints(claim: Segment, passage: Segment) -> list[str]:
    output: list[str] = []
    claim_years = set(re.findall(r"\b(?:19|20)\d{2}\b", claim.text))
    passage_years = set(re.findall(r"\b(?:19|20)\d{2}\b", passage.text))
    if claim_years and passage_years and claim_years != passage_years:
        output.append("TIME")
    if claim.geography_hint != passage.geography_hint:
        output.append("GEOGRAPHY")
    claim_measures = set(facet_hints(claim.text, claim.source_role, claim.period_hint, claim.geography_hint)["measure_candidates"])
    passage_measures = set(facet_hints(passage.text, passage.source_role, passage.period_hint, passage.geography_hint)["measure_candidates"])
    if claim_measures and passage_measures and not claim_measures & passage_measures:
        output.append("MEASURE")
    if claim.source_role != passage.source_role:
        output.append("SOURCE_ROLE")
    return output or ["REQUIRES_HUMAN_COMPARISON"]


def translate_texts(texts: list[str], model_name: str, batch_size: int = 16) -> dict[str, str]:
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    model.eval()
    translations: dict[str, str] = {}
    unique = list(dict.fromkeys(texts))
    for start in range(0, len(unique), batch_size):
        batch = unique[start : start + batch_size]
        encoded = tokenizer(
            batch,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,
        )
        with torch.no_grad():
            generated = model.generate(
                **encoded,
                max_new_tokens=512,
                num_beams=4,
            )
        decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)
        translations.update(dict(zip(batch, decoded)))
    return translations


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
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


def annotation_schema() -> dict[str, Any]:
    facet_enum = ["ALIGNED", "MISALIGNED", "UNKNOWN", "NOT_APPLICABLE"]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "IRP-27 Argentine Evidence Pair Annotation",
        "type": "object",
        "required": [
            "assignment_id",
            "annotator_id",
            "item_id",
            "facet_alignment",
            "claim_relation",
            "sufficiency",
            "translation_fidelity",
            "confidence",
        ],
        "properties": {
            "assignment_id": {"type": "string"},
            "annotator_id": {"type": "string"},
            "item_id": {"type": "string"},
            "facet_alignment": {
                "type": "object",
                "required": ["ENTITY", "TIME", "GEOGRAPHY", "POPULATION", "DENOMINATOR", "MEASURE", "SOURCE_ROLE"],
                "properties": {facet: {"enum": facet_enum} for facet in ["ENTITY", "TIME", "GEOGRAPHY", "POPULATION", "DENOMINATOR", "MEASURE", "SOURCE_ROLE"]},
                "additionalProperties": False,
            },
            "claim_relation": {"enum": ["SUPPORT", "REFUTE", "CONTEXT", "INSUFFICIENT", "CANNOT_DETERMINE"]},
            "sufficiency": {"enum": ["WHOLE_CLAIM", "SUBCLAIM_ONLY", "CONTEXT_ONLY", "NONE", "CANNOT_DETERMINE"]},
            "translation_fidelity": {"enum": ["EQUIVALENT", "MINOR_ISSUE", "MATERIAL_MISMATCH", "NOT_REVIEWED"]},
            "source_role": {"type": "string"},
            "evidence_span": {"type": "string"},
            "defeater_type": {"enum": ["NONE", "REBUTTAL", "UNDERCUTTER", "CONTEXT", "MEASUREMENT", "TRANSPORT", "AUTHORITY", "REVISION", "UNKNOWN"]},
            "confidence": {"type": "integer", "minimum": 1, "maximum": 5},
            "notes": {"type": "string"},
            "started_at": {"type": "string"},
            "completed_at": {"type": "string"},
        },
        "additionalProperties": False,
    }


def make_studio(pilot_items: list[dict[str, Any]], pilot_assignments: list[dict[str, Any]]) -> str:
    data = json.dumps({"items": pilot_items, "assignments": pilot_assignments}, ensure_ascii=False)
    return f"""<!doctype html>
<html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>IRP‑27 Argentine Bilingual Evidence Annotation Studio</title>
<style>
:root{{--bg:#0b1020;--panel:#151c31;--ink:#eef2ff;--muted:#aab4d0;--line:#2e3855;--accent:#8fb7ff}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font-family:system-ui,sans-serif}}
header{{position:sticky;top:0;background:#0b1020ee;border-bottom:1px solid var(--line);padding:14px;z-index:2}}
main{{max-width:1200px;margin:auto;padding:20px}} .grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px;margin-bottom:14px}}
label{{display:block;color:var(--muted);font-size:.84rem;margin:8px 0 4px}} select,textarea,input,button{{width:100%;padding:10px;border-radius:9px;border:1px solid var(--line);background:#0f1628;color:var(--ink)}}
button{{cursor:pointer;background:#24457c}} .claim{{font-size:1.08rem;line-height:1.45}} .en{{color:#b8d0ff}} .meta{{font-size:.82rem;color:var(--muted)}} .facets{{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}} pre{{white-space:pre-wrap}} @media(max-width:760px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body>
<header><strong>IRP‑27 · Gate SOTA‑009 · Pilot Tranche 60</strong><div class='meta'>Anotación ciega. Ninguna sugerencia automática constituye gold.</div></header>
<main>
<div class='card grid'><div><label>Annotator ID</label><select id='annotator'></select></div><div><label>Progreso</label><div id='progress'></div><button id='export'>Exportar JSON</button></div></div>
<div id='workspace'></div>
</main>
<script>
const DB={data}; const FACETS=['ENTITY','TIME','GEOGRAPHY','POPULATION','DENOMINATOR','MEASURE','SOURCE_ROLE'];
const states=['ALIGNED','MISALIGNED','UNKNOWN','NOT_APPLICABLE']; let current=0; let assigned=[]; let responses=JSON.parse(localStorage.getItem('irp27_sota009_responses')||'{{}}');
const annotators=[...new Set(DB.assignments.map(x=>x.annotator_id))]; const sel=document.getElementById('annotator'); annotators.forEach(a=>sel.add(new Option(a,a)));
function save(){{localStorage.setItem('irp27_sota009_responses',JSON.stringify(responses));}}
function render(){{const aid=sel.value; assigned=DB.assignments.filter(x=>x.annotator_id===aid); if(current>=assigned.length)current=0; const a=assigned[current]; if(!a){{workspace.innerHTML='<div class=card>Sin asignaciones.</div>';return}} const item=DB.items.find(x=>x.item_id===a.item_id); const r=responses[a.assignment_id]||{{facet_alignment:{{}},claim_relation:'',sufficiency:'',translation_fidelity:'NOT_REVIEWED',source_role:item.passage_source_role,defeater_type:'NONE',confidence:3,notes:'',started_at:new Date().toISOString()}};
let facetHtml=FACETS.map(f=>`<div><label>${{f}}</label><select data-facet='${{f}}'>${{states.map(s=>`<option ${{r.facet_alignment[f]===s?'selected':''}}>${{s}}</option>`).join('')}}</select></div>`).join('');
workspace.innerHTML=`<div class='card'><div class=meta>${{item.item_id}} · ${{item.domain_label}} · ${{item.candidate_role_hint}}</div><h3>Claim ES</h3><div class=claim>${{esc(item.claim_es)}}</div><h3>Claim EN · traducción automática pendiente de revisión</h3><div class='claim en'>${{esc(item.claim_en)}}</div></div><div class='card grid'><div><h3>Pasaje candidato ES</h3><div class=claim>${{esc(item.passage_es)}}</div></div><div><h3>Candidate passage EN</h3><div class='claim en'>${{esc(item.passage_en)}}</div></div><div class=meta>Fuente: ${{esc(item.passage_source_id)}} · ${{esc(item.passage_locator)}}<br>URL: ${{esc(item.passage_url)}}</div></div><div class=card><h3>Alineación facetada</h3><div class=facets>${{facetHtml}}</div><div class=grid><div><label>Relación</label><select id=relation>${{['','SUPPORT','REFUTE','CONTEXT','INSUFFICIENT','CANNOT_DETERMINE'].map(x=>`<option ${{r.claim_relation===x?'selected':''}}>${{x}}</option>`).join('')}}</select></div><div><label>Suficiencia</label><select id=suff>${{['','WHOLE_CLAIM','SUBCLAIM_ONLY','CONTEXT_ONLY','NONE','CANNOT_DETERMINE'].map(x=>`<option ${{r.sufficiency===x?'selected':''}}>${{x}}</option>`).join('')}}</select></div><div><label>Fidelidad traducción</label><select id=translation>${{['EQUIVALENT','MINOR_ISSUE','MATERIAL_MISMATCH','NOT_REVIEWED'].map(x=>`<option ${{r.translation_fidelity===x?'selected':''}}>${{x}}</option>`).join('')}}</select></div><div><label>Defeater</label><select id=defeater>${{['NONE','REBUTTAL','UNDERCUTTER','CONTEXT','MEASUREMENT','TRANSPORT','AUTHORITY','REVISION','UNKNOWN'].map(x=>`<option ${{r.defeater_type===x?'selected':''}}>${{x}}</option>`).join('')}}</select></div><div><label>Confianza 1–5</label><input id=confidence type=number min=1 max=5 value='${{r.confidence}}'></div></div><label>Span y notas</label><textarea id=notes rows=4>${{esc(r.notes||'')}}</textarea><div class=grid><button id=prev>Anterior</button><button id=next>Guardar y siguiente</button></div></div>`;
document.getElementById('progress').textContent=`${{current+1}} / ${{assigned.length}} · guardadas ${{assigned.filter(x=>responses[x.assignment_id]).length}}`;
document.getElementById('prev').onclick=()=>{{capture(a,item,r);current=Math.max(0,current-1);render()}}; document.getElementById('next').onclick=()=>{{capture(a,item,r);current=Math.min(assigned.length-1,current+1);render()}};}}
function capture(a,item,r){{document.querySelectorAll('[data-facet]').forEach(x=>r.facet_alignment[x.dataset.facet]=x.value);r.claim_relation=document.getElementById('relation').value;r.sufficiency=document.getElementById('suff').value;r.translation_fidelity=document.getElementById('translation').value;r.defeater_type=document.getElementById('defeater').value;r.confidence=+document.getElementById('confidence').value;r.notes=document.getElementById('notes').value;r.assignment_id=a.assignment_id;r.annotator_id=a.annotator_id;r.item_id=a.item_id;r.completed_at=new Date().toISOString();responses[a.assignment_id]=r;save();}}
function esc(x){{return String(x??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]))}}
sel.onchange=()=>{{current=0;render()}}; document.getElementById('export').onclick=()=>{{const aid=sel.value;const rows=DB.assignments.filter(x=>x.annotator_id===aid).map(x=>responses[x.assignment_id]).filter(Boolean);const blob=new Blob([JSON.stringify({{annotator_id:aid,responses:rows,exported_at:new Date().toISOString()}},null,2)],{{type:'application/json'}});const u=URL.createObjectURL(blob);const a=document.createElement('a');a.href=u;a.download=`IRP27_SOTA009_${{aid}}.json`;a.click();URL.revokeObjectURL(u)}}; render();
</script></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--translation-model", default="Helsinki-NLP/opus-mt-es-en")
    args = parser.parse_args()
    root = args.output
    for directory in ("raw", "data", "protocols", "study", "reports"):
        (root / directory).mkdir(parents=True, exist_ok=True)

    sources = json.loads(args.registry.read_text(encoding="utf-8"))
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "IRP27-SOTA009/1.8 public-research-corpus",
            "Accept": "text/html,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
        }
    )
    source_records: list[dict[str, Any]] = []
    all_segments: list[Segment] = []
    errors: list[dict[str, Any]] = []
    for source in sources:
        path, metadata = fetch(session, source, root / "raw")
        source_records.append(metadata)
        if path is None:
            errors.append({"source_id": source["source_id"], "stage": "fetch", "error": metadata["error"]})
            continue
        try:
            segments = parse_source(path, source)
            metadata["segments"] = len(segments)
            all_segments.extend(segments)
        except Exception as exc:
            errors.append({"source_id": source["source_id"], "stage": "parse", "error": f"{type(exc).__name__}: {exc}"})

    claims: list[dict[str, Any]] = []
    selected_segments: list[Segment] = []
    for domain in DOMAINS:
        domain_segments = [segment for segment in all_segments if segment.domain == domain]
        selected = select_claim_segments(domain_segments, 40)
        selected_segments.extend(selected)
        for index, segment in enumerate(selected, start=1):
            claim_id = f"ARG-{domain.upper().replace('_','-')}-{index:03d}"
            claims.append(
                {
                    "claim_id": claim_id,
                    "domain": domain,
                    "domain_label": DOMAIN_LABELS[domain],
                    "claim_es": segment.text,
                    "claim_en": "",
                    "translation_status": "MODEL_TRANSLATION_PENDING_HUMAN_REVIEW",
                    "source_id": segment.source_id,
                    "source_role": segment.source_role,
                    "source_url": segment.url,
                    "source_locator": segment.locator,
                    "source_order": segment.order,
                    "source_period_hint": segment.period_hint,
                    "source_geography_hint": segment.geography_hint,
                    "source_span_sha256": sha256_bytes(segment.text.encode("utf-8")),
                    "facet_hints": facet_hints(segment.text, segment.source_role, segment.period_hint, segment.geography_hint),
                    "gold_status": "UNANNOTATED",
                    "human_annotations": 0,
                    "automatic_evidence_promotion": False,
                }
            )

    by_claim_id = {claim["claim_id"]: claim for claim in claims}
    segment_by_claim_id = {claim["claim_id"]: segment for claim, segment in zip(claims, selected_segments)}
    segment_index_by_source: dict[str, list[Segment]] = defaultdict(list)
    for segment in all_segments:
        segment_index_by_source[segment.source_id].append(segment)
    for values in segment_index_by_source.values():
        values.sort(key=lambda segment: segment.order)

    candidate_pairs: list[dict[str, Any]] = []
    for domain in DOMAINS:
        domain_claims = [claim for claim in claims if claim["domain"] == domain]
        texts = [claim["claim_es"] for claim in domain_claims]
        matrix = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True).fit_transform(texts)
        similarities = cosine_similarity(matrix)
        for row_index, claim in enumerate(domain_claims):
            claim_segment = segment_by_claim_id[claim["claim_id"]]
            source_segments = segment_index_by_source[claim_segment.source_id]
            context_candidates = [segment for segment in source_segments if segment.order != claim_segment.order]
            context_candidates.sort(key=lambda segment: abs(segment.order - claim_segment.order))
            context = context_candidates[0] if context_candidates else claim_segment
            neighbor_indices = [index for index in np.argsort(similarities[row_index])[::-1] if index != row_index]
            real_neighbors = [domain_claims[index] for index in neighbor_indices if domain_claims[index]["source_id"] != claim["source_id"]]
            while len(real_neighbors) < 2:
                real_neighbors.append(domain_claims[neighbor_indices[len(real_neighbors)]])
            passages = [
                ("PRIMARY_SOURCE_ANCHOR_NOT_YET_GOLD", claim_segment),
                ("SAME_SOURCE_CONTEXT_CANDIDATE", context),
                ("HARD_NEAR_MISS_CANDIDATE", segment_by_claim_id[real_neighbors[0]["claim_id"]]),
                ("CONTRAST_OR_DEFEATER_CANDIDATE", segment_by_claim_id[real_neighbors[1]["claim_id"]]),
            ]
            for candidate_index, (role_hint, passage) in enumerate(passages, start=1):
                item_id = f"PAIR-{claim['claim_id']}-{candidate_index}"
                candidate_pairs.append(
                    {
                        "item_id": item_id,
                        "claim_id": claim["claim_id"],
                        "domain": domain,
                        "domain_label": DOMAIN_LABELS[domain],
                        "claim_es": claim["claim_es"],
                        "claim_en": "",
                        "claim_source_id": claim["source_id"],
                        "claim_source_role": claim["source_role"],
                        "claim_url": claim["source_url"],
                        "claim_locator": claim["source_locator"],
                        "passage_es": passage.text,
                        "passage_en": "",
                        "passage_source_id": passage.source_id,
                        "passage_source_role": passage.source_role,
                        "passage_url": passage.url,
                        "passage_locator": passage.locator,
                        "candidate_role_hint": role_hint,
                        "mismatch_hints": mismatch_hints(claim_segment, passage),
                        "gold_relation": None,
                        "gold_facet_alignment": None,
                        "gold_sufficiency": None,
                        "annotation_status": "PENDING_TRIPLE_BLIND_ANNOTATION",
                        "automatic_evidence_promotion": False,
                    }
                )

    translation_texts = [claim["claim_es"] for claim in claims] + [pair["passage_es"] for pair in candidate_pairs]
    translations = translate_texts(translation_texts, args.translation_model)
    for claim in claims:
        claim["claim_en"] = translations[claim["claim_es"]]
    for pair in candidate_pairs:
        pair["claim_en"] = by_claim_id[pair["claim_id"]]["claim_en"]
        pair["passage_en"] = translations[pair["passage_es"]]
        pair["translation_status"] = "MODEL_TRANSLATION_PENDING_HUMAN_REVIEW"

    annotators = [f"A{index:02d}" for index in range(1, 13)]
    assignments: list[dict[str, Any]] = []
    for item_index, item in enumerate(candidate_pairs):
        for replica in range(3):
            annotator = annotators[(item_index * 3 + replica) % len(annotators)]
            assignments.append(
                {
                    "assignment_id": f"ASG-{item['item_id']}-{annotator}",
                    "annotator_id": annotator,
                    "item_id": item["item_id"],
                    "claim_id": item["claim_id"],
                    "domain": item["domain"],
                    "replica": replica + 1,
                    "status": "UNASSIGNED_TO_HUMAN",
                }
            )

    pilot_claim_ids: set[str] = set()
    for domain in DOMAINS:
        pilot_claim_ids.update(claim["claim_id"] for claim in [row for row in claims if row["domain"] == domain][:10])
    pilot_items = [item for item in candidate_pairs if item["claim_id"] in pilot_claim_ids]
    pilot_item_ids = {item["item_id"] for item in pilot_items}
    pilot_assignments = [assignment for assignment in assignments if assignment["item_id"] in pilot_item_ids]
    for assignment in assignments:
        assignment["tranche"] = "PILOT_60" if assignment["item_id"] in pilot_item_ids else "FULL_240"

    source_records_path = root / "data" / "source_registry_materialized.json"
    source_records_path.write_text(json.dumps(source_records, ensure_ascii=False, indent=2), encoding="utf-8")
    write_jsonl(root / "data" / "claims_240.jsonl", claims)
    write_jsonl(root / "data" / "candidate_pairs_960.jsonl", candidate_pairs)
    write_csv(root / "data" / "assignments_2880.csv", assignments)
    write_jsonl(root / "data" / "pilot_claims_60.jsonl", [claim for claim in claims if claim["claim_id"] in pilot_claim_ids])
    write_jsonl(root / "data" / "pilot_pairs_240.jsonl", pilot_items)
    write_csv(root / "data" / "pilot_assignments_720.csv", pilot_assignments)
    write_csv(root / "data" / "adjudication_ledger.csv", [{"item_id": item["item_id"], "adjudication_status": "NOT_STARTED", "final_relation": "", "final_sufficiency": "", "adjudicator": "", "notes": ""} for item in candidate_pairs])
    (root / "protocols" / "annotation.schema.json").write_text(json.dumps(annotation_schema(), ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "study" / "IRP27_ARGENTINE_EVIDENCE_ANNOTATION_STUDIO_v1.8.html").write_text(make_studio(pilot_items, pilot_assignments), encoding="utf-8")

    manual = f"""# Manual de anotación — IRP-27 Gate SOTA-009 v1.8

## Unidad
Cada ítem contiene un claim público real y un pasaje candidato real. El hecho de que el pasaje provenga de la misma fuente no lo convierte automáticamente en evidencia suficiente.

## Facetas
Anotar por separado ENTITY, TIME, GEOGRAPHY, POPULATION, DENOMINATOR, MEASURE y SOURCE_ROLE como ALIGNED, MISALIGNED, UNKNOWN o NOT_APPLICABLE.

## Relación
- SUPPORT: el pasaje incrementa directamente la justificación del claim con alcance compatible.
- REFUTE: el pasaje contradice materialmente el claim.
- CONTEXT: es auténtico y relevante, pero no prueba ni refuta.
- INSUFFICIENT: no permite decidir la relación.
- CANNOT_DETERMINE: el anotador carece de base suficiente.

## Suficiencia
WHOLE_CLAIM, SUBCLAIM_ONLY, CONTEXT_ONLY, NONE o CANNOT_DETERMINE.

## Traducción
La traducción inglesa es automática y siempre requiere revisión humana. No corregir silenciosamente: marcar EQUIVALENT, MINOR_ISSUE o MATERIAL_MISMATCH.

## Independencia
Tres anotaciones se realizan de forma independiente. La adjudicación ocurre después y conserva todos los desacuerdos.

## Prohibiciones
No usar el hint del candidato como gold. No inferir intención política. No convertir similitud temática en soporte. No promover evidencia automáticamente.
"""
    (root / "protocols" / "ANNOTATION_MANUAL_v1.8.md").write_text(manual, encoding="utf-8")

    data_statement = f"""# Data Statement — Argentine Bilingual Evidence Gold Pilot v1.8

- 240 claims públicos reales, 40 por dominio.
- 960 pares claim–pasaje, cuatro candidatos reales por claim.
- 2.880 asignaciones, tres anotadores independientes por par.
- Español es la lengua fuente.
- Traducción inglesa: `{args.translation_model}`, pendiente de revisión humana.
- Fuentes: estadísticas oficiales, regulación, auditoría, presupuesto, encuestas institucionales y observatorios universitarios/internacionales.
- No contiene datos personales ni perfiles de votantes.
- El corpus no es gold hasta completar triple anotación y adjudicación.
- Los near-misses son pasajes reales; no se declaran falsos por construcción.
- Automatic evidence promotion: FALSE.
- Automatic publication: FALSE.
"""
    (root / "protocols" / "DATA_STATEMENT_v1.8.md").write_text(data_statement, encoding="utf-8")

    curriculum = {
        "gate": "IRP27-GATE-IN-DOMAIN-COMPETENCE-CURRICULUM-AND-ARGENTINE-BILINGUAL-EVIDENCE-GOLD-009",
        "stages": [
            {"stage": 0, "name": "SOURCE_ANCHOR_RECOGNITION", "authority": "PRETEXT_ONLY"},
            {"stage": 1, "name": "FACET_ALIGNMENT", "facets": ["ENTITY", "TIME", "GEOGRAPHY", "POPULATION", "DENOMINATOR", "MEASURE", "SOURCE_ROLE"]},
            {"stage": 2, "name": "PAIR_RELATION", "labels": ["SUPPORT", "REFUTE", "CONTEXT", "INSUFFICIENT"]},
            {"stage": 3, "name": "SET_LEVEL_SUFFICIENCY_AND_CONFLICT", "requires_adjudicated_gold": True},
            {"stage": 4, "name": "LEAVE_ONE_DOMAIN_OUT", "blocked_until_in_domain_gate": True},
            {"stage": 5, "name": "BILINGUAL_TRANSFER", "blocked_until_translation_review": True},
            {"stage": 6, "name": "OPEN_WEB", "blocked": True},
        ],
        "promotion_thresholds": {
            "support_precision_lcb95": 0.95,
            "refute_precision_lcb95": 0.95,
            "support_coverage": 0.05,
            "refute_coverage": 0.05,
            "swap_acceptance": 0.005,
            "unsafe_conflict_commits": 0,
            "class_conditional_conformal_coverage": 0.90,
        },
        "automatic_evidence_promotion": False,
        "automatic_publication": False,
    }
    (root / "protocols" / "CURRICULUM_MANIFEST_v1.8.json").write_text(json.dumps(curriculum, indent=2), encoding="utf-8")

    domain_counts = Counter(claim["domain"] for claim in claims)
    source_domain_counts = Counter(record["domain"] for record in source_records if record.get("bytes", 0) > 0)
    assignment_counts = Counter(assignment["annotator_id"] for assignment in assignments)
    qa = {
        "claims": len(claims),
        "domain_counts": dict(domain_counts),
        "pairs": len(candidate_pairs),
        "assignments": len(assignments),
        "pilot_claims": len(pilot_claim_ids),
        "pilot_pairs": len(pilot_items),
        "pilot_assignments": len(pilot_assignments),
        "sources_expected": len(sources),
        "sources_acquired": sum(record.get("bytes", 0) > 0 for record in source_records),
        "source_counts_by_domain": dict(source_domain_counts),
        "assignment_counts": dict(assignment_counts),
        "translation_model": args.translation_model,
        "translation_status": "MODEL_TRANSLATION_PENDING_HUMAN_REVIEW",
        "human_annotations_collected": 0,
        "adjudicated_items": 0,
        "gold_status": "NOT_YET_GOLD",
        "automatic_evidence_promotion": False,
        "automatic_publication": False,
        "errors": errors,
    }
    if len(claims) != 240 or any(domain_counts[domain] != 40 for domain in DOMAINS):
        raise RuntimeError(qa)
    if len(candidate_pairs) != 960 or len(assignments) != 2880:
        raise RuntimeError(qa)
    if len(pilot_claim_ids) != 60 or len(pilot_items) != 240 or len(pilot_assignments) != 720:
        raise RuntimeError(qa)
    if min(assignment_counts.values()) != max(assignment_counts.values()):
        raise RuntimeError({"unbalanced_assignments": dict(assignment_counts)})
    (root / "reports" / "QA_REPORT.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "reports" / "ERRORS.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "MANIFEST.sha256":
            manifest.append(f"{sha256_file(path)}  {path.relative_to(root).as_posix()}")
    (root / "MANIFEST.sha256").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    print(json.dumps(qa, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
