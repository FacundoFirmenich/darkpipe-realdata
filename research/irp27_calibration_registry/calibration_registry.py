#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

EPS = 1e-15


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    rows = list(rows)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def normalize_distribution(probabilities: Mapping[str, Any], labels: Sequence[str]) -> dict[str, float]:
    values = np.asarray([max(0.0, float(probabilities.get(label, 0.0))) for label in labels], dtype=float)
    total = float(values.sum())
    if total <= 0:
        values[:] = 1.0 / max(1, len(values))
    else:
        values /= total
    return {label: float(values[index]) for index, label in enumerate(labels)}


def answer_distribution(answer: Mapping[str, Any], question: Mapping[str, Any]) -> tuple[list[str], dict[str, float], Any]:
    qtype = question["type"]
    if qtype in {"choice", "score"}:
        labels = list(question.get("criteria", {}))
        distribution = normalize_distribution(answer.get("probabilities") or {}, labels)
        prediction = answer.get("choice") if qtype == "choice" else str(answer.get("score"))
        if qtype == "score" and prediction not in labels:
            prediction = max(distribution, key=distribution.get)
        return labels, distribution, prediction
    if qtype == "noul":
        labels = ["true", "false"]
        raw = answer.get("noul")
        if isinstance(raw, bool):
            probability_true = 1.0 if raw else 0.0
            prediction = raw
        else:
            probability_true = float(raw if raw is not None else answer.get("probability", answer.get("confidence", 0.5)))
            probability_true = min(1.0, max(0.0, probability_true))
            prediction = probability_true >= 0.5
        return labels, {"true": probability_true, "false": 1.0 - probability_true}, prediction
    raise ValueError(qtype)


def gold_label(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def reliability_bins(confidences: Sequence[float], correct: Sequence[int], bins: int = 10) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        selected = [i for i, confidence in enumerate(confidences) if lower <= confidence < (upper if index < bins - 1 else upper + 1e-12)]
        output.append({"bin": index, "lower": lower, "upper": upper, "n": len(selected), "mean_confidence": statistics.fmean(confidences[i] for i in selected) if selected else None, "accuracy": statistics.fmean(correct[i] for i in selected) if selected else None})
    return output


def expected_calibration_error(confidences: Sequence[float], correct: Sequence[int], bins: int = 10) -> float | None:
    if not confidences:
        return None
    result = 0.0
    for row in reliability_bins(confidences, correct, bins):
        if row["n"]:
            result += row["n"] / len(confidences) * abs(float(row["mean_confidence"]) - float(row["accuracy"]))
    return result


def risk_coverage_curve(confidences: Sequence[float], correct: Sequence[int]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    if not confidences:
        return output
    for threshold in np.linspace(0.0, 1.0, 21):
        selected = [i for i, confidence in enumerate(confidences) if confidence >= threshold]
        output.append({"threshold": float(threshold), "coverage": len(selected) / len(confidences), "selective_accuracy": statistics.fmean(correct[i] for i in selected) if selected else None, "selective_risk": 1.0 - statistics.fmean(correct[i] for i in selected) if selected else None, "n": len(selected)})
    return output


def js_divergence(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    labels = sorted(set(left) | set(right))
    p = np.asarray([max(EPS, float(left.get(label, 0.0))) for label in labels], dtype=float)
    q = np.asarray([max(EPS, float(right.get(label, 0.0))) for label in labels], dtype=float)
    p /= p.sum(); q /= q.sum(); m = 0.5 * (p + q)
    return float(0.5 * np.sum(p * np.log(p / m)) + 0.5 * np.sum(q * np.log(q / m)))


def calibration_key(*, contract_hash: str, provider: str, provider_version: str, checkpoint: str, primitive: str, domain: str, language: str, hardware: str, data_vintage: str, evaluation_mode: str) -> dict[str, str]:
    return {"contract_hash": contract_hash, "provider": provider, "provider_version": provider_version, "checkpoint": checkpoint, "primitive": primitive, "domain": domain, "language": language, "hardware": hardware, "data_vintage": data_vintage, "evaluation_mode": evaluation_mode}


def key_id(key: Mapping[str, str]) -> str:
    return "CAL-" + sha256_value(dict(key))[:20]


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
            labels, distribution, prediction = answer_distribution(answer, question)
            gold = gold_label(case["gold"][question_id])
            p_gold = max(EPS, float(distribution.get(gold, 0.0)))
            confidence = max(distribution.values())
            correct = int(str(prediction).lower() == str(case["gold"][question_id]).lower())
            one_hot = np.asarray([1.0 if label == gold else 0.0 for label in labels])
            probabilities = np.asarray([distribution[label] for label in labels])
            key = calibration_key(contract_hash=contract_hash, provider=provider, provider_version=provider_version, checkpoint=str(output.get("model") or "unknown"), primitive=question["type"], domain=str(case.get("track") or case.get("dataset") or "unknown"), language=str(case.get("lang") or "unknown"), hardware=hardware, data_vintage=data_vintage, evaluation_mode=evaluation_mode)
            records.append({"key": key, "case_id": case["id"], "question_id": question_id, "dataset": case.get("dataset"), "gold": case["gold"][question_id], "prediction": prediction, "distribution": distribution, "confidence": confidence, "correct": correct, "log_loss": -math.log(p_gold), "brier": float(np.sum((probabilities - one_hot) ** 2)), "latency_ms": float(output.get("ms") or 0.0), "label_confidence": case.get("label_confidence")})
    return records


def aggregate_cells(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list); keys: dict[str, dict[str, str]] = {}
    for record in records:
        identifier = key_id(record["key"]); grouped[identifier].append(record); keys[identifier] = dict(record["key"])
    cells: list[dict[str, Any]] = []
    for identifier in sorted(grouped):
        rows = grouped[identifier]; confidences = [float(row["confidence"]) for row in rows]; correct = [int(row["correct"]) for row in rows]
        cells.append({"calibration_id": identifier, "key": keys[identifier], "n": len(rows), "gold_status": "PUBLISHED_BENCHMARK_GOLD", "metrics": {"accuracy": statistics.fmean(correct), "log_loss": statistics.fmean(float(row["log_loss"]) for row in rows), "brier": statistics.fmean(float(row["brier"]) for row in rows), "ece_10": expected_calibration_error(confidences, correct, 10), "mean_confidence": statistics.fmean(confidences), "latency_ms_mean": statistics.fmean(float(row["latency_ms"]) for row in rows), "latency_ms_p50": float(np.quantile([float(row["latency_ms"]) for row in rows], 0.5)), "latency_ms_p95": float(np.quantile([float(row["latency_ms"]) for row in rows], 0.95)), "reliability_bins": reliability_bins(confidences, correct, 10), "risk_coverage": risk_coverage_curve(confidences, correct)}, "validity": "EXTERNAL_SHADOW_ONLY", "promotion_status": "BLOCKED", "blockers": ["CONTRACT_MISMATCH_WITH_IRP27_EVIDENCE_RELATION", "NO_INDEPENDENT_REPLICATION", "NO_ARGENTINE_GOLD", "NO_HUMAN_AUTHORITY"], "automatic_execution": False, "automatic_publication": False})
    return cells


def attach_flip_stability(cells: list[dict[str, Any]], base_records: Sequence[Mapping[str, Any]], flip_records: Sequence[Mapping[str, Any]]) -> None:
    base = {(row["key"]["provider"], row["case_id"], row["question_id"]): row for row in base_records}; flip = {(row["key"]["provider"], row["case_id"], row["question_id"]): row for row in flip_records}; grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for key in set(base) & set(flip):
        b = base[key]; f = flip[key]; identifier = key_id(b["key"]); grouped[identifier].append({"stable": int(str(b["prediction"]) == str(f["prediction"])), "harmful": int(b["correct"] == 1 and f["correct"] == 0), "beneficial": int(b["correct"] == 0 and f["correct"] == 1)})
    for cell in cells:
        rows = grouped.get(cell["calibration_id"], [])
        cell["metrics"]["option_order"] = {"n": len(rows), "stability": statistics.fmean(row["stable"] for row in rows) if rows else None, "harmful_flips": sum(row["harmful"] for row in rows), "beneficial_flips": sum(row["beneficial"] for row in rows)}
        if rows and cell["metrics"]["option_order"]["stability"] < 0.95:
            cell["blockers"].append("OPTION_ORDER_STABILITY_BELOW_0_95")


def bilingual_cells(outputs: Sequence[Mapping[str, Any]], pair_metadata: Mapping[str, Mapping[str, Any]], *, contract_hash: str, provider_version: str, hardware: str, data_vintage: str) -> list[dict[str, Any]]:
    by_pair: dict[tuple[str, str, str], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in outputs:
        if row.get("ok"):
            by_pair[(row["checkpoint"], row["item_id"], row["question_id"])][row["language"]] = row
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for (checkpoint, item_id, question_id), languages in by_pair.items():
        if "es" not in languages or "en" not in languages:
            continue
        es = languages["es"]; en = languages["en"]; meta = pair_metadata[item_id]; primitive = es["primitive"]
        drift = abs(float(es["distribution"]["true"]) - float(en["distribution"]["true"])) if primitive == "noul" else js_divergence(es["distribution"], en["distribution"])
        grouped[(checkpoint, primitive, meta["domain"])].append({"agreement": int(str(es["prediction"]) == str(en["prediction"])), "distribution_drift": drift, "es_confidence": max(es["distribution"].values()), "en_confidence": max(en["distribution"].values()), "latency_es": float(es.get("latency_ms") or 0.0), "latency_en": float(en.get("latency_ms") or 0.0)})
    cells: list[dict[str, Any]] = []
    for (checkpoint, primitive, domain), rows in sorted(grouped.items()):
        key = calibration_key(contract_hash=contract_hash, provider="laya", provider_version=provider_version, checkpoint=checkpoint, primitive=primitive, domain=domain, language="es-en-paired", hardware=hardware, data_vintage=data_vintage, evaluation_mode="BILINGUAL_SHADOW_INVARIANCE_ONLY")
        cells.append({"calibration_id": key_id(key), "key": key, "n": len(rows), "gold_status": "ARGENTINE_GOLD_NOT_FROZEN", "metrics": {"bilingual_prediction_agreement": statistics.fmean(row["agreement"] for row in rows), "mean_distribution_drift": statistics.fmean(row["distribution_drift"] for row in rows), "p95_distribution_drift": float(np.quantile([row["distribution_drift"] for row in rows], 0.95)), "mean_confidence_es": statistics.fmean(row["es_confidence"] for row in rows), "mean_confidence_en": statistics.fmean(row["en_confidence"] for row in rows), "latency_ms_mean_es": statistics.fmean(row["latency_es"] for row in rows), "latency_ms_mean_en": statistics.fmean(row["latency_en"] for row in rows), "accuracy": None, "log_loss": None, "brier": None, "ece_10": None}, "validity": "INVARIANCE_ONLY_NO_GOLD", "promotion_status": "BLOCKED", "blockers": ["GOLD_NOT_FROZEN", "TRANSLATION_NOT_HUMAN_REVIEWED", "HUMAN_ANNOTATIONS_INCOMPLETE", "NO_ACCURACY_OR_CALIBRATION_AUTHORITY", "NO_EXTERNAL_REPLICATION"], "automatic_execution": False, "automatic_publication": False})
    return cells


def disagreement_summary(records_by_provider: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    providers = sorted(records_by_provider); maps = {provider: {(row["case_id"], row["question_id"]): row for row in records_by_provider[provider]} for provider in providers}; output: dict[str, Any] = {}
    for index, left in enumerate(providers):
        for right in providers[index + 1 :]:
            keys = set(maps[left]) & set(maps[right]); disagreements = [key for key in keys if str(maps[left][key]["prediction"]) != str(maps[right][key]["prediction"])]
            if keys:
                output[f"{left}__{right}"] = {"n": len(keys), "disagreements": len(disagreements), "disagreement_rate": len(disagreements) / len(keys), "review_trigger": bool(disagreements)}
    return output


def receipt_chain(cells: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    previous = None; receipts: list[dict[str, Any]] = []
    for cell in sorted(cells, key=lambda row: row["calibration_id"]):
        body = {"calibration_id": cell["calibration_id"], "key": cell["key"], "cell_hash": sha256_value(cell), "promotion_status": cell["promotion_status"], "previous_receipt_hash": previous, "automatic_execution": False, "automatic_publication": False}
        receipt_hash = sha256_value(body); receipts.append({**body, "receipt_hash": receipt_hash}); previous = receipt_hash
    return receipts


def validate_no_cross_cell_transport(cells: Sequence[Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []; seen: dict[str, Mapping[str, Any]] = {}
    for cell in cells:
        expected = key_id(cell["key"])
        if expected != cell["calibration_id"]: errors.append(f"KEY_HASH_MISMATCH:{cell['calibration_id']}")
        if expected in seen and canonical_bytes(seen[expected]["key"]) != canonical_bytes(cell["key"]): errors.append(f"KEY_COLLISION:{expected}")
        seen[expected] = cell
        if cell["promotion_status"] != "BLOCKED": errors.append(f"UNAUTHORIZED_PROMOTION:{expected}")
        if cell["automatic_execution"] or cell["automatic_publication"]: errors.append(f"AUTHORITY_BOUNDARY_VIOLATION:{expected}")
    return errors


def build_registry(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output; output.mkdir(parents=True, exist_ok=True); cases = read_jsonl(args.cases); flip_cases = read_jsonl(args.flip_cases); benchmark_contract_hash = hashlib.sha256(args.cases.read_bytes()).hexdigest(); all_base_records: list[dict[str, Any]] = []; all_flip_records: list[dict[str, Any]] = []; records_by_provider: dict[str, list[dict[str, Any]]] = {}
    for provider, version, base_path, flip_path in zip(args.providers, args.provider_versions, args.base_outputs, args.flip_outputs):
        base = external_records(cases, read_jsonl(base_path), provider=provider, provider_version=version, contract_hash=benchmark_contract_hash, data_vintage=args.external_vintage, hardware="external_unknown"); flip = external_records(flip_cases, read_jsonl(flip_path), provider=provider, provider_version=version, contract_hash=benchmark_contract_hash, data_vintage=args.external_vintage, hardware="external_unknown"); records_by_provider[provider] = base; all_base_records.extend(base); all_flip_records.extend(flip)
    cells = aggregate_cells(all_base_records); attach_flip_stability(cells, all_base_records, all_flip_records)
    bilingual_status: dict[str, Any] = {"available": False, "reason": "NO_OUTPUT_FILE"}
    if args.bilingual_outputs and args.bilingual_outputs.exists() and args.bilingual_outputs.stat().st_size:
        outputs = read_jsonl(args.bilingual_outputs); pairs = {row["item_id"]: row for row in read_jsonl(args.bilingual_pairs)}; current_contract = json.loads(args.contract.read_text()); current_hash = sha256_value(current_contract); bilingual = bilingual_cells(outputs, pairs, contract_hash=current_hash, provider_version=args.laya_version, hardware=args.live_hardware, data_vintage=args.argentine_vintage); cells.extend(bilingual); bilingual_status = {"available": True, "records": len(outputs), "cells": len(bilingual)}
    errors = validate_no_cross_cell_transport(cells); receipts = receipt_chain(cells); disagreement = disagreement_summary(records_by_provider); write_jsonl(output / "calibration_registry.jsonl", cells); write_jsonl(output / "calibration_receipts.jsonl", receipts)
    with (output / "calibration_matrix.csv").open("w", newline="", encoding="utf-8") as file:
        fields = ["calibration_id", "contract_hash", "provider", "provider_version", "checkpoint", "primitive", "domain", "language", "hardware", "data_vintage", "evaluation_mode", "n", "gold_status", "validity", "promotion_status", "accuracy", "log_loss", "brier", "ece_10", "bilingual_prediction_agreement", "mean_distribution_drift", "blockers"]; writer = csv.DictWriter(file, fieldnames=fields); writer.writeheader()
        for cell in cells:
            metrics = cell["metrics"]; writer.writerow({"calibration_id": cell["calibration_id"], **cell["key"], "n": cell["n"], "gold_status": cell["gold_status"], "validity": cell["validity"], "promotion_status": cell["promotion_status"], "accuracy": metrics.get("accuracy"), "log_loss": metrics.get("log_loss"), "brier": metrics.get("brier"), "ece_10": metrics.get("ece_10"), "bilingual_prediction_agreement": metrics.get("bilingual_prediction_agreement"), "mean_distribution_drift": metrics.get("mean_distribution_drift"), "blockers": " | ".join(cell["blockers"])})
    index = {"gate": "IRP27-GATE-CONTRACT-CALIBRATION-REGISTRY-AND-BILINGUAL-SHADOW-EVALUATION-012", "registry_version": "2.2.0", "cells": len(cells), "external_cells": sum(cell["validity"] == "EXTERNAL_SHADOW_ONLY" for cell in cells), "bilingual_cells": sum(cell["validity"] == "INVARIANCE_ONLY_NO_GOLD" for cell in cells), "providers": sorted({cell["key"]["provider"] for cell in cells}), "primitives": sorted({cell["key"]["primitive"] for cell in cells}), "languages": sorted({cell["key"]["language"] for cell in cells}), "promotion_counts": dict(Counter(cell["promotion_status"] for cell in cells)), "bilingual_status": bilingual_status, "disagreement": disagreement, "receipt_root": receipts[-1]["receipt_hash"] if receipts else None, "validation_errors": errors, "provider_authority": "NONE", "automatic_execution": False, "automatic_publication": False}
    (output / "registry_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if errors: raise SystemExit(json.dumps(index, indent=2))
    return index


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--cases", type=Path, required=True); parser.add_argument("--flip-cases", type=Path, required=True); parser.add_argument("--providers", nargs="+", required=True); parser.add_argument("--provider-versions", nargs="+", required=True); parser.add_argument("--base-outputs", type=Path, nargs="+", required=True); parser.add_argument("--flip-outputs", type=Path, nargs="+", required=True); parser.add_argument("--contract", type=Path, required=True); parser.add_argument("--external-vintage", required=True); parser.add_argument("--bilingual-pairs", type=Path); parser.add_argument("--bilingual-outputs", type=Path); parser.add_argument("--laya-version", default="0.4.15"); parser.add_argument("--live-hardware", default="github_actions_cpu"); parser.add_argument("--argentine-vintage", default="SOTA009-v1.8-machine-translation-unreviewed"); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    if not (len(args.providers) == len(args.provider_versions) == len(args.base_outputs) == len(args.flip_outputs)): raise SystemExit("Provider argument lengths must match")
    print(json.dumps(build_registry(args), ensure_ascii=False, indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
