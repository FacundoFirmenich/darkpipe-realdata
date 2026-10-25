#!/usr/bin/env python3
"""IRP-27 Gate SOTA-007: selective evidence qualification and counterevidence.

The benchmark separates retrieval candidates from admissible evidence. It trains
simple, reproducible ternary claim–passage relation models on two public corpora:
CLIMATE-FEVER and SciFact. Promotion thresholds are calibrated on disjoint claim
splits using lower confidence bounds on directional precision. The held-out tests
measure relation quality, risk/coverage, claim-level aggregation, counterevidence
preservation and counterfactual-swap acceptance.

Important boundary: non-gold or swapped passages are diagnostic proxies. They are
not asserted to be false in the real world. Automatic publication is always false.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import tarfile
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.stats import beta
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.pipeline import FeatureUnion, Pipeline

SEED = 27
RNG = random.Random(SEED)
PAIR_LABELS = ("SUPPORT", "REFUTE", "NEUTRAL")
CLAIM_LABELS = ("SUPPORT", "REFUTE", "CONFLICTING", "INSUFFICIENT")


@dataclass(frozen=True)
class Pair:
    dataset: str
    claim_id: str
    claim: str
    evidence_id: str
    evidence: str
    label: str
    claim_label: str
    group: str


@dataclass(frozen=True)
class Threshold:
    relation: str
    probability: float | None
    margin: float | None
    calibration_n: int
    calibration_precision: float | None
    calibration_lower_95: float | None
    calibration_coverage: float
    target_lower_bound: float


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def pair_text(pair: Pair, evidence_only: bool = False) -> str:
    if evidence_only:
        return f"evidence: {pair.evidence}"
    return f"claim: {pair.claim}\nevidence: {pair.evidence}"


def build_model(evidence_only: bool = False) -> Pipeline:
    return Pipeline(
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
                                max_features=70_000,
                                sublinear_tf=True,
                                strip_accents="unicode",
                            ),
                        ),
                        (
                            "char",
                            TfidfVectorizer(
                                analyzer="char_wb",
                                ngram_range=(3, 5),
                                min_df=3,
                                max_features=70_000,
                                sublinear_tf=True,
                                strip_accents="unicode",
                            ),
                        ),
                    ]
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    max_iter=2_500,
                    class_weight="balanced",
                    solver="liblinear",
                    multi_class="ovr",
                    random_state=SEED,
                ),
            ),
        ]
    )


def lower_precision_bound(successes: int, total: int, alpha: float = 0.05) -> float:
    if total <= 0 or successes <= 0:
        return 0.0
    if successes == total:
        return float(beta.ppf(alpha, successes, 1))
    return float(beta.ppf(alpha, successes, total - successes + 1))


def upper_precision_bound(successes: int, total: int, alpha: float = 0.05) -> float:
    if total <= 0:
        return 1.0
    if successes == 0:
        return float(beta.ppf(1 - alpha, 1, total))
    return float(beta.ppf(1 - alpha, successes + 1, total - successes))


def fit_thresholds(
    probabilities: np.ndarray,
    labels: list[str],
    classes: list[str],
    target_lower_bound: float = 0.90,
    minimum_n: int = 15,
) -> dict[str, Threshold]:
    labels_array = np.asarray(labels)
    predicted_indices = probabilities.argmax(axis=1)
    predicted_labels = np.asarray([classes[index] for index in predicted_indices])
    sorted_probabilities = np.sort(probabilities, axis=1)
    margins = sorted_probabilities[:, -1] - sorted_probabilities[:, -2]
    output: dict[str, Threshold] = {}
    for relation in ("SUPPORT", "REFUTE"):
        relation_index = classes.index(relation)
        best: tuple[int, float, float, int, float, float] | None = None
        for probability_threshold in np.linspace(0.40, 0.995, 120):
            for margin_threshold in (0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30):
                accepted = (
                    (predicted_labels == relation)
                    & (probabilities[:, relation_index] >= probability_threshold)
                    & (margins >= margin_threshold)
                )
                total = int(accepted.sum())
                if total < minimum_n:
                    continue
                successes = int((labels_array[accepted] == relation).sum())
                precision = successes / total
                lower = lower_precision_bound(successes, total)
                if lower < target_lower_bound:
                    continue
                candidate = (
                    total,
                    precision,
                    lower,
                    -float(probability_threshold),
                    -float(margin_threshold),
                    successes,
                )
                if best is None or candidate > best:
                    best = candidate
                    best_parameters = (
                        float(probability_threshold),
                        float(margin_threshold),
                        total,
                        precision,
                        lower,
                    )
        if best is None:
            output[relation] = Threshold(
                relation,
                None,
                None,
                0,
                None,
                None,
                0.0,
                target_lower_bound,
            )
        else:
            probability_threshold, margin_threshold, total, precision, lower = best_parameters
            output[relation] = Threshold(
                relation,
                probability_threshold,
                margin_threshold,
                total,
                precision,
                lower,
                total / len(labels),
                target_lower_bound,
            )
    return output


def selective_predictions(
    probabilities: np.ndarray,
    classes: list[str],
    thresholds: dict[str, Threshold],
) -> list[str]:
    predicted_indices = probabilities.argmax(axis=1)
    predicted_labels = [classes[index] for index in predicted_indices]
    sorted_probabilities = np.sort(probabilities, axis=1)
    margins = sorted_probabilities[:, -1] - sorted_probabilities[:, -2]
    output: list[str] = []
    for row, relation in enumerate(predicted_labels):
        if relation not in {"SUPPORT", "REFUTE"}:
            output.append("ABSTAIN")
            continue
        threshold = thresholds[relation]
        if threshold.probability is None or threshold.margin is None:
            output.append("ABSTAIN")
            continue
        probability = probabilities[row, classes.index(relation)]
        if probability >= threshold.probability and margins[row] >= threshold.margin:
            output.append(relation)
        else:
            output.append("ABSTAIN")
    return output


def conformal_prediction_sets(
    calibration_probabilities: np.ndarray,
    calibration_labels: list[str],
    heldout_probabilities: np.ndarray,
    classes: list[str],
    alpha: float = 0.10,
) -> tuple[list[list[str]], float]:
    scores = np.asarray(
        [
            1.0 - calibration_probabilities[row, classes.index(label)]
            for row, label in enumerate(calibration_labels)
        ]
    )
    quantile_level = min(1.0, math.ceil((len(scores) + 1) * (1 - alpha)) / len(scores))
    qhat = float(np.quantile(scores, quantile_level, method="higher"))
    sets = [
        [classes[index] for index, probability in enumerate(row) if 1.0 - probability <= qhat]
        for row in heldout_probabilities
    ]
    return sets, qhat


def pair_metrics(
    gold: list[str],
    probabilities: np.ndarray,
    classes: list[str],
    selective: list[str],
    conformal_sets: list[list[str]],
) -> dict[str, Any]:
    argmax = [classes[index] for index in probabilities.argmax(axis=1)]
    accepted_indices = [index for index, label in enumerate(selective) if label != "ABSTAIN"]
    accepted_correct = sum(selective[index] == gold[index] for index in accepted_indices)
    accepted_directional_precision = (
        accepted_correct / len(accepted_indices) if accepted_indices else None
    )
    accepted_lower = (
        lower_precision_bound(accepted_correct, len(accepted_indices))
        if accepted_indices
        else None
    )
    conformal_coverage = np.mean(
        [label in prediction_set for label, prediction_set in zip(gold, conformal_sets)]
    )
    return {
        "n": len(gold),
        "label_distribution": dict(Counter(gold)),
        "argmax_macro_f1": float(f1_score(gold, argmax, labels=list(PAIR_LABELS), average="macro", zero_division=0)),
        "argmax_report": classification_report(
            gold,
            argmax,
            labels=list(PAIR_LABELS),
            output_dict=True,
            zero_division=0,
        ),
        "argmax_confusion": confusion_matrix(gold, argmax, labels=list(PAIR_LABELS)).tolist(),
        "selective_coverage": len(accepted_indices) / len(gold),
        "selective_directional_precision": accepted_directional_precision,
        "selective_directional_precision_lower_95": accepted_lower,
        "selective_directional_errors": len(accepted_indices) - accepted_correct,
        "conformal_marginal_coverage": float(conformal_coverage),
        "conformal_mean_set_size": float(np.mean([len(value) for value in conformal_sets])),
        "conformal_singleton_rate": float(np.mean([len(value) == 1 for value in conformal_sets])),
    }


def aggregate_claim_predictions(
    pairs: list[Pair],
    pair_predictions: list[str],
) -> tuple[dict[str, str], dict[str, str], dict[str, list[str]]]:
    by_claim_predictions: dict[str, list[str]] = defaultdict(list)
    gold: dict[str, str] = {}
    for pair, prediction in zip(pairs, pair_predictions):
        by_claim_predictions[pair.claim_id].append(prediction)
        gold[pair.claim_id] = pair.claim_label
    predicted: dict[str, str] = {}
    for claim_id, labels in by_claim_predictions.items():
        directional = {label for label in labels if label in {"SUPPORT", "REFUTE"}}
        if directional == {"SUPPORT", "REFUTE"}:
            predicted[claim_id] = "CONFLICTING"
        elif directional == {"SUPPORT"}:
            predicted[claim_id] = "SUPPORT"
        elif directional == {"REFUTE"}:
            predicted[claim_id] = "REFUTE"
        else:
            predicted[claim_id] = "INSUFFICIENT"
    return predicted, gold, by_claim_predictions


def claim_metrics(
    predicted: dict[str, str],
    gold: dict[str, str],
) -> dict[str, Any]:
    claim_ids = sorted(gold)
    y_true = [gold[claim_id] for claim_id in claim_ids]
    y_pred = [predicted[claim_id] for claim_id in claim_ids]
    conflicting_ids = [claim_id for claim_id in claim_ids if gold[claim_id] == "CONFLICTING"]
    unsafe = sum(
        predicted[claim_id] in {"SUPPORT", "REFUTE"}
        for claim_id in conflicting_ids
    )
    return {
        "n_claims": len(claim_ids),
        "gold_distribution": dict(Counter(y_true)),
        "prediction_distribution": dict(Counter(y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=list(CLAIM_LABELS), average="macro", zero_division=0)),
        "report": classification_report(
            y_true,
            y_pred,
            labels=list(CLAIM_LABELS),
            output_dict=True,
            zero_division=0,
        ),
        "confusion": confusion_matrix(y_true, y_pred, labels=list(CLAIM_LABELS)).tolist(),
        "conflicting_claims": len(conflicting_ids),
        "unsafe_directional_commitments_on_conflicting": unsafe,
        "unsafe_directional_commitment_rate": (
            unsafe / len(conflicting_ids) if conflicting_ids else None
        ),
    }


def counterfactual_swap_acceptance(
    pairs: list[Pair],
    model: Pipeline,
    classes: list[str],
    thresholds: dict[str, Threshold],
    evidence_only: bool = False,
) -> dict[str, Any]:
    rng = random.Random(SEED + 13)
    evidence_pool = list(pairs)
    swapped: list[Pair] = []
    for pair in pairs:
        candidate = rng.choice(evidence_pool)
        while candidate.claim_id == pair.claim_id:
            candidate = rng.choice(evidence_pool)
        swapped.append(
            Pair(
                pair.dataset,
                pair.claim_id,
                pair.claim,
                f"SWAP::{candidate.evidence_id}",
                candidate.evidence,
                "NEUTRAL_PROXY",
                pair.claim_label,
                pair.group,
            )
        )
    probabilities = model.predict_proba(
        [pair_text(pair, evidence_only=evidence_only) for pair in swapped]
    )
    predictions = selective_predictions(probabilities, classes, thresholds)
    accepted = sum(prediction in {"SUPPORT", "REFUTE"} for prediction in predictions)
    return {
        "n": len(swapped),
        "directional_acceptance_rate": accepted / len(swapped),
        "accepted": accepted,
        "interpretation": "COUNTERFACTUAL_SWAP_DIAGNOSTIC_PROXY_NOT_REAL_WORLD_FALSEHOOD",
    }


def risk_coverage_rows(
    gold: list[str],
    probabilities: np.ndarray,
    classes: list[str],
    dataset: str,
) -> list[dict[str, Any]]:
    predicted_indices = probabilities.argmax(axis=1)
    predicted_labels = np.asarray([classes[index] for index in predicted_indices])
    max_probability = probabilities.max(axis=1)
    output: list[dict[str, Any]] = []
    gold_array = np.asarray(gold)
    for threshold in np.linspace(0.40, 0.99, 60):
        accepted = (
            np.isin(predicted_labels, ["SUPPORT", "REFUTE"])
            & (max_probability >= threshold)
        )
        total = int(accepted.sum())
        if total == 0:
            continue
        successes = int((predicted_labels[accepted] == gold_array[accepted]).sum())
        output.append(
            {
                "dataset": dataset,
                "threshold": float(threshold),
                "coverage": total / len(gold),
                "precision": successes / total,
                "precision_lower_95": lower_precision_bound(successes, total),
                "errors": total - successes,
            }
        )
    return output


def load_climate(path: Path) -> tuple[list[Pair], list[Pair], list[Pair], dict[str, Any]]:
    rows = read_jsonl(path)
    ids = list(range(len(rows)))
    random.Random(SEED).shuffle(ids)
    train_end = int(0.70 * len(ids))
    calibration_end = int(0.85 * len(ids))
    split_indices = {
        "train": set(ids[:train_end]),
        "calibration": set(ids[train_end:calibration_end]),
        "heldout": set(ids[calibration_end:]),
    }
    pair_label_map = {
        "SUPPORTS": "SUPPORT",
        "REFUTES": "REFUTE",
        "NOT_ENOUGH_INFO": "NEUTRAL",
    }
    claim_label_map = {
        "SUPPORTS": "SUPPORT",
        "REFUTES": "REFUTE",
        "NOT_ENOUGH_INFO": "INSUFFICIENT",
        "DISPUTED": "CONFLICTING",
    }
    splits: dict[str, list[Pair]] = {name: [] for name in split_indices}
    for index, row in enumerate(rows):
        split = next(name for name, values in split_indices.items() if index in values)
        claim_label = claim_label_map[row["claim_label"]]
        for evidence in row["evidences"]:
            splits[split].append(
                Pair(
                    "CLIMATE_FEVER",
                    str(row["claim_id"]),
                    row["claim"],
                    evidence["evidence_id"],
                    evidence["evidence"],
                    pair_label_map[evidence["evidence_label"]],
                    claim_label,
                    evidence.get("article", ""),
                )
            )
    metadata = {
        "claims": len(rows),
        "pairs": sum(len(values) for values in splits.values()),
        "claim_labels": dict(Counter(row["claim_label"] for row in rows)),
        "split_claims": {name: len(values) for name, values in split_indices.items()},
        "split_pairs": {name: len(values) for name, values in splits.items()},
    }
    return splits["train"], splits["calibration"], splits["heldout"], metadata


def find_file(root: Path, name: str) -> Path:
    matches = list(root.rglob(name))
    if not matches:
        raise FileNotFoundError(name)
    return matches[0]


def lexical_overlap(claim: str, sentence: str) -> float:
    claim_tokens = set(claim.lower().split())
    sentence_tokens = set(sentence.lower().split())
    return len(claim_tokens & sentence_tokens) / max(1, len(claim_tokens | sentence_tokens))


def scifact_pairs_for_claim(
    claim_row: dict[str, Any],
    corpus: dict[int, dict[str, Any]],
    include_all_neutral: bool,
    neutral_limit: int = 5,
) -> list[Pair]:
    evidence_map = claim_row.get("evidence", {})
    sentence_relations: dict[tuple[int, int], str] = {}
    claim_relations: set[str] = set()
    for doc_id_string, rationales in evidence_map.items():
        doc_id = int(doc_id_string)
        for rationale in rationales:
            relation = "SUPPORT" if rationale["label"] == "SUPPORT" else "REFUTE"
            claim_relations.add(relation)
            for sentence_index in rationale["sentences"]:
                sentence_relations[(doc_id, int(sentence_index))] = relation
    if claim_relations == {"SUPPORT", "REFUTE"}:
        claim_label = "CONFLICTING"
    elif claim_relations == {"SUPPORT"}:
        claim_label = "SUPPORT"
    elif claim_relations == {"REFUTE"}:
        claim_label = "REFUTE"
    else:
        claim_label = "INSUFFICIENT"

    positive: list[Pair] = []
    neutral_candidates: list[tuple[float, Pair]] = []
    for doc_id in claim_row.get("cited_doc_ids", []):
        document = corpus.get(int(doc_id))
        if not document:
            continue
        group = f"{doc_id}::{document.get('title','')}"
        for sentence_index, sentence in enumerate(document.get("abstract", [])):
            relation = sentence_relations.get((int(doc_id), sentence_index), "NEUTRAL")
            pair = Pair(
                "SCIFACT",
                str(claim_row["id"]),
                claim_row["claim"],
                f"{doc_id}:{sentence_index}",
                sentence,
                relation,
                claim_label,
                group,
            )
            if relation == "NEUTRAL":
                neutral_candidates.append((lexical_overlap(claim_row["claim"], sentence), pair))
            else:
                positive.append(pair)
    if include_all_neutral:
        neutral = [pair for _, pair in neutral_candidates]
    else:
        neutral_candidates.sort(key=lambda item: item[0], reverse=True)
        neutral = [pair for _, pair in neutral_candidates[:neutral_limit]]
    return positive + neutral


def load_scifact(root: Path) -> tuple[list[Pair], list[Pair], list[Pair], dict[str, Any]]:
    corpus_rows = read_jsonl(find_file(root, "corpus.jsonl"))
    corpus = {int(row["doc_id"]): row for row in corpus_rows}
    train_claims = read_jsonl(find_file(root, "claims_train.jsonl"))
    dev_claims = read_jsonl(find_file(root, "claims_dev.jsonl"))
    train_indices = list(range(len(train_claims)))
    random.Random(SEED).shuffle(train_indices)
    calibration_count = max(1, int(0.20 * len(train_indices)))
    calibration_set = set(train_indices[:calibration_count])
    train_pairs: list[Pair] = []
    calibration_pairs: list[Pair] = []
    for index, claim in enumerate(train_claims):
        pairs = scifact_pairs_for_claim(
            claim,
            corpus,
            include_all_neutral=False,
            neutral_limit=5,
        )
        if index in calibration_set:
            calibration_pairs.extend(pairs)
        else:
            train_pairs.extend(pairs)
    heldout_pairs: list[Pair] = []
    for claim in dev_claims:
        heldout_pairs.extend(
            scifact_pairs_for_claim(
                claim,
                corpus,
                include_all_neutral=True,
            )
        )
    metadata = {
        "corpus_documents": len(corpus_rows),
        "train_claims": len(train_claims) - calibration_count,
        "calibration_claims": calibration_count,
        "heldout_claims": len(dev_claims),
        "train_pairs": len(train_pairs),
        "calibration_pairs": len(calibration_pairs),
        "heldout_pairs": len(heldout_pairs),
    }
    return train_pairs, calibration_pairs, heldout_pairs, metadata


def evaluate_dataset(
    name: str,
    train_pairs: list[Pair],
    calibration_pairs: list[Pair],
    heldout_pairs: list[Pair],
    output: Path,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    model = build_model(evidence_only=False)
    shortcut_model = build_model(evidence_only=True)
    model.fit([pair_text(pair) for pair in train_pairs], [pair.label for pair in train_pairs])
    shortcut_model.fit(
        [pair_text(pair, evidence_only=True) for pair in train_pairs],
        [pair.label for pair in train_pairs],
    )
    classes = list(model.named_steps["classifier"].classes_)
    shortcut_classes = list(shortcut_model.named_steps["classifier"].classes_)
    calibration_probabilities = model.predict_proba(
        [pair_text(pair) for pair in calibration_pairs]
    )
    heldout_probabilities = model.predict_proba(
        [pair_text(pair) for pair in heldout_pairs]
    )
    shortcut_probabilities = shortcut_model.predict_proba(
        [pair_text(pair, evidence_only=True) for pair in heldout_pairs]
    )
    thresholds = fit_thresholds(
        calibration_probabilities,
        [pair.label for pair in calibration_pairs],
        classes,
        target_lower_bound=0.90,
        minimum_n=max(10, int(0.01 * len(calibration_pairs))),
    )
    selective = selective_predictions(heldout_probabilities, classes, thresholds)
    conformal_sets, qhat = conformal_prediction_sets(
        calibration_probabilities,
        [pair.label for pair in calibration_pairs],
        heldout_probabilities,
        classes,
        alpha=0.10,
    )
    pair_result = pair_metrics(
        [pair.label for pair in heldout_pairs],
        heldout_probabilities,
        classes,
        selective,
        conformal_sets,
    )
    shortcut_argmax = [
        shortcut_classes[index] for index in shortcut_probabilities.argmax(axis=1)
    ]
    shortcut_macro_f1 = float(
        f1_score(
            [pair.label for pair in heldout_pairs],
            shortcut_argmax,
            labels=list(PAIR_LABELS),
            average="macro",
            zero_division=0,
        )
    )

    argmax_predictions = [classes[index] for index in heldout_probabilities.argmax(axis=1)]
    argmax_claim_pred, claim_gold, _ = aggregate_claim_predictions(
        heldout_pairs, argmax_predictions
    )
    selective_claim_pred, _, claim_pair_predictions = aggregate_claim_predictions(
        heldout_pairs, selective
    )
    claim_result_argmax = claim_metrics(argmax_claim_pred, claim_gold)
    claim_result_selective = claim_metrics(selective_claim_pred, claim_gold)

    swap = counterfactual_swap_acceptance(
        heldout_pairs, model, classes, thresholds, evidence_only=False
    )
    risk_rows = risk_coverage_rows(
        [pair.label for pair in heldout_pairs],
        heldout_probabilities,
        classes,
        name,
    )

    prediction_rows: list[dict[str, Any]] = []
    for index, pair in enumerate(heldout_pairs):
        row = {
            **asdict(pair),
            "argmax": argmax_predictions[index],
            "selective": selective[index],
            "conformal_set": " | ".join(conformal_sets[index]),
        }
        for class_index, relation in enumerate(classes):
            row[f"p_{relation.lower()}"] = float(
                heldout_probabilities[index, class_index]
            )
        prediction_rows.append(row)
    with (output / "heldout_pair_predictions.csv").open(
        "w", newline="", encoding="utf-8"
    ) as file:
        fields = list(prediction_rows[0])
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(prediction_rows)
    with (output / "heldout_claim_predictions.csv").open(
        "w", newline="", encoding="utf-8"
    ) as file:
        fields = [
            "claim_id",
            "gold",
            "argmax",
            "selective",
            "pair_predictions",
        ]
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for claim_id in sorted(claim_gold):
            writer.writerow(
                {
                    "claim_id": claim_id,
                    "gold": claim_gold[claim_id],
                    "argmax": argmax_claim_pred[claim_id],
                    "selective": selective_claim_pred[claim_id],
                    "pair_predictions": " | ".join(
                        claim_pair_predictions[claim_id]
                    ),
                }
            )
    with (output / "risk_coverage.csv").open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=list(risk_rows[0]))
        writer.writeheader()
        writer.writerows(risk_rows)

    result = {
        "dataset": name,
        "train_pairs": len(train_pairs),
        "calibration_pairs": len(calibration_pairs),
        "heldout_pairs": len(heldout_pairs),
        "classes": classes,
        "thresholds": {
            relation: asdict(threshold)
            for relation, threshold in thresholds.items()
        },
        "conformal_alpha": 0.10,
        "conformal_qhat": qhat,
        "pair_metrics": pair_result,
        "evidence_only_shortcut_macro_f1": shortcut_macro_f1,
        "claim_metrics_argmax": claim_result_argmax,
        "claim_metrics_selective": claim_result_selective,
        "counterfactual_swap": swap,
        "automatic_evidence_promotion": False,
    }
    (output / "results.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--climate", required=True, type=Path)
    parser.add_argument("--scifact-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    climate_train, climate_calibration, climate_heldout, climate_meta = load_climate(
        args.climate
    )
    scifact_train, scifact_calibration, scifact_heldout, scifact_meta = load_scifact(
        args.scifact_root
    )
    climate_result = evaluate_dataset(
        "CLIMATE_FEVER",
        climate_train,
        climate_calibration,
        climate_heldout,
        args.output / "climate_fever",
    )
    scifact_result = evaluate_dataset(
        "SCIFACT",
        scifact_train,
        scifact_calibration,
        scifact_heldout,
        args.output / "scifact",
    )
    status = {
        "gate": "IRP27-GATE-SELECTIVE-EVIDENCE-QUALIFICATION-AND-COUNTEREVIDENCE-007",
        "climate_metadata": climate_meta,
        "scifact_metadata": scifact_meta,
        "climate_pair_macro_f1": climate_result["pair_metrics"][
            "argmax_macro_f1"
        ],
        "climate_selective_precision": climate_result["pair_metrics"][
            "selective_directional_precision"
        ],
        "climate_selective_lower_95": climate_result["pair_metrics"][
            "selective_directional_precision_lower_95"
        ],
        "climate_conflict_directional_error": climate_result[
            "claim_metrics_selective"
        ]["unsafe_directional_commitment_rate"],
        "scifact_pair_macro_f1": scifact_result["pair_metrics"][
            "argmax_macro_f1"
        ],
        "scifact_selective_precision": scifact_result["pair_metrics"][
            "selective_directional_precision"
        ],
        "scifact_selective_lower_95": scifact_result["pair_metrics"][
            "selective_directional_precision_lower_95"
        ],
        "external_validation_completed": False,
        "open_web_validation_completed": False,
        "automatic_evidence_promotion": False,
        "automatic_publication": False,
        "authority": "INTERNAL_CLOSED_CORPUS_SELECTIVE_QUALIFICATION_PILOT",
    }
    (args.output / "status.json").write_text(
        json.dumps(status, indent=2), encoding="utf-8"
    )
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
