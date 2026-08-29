from __future__ import annotations

import numpy as np

from darkpipe.object_lensing import (
    G_MPC_KM2_S2_MSUN,
    MPC_M,
    FlatLambdaCDM,
    accumulate_esd,
    deproject_spherical_esd,
    fixed_gbar_radius_kpc,
    object_level_rar,
    sigma_critical_msun_mpc2,
    tangential_and_cross_ellipticity,
)


def test_sigma_critical_types_foreground_as_infinite() -> None:
    cosmology = FlatLambdaCDM()
    value = sigma_critical_msun_mpc2(
        np.array([0.2, 0.4]),
        np.array([0.8, 0.3]),
        cosmology=cosmology,
    )
    assert np.isfinite(value[0]) and value[0] > 0
    assert np.isinf(value[1])


def test_tangential_and_cross_channels_have_expected_rotation() -> None:
    tangential, cross = tangential_and_cross_ellipticity(
        np.array([0.0]),
        np.array([0.0]),
        np.array([1.0]),
        np.array([0.0]),
        np.array([-0.2]),
        np.array([0.0]),
    )
    np.testing.assert_allclose(tangential, [0.2], atol=1e-12)
    np.testing.assert_allclose(cross, [0.0], atol=1e-12)


def test_pair_accumulator_keeps_lenses_and_null_channel_separate() -> None:
    result = accumulate_esd(
        lens_index=np.array([0, 0, 1]),
        projected_radius_mpc=np.array([0.2, 0.3, 0.2]),
        tangential_ellipticity=np.array([0.1, 0.3, 0.2]),
        cross_ellipticity=np.array([0.0, 0.0, 0.1]),
        source_weight=np.ones(3),
        sigma_critical=np.full(3, 10.0),
        multiplicative_bias=np.zeros(3),
        lens_count=2,
        radial_edges_mpc=np.array([0.1, 0.5, 1.0]),
    )
    np.testing.assert_allclose(result["esd_msun_mpc2"][:, 0], [2.0, 2.0])
    np.testing.assert_allclose(result["cross_esd_msun_mpc2"][:, 0], [0.0, 1.0])
    np.testing.assert_array_equal(result["pair_count"][:, 0], [2, 1])


def test_power_law_deprojection_matches_analytic_operator() -> None:
    amplitude = 2.5e12
    radius = np.geomspace(0.01, 100.0, 300)
    profile = amplitude / radius
    evaluation = np.array([0.1, 1.0, 10.0])
    observed = deproject_spherical_esd(
        radius,
        profile,
        evaluation,
        inner_log_slope=-1.0,
        outer_log_slope=-1.0,
        quadrature_points=8192,
    )
    expected = (
        4.0
        * G_MPC_KM2_S2_MSUN
        * amplitude
        / evaluation
        * (1e6 / MPC_M)
    )
    np.testing.assert_allclose(observed, expected, rtol=2e-5)


def test_object_level_rar_deprojects_before_stacking() -> None:
    radial = np.geomspace(0.02, 20.0, 120)
    profiles = np.vstack([1.0e12 / radial, 2.0e12 / radial])
    masses = np.array([2.0e10, 5.0e10])
    gbar = np.array([1e-12, 3e-12])
    result = object_level_rar(
        radial,
        profiles,
        masses,
        gbar,
        inner_log_slope=-1.0,
        outer_log_slope=-1.0,
    )
    assert result["operation_order"] == "DEPROJECT_EACH_LENS_BEFORE_FIXED_GBAR_STACK"
    assert result["individual_gobs_m_s2"].shape == (2, 2)
    assert np.all(np.isfinite(result["gobs_m_s2"]))
    assert np.all(fixed_gbar_radius_kpc(masses[:, None], gbar[None, :]) > 0)
