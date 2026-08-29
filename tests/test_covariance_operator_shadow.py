from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from darkpipe.covariance_operator_shadow import (
    RAR_TRANSFER_AUTHORITY,
    CovarianceOperatorConfig,
    build_deprojection_operator,
    derive_operator_shadow,
    load_corrected_covariance,
    load_profile_family,
    summarize_operator_shadow,
)


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "third_party" / "kids_brouwer2021"
PROFILE_PATHS = [
    DATA / f"Fig-3_Lensing-rotation-curves_Massbin-{index}.txt"
    for index in range(1, 5)
]
MASS_BIN_MINIMA = [8.5, 10.3, 10.6, 10.8]
COVARIANCE_PATH = DATA / "Fig-3_Lensing-rotation-curves_Massbins_covmatrix.txt"

EXPECTED_SHA256 = {
    "README.txt": "b3680580696c5dbf5671c700d5e8f90fbfd1dc614fa7e3e07b2f66d1624e8645",
    "Fig-3_Lensing-rotation-curves_Massbin-1.txt": "cd8171d248a5c660701c2fcfb5f39eea01ae57b5b9ec2bae233e5aef77e7d78e",
    "Fig-3_Lensing-rotation-curves_Massbin-2.txt": "279d82e4faee34041221b617f0ce9cfc97966c431616c94608b0983e60421ae7",
    "Fig-3_Lensing-rotation-curves_Massbin-3.txt": "88eca49e85504c1eb6ce11e09edcdda37c0903dd678f2207ed4bca4fa31f7a22",
    "Fig-3_Lensing-rotation-curves_Massbin-4.txt": "05853565ae193347adff22f8aec58c50f80b2e22866fb9c532137c6f198a79e1",
    "Fig-3_Lensing-rotation-curves_Massbins_covmatrix.txt": "e2568b34578a4752c4cdc25c23cd38c896ac1c5e0477cce3fe8d7b32e4954445",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def real_surface():
    profiles = load_profile_family(PROFILE_PATHS, MASS_BIN_MINIMA)
    covariance, _, diagnostics = load_corrected_covariance(
        COVARIANCE_PATH, profiles
    )
    return profiles, covariance, diagnostics


def test_selected_cc_by_source_bytes_are_frozen() -> None:
    observed = {name: _sha256(DATA / name) for name in EXPECTED_SHA256}
    assert observed == EXPECTED_SHA256


def test_published_covariance_is_joint_symmetric_positive_definite(real_surface) -> None:
    _, covariance, diagnostics = real_surface
    assert covariance.shape == (60, 60)
    assert np.array_equal(covariance, covariance.T)
    assert diagnostics["minimum_eigenvalue"] > 0.0
    assert diagnostics["maximum_diagonal_relative_error"] < 2e-4
    assert 0.0 < diagnostics["maximum_absolute_off_diagonal_correlation"] < 0.1


def test_exact_operator_recovers_dense_sis_profile() -> None:
    radius = np.geomspace(0.03, 3.0, 96)
    esd = 1.0 / radius
    operator = build_deprojection_operator(
        radius, quadrature_nodes=512, interpolation="linear", tail="sis"
    )
    recovered = operator @ esd
    # A continuous 1/R ESD is an SIS and obeys integral(DeltaSigma)=DeltaSigma.
    assert np.allclose(recovered, esd, rtol=8e-4, atol=0.0)


def test_operator_is_numerically_converged_on_published_grid(real_surface) -> None:
    profiles, _, _ = real_surface
    radius = profiles[0].frame["radius_mpc"].to_numpy(dtype=float)
    operator_512 = build_deprojection_operator(radius, quadrature_nodes=512)
    operator_1024 = build_deprojection_operator(radius, quadrature_nodes=1024)
    assert np.max(np.abs(operator_512 - operator_1024)) < 2e-4


def test_real_surface_preserves_abstention_and_frozen_result_counts(real_surface) -> None:
    profiles, covariance, diagnostics = real_surface
    config = CovarianceOperatorConfig()
    result, matrices = derive_operator_shadow(profiles, covariance, config)
    summary = summarize_operator_shadow(result, config, diagnostics, [])

    assert len(result) == 60
    assert result["rar_transfer_authority"].eq(RAR_TRANSFER_AUTHORITY).all()
    assert summary["rar_transfer_authority"] == RAR_TRANSFER_AUTHORITY
    assert summary["status_counts"] == {
        "OPERATOR_DIFFERENCE_STATISTICALLY_UNRESOLVED_95": 39,
        "OPERATOR_DIFFERENCE_UNRESOLVED_SYSTEMATICS": 14,
        "OPERATOR_DIFFERENCE_RESOLVED_CONDITIONAL_95": 7,
    }
    assert np.isclose(summary["median_exact_over_sis_ratio"], 1.009836331172964)
    assert matrices["covariance_exact_minus_sis"].shape == (60, 60)
    assert np.allclose(
        matrices["covariance_exact_minus_sis"],
        matrices["covariance_exact_minus_sis"].T,
        rtol=0.0,
        atol=1e-24,
    )


def test_cross_component_remains_descriptive_without_invented_covariance(real_surface) -> None:
    profiles, covariance, _ = real_surface
    result, _ = derive_operator_shadow(
        profiles, covariance, CovarianceOperatorConfig()
    )
    assert result["cross_null_authority"].eq(
        "DESCRIPTIVE_ONLY_NO_PUBLISHED_CROSS_COVARIANCE"
    ).all()
    assert np.isfinite(
        result["cross_esd_over_tangential_error_descriptive"]
    ).all()
