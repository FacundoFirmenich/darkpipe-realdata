from __future__ import annotations

import unittest

from responseops_engine import evaluation_manifest, release_decision, validate_corpus


SOURCE = {"source_id": "S1"}
PACKAGE = {
    "package_id": "RSP-1",
    "steelman": "Best defensible opposing case.",
    "mandatory_concession": "The narrow fact is supported.",
    "blocked_wording": "Forbidden sentence.",
    "sources": {"primary": ["S1"], "contrast": ["S1"]},
    "outputs": {
        "30_seconds": "Safe",
        "3_minutes": "Safe",
        "fact_check": "Safe",
        "debate_card": "Safe",
        "technical_dossier": "Safe",
        "ai_grounding": {"answer": "Safe"},
        "steelman": "Safe",
        "revocation_note": "Safe",
    },
    "revocation_triggers": ["Source revision"],
    "authority": {
        "status": "UNSIGNED_SHADOW",
        "automatic_publication": False,
        "required_signatures": [
            "data_steward",
            "domain_reviewer",
            "statistical_reviewer",
            "policy_authority",
            "publication_authority",
        ],
    },
}


class ResponseOpsTests(unittest.TestCase):
    def test_valid_package(self) -> None:
        self.assertEqual([], validate_corpus([PACKAGE], [SOURCE]))

    def test_missing_steelman_fails(self) -> None:
        bad = {**PACKAGE, "steelman": ""}
        self.assertTrue(any(issue.code == "NO_STEELMAN" for issue in validate_corpus([bad], [SOURCE])))

    def test_blocked_wording_cannot_leak(self) -> None:
        bad = {**PACKAGE, "outputs": {**PACKAGE["outputs"], "30_seconds": "Forbidden sentence."}}
        self.assertTrue(any(issue.code == "BLOCKED_WORDING_LEAK" for issue in validate_corpus([bad], [SOURCE])))

    def test_publication_stays_manual(self) -> None:
        signatures = {role: "signed" for role in PACKAGE["authority"]["required_signatures"]}
        result = release_decision(PACKAGE, signatures)
        self.assertTrue(result["human_signed"])
        self.assertFalse(result["publication_authorized"])

    def test_unsigned_release_is_blocked(self) -> None:
        result = release_decision(PACKAGE, {})
        self.assertFalse(result["human_signed"])
        self.assertTrue(result["blockers"])

    def test_eval_manifest_is_advisory(self) -> None:
        result = evaluation_manifest([PACKAGE])
        self.assertEqual(6, result["prompts"])
        self.assertEqual("ADVISORY_ONLY", result["judge_authority"])
        self.assertFalse(result["automatic_promotion"])


if __name__ == "__main__":
    unittest.main()
