"""Covariance-aware weak-lensing deprojection operator shadow.

The module works on the public Brouwer et al. (2021) KiDS-1000 ESD
rotation-curve profiles.  It compares the published singular-isothermal-
sphere (SIS) conversion with a stack-first application of the exact
spherical deprojection operator from Mistele et al. (2024).

The stack-first result is conditional: it is not an object-level
deprojection and must not be transferred automatically to the RAR stacked
in baryonic-acceleration coordinates.  No discrepancy is ontologized.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any, Literal, Sequence

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d


SCHEMA = "darkpipe.covariance_operator_shadow.v1"
CAMPAIGN_ID = "DP-COVOP-0.12-20260829"
AUTHORITY = (
    "DERIVED_OPERATOR_SENSITIVITY_CONDITIONAL_STACK_FIRST_"
    "FULL_PUBLISHED_ESD_COVARIANCE_NOT_ONTOLOGIZED"
)
RAR_TRANSFER_AUTHORITY = (
    "NOT_ESTIMABLE_DIFFERENT_STACKING_COORDINATE_NO_OBJECT_LEVEL_WEIGHTS"
)

# Conversion prescribed by the public Brouwer et al. (2021) README.
G_PC3_PER_MSUN_S2 = 4.52e-30
PC_PER_M = 3.086e16
ESD_TO_ACCELERATION = 4.0 * G_PC3_PER_MSUN_S2 * PC_PER_M

PROFILE_COLUMNS = [
    "radius_mpc",
    "esd_t_h70_msun_pc2",
    "esd_x_h70_msun_pc2",
    "error_h70_msun_pc2",
    "bias_1_plus_k",
    "variance_e_s",
    "wk2",
    "w2k2",
]

COVARIANCE_COLUMNS = [
    "mass_bin_i_min_log10_mstar",
    "mass_bin_j_min_log10_mstar",
    "radius_i_mpc",
    "radius_j_mpc",
    "covariance_h70_msun_pc2_squared",
    "correlation",
    "bias_product",
]


@dataclass(frozen=True)
class CovarianceOperatorConfig:
    quadrature_nodes: int = 512
    central_interpolation: Literal["linear"] = "linear"
    alternate_interpolation: Literal["quadratic"] = "quadratic"
    central_tail: Literal["sis"] = "sis"
    tail_extremes: tuple[str, str] = ("zero", "flat")
    normal_95_multiplier: float = 1.959963984540054


@dataclass(frozen=True)
class PublishedProfile:
    mass_bin_min_log10_mstar: float
    frame: pd.DataFrame
    path: Path
    sha256: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_esd_profile(
    path: Path,
    mass_bin_min_log10_mstar: float,
) -> PublishedProfile:
    """Load and validate one 15-bin public KiDS radial ESD profile."""
    path = Path(path)
    frame = pd.read_csv(
        path,
        sep=r"\s+",
        comment="#",
        names=PROFILE_COLUMNS,
        engine="python",
    )
    if len(frame) != 15:
        raise ValueError(f"expected 15 radial bins in {path}, found {len(frame)}")
    values = frame.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError(f"non-finite profile value in {path}")
    radius = frame["radius_mpc"].to_numpy(dtype=float)
    if np.any(radius <= 0.0) or not np.all(np.diff(radius) > 0.0):
        raise ValueError(f"radii must be positive and strictly increasing in {path}")
    if np.any(frame["error_h70_msun_pc2"].to_numpy(dtype=float) <= 0.0):
        raise ValueError(f"profile errors must be positive in {path}")
    if np.any(frame["bias_1_plus_k"].to_numpy(dtype=float) <= 0.0):
        raise ValueError(f"multiplicative biases must be positive in {path}")
    return PublishedProfile(
        mass_bin_min_log10_mstar=float(mass_bin_min_log10_mstar),
        frame=frame,
        path=path,
        sha256=sha256_file(path),
    )


def load_profile_family(
    paths: Sequence[Path],
    mass_bin_minima: Sequence[float],
) -> list[PublishedProfile]:
    if len(paths) != len(mass_bin_minima) or not paths:
        raise ValueError("profile paths and mass-bin minima must have equal non-zero length")
    profiles = [
        load_esd_profile(path, mass_bin)
        for path, mass_bin in zip(paths, mass_bin_minima, strict=True)
    ]
    reference = profiles[0].frame["radius_mpc"].to_numpy(dtype=float)
    for profile in profiles[1:]:
        radius = profile.frame["radius_mpc"].to_numpy(dtype=float)
        if not np.allclose(radius, reference, rtol=2e-4, atol=0.0):
            raise ValueError("published profile radii are not aligned across mass bins")
    return profiles


def load_corrected_covariance(
    path: Path,
    profiles: Sequence[PublishedProfile],
) -> tuple[np.ndarray, pd.DataFrame, dict[str, Any]]:
    """Load, order, bias-correct, and validate the full published covariance."""
    path = Path(path)
    rows = pd.read_csv(
        path,
        sep=r"\s+",
        comment="#",
        names=COVARIANCE_COLUMNS,
        engine="python",
    )
    n_profile = len(profiles)
    n_radius = len(profiles[0].frame)
    n_total = n_profile * n_radius
    if len(rows) != n_total * n_total:
        raise ValueError(
            f"expected {n_total * n_total} covariance cells, found {len(rows)}"
        )

    mass_grid = np.array(
        [profile.mass_bin_min_log10_mstar for profile in profiles], dtype=float
    )
    radius_grid = profiles[0].frame["radius_mpc"].to_numpy(dtype=float)

    def nearest_grid_indices(values: np.ndarray, grid: np.ndarray) -> np.ndarray:
        distance = np.abs(values[:, None] - grid[None, :])
        return np.argmin(distance, axis=1)

    mass_i = nearest_grid_indices(
        rows["mass_bin_i_min_log10_mstar"].to_numpy(dtype=float), mass_grid
    )
    mass_j = nearest_grid_indices(
        rows["mass_bin_j_min_log10_mstar"].to_numpy(dtype=float), mass_grid
    )
    radius_i = nearest_grid_indices(
        rows["radius_i_mpc"].to_numpy(dtype=float), radius_grid
    )
    radius_j = nearest_grid_indices(
        rows["radius_j_mpc"].to_numpy(dtype=float), radius_grid
    )
    if not np.allclose(
        rows["mass_bin_i_min_log10_mstar"].to_numpy(dtype=float),
        mass_grid[mass_i],
        rtol=0.0,
        atol=1e-10,
    ) or not np.allclose(
        rows["mass_bin_j_min_log10_mstar"].to_numpy(dtype=float),
        mass_grid[mass_j],
        rtol=0.0,
        atol=1e-10,
    ):
        raise ValueError("covariance contains an unknown mass bin")
    if not np.allclose(
        rows["radius_i_mpc"].to_numpy(dtype=float),
        radius_grid[radius_i],
        rtol=2e-4,
        atol=0.0,
    ) or not np.allclose(
        rows["radius_j_mpc"].to_numpy(dtype=float),
        radius_grid[radius_j],
        rtol=2e-4,
        atol=0.0,
    ):
        raise ValueError("covariance contains an unknown radius")
    if np.any(rows["bias_product"].to_numpy(dtype=float) <= 0.0):
        raise ValueError("covariance bias product must be positive")

    flat_i = mass_i * n_radius + radius_i
    flat_j = mass_j * n_radius + radius_j
    flat_cells = flat_i * n_total + flat_j
    if len(np.unique(flat_cells)) != n_total * n_total:
        raise ValueError("covariance contains duplicate or missing coordinate cells")
    covariance = np.full((n_total, n_total), np.nan, dtype=float)
    correlation = np.full_like(covariance, np.nan)
    covariance[flat_i, flat_j] = (
        rows["covariance_h70_msun_pc2_squared"].to_numpy(dtype=float)
        / rows["bias_product"].to_numpy(dtype=float)
    )
    correlation[flat_i, flat_j] = rows["correlation"].to_numpy(dtype=float)

    if not np.isfinite(covariance).all():
        raise ValueError("covariance grid is incomplete")
    symmetry_error = float(np.max(np.abs(covariance - covariance.T)))
    if symmetry_error > 1e-10:
        raise ValueError(f"corrected covariance is asymmetric: {symmetry_error}")
    eigenvalues = np.linalg.eigvalsh(covariance)
    if float(eigenvalues[0]) <= 0.0:
        raise ValueError("corrected covariance is not positive definite")

    expected_diagonal = np.concatenate(
        [
            (
                profile.frame["error_h70_msun_pc2"].to_numpy(dtype=float)
                / profile.frame["bias_1_plus_k"].to_numpy(dtype=float)
            )
            ** 2
            for profile in profiles
        ]
    )
    diagonal_relative_error = float(
        np.max(
            np.abs(np.diag(covariance) - expected_diagonal)
            / expected_diagonal
        )
    )
    if diagonal_relative_error > 2e-4:
        raise ValueError(
            "covariance diagonal does not reproduce corrected profile errors: "
            f"{diagonal_relative_error}"
        )
    diagnostics = {
        "dimension": n_total,
        "symmetric_max_abs_error": symmetry_error,
        "minimum_eigenvalue": float(eigenvalues[0]),
        "maximum_eigenvalue": float(eigenvalues[-1]),
        "condition_number": float(eigenvalues[-1] / eigenvalues[0]),
        "maximum_absolute_off_diagonal_correlation": float(
            np.max(np.abs(correlation - np.diag(np.diag(correlation))))
        ),
        "maximum_diagonal_relative_error": diagonal_relative_error,
        "sha256": sha256_file(path),
    }
    return covariance, rows, diagnostics


def build_deprojection_operator(
    radius_mpc: np.ndarray,
    *,
    quadrature_nodes: int = 512,
    interpolation: Literal["linear", "quadratic"] = "linear",
    tail: Literal["sis", "zero", "flat"] = "sis",
) -> np.ndarray:
    """Build A such that A @ ESD approximates the exact spherical integral.

    The matrix excludes the common ``4G`` unit-conversion factor.  The
    interpolation and all three tails remain linear in the measured ESD, so
    the published covariance can be propagated exactly for this discretized
    conditional operator.
    """
    radius = np.asarray(radius_mpc, dtype=float)
    if radius.ndim != 1 or len(radius) < 3:
        raise ValueError("radius_mpc must be a one-dimensional grid of length >= 3")
    if not np.isfinite(radius).all() or np.any(radius <= 0.0):
        raise ValueError("radius grid must be finite and positive")
    if not np.all(np.diff(radius) > 0.0):
        raise ValueError("radius grid must be strictly increasing")
    if quadrature_nodes < 64:
        raise ValueError("quadrature_nodes must be >= 64")
    if interpolation not in {"linear", "quadratic"}:
        raise ValueError(f"unsupported interpolation: {interpolation}")
    if tail not in {"sis", "zero", "flat"}:
        raise ValueError(f"unsupported tail: {tail}")

    nodes, weights = np.polynomial.legendre.leggauss(quadrature_nodes)
    theta = (nodes + 1.0) * (np.pi / 4.0)
    theta_weights = weights * (np.pi / 4.0)
    basis = np.eye(len(radius), dtype=float)
    interpolator = interp1d(
        radius,
        basis,
        kind=interpolation,
        axis=0,
        bounds_error=False,
        fill_value=np.nan,
        assume_sorted=True,
    )
    operator = np.zeros((len(radius), len(radius)), dtype=float)
    for target_index, target_radius in enumerate(radius):
        query_radius = target_radius / np.sin(theta)
        inside = query_radius <= radius[-1]
        evaluated = np.zeros((quadrature_nodes, len(radius)), dtype=float)
        if np.any(inside):
            evaluated[inside] = interpolator(query_radius[inside])
        outside = ~inside
        if np.any(outside):
            if tail == "sis":
                evaluated[outside, -1] = radius[-1] / query_radius[outside]
            elif tail == "flat":
                evaluated[outside, -1] = 1.0
            # zero tail intentionally leaves all coefficients at zero.
        operator[target_index] = theta_weights @ evaluated
    if not np.isfinite(operator).all():
        raise ValueError("deprojection operator contains non-finite values")
    return operator


def _block_operator(single: np.ndarray, n_profiles: int) -> np.ndarray:
    return np.kron(np.eye(n_profiles, dtype=float), single)


def _stack_profile_values(
    profiles: Sequence[PublishedProfile], column: str, *, corrected: bool
) -> np.ndarray:
    arrays = []
    for profile in profiles:
        values = profile.frame[column].to_numpy(dtype=float)
        if corrected:
            values = values / profile.frame["bias_1_plus_k"].to_numpy(dtype=float)
        arrays.append(values)
    return np.concatenate(arrays)


def derive_operator_shadow(
    profiles: Sequence[PublishedProfile],
    corrected_covariance: np.ndarray,
    config: CovarianceOperatorConfig,
) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    """Derive SIS/exact operator shadows and propagate the full covariance."""
    if config.normal_95_multiplier <= 0.0:
        raise ValueError("normal_95_multiplier must be positive")
    n_profiles = len(profiles)
    radius = profiles[0].frame["radius_mpc"].to_numpy(dtype=float)
    n_total = n_profiles * len(radius)
    if corrected_covariance.shape != (n_total, n_total):
        raise ValueError("corrected covariance dimension does not match profiles")

    operators: dict[str, np.ndarray] = {}
    for interpolation, tail, name in [
        (config.central_interpolation, config.central_tail, "central"),
        (config.central_interpolation, config.tail_extremes[0], "tail_zero"),
        (config.central_interpolation, config.tail_extremes[1], "tail_flat"),
        (config.alternate_interpolation, config.central_tail, "quadratic"),
    ]:
        single = build_deprojection_operator(
            radius,
            quadrature_nodes=config.quadrature_nodes,
            interpolation=interpolation,
            tail=tail,
        )
        operators[name] = _block_operator(single, n_profiles)

    esd_t = _stack_profile_values(profiles, "esd_t_h70_msun_pc2", corrected=True)
    esd_x = _stack_profile_values(profiles, "esd_x_h70_msun_pc2", corrected=True)
    errors = _stack_profile_values(profiles, "error_h70_msun_pc2", corrected=True)
    identity = np.eye(n_total, dtype=float)

    g_sis = ESD_TO_ACCELERATION * esd_t
    g_exact = ESD_TO_ACCELERATION * (operators["central"] @ esd_t)
    g_tail_zero = ESD_TO_ACCELERATION * (operators["tail_zero"] @ esd_t)
    g_tail_flat = ESD_TO_ACCELERATION * (operators["tail_flat"] @ esd_t)
    g_quadratic = ESD_TO_ACCELERATION * (operators["quadratic"] @ esd_t)

    covariance_sis = ESD_TO_ACCELERATION**2 * corrected_covariance
    covariance_exact = (
        ESD_TO_ACCELERATION**2
        * operators["central"]
        @ corrected_covariance
        @ operators["central"].T
    )
    delta_operator = operators["central"] - identity
    covariance_difference = (
        ESD_TO_ACCELERATION**2
        * delta_operator
        @ corrected_covariance
        @ delta_operator.T
    )
    sigma_sis = np.sqrt(np.clip(np.diag(covariance_sis), 0.0, None))
    sigma_exact = np.sqrt(np.clip(np.diag(covariance_exact), 0.0, None))
    sigma_difference = np.sqrt(
        np.clip(np.diag(covariance_difference), 0.0, None)
    )
    difference = g_exact - g_sis
    z_difference = np.divide(
        difference,
        sigma_difference,
        out=np.full_like(difference, np.nan),
        where=sigma_difference > 0.0,
    )
    tail_low = np.minimum.reduce([g_exact, g_tail_zero, g_tail_flat])
    tail_high = np.maximum.reduce([g_exact, g_tail_zero, g_tail_flat])
    tail_half_span = 0.5 * (tail_high - tail_low)
    interpolation_shift = np.abs(g_quadratic - g_exact)

    rows: list[dict[str, Any]] = []
    index = 0
    for profile_index, profile in enumerate(profiles):
        frame = profile.frame
        for radial_index in range(len(radius)):
            central_delta = abs(float(difference[index]))
            systematic_scale = max(
                float(tail_half_span[index]), float(interpolation_shift[index])
            )
            if (
                not np.isfinite(z_difference[index])
                or g_sis[index] <= 0.0
                or g_exact[index] <= 0.0
            ):
                status = "NOT_ESTIMABLE_NONPOSITIVE_OR_DEGENERATE"
            elif systematic_scale >= central_delta:
                status = "OPERATOR_DIFFERENCE_UNRESOLVED_SYSTEMATICS"
            elif abs(z_difference[index]) >= config.normal_95_multiplier:
                status = "OPERATOR_DIFFERENCE_RESOLVED_CONDITIONAL_95"
            else:
                status = "OPERATOR_DIFFERENCE_STATISTICALLY_UNRESOLVED_95"
            cross_z_descriptive = float(esd_x[index] / errors[index])
            rows.append(
                {
                    "mass_bin": profile_index + 1,
                    "mass_bin_min_log10_mstar_h70_minus2_msun": (
                        profile.mass_bin_min_log10_mstar
                    ),
                    "radial_bin": radial_index + 1,
                    "radius_mpc": float(frame.iloc[radial_index]["radius_mpc"]),
                    "g_sis_m_s2": float(g_sis[index]),
                    "g_sis_sigma_stat_m_s2": float(sigma_sis[index]),
                    "g_exact_stack_first_m_s2": float(g_exact[index]),
                    "g_exact_sigma_stat_m_s2": float(sigma_exact[index]),
                    "exact_minus_sis_m_s2": float(difference[index]),
                    "exact_minus_sis_sigma_stat_m_s2": float(
                        sigma_difference[index]
                    ),
                    "exact_minus_sis_z_full_covariance": float(z_difference[index]),
                    "exact_over_sis_ratio": float(g_exact[index] / g_sis[index]),
                    "tail_envelope_low_m_s2": float(tail_low[index]),
                    "tail_envelope_high_m_s2": float(tail_high[index]),
                    "tail_half_span_m_s2": float(tail_half_span[index]),
                    "quadratic_minus_linear_abs_m_s2": float(
                        interpolation_shift[index]
                    ),
                    "cross_esd_over_tangential_error_descriptive": (
                        cross_z_descriptive
                    ),
                    "cross_null_authority": (
                        "DESCRIPTIVE_ONLY_NO_PUBLISHED_CROSS_COVARIANCE"
                    ),
                    "operator_status": status,
                    "authority": AUTHORITY,
                    "rar_transfer_authority": RAR_TRANSFER_AUTHORITY,
                }
            )
            index += 1

    matrices = {
        "covariance_esd_corrected": corrected_covariance,
        "covariance_g_sis": covariance_sis,
        "covariance_g_exact": covariance_exact,
        "covariance_exact_minus_sis": covariance_difference,
        "operator_central_block": operators["central"],
        "operator_tail_zero_block": operators["tail_zero"],
        "operator_tail_flat_block": operators["tail_flat"],
        "operator_quadratic_block": operators["quadratic"],
    }
    return pd.DataFrame(rows), matrices


def summarize_operator_shadow(
    result: pd.DataFrame,
    config: CovarianceOperatorConfig,
    covariance_diagnostics: dict[str, Any],
    source_receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    statuses = result["operator_status"].value_counts().to_dict()
    finite_ratio = result.loc[
        np.isfinite(result["exact_over_sis_ratio"]), "exact_over_sis_ratio"
    ].to_numpy(dtype=float)
    cross = result[
        "cross_esd_over_tangential_error_descriptive"
    ].to_numpy(dtype=float)
    return {
        "schema": SCHEMA,
        "campaign_id": CAMPAIGN_ID,
        "created_utc": _utc_now(),
        "authority": AUTHORITY,
        "rar_transfer_authority": RAR_TRANSFER_AUTHORITY,
        "decision": (
            "COVARIANCE_AWARE_RADIAL_OPERATOR_SHADOW_AVAILABLE_"
            "RAR_TRANSFER_ABSTAINS"
        ),
        "published_profiles": 4,
        "radial_bins_per_profile": 15,
        "joint_covariance_dimension": 60,
        "status_counts": {key: int(value) for key, value in statuses.items()},
        "median_exact_over_sis_ratio": float(np.median(finite_ratio)),
        "maximum_absolute_log10_exact_over_sis_dex": float(
            np.max(np.abs(np.log10(finite_ratio)))
        ),
        "descriptive_cross_abs_z_median": float(np.median(np.abs(cross))),
        "descriptive_cross_abs_z_maximum": float(np.max(np.abs(cross))),
        "descriptive_cross_abs_z_gt_2_count": int(np.sum(np.abs(cross) > 2.0)),
        "config": asdict(config),
        "covariance_diagnostics": covariance_diagnostics,
        "source_receipts": source_receipts,
        "observable_face": [
            "four published KiDS-1000 ESD profiles in physical projected radius",
            "published tangential and cross ESD components",
            "published joint 60x60 ESD covariance including cross-bin cells",
        ],
        "shadow_face": [
            "SIS-to-exact stack-first operator difference",
            "full-covariance whitening of that paired operator difference",
            "tail-policy and interpolation sensitivity envelopes",
            "descriptive cross-component null without invented covariance",
        ],
        "not_estimable": [
            "exact object-level deprojection",
            "transfer from radial stacking to the published g_bar-stacked RAR",
            "global cross-component null p-value without cross covariance",
            "joint baryonic-lensing likelihood",
            "intrinsic galaxy-by-galaxy lensing scatter",
            "dark-matter, modified-gravity, or plasma-hyperstate ontology",
        ],
    }
