from pathlib import Path

import numpy as np

from darkpipe.kids_external_rar import (
    BROUWER_ESD_TO_GOBS,
    load_brouwer_rar_reference,
    load_mistele2024_table1,
    mistele_reproduction_diagnostic,
    shared_random_corrected_stack,
    stack_interpolated_profile,
)


def test_shared_random_uncertainty_is_not_divided_per_lens() -> None:
    signal = np.asarray([[10.0], [14.0]])
    variance = np.asarray([[1.0], [1.0]])
    targets = np.asarray([[1.5], [1.5]])
    result = shared_random_corrected_stack(
        signal,
        variance,
        targets,
        np.asarray([1.0, 2.0]),
        np.asarray([2.0, 4.0]),
        np.asarray([4.0, 16.0]),
    )
    np.testing.assert_allclose(result["matched_signal"], [12.0])
    np.testing.assert_allclose(result["random_correction"], [3.0])
    np.testing.assert_allclose(result["corrected"], [9.0])
    np.testing.assert_allclose(result["signal_variance"], [0.5])
    np.testing.assert_allclose(result["random_variance_diagonal"], [5.0])
    np.testing.assert_allclose(result["corrected_variance_diagonal"], [5.5])


def test_shared_random_profile_is_not_extrapolated() -> None:
    result = shared_random_corrected_stack(
        np.asarray([[1.0, 1.0]]),
        np.asarray([[1.0, 1.0]]),
        np.asarray([[0.9, 2.1]]),
        np.asarray([1.0, 2.0]),
        np.asarray([0.0, 0.0]),
        np.asarray([1.0, 1.0]),
    )
    assert np.all(np.isnan(result["corrected"]))
    np.testing.assert_array_equal(result["effective_lenses"], [0, 0])


def test_brouwer_loader_applies_bias_to_profile_and_covariance(tmp_path: Path) -> None:
    profile = tmp_path / "profile.txt"
    covariance = tmp_path / "covariance.txt"
    profile.write_text(
        "1e-15 2 0 1 0.5 0 0 0\n2e-15 4 0 1 0.5 0 0 0\n",
        encoding="utf-8",
    )
    covariance.write_text(
        "-999 -999 1e-15 1e-15 1 1 0.25\n"
        "-999 -999 1e-15 2e-15 0.2 0 0.25\n"
        "-999 -999 2e-15 1e-15 0.2 0 0.25\n"
        "-999 -999 2e-15 2e-15 4 1 0.25\n",
        encoding="utf-8",
    )
    result = load_brouwer_rar_reference(profile, covariance)
    np.testing.assert_allclose(
        result["gobs_m_s2"], BROUWER_ESD_TO_GOBS * np.asarray([4, 8])
    )
    np.testing.assert_allclose(
        result["covariance_gobs"],
        BROUWER_ESD_TO_GOBS**2 * np.asarray([[4, 0.8], [0.8, 16]]),
    )


def test_mistele_reproduction_gate_requires_every_point_and_median(tmp_path: Path) -> None:
    table = tmp_path / "table.csv"
    rows = [
        f"{x},{x + 1},0.05,0.00" for x in np.linspace(-15.0, -11.5, 15)
    ]
    table.write_text(
        "log10_gbar_m_s2,log10_gobs_m_s2,sigma_statistical_log10_gobs,sigma_systematic_log10_gobs\n"
        + "\n".join(rows)
        + "\n",
        encoding="utf-8",
    )
    reference = load_mistele2024_table1(table)
    passed = mistele_reproduction_diagnostic(reference["gobs_m_s2"], reference)
    assert passed["reproduction_gate"] is True
    adverse_values = np.asarray(reference["gobs_m_s2"]).copy()
    adverse_values[0] = -1.0
    failed = mistele_reproduction_diagnostic(adverse_values, reference)
    assert failed["reproduction_gate"] is False
    assert failed["positive_estimable_bins"] == 14


def test_variable_radius_profile_stack_uses_interpolated_lens_weights() -> None:
    result = stack_interpolated_profile(
        np.asarray([1.0, 2.0, 4.0]),
        np.asarray([[1.0, 3.0, 7.0], [2.0, 4.0, 8.0]]),
        np.ones((2, 3)),
        np.asarray([[1.0, 3.0, 5.0], [3.0, 1.0, 5.0]]),
        np.asarray([[1.5], [1.5]]),
    )
    # At R=1.5, values are 2 and 3 while weights are 2 and 2.
    np.testing.assert_allclose(result["stacked"], [2.5])
    np.testing.assert_allclose(result["variance"], [0.5])
    np.testing.assert_array_equal(result["effective_lenses"], [2])
