"""External RAR reference and shared random-correction utilities.

The published Brouwer et al. surface is a comparison reference, not an
independent replication of DarkPipe: it uses overlapping KiDS data, a
different lens definition and the SIS approximation.  The random-control
helper keeps the uncertainty of one shared pilot profile from being
incorrectly divided by the number of signal lenses.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np

from .object_lensing import G_MPC_KM2_S2_MSUN, MPC_M


BROUWER_G_PC = 4.52e-30
PC_M = 3.086e16
BROUWER_ESD_TO_GOBS = 4.0 * BROUWER_G_PC * PC_M
EXTERNAL_REFERENCE_AUTHORITY = (
    "EXTERNAL_PUBLISHED_RANDOM_SUBTRACTED_REFERENCE_NO_SUBSTITUTE_FOR_DARKPIPE_50X_CONTROL"
)
ESD_TO_SIS_GOBS = 4.0 * G_MPC_KM2_S2_MSUN * (1e6 / MPC_M)
MISTELE_REPRODUCTION_AUTHORITY = (
    "PUBLISHED_MISTELE2024_TABLE1_TARGET_SAME_DECLARED_106843_LENS_SELECTION"
)


def load_mistele2024_table1(path: Path) -> dict[str, np.ndarray | str]:
    """Load the published Table 1 target for the DarkPipe reproduction."""

    payload = "".join(
        line
        for line in Path(path).read_text(encoding="utf-8").splitlines(keepends=True)
        if line.strip() and not line.lstrip().startswith("#")
    )
    table = np.genfromtxt(io.StringIO(payload), delimiter=",", names=True)
    required = (
        "log10_gbar_m_s2",
        "log10_gobs_m_s2",
        "sigma_statistical_log10_gobs",
        "sigma_systematic_log10_gobs",
    )
    if table.dtype.names != required or len(table) != 15:
        raise ValueError("Mistele Table 1 schema or row count differs")
    log_gbar = np.asarray(table[required[0]], dtype=np.float64)
    if np.any(~np.isfinite(log_gbar)) or np.any(np.diff(log_gbar) <= 0):
        raise ValueError("Mistele Table 1 gbar grid must increase")
    return {
        "gbar_m_s2": np.power(10.0, log_gbar),
        "gobs_m_s2": np.power(10.0, np.asarray(table[required[1]], dtype=np.float64)),
        "log10_gbar_m_s2": log_gbar,
        "log10_gobs_m_s2": np.asarray(table[required[1]], dtype=np.float64),
        "sigma_statistical_log10_gobs": np.asarray(table[required[2]], dtype=np.float64),
        "sigma_systematic_log10_gobs": np.asarray(table[required[3]], dtype=np.float64),
        "authority": MISTELE_REPRODUCTION_AUTHORITY,
    }


def mistele_reproduction_diagnostic(
    darkpipe_gobs: np.ndarray,
    reference: dict[str, np.ndarray | str],
) -> dict[str, float | int | bool | None | str]:
    """Apply the preregistered central-value reproduction gates."""

    dark = np.asarray(darkpipe_gobs, dtype=np.float64)
    log_reference = np.asarray(reference["log10_gobs_m_s2"], dtype=np.float64)
    statistical = np.asarray(reference["sigma_statistical_log10_gobs"], dtype=np.float64)
    systematic = np.asarray(reference["sigma_systematic_log10_gobs"], dtype=np.float64)
    if not (dark.shape == log_reference.shape == statistical.shape == systematic.shape):
        raise ValueError("Mistele reproduction vectors differ")
    positive = np.isfinite(dark) & (dark > 0)
    log_dark = np.full_like(dark, np.nan)
    log_dark[positive] = np.log10(dark[positive])
    total = np.sqrt(statistical**2 + systematic**2)
    inside = positive & (np.abs(log_dark - log_reference) <= total)
    median_absolute = (
        float(np.median(np.abs(log_dark[positive] - log_reference[positive])))
        if np.any(positive)
        else None
    )
    all_inside = bool(np.all(inside))
    median_gate = bool(median_absolute is not None and median_absolute <= 0.05)
    return {
        "published_bins": int(len(dark)),
        "positive_estimable_bins": int(np.count_nonzero(positive)),
        "central_points_inside_published_total_1sigma": int(np.count_nonzero(inside)),
        "all_15_inside_published_total_1sigma": all_inside,
        "median_absolute_log10_difference_dex": median_absolute,
        "median_absolute_difference_le_0p05_dex": median_gate,
        "monotonic_residual_gate": "NOT_ESTIMABLE_FOUR_NONPOSITIVE_CENTRAL_VALUES"
        if np.count_nonzero(positive) < len(dark)
        else "NOT_RUN_IN_THIS_FUNCTION",
        "reproduction_gate": bool(all_inside and median_gate and np.all(positive)),
        "authority": "PREREGISTERED_CENTRAL_VALUE_GATE_NO_MODEL_OR_ONTOLOGY_ADJUDICATION",
    }


def load_brouwer_rar_reference(
    profile_path: Path,
    covariance_path: Path,
) -> dict[str, np.ndarray | str]:
    """Load and calibrate the official Brouwer 2021 KiDS RAR surface."""

    profile = np.loadtxt(profile_path, comments="#", dtype=np.float64)
    covariance_rows = np.loadtxt(covariance_path, comments="#", dtype=np.float64)
    if profile.ndim != 2 or profile.shape[1] < 5 or len(profile) < 2:
        raise ValueError("invalid Brouwer RAR profile")
    if covariance_rows.ndim != 2 or covariance_rows.shape[1] < 7:
        raise ValueError("invalid Brouwer covariance")
    gbar = profile[:, 0]
    if np.any(gbar <= 0) or np.any(np.diff(gbar) <= 0):
        raise ValueError("Brouwer gbar grid must be positive and increasing")
    bias = profile[:, 4]
    if np.any(~np.isfinite(bias)) or np.any(bias <= 0):
        raise ValueError("invalid Brouwer multiplicative calibration")

    covariance_esd = np.full((len(gbar), len(gbar)), np.nan, dtype=np.float64)
    for row in covariance_rows:
        i = int(np.argmin(np.abs(gbar - row[2])))
        j = int(np.argmin(np.abs(gbar - row[3])))
        if not (
            np.isclose(gbar[i], row[2], rtol=2e-4, atol=0.0)
            and np.isclose(gbar[j], row[3], rtol=2e-4, atol=0.0)
        ):
            raise ValueError("covariance acceleration grid differs from profile")
        covariance_esd[i, j] = row[4] / row[6]
    if np.any(~np.isfinite(covariance_esd)):
        raise ValueError("Brouwer covariance is incomplete")
    if not np.allclose(covariance_esd, covariance_esd.T, rtol=2e-12, atol=1e-18):
        raise ValueError("Brouwer covariance is not symmetric")

    return {
        "gbar_m_s2": gbar,
        "gobs_m_s2": BROUWER_ESD_TO_GOBS * profile[:, 1] / bias,
        "cross_gobs_m_s2": BROUWER_ESD_TO_GOBS * profile[:, 2] / bias,
        "covariance_gobs": covariance_esd * BROUWER_ESD_TO_GOBS**2,
        "authority": EXTERNAL_REFERENCE_AUTHORITY,
    }


def shared_random_corrected_stack(
    signal: np.ndarray,
    signal_variance: np.ndarray,
    evaluation_radius_mpc: np.ndarray,
    random_radius_mpc: np.ndarray,
    random_signal: np.ndarray,
    random_variance: np.ndarray,
) -> dict[str, np.ndarray | str]:
    """Stack ``signal - random(R)`` with shared-profile uncertainty.

    Random values are linearly interpolated in physical radius and never
    extrapolated.  Signal lenses are inverse-variance stacked.  Interpolation
    coefficients are then aggregated before propagating the pilot variance,
    so the uncertainty of the one shared random curve is not treated as an
    independent error for every signal lens.  Radial random covariance is not
    available; the returned variance is therefore explicitly diagonal-only.
    """

    values = np.asarray(signal, dtype=np.float64)
    variances = np.asarray(signal_variance, dtype=np.float64)
    targets = np.asarray(evaluation_radius_mpc, dtype=np.float64)
    radius = np.asarray(random_radius_mpc, dtype=np.float64)
    random_values = np.asarray(random_signal, dtype=np.float64)
    random_variances = np.asarray(random_variance, dtype=np.float64)
    if values.ndim != 2 or variances.shape != values.shape or targets.shape != values.shape:
        raise ValueError("signal, variance and target radii must share (lens, target) shape")
    if not (
        radius.ndim == random_values.ndim == random_variances.ndim == 1
        and len(radius) == len(random_values) == len(random_variances)
        and len(radius) >= 2
    ):
        raise ValueError("random profile arrays must be equal one-dimensional vectors")
    if np.any(np.diff(radius) <= 0):
        raise ValueError("random radii must be strictly increasing")

    target_count = values.shape[1]
    corrected = np.full(target_count, np.nan)
    matched_signal = np.full(target_count, np.nan)
    correction = np.full(target_count, np.nan)
    signal_stack_variance = np.full(target_count, np.nan)
    correction_variance = np.full(target_count, np.nan)
    total_variance = np.full(target_count, np.nan)
    effective_lenses = np.zeros(target_count, dtype=np.int64)

    for column in range(target_count):
        query = targets[:, column]
        interval = np.searchsorted(radius, query, side="right") - 1
        at_upper_edge = query == radius[-1]
        interval[at_upper_edge] = len(radius) - 2
        in_range = (
            np.isfinite(query)
            & (query >= radius[0])
            & (query <= radius[-1])
            & (interval >= 0)
            & (interval < len(radius) - 1)
        )
        safe_interval = np.clip(interval, 0, len(radius) - 2)
        fraction = (
            (query - radius[safe_interval])
            / (radius[safe_interval + 1] - radius[safe_interval])
        )
        valid_random_nodes = (
            np.isfinite(random_values[safe_interval])
            & np.isfinite(random_values[safe_interval + 1])
            & np.isfinite(random_variances[safe_interval])
            & np.isfinite(random_variances[safe_interval + 1])
            & (random_variances[safe_interval] >= 0)
            & (random_variances[safe_interval + 1] >= 0)
        )
        valid = (
            in_range
            & valid_random_nodes
            & np.isfinite(values[:, column])
            & np.isfinite(variances[:, column])
            & (variances[:, column] > 0)
        )
        if not np.any(valid):
            continue
        weight = 1.0 / variances[valid, column]
        weight_sum = weight.sum()
        normalized = weight / weight_sum
        indices = safe_interval[valid]
        frac = fraction[valid]
        coefficients = np.zeros(len(radius), dtype=np.float64)
        np.add.at(coefficients, indices, normalized * (1.0 - frac))
        np.add.at(coefficients, indices + 1, normalized * frac)
        matched_signal[column] = np.sum(normalized * values[valid, column])
        correction[column] = coefficients @ random_values
        corrected[column] = matched_signal[column] - correction[column]
        signal_stack_variance[column] = 1.0 / weight_sum
        correction_variance[column] = np.sum(coefficients**2 * random_variances)
        total_variance[column] = (
            signal_stack_variance[column] + correction_variance[column]
        )
        effective_lenses[column] = np.count_nonzero(valid)

    return {
        "matched_signal": matched_signal,
        "random_correction": correction,
        "corrected": corrected,
        "signal_variance": signal_stack_variance,
        "random_variance_diagonal": correction_variance,
        "corrected_variance_diagonal": total_variance,
        "effective_lenses": effective_lenses,
        "authority": "EXPLORATORY_SHARED_PILOT_CORRECTION_NO_RANDOM_RADIAL_COVARIANCE",
    }


def stack_interpolated_profile(
    radial_centers_mpc: np.ndarray,
    profiles: np.ndarray,
    profile_variances: np.ndarray,
    lens_weights: np.ndarray,
    evaluation_radius_mpc: np.ndarray,
) -> dict[str, np.ndarray | str]:
    """Stack linearly interpolated per-lens profiles with Eq. 54 weights.

    This bounded-memory diagnostic localizes whether a failed exact RAR is
    already present in the upstream ESD surface.  Missing radial cells are
    bridged between valid knots as specified by Mistele et al.; no inner or
    outer extrapolation is introduced.
    """

    centers = np.asarray(radial_centers_mpc, dtype=np.float64)
    values = np.asarray(profiles, dtype=np.float64)
    variances = np.asarray(profile_variances, dtype=np.float64)
    weights = np.asarray(lens_weights, dtype=np.float64)
    targets = np.asarray(evaluation_radius_mpc, dtype=np.float64)
    if values.ndim != 2 or variances.shape != values.shape or weights.shape != values.shape:
        raise ValueError("profile, variance and weight surfaces must match")
    if targets.ndim != 2 or targets.shape[0] != values.shape[0]:
        raise ValueError("targets must have shape (lens, target)")
    if len(centers) != values.shape[1] or np.any(np.diff(centers) <= 0):
        raise ValueError("radial centers do not match the profiles")

    numerator = np.zeros(targets.shape[1], dtype=np.float64)
    denominator = np.zeros(targets.shape[1], dtype=np.float64)
    variance_numerator = np.zeros(targets.shape[1], dtype=np.float64)
    effective = np.zeros(targets.shape[1], dtype=np.int64)
    valid_surface = (
        np.isfinite(values)
        & np.isfinite(variances)
        & (variances >= 0)
        & np.isfinite(weights)
        & (weights > 0)
    )
    unique_masks, inverse = np.unique(valid_surface, axis=0, return_inverse=True)
    for mask_index, valid_knots in enumerate(unique_masks):
        if np.count_nonzero(valid_knots) < 2:
            continue
        lenses = np.flatnonzero(inverse == mask_index)
        knots = centers[valid_knots]
        query = targets[lenses]
        interval = np.searchsorted(knots, query, side="right") - 1
        at_upper = query == knots[-1]
        interval[at_upper] = len(knots) - 2
        valid_query = (
            np.isfinite(query)
            & (query >= knots[0])
            & (query <= knots[-1])
            & (interval >= 0)
            & (interval < len(knots) - 1)
        )
        safe = np.clip(interval, 0, len(knots) - 2)
        fraction = (query - knots[safe]) / (knots[safe + 1] - knots[safe])
        group_values = values[np.ix_(lenses, np.flatnonzero(valid_knots))]
        group_variances = variances[np.ix_(lenses, np.flatnonzero(valid_knots))]
        group_weights = weights[np.ix_(lenses, np.flatnonzero(valid_knots))]
        low_value = np.take_along_axis(group_values, safe, axis=1)
        high_value = np.take_along_axis(group_values, safe + 1, axis=1)
        low_variance = np.take_along_axis(group_variances, safe, axis=1)
        high_variance = np.take_along_axis(group_variances, safe + 1, axis=1)
        low_weight = np.take_along_axis(group_weights, safe, axis=1)
        high_weight = np.take_along_axis(group_weights, safe + 1, axis=1)
        interpolated_value = low_value + fraction * (high_value - low_value)
        interpolated_variance = low_variance + fraction * (
            high_variance - low_variance
        )
        interpolated_weight = low_weight + fraction * (high_weight - low_weight)
        usable = (
            valid_query
            & np.isfinite(interpolated_value)
            & np.isfinite(interpolated_variance)
            & (interpolated_variance >= 0)
            & np.isfinite(interpolated_weight)
            & (interpolated_weight > 0)
        )
        numerator += np.where(
            usable, interpolated_weight * interpolated_value, 0.0
        ).sum(axis=0)
        denominator += np.where(usable, interpolated_weight, 0.0).sum(axis=0)
        variance_numerator += np.where(
            usable, interpolated_weight**2 * interpolated_variance, 0.0
        ).sum(axis=0)
        effective += usable.sum(axis=0).astype(np.int64)
    stacked = np.divide(
        numerator,
        denominator,
        out=np.full_like(numerator, np.nan),
        where=denominator > 0,
    )
    stacked_variance = np.divide(
        variance_numerator,
        denominator**2,
        out=np.full_like(numerator, np.nan),
        where=denominator > 0,
    )
    return {
        "stacked": stacked,
        "variance": stacked_variance,
        "weight_sum": denominator,
        "effective_lenses": effective,
        "authority": "EQ54_VARIABLE_RADIUS_LINEAR_INTERPOLATION_NO_EXTRAPOLATION",
    }


def reference_residual_diagnostic(
    darkpipe_gobs: np.ndarray,
    darkpipe_variance: np.ndarray,
    reference_gobs: np.ndarray,
    reference_covariance: np.ndarray,
) -> dict[str, float | int | None | str]:
    """Return bounded descriptive diagnostics, not a hypothesis test."""

    dark = np.asarray(darkpipe_gobs, dtype=np.float64)
    dark_variance = np.asarray(darkpipe_variance, dtype=np.float64)
    reference = np.asarray(reference_gobs, dtype=np.float64)
    covariance = np.asarray(reference_covariance, dtype=np.float64)
    if dark.shape != reference.shape or dark_variance.shape != dark.shape:
        raise ValueError("RAR vectors differ")
    if covariance.shape != (len(dark), len(dark)):
        raise ValueError("reference covariance shape differs")
    valid = np.isfinite(dark) & np.isfinite(reference)
    indices = np.flatnonzero(valid)
    if len(indices) == 0:
        return {
            "valid_bins": 0,
            "reference_covariance_chi2_diagnostic": None,
            "median_log10_darkpipe_over_reference": None,
            "authority": "DESCRIPTIVE_NOT_A_HYPOTHESIS_TEST",
        }
    residual = dark[indices] - reference[indices]
    subcovariance = covariance[np.ix_(indices, indices)]
    chi2 = float(residual @ np.linalg.pinv(subcovariance, hermitian=True) @ residual)
    positive = (dark[indices] > 0) & (reference[indices] > 0)
    median_log_ratio = (
        float(np.median(np.log10(dark[indices][positive] / reference[indices][positive])))
        if np.any(positive)
        else None
    )
    combined_diagonal = np.diag(subcovariance) + dark_variance[indices]
    diagonal_z = np.divide(
        residual,
        np.sqrt(combined_diagonal),
        out=np.full_like(residual, np.nan),
        where=combined_diagonal > 0,
    )
    return {
        "valid_bins": int(len(indices)),
        "darkpipe_positive_bins": int(np.count_nonzero(dark[indices] > 0)),
        "reference_positive_bins": int(np.count_nonzero(reference[indices] > 0)),
        "reference_covariance_chi2_diagnostic": chi2,
        "reference_covariance_dof_label_only": int(len(indices)),
        "median_log10_darkpipe_over_reference": median_log_ratio,
        "max_abs_combined_diagonal_residual_z": float(np.nanmax(np.abs(diagonal_z))),
        "authority": "DESCRIPTIVE_NOT_A_HYPOTHESIS_TEST_SHARED_DATA_DIFFERENT_SELECTIONS",
    }


__all__ = [
    "BROUWER_ESD_TO_GOBS",
    "ESD_TO_SIS_GOBS",
    "EXTERNAL_REFERENCE_AUTHORITY",
    "MISTELE_REPRODUCTION_AUTHORITY",
    "load_brouwer_rar_reference",
    "load_mistele2024_table1",
    "mistele_reproduction_diagnostic",
    "reference_residual_diagnostic",
    "shared_random_corrected_stack",
    "stack_interpolated_profile",
]
