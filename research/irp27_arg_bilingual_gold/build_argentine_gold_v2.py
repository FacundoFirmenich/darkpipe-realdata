#!/usr/bin/env python3
"""Compatibility correction for the Argentine bilingual gold builder.

Preserves short numeric/measurement claims that would otherwise be discarded by
the generic sentence-length floor, while retaining the original upper bound and
all parsing, provenance, translation, assignment and authority semantics.
"""
from __future__ import annotations

import re

import build_argentine_gold as core


def sentence_split(text: str) -> list[str]:
    text = core.normalize(text)
    pieces = re.split(
        r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÜÑ0-9])|\s*[;]\s+(?=[A-ZÁÉÍÓÚÜÑ0-9])",
        text,
    )
    output: list[str] = []
    for piece in pieces:
        piece = core.normalize(piece)
        contains_measure = bool(
            re.search(r"\d+(?:[.,]\d+)?%?", piece)
            or any(term in core.canonical(piece) for term in core.MEASURE_TERMS)
        )
        minimum_length = 24 if contains_measure else 45
        if minimum_length <= len(piece) <= 700:
            output.append(piece)
    return output


core.sentence_split = sentence_split

# Re-export symbols used by tests and external validators.
Segment = core.Segment
annotation_schema = core.annotation_schema
facet_hints = core.facet_hints
mismatch_hints = core.mismatch_hints
normalize = core.normalize
select_claim_segments = core.select_claim_segments


if __name__ == "__main__":
    raise SystemExit(core.main())
