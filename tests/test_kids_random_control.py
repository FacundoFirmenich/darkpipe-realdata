import numpy as np

from darkpipe.kids_random_control import (
    finalize_random_control,
    merge_random_control_sums,
    random_control_sha256,
    reduce_random_pair_batch,
)
from darkpipe.kids_streaming_pairs import empty_pair_sums


def _batch(scale: float) -> dict[str, np.ndarray]:
    sums = empty_pair_sums(3, 3)
    sums["sum_pair_weight"][:] = scale
    sums["sum_tangential"][:] = scale * np.asarray([1.0, 0.5, 0.25])
    sums["sum_cross"][:] = scale * np.asarray([0.1, -0.1, 0.05])
    sums["sum_shape_variance"][:] = scale**2 * 0.04
    sums["pair_count"][:] = 2
    return sums


def test_random_batch_reduces_to_compact_additive_surface() -> None:
    edges = np.asarray([1.0, 2.0, 4.0, 8.0])
    reduced = reduce_random_pair_batch(_batch(2.0), edges)
    assert all(values.shape == (3,) for values in reduced.values())
    assert np.all(reduced["esd_effective_randoms"] == 3)
    assert np.all(reduced["pair_count"] == 6)
    final = finalize_random_control(reduced)
    assert np.all(np.isfinite(final["random_esd_msun_mpc2"]))
    assert np.all(np.isfinite(final["random_gobs_m_s2"]))


def test_random_reduction_merge_is_exact_and_hash_sensitive() -> None:
    edges = np.asarray([1.0, 2.0, 4.0, 8.0])
    first = reduce_random_pair_batch(_batch(1.0), edges)
    second = reduce_random_pair_batch(_batch(2.0), edges)
    merged = merge_random_control_sums([first, second])
    for key in merged:
        np.testing.assert_allclose(merged[key], first[key] + second[key])
    assert random_control_sha256(merged) != random_control_sha256(first)
