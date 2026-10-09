from __future__ import annotations

import unittest

from tariff_engine import TariffCell, hypothetical_discount, published_subtotal


class TariffEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cell = TariffCell(
            fixed_charge=4432.10,
            variable_charge_per_m3=316.16,
            pist_component_per_m3=210.04,
        )

    def test_published_subtotal(self) -> None:
        self.assertAlmostEqual(published_subtotal(self.cell, 100.0), 36048.10)

    def test_negative_consumption_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            published_subtotal(self.cell, -1.0)

    def test_local_variable_scenario(self) -> None:
        self.assertAlmostEqual(
            hypothetical_discount(self.cell, 100.0, 10.0, "variable"),
            32886.50,
        )

    def test_pist_scenario_requires_published_component(self) -> None:
        cell = TariffCell(100.0, 10.0, None)
        with self.assertRaises(ValueError):
            hypothetical_discount(cell, 10.0, 20.0, "pist")

    def test_no_implicit_scenario_scope(self) -> None:
        with self.assertRaises(ValueError):
            hypothetical_discount(self.cell, 100.0, 10.0, "unknown")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
