"""Signed, piecewise-linear KiDS deprojection for the v0.17 object pipeline.

This module integrates the published spherical deprojection formula exactly
for the explicitly assumed piecewise-linear ESD interpolant.  "Exact" refers
to that mathematical integration, not to the physical assumptions, input
catalogues, random subtraction, covariance model, or cosmological ontology.
"""

from __future__ import annotations

import math
from typing import Literal

import numpy as np

from .object_lensing import G_MPC_KM2_S2_MSUN, MPC_M


TailRule = Literal["sis", "flat", "zero"]
EXACT_DEPROJECTION_AUTHORITY = (
    "ANALYTIC_INTEGRAL_OF_SIGNED_PIECEWISE_LINEAR_ESD_NO_MODEL_ADJUDICATION"
)


def _log_tan_half(theta: float) -> float:
    return math.log(math.tan(theta / 2.0))


def integrate_piecewise_linear_profile(
    radius_mpc: np.ndarray,
    values: np.ndarray,
    evaluation_radius_mpc: np.ndarray,
    *,
    outer_tail: TailRule,
) -> np.ndarray:
    """Integrate ``profile(R/sin(theta))`` from zero to pi/2.

    The profile is linear in physical radius between supplied knots.  It may
    have either sign.  Evaluation below the first knot is deliberately typed
    as unavailable because no inner extrapolation is assumed.
    """

    radius = np.asarray(radius_mpc, dtype=np.float64)
    profile = np.asarray(values, dtype=np.float64)
    targets = np.asarray(evaluation_radius_mpc, dtype=np.float64)
    if radius.ndim != 1 or profile.shape != radius.shape or len(radius) < 2:
        raise ValueError("at least two one-dimensional profile knots are required")
    if np.any(~np.isfinite(radius)) or np.any(~np.isfinite(profile)):
        raise ValueError("profile knots and values must be finite")
    if np.any(radius <= 0) or np.any(np.diff(radius) <= 0):
        raise ValueError("profile radii must be positive and strictly increasing")
    if outer_tail not in {"sis", "flat", "zero"}:
        raise ValueError(f"unsupported outer tail: {outer_tail}")

    output = np.full(targets.shape, np.nan, dtype=np.float64)
    for output_index, target_value in np.ndenumerate(targets):
        target = float(target_value)
        if not math.isfinite(target) or target <= 0 or target < radius[0]:
            continue

        if target >= radius[-1]:
            tail_boundary = math.pi / 2.0
        else:
            tail_boundary = math.asin(target / float(radius[-1]))
        if outer_tail == "sis":
            integral = (
                float(profile[-1])
                * float(radius[-1])
                / target
                * (1.0 - math.cos(tail_boundary))
            )
        elif outer_tail == "flat":
            integral = float(profile[-1]) * tail_boundary
        else:
            integral = 0.0

        for index in range(len(radius) - 1):
            lower_radius = max(target, float(radius[index]))
            upper_radius = float(radius[index + 1])
            if lower_radius >= upper_radius:
                continue
            theta_low = math.asin(target / upper_radius)
            theta_high = math.asin(min(1.0, target / lower_radius))
            slope = float(
                (profile[index + 1] - profile[index])
                / (radius[index + 1] - radius[index])
            )
            intercept = float(profile[index] - slope * radius[index])
            csc_integral = _log_tan_half(theta_high) - _log_tan_half(theta_low)
            integral += (
                slope * target * csc_integral
                + intercept * (theta_high - theta_low)
            )
        output[output_index] = integral
    return output


def deproject_individual_profiles(
    radial_centers_mpc: np.ndarray,
    radial_edges_mpc: np.ndarray,
    esd_msun_mpc2: np.ndarray,
    variance_esd: np.ndarray,
    evaluation_radius_mpc: np.ndarray,
    *,
    outer_tail: TailRule = "sis",
) -> dict[str, np.ndarray | str]:
    """Deproject signed per-lens ESDs and propagate Eq. 60 variances."""

    centers = np.asarray(radial_centers_mpc, dtype=np.float64)
    edges = np.asarray(radial_edges_mpc, dtype=np.float64)
    profiles = np.asarray(esd_msun_mpc2, dtype=np.float64)
    variances = np.asarray(variance_esd, dtype=np.float64)
    evaluation = np.asarray(evaluation_radius_mpc, dtype=np.float64)
    if profiles.ndim != 2 or variances.shape != profiles.shape:
        raise ValueError("ESD and variance must have equal (lens, radial-bin) shape")
    if profiles.shape[1] != len(centers) or len(edges) != len(centers) + 1:
        raise ValueError("radial centers/edges do not match profile shape")
    if evaluation.ndim == 1:
        evaluation = np.broadcast_to(evaluation, (profiles.shape[0], len(evaluation)))
    if evaluation.ndim != 2 or evaluation.shape[0] != profiles.shape[0]:
        raise ValueError("evaluation radii must have shape (lens, target)")

    acceleration = np.full(evaluation.shape, np.nan, dtype=np.float64)
    acceleration_variance = np.full(evaluation.shape, np.nan, dtype=np.float64)
    esd_to_acceleration = 4.0 * G_MPC_KM2_S2_MSUN * (1e6 / MPC_M)
    for lens in range(profiles.shape[0]):
        valid = (
            np.isfinite(profiles[lens])
            & np.isfinite(variances[lens])
            & (variances[lens] >= 0)
        )
        if np.count_nonzero(valid) < 2:
            continue
        valid_indices = np.flatnonzero(valid)
        profile_radius = centers[valid]
        acceleration[lens] = esd_to_acceleration * integrate_piecewise_linear_profile(
            profile_radius,
            profiles[lens, valid],
            evaluation[lens],
            outer_tail=outer_tail,
        )

        # Eq. 60 sets uncertainty to zero beyond the last bin edge.  The extra
        # zero knot makes the specified linear fade from the last bin center to
        # that edge explicit before the zero tail is integrated.
        last_edge = float(edges[valid_indices[-1] + 1])
        variance_radius = profile_radius.copy()
        variance_profile = variances[lens, valid].copy()
        if last_edge > variance_radius[-1]:
            variance_radius = np.append(variance_radius, last_edge)
            variance_profile = np.append(variance_profile, 0.0)
        variance_integral = integrate_piecewise_linear_profile(
            variance_radius,
            variance_profile,
            evaluation[lens],
            outer_tail="zero",
        )
        acceleration_variance[lens] = esd_to_acceleration**2 * variance_integral
    return {
        "gobs_m_s2": acceleration,
        "variance_gobs": acceleration_variance,
        "authority": EXACT_DEPROJECTION_AUTHORITY,
        "interpolation": "LINEAR_IN_PHYSICAL_RADIUS_SIGNED",
        "outer_tail": outer_tail,
    }


def stack_inverse_variance(
    values: np.ndarray,
    variances: np.ndarray,
) -> dict[str, np.ndarray]:
    """Apply Eqs. 55 and 59 to an already deprojected lens surface."""

    signal = np.asarray(values, dtype=np.float64)
    variance = np.asarray(variances, dtype=np.float64)
    if signal.ndim != 2 or variance.shape != signal.shape:
        raise ValueError("signal and variance must have equal (lens, target) shape")
    valid = np.isfinite(signal) & np.isfinite(variance) & (variance > 0)
    weight = np.zeros_like(variance)
    weight[valid] = 1.0 / variance[valid]
    normalization = weight.sum(axis=0)
    stacked = np.divide(
        np.where(valid, signal * weight, 0.0).sum(axis=0),
        normalization,
        out=np.full(signal.shape[1], np.nan),
        where=normalization > 0,
    )
    stacked_variance = np.divide(
        1.0,
        normalization,
        out=np.full(signal.shape[1], np.nan),
        where=normalization > 0,
    )
    return {
        "stacked": stacked,
        "variance": stacked_variance,
        "weight_sum": normalization,
        "effective_lenses": valid.sum(axis=0).astype(np.int64),
    }


__all__ = [
    "EXACT_DEPROJECTION_AUTHORITY",
    "deproject_individual_profiles",
    "integrate_piecewise_linear_profile",
    "stack_inverse_variance",
]
