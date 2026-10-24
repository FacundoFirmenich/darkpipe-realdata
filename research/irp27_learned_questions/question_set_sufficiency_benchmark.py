#!/usr/bin/env python3
"""IRP-27 Gate SOTA-006: minimal verification-question sets and evidence sufficiency.

This benchmark extends the held-out policy from SOTA-005 in four ways:
1. presupposition-free, role-typed verification questions;
2. greedy consolidation into a minimal, non-redundant question set;
3. learned answerability and question–passage compatibility models trained only
   from observed AVeriTeC annotations and observed cross-claim passages;
4. explicit evidence states and a closed-pool false-attachment proxy.

The benchmark is internal and closed-pool. Non-gold passages are treated as
non-reference attachments, not as proven false real-world evidence.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.pipeline import FeatureUnion, Pipeline

import learned_question_benchmark_v2 as learned_v2

core = learned_v2.core
LABELS = tuple(core.LABELS)
SEED = 27
RNG = random.Random(SEED)


@dataclass
class PairExample:
    claim_index: int
    text: str
    label: int


def answerable_answers(question: dict[str, Any]) -> list[str]:
    output: list[str] = []
    for answer in question.get("answers", []):
        text = (answer.get("answer") or "").strip()
        if answer.get("answer_type") == "Unanswerable":
            continue
        if not text or text.startswith("No answer could be found"):
            continue
        output.append(text)
    return output


def is_answerable(question: dict[str, Any]) -> bool:
    return bool(answerable_answers(question))


def normalized_tokens(text: str) -> set[str]:
    return {
        token
        for token in core.tokenize(text)
        if token not in core.STOP and len(token) > 2
    }


def jaccard(left: set[Any], right: set[Any]) -> float:
    return len(left & right) / len(left | right) if left | right else 0.0


def build_answerability_examples(data: list[dict[str, Any]]) -> list[PairExample]:
    examples: list[PairExample] = []
    for claim_index, item in enumerate(data):
        for question in item.get("questions", []):
            text = f"claim: {item.get('claim','')}\nquestion: {question.get('question','')}"
            examples.append(PairExample(claim_index, text, int(is_answerable(question))))
    return examples


def observed_passages(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for claim_index, item in enumerate(data):
        for question_index, question in enumerate(item.get("questions", [])):
            roles = sorted(learned_v2.question_labels(question.get("question", "")))
            for passage in answerable_answers(question):
                rows.append(
                    {
                        "claim_index": claim_index,
                        "question_index": question_index,
                        "question": question.get("question", ""),
                        "roles": roles,
                        "passage": passage,
                        "token_set": normalized_tokens(passage),
                    }
                )
    return rows


def pair_text(claim: str, question: str, passage: str) -> str:
    return f"claim: {claim}\nquestion: {question}\npassage: {passage}"


def hard_negative_index(
    question: str,
    own_claim: int,
    rows: list[dict[str, Any]],
    rng: random.Random,
    candidate_count: int = 14,
) -> int:
    qtokens = normalized_tokens(question)
    candidates: list[int] = []
    while len(candidates) < candidate_count:
        index = rng.randrange(len(rows))
        if rows[index]["claim_index"] != own_claim and index not in candidates:
            candidates.append(index)
    return max(candidates, key=lambda index: jaccard(qtokens, rows[index]["token_set"]))


def build_compatibility_examples(
    data: list[dict[str, Any]],
    max_positives: int | None = None,
) -> list[PairExample]:
    rows = observed_passages(data)
    rng = random.Random(SEED)
    positive_indices = list(range(len(rows)))
    if max_positives is not None and len(positive_indices) > max_positives:
        rng.shuffle(positive_indices)
        positive_indices = positive_indices[:max_positives]
    examples: list[PairExample] = []
    for index in positive_indices:
        row = rows[index]
        claim = data[row["claim_index"]].get("claim", "")
        examples.append(
            PairExample(
                row["claim_index"],
                pair_text(claim, row["question"], row["passage"]),
                1,
            )
        )
        negative_index = hard_negative_index(
            row["question"], row["claim_index"], rows, rng
        )
        negative = rows[negative_index]
        examples.append(
            PairExample(
                row["claim_index"],
                pair_text(claim, row["question"], negative["passage"]),
                0,
            )
        )
    return examples


def fit_text_classifier(
    examples: list[PairExample],
    classifier: Any,
    word_features: int = 70_000,
    char_features: int = 70_000,
) -> Pipeline:
    pipeline = Pipeline(
        [
            (
                "features",
                FeatureUnion(
                    [
                        (
                            "word",
                            TfidfVectorizer(
                                ngram_range=(1, 2),
                                min_df=2,
                                max_features=word_features,
                                sublinear_tf=True,
                            ),
                        ),
                        (
                            "char",
                            TfidfVectorizer(
                                analyzer="char_wb",
                                ngram_range=(3, 5),
                                min_df=3,
                                max_features=char_features,
                                sublinear_tf=True,
                            ),
                        ),
                    ]
                ),
            ),
            ("classifier", classifier),
        ]
    )
    pipeline.fit([example.text for example in examples], [example.label for example in examples])
    return pipeline


def tune_binary_threshold(
    probabilities: np.ndarray,
    labels: np.ndarray,
) -> tuple[float, dict[str, float]]:
    best: tuple[float, float, dict[str, float]] | None = None
    for threshold in np.linspace(0.20, 0.80, 61):
        predicted = probabilities >= threshold
        precision, recall, f1, _ = precision_recall_fscore_support(
            labels, predicted, average="binary", zero_division=0
        )
        false_positive_rate = float(
            np.mean(predicted[labels == 0]) if np.any(labels == 0) else 0.0
        )
        utility = f1 - 0.25 * false_positive_rate
        record = {
            "threshold": float(threshold),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "false_positive_rate": false_positive_rate,
            "utility": float(utility),
        }
        if best is None or utility > best[0]:
            best = (utility, float(threshold), record)
    assert best is not None
    return best[1], best[2]


def evaluate_binary_model(
    model: Pipeline,
    examples: list[PairExample],
    calibration_claims: set[int],
    heldout_claims: set[int],
) -> dict[str, Any]:
    texts = [example.text for example in examples]
    labels = np.asarray([example.label for example in examples], dtype=int)
    claims = np.asarray([example.claim_index for example in examples], dtype=int)
    probabilities = model.predict_proba(texts)[:, 1]
    calibration_mask = np.asarray([claim in calibration_claims for claim in claims])
    heldout_mask = np.asarray([claim in heldout_claims for claim in claims])
    threshold, calibration = tune_binary_threshold(
        probabilities[calibration_mask], labels[calibration_mask]
    )

    def metrics(mask: np.ndarray) -> dict[str, float]:
        y = labels[mask]
        p = probabilities[mask]
        predicted = p >= threshold
        precision, recall, f1, _ = precision_recall_fscore_support(
            y, predicted, average="binary", zero_division=0
        )
        return {
            "n": int(mask.sum()),
            "prevalence": float(y.mean()),
            "threshold": threshold,
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "average_precision": float(average_precision_score(y, p)),
            "roc_auc": float(roc_auc_score(y, p)),
            "false_positive_rate": float(
                np.mean(predicted[y == 0]) if np.any(y == 0) else 0.0
            ),
        }

    return {
        "calibration_choice": calibration,
        "calibration": metrics(calibration_mask),
        "heldout": metrics(heldout_mask),
    }


def verification_question(role: str, item: dict[str, Any]) -> str:
    claim = item.get("claim", "").strip()
    speaker = item.get("speaker") or "the attributed actor"
    templates = {
        "NUMERIC": f"What value, percentage, unit, denominator and period are established for the numerical assertion in: {claim}?",
        "ATTRIBUTION": f"What primary record, if any, shows that {speaker} made the attributed statement in: {claim}?",
        "TEMPORAL": f"What date or period is established for the event or measurement described in: {claim}?",
        "LOCATION": f"What location or jurisdiction is established by reliable sources for: {claim}?",
        "SOURCE_PROVENANCE": f"What primary source, if any, documents the assertion: {claim}?",
        "DEFINITION_CONTEXT": f"How are the central terms in this assertion defined in the relevant source context: {claim}?",
        "EVENT_EXISTENCE": f"What evidence, if any, shows that the event or property described here occurred: {claim}?",
        "CAUSAL_MECHANISM": f"What evidence distinguishes the alleged cause from plausible alternatives in: {claim}?",
        "COMPARISON": f"What comparable measurements, baselines and periods support the comparison in: {claim}?",
        "SCOPE_EXCEPTION": f"Does this assertion hold across its stated scope, and what documented exceptions exist: {claim}?",
    }
    return templates[role]


def search_query(role: str, item: dict[str, Any]) -> str:
    claim = item.get("claim", "")
    contract = learned_v2.query_contract(item)
    entities = contract.get("entities", [])
    numbers = contract.get("numbers", [])
    terms = learned_v2.core.content_terms(claim, 16)
    speaker = [item.get("speaker")] if item.get("speaker") else []
    date = [item.get("claim_date")] if item.get("claim_date") else []
    additions = {
        "NUMERIC": ["value", "percentage", "denominator", "unit"],
        "ATTRIBUTION": ["transcript", "quote", "primary", "source"],
        "TEMPORAL": ["date", "period", "timeline"],
        "LOCATION": ["location", "jurisdiction"],
        "SOURCE_PROVENANCE": ["official", "primary", "report", "source"],
        "DEFINITION_CONTEXT": ["definition", "context"],
        "EVENT_EXISTENCE": ["official", "record", "evidence"],
        "CAUSAL_MECHANISM": ["cause", "effect", "alternative", "evidence"],
        "COMPARISON": ["comparison", "baseline", "period"],
        "SCOPE_EXCEPTION": ["scope", "exceptions"],
    }
    return " ".join(
        str(value)
        for value in entities + numbers + speaker + date + terms + additions[role]
        if value
    )


def build_dev_pool(
    data: list[dict[str, Any]],
) -> tuple[
    list[str],
    list[set[int]],
    list[list[set[int]]],
    list[dict[str, set[int]]],
    list[set[str]],
    list[int],
]:
    passages: list[str] = []
    claim_gold: list[set[int]] = []
    question_gold: list[list[set[int]]] = []
    role_gold: list[dict[str, set[int]]] = []
    role_labels: list[set[str]] = []
    answerable_counts: list[int] = []
    for item in data:
        cset: set[int] = set()
        qsets: list[set[int]] = []
        rsets: dict[str, set[int]] = defaultdict(set)
        rlabels: set[str] = set()
        answerable_count = 0
        for question in item.get("questions", []):
            roles = learned_v2.question_labels(question.get("question", ""))
            rlabels.update(roles)
            qset: set[int] = set()
            answers = answerable_answers(question)
            if answers:
                answerable_count += 1
            for text in answers:
                index = len(passages)
                passages.append(text)
                qset.add(index)
                cset.add(index)
                for role in roles:
                    rsets[role].add(index)
            if qset:
                qsets.append(qset)
        claim_gold.append(cset)
        question_gold.append(qsets)
        role_gold.append(dict(rsets))
        role_labels.append(rlabels)
        answerable_counts.append(answerable_count)
    return (
        passages,
        claim_gold,
        question_gold,
        role_gold,
        role_labels,
        answerable_counts,
    )


def normalize_scores(scores: np.ndarray) -> np.ndarray:
    maximum = float(scores.max())
    return scores / maximum if maximum else scores


def rrf_scores(
    rankings: list[np.ndarray],
    weights: list[float],
    size: int,
    constant: int = 60,
) -> np.ndarray:
    output = np.zeros(size, dtype=float)
    for ranking, weight in zip(rankings, weights):
        positions = np.empty(size, dtype=int)
        positions[ranking] = np.arange(1, size + 1)
        output += weight / (constant + positions)
    return output


def select_roles(
    claim_index: int,
    probabilities: np.ndarray,
    answerability_probabilities: dict[tuple[int, str], float],
    role_orders: list[dict[str, np.ndarray]],
    role_questions: list[dict[str, str]],
    threshold: float,
    answerability_threshold: float,
    budget: int,
    minimum_utility: float,
) -> list[str]:
    candidates: list[tuple[float, str]] = []
    for role_index, role in enumerate(LABELS):
        probability = float(probabilities[claim_index, role_index])
        answerability = answerability_probabilities[(claim_index, role)]
        if probability < threshold or answerability < answerability_threshold:
            continue
        candidates.append((probability * answerability, role))
    candidates.sort(key=lambda row: (-row[0], LABELS.index(row[1])))
    selected: list[str] = []
    for base_score, role in candidates:
        if len(selected) >= budget:
            break
        qtokens = normalized_tokens(role_questions[claim_index][role])
        rset = set(map(int, role_orders[claim_index][role][:10]))
        redundancy = 0.0
        for previous in selected:
            lexical = jaccard(
                qtokens,
                normalized_tokens(role_questions[claim_index][previous]),
            )
            retrieval = jaccard(
                rset,
                set(map(int, role_orders[claim_index][previous][:10])),
            )
            redundancy = max(redundancy, 0.5 * lexical + 0.5 * retrieval)
        utility = base_score * (1.0 - redundancy)
        if utility >= minimum_utility:
            selected.append(role)
    return selected


def fused_ranking(
    claim_scores: np.ndarray,
    selected: list[str],
    role_scores: dict[str, np.ndarray],
    probabilities: np.ndarray,
    claim_index: int,
    fusion: str,
) -> tuple[np.ndarray, np.ndarray]:
    vectors = [claim_scores]
    weights = [1.0]
    rankings = [np.argsort(claim_scores)[::-1]]
    for role in selected:
        role_index = LABELS.index(role)
        vectors.append(role_scores[role])
        weights.append(max(0.15, float(probabilities[claim_index, role_index])))
        rankings.append(np.argsort(role_scores[role])[::-1])
    if fusion == "rrf":
        scores = rrf_scores(rankings, weights, len(claim_scores))
    else:
        scores = np.max(
            np.vstack(
                [weight * normalize_scores(vector) for vector, weight in zip(vectors, weights)]
            ),
            axis=0,
        )
    return np.argsort(scores)[::-1], scores


def rerank_with_compatibility(
    order: np.ndarray,
    retrieval_scores: np.ndarray,
    claim_index: int,
    selected: list[str],
    compatibility: dict[tuple[int, str, int], float],
    alpha: float,
    candidate_depth: int = 30,
) -> np.ndarray:
    if alpha <= 0:
        return order
    roles = selected or ["CLAIM"]
    candidates = list(map(int, order[:candidate_depth]))
    base = normalize_scores(retrieval_scores)
    rescored = []
    for passage_index in candidates:
        probability = max(
            compatibility.get((claim_index, role, passage_index), 0.0)
            for role in roles
        )
        rescored.append((float(base[passage_index] + alpha * probability), passage_index))
    rescored.sort(reverse=True)
    head = [index for _, index in rescored]
    head_set = set(head)
    tail = [int(index) for index in order if int(index) not in head_set]
    return np.asarray(head + tail, dtype=int)


def evidence_state(
    item: dict[str, Any],
    question_coverage: float,
    exact_any: bool,
    predicted_false_attachment: bool,
    answerable_count: int,
) -> str:
    if answerable_count == 0:
        return "UNANSWERABLE"
    if not exact_any and predicted_false_attachment:
        return "FALSE_SUPPORT"
    if not exact_any:
        return "NO_EVIDENCE"
    if question_coverage < 0.25:
        return "RELATED"
    if question_coverage < 0.50:
        return "PARTIALLY_SUPPORTING"
    label = fold(item.get("label", ""))
    if "refut" in label:
        return "COUNTEREVIDENCE"
    if "support" in label:
        return "SUFFICIENT"
    if "conflict" in label or "cherry" in label:
        return "CONFLICTING"
    return "PARTIALLY_SUPPORTING"


def method_metrics(
    orders: list[np.ndarray],
    selected_roles: list[list[str]],
    data: list[dict[str, Any]],
    claim_gold: list[set[int]],
    question_gold: list[list[set[int]]],
    role_gold: list[dict[str, set[int]]],
    answerable_counts: list[int],
    role_orders: list[dict[str, np.ndarray]],
    compatibility: dict[tuple[int, str, int], float],
    compatibility_threshold: float,
    indices: list[int],
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    attachment_true = 0
    attachment_false = 0
    false_support_claims = 0
    for claim_index in indices:
        top10 = set(map(int, orders[claim_index][:10]))
        qsets = question_gold[claim_index]
        qcoverage = (
            sum(bool(top10 & qset) for qset in qsets) / len(qsets)
            if qsets
            else 0.0
        )
        exact_any = bool(top10 & claim_gold[claim_index])
        predicted_true = 0
        predicted_false = 0
        for role in selected_roles[claim_index]:
            gold_set = role_gold[claim_index].get(role, set())
            for passage_index in map(int, role_orders[claim_index][role][:5]):
                probability = compatibility.get(
                    (claim_index, role, passage_index), 0.0
                )
                if probability < compatibility_threshold:
                    continue
                if passage_index in gold_set:
                    predicted_true += 1
                else:
                    predicted_false += 1
        attachment_true += predicted_true
        attachment_false += predicted_false
        false_support = predicted_false > 0 and predicted_true == 0 and not exact_any
        false_support_claims += int(false_support)
        records.append(
            {
                "claim_index": claim_index,
                "label": data[claim_index].get("label", ""),
                "selected_roles": " | ".join(selected_roles[claim_index]),
                "question_coverage_10": qcoverage,
                "exact_any_10": int(exact_any),
                "predicted_true_attachments": predicted_true,
                "predicted_false_attachments": predicted_false,
                "state": evidence_state(
                    data[claim_index],
                    qcoverage,
                    exact_any,
                    false_support,
                    answerable_counts[claim_index],
                ),
            }
        )
    total_attachments = attachment_true + attachment_false
    return (
        {
            "recall_any@10": float(
                np.mean([record["exact_any_10"] for record in records])
            ),
            "question_coverage@10": float(
                np.mean([record["question_coverage_10"] for record in records])
            ),
            "sufficient25@10": float(
                np.mean(
                    [record["question_coverage_10"] >= 0.25 for record in records]
                )
            ),
            "sufficient50@10": float(
                np.mean(
                    [record["question_coverage_10"] >= 0.50 for record in records]
                )
            ),
            "attachment_precision_proxy": (
                attachment_true / total_attachments if total_attachments else 0.0
            ),
            "closed_pool_false_attachment_rate": (
                attachment_false / total_attachments if total_attachments else 0.0
            ),
            "false_support_claim_rate": false_support_claims / len(indices),
            "mean_queries": float(
                np.mean([len(selected_roles[index]) for index in indices])
            ),
        },
        records,
    )


def bootstrap_differences(
    baseline_records: list[dict[str, Any]],
    alternative_records: list[dict[str, Any]],
    iterations: int = 10_000,
) -> list[dict[str, Any]]:
    rng = np.random.default_rng(SEED)
    baseline = {record["claim_index"]: record for record in baseline_records}
    alternative = {record["claim_index"]: record for record in alternative_records}
    indices = sorted(baseline)
    metrics = {
        "recall_any@10": lambda record: float(record["exact_any_10"]),
        "question_coverage@10": lambda record: float(
            record["question_coverage_10"]
        ),
        "sufficient50@10": lambda record: float(
            record["question_coverage_10"] >= 0.50
        ),
        "false_support_claim_rate": lambda record: float(
            record["state"] == "FALSE_SUPPORT"
        ),
    }
    output: list[dict[str, Any]] = []
    for name, function in metrics.items():
        difference = np.asarray(
            [
                function(alternative[index]) - function(baseline[index])
                for index in indices
            ]
        )
        samples = np.asarray(
            [
                difference[
                    rng.integers(0, len(difference), len(difference))
                ].mean()
                for _ in range(iterations)
            ]
        )
        output.append(
            {
                "metric": name,
                "difference": float(difference.mean()),
                "ci_low": float(np.quantile(samples, 0.025)),
                "ci_high": float(np.quantile(samples, 0.975)),
                "wins": int(sum(difference > 0)),
                "losses": int(sum(difference < 0)),
                "ties": int(sum(difference == 0)),
            }
        )
    return output


def run(
    train_data: list[dict[str, Any]],
    dev_data: list[dict[str, Any]],
    output: Path,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    indices = list(range(len(dev_data)))
    random.Random(SEED).shuffle(indices)
    calibration = indices[: len(indices) // 2]
    heldout = indices[len(indices) // 2 :]
    calibration_set = set(calibration)
    heldout_set = set(heldout)

    type_features, type_model = core.train_type_model(train_data)
    type_probabilities = type_model.predict_proba(
        type_features.transform([item.get("claim", "") for item in dev_data])
    )

    answerability_train = build_answerability_examples(train_data)
    answerability_model = fit_text_classifier(
        answerability_train,
        LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            solver="liblinear",
            random_state=SEED,
        ),
        word_features=45_000,
        char_features=45_000,
    )
    answerability_dev = build_answerability_examples(dev_data)
    answerability_report = evaluate_binary_model(
        answerability_model,
        answerability_dev,
        calibration_set,
        heldout_set,
    )

    compatibility_train = build_compatibility_examples(
        train_data, max_positives=14_000
    )
    compatibility_model = fit_text_classifier(
        compatibility_train,
        SGDClassifier(
            loss="log_loss",
            alpha=1e-5,
            max_iter=1200,
            tol=1e-4,
            class_weight="balanced",
            random_state=SEED,
        ),
        word_features=65_000,
        char_features=65_000,
    )
    compatibility_dev = build_compatibility_examples(dev_data)
    compatibility_report = evaluate_binary_model(
        compatibility_model,
        compatibility_dev,
        calibration_set,
        heldout_set,
    )
    compatibility_threshold = compatibility_report["calibration_choice"][
        "threshold"
    ]

    (
        passages,
        claim_gold,
        question_gold,
        role_gold,
        role_labels,
        answerable_counts,
    ) = build_dev_pool(dev_data)
    bm25 = core.BM25([core.tokenize(passage) for passage in passages])

    claim_scores: list[np.ndarray] = []
    claim_orders: list[np.ndarray] = []
    role_scores: list[dict[str, np.ndarray]] = []
    role_orders: list[dict[str, np.ndarray]] = []
    role_questions: list[dict[str, str]] = []
    answerability_probabilities: dict[tuple[int, str], float] = {}

    answerability_texts: list[str] = []
    answerability_keys: list[tuple[int, str]] = []
    for claim_index, item in enumerate(dev_data):
        cscore = bm25.scores(core.tokenize(item.get("claim", "")))
        claim_scores.append(cscore)
        claim_orders.append(np.argsort(cscore)[::-1])
        score_map: dict[str, np.ndarray] = {}
        order_map: dict[str, np.ndarray] = {}
        question_map: dict[str, str] = {}
        for role in LABELS:
            question = verification_question(role, item)
            query = search_query(role, item)
            scores = bm25.scores(core.tokenize(query))
            score_map[role] = scores
            order_map[role] = np.argsort(scores)[::-1]
            question_map[role] = question
            answerability_texts.append(
                f"claim: {item.get('claim','')}\nquestion: {question}"
            )
            answerability_keys.append((claim_index, role))
        role_scores.append(score_map)
        role_orders.append(order_map)
        role_questions.append(question_map)
    generated_answerability = answerability_model.predict_proba(
        answerability_texts
    )[:, 1]
    for key, probability in zip(
        answerability_keys, generated_answerability
    ):
        answerability_probabilities[key] = float(probability)

    compatibility: dict[tuple[int, str, int], float] = {}
    compatibility_texts: list[str] = []
    compatibility_keys: list[tuple[int, str, int]] = []
    for claim_index, item in enumerate(dev_data):
        union = set(map(int, claim_orders[claim_index][:20]))
        for role in LABELS:
            union.update(map(int, role_orders[claim_index][role][:12]))
        roles = ["CLAIM"] + list(LABELS)
        for role in roles:
            question = (
                f"What evidence, if any, bears on this claim: {item.get('claim','')}?"
                if role == "CLAIM"
                else role_questions[claim_index][role]
            )
            for passage_index in union:
                compatibility_texts.append(
                    pair_text(
                        item.get("claim", ""),
                        question,
                        passages[passage_index],
                    )
                )
                compatibility_keys.append(
                    (claim_index, role, passage_index)
                )
    compatibility_probabilities = compatibility_model.predict_proba(
        compatibility_texts
    )[:, 1]
    for key, probability in zip(
        compatibility_keys, compatibility_probabilities
    ):
        compatibility[key] = float(probability)

    baseline_selected = [[] for _ in dev_data]
    baseline_metrics_cal, _ = method_metrics(
        claim_orders,
        baseline_selected,
        dev_data,
        claim_gold,
        question_gold,
        role_gold,
        answerable_counts,
        role_orders,
        compatibility,
        compatibility_threshold,
        calibration,
    )

    policy_grid: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    cached: dict[
        tuple[float, float, int, float, str, float],
        tuple[list[np.ndarray], list[list[str]], list[np.ndarray]],
    ] = {}

    def build_policy(
        threshold: float,
        answerability_threshold: float,
        budget: int,
        minimum_utility: float,
        fusion: str,
        alpha: float,
    ) -> tuple[list[np.ndarray], list[list[str]], list[np.ndarray]]:
        key = (
            threshold,
            answerability_threshold,
            budget,
            minimum_utility,
            fusion,
            alpha,
        )
        if key in cached:
            return cached[key]
        orders: list[np.ndarray] = []
        selected_all: list[list[str]] = []
        score_vectors: list[np.ndarray] = []
        for claim_index in range(len(dev_data)):
            selected = select_roles(
                claim_index,
                type_probabilities,
                answerability_probabilities,
                role_orders,
                role_questions,
                threshold,
                answerability_threshold,
                budget,
                minimum_utility,
            )
            order, scores = fused_ranking(
                claim_scores[claim_index],
                selected,
                role_scores[claim_index],
                type_probabilities,
                claim_index,
                fusion,
            )
            order = rerank_with_compatibility(
                order,
                scores,
                claim_index,
                selected,
                compatibility,
                alpha,
            )
            orders.append(order)
            selected_all.append(selected)
            score_vectors.append(scores)
        cached[key] = (orders, selected_all, score_vectors)
        return cached[key]

    for threshold in (0.40, 0.50, 0.60):
        for answerability_threshold in (0.25, 0.50):
            for budget in (1, 2, 3):
                for minimum_utility in (0.20, 0.30):
                    for fusion in ("max", "rrf"):
                        for alpha in (0.0, 0.40):
                            orders, selected_all, _ = build_policy(
                                threshold,
                                answerability_threshold,
                                budget,
                                minimum_utility,
                                fusion,
                                alpha,
                            )
                            metrics, _ = method_metrics(
                                orders,
                                selected_all,
                                dev_data,
                                claim_gold,
                                question_gold,
                                role_gold,
                                answerable_counts,
                                role_orders,
                                compatibility,
                                compatibility_threshold,
                                calibration,
                            )
                            utility = (
                                metrics["question_coverage@10"]
                                + 0.35 * metrics["sufficient50@10"]
                                + 0.20 * metrics["recall_any@10"]
                                + 0.10
                                * metrics["attachment_precision_proxy"]
                                - 0.50
                                * metrics["false_support_claim_rate"]
                                - 0.01 * metrics["mean_queries"]
                            )
                            record = {
                                "threshold": threshold,
                                "answerability_threshold": answerability_threshold,
                                "budget": budget,
                                "minimum_utility": minimum_utility,
                                "fusion": fusion,
                                "compatibility_alpha": alpha,
                                "utility": utility,
                                **metrics,
                            }
                            policy_grid.append(record)
                            if best is None or utility > best["utility"]:
                                best = record
    assert best is not None

    selected_orders, selected_roles, _ = build_policy(
        best["threshold"],
        best["answerability_threshold"],
        best["budget"],
        best["minimum_utility"],
        best["fusion"],
        best["compatibility_alpha"],
    )

    baseline_metrics, baseline_records = method_metrics(
        claim_orders,
        baseline_selected,
        dev_data,
        claim_gold,
        question_gold,
        role_gold,
        answerable_counts,
        role_orders,
        compatibility,
        compatibility_threshold,
        heldout,
    )
    selected_metrics, selected_records = method_metrics(
        selected_orders,
        selected_roles,
        dev_data,
        claim_gold,
        question_gold,
        role_gold,
        answerable_counts,
        role_orders,
        compatibility,
        compatibility_threshold,
        heldout,
    )

    result = {
        "dataset": "AVeriTeC",
        "train_claims": len(train_data),
        "dev_claims": len(dev_data),
        "candidate_passages": len(passages),
        "calibration_n": len(calibration),
        "heldout_n": len(heldout),
        "selected_policy": best,
        "answerability_model": answerability_report,
        "compatibility_model": compatibility_report,
        "compatibility_threshold": compatibility_threshold,
        "calibration_bm25": baseline_metrics_cal,
        "heldout_bm25": baseline_metrics,
        "heldout_question_set": selected_metrics,
        "heldout_bootstrap_vs_bm25": bootstrap_differences(
            baseline_records, selected_records
        ),
        "state_distribution": dict(
            Counter(record["state"] for record in selected_records)
        ),
        "selected_role_distribution": dict(
            Counter(
                role
                for index in heldout
                for role in selected_roles[index]
            )
        ),
        "authority": "INTERNAL_CLOSED_POOL_PILOT_NOT_EXTERNAL_VALIDATION",
        "closed_pool_non_gold_is_not_proven_false_evidence": True,
        "human_pilot_responses": 0,
        "automatic_publication": False,
    }

    (output / "gate_sota006_results.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    (output / "policy_grid.json").write_text(
        json.dumps(policy_grid, indent=2), encoding="utf-8"
    )
    (output / "answerability_report.json").write_text(
        json.dumps(answerability_report, indent=2), encoding="utf-8"
    )
    (output / "compatibility_report.json").write_text(
        json.dumps(compatibility_report, indent=2), encoding="utf-8"
    )
    with (output / "heldout_claim_states.csv").open(
        "w", newline="", encoding="utf-8"
    ) as file:
        fields = list(selected_records[0])
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(selected_records)
    (output / "question_sets.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "claim_index": index,
                    "claim": dev_data[index].get("claim", ""),
                    "selected_roles": selected_roles[index],
                    "questions": [
                        role_questions[index][role]
                        for role in selected_roles[index]
                    ],
                    "search_queries": [
                        search_query(role, dev_data[index])
                        for role in selected_roles[index]
                    ],
                },
                ensure_ascii=False,
            )
            for index in heldout
        )
        + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", required=True, type=Path)
    parser.add_argument("--dev", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    train_data = json.loads(args.train.read_text(encoding="utf-8"))
    dev_data = json.loads(args.dev.read_text(encoding="utf-8"))
    result = run(train_data, dev_data, args.output)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
