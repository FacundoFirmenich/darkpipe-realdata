#!/usr/bin/env python3
"""Gate SOTA-012 calibration registry v2.3.

This compatibility layer strengthens cell identity by adding `question_id`.
Two estimands that share a primitive—such as `supports` and `refutes`, both
Noul—must never share calibration statistics merely because their primitive is
identical. The underlying metrics and authority boundaries remain unchanged.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

import calibration_registry as core


def calibration_key(*, contract_hash: str, provider: str, provider_version: str, checkpoint: str, question_id: str, primitive: str, domain: str, language: str, hardware: str, data_vintage: str, evaluation_mode: str) -> dict[str, str]:
    return {
        "contract_hash": contract_hash,
        "provider": provider,
        "provider_version": provider_version,
        "checkpoint": checkpoint,
        "question_id": question_id,
        "primitive": primitive,
        "domain": domain,
        "language": language,
        "hardware": hardware,
        "data_vintage": data_vintage,
        "evaluation_mode": evaluation_mode,
    }


def external_records(cases: Sequence[Mapping[str, Any]], outputs: Sequence[Mapping[str, Any]], *, provider: str, provider_version: str, contract_hash: str, data_vintage: str, hardware: str, evaluation_mode: str = "EXTERNAL_PUBLISHED_RAW_REANALYSIS") -> list[dict[str, Any]]:
    by_id = {row["id"]: row for row in outputs}
    records: list[dict[str, Any]] = []
    for case in cases:
        output = by_id.get(case["id"])
        if not output or not output.get("ok"):
            continue
        for question_id, question in case["questions"].items():
            if question_id not in case.get("gold", {}):
                continue
            answer = (output.get("answers") or {}).get(question_id)
            if not answer:
                continue
            labels, distribution, prediction = core.answer_distribution(answer, question)
            gold = core.gold_label(case["gold"][question_id])
            p_gold = max(core.EPS, float(distribution.get(gold, 0.0)))
            confidence = max(distribution.values())
            correct = int(str(prediction).lower() == str(case["gold"][question_id]).lower())
            one_hot = np.asarray([1.0 if label == gold else 0.0 for label in labels])
            probabilities = np.asarray([distribution[label] for label in labels])
            key = calibration_key(
                contract_hash=contract_hash,
                provider=provider,
                provider_version=provider_version,
                checkpoint=str(output.get("model") or "unknown"),
                question_id=question_id,
                primitive=question["type"],
                domain=str(case.get("track") or case.get("dataset") or "unknown"),
                language=str(case.get("lang") or "unknown"),
                hardware=hardware,
                data_vintage=data_vintage,
                evaluation_mode=evaluation_mode,
            )
            records.append({
                "key": key,
                "case_id": case["id"],
                "question_id": question_id,
                "dataset": case.get("dataset"),
                "gold": case["gold"][question_id],
                "prediction": prediction,
                "distribution": distribution,
                "confidence": confidence,
                "correct": correct,
                "log_loss": -math.log(p_gold),
                "brier": float(np.sum((probabilities - one_hot) ** 2)),
                "latency_ms": float(output.get("ms") or 0.0),
                "label_confidence": case.get("label_confidence"),
            })
    return records


def bilingual_cells(outputs: Sequence[Mapping[str, Any]], pair_metadata: Mapping[str, Mapping[str, Any]], *, contract_hash: str, provider_version: str, hardware: str, data_vintage: str) -> list[dict[str, Any]]:
    by_pair: dict[tuple[str, str, str], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in outputs:
        if row.get("ok"):
            by_pair[(row["checkpoint"], row["item_id"], row["question_id"])][row["language"]] = row
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for (checkpoint, item_id, question_id), languages in by_pair.items():
        if "es" not in languages or "en" not in languages:
            continue
        es = languages["es"]
        en = languages["en"]
        meta = pair_metadata[item_id]
        primitive = es["primitive"]
        drift = (
            abs(float(es["distribution"]["true"]) - float(en["distribution"]["true"]))
            if primitive == "noul"
            else core.js_divergence(es["distribution"], en["distribution"])
        )
        grouped[(checkpoint, question_id, primitive, meta["domain"])].append({
            "agreement": int(str(es["prediction"]) == str(en["prediction"])),
            "distribution_drift": drift,
            "es_confidence": max(es["distribution"].values()),
            "en_confidence": max(en["distribution"].values()),
            "latency_es": float(es.get("latency_ms") or 0.0),
            "latency_en": float(en.get("latency_ms") or 0.0),
        })
    cells: list[dict[str, Any]] = []
    for (checkpoint, question_id, primitive, domain), rows in sorted(grouped.items()):
        key = calibration_key(
            contract_hash=contract_hash,
            provider="laya",
            provider_version=provider_version,
            checkpoint=checkpoint,
            question_id=question_id,
            primitive=primitive,
            domain=domain,
            language="es-en-paired",
            hardware=hardware,
            data_vintage=data_vintage,
            evaluation_mode="BILINGUAL_SHADOW_INVARIANCE_ONLY",
        )
        cells.append({
            "calibration_id": core.key_id(key),
            "key": key,
            "n": len(rows),
            "gold_status": "ARGENTINE_GOLD_NOT_FROZEN",
            "metrics": {
                "bilingual_prediction_agreement": core.statistics.fmean(row["agreement"] for row in rows),
                "mean_distribution_drift": core.statistics.fmean(row["distribution_drift"] for row in rows),
                "p95_distribution_drift": float(np.quantile([row["distribution_drift"] for row in rows], 0.95)),
                "mean_confidence_es": core.statistics.fmean(row["es_confidence"] for row in rows),
                "mean_confidence_en": core.statistics.fmean(row["en_confidence"] for row in rows),
                "latency_ms_mean_es": core.statistics.fmean(row["latency_es"] for row in rows),
                "latency_ms_mean_en": core.statistics.fmean(row["latency_en"] for row in rows),
                "accuracy": None,
                "log_loss": None,
                "brier": None,
                "ece_10": None,
            },
            "validity": "INVARIANCE_ONLY_NO_GOLD",
            "promotion_status": "BLOCKED",
            "blockers": [
                "GOLD_NOT_FROZEN",
                "TRANSLATION_NOT_HUMAN_REVIEWED",
                "HUMAN_ANNOTATIONS_INCOMPLETE",
                "NO_ACCURACY_OR_CALIBRATION_AUTHORITY",
                "NO_EXTERNAL_REPLICATION",
            ],
            "automatic_execution": False,
            "automatic_publication": False,
        })
    return cells


# Patch core functions that build_registry resolves through module globals.
core.calibration_key = calibration_key
core.external_records = external_records
core.bilingual_cells = bilingual_cells


def build_registry(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    cases = core.read_jsonl(args.cases)
    flip_cases = core.read_jsonl(args.flip_cases)
    benchmark_contract_hash = hashlib.sha256(args.cases.read_bytes()).hexdigest()
    all_base_records: list[dict[str, Any]] = []
    all_flip_records: list[dict[str, Any]] = []
    records_by_provider: dict[str, list[dict[str, Any]]] = {}
    for provider, version, base_path, flip_path in zip(args.providers, args.provider_versions, args.base_outputs, args.flip_outputs):
        base = external_records(cases, core.read_jsonl(base_path), provider=provider, provider_version=version, contract_hash=benchmark_contract_hash, data_vintage=args.external_vintage, hardware="external_unknown")
        flip = external_records(flip_cases, core.read_jsonl(flip_path), provider=provider, provider_version=version, contract_hash=benchmark_contract_hash, data_vintage=args.external_vintage, hardware="external_unknown")
        records_by_provider[provider] = base
        all_base_records.extend(base)
        all_flip_records.extend(flip)
    cells = core.aggregate_cells(all_base_records)
    core.attach_flip_stability(cells, all_base_records, all_flip_records)
    bilingual_status: dict[str, Any] = {"available": False, "reason": "NO_OUTPUT_FILE"}
    if args.bilingual_outputs and args.bilingual_outputs.exists() and args.bilingual_outputs.stat().st_size:
        outputs = core.read_jsonl(args.bilingual_outputs)
        pairs = {row["item_id"]: row for row in core.read_jsonl(args.bilingual_pairs)}
        current_contract = json.loads(args.contract.read_text())
        current_hash = core.sha256_value(current_contract)
        bilingual = bilingual_cells(outputs, pairs, contract_hash=current_hash, provider_version=args.laya_version, hardware=args.live_hardware, data_vintage=args.argentine_vintage)
        cells.extend(bilingual)
        bilingual_status = {"available": True, "records": len(outputs), "cells": len(bilingual)}
    errors = core.validate_no_cross_cell_transport(cells)
    receipts = core.receipt_chain(cells)
    disagreement = core.disagreement_summary(records_by_provider)
    core.write_jsonl(output / "calibration_registry.jsonl", cells)
    core.write_jsonl(output / "calibration_receipts.jsonl", receipts)
    fields = ["calibration_id", "contract_hash", "provider", "provider_version", "checkpoint", "question_id", "primitive", "domain", "language", "hardware", "data_vintage", "evaluation_mode", "n", "gold_status", "validity", "promotion_status", "accuracy", "log_loss", "brier", "ece_10", "bilingual_prediction_agreement", "mean_distribution_drift", "blockers"]
    with (output / "calibration_matrix.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for cell in cells:
            metrics = cell["metrics"]
            writer.writerow({
                "calibration_id": cell["calibration_id"],
                **cell["key"],
                "n": cell["n"],
                "gold_status": cell["gold_status"],
                "validity": cell["validity"],
                "promotion_status": cell["promotion_status"],
                "accuracy": metrics.get("accuracy"),
                "log_loss": metrics.get("log_loss"),
                "brier": metrics.get("brier"),
                "ece_10": metrics.get("ece_10"),
                "bilingual_prediction_agreement": metrics.get("bilingual_prediction_agreement"),
                "mean_distribution_drift": metrics.get("mean_distribution_drift"),
                "blockers": " | ".join(cell["blockers"]),
            })
    index = {
        "gate": "IRP27-GATE-CONTRACT-CALIBRATION-REGISTRY-AND-BILINGUAL-SHADOW-EVALUATION-012",
        "registry_version": "2.3.0",
        "cell_identity": ["contract_hash", "provider", "provider_version", "checkpoint", "question_id", "primitive", "domain", "language", "hardware", "data_vintage", "evaluation_mode"],
        "cells": len(cells),
        "external_cells": sum(cell["validity"] == "EXTERNAL_SHADOW_ONLY" for cell in cells),
        "bilingual_cells": sum(cell["validity"] == "INVARIANCE_ONLY_NO_GOLD" for cell in cells),
        "providers": sorted({cell["key"]["provider"] for cell in cells}),
        "questions": sorted({cell["key"]["question_id"] for cell in cells}),
        "primitives": sorted({cell["key"]["primitive"] for cell in cells}),
        "languages": sorted({cell["key"]["language"] for cell in cells}),
        "promotion_counts": dict(Counter(cell["promotion_status"] for cell in cells)),
        "bilingual_status": bilingual_status,
        "disagreement": disagreement,
        "receipt_root": receipts[-1]["receipt_hash"] if receipts else None,
        "validation_errors": errors,
        "provider_authority": "NONE",
        "automatic_execution": False,
        "automatic_publication": False,
    }
    (output / "registry_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if errors:
        raise SystemExit(json.dumps(index, indent=2))
    return index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--flip-cases", type=Path, required=True)
    parser.add_argument("--providers", nargs="+", required=True)
    parser.add_argument("--provider-versions", nargs="+", required=True)
    parser.add_argument("--base-outputs", type=Path, nargs="+", required=True)
    parser.add_argument("--flip-outputs", type=Path, nargs="+", required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--external-vintage", required=True)
    parser.add_argument("--bilingual-pairs", type=Path)
    parser.add_argument("--bilingual-outputs", type=Path)
    parser.add_argument("--laya-version", default="0.4.15")
    parser.add_argument("--live-hardware", default="github_actions_cpu")
    parser.add_argument("--argentine-vintage", default="SOTA009-v1.8-machine-translation-unreviewed")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not (len(args.providers) == len(args.provider_versions) == len(args.base_outputs) == len(args.flip_outputs)):
        raise SystemExit("Provider argument lengths must match")
    print(json.dumps(build_registry(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
