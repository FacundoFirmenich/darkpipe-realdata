# DarkPipe 0.3.0 — real-data-first foreground pipeline

DarkPipe acquires current official heliospheric and geomagnetic observations, preserves byte-level provenance, aligns measured channels, projects environmental nuisance variables from a geomagnetic target, and calculates spectral, Whittle-baseline, lag, coherence and non-Gaussian residual diagnostics.

**Current authority ceiling:** this release proves an operational, lightweight real-data foreground workflow. It does not claim detection of dark matter, hidden plasma, topological transients, or sensitivity of an atom-interferometer facility.

## What is deployed

- NOAA SWPC real-time solar-wind magnetic and plasma products (RTSW), one-minute cadence over a bounded 24-hour analysis window.
- USGS Geomagnetism adjusted Boulder (BOU) XYZF observations over the matching interval.
- Optional generic HAPI acquisition for INTERMAGNET and NASA CDAWeb.
- Raw JSON receipts, retrieval timestamps, resolved URLs, byte counts and SHA-256 hashes.
- One-minute time alignment, environmental nuisance projection, Welch spectrum, constant-free Whittle baseline score, residual diagnostics, lag scan and coherence.
- A command-line application, Colab notebook, offline tests and GitHub Actions.

## Run locally

    python -m pip install -e .
    darkpipe run --output darkpipe_run --station BOU

The default live run downloads only a few kilobytes. Every response is protected by a hard byte ceiling (1–10 MB depending on source). Generated run directories are ignored by Git and should be moved to external custody or deleted manually after verification when local space matters.

## Colab

Open notebooks/DarkPipe_RealData_v03_Colab.ipynb and execute from top to bottom. It installs this public repository, runs the live pipeline, renders the report and prepares a ZIP containing the bounded receipt.

## Scientific interpretation

The default target is the first difference of the observed geomagnetic field magnitude F. Measured solar-wind Bz, total field, speed and density are standardized and projected as nuisance channels. Diagnostics of the remaining residual are descriptive and conditional on a short window. A residual is not automatically signal; non-Gaussianity is not automatically new physics; a lagged association is not causality.

Before any detection claim, DarkPipe still requires a preregistered sensor-level likelihood, real facility data, transfer functions, clock/systematics models, blind injection-recovery, long-baseline and multi-site replication, multiple-testing control, and held-out validation.

## Sources

- NOAA SWPC current products: https://services.swpc.noaa.gov/products/
- USGS Geomagnetism Web Services: https://geomag.usgs.gov/ws/
- INTERMAGNET HAPI: https://imag-data.bgs.ac.uk/GIN_V1/hapi
- NASA CDAWeb HAPI: https://cdaweb.gsfc.nasa.gov/hapi
- USGS ComCat interface (supported adapter constant; not part of the default run): https://earthquake.usgs.gov/fdsnws/event/1/

See docs/SCIENTIFIC_SCOPE.md, docs/SOURCE_ENDPOINTS.md, docs/ARCHAEOLOGY_AND_CUSTODY.md, SECURITY.md and the latest release receipt under evidence/.

## License

DarkPipe is released under GNU GPL version 3 or later (SPDX: GPL-3.0-or-later). See LICENSE and LICENSE-NOTICE.