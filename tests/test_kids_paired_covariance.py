"""Analytic algorithm fixtures; these are not observational science evidence."""
import numpy as np
import pytest

from darkpipe.kids_paired_covariance import paired_spatial_jackknife
from darkpipe.kids_random_control import empty_random_control_sums


IDS = tuple(f"region-{i}" for i in range(5))


def sums(values):
    array = np.asarray(values, dtype=float)
    output = {k: np.zeros_like(array, dtype=v.dtype)
              for k, v in empty_random_control_sums(array.shape[1]).items()}
    for key in ("esd_weight_sum", "gobs_weight_sum_tangential", "gobs_weight_sum_cross"):
        output[key][:] = 1
    for key in ("esd_weighted_sum_tangential", "gobs_inverse_variance_sum_tangential"):
        output[key][:] = array
    for key in ("esd_weighted_sum_cross", "gobs_inverse_variance_sum_cross"):
        output[key][:] = -array / 3
    return output


def run(signal, random, **kwargs):
    return paired_spatial_jackknife(signal, random, signal_region_ids=IDS,
                                   random_region_ids=kwargs.pop("random_ids", IDS),
                                   region_map_sha256="a" * 64, **kwargs)


def test_shared_source_mode_cancels_in_difference_but_not_independent_sum():
    values = np.array([[1, 3], [4, 1], [2, 8], [9, 4], [3, 2]])
    result = run(sums(values), sums(values))
    assert np.max(result["covariance_signal"]) > 0
    np.testing.assert_array_equal(result["covariance_corrected"], np.zeros((8, 8)))
    np.testing.assert_array_equal(result["corrected_values"], np.zeros(8))


def test_cross_covariance_identity_and_direct_replicate_gram_agree():
    signal = sums([[1, 3], [4, 1], [2, 8], [9, 4], [3, 2]])
    random = sums([[0, 2], [3, 1], [1, 3], [6, 2], [1, 1]])
    result = run(signal, random)
    cross = result["covariance_signal_random"]
    identity = result["covariance_signal"] + result["covariance_random"] - cross - cross.T
    np.testing.assert_allclose(result["covariance_corrected"], identity, atol=1e-14)
    reps = result["corrected_replicates"]
    centered = reps - reps.mean(axis=0)
    np.testing.assert_allclose(result["covariance_corrected"], 4 / 5 * centered.T @ centered)
    assert np.linalg.eigvalsh(result["covariance_corrected"]).min() > -1e-12


def test_permuted_region_ids_are_rejected_instead_of_independent_subtraction():
    source = sums(np.arange(10).reshape(5, 2))
    with pytest.raises(ValueError, match="identical ordered"):
        run(source, source, random_ids=IDS[::-1])


def test_missing_bin_keeps_nan_and_one_common_support():
    source = sums(np.arange(10).reshape(5, 2))
    for key in ("esd_weight_sum", "gobs_weight_sum_tangential", "gobs_weight_sum_cross"):
        source[key][:, 1] = 0
    result = run(source, source)
    np.testing.assert_array_equal(result["valid_columns"], [True, False] * 4)
    assert np.isnan(result["covariance_corrected"][1]).all()
    assert result["scientific_result"] is False


def test_unpaired_shapes_and_nonfinite_input_cannot_promote():
    source = sums(np.arange(10).reshape(5, 2))
    bad = {k: v[:, :1] for k, v in source.items()}
    with pytest.raises(ValueError, match="shapes"):
        run(source, bad)
    source["esd_weighted_sum_tangential"][0, 0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        run(source, source)
