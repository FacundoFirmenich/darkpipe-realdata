# Changelog

## 0.16.0 - KiDS object-level reconstruction and RAR shadow

- added a bounded-memory HTTP-range FITS binary-table reader;
- bound the 17.7 GB KiDS SOM-gold catalogue to 185 contiguous Drive range
  receipts without materializing the complete file locally;
- reconstructed and audited the public KiDS-bright/LePhare lens-side tables;
- preserved the adverse first lens-count mismatch and then closed its successor
  gate from native KiDS DR4 GAAP photometry obtained through the official ESO
  TAP service: all 1,239,422 bright rows matched and the legacy
  angular-diameter Cartesian isolation implementation reproduced exactly
  106,843 lenses, with zero fallback and no threshold tuning;
- derived the bin-level effective inobservable `eta=log10(g_obs/g_bar)` from
  the published Mistele et al. RAR, while withholding ontology and global model
  significance in the absence of the cross-bin covariance;
- completed a restartable full-source selection audit over all 21,262,011 rows,
  retaining 19,109,925 after the published quality and finite-weight gates;
- ingested the five official SOM `n(z)` tables and implemented the Mistele et
  al. Eq. 10 effective critical-density integration, with explicit lens photo-z
  uncertainty and source-tail renormalization.
## 0.11.0 - unreleased

- Selected the Mistele et al. 2024 KiDS weak-lensing RAR as a genuinely distinct galaxy-scale observational channel through a primary-source deep-research comparison.
- Added a CC BY 4.0 attributed machine-readable transcription of the 15 published Table 1 bins; no raw KiDS survey data are redistributed.
- Frozen a signed population-level acceleration discrepancy and logarithmic excess operator with explicit statistical, deprojection and stellar-mass sensitivity terms.
- Typed the four bins below log10(g_bar) = -14 as LOW_ACCELERATION_TAIL_SYSTEMATICS_DOMINANT rather than suppressing them.
- Added a galaxy-equal-weight descriptive overlap atlas against the immutable v0.10 SPARC surface.
- Prohibited object-level fusion, joint likelihood, independent-confirmation language, model adjudication and ontological promotion.
- Deferred the compact CLASH cluster profiles because their public files do not supply the radial baryonic profile required for a non-fabricated radial residual.
- Preserved GNU GPL version 3 or later (GPL-3.0-or-later), never GPL-3.0-only.
## 0.10.0 - 2026-08-26

- Corrected the governing mission to `observables -> shadows -> derived inobservables`; v0.9 remains a valid but peripheral detector-level null.
- Selected the SPARC rotation-curve and baryonic mass-model tables as the first real, compact and auditable shadow family.
- Preregistered source hashes, cuts, nuisance priors, 4,096 draws, seed `20260826010`, signed adverse preservation and a non-ontologizing authority ceiling in commit `5372d5f` before inference.
- Executed the official campaign exactly once from merged commit `4819501a0b10709f6128cbd992ad2e9fac830359` in GitHub Actions run `32975513896`; no relaunch or retuning occurred.
- Derived 2,700 finite, unique radial inobservable profiles across 149 galaxies from 3,391 source radii.
- Recorded 1,917 positive, 775 sign-ambiguous and 8 negative profiles at 95%; preserved all adverse and ambiguous cases.
- Found at least one positive supported radius in 145/149 galaxies and positive support at the outermost selected radius in 144/149, with the remaining 5 ambiguous.
- Kept particle identity, 3D density, MOND/Lambda-CDM adjudication, gravity mechanism, plasma-hyperstate ontology and full factometric/topological channels as `NOT_ESTIMABLE`.
- Retained only compact derived evidence; verified and deleted raw CC-BY-4.0 SPARC tables from ephemeral storage.
- Preserved GNU GPL version 3 or later (`GPL-3.0-or-later`), never `GPL-3.0-only`.
## 0.9.0 - 2026-08-26

- Selected native JPL Final high-rate GPS clock and orbit products through a primary-source deep-research comparison with combined IGS clocks, GNOME magnetometers and contextual geomagnetic/solar-wind networks.
- Preregistered `DP-GPS-NETWORK-TRANSIENT-0.9-20260825` before target access: 22 coverage-qualified nodes, 42 authentic daily null maxima, robust location/scale, Ledoit-Wolf covariance and 256 scrambled-Sobol velocity templates.
- Corrected the JPL GPS-time origin, product-name asymmetry and HTTP user-agent/retry behavior before freeze; excluded the structurally opened 2024-12-12 smoke day from the prospective null.
- Passed the target-opening power gate at 8 sigma with 120/128 jointly detected and localized injections and a 95% Wilson lower bound of 0.8815120889557413.
- Preserved adverse sensitivity at 4 sigma: 38/128 joint successes and Wilson lower bound 0.2245816608356667, prohibiting a strong physical exclusion.
- Opened the frozen target exactly once from merged commit `45cfe3108b2588c97167d5ee4cbaa7d93c10773f`; no relaunch, retuning or target recycling occurred.
- Recorded `NO_GPS_NETWORK_TRANSIENT_CANDIDATE`: target maximum 7.6678744897237845 and exact familywise rank p 0.3023255813953488 against 42 authentic daily maxima.
- Kept dark matter, plasma hyperstates, gravity mechanism, physical coupling/exclusion limits and cross-instrument confirmation of AION as `NOT_ESTIMABLE`.
- Added exact compact calibration/target receipts, Spanish substantive closure and a Colab that verifies the frozen result without reopening the target.
- Preserved GNU GPL version 3 or later (`GPL-3.0-or-later`), never `GPL-3.0-only`.


## 0.8.0 — 2026-08-25

- Added a second, historically independent AION acquisition epoch from RID34056 (2024-12-13), explicitly treated as the same instrument family rather than an independent instrument.
- Inventoried the 564,439,752-byte HDF5 source without endpoint access, verified MD5 and SHA-256, and deleted raw bytes from every ephemeral runner before artifact upload.
- Preregistered a chronological 40/60 development/holdout split, fixed nuisance model, adaptive 0.112–74.987 mHz grid, maximum family of eight separated development maxima and 4,095-rotation holdout FWER gate.
- Preserved the source's missing machine-readable reuse license by publishing links, metadata, hashes and derived aggregate results only; no raw or row-level upstream data are redistributed.
- Recorded adverse development sensitivity: maximum declared fixed-family injected-signal detection power was 0.4375, so a null result cannot support a strong physical exclusion.
- Frozen candidate family commit: `7b5052a0f8534a258413eb06fe58e2f846d6c5e5`; confirmation was executed once from merged commit `2b4eba96bd813effcd6c4c0e0f165950b5a492ea`.
- Recorded `NO_INDEPENDENT_HOLDOUT_CANDIDATE`: 0/8 development maxima survived holdout FWER; all corrected p-values were between 0.837890625 and 1.0.
- Kept false-positive rate across only two epochs, independent-instrument transfer, continuous-search physical power, physical coupling/exclusion, dark-matter or gravitational-wave detection, and the morphotopological plasma-hyperstate conjecture as `NOT_ESTIMABLE`.
- Added checked compact evidence, a full reproduction test, Spanish substantive closure and a Colab workflow that uses ephemeral raw storage and exports only compact results.
- Preserved GNU GPL version 3 or later (`GPL-3.0-or-later`), never `GPL-3.0-only`.
## 0.7.0 — 2026-08-25

- Added a development-only 0.1–75 mHz continuous scan at one Rayleigh-cell spacing and a maximum frozen family of eight separated local maxima.
- Added chronological holdout confirmation with 4,095 condition-wise circular rotations and familywise alpha 0.05.
- Added measured INTERMAGNET/BGS Hartland one-second environmental classification and NASA CDAWeb OMNI one-minute context for holdout survivors.
- Preserved the first failed engineering equivalence probe, repaired the time-origin defect and excluded all four exposed development frequencies plus two-Rayleigh-cell neighborhoods.
- Kept the morphotopological plasma-hyperstate conjecture, gravitational-wave detection, causal coupling and independent-epoch false-positive rate as `NOT_ESTIMABLE` by construction.
- Reduced the upper bound from 100 to 75 mHz before freeze after cadence checks put the lower nominal median Nyquist at 79.056 mHz; 75–100 mHz remains `NOT_ESTIMABLE`.
- Split compact adjudication artifacts from potentially large raw environmental receipts so heavy HAPI evidence can remain in cloud custody.
- Recorded `NO_HOLDOUT_CANDIDATE`: 0/8 frozen development maxima passed holdout FWER.
- The smallest holdout p FWER was 0.405517578125 for c005 at 47.5447 mHz.
- Kept Hartland and OMNI `NOT_APPLICABLE`; no survivor triggered HAPI acquisition.
- Preserved the adverse result without retuning or recycling the holdout.
- Added a post-discovery terminology erratum without changing any frozen analytical rule; historical bytes retain their original wording as provenance.

## 0.6.0 — 2026-08-25

- Froze seed-committed campaign `DP-AION-BLIND-0.6-20260825` in commit `dbd2da7` before challenge construction.
- Split authentic LLN/HLN controls 40/60 into development and holdout after stable timestamp ordering while preserving raw reversals.
- Added a fixed seven-frequency differential-phase score detector and 4,095-rotation familywise null calibration.
- Sealed eight opaque cases and committed blind predictions in `3dd30b6` before seed reveal.
- Recorded `PASS_BOUNDED`: null 0/7 detections and signal identification 7/7, with each injected-case global p equal to 1/4096.
- Preserved independent repeated false-positive rate, continuous-band search, nonlinear likelihood equivalence and physical detection as `NOT_ESTIMABLE`.
- Added staged CLI, direct reproduction script, Colab, complete reproduction tests and substantive Spanish closure.
- Preserved GNU GPL version 3 or later (`GPL-3.0-or-later`), never `GPL-3.0-only`.

## 0.5.0 — 2026-08-25

- Added typed `ObservationEnvelope`, `ObservedDecoupling`, `ClaimLedger` and contextual `ConducenceVector` primitives.
- Prohibited automatic promotion from observational receipts to causal, detection, generalization or intervention claims.
- Added authority receipts to new AION and NOAA-USGS runs while preserving frozen v0.4 endpoint values.
- Replaced the invalid native-thread manifest (`undefined`) with valid public-safe JSON containing hashes, counts, privacy policy and one explicit 20,000-character truncation.
- Kept raw native conversation pages and adjacent attachments out of the public repository.
- Added integration tests, authority contract, v0.5 Colab and substantive Spanish closure.
- Preserved GNU GPL version 3 or later (`GPL-3.0-or-later`), never `GPL-3.0-only`.

## 0.4.0 — 2026-08-25

- Added a bounded 27-file AION differential atom-interferometer evidence slice with byte-level hashes, record metadata, attribution and explicit CC-BY-4.0/MIT/GPL jurisdiction boundaries.
- Froze preregistration `DP-AION-0.4-20260825` in commit `f2da008` before endpoint computation.
- Added exact integrity/schema abstention, seven-frequency injection recovery and HLN–LLN differential-noise consistency endpoints.
- Recorded terminal `PASS_BOUNDED`: Gate 0 PASS, E1 7/7 PASS and E2 PASS; preserved blind-search and facility-transfer quantities as `NOT_ESTIMABLE`.
- Added the `darkpipe aion-validate` command, direct 0.4 script, Colab notebook, checked receipt/figure and five AION tests.
- Preserved adverse engineering evidence: Windows long-path omission, comment-prefixed CSV parse failures, several timestamp reversals and one initially over-literal license test.
## 0.3.0 — 2026-08-25

- Reconstructed the DarkPipe objective from the native 59-turn conversation to EOF.
- Replaced two retired NOAA v0.2 endpoints with the current propagated-solar-wind product.
- Added bounded NOAA, USGS and HAPI adapters with byte-level provenance.
- Added observed-data alignment, nuisance projection, spectral/Whittle baseline, residual, lag and coherence diagnostics.
- Added Colab, offline tests, CI, scientific claim ledger, archaeology and security documentation.
- Set the project license to GNU GPL v3 or later (GPL-3.0-or-later).
- Preserved adverse evidence: one transport truncation, two old endpoint 404s, snapshot-local notebook errors and a public adjacent credential exposure.
