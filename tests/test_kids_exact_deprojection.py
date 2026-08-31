import numpy as np
from scipy.integrate import quad

from darkpipe.kids_exact_deprojection import (
    deproject_individual_profiles,
    integrate_piecewise_linear_profile,
    stack_inverse_variance,
)
from darkpipe.object_lensing import G_MPC_KM2_S2_MSUN, MPC_M


def test_signed_linear_profile_is_integrated_analytically() -> None:
    radius = np.asarray([1.0, 2.0, 4.0])
    values = 3.0 * radius - 10.0
    target = np.asarray([1.5])
    observed = integrate_piecewise_linear_profile(
        radius, values, target, outer_tail="zero"
    )[0]
    boundary = np.arcsin(target[0] / radius[-1])
    expected = 3.0 * target[0] * (
        np.log(np.tan(np.pi / 4.0)) - np.log(np.tan(boundary / 2.0))
    ) - 10.0 * (np.pi / 2.0 - boundary)
    np.testing.assert_allclose(observed, expected, rtol=0, atol=1e-14)
    assert values[0] < 0


def test_sis_tail_has_closed_form() -> None:
    radius = np.asarray([1.0, 2.0])
    values = 5.0 / radius
    target = np.asarray([3.0])
    observed = integrate_piecewise_linear_profile(
        radius, values, target, outer_tail="sis"
    )
    np.testing.assert_allclose(observed, [5.0 / 3.0], rtol=0, atol=1e-15)


def test_analytic_piecewise_integral_matches_independent_quadrature() -> None:
    radius = np.asarray([0.7, 1.4, 2.8, 5.6])
    values = np.asarray([-1.2, 0.4, 2.1, -0.3])
    targets = np.asarray([0.7, 1.1, 2.3, 5.0, 7.0])

    def profile(query: float) -> float:
        if query > radius[-1]:
            return values[-1] * radius[-1] / query
        return float(np.interp(query, radius, values))

    expected = np.asarray(
        [
            quad(
                lambda theta: profile(target / np.sin(theta)),
                1e-12,
                np.pi / 2.0,
                points=[
                    np.arcsin(target / knot)
                    for knot in radius
                    if target < knot
                ],
                epsabs=1e-12,
                epsrel=1e-12,
                limit=200,
            )[0]
            for target in targets
        ]
    )
    observed = integrate_piecewise_linear_profile(
        radius, values, targets, outer_tail="sis"
    )
    np.testing.assert_allclose(observed, expected, rtol=2e-11, atol=2e-12)


def test_profile_deprojection_propagates_variance_and_keeps_sign() -> None:
    centers = np.asarray([1.0, 2.0, 3.0])
    edges = np.asarray([0.5, 1.5, 2.5, 3.5])
    profiles = np.asarray([[-2.0, -1.0, 0.5], [2.0, 1.0, 0.5]])
    variances = np.full_like(profiles, 4.0)
    result = deproject_individual_profiles(
        centers,
        edges,
        profiles,
        variances,
        np.asarray([[1.0, 2.0], [1.0, 2.0]]),
    )
    assert result["gobs_m_s2"][0, 0] < 0
    assert np.all(result["variance_gobs"] > 0)
    factor = 4.0 * G_MPC_KM2_S2_MSUN * (1e6 / MPC_M)
    assert np.nanmax(np.abs(result["gobs_m_s2"])) < factor * 10


def test_inverse_variance_stack_matches_closed_form() -> None:
    result = stack_inverse_variance(
        np.asarray([[1.0, 3.0], [3.0, 7.0]]),
        np.asarray([[1.0, 4.0], [1.0, 4.0]]),
    )
    np.testing.assert_allclose(result["stacked"], [2.0, 5.0])
    np.testing.assert_allclose(result["variance"], [0.5, 2.0])
    np.testing.assert_array_equal(result["effective_lenses"], [2, 2])
