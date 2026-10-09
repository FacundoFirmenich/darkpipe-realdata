"""Fail-closed computational rules for IRP-27 Tarifa Abierta.

These functions compute a published tariff-schedule subtotal and explicitly
hypothetical local counterfactuals. They do not calculate a legally payable
invoice, population average, fiscal cost, causal effect, or political verdict.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ScenarioScope = Literal["subtotal", "variable", "pist"]


@dataclass(frozen=True)
class TariffCell:
    fixed_charge: float
    variable_charge_per_m3: float
    pist_component_per_m3: float | None = None

    def validate(self) -> None:
        if self.fixed_charge < 0:
            raise ValueError("fixed_charge must be non-negative")
        if self.variable_charge_per_m3 < 0:
            raise ValueError("variable_charge_per_m3 must be non-negative")


def published_subtotal(cell: TariffCell, consumption_m3: float) -> float:
    """Return fixed + variable*m3 for one fully specified published cell.

    The result is a source-defined tariff subtotal, not a final invoice.
    """
    cell.validate()
    if consumption_m3 < 0:
        raise ValueError("consumption_m3 must be non-negative")
    return cell.fixed_charge + cell.variable_charge_per_m3 * consumption_m3


def hypothetical_discount(
    cell: TariffCell,
    consumption_m3: float,
    percent: float,
    scope: ScenarioScope,
    cap: float | None = None,
) -> float:
    """Apply an explicit operator-entered local scenario.

    This function intentionally supplies no default parameters and performs no
    population weighting. The PIST scenario is unavailable unless the source
    publishes that component for the selected cell.
    """
    if not 0 <= percent <= 100:
        raise ValueError("percent must be in [0, 100]")
    if cap is not None and cap < 0:
        raise ValueError("cap must be non-negative")

    base = published_subtotal(cell, consumption_m3)
    fraction = percent / 100.0

    if scope == "subtotal":
        value = base * (1.0 - fraction)
    elif scope == "variable":
        value = cell.fixed_charge + cell.variable_charge_per_m3 * (1.0 - fraction) * consumption_m3
    elif scope == "pist":
        if cell.pist_component_per_m3 is None:
            raise ValueError("PIST component is not published for this cell")
        value = cell.fixed_charge + (
            cell.variable_charge_per_m3 - cell.pist_component_per_m3 * fraction
        ) * consumption_m3
    else:
        raise ValueError(f"unsupported scope: {scope}")

    return min(value, cap) if cap is not None else value
