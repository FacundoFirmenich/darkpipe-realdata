#!/usr/bin/env python3
"""IRP-27 Lean Decision Governance companion runtime.

The statistical runtime computes typed signal diagnostics, exact risk bounds,
routes decision proposals, and emits append-only receipts. It deliberately does
not confer permission, authority, execution, or publication power on a model.
Those boundaries are duplicated in the Lean proof kernel.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from scipy.stats import beta


class GovernanceError(ValueError):
    pass


class Provider(str, Enum):
    JEV = "jev"
    LAYA = "laya"
    NIMBLE = "nimble"
    OPENJEV = "openjev"
    DETERMINISTIC = "deterministic"
    OTHER = "other"


class Primitive(str, Enum):
    CHOICE = "choice"
    SCORE = "score"
    NOUL = "noul"


class EvidenceState(str, Enum):
    CANDIDATE = "candidate"
    CONTEXT = "context"
    SUPPORT = "support"
    REFUTE = "refute"
    CONFLICTING = "conflicting"
    INSUFFICIENT = "insufficient"


class Route(str, Enum):
    BLOCKED_PREREQUISITE = "BLOCKED_PREREQUISITE"
    ABSTAIN = "ABSTAIN"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    QUALIFIED_AWAITING_AUTHORITY = "QUALIFIED_AWAITING_AUTHORITY"
    AUTHORIZED_AWAITING_LEASE = "AUTHORIZED_AWAITING_LEASE"
    READY_TO_EXECUTE = "READY_TO_EXECUTE"


class PublicationRoute(str, Enum):
    BLOCKED = "BLOCKED"
    READY_FOR_EXPLICIT_HUMAN_PUBLICATION = "READY_FOR_EXPLICIT_HUMAN_PUBLICATION"


@dataclass(frozen=True)
class TypedSignal:
    primitive: Primitive
    labels: tuple[str, ...]
    probabilities: tuple[float, ...]
    selected_index: int | None = None
    score: float | None = None
    noul_probability: float | None = None

    def validate(self) -> None:
        if self.primitive is Primitive.NOUL:
            if self.labels or self.probabilities or self.selected_index is not None or self.score is not None:
                raise GovernanceError("A Noul carries only the probability of yes")
            if self.noul_probability is None or not 0.0 <= self.noul_probability <= 1.0:
                raise GovernanceError("Noul probability must be in [0,1]")
            return

        if len(self.labels) < 2 or len(self.labels) != len(self.probabilities):
            raise GovernanceError("Choice/Score labels and probabilities must align")
        if any(probability < 0.0 or probability > 1.0 for probability in self.probabilities):
            raise GovernanceError("Probabilities must be in [0,1]")
        if not math.isclose(sum(self.probabilities), 1.0, abs_tol=1e-6):
            raise GovernanceError("Choice/Score probabilities must sum to one")

        if self.primitive is Primitive.CHOICE:
            if self.selected_index is None or not 0 <= self.selected_index < len(self.labels):
                raise GovernanceError("Choice requires a valid selected_index")
            if self.score is not None or self.noul_probability is not None:
                raise GovernanceError("Choice cannot carry Score or Noul semantics")
        elif self.primitive is Primitive.SCORE:
            if self.score is None or not 0.0 <= self.score <= len(self.labels) - 1:
                raise GovernanceError("Score must lie on the declared levels")
            if self.selected_index is not None or self.noul_probability is not None:
                raise GovernanceError("Score cannot carry Choice or Noul semantics")

    def diagnostics(self) -> dict[str, float | str]:
        self.validate()
        if self.primitive is Primitive.NOUL:
            assert self.noul_probability is not None
            p = self.noul_probability
            return {
                "primitive": self.primitive.value,
                "p_yes": p,
                "confidence_distance_from_half": abs(2.0 * p - 1.0),
                "semantic_warning": "probability_of_yes_not_degree",
            }

        probabilities = self.probabilities
        n = len(probabilities)
        maximum = max(probabilities)
        ordered = sorted(probabilities, reverse=True)
        entropy = -sum(p * math.log(p) for p in probabilities if p > 0)
        normalized_entropy = entropy / math.log(n)
        result: dict[str, float | str] = {
            "primitive": self.primitive.value,
            "max_probability": maximum,
            "margin": ordered[0] - ordered[1],
            "normalized_entropy": normalized_entropy,
            "derived_concentration": 1.0 - normalized_entropy,
        }
        if self.primitive is Primitive.CHOICE:
            result["choice_confidence"] = max(
                0.0,
                min(1.0, (maximum - 1.0 / n) / (1.0 - 1.0 / n)),
            )
        else:
            result["semantic_warning"] = "score_is_position_on_declared_levels"
        return result


@dataclass(frozen=True)
class Provenance:
    provider: Provider
    model_version: str
    question_id: str
    state_sha256: str
    response_sha256: str


@dataclass(frozen=True)
class Proposal:
    signal: TypedSignal
    evidence_state: EvidenceState
    provenance: Provenance


@dataclass(frozen=True)
class RiskThresholds:
    support_precision_lcb95: float = 0.95
    refute_precision_lcb95: float = 0.95
    support_coverage: float = 0.05
    refute_coverage: float = 0.05
    swap_acceptance: float = 0.005
    unsafe_conflict_commits: int = 0
    class_conditional_conformal_coverage: float = 0.90


@dataclass(frozen=True)
class RiskCertificate:
    support_precision_lcb95: float | None
    refute_precision_lcb95: float | None
    support_coverage: float | None
    refute_coverage: float | None
    swap_acceptance: float | None
    unsafe_conflict_commits: int | None
    class_conditional_conformal_coverage: float | None
    source_gate: str
    source_hash: str

    def blockers(self, thresholds: RiskThresholds) -> list[str]:
        checks: tuple[tuple[str, float | int | None, str, float | int], ...] = (
            ("support_precision_lcb95", self.support_precision_lcb95, ">=", thresholds.support_precision_lcb95),
            ("refute_precision_lcb95", self.refute_precision_lcb95, ">=", thresholds.refute_precision_lcb95),
            ("support_coverage", self.support_coverage, ">=", thresholds.support_coverage),
            ("refute_coverage", self.refute_coverage, ">=", thresholds.refute_coverage),
            ("swap_acceptance", self.swap_acceptance, "<=", thresholds.swap_acceptance),
            ("unsafe_conflict_commits", self.unsafe_conflict_commits, "==", thresholds.unsafe_conflict_commits),
            (
                "class_conditional_conformal_coverage",
                self.class_conditional_conformal_coverage,
                ">=",
                thresholds.class_conditional_conformal_coverage,
            ),
        )
        blockers: list[str] = []
        for name, value, operator, threshold in checks:
            if value is None:
                blockers.append(f"MISSING:{name}")
            elif operator == ">=" and value < threshold:
                blockers.append(f"BELOW_THRESHOLD:{name}:{value}<{threshold}")
            elif operator == "<=" and value > threshold:
                blockers.append(f"ABOVE_THRESHOLD:{name}:{value}>{threshold}")
            elif operator == "==" and value != threshold:
                blockers.append(f"UNEQUAL:{name}:{value}!={threshold}")
        return blockers


@dataclass(frozen=True)
class Prerequisites:
    gold_frozen: bool
    translation_reviewed: bool
    human_annotations_complete: bool
    open_web_enabled: bool = False


@dataclass(frozen=True)
class Authority:
    human_authorized: bool
    domain_reviewer: str | None = None
    statistical_reviewer: str | None = None
    policy_authority: str | None = None
    authorization_hash: str | None = None

    def complete(self) -> bool:
        return self.human_authorized and all(
            (
                self.domain_reviewer,
                self.statistical_reviewer,
                self.policy_authority,
                self.authorization_hash,
            )
        )


@dataclass(frozen=True)
class ExecutionLease:
    valid: bool
    lease_id: str | None = None
    future_only: bool = True
    expires_at: str | None = None

    def complete(self) -> bool:
        return self.valid and self.future_only and bool(self.lease_id and self.expires_at)


@dataclass(frozen=True)
class GovernanceContext:
    proposal: Proposal
    risk: RiskCertificate
    thresholds: RiskThresholds
    prerequisites: Prerequisites
    authority: Authority
    lease: ExecutionLease
    unresolved_defeaters: tuple[str, ...] = ()


@dataclass(frozen=True)
class GovernanceResult:
    route: Route
    blockers: tuple[str, ...]
    provider_has_authority: bool
    ready_to_execute: bool


@dataclass(frozen=True)
class PublicationContext:
    execution_verified: bool
    publication_signed: bool
    explicit_publish_request: bool
    publication_authority: str | None


def clopper_pearson_lower(successes: int, trials: int, alpha: float = 0.05) -> float | None:
    if trials <= 0 or successes < 0 or successes > trials:
        return None
    if successes == 0:
        return 0.0
    return float(beta.ppf(alpha, successes, trials - successes + 1))


def certificate_from_counts(
    *,
    support_successes: int,
    support_trials: int,
    refute_successes: int,
    refute_trials: int,
    support_coverage: float,
    refute_coverage: float,
    swap_acceptance: float,
    unsafe_conflict_commits: int,
    class_conditional_conformal_coverage: float,
    source_gate: str,
    source_hash: str,
) -> RiskCertificate:
    return RiskCertificate(
        support_precision_lcb95=clopper_pearson_lower(support_successes, support_trials),
        refute_precision_lcb95=clopper_pearson_lower(refute_successes, refute_trials),
        support_coverage=support_coverage,
        refute_coverage=refute_coverage,
        swap_acceptance=swap_acceptance,
        unsafe_conflict_commits=unsafe_conflict_commits,
        class_conditional_conformal_coverage=class_conditional_conformal_coverage,
        source_gate=source_gate,
        source_hash=source_hash,
    )


def govern(context: GovernanceContext) -> GovernanceResult:
    blockers: list[str] = []
    prerequisites = context.prerequisites
    if not prerequisites.gold_frozen:
        blockers.append("PREREQUISITE:GOLD_NOT_FROZEN")
    if not prerequisites.translation_reviewed:
        blockers.append("PREREQUISITE:TRANSLATION_NOT_REVIEWED")
    if not prerequisites.human_annotations_complete:
        blockers.append("PREREQUISITE:HUMAN_ANNOTATIONS_INCOMPLETE")
    if blockers:
        return GovernanceResult(
            route=Route.BLOCKED_PREREQUISITE,
            blockers=tuple(blockers),
            provider_has_authority=False,
            ready_to_execute=False,
        )

    if context.unresolved_defeaters or context.proposal.evidence_state is EvidenceState.CONFLICTING:
        blockers.extend(f"DEFEATER:{value}" for value in context.unresolved_defeaters)
        if context.proposal.evidence_state is EvidenceState.CONFLICTING:
            blockers.append("EVIDENCE:CONFLICTING")
        return GovernanceResult(Route.HUMAN_REVIEW, tuple(blockers), False, False)

    if context.proposal.evidence_state not in {EvidenceState.SUPPORT, EvidenceState.REFUTE}:
        return GovernanceResult(
            Route.ABSTAIN,
            (f"EVIDENCE_NOT_ADMISSIBLE:{context.proposal.evidence_state.value}",),
            False,
            False,
        )

    blockers = context.risk.blockers(context.thresholds)
    if blockers:
        return GovernanceResult(Route.ABSTAIN, tuple(blockers), False, False)

    if not context.authority.complete():
        return GovernanceResult(
            Route.QUALIFIED_AWAITING_AUTHORITY,
            ("AUTHORITY:INCOMPLETE",),
            False,
            False,
        )

    if not context.lease.complete():
        return GovernanceResult(
            Route.AUTHORIZED_AWAITING_LEASE,
            ("EXECUTION_LEASE:INCOMPLETE",),
            False,
            False,
        )

    return GovernanceResult(Route.READY_TO_EXECUTE, (), False, True)


def publication_route(context: PublicationContext) -> PublicationRoute:
    if not (
        context.execution_verified
        and context.publication_signed
        and context.explicit_publish_request
        and context.publication_authority
    ):
        return PublicationRoute.BLOCKED
    return PublicationRoute.READY_FOR_EXPLICIT_HUMAN_PUBLICATION


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def decision_receipt(
    context: GovernanceContext,
    result: GovernanceResult,
    previous_receipt_hash: str | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "proposal": {
            "provider": context.proposal.provenance.provider.value,
            "model_version": context.proposal.provenance.model_version,
            "question_id": context.proposal.provenance.question_id,
            "state_sha256": context.proposal.provenance.state_sha256,
            "response_sha256": context.proposal.provenance.response_sha256,
            "primitive": context.proposal.signal.primitive.value,
            "evidence_state": context.proposal.evidence_state.value,
            "diagnostics": context.proposal.signal.diagnostics(),
        },
        "risk_source": {
            "gate": context.risk.source_gate,
            "sha256": context.risk.source_hash,
        },
        "route": result.route.value,
        "blockers": list(result.blockers),
        "provider_has_authority": False,
        "ready_to_execute": result.ready_to_execute,
        "previous_receipt_hash": previous_receipt_hash,
        "automatic_publication": False,
    }
    receipt_hash = sha256_value(body)
    return {**body, "receipt_hash": receipt_hash}


def verify_receipt_chain(receipts: Iterable[Mapping[str, Any]]) -> bool:
    previous: str | None = None
    for receipt in receipts:
        body = dict(receipt)
        expected_hash = body.pop("receipt_hash", None)
        if body.get("previous_receipt_hash") != previous:
            return False
        actual_hash = sha256_value(body)
        if expected_hash != actual_hash:
            return False
        previous = expected_hash
    return True


def load_thresholds(path: Path) -> RiskThresholds:
    data = json.loads(path.read_text(encoding="utf-8"))["promotion_thresholds"]
    return RiskThresholds(**data)


def blocked_certificate(source_gate: str, source_hash: str) -> RiskCertificate:
    return RiskCertificate(
        support_precision_lcb95=None,
        refute_precision_lcb95=None,
        support_coverage=None,
        refute_coverage=None,
        swap_acceptance=None,
        unsafe_conflict_commits=None,
        class_conditional_conformal_coverage=None,
        source_gate=source_gate,
        source_hash=source_hash,
    )


def context_from_sota009(
    *,
    provider: Provider,
    curriculum_path: Path,
    qa_path: Path,
    sota008_path: Path,
) -> GovernanceContext:
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    gate008 = json.loads(sota008_path.read_text(encoding="utf-8"))
    thresholds = load_thresholds(curriculum_path)
    proposal = Proposal(
        signal=TypedSignal(
            primitive=Primitive.CHOICE,
            labels=("support", "refute", "context", "insufficient"),
            probabilities=(0.0, 0.0, 1.0, 0.0),
            selected_index=2,
        ),
        evidence_state=EvidenceState.CONTEXT,
        provenance=Provenance(
            provider=provider,
            model_version="contract-only-no-live-call",
            question_id="evidence_relation",
            state_sha256=sha256_value(qa),
            response_sha256=sha256_value(gate008),
        ),
    )
    return GovernanceContext(
        proposal=proposal,
        risk=blocked_certificate(gate008["gate"], sha256_value(gate008)),
        thresholds=thresholds,
        prerequisites=Prerequisites(
            gold_frozen=qa["gold_status"] == "FROZEN",
            translation_reviewed=qa.get("translation_status") == "HUMAN_REVIEWED",
            human_annotations_complete=qa["human_annotations_collected"] > 0
            and qa["adjudicated_items"] == qa["pairs"],
            open_web_enabled=False,
        ),
        authority=Authority(False),
        lease=ExecutionLease(False),
        unresolved_defeaters=(gate008["formal_decision"],),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--curriculum", type=Path, required=True)
    parser.add_argument("--qa", type=Path, required=True)
    parser.add_argument("--sota008", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    receipts: list[dict[str, Any]] = []
    previous: str | None = None
    matrix: list[dict[str, Any]] = []
    for provider in (Provider.JEV, Provider.LAYA, Provider.NIMBLE, Provider.OPENJEV):
        context = context_from_sota009(
            provider=provider,
            curriculum_path=args.curriculum,
            qa_path=args.qa,
            sota008_path=args.sota008,
        )
        result = govern(context)
        receipt = decision_receipt(context, result, previous)
        receipts.append(receipt)
        previous = receipt["receipt_hash"]
        matrix.append(
            {
                "provider": provider.value,
                "route": result.route.value,
                "blockers": list(result.blockers),
                "provider_has_authority": result.provider_has_authority,
                "ready_to_execute": result.ready_to_execute,
                "receipt_hash": receipt["receipt_hash"],
            }
        )

    if not verify_receipt_chain(receipts):
        raise GovernanceError("Receipt chain verification failed")
    routes = {row["route"] for row in matrix}
    blockers = {tuple(row["blockers"]) for row in matrix}
    if len(routes) != 1 or len(blockers) != 1:
        raise GovernanceError("Provider changed governance outcome")

    (args.output / "provider_invariance_matrix.json").write_text(
        json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output / "decision_receipts.jsonl").write_text(
        "\n".join(json.dumps(receipt, ensure_ascii=False) for receipt in receipts) + "\n",
        encoding="utf-8",
    )
    status = {
        "providers_evaluated": [provider.value for provider in (Provider.JEV, Provider.LAYA, Provider.NIMBLE, Provider.OPENJEV)],
        "live_model_calls": 0,
        "provider_invariance": True,
        "unique_route": next(iter(routes)),
        "receipt_chain_valid": True,
        "automatic_execution": False,
        "automatic_publication": False,
        "authority": "FORMAL_GOVERNANCE_PILOT_NOT_MODEL_VALIDATION",
    }
    (args.output / "status.json").write_text(
        json.dumps(status, indent=2), encoding="utf-8"
    )
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
