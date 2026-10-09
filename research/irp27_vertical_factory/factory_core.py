#!/usr/bin/env python3
"""IRP-27 Vertical Factory core.

Shared fail-closed validation, audit and promotion logic for evidence-first
political-computational verticals. The module never publishes automatically.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import argparse
import json
from pathlib import Path

REQUIRED_ROLES = (
    "data_steward",
    "legal_reviewer",
    "statistical_reviewer",
    "policy_authority",
    "publication_authority",
)
STATES = (
    "SPECIFIED",
    "SOURCE_MATERIALIZED",
    "MEASURED",
    "CLAIM_BOUND",
    "SIMULABLE",
    "OPERATIVE_SHADOW",
    "HUMAN_SIGNED",
    "PUBLISHED",
)
FACT_TYPES = {"FACT", "CONTRAST", "COMPUTABLE_RULE"}
MATERIALIZED_SOURCE_STATES = {
    "RAW_BYTES_ARCHIVED_HASHED_PARSED",
    "RAW_BYTES_ARCHIVED",
    "REMOTE_VERIFIED",
}


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str
    severity: str = "ERROR"


@dataclass(frozen=True)
class PromotionDecision:
    current: str
    requested: str
    allowed: bool
    blockers: tuple[str, ...]


def load_spec(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate(spec: dict) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    required = (
        "schema_version", "vertical_id", "release", "authority", "sources",
        "metrics", "claims", "rules", "outputs", "forbidden_inferences", "actions",
    )
    for field in required:
        if field not in spec:
            issues.append(ValidationIssue("MISSING_FIELD", field, f"Missing {field}"))

    authority = spec.get("authority", {})
    if authority.get("automatic_publication") is not False:
        issues.append(ValidationIssue(
            "AUTO_PUBLICATION", "authority.automatic_publication", "Must be false"
        ))
    signatures = authority.get("signatures", {})
    for role in REQUIRED_ROLES:
        if role not in signatures:
            issues.append(ValidationIssue(
                "MISSING_ROLE", f"authority.signatures.{role}", "Role absent"
            ))

    sources = {row.get("source_id") for row in spec.get("sources", [])}
    metrics = {row.get("metric_id"): row for row in spec.get("metrics", [])}
    claim_ids: set[str | None] = set()
    for index, claim in enumerate(spec.get("claims", [])):
        claim_id = claim.get("claim_id")
        if claim_id in claim_ids:
            issues.append(ValidationIssue("DUPLICATE_CLAIM", f"claims[{index}]", str(claim_id)))
        claim_ids.add(claim_id)
        if claim.get("type") in FACT_TYPES and not claim.get("support"):
            issues.append(ValidationIssue(
                "UNSUPPORTED_FACT", f"claims[{index}].support", str(claim_id)
            ))
        for support in claim.get("support", []):
            if support not in metrics and support not in claim_ids and support not in sources:
                issues.append(ValidationIssue(
                    "UNKNOWN_SUPPORT", f"claims[{index}].support", str(support)
                ))

    for index, metric in enumerate(spec.get("metrics", [])):
        if metric.get("source_id") not in sources:
            issues.append(ValidationIssue(
                "UNKNOWN_SOURCE", f"metrics[{index}].source_id", str(metric.get("source_id"))
            ))

    if authority.get("causal_authority") is False:
        for index, rule in enumerate(spec.get("rules", [])):
            if str(rule.get("authority", "")).startswith("CAUSAL"):
                issues.append(ValidationIssue(
                    "CAUSAL_LEAK", f"rules[{index}].authority", str(rule.get("rule_id"))
                ))

    if not spec.get("forbidden_inferences"):
        issues.append(ValidationIssue(
            "NO_FORBIDDEN_INFERENCES", "forbidden_inferences", "At least one is required"
        ))
    return issues


def assess_promotion(spec: dict, requested: str) -> PromotionDecision:
    current = spec.get("release", {}).get("status", "SPECIFIED")
    blockers: list[str] = []
    if requested not in STATES:
        blockers.append("UNKNOWN_STATE")

    requires_sources = requested in STATES[1:]
    if requires_sources:
        if not spec.get("sources"):
            blockers.append("NO_SOURCES")
        if any(
            source.get("retrieval_state") not in MATERIALIZED_SOURCE_STATES
            for source in spec.get("sources", [])
        ):
            blockers.append("UNMATERIALIZED_SOURCE")

    if requested in STATES[2:] and not spec.get("metrics"):
        blockers.append("NO_METRICS")
    if requested in STATES[3:] and not spec.get("claims"):
        blockers.append("NO_CLAIMS")
    if requested in STATES[4:] and not spec.get("rules"):
        blockers.append("NO_RULES")
    if requested in {"HUMAN_SIGNED", "PUBLISHED"}:
        missing = [name for name, value in spec.get("authority", {}).get("signatures", {}).items() if not value]
        if missing:
            blockers.append("MISSING_SIGNATURES:" + ",".join(missing))
    if requested == "PUBLISHED" and spec.get("authority", {}).get("automatic_publication") is not False:
        blockers.append("AUTO_PUBLICATION_MUST_REMAIN_FALSE")
    return PromotionDecision(current, requested, not blockers, tuple(blockers))


def audit(spec: dict) -> dict:
    return {
        "vertical_id": spec.get("vertical_id"),
        "release": spec.get("release"),
        "source_states": dict(Counter(s.get("retrieval_state", "UNKNOWN") for s in spec.get("sources", []))),
        "claim_states": dict(Counter(c.get("status", "UNKNOWN") for c in spec.get("claims", []))),
        "metrics": len(spec.get("metrics", [])),
        "timeseries": len(spec.get("timeseries", [])),
        "claims": len(spec.get("claims", [])),
        "rules": len(spec.get("rules", [])),
        "forbidden_inferences": len(spec.get("forbidden_inferences", [])),
        "automatic_publication": spec.get("authority", {}).get("automatic_publication"),
        "causal_authority": spec.get("authority", {}).get("causal_authority"),
        "programmatic_authority": spec.get("authority", {}).get("programmatic_authority"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="irp27-factory")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "audit"):
        command = sub.add_parser(name)
        command.add_argument("spec")
    promote = sub.add_parser("promote")
    promote.add_argument("spec")
    promote.add_argument("state")
    args = parser.parse_args()
    spec = load_spec(args.spec)

    if args.command == "validate":
        issues = validate(spec)
        print(json.dumps([asdict(issue) for issue in issues], ensure_ascii=False, indent=2))
        return 1 if any(issue.severity == "ERROR" for issue in issues) else 0
    if args.command == "audit":
        print(json.dumps(audit(spec), ensure_ascii=False, indent=2))
        return 0
    decision = assess_promotion(spec, args.state)
    print(json.dumps(asdict(decision), ensure_ascii=False, indent=2))
    return 0 if decision.allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
