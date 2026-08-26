# DarkPipe 0.10.0 — observable shadows and conditional inobservables

DarkPipe now implements the governing chain `real observables -> signed shadow
-> conditional derived inobservables`. Version 0.10 uses SPARC rotation curves
and separate gas, disk and bulge mass-model projections. The design was
preregistered and merged before the only official inferential run.

**Terminal result:** `DERIVED_CONDITIONAL_INOBSERVABLE_PROFILES_AVAILABLE`.
The checked result contains 2,700 radial profiles across 149 galaxies: 1,917
positive at 95%, 775 sign-ambiguous and 8 negative at 95%.

**v0.10 authority ceiling:** signed spherical-equivalent effective acceleration
and enclosed-mass discrepancy profiles, conditional on circular Newtonian
mapping and the declared nuisance model. This is not a particle detection,
three-dimensional density, MOND/Lambda-CDM adjudication, gravity mechanism or
validation of the morphotopological plasma-hyperstate conjecture.

## v0.10 checked result

| Gate | Result |
|---|---|
| Source | SPARC; 175 galaxies; CC-BY-4.0 |
| Frozen selection | 149 galaxies; 2,700 of 3,391 radii |
| Positive signed profile at 95% | 1,917 radii |
| Sign ambiguous at 95% | 775 radii |
| Negative signed profile at 95% | 8 radii in 4 galaxies |
| Galaxies with at least one positive radius | 145 of 149 |
| Outermost selected radius | 144 positive; 5 ambiguous; 0 negative |
| Terminal decision | `DERIVED_CONDITIONAL_INOBSERVABLE_PROFILES_AVAILABLE` |

The pointwise states are not independent because radii share galaxy-level
distance, inclination and mass-to-light draws. Adverse and ambiguous profiles
are retained. Raw SPARC tables were hash-verified in ephemeral storage and
removed; only compact derived evidence is redistributed.

Read the [preregistration](docs/PREREGISTRATION_OBSERVABLE_SHADOW_INOBSERVABLE_0.10.md),
[deep-research selection](docs/DEEP_RESEARCH_V010_SHADOW_INOBSERVABLE_SELECTION_2026-08-26.md),
[checked summary](evidence/v010_shadow_inobservable/inobservable_summary.json),
[derived profiles](evidence/v010_shadow_inobservable/derived_inobservable_profiles.csv)
and [substantive Spanish adjudication](docs/V010_SUBSTANTIVE_ADJUDICATION_ES_2026-08-26.md).

The official run was executed once from merged commit
`4819501a0b10709f6128cbd992ad2e9fac830359` as GitHub Actions run
`32975513896`; do not relabel reproductions as the historical run.

## What 0.9 established

### DarkPipe 0.9.0 — independent GPS clock-network transient search

DarkPipe acquires bounded official observations, preserves provenance and runs
reproducible environmental, atom-interferometer and clock-network validation.
Version 0.9 tests one frozen AION-genealogical UTC window with a genuinely
independent sensor family: JPL Final high-rate GPS clock and orbit products.

**Terminal result:** `NO_GPS_NETWORK_TRANSIENT_CANDIDATE`. The largest coherent
GPS-network statistic was not exceptional against authentic daily background
maxima: exact familywise rank p = 0.3023255813953488.

**v0.9 authority ceiling:** a candidate/no-candidate decision for a propagating
transient under the frozen GPS operator, velocity bank and UTC window. It is
not a physical exclusion and cannot establish or refute dark matter, a gravity
mechanism or the morphotopological plasma-hyperstate conjecture.

## v0.9 checked result

| Gate | Result |
|---|---|
| Source | JPL Final high-rate clocks and orbits; 30 s cadence |
| Calibrated network | 22 GPS nodes; Ledoit-Wolf coherent combination |
| Authentic null | 42 daily background maxima |
| Frozen search | 2 target parts x centers x signs x 256 velocity templates |
| Power gate at 8 sigma | 120/128 joint detections; Wilson lower 0.881512 |
| Adverse power at 4 sigma | 38/128; Wilson lower 0.224582 |
| Target maximum | 7.6678744897237845 at 2024-12-14T00:20:42Z |
| Exact corrected p | 0.3023255813953488 |
| Terminal decision | `NO_GPS_NETWORK_TRANSIENT_CANDIDATE` |

Protocol facts:

- Node selection, covariance, 42 null maxima and power were frozen before the
  target was opened.
- The target was opened exactly once after the 8-sigma power gate passed; it
  was not relaunched, retuned or recycled.
- Target multiplicity is internal to each daily maximum, so the rank p covers
  both target parts, all centers, signs and velocity templates.
- The only synthetic component is the explicitly declared power injection;
  calibration and target backgrounds are authentic JPL observations.
- Raw JPL bytes were verified in ephemeral GitHub storage and are not
  redistributed or retained locally.
- Poor 4-sigma power prevents a strong physical exclusion despite the clear
  detector-level null.

Read the [v0.9 preregistration](docs/PREREGISTRATION_GPS_NETWORK_TRANSIENT_0.9.md),
[checked result](evidence/gps_network_v09/target_result.json),
[deep-research sensor selection](docs/DEEP_RESEARCH_V09_INDEPENDENT_SENSOR_SELECTION_2026-08-25.md)
and [Spanish substantive closure](docs/V09_SUBSTANTIVE_CLOSURE_ES_2026-08-26.md).

## Inspect without reopening the target

The historical target has a one-launch/no-relaunch constraint. Inspect its
checked receipt instead of reopening it:

```python
import json
from pathlib import Path
result = json.loads(
    Path("evidence/gps_network_v09/target_result.json").read_text()
)
print(result["decision"], result["exact_familywise_rank_p"])
```

The calibration operator remains executable on ephemeral storage through
`.github/workflows/v09-calibrate.yml`.

## v0.9 Colab

Open `notebooks/DarkPipe_GPS_Network_v09_Colab.ipynb`. It installs the tagged
release, verifies and explains the checked target receipt, checks calibration
power and exports only a compact result ZIP. It deliberately does not relaunch
the historical target.

## v0.9 source jurisdiction

The data source is the
[JPL GNSS Final-products archive](https://sideshow.jpl.nasa.gov/pub/JPL_GNSS_Products/README/).
JPL makes these products available for research and education; DarkPipe
preserves source links and cryptographic receipts without redistributing raw
products. Earlier AION sources remain under their own separate license and
evidential jurisdictions.

## What 0.8 established
### DarkPipe 0.8.0 — independent-epoch AION holdout

DarkPipe acquires bounded official observations, preserves provenance and runs
reproducible environmental and atom-interferometer validation. Version 0.8 adds
a historical AION acquisition epoch from 2024-12-13, independent in time from
the v0.7 epoch but belonging to the same instrument family.

**Terminal result:** `NO_INDEPENDENT_HOLDOUT_CANDIDATE`. None of eight
development maxima survived the frozen holdout familywise gate.

**v0.8 authority ceiling:** a split-sample sensor result in a second temporal
epoch. It is not an independent-instrument replication and cannot establish a
physical exclusion, dark-matter detection, gravity mechanism or the
morphotopological plasma-hyperstate conjecture.

## v0.8 checked result

| Gate | Result |
|---|---|
| Source | AION RID34056; 22,839 rows; 564,439,752 bytes |
| Development grid | 2,007 frequencies; 0.112–74.987 mHz |
| Frozen family | 8 maxima; commit `7b5052a` |
| Holdout | 0/8 confirmed |
| Smallest corrected p | c007 at 16.5725 mHz; p FWER = 0.837890625 |
| Maximum declared calibration power | 0.4375 |
| Terminal decision | `NO_INDEPENDENT_HOLDOUT_CANDIDATE` |

Protocol facts:

- Discovery used only the first 40% per condition; holdout excitation values
  were not accessed before the candidate family was committed.
- Holdout FWER used 4,095 fixed condition-wise circular rotations.
- Raw HDF5 bytes were verified and removed in ephemeral GitHub storage.
- No raw or row-level source data are redistributed because the Zenodo v1
  record exposes no machine-readable reuse license.
- Low and heterogeneous calibration power prevents a strong physical exclusion.

Read the [v0.8 preregistration](docs/PREREGISTRATION_AION_INDEPENDENT_EPOCH_0.8.md),
[checked report](evidence/aion_independent_epoch_2026-08-25/report.json) and
[Spanish substantive closure](docs/CIERRE_SUSTANTIVO_ES_AION_INDEPENDENT_0.8_2026-08-25.md).

## What 0.7 established

Version 0.7 froze a continuous 0.1–75 mHz scan on the 2025 AION family and
recorded `NO_HOLDOUT_CANDIDATE` with 0/8 confirmations. Its terminology
erratum and all historical bytes remain preserved as provenance.

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
    python run_darkpipe_aion_independent_search_v08.py --mode confirm \
      --output darkpipe_v08_reproduction \
      --scratch /temporary/darkpipe-v08 \
      --discovery evidence/aion_independent_epoch_2026-08-25/discovery.json \
      --candidate-commit 2b4eba96bd813effcd6c4c0e0f165950b5a492ea

This downloads the 564 MB source, verifies it and removes it in `finally`.
Use ephemeral scratch storage. The historical v0.7 replay remains available:

    python run_darkpipe_aion_continuous_v07.py --mode confirm \
      --campaign evidence/aion_continuous_environment_2026-08-25 \
      --candidate-commit 0fa86e0906e613207ba4e69120bcc5fea5bf7949

The historical commands remain available:

    python run_darkpipe_aion_blind_v06.py --mode reproduce \
      --campaign darkpipe_aion_blind_reproduction
    darkpipe aion-validate --evidence evidence/aion_sensor_validation_2026-08-25 --output darkpipe_aion_run
    darkpipe run --output darkpipe_run --station BOU

## Colab

Open `notebooks/DarkPipe_AION_Independent_v08_Colab.ipynb`. It installs the
tagged release, verifies the checked receipt, reproduces the holdout in Colab
ephemeral storage and exports only a compact result ZIP.

## Preserved history and privacy

The v0.4 AION result remains 27/27 integrity, 7/7 published-injection recovery and HLN−LLN consistency under its frozen rule. Version 0.5's authority typing remains intact. Raw native chats remain private; the public trace manifest still records one 20,000-character truncation rather than claiming complete transport.

## Evidence and license

The v0.8 source is
[AION v1 RID34056](https://zenodo.org/records/15166670). Its source links,
metadata and hashes are preserved, but its raw/row-level bytes are not
redistributed because the record exposes no machine-readable reuse license.
The current AION v2 evidence remains separately cited under its own jurisdiction.

DarkPipe code and derived documentation use GNU GPL version 3 or later,
SPDX `GPL-3.0-or-later` — explicitly not `GPL-3.0-only`.
