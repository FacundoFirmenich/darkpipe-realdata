# DarkPipe 0.7.0 candidate — continuous AION search with measured environmental controls

DarkPipe acquires bounded official observations, preserves byte-level provenance and runs reproducible environmental and atom-interferometer validation.
Version 0.7 preregisters a development-only continuous scan of authentic AION LLN/HLN control noise,
a frozen-family chronological holdout gate and measured local geomagnetic classification. The v0.7 campaign has not yet been adjudicated.

**Latest adjudicated result:** v0.6.0 `PASS_BOUNDED`. The unchanged null case produced no familywise detections, and all seven 0.60-rad injected cases were identified as the sole detected target at the frozen AION frequency family.

**v0.7 authority ceiling:** at most one single-epoch split-sample sensor candidate
and its measured environmental classification. It cannot establish the
morfo-syntactic-plasma/dark-matter conjecture, causation or physical detection.

## What 0.7 tests

- A 0.1–75 mHz development-only grid at one Rayleigh-cell spacing, with no development significance threshold.
- At most eight separated local maxima, committed before any holdout frequency endpoint is computed.
- Holdout familywise calibration from 4,095 condition-wise circular rotations.
- INTERMAGNET/BGS Hartland one-second XYZF as a measured regional-field control for holdout survivors.
- NASA CDAWeb OMNI one-minute variables as heliospheric context only, never as a causal veto.
- Explicit exclusion of the four development frequencies exposed by pre-freeze engineering equivalence probes and their two-Rayleigh-cell neighborhoods.
- Mandatory `NOT_ESTIMABLE` status for the morfo-syntactic-plasma/dark-matter conjecture and gravitational-wave detection in this campaign.
- The unsearched 75–100 mHz interval remains `NOT_ESTIMABLE` because of the AION development cadence.

Read the [v0.7 preregistration](docs/PREREGISTRATION_AION_CONTINUOUS_ENVIRONMENT_0.7.md). The executable rules and this documentation must be committed before the full continuous scan.

The post-discovery [terminology erratum](docs/TERMINOLOGY_ERRATUM_MORPHOSYNTACTIC_PLASMA_0.7.md) changes no analytical rule and preserves frozen historical wording as provenance.

## What 0.6 established

- Chronological 40/60 development/holdout split on the preserved LLN and HLN controls.
- Fixed nuisance fringe model and paired-arm differential-phase score.
- Familywise calibration from 4,095 condition-wise circular rotations of development residuals.
- SHA-256 commitment to a 256-bit seed before challenge construction.
- Eight opaque cases: one authentic null and seven declared tangent-space phase injections.
- Git chronology: preregistration `dbd2da7`; sealed predictions before reveal `3dd30b6`.
- Typed claim ledger retaining continuous search, physical detection and independent repeated false-positive rate as `NOT_ESTIMABLE`.

Read the [frozen preregistration](docs/PREREGISTRATION_AION_BLIND_HOLDOUT_0.6.md), [scientific scope](docs/SCIENTIFIC_SCOPE.md) and [Spanish substantive closure](docs/CIERRE_SUSTANTIVO_ES_AION_BLIND_0.6_2026-08-25.md).

## Checked result

| Gate | Result |
|---|---|
| Source/sealed integrity | PASS |
| Holdout null | PASS — zero detections, global p = 0.3857421875 |
| Signal identification | PASS — 7/7 |
| Injected-case global p | 0.000244140625 for each |
| Terminal decision | `PASS_BOUNDED` |

The synthetic component is only the explicitly declared first-order differential-phase perturbation. The noise samples, timestamps, phase steps and instrument covariates come from the authentic AION controls.

## Reproduce

    python -m pip install -e .
    python run_darkpipe_aion_blind_v06.py --mode reproduce --campaign darkpipe_aion_blind_reproduction

The staged CLI preserves the blind boundary for a new seed:

    darkpipe aion-blind-prepare --campaign campaign --seed-file private_seed.txt --preregistration-commit <freeze-commit>
    darkpipe aion-blind-analyze --campaign campaign
    darkpipe aion-blind-reveal --campaign campaign --seed-file private_seed.txt

The historical commands remain available:

    darkpipe aion-validate --evidence evidence/aion_sensor_validation_2026-08-25 --output darkpipe_aion_run
    darkpipe run --output darkpipe_run --station BOU

## Colab

Open `notebooks/DarkPipe_AION_Blind_v06_Colab.ipynb`. It installs the tagged release, runs the full suite, reconstructs the sealed challenge from the revealed seed, reproduces the blind predictions and terminal report, and exports a compact ZIP.

## Preserved history and privacy

The v0.4 AION result remains 27/27 integrity, 7/7 published-injection recovery and HLN−LLN consistency under its frozen rule. Version 0.5's authority typing remains intact. Raw native chats remain private; the public trace manifest still records one 20,000-character truncation rather than claiming complete transport.

## Evidence and license

AION evidence: [Zenodo 10.5281/zenodo.19592552](https://doi.org/10.5281/zenodo.19592552), associated with [Baynham et al. (2026)](https://doi.org/10.1038/s41586-026-10617-1). Upstream CC-BY-4.0/MIT jurisdictions remain separate.

DarkPipe code and derived documentation use GNU GPL version 3 or later, SPDX `GPL-3.0-or-later` — explicitly not `GPL-3.0-only`.
