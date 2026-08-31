from __future__ import annotations

import numpy as np

from darkpipe.kids_lens_sample import (
    FlatCosmology,
    derive_masses,
    isolation_mask,
    nearest_qualifying_neighbor_proper_distance,
    reconstruct_gaap_magnitudes,
)


def test_cosmology_and_apparent_magnitude_reconstruction() -> None:
    cosmology = FlatCosmology(h0=70.0, omega_m=0.3)
    assert 38.2 < cosmology.distance_modulus([0.1])[0] < 38.4
    u, r = reconstruct_gaap_magnitudes(
        np.array([0.1]), np.array([-18.0]), np.array([-20.0]), np.array([0.2]), np.array([0.1])
    )
    np.testing.assert_allclose((u - r)[0], 2.1, rtol=0.0, atol=1e-12)


def test_published_mass_transformations_are_applied_by_type() -> None:
    catalogue = {
        "zphot_ANNz2": np.array([0.1, 0.1]),
        "MAG_ABS_u": np.array([-17.0, -20.0]),
        "MAG_ABS_r": np.array([-20.0, -20.0]),
        "K_COR_u": np.zeros(2),
        "K_COR_r": np.zeros(2),
        "MAG_AUTO_CALIB": np.array([18.0, 18.0]),
        "MASS_BEST": np.array([10.0, 10.0]),
    }
    result = derive_masses(catalogue)
    np.testing.assert_array_equal(result["is_etg"], [True, False])
    assert np.isclose(
        result["log_m_star_mistele"][0] - result["log_m_kids_h73"][0], np.log10(1.4)
    )
    assert np.isclose(result["log_m_star_mistele"][1], result["log_m_kids_h73"][1])
    assert np.all(result["log_m_baryon_mistele"] > result["log_m_star_mistele"])


def test_isolation_rejects_only_sufficiently_massive_close_neighbor() -> None:
    xyz = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [20.0, 0.0, 0.0]])
    z = np.array([0.2, 0.2, 0.2])
    masses = np.array([10.0, 9.2, 11.0])
    candidates = np.array([True, True, True])
    selected = isolation_mask(xyz, z, masses, candidates, proper_radius_mpc_h70=4.0)
    np.testing.assert_array_equal(selected, [False, False, True])
    nearest = nearest_qualifying_neighbor_proper_distance(
        xyz, z, masses, candidates, max_proper_radius_mpc_h70=10.0
    )
    assert np.isclose(nearest[0], 1.0 / 1.2)
    assert np.isclose(nearest[1], 1.0 / 1.2)
    assert np.isinf(nearest[2])
