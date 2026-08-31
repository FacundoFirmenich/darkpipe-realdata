import numpy as np

from darkpipe.kids_random_catalogue import (
    RANDOM_MULTIPLIER,
    allocate_redshift_counts,
    generate_tile_randoms,
    source_tile_to_observation_name,
)


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
