# DarkPipe 0.7.0 — split-sample continuous AION search

DarkPipe acquires bounded official observations, preserves byte-level provenance and runs reproducible environmental and atom-interferometer validation.
Version 0.7 executes a prospectively frozen 0.1–75 mHz development scan and a
chronological holdout gate on authentic AION LLN/HLN control noise.

**Terminal result:** `NO_HOLDOUT_CANDIDATE`. None of the eight development
maxima survived holdout familywise correction.

**v0.7 authority ceiling:** at most one single-epoch split-sample sensor candidate
and its measured environmental classification. It cannot establish the
morphotopological plasma-hyperstate conjecture, causation or physical detection.

## v0.7 checked result

| Gate | Result |
|---|---|
| Development grid | 5,578 frequencies; 0.1–75 mHz |
| Frozen family | 8 maxima; commit `0fa86e0` |
| Holdout | 0/8 confirmed |
| Best holdout candidate | c005 at 47.5447 mHz; p FWER = 0.405517578125 |
| Regional environment | `NOT_APPLICABLE`; no survivor triggered HAPI acquisition |
| Terminal decision | `NO_HOLDOUT_CANDIDATE` |

Protocol facts:

- Grid spacing was one development Rayleigh cell with no development threshold.
- Holdout FWER used 4,095 frozen condition-wise circular rotations.
- The four engineering-probe neighborhoods remained excluded.
- The unsearched 75–100 mHz interval and the morphotopological plasma-hyperstate
  conjecture remain `NOT_ESTIMABLE`.

Read the [v0.7 preregistration](docs/PREREGISTRATION_AION_CONTINUOUS_ENVIRONMENT_0.7.md),
[checked report](evidence/aion_continuous_environment_2026-08-25/report.md) and
[Spanish substantive closure](docs/CIERRE_SUSTANTIVO_ES_AION_CONTINUOUS_0.7_2026-08-25.md).

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

## v0.6 checked result

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
    python run_darkpipe_aion_continuous_v07.py --mode confirm \
      --campaign evidence/aion_continuous_environment_2026-08-25 \
      --candidate-commit 0fa86e0906e613207ba4e69120bcc5fea5bf7949

Because no candidate survived, this reproduction performs no HAPI acquisition.
The historical v0.6 injected-detector replay remains available:

    python run_darkpipe_aion_blind_v06.py --mode reproduce \
      --campaign darkpipe_aion_blind_reproduction

The historical commands remain available:

    darkpipe aion-validate --evidence evidence/aion_sensor_validation_2026-08-25 --output darkpipe_aion_run
    darkpipe run --output darkpipe_run --station BOU

## Colab

Open `notebooks/DarkPipe_AION_Continuous_v07_Colab.ipynb`. It installs the
tagged release, verifies the checked receipt, reproduces the holdout decision and
exports a compact ZIP. The v0.6 notebook remains preserved.

## Preserved history and privacy

The v0.4 AION result remains 27/27 integrity, 7/7 published-injection recovery and HLN−LLN consistency under its frozen rule. Version 0.5's authority typing remains intact. Raw native chats remain private; the public trace manifest still records one 20,000-character truncation rather than claiming complete transport.

## Evidence and license

AION evidence: [Zenodo 10.5281/zenodo.19592552](https://doi.org/10.5281/zenodo.19592552), associated with [Baynham et al. (2026)](https://doi.org/10.1038/s41586-026-10617-1). Upstream CC-BY-4.0/MIT jurisdictions remain separate.

DarkPipe code and derived documentation use GNU GPL version 3 or later, SPDX `GPL-3.0-or-later` — explicitly not `GPL-3.0-only`.
