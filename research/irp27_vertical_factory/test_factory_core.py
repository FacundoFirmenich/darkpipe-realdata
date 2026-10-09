from __future__ import annotations

import unittest

from factory_core import assess_promotion, audit, validate


def specimen() -> dict:
    return {
        "schema_version": "1.7",
        "vertical_id": "TEST-VERTICAL",
        "release": {"status": "OPERATIVE_SHADOW"},
        "authority": {
            "automatic_publication": False,
            "causal_authority": False,
            "programmatic_authority": False,
            "signatures": {
                "data_steward": None,
                "legal_reviewer": None,
                "statistical_reviewer": None,
                "policy_authority": None,
                "publication_authority": None,
            },
        },
        "sources": [{"source_id": "S1", "retrieval_state": "RAW_BYTES_ARCHIVED_HASHED_PARSED"}],
        "metrics": [{"metric_id": "M1", "source_id": "S1"}],
        "claims": [{
            "claim_id": "C1",
            "type": "FACT",
            "support": ["M1"],
            "status": "SUPPORTED_WITH_SCOPE",
        }],
        "rules": [{"rule_id": "R1", "authority": "INTERNAL_EXPLORATION_ONLY"}],
        "outputs": [],
        "forbidden_inferences": ["observation != causality"],
        "actions": [],
        "timeseries": [{"series_id": "T1"}],
    }


class FactoryCoreTests(unittest.TestCase):
    def test_specimen_validates(self) -> None:
        self.assertEqual([], validate(specimen()))

    def test_shadow_is_allowed(self) -> None:
        self.assertTrue(assess_promotion(specimen(), "OPERATIVE_SHADOW").allowed)

    def test_publication_is_blocked_without_signatures(self) -> None:
        decision = assess_promotion(specimen(), "PUBLISHED")
        self.assertFalse(decision.allowed)
        self.assertTrue(any(x.startswith("MISSING_SIGNATURES") for x in decision.blockers))

    def test_audit_is_non_authorizing(self) -> None:
        result = audit(specimen())
        self.assertFalse(result["automatic_publication"])
        self.assertFalse(result["causal_authority"])
        self.assertEqual(1, result["timeseries"])


if __name__ == "__main__":
    unittest.main()
