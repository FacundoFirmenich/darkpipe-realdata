"""KiDS-1000 lens/source calibration primitives for DarkPipe v0.16.

The effective critical surface density follows Eq. 10 of Mistele et al.
(2024): it integrates the lens photo-z uncertainty and the calibrated SOM
source n(z).  A source best-fit redshift selects one of the five tomographic
distributions; it is not substituted for that distribution.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path

import numpy as np

from .object_lensing import C_KM_S, G_MPC_KM2_S2_MSUN, FlatLambdaCDM


KIDS_TOMOGRAPHIC_EDGES = np.asarray((0.1, 0.3, 0.5, 0.7, 0.9, 1.2), dtype=float)
EFFECTIVE_SIGMA_AUTHORITY = "MISTELE2024_EQ10_SOM_NZ_NUMERICAL_LOOKUP"


@dataclass(frozen=True)
class TomographicNz:
    redshift: np.ndarray
    density: np.ndarray

    def __post_init__(self) -> None:
        z = np.asarray(self.redshift, dtype=float)
        n = np.asarray(self.density, dtype=float)
        if z.ndim != 1 or n.shape != z.shape or len(z) < 3:
            raise ValueError("redshift and density must be equal 1D arrays")
        if np.any(~np.isfinite(z)) or np.any(~np.isfinite(n)):
            raise ValueError("n(z) contains non-finite values")
        if np.any(np.diff(z) <= 0) or np.any(n < 0):
            raise ValueError("n(z) requires increasing redshift and non-negative density")
        if np.trapezoid(n, z) <= 0:
            raise ValueError("n(z) has zero integral")


def load_som_nz(directory: Path) -> tuple[TomographicNz, ...]:
    """Load and validate the five official KiDS-1000 SOM n(z) tables."""

    result: list[TomographicNz] = []
    for index in range(1, 6):
        matches = sorted(Path(directory).glob(f"*TOMO{index}_Nz.asc"))
        if len(matches) != 1:
            raise ValueError(f"expected one TOMO{index} n(z) file, found {len(matches)}")
        table = np.loadtxt(matches[0], comments="#")
        result.append(TomographicNz(table[:, 0], table[:, 1]))
    reference = result[0].redshift
    if any(not np.array_equal(reference, item.redshift) for item in result[1:]):
        raise ValueError("all tomographic n(z) tables must share one redshift grid")
    return tuple(result)


def source_tomographic_bin(z_best: np.ndarray) -> np.ndarray:
    """Return zero-based KiDS tomographic bin, or -1 outside (0.1, 1.2]."""

    z = np.asarray(z_best, dtype=float)
    bins = np.searchsorted(KIDS_TOMOGRAPHIC_EDGES, z, side="left") - 1
    valid = np.isfinite(z) & (z > KIDS_TOMOGRAPHIC_EDGES[0]) & (z <= KIDS_TOMOGRAPHIC_EDGES[-1])
    return np.where(valid, bins, -1).astype(np.int8)


def _distance_grids(cosmology: FlatLambdaCDM, redshift: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized comoving/angular distances on a dense deterministic grid."""

    z = np.asarray(redshift, dtype=float)
    step = 0.0005
    dense = np.arange(0.0, float(np.max(z)) + step, step)
    integrand = 1.0 / np.sqrt(
        cosmology.omega_m * (1.0 + dense) ** 3 + cosmology.omega_lambda
    )
    increments = 0.5 * (integrand[1:] + integrand[:-1]) * np.diff(dense)
    cumulative = np.concatenate((np.asarray([0.0]), np.cumsum(increments)))
    chi = C_KM_S / cosmology.h0_km_s_mpc * np.interp(z, dense, cumulative)
    angular = chi / (1.0 + z)
    return chi, angular


def effective_sigma_critical_lookup(
    lens_redshift_grid: np.ndarray,
    source_nz: tuple[TomographicNz, ...],
    *,
    cosmology: FlatLambdaCDM,
    lens_integration_step: float = 0.001,
    lens_sigma_scale: float = 0.02,
    lens_sigma_window: float = 6.0,
) -> dict[str, np.ndarray | str]:
    """Precompute effective Sigma_crit for lens z and five source bins.

    For each integration value z_l, each source n(z) is renormalized on
    [z_l, infinity), exactly as specified in Mistele et al. (2024).  The outer
    lens-photo-z Gaussian is normalized on the numerical non-negative grid.
    """

    lens_grid = np.asarray(lens_redshift_grid, dtype=float)
    if lens_grid.ndim != 1 or np.any(~np.isfinite(lens_grid)) or np.any(lens_grid < 0):
        raise ValueError("lens_redshift_grid must be finite, non-negative and one-dimensional")
    if np.any(np.diff(lens_grid) <= 0):
        raise ValueError("lens_redshift_grid must be strictly increasing")
    if len(source_nz) != 5:
        raise ValueError("five tomographic n(z) distributions are required")
    if lens_integration_step <= 0 or lens_sigma_scale <= 0 or lens_sigma_window < 4:
        raise ValueError("invalid numerical integration controls")

    source_z = np.asarray(source_nz[0].redshift, dtype=float)
    if any(not np.array_equal(source_z, item.redshift) for item in source_nz):
        raise ValueError("source n(z) grids differ")
    max_sigma = lens_sigma_scale * (1.0 + float(np.max(lens_grid)))
    outer_max = max(float(np.max(lens_grid)) + lens_sigma_window * max_sigma, 0.8)
    zl = np.arange(0.0, outer_max + lens_integration_step / 2.0, lens_integration_step)
    chi_l, d_l = _distance_grids(cosmology, zl)
    chi_s, d_s = _distance_grids(cosmology, source_z)

    inner = np.zeros((5, len(zl)), dtype=float)
    for tomo_index, distribution in enumerate(source_nz):
        density = np.asarray(distribution.density, dtype=float)
        for i, lens_z in enumerate(zl):
            behind = (source_z > lens_z) & (d_s > 0.0)
            if np.count_nonzero(behind) < 2:
                continue
            z_tail = source_z[behind]
            n_tail = density[behind]
            norm = np.trapezoid(n_tail, z_tail)
            if norm <= 0:
                continue
            dls = (chi_s[behind] - chi_l[i]) / (1.0 + source_z[behind])
            efficiency = np.maximum(dls, 0.0) / d_s[behind]
            inner[tomo_index, i] = np.trapezoid(n_tail * efficiency, z_tail) / norm

    prefactor = 4.0 * math.pi * G_MPC_KM2_S2_MSUN / C_KM_S**2
    inverse = np.zeros((len(lens_grid), 5), dtype=float)
    for row, center in enumerate(lens_grid):
        sigma = lens_sigma_scale * (1.0 + center)
        pdf = np.exp(-0.5 * ((zl - center) / sigma) ** 2)
        pdf /= np.trapezoid(pdf, zl)
        inverse[row] = prefactor * np.trapezoid(pdf[None, :] * d_l[None, :] * inner, zl, axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        sigma_critical = np.divide(1.0, inverse, out=np.full_like(inverse, np.inf), where=inverse > 0)
    return {
        "lens_redshift": lens_grid,
        "inverse_sigma_critical_mpc2_msun": inverse,
        "sigma_critical_msun_mpc2": sigma_critical,
        "authority": EFFECTIVE_SIGMA_AUTHORITY,
    }


def interpolate_effective_sigma_critical(
    lens_redshift: np.ndarray,
    source_best_redshift: np.ndarray,
    lookup: dict[str, np.ndarray | str],
) -> np.ndarray:
    """Interpolate the lookup for lens/source pairs after tomographic selection."""

    zl, zs = np.broadcast_arrays(
        np.asarray(lens_redshift, dtype=float), np.asarray(source_best_redshift, dtype=float)
    )
    lens_grid = np.asarray(lookup["lens_redshift"], dtype=float)
    values = np.asarray(lookup["sigma_critical_msun_mpc2"], dtype=float)
    if values.shape != (len(lens_grid), 5):
        raise ValueError("lookup sigma grid must have shape (lens_redshift, 5)")
    tomo = source_tomographic_bin(zs)
    result = np.full(zl.shape, np.inf, dtype=float)
    valid = np.isfinite(zl) & (tomo >= 0) & (zs > zl + 0.2)
    for index in range(5):
        chosen = valid & (tomo == index)
        if np.any(chosen):
            result[chosen] = np.interp(zl[chosen], lens_grid, values[:, index], left=np.inf, right=np.inf)
    return result


__all__ = [
    "EFFECTIVE_SIGMA_AUTHORITY",
    "KIDS_TOMOGRAPHIC_EDGES",
    "TomographicNz",
    "effective_sigma_critical_lookup",
    "interpolate_effective_sigma_critical",
    "load_som_nz",
    "source_tomographic_bin",
]
