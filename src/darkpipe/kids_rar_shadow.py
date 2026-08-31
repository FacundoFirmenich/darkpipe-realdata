"""Derived observational shadows from the published Mistele et al. KiDS RAR.

This module operates on the published 15-bin table.  It derives effective
inobservables without assigning them a particle, plasma or modified-gravity
ontology.  Cross-bin inference is intentionally withheld because the public
table does not provide the full covariance used by the analysis.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


RAR_SHADOW_AUTHORITY = "PUBLISHED_BIN_LEVEL_DERIVED_INOBSERVABLE_NO_ONTOLOGY"


def mond_rar_acceleration(gbar: np.ndarray, a0: float = 1.2e-10) -> np.ndarray:
    values = np.asarray(gbar, dtype=float)
    return values / (1.0 - np.exp(-np.sqrt(values / a0)))


def derive_rar_shadows(table: pd.DataFrame) -> pd.DataFrame:
    required = {
        "log10_gbar_m_s2",
        "log10_gobs_m_s2",
        "sigma_stat_log10_gobs",
        "sigma_deprojection_systematic_log10_gobs",
    }
    if not required.issubset(table.columns):
        raise ValueError(f"missing columns: {sorted(required - set(table.columns))}")
    output = table.copy()
    gbar = np.power(10.0, output["log10_gbar_m_s2"].to_numpy(float))
    gobs = np.power(10.0, output["log10_gobs_m_s2"].to_numpy(float))
    eta = output["log10_gobs_m_s2"].to_numpy(float) - output["log10_gbar_m_s2"].to_numpy(float)
    sigma_stat = output["sigma_stat_log10_gobs"].to_numpy(float)
    sigma_deprojection = output["sigma_deprojection_systematic_log10_gobs"].to_numpy(float)
    sigma_measurement = np.sqrt(sigma_stat**2 + sigma_deprojection**2)
    gmond = mond_rar_acceleration(gbar)
    output["eta_log10_gobs_over_gbar"] = eta
    output["effective_acceleration_enhancement"] = np.power(10.0, eta)
    output["effective_excess_acceleration_m_s2"] = gobs - gbar
    output["sigma_measurement_log10_gobs"] = sigma_measurement
    output["sigma_with_fixed_stellar_mass_systematic_dex"] = np.sqrt(sigma_measurement**2 + 0.1**2)
    output["log10_gmond_m_s2_a0_1p2e10"] = np.log10(gmond)
    output["residual_to_mond_log10"] = np.log10(gobs) - np.log10(gmond)
    output["residual_to_mond_diagonal_z"] = output["residual_to_mond_log10"] / sigma_measurement
    output["newtonian_closure_diagonal_z"] = eta / sigma_measurement
    return output


def descriptive_summary(shadows: pd.DataFrame) -> dict[str, object]:
    eta = shadows["eta_log10_gobs_over_gbar"].to_numpy(float)
    enhancement = shadows["effective_acceleration_enhancement"].to_numpy(float)
    mond_residual = shadows["residual_to_mond_log10"].to_numpy(float)
    x = shadows["log10_gbar_m_s2"].to_numpy(float)
    y = shadows["log10_gobs_m_s2"].to_numpy(float)
    sigma = shadows["sigma_measurement_log10_gobs"].to_numpy(float)
    weights = 1.0 / sigma**2
    design = np.column_stack((np.ones_like(x), x))
    beta = np.linalg.solve(design.T @ (weights[:, None] * design), design.T @ (weights * y))
    return {
        "bins": int(len(shadows)),
        "eta_min_dex": float(np.min(eta)),
        "eta_max_dex": float(np.max(eta)),
        "enhancement_min": float(np.min(enhancement)),
        "enhancement_max": float(np.max(enhancement)),
        "all_effective_excess_accelerations_positive": bool(
            np.all(shadows["effective_excess_acceleration_m_s2"].to_numpy(float) > 0.0)
        ),
        "mond_residual_median_dex": float(np.median(mond_residual)),
        "mond_residual_max_abs_dex": float(np.max(np.abs(mond_residual))),
        "diagonal_weighted_line_intercept": float(beta[0]),
        "diagonal_weighted_line_slope": float(beta[1]),
        "cross_bin_covariance_available": False,
        "global_model_p_value": "NOT_ESTIMABLE_WITHOUT_COVARIANCE",
        "ontology": "NOT_IDENTIFIED",
        "authority": RAR_SHADOW_AUTHORITY,
    }


__all__ = [
    "RAR_SHADOW_AUTHORITY",
    "derive_rar_shadows",
    "descriptive_summary",
    "mond_rar_acceleration",
]
