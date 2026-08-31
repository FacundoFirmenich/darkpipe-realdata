from pathlib import Path

import numpy as np

from darkpipe.kids_pair_estimator import (
    TomographicNz,
    effective_sigma_critical_lookup,
    interpolate_effective_sigma_critical,
    source_tomographic_bin,
)
from darkpipe.object_lensing import FlatLambdaCDM


def _nz() -> tuple[TomographicNz, ...]:
    z = np.linspace(0.0, 2.0, 201)
    output = []
    for center in (0.25, 0.4, 0.6, 0.8, 1.0):
        output.append(TomographicNz(z, np.exp(-0.5 * ((z - center) / 0.12) ** 2)))
    return tuple(output)


def test_tomographic_edges_are_explicit() -> None:
    values = source_tomographic_bin(np.asarray([0.1, 0.1001, 0.3, 0.3001, 1.2, 1.2001, np.nan]))
    assert values.tolist() == [-1, 0, 0, 1, 4, -1, -1]


def test_effective_sigma_lookup_is_finite_and_source_ordered() -> None:
    lookup = effective_sigma_critical_lookup(
        np.asarray([0.1, 0.2, 0.3]),
        _nz(),
        cosmology=FlatLambdaCDM(h0_km_s_mpc=73.0, omega_m=0.2793),
        lens_integration_step=0.005,
    )
    sigma = np.asarray(lookup["sigma_critical_msun_mpc2"])
    assert sigma.shape == (3, 5)
    assert np.all(np.isfinite(sigma))
    assert np.all(sigma > 0)
    assert sigma[1, 4] < sigma[1, 0]


def test_interpolation_enforces_pair_cut_and_tomographic_domain() -> None:
    lookup = effective_sigma_critical_lookup(
        np.asarray([0.1, 0.2, 0.3, 0.4]),
        _nz(),
        cosmology=FlatLambdaCDM(h0_km_s_mpc=73.0, omega_m=0.2793),
        lens_integration_step=0.005,
    )
    result = interpolate_effective_sigma_critical(
        np.asarray([0.2, 0.2, 0.2]), np.asarray([0.35, 0.45, 1.3]), lookup
    )
    assert np.isinf(result[0])
    assert np.isfinite(result[1])
    assert np.isinf(result[2])
