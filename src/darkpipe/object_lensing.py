"""Object-level weak-lensing kernels for the DarkPipe v0.14 remote pipeline.

The functions implement pair weighting, null-channel accumulation and the
spherical deprojection operator.  They do not select a cosmological model or
turn a software calculation into evidence for a material ontology.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
from typing import Any

import numpy as np
from scipy.integrate import quad


C_KM_S = 299_792.458
G_MPC_KM2_S2_MSUN = 4.30091e-9
G_SI = 6.67430e-11
MSUN_KG = 1.98847e30
MPC_M = 3.085677581491367e22
KPC_M = MPC_M / 1000.0
PAIR_KERNEL_AUTHORITY = "COMPUTE_KERNEL_ONLY_NO_MODEL_ADJUDICATION"


@dataclass(frozen=True)
class FlatLambdaCDM:
    h0_km_s_mpc: float = 70.0
    omega_m: float = 0.3

    def __post_init__(self) -> None:
        if self.h0_km_s_mpc <= 0:
            raise ValueError("H0 must be positive")
        if not 0 < self.omega_m < 1:
            raise ValueError("omega_m must lie strictly between zero and one")

    @property
    def omega_lambda(self) -> float:
        return 1.0 - self.omega_m

    @lru_cache(maxsize=8192)
    def comoving_distance_mpc(self, redshift: float) -> float:
        if redshift < 0:
            raise ValueError("redshift cannot be negative")
        integral, _ = quad(
            lambda z: 1.0
            / math.sqrt(self.omega_m * (1.0 + z) ** 3 + self.omega_lambda),
            0.0,
            float(redshift),
            epsabs=1e-9,
            epsrel=1e-9,
            limit=200,
        )
        return C_KM_S / self.h0_km_s_mpc * integral

    def angular_diameter_distance_mpc(self, redshift: float) -> float:
        return self.comoving_distance_mpc(float(redshift)) / (1.0 + float(redshift))

    def angular_diameter_between_mpc(self, z_near: float, z_far: float) -> float:
        if z_far <= z_near:
            return 0.0
        return (
            self.comoving_distance_mpc(float(z_far))
            - self.comoving_distance_mpc(float(z_near))
        ) / (1.0 + float(z_far))


def sigma_critical_msun_mpc2(
    z_lens: np.ndarray,
    z_source: np.ndarray,
    *,
    cosmology: FlatLambdaCDM,
) -> np.ndarray:
    """Critical surface density for point redshifts in Msun/Mpc^2."""

    zl, zs = np.broadcast_arrays(
        np.asarray(z_lens, dtype=float), np.asarray(z_source, dtype=float)
    )
    result = np.full(zl.shape, np.inf, dtype=float)
    for index in np.ndindex(zl.shape):
        if not np.isfinite(zl[index]) or not np.isfinite(zs[index]):
            continue
        if zs[index] <= zl[index]:
            continue
        dl = cosmology.angular_diameter_distance_mpc(float(zl[index]))
        ds = cosmology.angular_diameter_distance_mpc(float(zs[index]))
        dls = cosmology.angular_diameter_between_mpc(
            float(zl[index]), float(zs[index])
        )
        if dl <= 0 or ds <= 0 or dls <= 0:
            continue
        result[index] = (
            C_KM_S**2 / (4.0 * math.pi * G_MPC_KM2_S2_MSUN)
            * ds / (dl * dls)
        )
    return result


def angular_separation_rad(
    ra_lens_deg: np.ndarray,
    dec_lens_deg: np.ndarray,
    ra_source_deg: np.ndarray,
    dec_source_deg: np.ndarray,
) -> np.ndarray:
    ra_l, dec_l, ra_s, dec_s = np.broadcast_arrays(
        np.deg2rad(ra_lens_deg),
        np.deg2rad(dec_lens_deg),
        np.deg2rad(ra_source_deg),
        np.deg2rad(dec_source_deg),
    )
    dra = ra_s - ra_l
    a = (
        np.sin((dec_s - dec_l) / 2.0) ** 2
        + np.cos(dec_l) * np.cos(dec_s) * np.sin(dra / 2.0) ** 2
    )
    return 2.0 * np.arcsin(np.minimum(1.0, np.sqrt(a)))


def tangential_and_cross_ellipticity(
    ra_lens_deg: np.ndarray,
    dec_lens_deg: np.ndarray,
    ra_source_deg: np.ndarray,
    dec_source_deg: np.ndarray,
    e1: np.ndarray,
    e2: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return flat-sky tangential and 45-degree cross ellipticity channels."""

    ra_l, dec_l, ra_s, dec_s, q1, q2 = np.broadcast_arrays(
        np.deg2rad(ra_lens_deg),
        np.deg2rad(dec_lens_deg),
        np.deg2rad(ra_source_deg),
        np.deg2rad(dec_source_deg),
        np.asarray(e1, dtype=float),
        np.asarray(e2, dtype=float),
    )
    x = (ra_s - ra_l) * np.cos(dec_l)
    y = dec_s - dec_l
    phi = np.arctan2(y, x)
    cos2 = np.cos(2.0 * phi)
    sin2 = np.sin(2.0 * phi)
    tangential = -(q1 * cos2 + q2 * sin2)
    cross = q1 * sin2 - q2 * cos2
    return tangential, cross


def accumulate_esd(
    lens_index: np.ndarray,
    projected_radius_mpc: np.ndarray,
    tangential_ellipticity: np.ndarray,
    cross_ellipticity: np.ndarray,
    source_weight: np.ndarray,
    sigma_critical: np.ndarray,
    multiplicative_bias: np.ndarray,
    *,
    lens_count: int,
    radial_edges_mpc: np.ndarray,
) -> dict[str, np.ndarray]:
    """Accumulate individual-lens ESD and cross-null profiles.

    The denominator includes the pair-weighted multiplicative response:
    sum(w Sigma_crit^-2 (1+m)).  Invalid or foreground pairs are excluded.
    """

    arrays = np.broadcast_arrays(
        np.asarray(lens_index, dtype=int),
        np.asarray(projected_radius_mpc, dtype=float),
        np.asarray(tangential_ellipticity, dtype=float),
        np.asarray(cross_ellipticity, dtype=float),
        np.asarray(source_weight, dtype=float),
        np.asarray(sigma_critical, dtype=float),
        np.asarray(multiplicative_bias, dtype=float),
    )
    li, radius, et, ex, ws, sc, mb = (item.ravel() for item in arrays)
    edges = np.asarray(radial_edges_mpc, dtype=float)
    if lens_count <= 0:
        raise ValueError("lens_count must be positive")
    if edges.ndim != 1 or len(edges) < 2 or np.any(np.diff(edges) <= 0):
        raise ValueError("radial_edges_mpc must be strictly increasing")

    radial_bin = np.searchsorted(edges, radius, side="right") - 1
    valid = (
        (li >= 0)
        & (li < lens_count)
        & (radial_bin >= 0)
        & (radial_bin < len(edges) - 1)
        & np.isfinite(et)
        & np.isfinite(ex)
        & np.isfinite(ws)
        & (ws > 0)
        & np.isfinite(sc)
        & (sc > 0)
        & np.isfinite(mb)
        & (1.0 + mb > 0)
    )
    li = li[valid]
    rb = radial_bin[valid]
    et, ex, ws, sc, mb = (
        et[valid],
        ex[valid],
        ws[valid],
        sc[valid],
        mb[valid],
    )
    shape = (lens_count, len(edges) - 1)
    flat_size = shape[0] * shape[1]
    cell = li * shape[1] + rb

    denominator = np.zeros(flat_size, dtype=float)
    numerator_t = np.zeros(flat_size, dtype=float)
    numerator_x = np.zeros(flat_size, dtype=float)
    pair_count = np.zeros(flat_size, dtype=np.int64)
    pair_weight = ws / sc**2
    np.add.at(denominator, cell, pair_weight * (1.0 + mb))
    np.add.at(numerator_t, cell, pair_weight * sc * et)
    np.add.at(numerator_x, cell, pair_weight * sc * ex)
    np.add.at(pair_count, cell, 1)

    with np.errstate(divide="ignore", invalid="ignore"):
        esd = np.divide(
            numerator_t,
            denominator,
            out=np.full(flat_size, np.nan),
            where=denominator > 0,
        )
        cross_esd = np.divide(
            numerator_x,
            denominator,
            out=np.full(flat_size, np.nan),
            where=denominator > 0,
        )
    return {
        "esd_msun_mpc2": esd.reshape(shape),
        "cross_esd_msun_mpc2": cross_esd.reshape(shape),
        "pair_weight_sum": denominator.reshape(shape),
        "pair_count": pair_count.reshape(shape),
        "authority": np.asarray(PAIR_KERNEL_AUTHORITY),
    }


def fixed_gbar_radius_kpc(
    baryonic_mass_msun: np.ndarray,
    gbar_m_s2: np.ndarray,
) -> np.ndarray:
    mass, acceleration = np.broadcast_arrays(
        np.asarray(baryonic_mass_msun, dtype=float),
        np.asarray(gbar_m_s2, dtype=float),
    )
    if np.any(mass <= 0) or np.any(acceleration <= 0):
        raise ValueError("mass and gbar must be positive")
    return np.sqrt(G_SI * mass * MSUN_KG / acceleration) / KPC_M


def _log_profile(
    radius: np.ndarray,
    delta_sigma: np.ndarray,
    query: np.ndarray,
    *,
    inner_slope: float,
    outer_slope: float,
) -> np.ndarray:
    if np.any(radius <= 0) or np.any(delta_sigma <= 0):
        raise ValueError("log-profile deprojection requires positive inputs")
    if np.any(np.diff(radius) <= 0):
        raise ValueError("radius grid must be strictly increasing")
    lr, ld, lq = np.log(radius), np.log(delta_sigma), np.log(query)
    values = np.interp(lq, lr, ld)
    low = lq < lr[0]
    high = lq > lr[-1]
    values[low] = ld[0] + inner_slope * (lq[low] - lr[0])
    values[high] = ld[-1] + outer_slope * (lq[high] - lr[-1])
    return np.exp(values)


def deproject_spherical_esd(
    radius_mpc: np.ndarray,
    delta_sigma_msun_mpc2: np.ndarray,
    evaluation_radius_mpc: np.ndarray,
    *,
    inner_log_slope: float,
    outer_log_slope: float,
    quadrature_points: int = 4096,
) -> np.ndarray:
    """Apply g_obs(R)=4G integral DeltaSigma(R/sin(theta)) dtheta.

    Extrapolation slopes are mandatory preregistered inputs; there are no hidden
    defaults.  Returned acceleration is in m/s^2.
    """

    radius = np.asarray(radius_mpc, dtype=float)
    profile = np.asarray(delta_sigma_msun_mpc2, dtype=float)
    evaluation = np.asarray(evaluation_radius_mpc, dtype=float)
    if radius.shape != profile.shape or radius.ndim != 1:
        raise ValueError("radius and profile must be equal one-dimensional arrays")
    if np.any(evaluation <= 0):
        raise ValueError("evaluation radii must be positive")
    if quadrature_points < 256:
        raise ValueError("quadrature_points must be at least 256")

    theta = np.linspace(1e-8, math.pi / 2.0, quadrature_points)
    conversion = 1e6 / MPC_M
    output = np.empty_like(evaluation)
    for index, target in np.ndenumerate(evaluation):
        query = target / np.sin(theta)
        values = _log_profile(
            radius,
            profile,
            query,
            inner_slope=inner_log_slope,
            outer_slope=outer_log_slope,
        )
        integral = np.trapezoid(values, theta)
        output[index] = 4.0 * G_MPC_KM2_S2_MSUN * integral * conversion
    return output


def object_level_rar(
    radial_grid_mpc: np.ndarray,
    individual_esd_msun_mpc2: np.ndarray,
    baryonic_mass_msun: np.ndarray,
    gbar_grid_m_s2: np.ndarray,
    *,
    inner_log_slope: float,
    outer_log_slope: float,
    lens_weight: np.ndarray | None = None,
) -> dict[str, Any]:
    """Deproject each lens before stacking at fixed baryonic acceleration."""

    profiles = np.asarray(individual_esd_msun_mpc2, dtype=float)
    masses = np.asarray(baryonic_mass_msun, dtype=float)
    gbar = np.asarray(gbar_grid_m_s2, dtype=float)
    if profiles.ndim != 2 or profiles.shape[1] != len(radial_grid_mpc):
        raise ValueError("profiles must have shape (lens, radial_bin)")
    if profiles.shape[0] != len(masses):
        raise ValueError("one baryonic mass is required per lens")
    weights = (
        np.ones(len(masses), dtype=float)
        if lens_weight is None
        else np.asarray(lens_weight, dtype=float)
    )
    if weights.shape != masses.shape or np.any(weights < 0):
        raise ValueError("lens weights must match masses and be non-negative")

    lens_gobs = np.full((len(masses), len(gbar)), np.nan)
    for lens in range(len(masses)):
        valid = np.isfinite(profiles[lens]) & (profiles[lens] > 0)
        if np.count_nonzero(valid) < 3 or weights[lens] == 0:
            continue
        target_kpc = fixed_gbar_radius_kpc(masses[lens], gbar)
        lens_gobs[lens] = deproject_spherical_esd(
            np.asarray(radial_grid_mpc)[valid],
            profiles[lens, valid],
            target_kpc / 1000.0,
            inner_log_slope=inner_log_slope,
            outer_log_slope=outer_log_slope,
        )

    stacked = np.full(len(gbar), np.nan)
    effective_lenses = np.zeros(len(gbar), dtype=int)
    for column in range(len(gbar)):
        valid = np.isfinite(lens_gobs[:, column]) & (weights > 0)
        effective_lenses[column] = int(np.count_nonzero(valid))
        if np.any(valid):
            stacked[column] = np.average(lens_gobs[valid, column], weights=weights[valid])
    return {
        "gbar_m_s2": gbar,
        "gobs_m_s2": stacked,
        "effective_lenses": effective_lenses,
        "individual_gobs_m_s2": lens_gobs,
        "authority": PAIR_KERNEL_AUTHORITY,
        "operation_order": "DEPROJECT_EACH_LENS_BEFORE_FIXED_GBAR_STACK",
    }


__all__ = [
    "FlatLambdaCDM",
    "PAIR_KERNEL_AUTHORITY",
    "accumulate_esd",
    "angular_separation_rad",
    "deproject_spherical_esd",
    "fixed_gbar_radius_kpc",
    "object_level_rar",
    "sigma_critical_msun_mpc2",
    "tangential_and_cross_ellipticity",
]
