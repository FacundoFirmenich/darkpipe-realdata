from __future__ import annotations

import unittest

from build_argentine_gold import (
    Segment,
    annotation_schema,
    facet_hints,
    mismatch_hints,
    normalize,
    select_claim_segments,
    sentence_split,
)


class ArgentineGoldTests(unittest.TestCase):
    def test_sentence_split_keeps_numeric_claim(self) -> None:
        text = "La tasa de desocupación alcanzó 7,9% en 2026. La tasa de empleo fue 45,0%."
        pieces = sentence_split(text)
        self.assertEqual(2, len(pieces))
        self.assertIn("7,9%", pieces[0])

    def test_claim_selection_is_unique_and_balanced_across_sources(self) -> None:
        segments = []
        for source in ("A", "B", "C"):
            for index in range(20):
                segments.append(
                    Segment(
                        source,
                        "fiscal",
                        "official",
                        "https://example.org",
                        f"row:{index}",
                        index,
                        f"El resultado fiscal {source} {index} alcanzó {index + 1}% durante 2026.",
                        10.0 - index / 100,
                        "2026",
                        "Argentina",
                    )
                )
        selected = select_claim_segments(segments, 40)
        self.assertEqual(40, len(selected))
        self.assertEqual(40, len({normalize(segment.text) for segment in selected}))
        counts = {source: sum(segment.source_id == source for segment in selected) for source in ("A", "B", "C")}
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)

    def test_mismatch_detects_time(self) -> None:
        claim = Segment("A", "social", "official", "u", "p1", 1, "La pobreza fue 30% en 2026.", 10, "2026", "Argentina")
        passage = Segment("B", "social", "survey", "u2", "p2", 2, "La pobreza fue 40% en 2025.", 9, "2025", "Argentina")
        self.assertIn("TIME", mismatch_hints(claim, passage))

    def test_schema_requires_all_facets(self) -> None:
        schema = annotation_schema()
        required = schema["properties"]["facet_alignment"]["required"]
        self.assertEqual(7, len(required))
        self.assertIn("DENOMINATOR", required)

    def test_facet_hints_preserve_scope(self) -> None:
        hints = facet_hints(
            "En 31 aglomerados urbanos, 2.498.000 hogares estaban por debajo de la línea de pobreza en 2026.",
            "official_statistics",
            "2026-H1",
            "31 aglomerados urbanos",
        )
        self.assertIn("2026", hints["time_candidates"])
        self.assertIn("hogares", hints["population_candidates"])


if __name__ == "__main__":
    unittest.main()
