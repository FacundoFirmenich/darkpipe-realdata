#!/usr/bin/env python3
"""IRP-27 Gate 016: fail-closed ResponseOps package validator.

A package is a governed response object, not merely copy. It must preserve the
narrow fact, strongest opposing argument, mandatory concession, contrast-source
lineage, output family, revocation triggers, and human publication boundary.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

OUTPUT_FORMATS = {
    "30_seconds",
    "3_minutes",
    "fact_check",
    "debate_card",
    "technical_dossier",
    "ai_grounding",
    "steelman",
    "revocation_note",
}
REQUIRED_SIGNATURES = {
    "data_steward",
    "domain_reviewer",
    "statistical_reviewer",
    "policy_authority",
    "publication_authority",
}


@dataclass(frozen=True)
class Issue:
    code: str
    path: str
    message: str


def validate_package(package: dict[str, Any], known_sources: set[str]) -> list[Issue]:
    issues: list[Issue] = []
    pid = package.get("package_id", "<unknown>")
    if set(package.get("outputs", {})) != OUTPUT_FORMATS:
        issues.append(Issue("OUTPUT_FAMILY", f"{pid}.outputs", "Eight canonical outputs are required"))
    if not package.get("steelman"):
        issues.append(Issue("NO_STEELMAN", f"{pid}.steelman", "Strongest defensible opposing case is required"))
    if not package.get("mandatory_concession"):
        issues.append(Issue("NO_CONCESSION", f"{pid}.mandatory_concession", "Supported narrow facts require a concession"))
    source_block = package.get("sources", {})
    if not source_block.get("primary"):
        issues.append(Issue("NO_PRIMARY_SOURCE", f"{pid}.sources.primary", "At least one primary source is required"))
    if not source_block.get("contrast"):
        issues.append(Issue("NO_CONTRAST_SOURCE", f"{pid}.sources.contrast", "At least one contrast source is required"))
    for source_id in source_block.get("primary", []) + source_block.get("contrast", []):
        if source_id not in known_sources:
            issues.append(Issue("UNKNOWN_SOURCE", f"{pid}.sources", source_id))
    authority = package.get("authority", {})
    if authority.get("automatic_publication") is not False:
        issues.append(Issue("AUTO_PUBLICATION", f"{pid}.authority", "Must be false"))
    if set(authority.get("required_signatures", [])) != REQUIRED_SIGNATURES:
        issues.append(Issue("SIGNATURE_SET", f"{pid}.authority.required_signatures", "Five canonical roles are required"))
    blocked = package.get("blocked_wording", "")
    if blocked:
        for output_name, output in package.get("outputs", {}).items():
            text = str(output)
            if blocked in text:
                issues.append(Issue("BLOCKED_WORDING_LEAK", f"{pid}.outputs.{output_name}", blocked))
    if not package.get("revocation_triggers"):
        issues.append(Issue("NO_REVOCATION", f"{pid}.revocation_triggers", "At least one trigger is required"))
    return issues


def validate_corpus(packages: Iterable[dict[str, Any]], sources: Iterable[dict[str, Any]]) -> list[Issue]:
    packages = list(packages)
    sources = list(sources)
    known_sources = {row["source_id"] for row in sources}
    issues: list[Issue] = []
    ids = [row.get("package_id") for row in packages]
    for package_id, count in Counter(ids).items():
        if count != 1:
            issues.append(Issue("DUPLICATE_PACKAGE", "packages", str(package_id)))
    for package in packages:
        issues.extend(validate_package(package, known_sources))
    return issues


def release_decision(package: dict[str, Any], signatures: dict[str, str | None]) -> dict[str, Any]:
    """A package can be signed only by all named roles; publication stays manual."""
    missing = sorted(role for role in REQUIRED_SIGNATURES if not signatures.get(role))
    blockers = []
    if package.get("authority", {}).get("automatic_publication") is not False:
        blockers.append("AUTOMATIC_PUBLICATION_MUST_BE_FALSE")
    if missing:
        blockers.append("MISSING_SIGNATURES:" + ",".join(missing))
    return {
        "package_id": package.get("package_id"),
        "current_status": package.get("authority", {}).get("status", "UNSIGNED_SHADOW"),
        "human_signed": not missing,
        "publication_authorized": False,
        "blockers": blockers,
    }


def evaluation_manifest(packages: Iterable[dict[str, Any]]) -> dict[str, Any]:
    packages = list(packages)
    return {
        "packages": len(packages),
        "prompts": len(packages) * 6,
        "scorers": [
            "scope_fidelity",
            "citation_entailment",
            "steelman_fidelity",
            "abstention",
            "causal_restraint",
            "revocation_clarity",
        ],
        "multi_provider_execution": "NOT_EXECUTED",
        "judge_authority": "ADVISORY_ONLY",
        "automatic_promotion": False,
    }
