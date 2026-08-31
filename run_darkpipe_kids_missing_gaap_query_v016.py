#!/usr/bin/env python3
"""Query complete native GAAP rows for the residual unmatched KiDS lenses."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests


def sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=Path, default=Path("evidence/kids_native_lens_v016_lt21/unmatched_hybrid_selected_rows.npy"))
    parser.add_argument("--cache", type=Path, default=Path("evidence/kids_native_lens_v016/lens_catalogue_cache.npz"))
    parser.add_argument("--output", type=Path, default=Path("evidence/kids_native_lens_v016_lt21/missing_native_gaap_tap.fits"))
    args = parser.parse_args()
    rows = np.load(args.rows).astype(int)
    with np.load(args.cache, allow_pickle=False) as cache:
        ra = np.asarray(cache["RAJ2000"], dtype=float)[rows]
        dec = np.asarray(cache["DECJ2000"], dtype=float)[rows]
    radius_deg = 0.5 / 3600.0
    clauses = [
        f"(RAJ2000 BETWEEN {right_ascension-radius_deg:.10f} AND {right_ascension+radius_deg:.10f} "
        f"AND DECJ2000 BETWEEN {declination-radius_deg:.10f} AND {declination+radius_deg:.10f})"
        for right_ascension, declination in zip(ra, dec, strict=True)
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    responses = []
    query_hashes = []
    session = requests.Session()
    session.headers.update({"User-Agent": "DarkPipe/0.16 residual-KiDS-GAAP-recovery"})
    for batch_index, start in enumerate(range(0, len(clauses), 5)):
        query = (
            "SELECT RAJ2000,DECJ2000,MAG_GAAP_u,MAG_GAAP_r,MAG_AUTO "
            "FROM KiDS_DR4_0_ugriZYJHKs_cat_fits_V3 WHERE "
            + " OR ".join(clauses[start : start + 5])
        )
        response = session.post(
            "https://archive.eso.org/tap_cat/sync",
            data={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "fits", "MAXREC": "100", "QUERY": query},
            timeout=(30, 600),
        )
        response.raise_for_status()
        if not response.content.startswith(b"SIMPLE"):
            raise RuntimeError(response.text[:2000])
        part = args.output.with_name(f"{args.output.stem}_part{batch_index:02d}.fits")
        part.write_bytes(response.content)
        query_hashes.append(hashlib.sha256(query.encode("utf-8")).hexdigest())
        responses.append({"path": part.as_posix(), "bytes": part.stat().st_size, "sha256": sha256(part)})
    session.close()
    receipt = {
        "schema": "darkpipe.kids-missing-gaap-query.v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "requested_lens_rows": int(len(rows)),
        "cone_radius_arcsec": 0.5,
        "query_sha256_by_part": query_hashes,
        "responses": responses,
        "source": "ESO_PUBLIC_TAP_KIDS_DR4_V3",
        "authority": "RESIDUAL_NATIVE_PHOTOMETRY_RECOVERY_ONLY",
    }
    receipt_path = args.output.with_suffix(".receipt.json")
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
