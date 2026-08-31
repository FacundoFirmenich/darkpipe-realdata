"""Compact additive reduction of authentic KiDS random-coordinate controls.

Random lenses are finalized, deprojected and reduced batchwise.  No
45-million-row catalogue and no per-random-lens profile matrix is persisted.
The reduction preserves the stacked ESD, cross ESD, deproject-first radial
acceleration and cross-acceleration estimators described by Mistele et al.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

import numpy as np

from .kids_exact_deprojection import deproject_individual_profiles
from .kids_streaming_pairs import finalize_individual_esd


RANDOM_CONTROL_AUTHORITY = (
    "ADDITIVE_RANDOM_ESD_AND_DEPROJECT_FIRST_CONTROL_NO_MODEL_ADJUDICATION"
)
_FLOAT_KEYS = (
    "esd_weighted_sum_tangential",
    "esd_weighted_sum_cross",
    "esd_weight_sum",
    "esd_variance_numerator",
    "gobs_inverse_variance_sum_tangential",
    "gobs_inverse_variance_sum_cross",
    "gobs_weight_sum_tangential",
    "gobs_weight_sum_cross",
)
_INTEGER_KEYS = (
    "esd_effective_randoms",
    "gobs_effective_randoms_tangential",
    "gobs_effective_randoms_cross",
    "pair_count",
)


def empty_random_control_sums(radial_bin_count: int) -> dict[str, np.ndarray]:
    if radial_bin_count <= 0:
        raise ValueError("radial_bin_count must be positive")
    return {
        **{key: np.zeros(radial_bin_count, dtype=np.float64) for key in _FLOAT_KEYS},
        **{key: np.zeros(radial_bin_count, dtype=np.int64) for key in _INTEGER_KEYS},
    }


def _inverse_variance_reduce(
    values: np.ndarray, variances: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    valid = np.isfinite(values) & np.isfinite(variances) & (variances > 0)
    weight = np.zeros_like(variances, dtype=np.float64)
    weight[valid] = 1.0 / variances[valid]
    weighted = np.where(valid, values * weight, 0.0)
    return weighted.sum(axis=0), weight.sum(axis=0), valid.sum(axis=0).astype(np.int64)


def reduce_random_pair_batch(
    pair_sums: Mapping[str, np.ndarray],
    radial_edges_mpc_h70: np.ndarray,
) -> dict[str, np.ndarray]:
    """Finalize and reduce one bounded batch of random-lens pair sums."""

    edges = np.asarray(radial_edges_mpc_h70, dtype=np.float64)
    if edges.ndim != 1 or len(edges) < 3 or np.any(np.diff(edges) <= 0):
        raise ValueError("strictly increasing radial edges are required")
    centers = np.sqrt(edges[:-1] * edges[1:])
    individual = finalize_individual_esd(pair_sums)
    esd = np.asarray(individual["esd_msun_mpc2"], dtype=np.float64)
    cross = np.asarray(individual["cross_esd_msun_mpc2"], dtype=np.float64)
    variance = np.asarray(individual["variance_esd"], dtype=np.float64)
    pair_weight = np.asarray(individual["pair_weight_sum"], dtype=np.float64)
    if esd.ndim != 2 or esd.shape[1] != len(centers):
        raise ValueError("pair sums do not match radial edges")

    result = empty_random_control_sums(len(centers))
    valid_esd = np.isfinite(esd) & np.isfinite(cross) & np.isfinite(variance) & (pair_weight > 0)
    result["esd_weighted_sum_tangential"] = np.where(
        valid_esd, pair_weight * esd, 0.0
    ).sum(axis=0)
    result["esd_weighted_sum_cross"] = np.where(
        valid_esd, pair_weight * cross, 0.0
    ).sum(axis=0)
    result["esd_weight_sum"] = np.where(valid_esd, pair_weight, 0.0).sum(axis=0)
    result["esd_variance_numerator"] = np.where(
        valid_esd, pair_weight**2 * variance, 0.0
    ).sum(axis=0)
    result["esd_effective_randoms"] = valid_esd.sum(axis=0).astype(np.int64)
    result["pair_count"] = np.asarray(individual["pair_count"], dtype=np.int64).sum(axis=0)

    tangential_gobs = deproject_individual_profiles(
        centers, edges, esd, variance, centers, outer_tail="sis"
    )
    cross_gobs = deproject_individual_profiles(
        centers, edges, cross, variance, centers, outer_tail="zero"
    )
    tangential_sum, tangential_weight, tangential_count = _inverse_variance_reduce(
        np.asarray(tangential_gobs["gobs_m_s2"]),
        np.asarray(tangential_gobs["variance_gobs"]),
    )
    cross_sum, cross_weight, cross_count = _inverse_variance_reduce(
        np.asarray(cross_gobs["gobs_m_s2"]),
        np.asarray(cross_gobs["variance_gobs"]),
    )
    result["gobs_inverse_variance_sum_tangential"] = tangential_sum
    result["gobs_inverse_variance_sum_cross"] = cross_sum
    result["gobs_weight_sum_tangential"] = tangential_weight
    result["gobs_weight_sum_cross"] = cross_weight
    result["gobs_effective_randoms_tangential"] = tangential_count
    result["gobs_effective_randoms_cross"] = cross_count
    return result


def merge_random_control_sums(
    parts: list[Mapping[str, np.ndarray]],
) -> dict[str, np.ndarray]:
    if not parts:
        raise ValueError("at least one random-control part is required")
    bin_count = len(np.asarray(parts[0]["esd_weight_sum"]))
    merged = empty_random_control_sums(bin_count)
    for part in parts:
        if set(part) != set(merged):
            raise ValueError("random-control keys differ")
        for key in merged:
            values = np.asarray(part[key])
            if values.shape != merged[key].shape:
                raise ValueError(f"random-control shape differs for {key}")
            merged[key] += values
    return merged


def finalize_random_control(
    sums: Mapping[str, np.ndarray],
) -> dict[str, np.ndarray | str]:
    weight = np.asarray(sums["esd_weight_sum"], dtype=np.float64)
    tangential_weight = np.asarray(sums["gobs_weight_sum_tangential"], dtype=np.float64)
    cross_weight = np.asarray(sums["gobs_weight_sum_cross"], dtype=np.float64)

    def divide(numerator: str, denominator: np.ndarray) -> np.ndarray:
        values = np.asarray(sums[numerator], dtype=np.float64)
        return np.divide(values, denominator, out=np.full_like(values, np.nan), where=denominator > 0)

    return {
        "random_esd_msun_mpc2": divide("esd_weighted_sum_tangential", weight),
        "random_cross_esd_msun_mpc2": divide("esd_weighted_sum_cross", weight),
        "random_esd_variance": np.divide(
            np.asarray(sums["esd_variance_numerator"], dtype=np.float64),
            weight**2,
            out=np.full_like(weight, np.nan),
            where=weight > 0,
        ),
        "random_gobs_m_s2": divide(
            "gobs_inverse_variance_sum_tangential", tangential_weight
        ),
        "random_cross_gobs_m_s2": divide(
            "gobs_inverse_variance_sum_cross", cross_weight
        ),
        "random_gobs_variance": np.divide(
            1.0,
            tangential_weight,
            out=np.full_like(tangential_weight, np.nan),
            where=tangential_weight > 0,
        ),
        "random_cross_gobs_variance": np.divide(
            1.0,
            cross_weight,
            out=np.full_like(cross_weight, np.nan),
            where=cross_weight > 0,
        ),
        "authority": RANDOM_CONTROL_AUTHORITY,
    }


def random_control_sha256(sums: Mapping[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for key in sorted(sums):
        values = np.ascontiguousarray(np.asarray(sums[key]))
        digest.update(key.encode("utf-8"))
        digest.update(str(values.dtype).encode("ascii"))
        digest.update(json.dumps(values.shape).encode("ascii"))
        digest.update(values.view(np.uint8))
    return digest.hexdigest()


def save_random_control(
    path: Path, sums: Mapping[str, np.ndarray], metadata: Mapping[str, object]
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    with temporary.open("wb") as stream:
        np.savez_compressed(
            stream,
            **{key: np.asarray(value) for key, value in sums.items()},
            metadata_json=np.asarray(json.dumps(dict(metadata), sort_keys=True)),
            content_sha256=np.asarray(random_control_sha256(sums)),
        )
    temporary.replace(target)


__all__ = [
    "RANDOM_CONTROL_AUTHORITY",
    "empty_random_control_sums",
    "finalize_random_control",
    "merge_random_control_sums",
    "random_control_sha256",
    "reduce_random_pair_batch",
    "save_random_control",
]
