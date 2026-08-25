# DarkPipe 0.7 preregistration: continuous AION search with environmental controls

Preregistration ID: DP-AION-CONTINUOUS-0.7-20260825

Status: protocol and executable rules are frozen after four explicitly bounded
engineering equivalence probes and before the full continuous scan. The Git
commit containing this document, src/darkpipe/aion_continuous.py, the runner and
tests is the authority.

## Governing objective and claim ceiling

This campaign asks whether a development-only continuous frequency scan of the
authentic AION LLN/HLN controls yields a bounded candidate family that replicates
on the chronological holdout, and whether any survivor is spectrally associated
with measured local geomagnetic variation.

A terminal result can support at most a single-epoch sensor candidate and its
measured environmental classification. It cannot establish dark plasma, dark
matter, gravitational waves, causation, an independent false-positive rate, a
specific particle/field coupling, or transfer to another instrument.

## Frozen source and chronology

- LLN control: 28,309 rows; SHA-256
  d582be3ecccdb5fa139d2a5280da51f926fee8b31963662a68be980c27a7d224.
- HLN control: 28,314 rows; SHA-256
  ba800196b6db0f3be93c4fe66cd18332d11189d78234488c5d283719218c5319.
- Stable timestamp sort and the existing floor(0.40 n) development / 60 percent
  holdout split are retained byte-for-byte.
- LLN spans 2025-12-19T19:42:50.428Z to 2025-12-22T09:36:40.661Z.
- HLN spans 2025-12-19T19:42:56.819Z to 2025-12-22T09:36:47.035Z.
- The v0.6 seven-frequency results remain historical evidence. This campaign
  reuses the epoch, so it is not independent replication.

The files must be read to split them, but the discovery stage is forbidden to
compute, rank, plot, report or threshold any holdout frequency endpoint.

- Development median sampling interval is 6.324622154 s for LLN and
  6.323342323 s for HLN. Their nominal median-cadence Nyquist frequencies are
  79.056106 and 79.072107 mHz. Sampling is irregular, so these are cadence
  diagnostics rather than a claim of an ideal uniformly sampled spectrum.
- The scientific upper bound is fixed at 75 mHz, below the lower nominal
  median-cadence Nyquist. The 75–100 mHz interval is not searched.
## Frozen signal and nuisance score

For each LLN/HLN and forward/backward arm, development fits the same six-column
fringe nuisance model used by v0.6. Scale is 1.4826 times the development
residual MAD, with sample standard deviation only as a non-positive fallback.

At each frequency, the two signal columns are the fitted fringe derivative
multiplied by cosine and sine. Forward and backward signs are +1/2 and -1/2.
Nuisance columns are profiled within the analyzed segment. The score statistic
is the exact two-quadrature profiled quadratic form. Bounded batching changes
memory use only; tests require equality with the explicit v0.6 design.

## Adverse pre-freeze engineering probes

The numerical equivalence test computed development statistics at exactly
0.1, 1.2345, 30 and 99 mHz before freeze. Its first failing run exposed those
four values while localizing an incorrect global time origin. No holdout
endpoint or full-band ranking was computed. The defect was repaired and exact
equivalence passed. These four frequencies and a two-Rayleigh-cell neighborhood
around each are ineligible for candidate selection. This preserves the adverse
trace instead of rewriting the campaign as fully untouched. The 99 mHz probe is
outside the finalized scientific band.


## Development-only continuous discovery

- Closed band: 0.1 mHz through 75 mHz.
- Grid spacing: one development Rayleigh cell, 1 / T_development.
- Oversampling: 1.
- Candidate eligibility: a finite local maximum whose left neighbor is not
  larger and whose right neighbor is strictly smaller.
- Ranking: statistic descending, then frequency ascending.
- Separation: at least two development Rayleigh cells.
- Exclusion: the four pre-freeze engineering probes and two Rayleigh cells
  around each cannot become candidates.
- Maximum family: eight candidates.
- No development significance threshold is used.

The candidate JSON and plot must be committed before any holdout endpoint is
computed. Its commit is the candidate-freeze authority.

## Holdout confirmation and multiplicity

Only the committed candidate frequencies may be evaluated on holdout. Exactly
4,095 nonzero condition-wise circular rotations are drawn with seed 2026082507;
forward/backward arms share a rotation and LLN/HLN rotations are independent.
Each surrogate contributes the maximum statistic over the frozen family.

For statistic T, p_FWER = (1 + count(null_max >= T)) / 4096. A candidate is
confirmed iff p_FWER <= 0.05. Frequencies, family size, nuisance basis, split,
surrogate count, seed and threshold cannot change after the freeze.

## Measured environmental classification

Environmental analysis is attempted only for confirmed holdout candidates.

1. Local field: INTERMAGNET/BGS Hartland best-available XYZF one-second data,
   dataset had/best-avail/PT1S/xyzf.
   Hartland is a regional reference observatory, not a co-located AION
   magnetometer; non-association cannot exclude strictly local mechanisms.
2. Heliospheric context: NASA CDAWeb OMNI_HRO2_1MIN. Its 8.333 mHz Nyquist
   ceiling is explicit and OMNI never acts as a causal veto.
3. An AION differential-phase proxy is formed from the opposite-sign arm
   residuals with inverse-information weighting. The lowest 10 percent of
   phase-information samples are excluded.
4. The holdout is divided into eight fixed equal-duration blocks. Each block is
   linearly detrended before its complex coefficient is evaluated.
5. Hartland association uses magnitude-squared coherence across blocks for
   X, Y, Z and F. A valid comparison needs at least six blocks.
6. Exactly 4,095 deterministic block-pair permutations use seed 2026082517.
   Every permutation contributes the maximum coherence across every confirmed
   candidate and Hartland component.
7. Local association is SUPPORTED iff its familywise permutation p <= 0.05.
   It is association, not causation. OMNI coherences are context only.

Raw HAPI JSON and info receipts are retained in the cloud campaign artifact with
byte hashes. If acquisition, schema, coverage or valid-block requirements fail,
environmental classification is NOT_ESTIMABLE; the sensor candidate is not
silently promoted or discarded.

## Terminal decisions

- NO_HOLDOUT_CANDIDATE: no eligible development maximum exists, or no frozen
  development candidate passes holdout FWER.
- LOCAL_GEOMAGNETIC_ASSOCIATION: at least one holdout candidate passes and the
  Hartland association gate is supported.
- UNEXPLAINED_SENSOR_CANDIDATE: at least one passes and Hartland association is
  contradicted under the frozen gate.
- CANDIDATE_ENVIRONMENT_NOT_ESTIMABLE: at least one passes but the environmental
  gate cannot be estimated.
- ABSTAIN_INTEGRITY: source, candidate file or chronology integrity fails; no
  endpoint is promoted.

## Mandatory NOT_ESTIMABLE claims

- the unsearched 75–100 mHz interval;
- dark-plasma, dark-matter or gravitational-wave detection;
- independent-epoch or independent-instrument false-positive rate;
- causal environmental coupling;
- nonlinear raw-HDF5 likelihood equivalence;
- transfer to AION-10, AION-km or another facility;
- universality of the projection/authority architecture.
