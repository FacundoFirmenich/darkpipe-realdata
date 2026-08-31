"""Sealed, batchwise KiDS random-coordinate construction for DarkPipe v0.17."""

from __future__ import annotations

import re
from typing import Sequence

import numpy as np


RANDOM_SEED = 20_260_831_017
RANDOM_MULTIPLIER = 50
REDSHIFT_EDGES = np.linspace(0.1, 0.5, 81)
EXPECTED_SOURCE_TILE_COUNT = 1006
EXPECTED_SOURCE_THELI_TILE_COUNT = 988
RANDOM_AUTHORITY = "MISTELE2024_RANDOM_CONSTRUCTION_INDEPENDENT_REPRODUCTION"
RANDOM_PILOT_AUTHORITY = "STRATIFIED_SUBSET_OF_FROZEN_RANDOM_CATALOGUE_ENGINEERING_PILOT"
_SOURCE_TILE = re.compile(r"^KIDS_(\d+)p(\d+)_([mp]?)(\d+)p(\d+)$")
_RELEASE_CATALOGUE = re.compile(
    r"KiDS_DR4\.[01]_([0-9.]+_-?[0-9.]+)_ugriZYJHKs_cat\.fits"
)


def source_tile_to_observation_name(name: str) -> str:
    match = _SOURCE_TILE.fullmatch(name.strip())
    if not match:
        raise ValueError(f"unrecognized KiDS source tile name: {name!r}")
    ra_integer, ra_fraction, sign, dec_integer, dec_fraction = match.groups()
    dec_sign = "-" if sign == "m" else ""
    return f"KIDS_{int(ra_integer)}.{ra_fraction}_{dec_sign}{int(dec_integer)}.{dec_fraction}"


def official_release_tiles(manifest_text: str) -> list[str]:
    """Extract the exact 1006 DR4 survey tiles from the official download manifest."""

    tiles = sorted({f"KIDS_{match}" for match in _RELEASE_CATALOGUE.findall(manifest_text)})
    if len(tiles) != EXPECTED_SOURCE_TILE_COUNT:
        raise ValueError(
            f"official DR4 catalogue manifest contains {len(tiles)} unique tiles, "
            f"expected {EXPECTED_SOURCE_TILE_COUNT}"
        )
    return tiles


def allocate_redshift_counts(
    parent_bin_counts: Sequence[int], *, tile_count: int
) -> np.ndarray:
    counts = np.asarray(parent_bin_counts, dtype=np.int64)
    if counts.shape != (80,) or np.any(counts < 0):
        raise ValueError("parent redshift histogram must contain 80 non-negative counts")
    if tile_count <= 0:
        raise ValueError("tile_count must be positive")
    totals = counts * RANDOM_MULTIPLIER
    allocation = np.empty((80, tile_count), dtype=np.int64)
    for redshift_bin, total in enumerate(totals):
        quotient, remainder = divmod(int(total), tile_count)
        allocation[redshift_bin] = quotient
        if remainder:
            indices = (redshift_bin + np.arange(remainder)) % tile_count
            allocation[redshift_bin, indices] += 1
    if not np.array_equal(allocation.sum(axis=1), totals):
        raise RuntimeError("random redshift allocation failed exact-count conservation")
    return allocation


def generate_tile_randoms(
    *,
    tile_index: int,
    tile_ra_deg: float,
    tile_dec_deg: float,
    redshift_allocation: Sequence[int],
    seed: int = RANDOM_SEED,
    tile_width_deg: float = 1.0,
) -> dict[str, np.ndarray]:
    """Generate one tile batch without materializing the 45-million-row catalogue."""

    allocation = np.asarray(redshift_allocation, dtype=np.int64)
    if allocation.shape != (80,) or np.any(allocation < 0):
        raise ValueError("one 80-bin non-negative allocation vector is required")
    if tile_index < 0 or tile_width_deg <= 0:
        raise ValueError("invalid tile index or width")
    rng = np.random.default_rng(np.random.SeedSequence([seed, tile_index]))
    total = int(allocation.sum())
    ra = rng.uniform(tile_ra_deg - tile_width_deg / 2, tile_ra_deg + tile_width_deg / 2, total)
    lower_dec = max(-90.0, tile_dec_deg - tile_width_deg / 2)
    upper_dec = min(90.0, tile_dec_deg + tile_width_deg / 2)
    sin_dec = rng.uniform(np.sin(np.deg2rad(lower_dec)), np.sin(np.deg2rad(upper_dec)), total)
    dec = np.rad2deg(np.arcsin(sin_dec))
    redshift = np.empty(total, dtype=np.float64)
    cursor = 0
    for index, count in enumerate(allocation):
        next_cursor = cursor + int(count)
        redshift[cursor:next_cursor] = rng.uniform(
            REDSHIFT_EDGES[index], REDSHIFT_EDGES[index + 1], int(count)
        )
        cursor = next_cursor
    order = rng.permutation(total)
    return {
        "ra_deg": ra[order],
        "dec_deg": dec[order],
        "redshift": redshift[order],
    }


def select_frozen_tile_subset(
    tile_randoms: dict[str, np.ndarray],
    *,
    tile_index: int,
    count: int,
    seed: int = RANDOM_SEED,
) -> dict[str, np.ndarray]:
    """Select a deterministic uniform subset of an already frozen tile batch."""

    lengths = {len(np.asarray(values)) for values in tile_randoms.values()}
    if len(lengths) != 1:
        raise ValueError("tile random columns have unequal lengths")
    total = lengths.pop()
    if tile_index < 0 or count <= 0 or count > total:
        raise ValueError("invalid tile subset request")
    selector = np.random.default_rng(np.random.SeedSequence([seed, tile_index, 0xD017]))
    indices = np.sort(selector.choice(total, size=count, replace=False))
    return {key: np.asarray(values)[indices] for key, values in tile_randoms.items()}


__all__ = [
    "EXPECTED_SOURCE_TILE_COUNT",
    "EXPECTED_SOURCE_THELI_TILE_COUNT",
    "RANDOM_AUTHORITY",
    "RANDOM_MULTIPLIER",
    "RANDOM_PILOT_AUTHORITY",
    "RANDOM_SEED",
    "REDSHIFT_EDGES",
    "allocate_redshift_counts",
    "generate_tile_randoms",
    "official_release_tiles",
    "select_frozen_tile_subset",
    "source_tile_to_observation_name",
]
