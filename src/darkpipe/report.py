"""Human-readable bounded run reporting."""
from pathlib import Path
import matplotlib;matplotlib.use("Agg")
import matplotlib.pyplot as plt

def write_figure(frame,output):
    target=Path(output);target.parent.mkdir(parents=True,exist_ok=True);fig,ax=plt.subplots(3,1,figsize=(11,9),sharex=True,constrained_layout=True)
    ax[0].plot(frame.time,frame.geomag_dF_dt_nT_per_min,color="#1f4e79");ax[0].set_ylabel("dF/dt [nT/min]");ax[0].set_title("DarkPipe observed foreground window")
    if "sw_bz" in frame: ax[1].plot(frame.time,frame.sw_bz,color="#9b2226")
    ax[1].set_ylabel("IMF Bz [nT]");ax[2].plot(frame.time,frame.projected_residual_nT_per_min,color="#2a9d8f");ax[2].axhline(0,color="black",lw=.6);ax[2].set_ylabel("projected residual");ax[2].set_xlabel("UTC");fig.savefig(target,dpi=170);plt.close(fig)
def render_markdown(report):
    a=report["analysis"];r=a["residual_diagnostics"];lag=a["bz_to_geomag_lag_scan"]["max_absolute_correlation"];coh=a["bz_to_geomag_coherence"]
    return f"""# DarkPipe live-run report

- Run UTC: {report['run']['finished_at_utc']}
- Station: {report['run']['station']}
- Fully aligned observed rows: {a['aligned_finite_rows']}
- Observed interval: {a['time_start_utc']} to {a['time_stop_utc']}
- Raw acquisition bytes: {report['run']['raw_byte_count']}

## Result

Current official NOAA SWPC and USGS Geomagnetism data were acquired, aligned at one-minute cadence, and four measured solar-wind nuisance channels were projected from the geomagnetic target. Residual spectral and non-Gaussian diagnostics were then calculated.

This is an environmental-foreground characterization receipt. It is **not** evidence for dark matter, a hidden plasma, a topological transient, or instrument sensitivity.

## Observed diagnostics

- Residual skewness: {r['skewness']:.6g}
- Residual excess kurtosis: {r['excess_kurtosis']:.6g}
- D'Agostino-Pearson p-value: {r['normaltest_pvalue']:.6g}
- Robust 3-sigma tail fraction: {r['robust_three_sigma_tail_fraction']:.6g}
- Strongest scanned Bz/geomagnetic correlation: r={lag['correlation']:.6g} at lag={lag['lag_minutes']} min (descriptive, not causal)
- Maximum estimated coherence: {coh['max_coherence']:.6g} at {coh['frequency_at_max_hz']:.6g} Hz

## Evidence boundary

The result is conditional on this short live window, Boulder station, provider products, and current parsers. Multiple-testing control, long-baseline stability, replication, sensor transfer functions, clock uncertainty, injection-recovery calibration and a preregistered detection statistic remain pending. The constant-free Whittle score is an internal baseline diagnostic and is not comparable across differently binned runs without a common likelihood specification.

See manifest.json for exact URLs, retrieval times, byte counts, and SHA-256 hashes.
"""
