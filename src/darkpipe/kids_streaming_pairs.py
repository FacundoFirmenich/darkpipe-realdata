"""Bounded-memory KiDS lens/source pair accumulation for DarkPipe v0.17.

The module reduces source rows to additive sufficient statistics.  It never
stores the full KiDS source catalogue or a pair table.  Independent row
partitions can therefore be summed exactly before any deprojection or model
comparison.  The output is an observational estimator, not an ontological
classification of the inferred acceleration discrepancy.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Mapping

import numpy as np
from scipy.spatial import cKDTree

from .kids_pair_estimator import source_tomographic_bin
from .object_lensing import FlatLambdaCDM


RADIAL_EDGES_MPC_H70 = np.asarray(
    (
        0.003,
        0.004078028507465327,
        0.005543438835899953,
        0.007535433867396794,
        0.010243238042454604,
        0.013924072248627723,
        0.018927587856636882,
        0.02572908095230656,
        0.0349746418647964,
        0.04754252885434329,
        0.06462659599500155,
        0.08784970026935354,
        0.11941786069023594,
        0.1623298133984349,
        0.220661868883448,
        0.2999551306057588,
        0.40774185785692285,
        0.5542609733424687,
        0.7534306832886879,
        1.0241706016167818,
        1.3921989699670496,
        1.8924756958631634,
        2.572523279138417,
        3.4969410894815445,
        4.75354181727753,
        6.461693014095433,
        8.78365610599023,
        11.94,
    ),
    dtype=np.float64,
)
RADIAL_EDGES_SHA256 = hashlib.sha256(
    np.asarray(RADIAL_EDGES_MPC_H70, dtype="<f8").tobytes()
).hexdigest()
KIDS_BLIND_C_SIGMA_E = np.asarray((0.270, 0.258, 0.273, 0.254, 0.270))
MISTELE_MULTIPLICATIVE_RESPONSE = 0.98531
STREAMING_PAIR_AUTHORITY = (
    "KIDS_OBJECT_PAIR_SUFFICIENT_STATISTICS_NO_MODEL_OR_ONTOLOGY_ADJUDICATION"
)
ORIENTATION_BASIS_KEYS = (
    "sum_e1_cos2phi",
    "sum_e1_sin2phi",
    "sum_e2_cos2phi",
    "sum_e2_sin2phi",
)
ORIENTATION_CONVENTIONS = {
    "east_ccw_catalog_e2_as_math": "CURRENT_IMPLEMENTATION",
    "east_ccw_catalog_e2_sign_flipped": "KIDS_RA_DEC_SIGN_WARNING_TRANSFORM",
    "north_ccw_catalog_e2_as_math": "NORTH_REFERENCED_ANGLE",
    "north_ccw_catalog_e2_sign_flipped": "NORTH_REFERENCED_AND_E2_FLIPPED",
}


@dataclass(frozen=True)
class StreamingPairConfig:
    radial_edges_mpc_h70: tuple[float, ...] = tuple(RADIAL_EDGES_MPC_H70)
    h0_km_s_mpc: float = 73.0
    omega_m: float = 0.2793
    lens_redshift_groups: int = 16

    def __post_init__(self) -> None:
        edges = np.asarray(self.radial_edges_mpc_h70, dtype=float)
        if edges.ndim != 1 or len(edges) < 2 or np.any(np.diff(edges) <= 0):
            raise ValueError("radial edges must be a strictly increasing vector")
        if self.h0_km_s_mpc <= 0 or not 0 < self.omega_m < 1:
            raise ValueError("invalid flat-cosmology parameters")
        if self.lens_redshift_groups < 1:
            raise ValueError("lens_redshift_groups must be positive")


@dataclass(frozen=True)
class LensPayload:
    ra_deg: np.ndarray
    dec_deg: np.ndarray
    redshift: np.ndarray
    baryonic_mass_msun: np.ndarray
    source_row: np.ndarray

    def __post_init__(self) -> None:
        arrays = tuple(
            np.asarray(item)
            for item in (
                self.ra_deg,
                self.dec_deg,
                self.redshift,
                self.baryonic_mass_msun,
                self.source_row,
            )
        )
        if any(item.ndim != 1 for item in arrays):
            raise ValueError("lens payload columns must be one-dimensional")
        if len({len(item) for item in arrays}) != 1 or len(arrays[0]) == 0:
            raise ValueError("lens payload columns must have one non-zero length")
        if np.any(~np.isfinite(arrays[0])) or np.any(~np.isfinite(arrays[1])):
            raise ValueError("lens coordinates must be finite")
        if np.any(~np.isfinite(arrays[2])) or np.any(arrays[2] <= 0):
            raise ValueError("lens redshifts must be finite and positive")
        if np.any(~np.isfinite(arrays[3])) or np.any(arrays[3] <= 0):
            raise ValueError("lens baryonic masses must be finite and positive")

    @property
    def count(self) -> int:
        return len(self.redshift)


def _unit_xyz(ra_deg: np.ndarray, dec_deg: np.ndarray) -> np.ndarray:
    ra = np.deg2rad(np.asarray(ra_deg, dtype=float))
    dec = np.deg2rad(np.asarray(dec_deg, dtype=float))
    cos_dec = np.cos(dec)
    return np.column_stack((cos_dec * np.cos(ra), cos_dec * np.sin(ra), np.sin(dec)))


def empty_pair_sums(lens_count: int, radial_bin_count: int) -> dict[str, np.ndarray]:
    if lens_count <= 0 or radial_bin_count <= 0:
        raise ValueError("positive lens and radial-bin counts are required")
    shape = (lens_count, radial_bin_count)
    return {
        "sum_pair_weight": np.zeros(shape, dtype=np.float64),
        "sum_tangential": np.zeros(shape, dtype=np.float64),
        "sum_cross": np.zeros(shape, dtype=np.float64),
        "sum_shape_variance": np.zeros(shape, dtype=np.float64),
        "pair_count": np.zeros(shape, dtype=np.int64),
    }


def merge_pair_sums(parts: list[Mapping[str, np.ndarray]]) -> dict[str, np.ndarray]:
    if not parts:
        raise ValueError("at least one pair-sum partition is required")
    base_keys = tuple(empty_pair_sums(1, 1))
    required = tuple(parts[0])
    if any(key not in required for key in base_keys):
        raise ValueError("pair-sum partition misses a required base statistic")
    if any(tuple(part) != required for part in parts[1:]):
        raise ValueError("pair-sum partitions expose different statistic keys")
    shape = np.asarray(parts[0][required[0]]).shape
    merged = {
        key: np.zeros(shape, dtype=np.int64 if key == "pair_count" else np.float64)
        for key in required
    }
    for part in parts:
        for key in required:
            values = np.asarray(part[key])
            if values.shape != shape:
                raise ValueError(f"partition shape mismatch for {key}")
            merged[key] += values
    return merged


def _bearing_components(
    lens_ra_rad: np.ndarray,
    lens_dec_rad: np.ndarray,
    source_ra_rad: np.ndarray,
    source_dec_rad: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return cos(2phi), sin(2phi) from an exact spherical bearing."""

    dra = (source_ra_rad - lens_ra_rad + np.pi) % (2.0 * np.pi) - np.pi
    east = np.cos(source_dec_rad) * np.sin(dra)
    north = (
        np.cos(lens_dec_rad) * np.sin(source_dec_rad)
        - np.sin(lens_dec_rad) * np.cos(source_dec_rad) * np.cos(dra)
    )
    phi = np.arctan2(north, east)
    return np.cos(2.0 * phi), np.sin(2.0 * phi)


def _lens_groups(redshift: np.ndarray, count: int) -> tuple[np.ndarray, ...]:
    order = np.argsort(np.asarray(redshift, dtype=float), kind="stable")
    return tuple(group for group in np.array_split(order, count) if len(group))


def accumulate_source_chunk(
    lenses: LensPayload,
    sources: Mapping[str, np.ndarray],
    sigma_critical_by_lens_tomo: np.ndarray,
    *,
    config: StreamingPairConfig = StreamingPairConfig(),
    include_orientation_basis: bool = False,
) -> tuple[dict[str, np.ndarray], dict[str, int]]:
    """Reduce one authentic source chunk to per-lens radial sufficient sums.

    ``sigma_critical_by_lens_tomo`` is the already calibrated Eq. 10 lookup
    evaluated for each lens and each of the five source tomographic bins.
    """

    required = (
        "ALPHA_J2000",
        "DELTA_J2000",
        "Z_B",
        "e1",
        "e2",
        "weight",
        "SG_FLAG",
        "SG2DPHOT",
        "CLASS_STAR",
        "IMAFLAGS_ISO",
        "MASK",
    )
    missing = [name for name in required if name not in sources]
    if missing:
        raise ValueError(f"source chunk misses columns: {missing}")
    arrays = {name: np.asarray(sources[name]) for name in required}
    row_count = len(arrays["Z_B"])
    if any(len(values) != row_count for values in arrays.values()):
        raise ValueError("source columns have unequal lengths")
    sigma_grid = np.asarray(sigma_critical_by_lens_tomo, dtype=float)
    if sigma_grid.shape != (lenses.count, 5):
        raise ValueError("sigma-critical grid must have shape (lens_count, 5)")

    selected = (
        (arrays["SG_FLAG"] == 1)
        & (arrays["SG2DPHOT"] == 0)
        & (arrays["CLASS_STAR"] < 0.5)
        & (arrays["IMAFLAGS_ISO"] == 0)
        & ((arrays["MASK"].astype(np.int64) & 28668) == 0)
        & np.isfinite(arrays["ALPHA_J2000"])
        & np.isfinite(arrays["DELTA_J2000"])
        & np.isfinite(arrays["Z_B"])
        & np.isfinite(arrays["e1"])
        & np.isfinite(arrays["e2"])
        & np.isfinite(arrays["weight"])
        & (arrays["weight"] > 0)
    )
    tomo_all = source_tomographic_bin(arrays["Z_B"])
    selected &= tomo_all >= 0
    chosen = np.flatnonzero(selected)
    edges = np.asarray(config.radial_edges_mpc_h70, dtype=float)
    output = empty_pair_sums(lenses.count, len(edges) - 1)
    if include_orientation_basis:
        output.update(
            {
                key: np.zeros_like(output["sum_pair_weight"])
                for key in ORIENTATION_BASIS_KEYS
            }
        )
    diagnostics = {
        "source_rows": int(row_count),
        "selected_source_rows": int(len(chosen)),
        "candidate_pairs": 0,
        "accepted_pairs": 0,
    }
    if len(chosen) == 0:
        return output, diagnostics

    source_ra = np.deg2rad(arrays["ALPHA_J2000"][chosen].astype(float))
    source_dec = np.deg2rad(arrays["DELTA_J2000"][chosen].astype(float))
    source_xyz = _unit_xyz(
        arrays["ALPHA_J2000"][chosen], arrays["DELTA_J2000"][chosen]
    )
    source_tree = cKDTree(source_xyz)
    lens_xyz = _unit_xyz(lenses.ra_deg, lenses.dec_deg)
    lens_ra = np.deg2rad(np.asarray(lenses.ra_deg, dtype=float))
    lens_dec = np.deg2rad(np.asarray(lenses.dec_deg, dtype=float))
    cosmology = FlatLambdaCDM(config.h0_km_s_mpc, config.omega_m)
    h70 = config.h0_km_s_mpc / 70.0
    distance_h70 = np.asarray(
        [cosmology.angular_diameter_distance_mpc(float(z)) * h70 for z in lenses.redshift]
    )
    max_radius = float(edges[-1])
    flat_bins = lenses.count * (len(edges) - 1)

    for global_lenses in _lens_groups(lenses.redshift, config.lens_redshift_groups):
        maximum_angle = max_radius / float(np.min(distance_h70[global_lenses]))
        maximum_chord = 2.0 * np.sin(min(maximum_angle, np.pi) / 2.0)
        lens_tree = cKDTree(lens_xyz[global_lenses])
        pairs = lens_tree.sparse_distance_matrix(
            source_tree, maximum_chord, output_type="coo_matrix"
        )
        if pairs.nnz == 0:
            continue
        lens_index = global_lenses[np.asarray(pairs.row, dtype=np.int64)]
        source_local = np.asarray(pairs.col, dtype=np.int64)
        diagnostics["candidate_pairs"] += int(len(lens_index))
        separation = 2.0 * np.arcsin(np.minimum(1.0, np.asarray(pairs.data) / 2.0))
        radius = separation * distance_h70[lens_index]
        source_index = chosen[source_local]
        tomo = tomo_all[source_index].astype(np.int64)
        valid = (
            (radius >= edges[0])
            & (radius < edges[-1])
            & (arrays["Z_B"][source_index] > lenses.redshift[lens_index] + 0.2)
        )
        sigma = sigma_grid[lens_index, tomo]
        valid &= np.isfinite(sigma) & (sigma > 0)
        if not np.any(valid):
            continue
        lens_index = lens_index[valid]
        source_index = source_index[valid]
        source_local = source_local[valid]
        tomo = tomo[valid]
        sigma = sigma[valid]
        radius = radius[valid]
        radial_bin = np.searchsorted(edges, radius, side="right") - 1
        cos2, sin2 = _bearing_components(
            lens_ra[lens_index],
            lens_dec[lens_index],
            source_ra[source_local],
            source_dec[source_local],
        )
        e1 = arrays["e1"][source_index].astype(float)
        e2 = arrays["e2"][source_index].astype(float)
        tangential = -(e1 * cos2 + e2 * sin2)
        cross = e1 * sin2 - e2 * cos2
        source_weight = arrays["weight"][source_index].astype(float)
        pair_weight = source_weight / sigma**2
        cell = lens_index * (len(edges) - 1) + radial_bin
        output["sum_pair_weight"] += np.bincount(
            cell, weights=pair_weight, minlength=flat_bins
        ).reshape(output["sum_pair_weight"].shape)
        output["sum_tangential"] += np.bincount(
            cell, weights=source_weight * tangential / sigma, minlength=flat_bins
        ).reshape(output["sum_tangential"].shape)
        output["sum_cross"] += np.bincount(
            cell, weights=source_weight * cross / sigma, minlength=flat_bins
        ).reshape(output["sum_cross"].shape)
        if include_orientation_basis:
            basis_scale = source_weight / sigma
            for key, values in (
                ("sum_e1_cos2phi", e1 * cos2),
                ("sum_e1_sin2phi", e1 * sin2),
                ("sum_e2_cos2phi", e2 * cos2),
                ("sum_e2_sin2phi", e2 * sin2),
            ):
                output[key] += np.bincount(
                    cell,
                    weights=basis_scale * values,
                    minlength=flat_bins,
                ).reshape(output[key].shape)
        output["sum_shape_variance"] += np.bincount(
            cell,
            weights=(source_weight**2 / sigma**2) * KIDS_BLIND_C_SIGMA_E[tomo] ** 2,
            minlength=flat_bins,
        ).reshape(output["sum_shape_variance"].shape)
        output["pair_count"] += np.bincount(
            cell, minlength=flat_bins
        ).astype(np.int64).reshape(output["pair_count"].shape)
        diagnostics["accepted_pairs"] += int(len(cell))
    return output, diagnostics


def finalize_orientation_conventions(
    pair_sums: Mapping[str, np.ndarray],
) -> dict[str, dict[str, np.ndarray | str]]:
    """Reconstruct the four preregistered sky-coordinate conventions.

    KiDS documents that the sign of catalog ``e2`` depends on the user's
    angular convention in the RA/Dec frame.  Keeping the four linear basis
    terms makes that convention test exact: no source rows or pair geometry
    are recomputed and no result-dependent rotation is fitted.
    """

    missing = [key for key in ORIENTATION_BASIS_KEYS if key not in pair_sums]
    if missing:
        raise ValueError(f"orientation basis is incomplete: {missing}")
    denominator = np.asarray(pair_sums["sum_pair_weight"], dtype=float)
    variance_sum = np.asarray(pair_sums["sum_shape_variance"], dtype=float)
    e1c, e1s, e2c, e2s = (
        np.asarray(pair_sums[key], dtype=float) for key in ORIENTATION_BASIS_KEYS
    )
    numerators = {
        "east_ccw_catalog_e2_as_math": (-(e1c + e2s), e1s - e2c),
        "east_ccw_catalog_e2_sign_flipped": (-(e1c - e2s), e1s + e2c),
        "north_ccw_catalog_e2_as_math": (e1c - e2s, e1s + e2c),
        "north_ccw_catalog_e2_sign_flipped": (e1c + e2s, e1s - e2c),
    }
    with np.errstate(divide="ignore", invalid="ignore"):
        variance = np.divide(
            variance_sum,
            denominator**2,
            out=np.full_like(denominator, np.nan),
            where=denominator > 0,
        ) / MISTELE_MULTIPLICATIVE_RESPONSE**2
    result: dict[str, dict[str, np.ndarray | str]] = {}
    for name, (tangential_sum, cross_sum) in numerators.items():
        with np.errstate(divide="ignore", invalid="ignore"):
            tangential = np.divide(
                tangential_sum,
                denominator,
                out=np.full_like(denominator, np.nan),
                where=denominator > 0,
            ) / MISTELE_MULTIPLICATIVE_RESPONSE
            cross = np.divide(
                cross_sum,
                denominator,
                out=np.full_like(denominator, np.nan),
                where=denominator > 0,
            ) / MISTELE_MULTIPLICATIVE_RESPONSE
        result[name] = {
            "esd_msun_mpc2": tangential,
            "cross_esd_msun_mpc2": cross,
            "variance_esd": variance.copy(),
            "pair_weight_sum": denominator.copy(),
            "pair_count": np.asarray(pair_sums["pair_count"], dtype=np.int64).copy(),
            "authority": ORIENTATION_CONVENTIONS[name],
        }
    return result


def finalize_individual_esd(
    pair_sums: Mapping[str, np.ndarray],
) -> dict[str, np.ndarray | str]:
    denominator = np.asarray(pair_sums["sum_pair_weight"], dtype=float)
    numerator_t = np.asarray(pair_sums["sum_tangential"], dtype=float)
    numerator_x = np.asarray(pair_sums["sum_cross"], dtype=float)
    variance_sum = np.asarray(pair_sums["sum_shape_variance"], dtype=float)
    if not (
        denominator.shape == numerator_t.shape == numerator_x.shape == variance_sum.shape
    ):
        raise ValueError("pair-sum arrays have incompatible shapes")
    with np.errstate(divide="ignore", invalid="ignore"):
        esd = np.divide(
            numerator_t,
            denominator,
            out=np.full_like(denominator, np.nan),
            where=denominator > 0,
        )
        cross = np.divide(
            numerator_x,
            denominator,
            out=np.full_like(denominator, np.nan),
            where=denominator > 0,
        )
        variance = np.divide(
            variance_sum,
            denominator**2,
            out=np.full_like(denominator, np.nan),
            where=denominator > 0,
        )
    return {
        "esd_msun_mpc2": esd / MISTELE_MULTIPLICATIVE_RESPONSE,
        "cross_esd_msun_mpc2": cross / MISTELE_MULTIPLICATIVE_RESPONSE,
        "variance_esd": variance / MISTELE_MULTIPLICATIVE_RESPONSE**2,
        "pair_weight_sum": denominator,
        "pair_count": np.asarray(pair_sums["pair_count"], dtype=np.int64),
        "authority": STREAMING_PAIR_AUTHORITY,
    }


def pair_sums_sha256(pair_sums: Mapping[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for key in sorted(pair_sums):
        values = np.ascontiguousarray(np.asarray(pair_sums[key]))
        digest.update(key.encode("utf-8"))
        digest.update(str(values.dtype).encode("ascii"))
        digest.update(json.dumps(values.shape).encode("ascii"))
        digest.update(values.view(np.uint8))
    return digest.hexdigest()


def save_pair_partition(
    path: Path,
    pair_sums: Mapping[str, np.ndarray],
    metadata: Mapping[str, object],
) -> None:
    """Write one compact restartable partition atomically."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    arrays = {key: np.asarray(value) for key, value in pair_sums.items()}
    with temporary.open("wb") as stream:
        np.savez_compressed(
            stream,
            **arrays,
            metadata_json=np.asarray(json.dumps(dict(metadata), sort_keys=True)),
            content_sha256=np.asarray(pair_sums_sha256(pair_sums)),
        )
    temporary.replace(target)


__all__ = [
    "KIDS_BLIND_C_SIGMA_E",
    "LensPayload",
    "MISTELE_MULTIPLICATIVE_RESPONSE",
    "ORIENTATION_BASIS_KEYS",
    "ORIENTATION_CONVENTIONS",
    "RADIAL_EDGES_MPC_H70",
    "RADIAL_EDGES_SHA256",
    "STREAMING_PAIR_AUTHORITY",
    "StreamingPairConfig",
    "accumulate_source_chunk",
    "empty_pair_sums",
    "finalize_individual_esd",
    "finalize_orientation_conventions",
    "merge_pair_sums",
    "pair_sums_sha256",
    "save_pair_partition",
]
