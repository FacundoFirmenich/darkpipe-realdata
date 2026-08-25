# DarkPipe 0.5.0 — authority-typed real-data validation

DarkPipe acquires bounded official observations, preserves byte-level provenance and runs reproducible environmental and atom-interferometer validation. Version 0.5 adds an executable observational-authority layer: observations, associations, causal claims, detections, generalizations and interventions are different types and cannot be promoted by adjacency or rhetoric.

**Authority ceiling:** DarkPipe establishes reproducible software, transport and selected instrument-control results. It does not claim dark matter, gravitational waves, hidden plasma or topological transients; AION-10/AION-km sensitivity; a blind-search false-positive rate; or causation from lag/coherence.

## What 0.5 changes

- `ObservationEnvelope` declares source, observable, time basis, scale, layer, resolution, preprocessing and provenance.
- `ObservedDecoupling` records a difference without fields for cause, duration, meaning, intent or provisionality.
- `ClaimLedger` separates `OBSERVATION`, `ASSOCIATION`, `CAUSAL`, `DETECTION`, `GENERALIZATION` and `INTERVENTION`.
- Observational receipts can promote only observations and associations. Higher-authority claims remain `NOT_ESTIMABLE` with explicit blockers.
- `ConducenceVector` preserves contextual per-axis outcomes; scalar collapse raises an error.
- New evidence is future-only: it does not rewrite the adjudicated v0.4 receipt.

Read [the authority contract](docs/OBSERVATIONAL_AUTHORITY_0.5.md), [scientific scope](docs/SCIENTIFIC_SCOPE.md) and [Spanish substantive closure](docs/CIERRE_SUSTANTIVO_ES_0.5_2026-08-25.md).

## Preserved AION result

Campaign `DP-AION-0.4-20260825` remains unchanged:

- 27/27 selected files pass integrity/schema.
- Injected-frequency recovery is 7/7 within one Fourier cell.
- HLN−LLN = 14.2767 µrad; frozen 95% interval [−23.5180, 52.0714] µrad.
- Decision: `PASS_BOUNDED`.
- Blind significance and facility transfer: `NOT_ESTIMABLE`.

Version 0.5 reproduces the endpoint values exactly and adds a separate authority receipt. An interval including zero is observed consistency under the frozen rule, not causal equivalence.

## Run

    python -m pip install -e .
    darkpipe aion-validate --evidence evidence/aion_sensor_validation_2026-08-25 --output darkpipe_aion_run
    darkpipe run --output darkpipe_run --station BOU

The live path acquires NOAA SWPC and USGS Geomagnetism observations, aligns them, projects declared nuisance channels and calculates residual diagnostics. Correlation and coherence remain descriptive.

## Colab

Open `notebooks/DarkPipe_Authority_v05_Colab.ipynb`. It installs the package, runs all tests, reproduces AION, verifies typed claims and creates a compact result ZIP. The v0.4 notebook remains as historical workflow.

## Genealogy and privacy

Two adjacent native threads were read to EOF as genealogical/correction sources. Raw pages remain private and ignored by Git. `evidence/native_thread_trace_manifest.json` contains hashes, counts and one adverse record: one early assistant message was cut at 20,000 characters. The transport is therefore not called complete.

## Evidence and license

AION evidence: [Zenodo 10.5281/zenodo.19592552](https://doi.org/10.5281/zenodo.19592552), associated with [Baynham et al. (2026)](https://doi.org/10.1038/s41586-026-10617-1). Upstream CC-BY-4.0/MIT jurisdictions remain separate.

DarkPipe code and derived documentation use GNU GPL version 3 or later, SPDX `GPL-3.0-or-later` — explicitly not `GPL-3.0-only`.
