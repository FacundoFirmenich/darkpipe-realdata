# DarkPipe 0.4.0 — real-data-first environmental and quantum-sensor validation

DarkPipe preserves byte-level provenance for bounded official observations and applies preregistered diagnostics without promoting residuals or control injections into discovery claims.

Version 0.4 adds an authentic AION differential atom-interferometer evidence track to the 0.3 NOAA–USGS environmental-foreground pipeline.

**Current authority ceiling:** DarkPipe 0.4 establishes a reproducible software-and-instrument validation on selected AION controls. It does not claim detection of dark matter, gravitational waves, hidden plasma or topological transients; it does not establish AION-10/AION-km sensitivity or a blind-search false-positive rate.

## AION 0.4 result

The preregistered campaign `DP-AION-0.4-20260825` was committed before endpoint calculation.

- Integrity/schema gate: 27/27 selected files, 19,018,652 bytes, PASS.
- Injected-frequency recovery: 7/7 within one Fourier-resolution cell, PASS.
- High- versus low-laser-noise consistency: HLN−LLN = 14.2767 µrad, 95% interval [−23.5180, 52.0714] µrad, PASS under the frozen rule.
- Terminal decision: `PASS_BOUNDED`.
- Blind discovery false-positive rate and global new-physics significance: `NOT_ESTIMABLE` from this evidence slice.

Read [the preregistration](docs/PREREGISTRATION_AION_SENSOR_VALIDATION_0.4.md), [scientific scope](docs/SCIENTIFIC_SCOPE.md) and [substantive Spanish closure](docs/CIERRE_SUSTANTIVO_ES_AION_0.4_2026-08-25.md).

## Run the checked AION validation

    python -m pip install -e .
    darkpipe aion-validate \
      --evidence evidence/aion_sensor_validation_2026-08-25 \
      --output darkpipe_aion_run

The command re-hashes all 27 files, validates schemas/mappings, executes the frozen E1/E2 rules and writes `report.json`, `report.md`, `validation.png` and `manifest.json`.

A direct script is also provided:

    python run_darkpipe_aion_v04.py --output darkpipe_aion_run

## Run the live environmental pipeline

    darkpipe run --output darkpipe_run --station BOU

This retains the 0.3 bounded acquisition and analysis path for current NOAA SWPC solar-wind products and USGS Geomagnetism observations, plus generic HAPI adapters for INTERMAGNET and NASA CDAWeb.

Generated run directories are ignored by Git. No daemon or persistent local service is required.

## Colab

Open `notebooks/DarkPipe_AION_v04_Colab.ipynb`. It shallow-clones the public repository, installs the package, runs the AION test module, executes the preregistered validation, renders the checked figure and creates a small ZIP containing only the result receipt.

## Evidence and licensing

The AION subset derives from Charles Baynham and the AION Collaboration, Zenodo DOI [10.5281/zenodo.19592552](https://doi.org/10.5281/zenodo.19592552), associated with [Baynham et al., Nature 654, 622–628 (2026)](https://doi.org/10.1038/s41586-026-10617-1).

Zenodo declares the record `CC-BY-4.0`; the upstream bundle contains an MIT software notice. Both are preserved under `evidence/aion_sensor_validation_2026-08-25/`. DarkPipe’s original code is licensed separately under GNU GPL version 3 or later, SPDX `GPL-3.0-or-later`—explicitly not `GPL-3.0-only`.

## Sources

- AION data/code: https://doi.org/10.5281/zenodo.19592552
- AION article: https://doi.org/10.1038/s41586-026-10617-1
- NOAA SWPC products: https://services.swpc.noaa.gov/products/
- USGS Geomagnetism Web Services: https://geomag.usgs.gov/ws/
- INTERMAGNET HAPI: https://imag-data.bgs.ac.uk/GIN_V1/hapi
- NASA CDAWeb HAPI: https://cdaweb.gsfc.nasa.gov/hapi

## License

DarkPipe original code and derived project documentation are released under GNU GPL version 3 or later (SPDX: `GPL-3.0-or-later`). See `LICENSE` and `LICENSE-NOTICE`. Upstream evidence retains the separate licenses documented in its evidence notice.
