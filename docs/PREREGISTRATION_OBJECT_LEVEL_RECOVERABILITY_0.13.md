# DarkPipe 0.13 preregistration — object-level recoverability and differential-signature gate

Status: `FROZEN_BEFORE_OBJECT_LEVEL_DATA_ACQUISITION`. Campaign:
`DP-OBJREC-0.13-20260829`.

## Governing objective

Determine whether the v0.12 radial operator shadow can be transferred into the
weak-lensing RAR by reconstructing lens-source weights and deprojecting before
stacking at fixed baryonic acceleration. If that reconstruction succeeds,
define — but do not yet execute — the minimum differential experiment capable
of distinguishing conventional gravitational/baryonic explanations from the
project's morphotopological plasma conjecture.

This campaign is not a dark-matter detection, a MOND rejection, a plasma-state
detection or an ontological identification.

## Frozen stage gates

### G0 — bounded public-input probe

The gate must read only HTTP byte ranges and the complete 4,360-byte `n(z)`
archive. It must not download any large catalogue. The expected public surface
is:

| Input | Expected bytes | Expected rows/members |
|---|---:|---:|
| KiDS-1000 SOM-gold sources | 17,712,469,440 | 21,262,011 rows |
| KiDS DR4 bright lenses | 89,259,840 | 1,239,422 rows |
| KiDS DR4 bright LePhare properties | 257,817,600 | 1,239,422 rows |
| SOM tomographic `n(z)` | 4,360 | 5 files |

G0 passes only if every endpoint responds, its total length matches, its
container is structurally valid and all required columns are present. Drift is
information-bearing and yields `NOT_READY_PUBLIC_INPUT_PROBE_FAILED_OR_DRIFTED`.

### G1 — remote acquisition and custody

Full catalogues may be downloaded only to remote scratch storage with at least
40 GiB available. No full input is written to the user's local disks. Each
completed file receives a SHA-256 checksum, source URL, retrieval time, byte
count and acknowledgement metadata. Partial files are not scientific inputs.

### G2 — independent object-level reconstruction

Use the public SOM-gold sources and KiDS-bright lenses with the selections
declared by Mistele et al. (2024): lens `masked = 0`,
`0.1 < zphot_ANNz2 < 0.5`, source star/quality masks and
`Z_B > z_l + 0.2`. Reconstruct the isolation selection before signal
inspection. The default isolation radius is `4 Mpc/h70`; alternatives are
predeclared sensitivity branches, not substitutions after inspection.

For each lens-source pair:

\[
W_{ls}=w_s\Sigma_{\rm crit,ls}^{-2},
\]

and each individual-lens ESD bin is

\[
\Delta\Sigma_l(R)=
\frac{\sum_s W_{ls}\Sigma_{\rm crit,ls}\epsilon_{t,ls}}
     {\sum_s W_{ls}}.
\]

The exact spherical operator is applied to each lens before stacking:

\[
g_{{\rm obs},l}(R)=4G\int_0^{\pi/2}
\Delta\Sigma_l\left(\frac{R}{\sin\theta}\right)d\theta.
\]

For point-like baryonic masses, the fixed-acceleration coordinate is

\[
R_l(g_{\rm bar})=\sqrt{GM_{b,l}/g_{\rm bar}}.
\]

The main result uses deproject-before-stack. Stack-before-deproject is retained
as a sensitivity branch. No aggregate v0.12 profile may masquerade as an
individual-lens input.

### G3 — additive and multiplicative controls

Generate survey-footprint-matched random coordinates in a separate sealed
configuration before inspecting lensing results. The seed, tile list, redshift
histogram construction and requested count are immutable after the first data
read. Because the historical random catalogue is unavailable, the result is an
independent scientific reproduction, never a byte-identical reproduction.

Apply the published multiplicative-calibration convention and report the
cross-shear profile. A failed cross/null gate is preserved and blocks model
comparison; it is not tuned away.

### G4 — reproduction equivalence

Compare the reconstructed 15-bin RAR with the published Mistele Table 1. Since
the public table has no full inter-bin covariance, this is an engineering
equivalence gate, not a chi-square hypothesis test.

The gate passes only if all conditions hold:

1. every reconstructed central point lies within its corresponding published
   total one-sigma envelope, with total uncertainty formed from the published
   statistical, interpolation/extrapolation and fixed 0.1 dex stellar-mass
   terms;
2. median absolute central-value difference is at most `0.05 dex`;
3. no monotonic radius/acceleration trend remains in signed differences under
   a two-sided Spearman test at `p < 0.01`;
4. cross and random-coordinate controls pass their separately frozen null
   diagnostics.

Failure yields `OBJECT_LEVEL_REPRODUCTION_NOT_ESTABLISHED`. Thresholds may be
criticized after the run, but not silently replaced.

## Differential-signature gate

Only after G0–G4 pass may a model-facing preregistration be opened. Its response
variable is the derived inobservable

\[
\eta=\log_{10}(g_{\rm obs}/g_{\rm bar}),
\]

conditioned at minimum on `g_bar`, stellar mass, redshift, galaxy type,
isolation/environment and survey selection.

Candidate plasma-sensitive shadows are Planck Compton-y, eROSITA X-ray and
LoTSS rotation-measure information. They have non-equivalent physical meaning,
angular resolution and sky coverage and may not be averaged into one generic
“plasma score”. `NOT_APPLICABLE` and `NOT_ESTIMABLE` remain typed outcomes.

Before unblinding any joint result, every compared model family must supply:

1. a signed prediction or explicit order relation;
2. a scale dependence or transition region;
3. an amplitude, bound or equivalence class;
4. a conditional invariance/interaction statement after conventional
   baryonic and environmental controls;
5. a result that would count against the model.

Until the morphotopological plasma conjecture supplies this payload, its status
is fixed as `NOT_ESTIMABLE_MODEL_NOT_YET_DIFFERENTIALLY_PREDICTIVE`.

## Non-decisive outcomes

None of the following identifies the proposed plasma ontology:

- `g_obs > g_bar` in lensing;
- agreement or disagreement with one Lambda-CDM simulation realization;
- an unconditioned association with SZ, X-ray, synchrotron or Faraday rotation;
- topological complexity without an ex-ante null distribution;
- a post-hoc signature chosen because it separates the observed data.

## Mandatory artifacts

- `dataset_probe.json`
- `data_sufficiency_ledger.csv`
- remote input checksum manifest after G1
- sealed random-coordinate configuration after G1 and before G2
- object-level selection and attrition ledger
- reproduced RAR with control/null products after G2–G4
- claim-to-source ledger
- substantive Spanish closure

## Authority ceiling

The current v0.13 implementation has authority only for G0. Passing G0 means
that the public inputs are available and structurally sufficient in principle.
It does not mean that G1–G4 ran, that the RAR was reproduced, or that any model
was supported or rejected.

