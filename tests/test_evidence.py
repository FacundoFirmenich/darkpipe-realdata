import json
from pathlib import Path
import numpy as np
import pandas as pd
from darkpipe.analysis import projection_aware_diagnostics
from darkpipe.provenance import sha256_file
from darkpipe.sources import parse_hapi,parse_usgs_geomag

ROOT=Path(__file__).parents[1]
LIVE=ROOT/"evidence"/"live_run_rtsw_2026-08-25"

def test_live_manifest_hashes_every_artifact():
    manifest=json.loads((LIVE/"manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["files"])==9
    for item in manifest["files"]:
        path=LIVE/item["path"]
        assert path.stat().st_size==item["byte_count"]
        assert sha256_file(path)==item["sha256"]

def test_usgs_raw_receipt_has_real_finite_values():
    payload=json.loads((LIVE/"raw"/"usgs_geomag.json").read_text(encoding="utf-8"))
    frame=parse_usgs_geomag(payload)
    assert len(frame)>=1400
    assert frame[["X","Y","Z","F"]].notna().all(axis=1).sum()>=1400

def test_reanalysis_reproduces_checked_in_receipt():
    frame=pd.read_csv(LIVE/"data"/"aligned_observations.csv",parse_dates=["time"])
    observed=json.loads((LIVE/"analysis"/"report.json").read_text(encoding="utf-8"))["analysis"]
    repeated,_=projection_aware_diagnostics(frame)
    assert repeated["aligned_finite_rows"]==observed["aligned_finite_rows"]
    for key in ("skewness","excess_kurtosis","normaltest_pvalue","robust_three_sigma_tail_fraction"):
        assert np.isclose(repeated["residual_diagnostics"][key],observed["residual_diagnostics"][key],rtol=1e-10,atol=1e-12)

def test_claim_ceiling_is_explicit():
    report=json.loads((LIVE/"analysis"/"report.json").read_text(encoding="utf-8"))
    assert "not a dark-sector detection test" in report["analysis"]["jurisdiction"]

def test_intermagnet_hapi_receipt_parses_from_info_plus_data():
    probe=ROOT/"evidence"/"hapi_intermagnet_probe_2026-08-25"
    info=json.loads((probe/"info.json").read_text(encoding="utf-8"))
    data=json.loads((probe/"data.json").read_text(encoding="utf-8"))
    data["parameters"]=info["parameters"]
    frame=parse_hapi(data)
    assert len(frame)==60
    assert {"time","Field_Vector_0","Field_Vector_1","Field_Vector_2","Field_Magnitude"}.issubset(frame.columns)
