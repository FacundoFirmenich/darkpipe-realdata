#!/usr/bin/env python3
"""Validate triple annotations and prepare, but never silently create, gold labels.

Majority agreement is reported as a recommendation only. Any disagreement remains
PENDING_ADJUDICATION until a named adjudicator records a decision. The script
computes nominal Krippendorff alpha for relation, sufficiency, translation and
facet fields, preserving missing values and all annotator-level records.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

FIELDS = (
    "claim_relation",
    "sufficiency",
    "translation_fidelity",
    "defeater_type",
)
FACETS = (
    "ENTITY",
    "TIME",
    "GEOGRAPHY",
    "POPULATION",
    "DENOMINATOR",
    "MEASURE",
    "SOURCE_ROLE",
)


def read_json_or_jsonl(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    payload = json.loads(text)
    if isinstance(payload, list):
        return payload
    if "responses" in payload:
        return payload["responses"]
    raise ValueError(path)


def nominal_krippendorff(units: list[list[str | None]]) -> dict[str, Any]:
    usable = [[value for value in unit if value not in (None, "")] for unit in units]
    usable = [unit for unit in usable if len(unit) >= 2]
    if not usable:
        return {"alpha": None, "units": 0, "observed_disagreement": None, "expected_disagreement": None}

    observed_numerator = 0.0
    observed_denominator = 0.0
    category_counts: Counter[str] = Counter()
    for unit in usable:
        category_counts.update(unit)
        n = len(unit)
        observed_denominator += n * (n - 1)
        for category, count in Counter(unit).items():
            observed_numerator += count * (n - count)
    observed = observed_numerator / observed_denominator if observed_denominator else 0.0

    total = sum(category_counts.values())
    expected_numerator = sum(count * (total - count) for count in category_counts.values())
    expected_denominator = total * (total - 1)
    expected = expected_numerator / expected_denominator if expected_denominator else 0.0
    alpha = 1.0 - observed / expected if expected > 0 else 1.0
    return {
        "alpha": alpha,
        "units": len(usable),
        "observed_disagreement": observed,
        "expected_disagreement": expected,
        "categories": dict(category_counts),
    }


def recommendation(values: Iterable[str | None]) -> dict[str, Any]:
    clean = [value for value in values if value not in (None, "")]
    counts = Counter(clean)
    if not clean:
        return {"recommended": None, "agreement": "MISSING", "counts": {}}
    value, count = counts.most_common(1)[0]
    if len(clean) == 3 and count == 3:
        agreement = "UNANIMOUS"
    elif len(clean) == 3 and count == 2:
        agreement = "MAJORITY_2_OF_3"
    elif len(clean) < 3:
        agreement = "INCOMPLETE"
    else:
        agreement = "THREE_WAY_DISAGREEMENT"
    return {"recommended": value if count >= 2 else None, "agreement": agreement, "counts": dict(counts)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", required=True, type=Path)
    parser.add_argument("--assignments", required=True, type=Path)
    parser.add_argument("--responses", required=True, type=Path, nargs="+")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    pairs = {row["item_id"]: row for row in read_json_or_jsonl(args.pairs)}
    with args.assignments.open(encoding="utf-8") as file:
        assignments = list(csv.DictReader(file))
    expected = {row["assignment_id"]: row for row in assignments}

    responses: list[dict[str, Any]] = []
    for path in args.responses:
        responses.extend(read_json_or_jsonl(path))
    seen_assignments: set[str] = set()
    errors: list[dict[str, Any]] = []
    valid: list[dict[str, Any]] = []
    for response in responses:
        assignment_id = response.get("assignment_id")
        if assignment_id not in expected:
            errors.append({"assignment_id": assignment_id, "error": "UNKNOWN_ASSIGNMENT"})
            continue
        if assignment_id in seen_assignments:
            errors.append({"assignment_id": assignment_id, "error": "DUPLICATE_RESPONSE"})
            continue
        seen_assignments.add(assignment_id)
        expected_row = expected[assignment_id]
        if response.get("annotator_id") != expected_row["annotator_id"] or response.get("item_id") != expected_row["item_id"]:
            errors.append({"assignment_id": assignment_id, "error": "IDENTITY_MISMATCH"})
            continue
        seen_assignments.add(assignment_id)
        valid.append(response)

    by_item: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for response in valid:
        by_item[response["item_id"]].append(response)

    agreement_rows: list[dict[str, Any]] = []
    metric_units: dict[str, list[list[str | None]]] = defaultdict(list)
    pending = 0
    for item_id, pair in pairs.items():
        item_responses = by_item.get(item_id, [])
        row: dict[str, Any] = {
            "item_id": item_id,
            "claim_id": pair["claim_id"],
            "domain": pair["domain"],
            "responses": len(item_responses),
            "adjudication_status": "PENDING_ADJUDICATION",
            "gold_relation": "",
            "gold_sufficiency": "",
            "adjudicator": "",
        }
        for field in FIELDS:
            values = [response.get(field) for response in item_responses]
            rec = recommendation(values)
            row[f"{field}_recommendation"] = rec["recommended"] or ""
            row[f"{field}_agreement"] = rec["agreement"]
            row[f"{field}_counts"] = json.dumps(rec["counts"], ensure_ascii=False, sort_keys=True)
            metric_units[field].append(values)
        for facet in FACETS:
            values = [response.get("facet_alignment", {}).get(facet) for response in item_responses]
            rec = recommendation(values)
            row[f"facet_{facet}_recommendation"] = rec["recommended"] or ""
            row[f"facet_{facet}_agreement"] = rec["agreement"]
            metric_units[f"facet_{facet}"].append(values)
        if len(item_responses) != 3:
            row["blocking_reason"] = "TRIPLE_ANNOTATION_INCOMPLETE"
        elif any(row[f"{field}_agreement"] in {"THREE_WAY_DISAGREEMENT", "MISSING"} for field in FIELDS):
            row["blocking_reason"] = "RELATION_OR_SUFFICIENCY_DISAGREEMENT"
        else:
            row["blocking_reason"] = "HUMAN_ADJUDICATION_REQUIRED_EVEN_WITH_MAJORITY"
        pending += 1
        agreement_rows.append(row)

    metrics = {field: nominal_krippendorff(units) for field, units in metric_units.items()}
    status = {
        "pairs_expected": len(pairs),
        "assignments_expected": len(assignments),
        "responses_received": len(responses),
        "responses_valid": len(valid),
        "items_with_three_annotations": sum(len(by_item.get(item_id, [])) == 3 for item_id in pairs),
        "items_adjudicated": 0,
        "items_pending": pending,
        "gold_frozen": False,
        "automatic_majority_as_gold": False,
        "automatic_evidence_promotion": False,
        "errors": errors,
        "agreement": metrics,
    }
    fields = list(agreement_rows[0]) if agreement_rows else []
    with (args.output / "adjudication_queue.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(agreement_rows)
    (args.output / "agreement_report.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "validated_responses.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in valid) + ("\n" if valid else ""), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
