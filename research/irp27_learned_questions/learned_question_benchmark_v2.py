#!/usr/bin/env python3
"""Corrected compatibility layer for Gate SOTA-005.

This module patches the initial benchmark implementation so temporal years are
recognized, metadata dates are admissible, numeric tokens are not duplicated as
bare content terms, and multi-token entity queries are validated token-wise.
"""
from __future__ import annotations

import re
from typing import Any

import learned_question_benchmark as core

_ORIGINAL_QUESTION_LABELS = core.question_labels


def question_labels(question: str) -> set[str]:
    labels = set(_ORIGINAL_QUESTION_LABELS(question))
    if re.search(r"\b(?:19|20)\d{2}\b", core.fold(question)):
        labels.add("TEMPORAL")
    return labels


def content_terms(text: str, limit: int = 16) -> list[str]:
    terms = [
        term
        for term in core.tokenize(text)
        if term not in core.STOP and len(term) > 2 and not term.isdigit()
    ]
    return list(dict.fromkeys(terms))[:limit]


def validate_query(text: str, contract: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    allowed_numbers = set(core.extract_numbers(contract["claim"])) | set(
        core.extract_numbers(contract.get("date") or "")
    )
    for number in core.extract_numbers(text):
        if number not in allowed_numbers:
            issues.append(f"invented_number:{number}")

    allowed_tokens = (
        set(core.tokenize(contract["claim"]))
        | set(core.tokenize(contract.get("speaker") or ""))
        | set(core.tokenize(contract.get("date") or ""))
        | {
            "official", "report", "transcript", "record", "quote", "source",
            "location", "definition", "context", "cause", "effect", "alternative",
            "evidence", "comparison", "scope", "exceptions",
        }
    )
    for entity in core.extract_entities(text):
        if not set(core.tokenize(entity)).issubset(allowed_tokens):
            issues.append(f"invented_entity:{entity}")
    return issues


# Patch globals used by functions defined in the core module.
core.question_labels = question_labels
core.content_terms = content_terms
core.validate_query = validate_query

# Re-export the tested public API.
LABELS = core.LABELS
claim_type_labels = core.claim_type_labels
learned_queries = core.learned_queries
query_contract = core.query_contract
extract_numbers = core.extract_numbers
extract_entities = core.extract_entities


def main() -> int:
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
