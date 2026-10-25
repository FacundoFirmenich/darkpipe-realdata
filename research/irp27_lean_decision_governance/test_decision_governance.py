from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from decision_governance import (
    Authority,
    EvidenceState,
    ExecutionLease,
    GovernanceContext,
    Prerequisites,
    Primitive,
    Proposal,
    Provider,
    Provenance,
    PublicationContext,
    PublicationRoute,
    RiskCertificate,
    RiskThresholds,
    Route,
    TypedSignal,
    certificate_from_counts,
    context_from_sota009,
    decision_receipt,
    govern,
    publication_route,
    verify_receipt_chain,
)

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"


def signal() -> TypedSignal:
    return TypedSignal(
        primitive=Primitive.CHOICE,
        labels=("support", "refute", "context", "insufficient"),
        probabilities=(0.97, 0.01, 0.01, 0.01),
        selected_index=0,
    )


def proposal(provider: Provider, state: EvidenceState = EvidenceState.SUPPORT) -> Proposal:
    return Proposal(
        signal=signal(),
        evidence_state=state,
        provenance=Provenance(
            provider=provider,
            model_version="contract-test",
            question_id="evidence_relation",
            state_sha256="s" * 64,
            response_sha256="r" * 64,
        ),
    )


def passing_certificate() -> RiskCertificate:
    return certificate_from_counts(
        support_successes=100,
        support_trials=100,
        refute_successes=100,
        refute_trials=100,
        support_coverage=0.10,
        refute_coverage=0.10,
        swap_acceptance=0.0,
        unsafe_conflict_commits=0,
        class_conditional_conformal_coverage=0.95,
        source_gate="unit-boundary",
        source_hash="g" * 64,
    )


def context(provider: Provider, state: EvidenceState = EvidenceState.SUPPORT) -> GovernanceContext:
    return GovernanceContext(
        proposal=proposal(provider, state),
        risk=passing_certificate(),
        thresholds=RiskThresholds(),
        prerequisites=Prerequisites(True, True, True),
        authority=Authority(
            True,
            domain_reviewer="domain",
            statistical_reviewer="statistics",
            policy_authority="authority",
            authorization_hash="a" * 64,
        ),
        lease=ExecutionLease(
            True,
            lease_id="lease-1",
            future_only=True,
            expires_at="2099-01-01T00:00:00Z",
        ),
    )


class DecisionGovernanceTests(unittest.TestCase):
    def test_provider_never_changes_route(self) -> None:
        routes = {
            govern(context(provider_name)).route
            for provider_name in (
                Provider.JEV,
                Provider.LAYA,
                Provider.NIMBLE,
                Provider.OPENJEV,
            )
        }
        self.assertEqual({Route.READY_TO_EXECUTE}, routes)

    def test_provider_never_has_authority(self) -> None:
        result = govern(context(Provider.JEV))
        self.assertFalse(result.provider_has_authority)

    def test_conflict_requires_human_review(self) -> None:
        result = govern(context(Provider.JEV, EvidenceState.CONFLICTING))
        self.assertEqual(Route.HUMAN_REVIEW, result.route)
        self.assertFalse(result.ready_to_execute)

    def test_insufficient_evidence_abstains(self) -> None:
        result = govern(context(Provider.JEV, EvidenceState.INSUFFICIENT))
        self.assertEqual(Route.ABSTAIN, result.route)

    def test_sota009_real_state_is_blocked_for_every_provider(self) -> None:
        routes = set()
        for provider_name in (
            Provider.JEV,
            Provider.LAYA,
            Provider.NIMBLE,
            Provider.OPENJEV,
        ):
            gate_context = context_from_sota009(
                provider=provider_name,
                curriculum_path=FIXTURES / "sota009_curriculum.json",
                qa_path=FIXTURES / "sota009_qa.json",
                sota008_path=FIXTURES / "sota008_gate_decision.json",
            )
            result = govern(gate_context)
            routes.add(result.route)
            self.assertIn("PREREQUISITE:GOLD_NOT_FROZEN", result.blockers)
            self.assertFalse(result.ready_to_execute)
        self.assertEqual({Route.BLOCKED_PREREQUISITE}, routes)

    def test_noul_probability_is_not_a_score(self) -> None:
        noul = TypedSignal(
            primitive=Primitive.NOUL,
            labels=(),
            probabilities=(),
            noul_probability=0.75,
        )
        diagnostics = noul.diagnostics()
        self.assertEqual("probability_of_yes_not_degree", diagnostics["semantic_warning"])
        self.assertAlmostEqual(0.5, diagnostics["confidence_distance_from_half"])

    def test_publication_requires_explicit_human_request(self) -> None:
        blocked = publication_route(
            PublicationContext(True, True, False, "publisher")
        )
        ready = publication_route(
            PublicationContext(True, True, True, "publisher")
        )
        self.assertEqual(PublicationRoute.BLOCKED, blocked)
        self.assertEqual(
            PublicationRoute.READY_FOR_EXPLICIT_HUMAN_PUBLICATION,
            ready,
        )

    def test_append_only_receipt_chain(self) -> None:
        receipts = []
        previous = None
        for provider_name in (Provider.JEV, Provider.LAYA, Provider.NIMBLE):
            governance_context = context(provider_name)
            receipt = decision_receipt(
                governance_context,
                govern(governance_context),
                previous,
            )
            receipts.append(receipt)
            previous = receipt["receipt_hash"]
        self.assertTrue(verify_receipt_chain(receipts))
        tampered = [dict(receipt) for receipt in receipts]
        tampered[1]["route"] = Route.ABSTAIN.value
        self.assertFalse(verify_receipt_chain(tampered))

    def test_cli_fixtures_are_real_gate_states(self) -> None:
        gate008 = json.loads((FIXTURES / "sota008_gate_decision.json").read_text())
        gate009 = json.loads((FIXTURES / "sota009_qa.json").read_text())
        self.assertEqual(0, gate008["promotions"])
        self.assertEqual("NOT_YET_GOLD", gate009["gold_status"])
        self.assertEqual(0, gate009["human_annotations_collected"])


if __name__ == "__main__":
    unittest.main()
