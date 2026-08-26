"""Tests for observable-shadow to conditional-inobservable derivation."""

import numpy as np

from darkpipe.inobservable import (
    AUTHORITY,
    DerivationConfig,
    derive_shadow_inobservables,
    parse_sparc_mass_models,
    parse_sparc_sample,
    select_observable_points,
    signed_square,
    summarize_derivation,
)


SAMPLE_TABLE = """
       CamB 10   3.36  0.26  2 65.0  5.0   0.075   0.003  1.21     7.89  0.47    66.20   0.012  1.21   0.0   0.0   2           Bm03
     D512-2 10  15.20  4.56  1 56.0 10.0   0.325   0.022  2.37     9.22  1.24    93.94   0.081  0.00   0.0   0.0   2           Tr09
"""

MASS_TABLE = """
CamB          3.36   0.16   1.99  1.50   1.86   3.75   0.00   30.32     0.00
CamB          3.36   0.41   4.84  1.50   4.24   9.47   0.00   23.77     0.00
D512-2       15.20   0.96  22.90  2.71   4.08  14.85   0.00   16.45     0.00
"""


def test_real_sparc_excerpt_parses():
    galaxies = parse_sparc_sample(SAMPLE_TABLE)
    mass = parse_sparc_mass_models(MASS_TABLE)
    assert list(galaxies["galaxy"]) == ["CamB", "D512-2"]
    assert len(mass) == 3
    assert galaxies.loc[galaxies["galaxy"] == "CamB", "quality"].iloc[0] == 2


def test_signed_gas_contribution_is_preserved():
    values = signed_square(np.array([-2.0, 0.0, 3.0]))
    assert np.array_equal(values, np.array([-4.0, 0.0, 9.0]))


def test_selection_and_derivation_are_deterministic():
    galaxies = parse_sparc_sample(SAMPLE_TABLE)
    mass = parse_sparc_mass_models(MASS_TABLE)
    config = DerivationConfig(
        draws=256,
        seed=123,
        maximum_fractional_velocity_error=1.0,
    )
    selected = select_observable_points(mass, galaxies, config)
    first = derive_shadow_inobservables(selected, config)
    second = derive_shadow_inobservables(selected, config)
    assert first.equals(second)
    assert set(first["authority"]) == {AUTHORITY}
    assert np.isfinite(first.select_dtypes(include=[np.number])).all().all()


def test_summary_abstains_for_tiny_real_excerpt_and_does_not_ontologize():
    galaxies = parse_sparc_sample(SAMPLE_TABLE)
    mass = parse_sparc_mass_models(MASS_TABLE)
    config = DerivationConfig(
        draws=128,
        seed=456,
        maximum_fractional_velocity_error=1.0,
    )
    selected = select_observable_points(mass, galaxies, config)
    profiles = derive_shadow_inobservables(selected, config)
    summary = summarize_derivation(
        profiles,
        selected,
        config,
        {"schema": "test-real-excerpt"},
    )
    assert summary["decision"] == "ABSTAIN_INTEGRITY_INSUFFICIENT_REAL_OBSERVATIONS"
    assert "dark-matter particle identity or density profile" in summary["not_estimable"]
