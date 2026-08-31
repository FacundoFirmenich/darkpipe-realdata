#!/usr/bin/env python3
"""Emit residual unmatched bright rows after primary plus supplemental TAP data."""

from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from run_darkpipe_kids_native_lens_v016 import decode_local_fits, unit_xyz


def main() -> int:
    primary, _, _ = decode_local_fits(Path("evidence/kids_eso_tap_gaap_bright_lt21.fits"))
    supplements = [decode_local_fits(path)[0] for path in sorted(Path().glob("evidence/kids_native_lens_v016_lt21/missing_native_gaap_tap_part*.fits"))]
    tap = {name: np.concatenate([primary[name]] + [item[name] for item in supplements]) for name in primary}
    with np.load("evidence/kids_native_lens_v016/lens_catalogue_cache.npz", allow_pickle=False) as cache:
        lens_xyz = unit_xyz(cache["RAJ2000"], cache["DECJ2000"])
    tree = cKDTree(unit_xyz(tap["RAJ2000"], tap["DECJ2000"]))
    chord = 2.0 * np.sin(np.deg2rad(0.5 / 3600.0) / 2.0)
    distance, index = tree.query(lens_xyz, k=1, distance_upper_bound=chord, workers=-1)
    matched = np.isfinite(distance) & (index < len(tap["RAJ2000"]))
    output = Path("evidence/kids_native_lens_v016_final/unmatched_rows.npy")
    np.save(output, np.flatnonzero(~matched).astype(np.int32))
    print(f"matched={np.count_nonzero(matched)} unmatched={np.count_nonzero(~matched)} path={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
