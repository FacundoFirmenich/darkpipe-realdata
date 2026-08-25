# Scientific scope and claim ledger

## Governing objective

Build a real-data-first, projection-aware pipeline for identifying and characterizing environmental foregrounds relevant to a future search for transient ultralight or topological dark-sector signatures in precision gradiometric data.

## Established in 0.3.0

1. Current official environmental data can be acquired within strict local byte ceilings.
2. Exact transport provenance is retained for every live source response.
3. Solar-wind measurements can be aligned with a terrestrial geomagnetic target and treated explicitly as measured nuisance channels.
4. The residual can be inspected through a colored-noise spectral baseline, a constant-free Whittle score, distributional diagnostics, lag scans and coherence.
5. The workflow runs on ordinary CPU hardware and does not require heavy local storage.

## Not established

- Existence or detection of dark plasma, ultralight fields or topological defects.
- Any mapping from these environmental channels to an atom-interferometer transfer function.
- Facility sensitivity, false-alarm rate, discovery reach or exclusion limits.
- Gaussianity or stationarity outside the observed window.
- Causality from a lag or coherence maximum.
- Generalization across time, observatories or instruments.

## Required next scientific gate

Obtain a real, time-synchronized gradiometer/atom-interferometer channel with its calibration and auxiliary sensors; preregister the physical template family, nuisance hierarchy, quality cuts, blind injections, search band, trials correction and held-out evaluation. Until then DarkPipe is an environmental-foreground engine, not a detection pipeline.
