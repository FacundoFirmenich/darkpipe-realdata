from __future__ import annotations

import unittest

from estimand_decomposition import claim_contract, generate_queries, validate_contract


class EstimandDecompositionTests(unittest.TestCase):
    def test_numeric_quantity_is_preserved(self) -> None:
        item = {
            "claim": "Government revenue fell by 60% in Nigeria in 2020.",
            "claim_date": "1-10-2020",
            "speaker": "Muhammadu Buhari",
            "claim_types": ["Numerical Claim"],
        }
        contract, queries = generate_queries(item)
        self.assertIn("60%", contract["quantities"])
        self.assertTrue(any("60%" in query["text"] for query in queries))
        self.assertEqual([], validate_contract(contract))

    def test_quote_preserves_speaker(self) -> None:
        item = {
            "claim": "Donald Trump said climate change is a hoax.",
            "claim_date": "1-9-2020",
            "speaker": "Joe Biden",
            "claim_types": ["Quote Verification"],
        }
        contract, queries = generate_queries(item)
        self.assertTrue(contract["is_quote"])
        self.assertTrue(any(query["query_type"] == "quote_provenance" for query in queries))
        self.assertTrue(any("Joe Biden" in query["text"] for query in queries))

    def test_causal_claim_gets_contrast_query(self) -> None:
        item = {
            "claim": "Incidence increased because of the nationwide screening programme.",
            "claim_date": None,
            "speaker": None,
            "claim_types": ["Event/Property Claim"],
        }
        contract, queries = generate_queries(item)
        self.assertTrue(contract["is_causal"])
        self.assertTrue(any(query["query_type"] == "causal_contrast" for query in queries))

    def test_universal_claim_gets_exception_query(self) -> None:
        item = {
            "claim": "All school books are taxed in India.",
            "claim_date": None,
            "speaker": None,
            "claim_types": ["Event/Property Claim"],
        }
        contract, queries = generate_queries(item)
        self.assertTrue(contract["is_universal"])
        self.assertTrue(any(query["query_type"] == "scope_exception" for query in queries))

    def test_contract_never_invents_quantities(self) -> None:
        item = {
            "claim": "A policy improved employment.",
            "claim_date": None,
            "speaker": None,
            "claim_types": ["Event/Property Claim"],
        }
        contract = claim_contract(item)
        self.assertEqual([], contract["quantities"])
        self.assertEqual([], validate_contract(contract))


if __name__ == "__main__":
    unittest.main()
