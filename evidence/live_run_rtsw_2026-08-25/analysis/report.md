# DarkPipe live-run report

- Run UTC: 2026-08-25T05:59:41.770230Z
- Station: BOU
- Fully aligned observed rows: 1433
- Observed interval: 2026-08-24T06:00:00+00:00 to 2026-08-25T05:54:00+00:00
- Raw acquisition bytes: 3747961

## Result

Current official NOAA SWPC and USGS Geomagnetism data were acquired, aligned at one-minute cadence, and four measured solar-wind nuisance channels were projected from the geomagnetic target. Residual spectral and non-Gaussian diagnostics were then calculated.

This is an environmental-foreground characterization receipt. It is **not** evidence for dark matter, a hidden plasma, a topological transient, or instrument sensitivity.

## Observed diagnostics

- Residual skewness: -0.672584
- Residual excess kurtosis: 5.32222
- D'Agostino-Pearson p-value: 7.26351e-58
- Robust 3-sigma tail fraction: 0.038381
- Strongest scanned Bz/geomagnetic correlation: r=-0.135881 at lag=8 min (descriptive, not causal)
- Maximum estimated coherence: 0.417071 at 0.00078125 Hz

## Evidence boundary

The result is conditional on this short live window, Boulder station, provider products, and current parsers. Multiple-testing control, long-baseline stability, replication, sensor transfer functions, clock uncertainty, injection-recovery calibration and a preregistered detection statistic remain pending. The constant-free Whittle score is an internal baseline diagnostic and is not comparable across differently binned runs without a common likelihood specification.

See manifest.json for exact URLs, retrieval times, byte counts, and SHA-256 hashes.
