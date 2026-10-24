#!/usr/bin/env python3
"""IRP-27 Gate SOTA-005: learned verification-question policy.

The model learns a weakly supervised question-type policy from the AVeriTeC
training split, generates estimand-preserving evidence-seeking queries, tunes a
fusion policy on a frozen calibration half of the development split, and evaluates
once on the held-out half. It uses only public benchmark annotations and does not
claim open-web or human external validity.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import f1_score, hamming_loss
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import FeatureUnion
from sklearn.linear_model import LogisticRegression

SEED = 27
LABELS = (
    "NUMERIC",
    "ATTRIBUTION",
    "TEMPORAL",
    "LOCATION",
    "SOURCE_PROVENANCE",
    "DEFINITION_CONTEXT",
    "EVENT_EXISTENCE",
    "CAUSAL_MECHANISM",
    "COMPARISON",
    "SCOPE_EXCEPTION",
)
STOP = set(
    "the a an in on at for to of and but or as if it this that there has have had been is are was were be being "
    "from by with during more than would could should now just fact check says said say claim claimed people "
    "government president administration current new all completely approximately because due result under over "
    "into about against after before when who what which why how yes no does did do where source report evidence".split()
)


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text).lower())
    return "".join(char for char in text if not unicodedata.combining(char))


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", fold(text))


class BM25:
    def __init__(self, documents: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.documents = documents
        self.k1 = k1
        self.b = b
        self.n = len(documents)
        self.avg_length = sum(map(len, documents)) / max(self.n, 1)
        self.term_frequencies = [Counter(document) for document in documents]
        document_frequency: Counter[str] = Counter()
        for document in documents:
            document_frequency.update(set(document))
        self.idf = {
            term: math.log(1 + (self.n - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in document_frequency.items()
        }

    def scores(self, query: str) -> np.ndarray:
        output = np.zeros(self.n, dtype=float)
        for term in tokenize(query):
            idf = self.idf.get(term, 0.0)
            if not idf:
                continue
            for index, frequencies in enumerate(self.term_frequencies):
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                denominator = frequency + self.k1 * (
                    1 - self.b + self.b * len(self.documents[index]) / self.avg_length
                )
                output[index] += idf * frequency * (self.k1 + 1) / denominator
        return output


def question_labels(question: str) -> set[str]:
    q = fold(question).strip()
    labels: set[str] = set()
    if re.search(r"\b(how many|how much|what percentage|what percent|what rate|what number|what amount|by how much)\b", q):
        labels.add("NUMERIC")
    if re.search(r"\b(who said|who stated|who claimed|according to whom|what did .+ say|quote|transcript)\b", q):
        labels.add("ATTRIBUTION")
    if re.search(r"\b(when|what date|what year|which year|during what period|how long)\b", q):
        labels.add("TEMPORAL")
    if re.search(r"\b(where|which country|which state|which city|which region|what location)\b", q):
        labels.add("LOCATION")
    if re.search(r"\b(what source|which source|what report|which report|what study|official source|where was .+ published|evidence)\b", q):
        labels.add("SOURCE_PROVENANCE")
    if re.search(r"\b(what is|what are|what does .+ mean|define|definition|what was the context|what is the context)\b", q):
        labels.add("DEFINITION_CONTEXT")
    if re.search(r"\b(did|does|do|is there|are there|was there|were there|has .+ occurred|have .+ occurred|whether)\b", q):
        labels.add("EVENT_EXISTENCE")
    if re.search(r"\b(why|what caused|what causes|because of|due to|lead to|result in|effect of|impact of)\b", q):
        labels.add("CAUSAL_MECHANISM")
    if re.search(r"\b(compare|comparison|more than|less than|higher than|lower than|difference between|versus|vs\b)\b", q):
        labels.add("COMPARISON")
    if re.search(r"\b(all|every|any|only|always|never|exception|exceptions|how many countries|how many states)\b", q):
        labels.add("SCOPE_EXCEPTION")
    if not labels:
        labels.add("EVENT_EXISTENCE")
    return labels


def claim_type_labels(item: dict[str, Any]) -> set[str]:
    labels: set[str] = set()
    for question in item.get("questions", []):
        labels.update(question_labels(question.get("question", "")))
    return labels or {"EVENT_EXISTENCE"}


def extract_numbers(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\d+(?:[.,]\d+)?%?", text)))


def extract_entities(text: str) -> list[str]:
    entities: list[str] = []
    for match in re.finditer(r"\b[A-Z][A-Za-z0-9\'-]+(?:\s+[A-Z][A-Za-z0-9\'-]+){0,4}", text):
        entities.append(match.group(0))
    return list(dict.fromkeys(entities))[:10]


def content_terms(text: str, limit: int = 16) -> list[str]:
    terms = [term for term in tokenize(text) if term not in STOP and len(term) > 2]
    return list(dict.fromkeys(terms))[:limit]


def query_contract(item: dict[str, Any]) -> dict[str, Any]:
    claim = item.get("claim", "").strip()
    return {
        "claim": claim,
        "entities": extract_entities(claim),
        "numbers": extract_numbers(claim),
        "speaker": item.get("speaker") or None,
        "date": item.get("claim_date") or None,
        "terms": content_terms(claim),
    }


def validate_query(text: str, contract: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    claim_folded = fold(contract["claim"])
    for number in extract_numbers(text):
        if fold(number) not in claim_folded:
            issues.append(f"invented_number:{number}")
    for entity in extract_entities(text):
        if fold(entity) not in claim_folded and entity not in {"Official", "Report", "Transcript"}:
            issues.append(f"invented_entity:{entity}")
    return issues


def learned_queries(item: dict[str, Any], label_probabilities: dict[str, float], threshold: float, budget: int) -> list[dict[str, Any]]:
    contract = query_contract(item)
    claim = contract["claim"]
    entities = contract["entities"]
    numbers = contract["numbers"]
    speaker = [contract["speaker"]] if contract["speaker"] else []
    date = [contract["date"]] if contract["date"] else []
    terms = contract["terms"]
    prefix = entities + numbers + speaker + date
    candidates: list[tuple[float, str, str]] = []

    def add(label: str, text_parts: Iterable[str]) -> None:
        probability = float(label_probabilities[label])
        text = " ".join(part for part in text_parts if part).strip()
        if probability >= threshold and text:
            candidates.append((probability, label, text))

    add("NUMERIC", prefix + terms[:12])
    add("ATTRIBUTION", speaker + entities + terms[:12] + ["transcript", "quote", "source"])
    add("TEMPORAL", entities + terms[:12] + date)
    add("LOCATION", entities + terms[:12] + ["location"])
    add("SOURCE_PROVENANCE", entities + terms[:14] + ["official", "report", "source"])
    add("DEFINITION_CONTEXT", entities + terms[:12] + ["definition", "context"])
    add("EVENT_EXISTENCE", prefix + terms[:14] + ["official", "record"])
    add("CAUSAL_MECHANISM", entities + terms[:12] + ["cause", "effect", "alternative", "evidence"])
    add("COMPARISON", prefix + terms[:14] + ["comparison"])
    add("SCOPE_EXCEPTION", entities + terms[:12] + ["scope", "exceptions"])

    candidates.sort(key=lambda row: (-row[0], LABELS.index(row[1])))
    output = [{"label": "CLAIM", "probability": 1.0, "text": claim}]
    seen = {fold(claim)}
    for probability, label, text in candidates:
        if len(output) >= budget + 1:
            break
        key = fold(text)
        if key in seen:
            continue
        issues = validate_query(text, contract)
        if issues:
            raise ValueError({"claim": claim, "query": text, "issues": issues})
        seen.add(key)
        output.append({"label": label, "probability": probability, "text": text})
    return output


def structured_v13_queries(item: dict[str, Any]) -> list[str]:
    claim = item.get("claim", "").strip()
    folded = fold(claim)
    entities = [fold(entity) for entity in extract_entities(claim)]
    numbers = extract_numbers(claim)
    terms = content_terms(claim)
    speaker = [item.get("speaker")] if item.get("speaker") else []
    date = [item.get("claim_date")] if item.get("claim_date") else []
    queries = [claim]
    context = " ".join(speaker + entities + numbers + date + terms[:16])
    if context:
        queries.append(context)
    if numbers or "Numerical Claim" in (item.get("claim_types") or []):
        queries.append(" ".join(["amount", "value", "percentage", "number"] + entities + numbers + terms[:12] + date))
    if "Quote Verification" in (item.get("claim_types") or []) or re.search(r"\b(said|says|declared|announced)\b", folded):
        queries.append(" ".join(["quote", "transcript", "said", "source"] + speaker + entities + terms[:14]))
    if re.search(r"\b(all|every|completely|never|none|unprecedented)\b", folded):
        queries.append(" ".join(["scope", "exception", "all", "evidence"] + entities + terms[:14]))
    if re.search(r"\b(because|due to|causes?|results? in|leads? to|as a result)\b", folded):
        queries.append(" ".join(["cause", "effect", "evidence", "alternative"] + entities + terms[:14]))
    return list(dict.fromkeys(" ".join(query.split()) for query in queries if query.strip()))[:6]


def gold_questions(item: dict[str, Any]) -> list[str]:
    return [question.get("question", "").strip() for question in item.get("questions", []) if question.get("question", "").strip()]


def rrf_scores(rankings: list[np.ndarray], weights: list[float], n_documents: int, constant: int) -> np.ndarray:
    scores = np.zeros(n_documents, dtype=float)
    for ranking, weight in zip(rankings, weights):
        positions = np.empty(n_documents, dtype=int)
        positions[ranking] = np.arange(1, n_documents + 1)
        scores += weight / (constant + positions)
    return scores


def max_scores(score_vectors: list[np.ndarray], weights: list[float]) -> np.ndarray:
    normalized: list[np.ndarray] = []
    for scores, weight in zip(score_vectors, weights):
        maximum = float(scores.max()) or 1.0
        normalized.append(weight * scores / maximum)
    return np.max(np.vstack(normalized), axis=0)


def evidence_map(data: list[dict[str, Any]]) -> tuple[list[str], list[set[int]], list[list[set[int]]]]:
    passages: list[str] = []
    claim_relevant: list[set[int]] = []
    question_relevant: list[list[set[int]]] = []
    for item in data:
        claim_set: set[int] = set()
        question_sets: list[set[int]] = []
        for question in item.get("questions", []):
            qset: set[int] = set()
            for answer in question.get("answers", []):
                text = (answer.get("answer") or "").strip()
                if answer.get("answer_type") == "Unanswerable" or text.startswith("No, There is not enough information."):
                    continue
                index = len(passages)
                passages.append(text)
                qset.add(index)
                claim_set.add(index)
            if qset:
                question_sets.append(qset)
        claim_relevant.append(claim_set)
        question_relevant.append(question_sets)
    return passages, claim_relevant, question_relevant


def ranking_metrics(orders: list[np.ndarray], claim_gold: list[set[int]], question_gold: list[list[set[int]]], indices: list[int]) -> dict[str, float]:
    output: dict[str, float] = {}
    for cutoff in (1, 5, 10):
        output[f"recall_any@{cutoff}"] = sum(
            any(int(index) in claim_gold[item] for index in orders[item][:cutoff]) for item in indices
        ) / len(indices)
        coverage_values: list[float] = []
        sufficient_25 = 0
        sufficient_50 = 0
        precision_values: list[float] = []
        for item in indices:
            top = {int(index) for index in orders[item][:cutoff]}
            qsets = question_gold[item]
            coverage = sum(bool(top & qset) for qset in qsets) / len(qsets) if qsets else 0.0
            coverage_values.append(coverage)
            sufficient_25 += coverage >= 0.25
            sufficient_50 += coverage >= 0.50
            precision_values.append(len(top & claim_gold[item]) / cutoff)
        output[f"question_coverage@{cutoff}"] = float(np.mean(coverage_values))
        output[f"sufficient25@{cutoff}"] = sufficient_25 / len(indices)
        output[f"sufficient50@{cutoff}"] = sufficient_50 / len(indices)
        output[f"precision@{cutoff}"] = float(np.mean(precision_values))
    reciprocal = []
    for item in indices:
        rank = next((position for position, index in enumerate(orders[item], 1) if int(index) in claim_gold[item]), None)
        reciprocal.append(0.0 if rank is None else 1.0 / rank)
    output["mrr"] = float(np.mean(reciprocal))
    return output


def bootstrap_differences(baseline_orders: list[np.ndarray], alternative_orders: list[np.ndarray], claim_gold: list[set[int]], question_gold: list[list[set[int]]], indices: list[int], iterations: int = 10000) -> list[dict[str, Any]]:
    rng = np.random.default_rng(SEED)
    results: list[dict[str, Any]] = []
    metric_functions = {
        "recall_any@10": lambda order, item: float(any(int(index) in claim_gold[item] for index in order[:10])),
        "question_coverage@10": lambda order, item: (sum(bool(set(map(int, order[:10])) & qset) for qset in question_gold[item]) / len(question_gold[item]) if question_gold[item] else 0.0),
        "sufficient25@10": lambda order, item: float((sum(bool(set(map(int, order[:10])) & qset) for qset in question_gold[item]) / len(question_gold[item]) if question_gold[item] else 0.0) >= 0.25),
        "precision@10": lambda order, item: len(set(map(int, order[:10])) & claim_gold[item]) / 10,
    }
    for metric, function in metric_functions.items():
        baseline = np.asarray([function(baseline_orders[item], item) for item in indices])
        alternative = np.asarray([function(alternative_orders[item], item) for item in indices])
        difference = alternative - baseline
        samples = np.asarray([difference[rng.integers(0, len(difference), len(difference))].mean() for _ in range(iterations)])
        results.append({"metric": metric, "difference": float(difference.mean()), "ci_low": float(np.quantile(samples, 0.025)), "ci_high": float(np.quantile(samples, 0.975)), "wins": int(sum(difference > 0)), "losses": int(sum(difference < 0)), "ties": int(sum(difference == 0))})
    return results


def build_label_matrix(data: list[dict[str, Any]]) -> np.ndarray:
    matrix = np.zeros((len(data), len(LABELS)), dtype=int)
    for row, item in enumerate(data):
        for label in claim_type_labels(item):
            matrix[row, LABELS.index(label)] = 1
    return matrix


def train_type_model(train_data: list[dict[str, Any]]):
    texts = [item.get("claim", "") for item in train_data]
    labels = build_label_matrix(train_data)
    features = FeatureUnion([
        ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=60000, sublinear_tf=True)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3, max_features=60000, sublinear_tf=True)),
    ])
    x = features.fit_transform(texts)
    model = OneVsRestClassifier(LogisticRegression(max_iter=2000, class_weight="balanced", solver="liblinear", random_state=SEED))
    model.fit(x, labels)
    return features, model


def evaluate_type_model(probabilities: np.ndarray, gold: np.ndarray, threshold: float) -> dict[str, Any]:
    predicted = (probabilities >= threshold).astype(int)
    return {"threshold": threshold, "micro_f1": float(f1_score(gold, predicted, average="micro", zero_division=0)), "macro_f1": float(f1_score(gold, predicted, average="macro", zero_division=0)), "hamming_loss": float(hamming_loss(gold, predicted)), "per_label_f1": {label: float(f1_score(gold[:, index], predicted[:, index], zero_division=0)) for index, label in enumerate(LABELS)}}


def run(train_data: list[dict[str, Any]], dev_data: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    features, model = train_type_model(train_data)
    probabilities = model.predict_proba(features.transform([item.get("claim", "") for item in dev_data]))
    weak_gold = build_label_matrix(dev_data)

    rng = random.Random(SEED)
    indices = list(range(len(dev_data)))
    rng.shuffle(indices)
    calibration = indices[: len(indices) // 2]
    heldout = indices[len(indices) // 2 :]

    passages, claim_gold, question_gold = evidence_map(dev_data)
    bm25 = BM25([tokenize(passage) for passage in passages])
    baseline_orders: list[np.ndarray] = []
    structured_orders: list[np.ndarray] = []
    gold_orders: list[np.ndarray] = []
    baseline_score_cache: list[np.ndarray] = []
    query_score_cache: list[dict[str, np.ndarray]] = []
    query_audit: list[dict[str, Any]] = []

    for item_index, item in enumerate(dev_data):
        baseline_scores = bm25.scores(item.get("claim", ""))
        baseline_score_cache.append(baseline_scores)
        baseline_orders.append(np.argsort(baseline_scores)[::-1])
        structured_vectors = [bm25.scores(query) for query in structured_v13_queries(item)]
        structured_orders.append(np.argsort(max_scores(structured_vectors, [1.0] + [0.9] * (len(structured_vectors) - 1)))[::-1])
        gold_vectors = [bm25.scores(query) for query in gold_questions(item)] or [baseline_scores]
        gold_orders.append(np.argsort(max_scores(gold_vectors, [1.0] * len(gold_vectors)))[::-1])
        label_map = {label: float(probabilities[item_index, index]) for index, label in enumerate(LABELS)}
        cache: dict[str, np.ndarray] = {}
        for query in learned_queries(item, label_map, 0.0, len(LABELS)):
            cache[query["label"]] = bm25.scores(query["text"])
        query_score_cache.append(cache)
        query_audit.append({"claim_index": item_index, "claim": item.get("claim", ""), "label_probabilities": label_map, "weak_gold_labels": sorted(claim_type_labels(item))})

    cache_policies: dict[tuple[float, int, str, int], tuple[list[np.ndarray], list[int]]] = {}
    def policy_orders(threshold: float, budget: int, fusion: str, rrf_constant: int) -> tuple[list[np.ndarray], list[int]]:
        key = (threshold, budget, fusion, rrf_constant)
        if key in cache_policies:
            return cache_policies[key]
        orders: list[np.ndarray] = []
        counts: list[int] = []
        for item_index in range(len(dev_data)):
            selected = sorted([(float(probabilities[item_index, LABELS.index(label)]), label) for label in LABELS if probabilities[item_index, LABELS.index(label)] >= threshold], key=lambda row: (-row[0], LABELS.index(row[1])))[:budget]
            rankings = [baseline_orders[item_index]]
            weights = [1.0]
            vectors = [baseline_score_cache[item_index]]
            for probability, label in selected:
                scores = query_score_cache[item_index].get(label)
                if scores is None:
                    continue
                rankings.append(np.argsort(scores)[::-1])
                weights.append(max(0.15, probability))
                vectors.append(scores)
            fused = rrf_scores(rankings, weights, len(passages), rrf_constant) if fusion == "rrf" else max_scores(vectors, weights)
            orders.append(np.argsort(fused)[::-1])
            counts.append(len(rankings) - 1)
        cache_policies[key] = (orders, counts)
        return orders, counts

    best: dict[str, Any] | None = None
    grid_records: list[dict[str, Any]] = []
    for threshold in (0.20, 0.30, 0.40, 0.50, 0.60):
        for budget in (1, 2, 3, 4):
            for fusion in ("rrf", "max"):
                for rrf_constant in ((20, 60) if fusion == "rrf" else (0,)):
                    orders, counts = policy_orders(threshold, budget, fusion, rrf_constant)
                    metrics = ranking_metrics(orders, claim_gold, question_gold, calibration)
                    mean_queries = float(np.mean([counts[index] for index in calibration]))
                    utility = metrics["question_coverage@10"] + 0.35 * metrics["recall_any@10"] + 0.20 * metrics["sufficient25@10"] + 0.05 * metrics["mrr"] - 0.005 * mean_queries
                    record = {"threshold": threshold, "budget": budget, "fusion": fusion, "rrf_constant": rrf_constant, "mean_queries": mean_queries, "utility": utility, **metrics}
                    grid_records.append(record)
                    if best is None or utility > best["utility"]:
                        best = record
    assert best is not None
    learned_orders, learned_counts = policy_orders(best["threshold"], best["budget"], best["fusion"], best["rrf_constant"])

    type_best: tuple[float, float] | None = None
    for threshold in np.linspace(0.15, 0.75, 25):
        metrics = evaluate_type_model(probabilities[calibration], weak_gold[calibration], float(threshold))
        if type_best is None or metrics["micro_f1"] > type_best[0]:
            type_best = (metrics["micro_f1"], float(threshold))
    assert type_best is not None

    results = {
        "dataset": "AVeriTeC", "train_claims": len(train_data), "dev_claims": len(dev_data), "candidate_passages": len(passages), "split_seed": SEED, "calibration_n": len(calibration), "heldout_n": len(heldout), "selected_policy": best,
        "type_model_calibration": evaluate_type_model(probabilities[calibration], weak_gold[calibration], type_best[1]),
        "type_model_heldout": evaluate_type_model(probabilities[heldout], weak_gold[heldout], type_best[1]),
        "calibration": {"bm25": ranking_metrics(baseline_orders, claim_gold, question_gold, calibration), "structured_v13": ranking_metrics(structured_orders, claim_gold, question_gold, calibration), "learned_policy": ranking_metrics(learned_orders, claim_gold, question_gold, calibration), "gold_question_oracle": ranking_metrics(gold_orders, claim_gold, question_gold, calibration)},
        "heldout": {"bm25": ranking_metrics(baseline_orders, claim_gold, question_gold, heldout), "structured_v13": ranking_metrics(structured_orders, claim_gold, question_gold, heldout), "learned_policy": ranking_metrics(learned_orders, claim_gold, question_gold, heldout), "gold_question_oracle": ranking_metrics(gold_orders, claim_gold, question_gold, heldout)},
        "heldout_bootstrap_learned_vs_bm25": bootstrap_differences(baseline_orders, learned_orders, claim_gold, question_gold, heldout),
        "mean_learned_queries_calibration": float(np.mean([learned_counts[index] for index in calibration])), "mean_learned_queries_heldout": float(np.mean([learned_counts[index] for index in heldout])),
        "authority": "SUPERVISED_INTERNAL_BENCHMARK_NOT_EXTERNAL_VALIDATION", "external_human_results": 0, "automatic_publication": False,
    }
    (output / "learned_question_benchmark_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (output / "policy_grid.json").write_text(json.dumps(grid_records, indent=2), encoding="utf-8")
    (output / "query_audit.jsonl").write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in query_audit) + "\n", encoding="utf-8")
    with (output / "heldout_indices.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["claim_index", "split", "learned_query_count"])
        writer.writeheader()
        calibration_set = set(calibration)
        for index in indices:
            writer.writerow({"claim_index": index, "split": "calibration" if index in calibration_set else "heldout", "learned_query_count": learned_counts[index]})
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", required=True, type=Path)
    parser.add_argument("--dev", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    train_data = json.loads(args.train.read_text(encoding="utf-8"))
    dev_data = json.loads(args.dev.read_text(encoding="utf-8"))
    results = run(train_data, dev_data, args.output)
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
