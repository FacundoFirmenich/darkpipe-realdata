"""Paired spatial jackknife for signal-minus-random KiDS observables.

SPDX-License-Identifier: GPL-3.0-or-later
This is an empirical spatial covariance conditional on the supplied region
map and estimator. It does not certify survey completeness or physical models.
"""
from __future__ import annotations

import hashlib
import json
from typing import Mapping, Sequence

import numpy as np

from .kids_random_control import finalize_random_control


FIELDS = (
    "random_esd_msun_mpc2", "random_cross_esd_msun_mpc2",
    "random_gobs_m_s2", "random_cross_gobs_m_s2",
)


def paired_spatial_jackknife(
    signal_sums: Mapping[str, np.ndarray],
    random_sums: Mapping[str, np.ndarray],
    *,
    signal_region_ids: Sequence[str],
    random_region_ids: Sequence[str],
    region_map_sha256: str,
) -> dict:
    """Delete the same spatial region from both populations in each replicate.

    Inputs use the numeric sufficient-sum schema of reduce_random_pair_batch;
    that arithmetic also applies to signal lenses. Each region must represent
    the same spatial exclusion in both inputs, including any declared source
    deletion policy. An ID/hash alone cannot prove that upstream construction.
    Region-level sums must be produced before opening the corrected RAR.
    """
    sids, rids = tuple(signal_region_ids), tuple(random_region_ids)
    if sids != rids or len(set(sids)) != len(sids) or len(sids) < 3:
        raise ValueError("identical ordered, unique region IDs (at least three) required")
    if len(region_map_sha256) != 64 or any(c not in "0123456789abcdef" for c in region_map_sha256):
        raise ValueError("a SHA-256 binding of the frozen spatial region map is required")
    signal = {k: np.asarray(v) for k, v in signal_sums.items()}
    random = {k: np.asarray(v) for k, v in random_sums.items()}
    if not signal or set(signal) != set(random):
        raise ValueError("signal and random sufficient-sum keys must match")
    shapes = {a.shape for a in (*signal.values(), *random.values())}
    if len(shapes) != 1:
        raise ValueError("signal and random region/bin shapes must match")
    shape = next(iter(shapes))
    if len(shape) != 2 or shape[0] != len(sids) or shape[1] < 1:
        raise ValueError("region sums must have shape (region count, radial bins)")
    if any(not np.issubdtype(a.dtype, np.number) or not np.isfinite(a).all()
           for a in (*signal.values(), *random.values())):
        raise ValueError("sufficient sums must be finite numeric arrays")
    n, bins = shape

    def surfaces(sums):
        totals = {k: a.sum(axis=0) for k, a in sums.items()}
        full = finalize_random_control(totals)
        loo = finalize_random_control({k: totals[k][None, :] - a for k, a in sums.items()})
        return (np.concatenate([full[k] for k in FIELDS]),
                np.concatenate([loo[k] for k in FIELDS], axis=1))

    sfull, srep = surfaces(signal)
    rfull, rrep = surfaces(random)
    # One common support for every block: pairwise deletion can destroy PSD
    # and conceal changes in the region family between covariance entries.
    valid = (np.isfinite(srep).all(axis=0) & np.isfinite(rrep).all(axis=0)
             & np.isfinite(sfull) & np.isfinite(rfull))
    sc = srep[:, valid] - srep[:, valid].mean(axis=0)
    rc = rrep[:, valid] - rrep[:, valid].mean(axis=0)
    dc = sc - rc
    factor = (n - 1) / n
    css, crr, csr = factor * sc.T @ sc, factor * rc.T @ rc, factor * sc.T @ rc
    cdd = factor * dc.T @ dc
    dimension = len(valid)

    def expand(block):
        output = np.full((dimension, dimension), np.nan)
        output[np.ix_(valid, valid)] = block
        return output

    return {
        "schema": "darkpipe.paired-spatial-jackknife.v1",
        "authority": "CONDITIONAL_PAIRED_SPATIAL_COVARIANCE_NO_MODEL_ADJUDICATION",
        "scientific_result": False,
        "region_map_sha256": region_map_sha256,
        "region_ids_sha256": hashlib.sha256(json.dumps(sids, separators=(",", ":")).encode()).hexdigest(),
        "region_count": n, "radial_bins": bins, "field_order": FIELDS,
        "valid_columns": valid, "corrected_values": sfull - rfull,
        "corrected_replicates": srep - rrep,
        "covariance_signal": expand(css), "covariance_random": expand(crr),
        "covariance_signal_random": expand(csr), "covariance_corrected": expand(cdd),
        "maximum_rank": min(n - 1, int(valid.sum())),
        "inverse_covariance_established": False,
        "uncertainty_boundary": "EMPIRICAL_SPATIAL_ONLY_CONDITIONAL_ON_MAP_AND_DELETION_POLICY",
    }
