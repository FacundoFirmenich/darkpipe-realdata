"""Reconstruct the KiDS-bright lens sample used by Mistele et al. (2024).

The implementation is deliberately evidence-bounded.  It consumes the public
KiDS-bright and LePhare FITS tables by HTTP range, verifies row identity, and
derives only quantities whose transformations are explicitly recorded here.
It does not claim to reproduce the weak-lensing signal; that requires the
source catalogue, pair estimator, random catalogue and covariance stages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import numpy as np
from scipy.integrate import cumulative_trapezoid
from scipy.spatial import cKDTree

from .fits_range_table import iter_remote_numeric_columns


C_KM_S = 299_792.458
BRIGHT_URL = "https://kids.strw.leidenuniv.nl/DR4/data_files/KiDS_DR4_brightsample.fits"
BRIGHT_BYTES = 89_259_840
LEPHARE_URL = "https://kids.strw.leidenuniv.nl/DR4/data_files/KiDS_DR4_brightsample_LePhare.fits"
LEPHARE_BYTES = 257_817_600
LENS_SAMPLE_AUTHORITY = "OBJECT_LEVEL_LENS_SAMPLE_RECONSTRUCTION_ONLY_NO_LENSING_RESULT"


@dataclass(frozen=True)
class FlatCosmology:
    h0: float
    omega_m: float
    z_max: float = 1.5
    grid_size: int = 200_001

    def _grid(self) -> tuple[np.ndarray, np.ndarray]:
        z = np.linspace(0.0, self.z_max, self.grid_size)
        inv_e = 1.0 / np.sqrt(self.omega_m * (1.0 + z) ** 3 + 1.0 - self.omega_m)
        chi = C_KM_S / self.h0 * np.concatenate(([0.0], cumulative_trapezoid(inv_e, z)))
        return z, chi

    def comoving_distance_mpc(self, redshift: np.ndarray | Sequence[float]) -> np.ndarray:
        values = np.asarray(redshift, dtype=float)
        if np.any((values < 0.0) | (values > self.z_max)):
            raise ValueError("redshift outside cosmology interpolation domain")
        grid_z, grid_chi = self._grid()
        return np.interp(values, grid_z, grid_chi)

    def distance_modulus(self, redshift: np.ndarray | Sequence[float]) -> np.ndarray:
        values = np.asarray(redshift, dtype=float)
        luminosity_distance = (1.0 + values) * self.comoving_distance_mpc(values)
        if np.any(luminosity_distance <= 0.0):
            raise ValueError("distance modulus requires positive redshift")
        return 5.0 * np.log10(luminosity_distance) + 25.0


def _collect_remote(
    url: str,
    total_bytes: int,
    names: Sequence[str],
    *,
    target_chunk_bytes: int = 32 * 1024 * 1024,
) -> dict[str, np.ndarray]:
    pieces: dict[str, list[np.ndarray]] = {name: [] for name in names}
    expected_first = 0
    for first, columns in iter_remote_numeric_columns(
        url,
        total_bytes=total_bytes,
        names=names,
        target_chunk_bytes=target_chunk_bytes,
    ):
        if first != expected_first:
            raise RuntimeError(f"non-contiguous FITS rows: {first} != {expected_first}")
        row_count = len(next(iter(columns.values())))
        if any(len(column) != row_count for column in columns.values()):
            raise RuntimeError("column length mismatch inside FITS chunk")
        for name in names:
            pieces[name].append(columns[name])
        expected_first += row_count
    return {name: np.concatenate(chunks) for name, chunks in pieces.items()}


def load_aligned_catalogues(*, target_chunk_bytes: int = 32 * 1024 * 1024) -> dict[str, np.ndarray]:
    """Load the compact lens-side columns and prove row-level alignment."""

    bright_names = (
        "ID",
        "RAJ2000",
        "DECJ2000",
        "MAG_AUTO_CALIB",
        "zphot_ANNz2",
        "MASK",
        "masked",
    )
    lephare_names = (
        "ID",
        "RAJ2000",
        "DECJ2000",
        "K_COR_u",
        "K_COR_r",
        "MAG_ABS_u",
        "MAG_ABS_r",
        "REDSHIFT",
        "MASS_BEST",
    )
    bright = _collect_remote(BRIGHT_URL, BRIGHT_BYTES, bright_names, target_chunk_bytes=target_chunk_bytes)
    lephare = _collect_remote(
        LEPHARE_URL, LEPHARE_BYTES, lephare_names, target_chunk_bytes=target_chunk_bytes
    )
    if len(bright["ID"]) != len(lephare["ID"]):
        raise RuntimeError("KiDS-bright and LePhare row counts differ")
    if not np.array_equal(bright["ID"], lephare["ID"]):
        mismatch = int(np.flatnonzero(bright["ID"] != lephare["ID"])[0])
        raise RuntimeError(f"catalogue ID alignment fails at row {mismatch}")
    if not np.allclose(bright["RAJ2000"], lephare["RAJ2000"], rtol=0.0, atol=5e-7, equal_nan=True):
        raise RuntimeError("catalogue RA alignment fails")
    if not np.allclose(bright["DECJ2000"], lephare["DECJ2000"], rtol=0.0, atol=5e-7, equal_nan=True):
        raise RuntimeError("catalogue Dec alignment fails")
    bright_z = np.asarray(bright["zphot_ANNz2"], dtype=float)
    lephare_z = np.asarray(lephare["REDSHIFT"], dtype=float)
    science_window = np.isfinite(bright_z) & np.isfinite(lephare_z) & (bright_z > 0.1) & (bright_z < 0.5)
    redshift_delta = np.abs(bright_z[science_window] - lephare_z[science_window])
    if redshift_delta.size == 0 or float(np.max(redshift_delta)) > 1e-5:
        raise RuntimeError(
            "catalogue redshift alignment fails in science window: "
            f"max_abs={float(np.max(redshift_delta)) if redshift_delta.size else None}"
        )
    output = dict(bright)
    output.update({name: values for name, values in lephare.items() if name not in {"ID", "RAJ2000", "DECJ2000", "REDSHIFT"}})
    output["_redshift_alignment_max_abs"] = np.array([float(np.max(redshift_delta))])
    return output


def reconstruct_gaap_magnitudes(
    redshift: np.ndarray,
    mag_abs_u: np.ndarray,
    mag_abs_r: np.ndarray,
    k_cor_u: np.ndarray,
    k_cor_r: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Reconstruct apparent GAAP magnitudes as ``m=M+DM+K``.

    LePhare catalogue documentation fixes H0=70, Omega_m=0.3.  The result is
    treated as a derived reconstruction, not as a native released column.
    """

    values = np.asarray(redshift, dtype=float)
    valid = np.isfinite(values) & (values > 0.0) & (values <= 1.5)
    dm = np.full(values.shape, np.nan, dtype=float)
    dm[valid] = FlatCosmology(h0=70.0, omega_m=0.3).distance_modulus(values[valid])
    return mag_abs_u.astype(float) + dm + k_cor_u, mag_abs_r.astype(float) + dm + k_cor_r


def derive_masses(catalogue: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Apply the published KiDS/Mistele stellar- and gas-mass transformations."""

    z = np.asarray(catalogue["zphot_ANNz2"], dtype=float)
    gaap_u, gaap_r = reconstruct_gaap_magnitudes(
        z,
        np.asarray(catalogue["MAG_ABS_u"]),
        np.asarray(catalogue["MAG_ABS_r"]),
        np.asarray(catalogue["K_COR_u"]),
        np.asarray(catalogue["K_COR_r"]),
    )
    colour_ur = gaap_u - gaap_r
    is_etg = colour_ur > 2.5
    log_m_kids_h70_1 = (
        np.asarray(catalogue["MASS_BEST"], dtype=float)
        + (gaap_r - np.asarray(catalogue["MAG_AUTO_CALIB"], dtype=float)) / 2.5
        + 0.056
    )
    h70 = 73.0 / 70.0
    log_m_kids_h73 = log_m_kids_h70_1 - 2.0 * np.log10(h70)
    log_m_star = log_m_kids_h73 + np.where(is_etg, np.log10(1.4), 0.0)
    m_star = np.power(10.0, log_m_star)
    hot_ratio = np.power(10.0, -5.414) * np.power(m_star, 0.47)
    hydrogen_fraction = 0.75 - 38.2 * np.power(m_star / 1.5e24, 0.22)
    cold_ratio = (11550.0 * np.power(m_star, -0.46) + 0.07) / hydrogen_fraction
    gas_ratio = np.where(is_etg, hot_ratio, cold_ratio)
    log_m_baryon = np.log10(m_star * (1.0 + gas_ratio))
    return {
        "mag_gaap_u_reconstructed": gaap_u,
        "mag_gaap_r_reconstructed": gaap_r,
        "colour_ur_reconstructed": colour_ur,
        "is_etg": is_etg,
        "log_m_kids_h70_1": log_m_kids_h70_1,
        "log_m_kids_h73": log_m_kids_h73,
        "log_m_star_mistele": log_m_star,
        "gas_to_stellar_ratio": gas_ratio,
        "log_m_baryon_mistele": log_m_baryon,
    }


def comoving_xyz_mpc_h70(ra_deg: np.ndarray, dec_deg: np.ndarray, redshift: np.ndarray) -> np.ndarray:
    """Cartesian comoving positions in Mpc/h70 for the isolation search."""

    values = np.asarray(redshift, dtype=float)
    valid = np.isfinite(values) & (values >= 0.0) & (values <= 1.5)
    chi = np.full(values.shape, np.nan, dtype=float)
    chi[valid] = FlatCosmology(h0=70.0, omega_m=0.2793).comoving_distance_mpc(values[valid])
    ra = np.deg2rad(ra_deg)
    dec = np.deg2rad(dec_deg)
    cos_dec = np.cos(dec)
    return np.column_stack((chi * cos_dec * np.cos(ra), chi * cos_dec * np.sin(ra), chi * np.sin(dec)))


def isolation_mask(
    xyz_comoving: np.ndarray,
    redshift: np.ndarray,
    log_mass_for_isolation: np.ndarray,
    candidate_mask: np.ndarray,
    *,
    proper_radius_mpc_h70: float = 4.0,
    batch_size: int = 10_000,
) -> np.ndarray:
    """Require no >=10%-mass neighbour inside the proper spherical radius.

    The catalogue coordinates are represented comovingly; the proper radius is
    therefore queried as ``R_proper*(1+z_lens)``.  Candidate self-matches are
    removed explicitly.
    """

    xyz = np.asarray(xyz_comoving, dtype=float)
    z = np.asarray(redshift, dtype=float)
    mass = np.asarray(log_mass_for_isolation, dtype=float)
    candidates = np.flatnonzero(candidate_mask)
    finite_pool = np.isfinite(xyz).all(axis=1) & np.isfinite(mass) & np.isfinite(z) & (z > 0.0)
    pool_indices = np.flatnonzero(finite_pool)
    tree = cKDTree(xyz[pool_indices])
    result = np.zeros(len(z), dtype=bool)
    for start in range(0, len(candidates), batch_size):
        batch = candidates[start : start + batch_size]
        radii = proper_radius_mpc_h70 * (1.0 + z[batch])
        neighbor_lists = tree.query_ball_point(xyz[batch], radii, workers=-1)
        for lens_index, local_neighbors in zip(batch, neighbor_lists, strict=True):
            neighbors = pool_indices[np.asarray(local_neighbors, dtype=np.int64)]
            neighbors = neighbors[neighbors != lens_index]
            result[lens_index] = not np.any(mass[neighbors] >= mass[lens_index] - 1.0)
    return result


def nearest_qualifying_neighbor_proper_distance(
    xyz_comoving: np.ndarray,
    redshift: np.ndarray,
    log_mass_for_isolation: np.ndarray,
    candidate_mask: np.ndarray,
    *,
    max_proper_radius_mpc_h70: float = 8.0,
    batch_size: int = 10_000,
) -> np.ndarray:
    """Return the nearest >=10%-mass neighbour distance for each candidate.

    Distances beyond ``max_proper_radius_mpc_h70`` remain infinite.  This is a
    diagnostic surface for adjudicating isolation-geometry choices; it does
    not tune the preregistered 4 Mpc/h70 criterion to a target count.
    """

    xyz = np.asarray(xyz_comoving, dtype=float)
    z = np.asarray(redshift, dtype=float)
    mass = np.asarray(log_mass_for_isolation, dtype=float)
    candidates = np.flatnonzero(candidate_mask)
    finite_pool = np.isfinite(xyz).all(axis=1) & np.isfinite(mass) & np.isfinite(z) & (z > 0.0)
    pool_indices = np.flatnonzero(finite_pool)
    tree = cKDTree(xyz[pool_indices])
    nearest = np.full(len(z), np.inf, dtype=float)
    for start in range(0, len(candidates), batch_size):
        batch = candidates[start : start + batch_size]
        radii = max_proper_radius_mpc_h70 * (1.0 + z[batch])
        neighbor_lists = tree.query_ball_point(xyz[batch], radii, workers=-1)
        for lens_index, local_neighbors in zip(batch, neighbor_lists, strict=True):
            neighbors = pool_indices[np.asarray(local_neighbors, dtype=np.int64)]
            neighbors = neighbors[
                (neighbors != lens_index) & (mass[neighbors] >= mass[lens_index] - 1.0)
            ]
            if neighbors.size:
                comoving = np.linalg.norm(xyz[neighbors] - xyz[lens_index], axis=1)
                nearest[lens_index] = float(np.min(comoving) / (1.0 + z[lens_index]))
    return nearest


def reconstruct_lens_sample(catalogue: Mapping[str, np.ndarray]) -> dict[str, object]:
    masses = derive_masses(catalogue)
    z = np.asarray(catalogue["zphot_ANNz2"], dtype=float)
    base = (
        (np.asarray(catalogue["masked"]) == 0)
        & np.isfinite(z)
        & (z > 0.1)
        & (z < 0.5)
        & np.isfinite(masses["log_m_star_mistele"])
        & (masses["log_m_star_mistele"] < 11.1)
    )
    xyz = comoving_xyz_mpc_h70(
        np.asarray(catalogue["RAJ2000"], dtype=float),
        np.asarray(catalogue["DECJ2000"], dtype=float),
        z,
    )
    isolated = isolation_mask(xyz, z, masses["log_m_kids_h70_1"], base)
    selected = base & isolated
    native_r = np.asarray(catalogue["MAG_AUTO_CALIB"], dtype=float)
    gaap_r = masses["mag_gaap_r_reconstructed"]
    diagnostics = {
        "rows": int(len(z)),
        "masked_zero": int(np.count_nonzero(np.asarray(catalogue["masked"]) == 0)),
        "redshift_0p1_0p5": int(np.count_nonzero((z > 0.1) & (z < 0.5))),
        "base_before_isolation": int(np.count_nonzero(base)),
        "isolated_final": int(np.count_nonzero(selected)),
        "published_target_count": 106_843,
        "count_delta": int(np.count_nonzero(selected) - 106_843),
        "gaap_minus_auto_r_quantiles": {
            str(q): float(np.nanquantile(gaap_r - native_r, q)) for q in (0.01, 0.5, 0.99)
        },
        "reconstructed_colour_quantiles": {
            str(q): float(np.nanquantile(masses["colour_ur_reconstructed"], q)) for q in (0.01, 0.5, 0.99)
        },
        "etg_fraction_base": float(np.mean(masses["is_etg"][base])),
        "authority": LENS_SAMPLE_AUTHORITY,
    }
    return {"selected": selected, "base": base, "isolated": isolated, "masses": masses, "diagnostics": diagnostics}


__all__ = [
    "BRIGHT_BYTES",
    "BRIGHT_URL",
    "LEPHARE_BYTES",
    "LEPHARE_URL",
    "LENS_SAMPLE_AUTHORITY",
    "FlatCosmology",
    "comoving_xyz_mpc_h70",
    "derive_masses",
    "isolation_mask",
    "nearest_qualifying_neighbor_proper_distance",
    "load_aligned_catalogues",
    "reconstruct_gaap_magnitudes",
    "reconstruct_lens_sample",
]
