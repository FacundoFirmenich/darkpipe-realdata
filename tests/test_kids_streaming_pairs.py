from __future__ import annotations

import numpy as np

from darkpipe.kids_streaming_pairs import (
    LensPayload,
    StreamingPairConfig,
    accumulate_source_chunk,
    finalize_individual_esd,
    merge_pair_sums,
    pair_sums_sha256,
)


def _sources(ra: np.ndarray, dec: np.ndarray) -> dict[str, np.ndarray]:
    count = len(ra)
    return {
        "ALPHA_J2000": np.asarray(ra, dtype=float),
        "DELTA_J2000": np.asarray(dec, dtype=float),
        "Z_B": np.full(count, 0.6),
        "e1": np.linspace(0.1, 0.1 * count, count),
        "e2": np.zeros(count),
        "weight": np.arange(1, count + 1, dtype=float),
        "SG_FLAG": np.ones(count, dtype=np.int16),
        "SG2DPHOT": np.zeros(count, dtype=np.int16),
        "CLASS_STAR": np.zeros(count),
        "IMAFLAGS_ISO": np.zeros(count, dtype=np.int32),
        "MASK": np.zeros(count, dtype=np.int32),
    }


def _lens_payload() -> LensPayload:
    return LensPayload(
        ra_deg=np.asarray((10.0, 10.5)),
        dec_deg=np.asarray((0.0, 0.0)),
        redshift=np.asarray((0.2, 0.3)),
        baryonic_mass_msun=np.asarray((1e10, 2e10)),
        source_row=np.asarray((3, 8), dtype=np.int32),
    )


def test_partition_merge_is_exactly_additive() -> None:
    lenses = _lens_payload()
    sources = _sources(
        np.asarray((10.01, 10.02, 10.49, 10.51)),
        np.asarray((0.0, 0.01, 0.0, -0.01)),
    )
    sigma = np.full((lenses.count, 5), 4.0e15)
    config = StreamingPairConfig(
        radial_edges_mpc_h70=(0.001, 0.1, 1.0, 20.0),
        lens_redshift_groups=2,
    )
    complete, complete_diag = accumulate_source_chunk(
        lenses, sources, sigma, config=config
    )
    left = {key: value[:2] for key, value in sources.items()}
    right = {key: value[2:] for key, value in sources.items()}
    first, first_diag = accumulate_source_chunk(lenses, left, sigma, config=config)
    second, second_diag = accumulate_source_chunk(lenses, right, sigma, config=config)
    merged = merge_pair_sums([first, second])
    for key in complete:
        np.testing.assert_array_equal(merged[key], complete[key])
    assert first_diag["accepted_pairs"] + second_diag["accepted_pairs"] == complete_diag["accepted_pairs"]
    assert pair_sums_sha256(merged) == pair_sums_sha256(complete)


def test_source_cuts_redshift_cut_cross_channel_and_calibration() -> None:
    lenses = LensPayload(
        ra_deg=np.asarray((0.0,)),
        dec_deg=np.asarray((0.0,)),
        redshift=np.asarray((0.2,)),
        baryonic_mass_msun=np.asarray((1e10,)),
        source_row=np.asarray((0,), dtype=np.int32),
    )
    sources = _sources(np.asarray((0.01, 0.02, 0.03)), np.zeros(3))
    sources["e1"][:] = 0.2
    sources["e2"][:] = 0.0
    sources["Z_B"][:] = (0.6, 0.39, 0.6)
    sources["MASK"][2] = 4
    sigma = np.full((1, 5), 2.0e15)
    sums, diagnostics = accumulate_source_chunk(
        lenses,
        sources,
        sigma,
        config=StreamingPairConfig(
            radial_edges_mpc_h70=(0.001, 1.0, 20.0),
            lens_redshift_groups=1,
        ),
    )
    result = finalize_individual_esd(sums)
    assert diagnostics["accepted_pairs"] == 1
    assert int(np.sum(result["pair_count"])) == 1
    # A source due east has phi=0 and therefore e_t=-e1 and e_x=0.
    finite = np.isfinite(result["esd_msun_mpc2"])
    np.testing.assert_allclose(result["esd_msun_mpc2"][finite], -4.0e14 / 0.98531)
    np.testing.assert_allclose(result["cross_esd_msun_mpc2"][finite], 0.0, atol=1e-12)


def test_mask_rejection_and_empty_chunk_preserve_shape() -> None:
    lenses = _lens_payload()
    sources = _sources(np.asarray((10.0,)), np.asarray((0.0,)))
    sources["IMAFLAGS_ISO"][0] = 1
    sums, diagnostics = accumulate_source_chunk(
        lenses,
        sources,
        np.full((2, 5), 3.0e15),
        config=StreamingPairConfig(radial_edges_mpc_h70=(0.003, 11.94)),
    )
    assert diagnostics["selected_source_rows"] == 0
    assert sums["pair_count"].shape == (2, 1)
    assert int(np.sum(sums["pair_count"])) == 0
