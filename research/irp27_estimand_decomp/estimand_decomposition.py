#!/usr/bin/env python3
"""IRP-27 Gate SOTA-004: estimand-preserving decomposition benchmark.

The engine preserves claim entities, quantities, time, source role and claim mode;
it generates typed search queries, compares them with a BM25 claim baseline on the
same AVeriTeC closed pool, calibrates a transparent router on a frozen half split,
and evaluates exactly once on the held-out half. It does not claim external validity.
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
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SPLIT_SEED = 27
STOP = set(
    "the a an in on at for to of and but or as if it this that there has have had been is are was were be being "
    "from by with during more than would could should now just fact check says said say claim claimed people "
    "government president administration current new all completely approximately because due result under over "
    "into about against after before when who what which why how yes no".split()
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
        self.avg_length = sum(map(len, documents)) / self.n
        self.term_frequencies = [Counter(document) for document in documents]
        document_frequency: Counter[str] = Counter()
        for document in documents:
            document_frequency.update(set(document))
        self.idf = {
            term: math.log(1 + (self.n - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in document_frequency.items()
        }

    def scores(self, query: list[str]) -> np.ndarray:
        output = np.zeros(self.n)
        for term in query:
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


def extract_entities(claim: str) -> list[str]:
    tokens: list[str] = []
    for match in re.finditer(
        r"\b[A-Z][A-Za-z0-9\'-]+(?:\s+[A-Z][A-Za-z0-9\'-]+){0,4}", claim
    ):
        tokens.extend(tokenize(match.group(0)))
    return list(dict.fromkeys(token for token in tokens if token not in STOP))[:12]


def extract_numbers(claim: str) -> list[str]:
    return re.findall(r"\d+(?:[.,]\d+)?%?", claim)


def content_terms(claim: str) -> list[str]:
    return [term for term in tokenize(claim) if term not in STOP and len(term) > 2]


def claim_contract(item: dict[str, Any]) -> dict[str, Any]:
    claim = item["claim"].strip()
    types = item.get("claim_types") or []
    folded = fold(claim)
    return {
        "claim": claim,
        "entities": extract_entities(claim),
        "quantities": extract_numbers(claim),
        "speaker": item.get("speaker") or None,
        "time": item.get("claim_date") or None,
        "claim_types": types,
        "is_numeric": bool(extract_numbers(claim) or "Numerical Claim" in types),
        "is_quote": bool("Quote Verification" in types or re.search(r"\b(said|says|declared|announced)\b", folded)),
        "is_universal": bool(re.search(r"\b(all|every|completely|never|none|unprecedented)\b", folded)),
        "is_causal": bool(re.search(r"\b(because|due to|causes?|results? in|leads? to|as a result)\b", folded)),
        "is_event": bool(re.search(r"\b(approved|banned|charged|declared|imposed|increased|decreased|joined|joining|died|killed|privatized|refused)\b", folded)),
    }


def validate_contract(contract: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    claim_folded = fold(contract["claim"])
    for number in contract["quantities"]:
        if fold(number) not in claim_folded:
            issues.append(f"quantity_not_grounded:{number}")
    for entity in contract["entities"]:
        if entity not in tokenize(contract["claim"]):
            issues.append(f"entity_not_grounded:{entity}")
    return issues


def generate_queries(item: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    contract = claim_contract(item)
    claim = contract["claim"]
    entities = contract["entities"]
    quantities = contract["quantities"]
    terms = content_terms(claim)
    speaker = contract["speaker"] or ""
    time = contract["time"] or ""
    queries: list[tuple[str, str, float]] = [("claim", claim, 1.0)]

    context = " ".join(([speaker] if speaker else []) + entities + quantities + ([time] if time else []) + terms[:16])
    if context:
        queries.append(("context", context, 0.90))
    if contract["is_numeric"]:
        queries.append(("numeric_estimand", " ".join(["amount", "value", "percentage", "number"] + entities + quantities + terms[:12] + ([time] if time else [])), 0.95))
    if contract["is_quote"]:
        queries.append(("quote_provenance", " ".join(["quote", "transcript", "said", "source"] + ([speaker] if speaker else []) + entities + terms[:14]), 0.95))
    if contract["is_universal"]:
        queries.append(("scope_exception", " ".join(["scope", "exception", "all", "evidence"] + entities + terms[:14]), 0.85))
    if contract["is_causal"]:
        queries.append(("causal_contrast", " ".join(["cause", "effect", "evidence", "alternative"] + entities + terms[:14]), 0.90))
    if contract["is_event"]:
        queries.append(("event_provenance", " ".join(["event", "official", "source"] + entities + terms[:16] + ([time] if time else [])), 0.90))

    deduplicated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for query_type, text, weight in queries:
        text = " ".join(text.split())
        key = fold(text)
        if text and key not in seen:
            seen.add(key)
            deduplicated.append({"query_type": query_type, "text": text, "weight": weight})
    return contract, deduplicated[:6]


def first_relevant_rank(order: np.ndarray, relevant: set[int]) -> int:
    for rank, index in enumerate(order, start=1):
        if int(index) in relevant:
            return rank
    return 10**9


def metric_bundle(orders: list[np.ndarray], gold: list[set[int]], indices: list[int]) -> dict[str, float]:
    output: dict[str, float] = {}
    for cutoff in (1, 5, 10):
        output[f"recall@{cutoff}"] = sum(
            any(int(index) in gold[item] for index in orders[item][:cutoff]) for item in indices
        ) / len(indices)
    reciprocal_rank = 0.0
    for item in indices:
        rank = first_relevant_rank(orders[item], gold[item])
        reciprocal_rank += 0.0 if rank >= 10**9 else 1.0 / rank
    output["mrr"] = reciprocal_rank / len(indices)
    return output


def run(data: list[dict[str, Any]], output_directory: Path) -> dict[str, Any]:
    passages: list[str] = []
    gold: list[set[int]] = []
    for item in data:
        relevant: set[int] = set()
        for question in item["questions"]:
            for answer in question.get("answers", []):
                text = (answer.get("answer") or "").strip()
                if answer.get("answer_type") == "Unanswerable" or text.startswith("No, There is not enough information."):
                    continue
                relevant.add(len(passages))
                passages.append(text)
        gold.append(relevant)

    bm25 = BM25([tokenize(passage) for passage in passages])
    baseline_orders: list[np.ndarray] = []
    structured_orders: list[np.ndarray] = []
    contracts: list[dict[str, Any]] = []
    query_records: list[dict[str, Any]] = []
    router_features: list[list[float]] = []
    router_labels: list[int] = []

    for item_index, item in enumerate(data):
        baseline_scores = bm25.scores(tokenize(item["claim"]))
        baseline_order = np.argsort(baseline_scores)[::-1]
        contract, queries = generate_queries(item)
        contract_issues = validate_contract(contract)
        if contract_issues:
            raise ValueError({"item": item_index, "issues": contract_issues})

        score_vectors: list[np.ndarray] = []
        for query in queries:
            scores = bm25.scores(tokenize(query["text"]))
            maximum = float(scores.max()) or 1.0
            score_vectors.append(float(query["weight"]) * scores / maximum)
        structured_scores = np.max(np.vstack(score_vectors), axis=0)
        structured_order = np.argsort(structured_scores)[::-1]

        baseline_orders.append(baseline_order)
        structured_orders.append(structured_order)
        contracts.append(contract)
        baseline_rank = first_relevant_rank(baseline_order, gold[item_index])
        structured_rank = first_relevant_rank(structured_order, gold[item_index])
        router_labels.append(int(structured_rank < baseline_rank))
        top = float(baseline_scores[baseline_order[0]])
        second = float(baseline_scores[baseline_order[1]]) if len(baseline_order) > 1 else 0.0
        router_features.append([
            len(tokenize(item["claim"])),
            len(contract["entities"]),
            len(contract["quantities"]),
            int(contract["is_numeric"]),
            int(contract["is_quote"]),
            int(contract["is_event"]),
            int(contract["is_universal"]),
            int(contract["is_causal"]),
            top,
            top - second,
            len(queries),
        ])
        query_records.append({
            "claim_index": item_index,
            "claim": item["claim"],
            "contract": contract,
            "queries": queries,
            "baseline_first_relevant_rank": None if baseline_rank >= 10**9 else baseline_rank,
            "structured_first_relevant_rank": None if structured_rank >= 10**9 else structured_rank,
        })

    random.seed(SPLIT_SEED)
    indices = list(range(len(data)))
    random.shuffle(indices)
    calibration = indices[: len(indices) // 2]
    heldout = indices[len(indices) // 2 :]
    features = np.asarray(router_features, dtype=float)
    labels = np.asarray(router_labels, dtype=int)
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced", random_state=SPLIT_SEED))
    model.fit(features[calibration], labels[calibration])
    probabilities = model.predict_proba(features)[:, 1]

    best: tuple[float, float] | None = None
    for threshold in np.linspace(0.05, 0.95, 91):
        routed = [structured_orders[index] if probabilities[index] >= threshold else baseline_orders[index] for index in range(len(data))]
        metrics = metric_bundle(routed, gold, calibration)
        utility = metrics["recall@10"] + 0.3 * metrics["recall@5"] + 0.1 * metrics["mrr"]
        if best is None or utility > best[0]:
            best = (utility, float(threshold))
    assert best is not None
    threshold = best[1]
    routed_orders = [structured_orders[index] if probabilities[index] >= threshold else baseline_orders[index] for index in range(len(data))]

    result = {
        "dataset": "AVeriTeC-dev",
        "claims": len(data),
        "candidate_passages": len(passages),
        "split_seed": SPLIT_SEED,
        "calibration_n": len(calibration),
        "heldout_n": len(heldout),
        "router_threshold": threshold,
        "structured_selected_calibration": int(sum(probabilities[calibration] >= threshold)),
        "structured_selected_heldout": int(sum(probabilities[heldout] >= threshold)),
        "baseline_calibration": metric_bundle(baseline_orders, gold, calibration),
        "structured_calibration": metric_bundle(structured_orders, gold, calibration),
        "routed_calibration": metric_bundle(routed_orders, gold, calibration),
        "baseline_heldout": metric_bundle(baseline_orders, gold, heldout),
        "structured_heldout": metric_bundle(structured_orders, gold, heldout),
        "routed_heldout": metric_bundle(routed_orders, gold, heldout),
        "baseline_all": metric_bundle(baseline_orders, gold, indices),
        "structured_all": metric_bundle(structured_orders, gold, indices),
        "routed_all": metric_bundle(routed_orders, gold, indices),
        "authority": "HELDOUT_INTERNAL_PILOT_NOT_EXTERNAL_VALIDATION",
    }

    rng = np.random.default_rng(SPLIT_SEED)
    comparisons: list[dict[str, Any]] = []
    for name, orders in (("structured", structured_orders), ("routed", routed_orders)):
        for metric, cutoff in (("recall@1", 1), ("recall@5", 5), ("recall@10", 10)):
            baseline_vector = np.asarray([int(any(int(x) in gold[item] for x in baseline_orders[item][:cutoff])) for item in heldout])
            alternative_vector = np.asarray([int(any(int(x) in gold[item] for x in orders[item][:cutoff])) for item in heldout])
            difference = alternative_vector - baseline_vector
            bootstrap = np.asarray([
                difference[rng.integers(0, len(difference), len(difference))].mean() for _ in range(10000)
            ])
            comparisons.append({
                "comparison": f"{name}-baseline",
                "metric": metric,
                "difference": float(difference.mean()),
                "ci_low": float(np.quantile(bootstrap, 0.025)),
                "ci_high": float(np.quantile(bootstrap, 0.975)),
                "wins": int(sum(difference > 0)),
                "losses": int(sum(difference < 0)),
                "ties": int(sum(difference == 0)),
            })

    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "estimand_decomposition_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (output_directory / "paired_bootstrap.json").write_text(json.dumps(comparisons, indent=2), encoding="utf-8")
    (output_directory / "query_records.jsonl").write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in query_records) + "\n", encoding="utf-8")
    with (output_directory / "router_predictions.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["claim_index", "split", "probability_structured", "selected_structured", "baseline_rank", "structured_rank"])
        writer.writeheader()
        calibration_set = set(calibration)
        for index, record in enumerate(query_records):
            writer.writerow({
                "claim_index": index,
                "split": "calibration" if index in calibration_set else "heldout",
                "probability_structured": f"{probabilities[index]:.8f}",
                "selected_structured": int(probabilities[index] >= threshold),
                "baseline_rank": record["baseline_first_relevant_rank"],
                "structured_rank": record["structured_first_relevant_rank"],
            })
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    result = run(data, args.output)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
