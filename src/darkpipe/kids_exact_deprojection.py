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


def _integration_operator(
    radius_mpc: np.ndarray,
    evaluation_radius_mpc: np.ndarray,
    *,
    outer_tail: TailRule,
    append_zero_radius_mpc: float | None = None,
) -> np.ndarray:
    """Return the exact linear map from profile knots to integrated targets."""

    radius = np.asarray(radius_mpc, dtype=np.float64)
    evaluation = np.asarray(evaluation_radius_mpc, dtype=np.float64)
    basis_count = len(radius)
    operator_radius = radius
    if append_zero_radius_mpc is not None:
        if append_zero_radius_mpc <= radius[-1]:
            raise ValueError("the appended zero radius must exceed the last profile knot")
        operator_radius = np.append(radius, append_zero_radius_mpc)
    columns = []
    for index in range(basis_count):
        basis = np.zeros(len(operator_radius), dtype=np.float64)
        basis[index] = 1.0
        columns.append(
            integrate_piecewise_linear_profile(
                operator_radius,
                basis,
                evaluation,
                outer_tail=outer_tail,
            )
        )
    return np.column_stack(columns)


def _integrate_profile_rows(
    radius_mpc: np.ndarray,
    values: np.ndarray,
    evaluation_radius_mpc: np.ndarray,
    *,
    outer_tail: TailRule,
) -> np.ndarray:
    """Vectorize the exact integral for rows with a shared knot grid.

    Each profile row may have its own evaluation radii.  The calculation is
    algebraically identical to :func:`integrate_piecewise_linear_profile`;
    only the scalar target loop is replaced by broadcasting over rows and
    targets.  This is the production path for object-level fixed-gbar RARs.
    """

    radius = np.asarray(radius_mpc, dtype=np.float64)
    profiles = np.asarray(values, dtype=np.float64)
    targets = np.asarray(evaluation_radius_mpc, dtype=np.float64)
    if radius.ndim != 1 or len(radius) < 2:
        raise ValueError("at least two one-dimensional profile knots are required")
    if profiles.ndim != 2 or profiles.shape[1] != len(radius):
        raise ValueError("profile rows must share the supplied knot grid")
    if targets.ndim != 2 or targets.shape[0] != profiles.shape[0]:
        raise ValueError("targets must have shape (profile, target)")
    if np.any(~np.isfinite(radius)) or np.any(~np.isfinite(profiles)):
        raise ValueError("profile knots and values must be finite")
    if np.any(radius <= 0) or np.any(np.diff(radius) <= 0):
        raise ValueError("profile radii must be positive and strictly increasing")
    if outer_tail not in {"sis", "flat", "zero"}:
        raise ValueError(f"unsupported outer tail: {outer_tail}")

    valid_target = np.isfinite(targets) & (targets > 0) & (targets >= radius[0])
    safe_target = np.where(valid_target, targets, radius[0])
    tail_boundary = np.where(
        safe_target >= radius[-1],
        np.pi / 2.0,
        np.arcsin(np.clip(safe_target / radius[-1], 0.0, 1.0)),
    )
    if outer_tail == "sis":
        integral = (
            profiles[:, -1, None]
            * radius[-1]
            / safe_target
            * (1.0 - np.cos(tail_boundary))
        )
    elif outer_tail == "flat":
        integral = profiles[:, -1, None] * tail_boundary
    else:
        integral = np.zeros_like(targets, dtype=np.float64)

    for index in range(len(radius) - 1):
        lower_radius = np.maximum(safe_target, radius[index])
        upper_radius = radius[index + 1]
        active = valid_target & (lower_radius < upper_radius)
        theta_low = np.arcsin(np.clip(safe_target / upper_radius, 0.0, 1.0))
        theta_high = np.arcsin(
            np.clip(safe_target / np.maximum(lower_radius, np.finfo(float).tiny), 0.0, 1.0)
        )
        slope = (
            (profiles[:, index + 1] - profiles[:, index])
            / (radius[index + 1] - radius[index])
        )[:, None]
        intercept = (profiles[:, index] - slope[:, 0] * radius[index])[:, None]
        with np.errstate(divide="ignore", invalid="ignore"):
            csc_integral = np.log(np.tan(theta_high / 2.0)) - np.log(
                np.tan(theta_low / 2.0)
            )
        contribution = (
            slope * safe_target * csc_integral
            + intercept * (theta_high - theta_low)
        )
        integral += np.where(active, contribution, 0.0)
    return np.where(valid_target, integral, np.nan)


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

    # Because the piecewise-linear integral is a linear map, lenses sharing a
    # validity mask can be evaluated exactly as a group.  Shared targets use a
    # matrix operator; object-specific fixed-gbar targets use the vectorized
    # analytic expression above.  Neither path changes interpolation, sign,
    # tail rule, or the Eq. 60 variance construction.
    shared_evaluation = bool(
        evaluation.shape[0] > 0
        and np.array_equal(evaluation, np.broadcast_to(evaluation[0], evaluation.shape))
    )
    valid_surface = np.isfinite(profiles) & np.isfinite(variances) & (variances >= 0)
    unique_masks, inverse = np.unique(valid_surface, axis=0, return_inverse=True)
    for mask_index, valid in enumerate(unique_masks):
        if np.count_nonzero(valid) < 2:
            continue
        lenses = np.flatnonzero(inverse == mask_index)
        valid_indices = np.flatnonzero(valid)
        profile_radius = centers[valid]
        if shared_evaluation:
            profile_operator = _integration_operator(
                profile_radius,
                evaluation[0],
                outer_tail=outer_tail,
            )
            acceleration[lenses] = esd_to_acceleration * (
                profiles[np.ix_(lenses, valid_indices)] @ profile_operator.T
            )

        else:
            acceleration[lenses] = esd_to_acceleration * _integrate_profile_rows(
                profile_radius,
                profiles[np.ix_(lenses, valid_indices)],
                evaluation[lenses],
                outer_tail=outer_tail,
            )

        last_edge = float(edges[valid_indices[-1] + 1])
        if last_edge > profile_radius[-1]:
            variance_radius = np.append(profile_radius, last_edge)
            variance_profiles = np.column_stack(
                (variances[np.ix_(lenses, valid_indices)], np.zeros(len(lenses)))
            )
        else:
            variance_radius = profile_radius
            variance_profiles = variances[np.ix_(lenses, valid_indices)]
        if shared_evaluation:
            if last_edge > profile_radius[-1]:
                variance_operator = _integration_operator(
                    profile_radius,
                    evaluation[0],
                    outer_tail="zero",
                    append_zero_radius_mpc=last_edge,
                )
            else:
                variance_operator = _integration_operator(
                    profile_radius,
                    evaluation[0],
                    outer_tail="zero",
                )
            acceleration_variance[lenses] = esd_to_acceleration**2 * (
                variances[np.ix_(lenses, valid_indices)] @ variance_operator.T
            )
        else:
            acceleration_variance[lenses] = (
                esd_to_acceleration**2
                * _integrate_profile_rows(
                    variance_radius,
                    variance_profiles,
                    evaluation[lenses],
                    outer_tail="zero",
                )
            )
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
