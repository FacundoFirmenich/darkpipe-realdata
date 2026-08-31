import numpy as np
import pytest

from darkpipe.kids_random_catalogue import (
    RANDOM_MULTIPLIER,
    allocate_redshift_counts,
    generate_tile_randoms,
    official_release_tiles,
    select_frozen_tile_subset,
    source_tile_to_observation_name,
)


def test_official_release_manifest_requires_exact_1006_unique_tiles() -> None:
    manifest = "\n".join(
        f"wget https://example/KiDS_DR4.0_{index}.0_-1.5_ugriZYJHKs_cat.fits"
        for index in range(1006)
    )
    tiles = official_release_tiles(manifest)
    assert len(tiles) == 1006
    assert "KIDS_0.0_-1.5" in tiles
    with pytest.raises(ValueError, match="1005 unique tiles"):
        official_release_tiles("\n".join(manifest.splitlines()[:-1]))


def test_source_tile_name_maps_to_official_observations_name() -> None:
    assert source_tile_to_observation_name("KIDS_129p0_m1p5") == "KIDS_129.0_-1.5"
    assert source_tile_to_observation_name("KIDS_32p5_p12p0") == "KIDS_32.5_12.0"
    assert source_tile_to_observation_name("KIDS_129p4_2p5") == "KIDS_129.4_2.5"


def test_random_allocation_is_exact_and_tile_batches_are_reproducible() -> None:
    parent = np.arange(1, 81)
    allocation = allocate_redshift_counts(parent, tile_count=7)
    np.testing.assert_array_equal(allocation.sum(axis=1), parent * RANDOM_MULTIPLIER)
    first = generate_tile_randoms(
        tile_index=3,
        tile_ra_deg=10.0,
        tile_dec_deg=-2.0,
        redshift_allocation=allocation[:, 3],
    )
    second = generate_tile_randoms(
        tile_index=3,
        tile_ra_deg=10.0,
        tile_dec_deg=-2.0,
        redshift_allocation=allocation[:, 3],
    )
    for key in first:
        np.testing.assert_array_equal(first[key], second[key])
    assert np.all((first["ra_deg"] >= 9.5) & (first["ra_deg"] <= 10.5))
    assert np.all((first["dec_deg"] >= -2.5) & (first["dec_deg"] <= -1.5))
    assert np.all((first["redshift"] >= 0.1) & (first["redshift"] <= 0.5))
    subset = select_frozen_tile_subset(first, tile_index=3, count=5)
    repeated = select_frozen_tile_subset(first, tile_index=3, count=5)
    for key in subset:
        np.testing.assert_array_equal(subset[key], repeated[key])
        assert np.all(np.isin(subset[key], first[key]))
