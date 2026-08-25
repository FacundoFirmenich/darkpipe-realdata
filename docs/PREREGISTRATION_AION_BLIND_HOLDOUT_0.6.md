# DarkPipe 0.6 preregistration: seed-committed AION holdout replay

Preregistration ID: `DP-AION-BLIND-0.6-20260825`

Status: protocol and executable decision rule frozen before challenge construction, prediction, or reveal. The Git commit containing this document and `src/darkpipe/aion_blind.py` is the preregistration authority.

Seed commitment (SHA-256): `0a1ad503b576ba7ec553d43da1199d2f05c3eb4d8e577e36be8a38d457eb382d`. The 256-bit preimage remains outside the repository until predictions are written.

## Governing objective and claim ceiling

The campaign tests a fixed seven-frequency score detector on authentic AION LLN/HLN control noise through an operationally blinded, seed-committed replay. It advances v0.5 from published-injection recovery to a held-out null plus unlabeled challenges with familywise calibration.

A passing result supports only one fixed-family software-detector replay on one authentic control holdout. It is not a physical detection, an independent repeated-instrument false-positive rate, a continuous-band search, a nonlinear raw-likelihood equivalence, or a sensitivity projection for AION-10/AION-km.

## Frozen evidence and split

- LLN control: 28,309 rows; SHA-256 `d582be3ecccdb5fa139d2a5280da51f926fee8b31963662a68be980c27a7d224`.
- HLN control: 28,314 rows; SHA-256 `ba800196b6db0f3be93c4fe66cd18332d11189d78234488c5d283719218c5319`.
- Source integrity remains governed by the 27-file AION manifest of campaign `DP-AION-0.4-20260825`.
- Rows are stable-sorted by timestamp. The first floor(0.40 n) rows of each condition are development; the remaining 60% are holdout. The five raw timestamp reversals in each control remain reported and the raw files are not rewritten.
- Detector implementation SHA-256 before freeze: `6cadd02a8f033683ac549a0df564958992786d7b933e106c86e681a3e7dcdc6f`.

## Declared development-only design check

Before freeze, and without computing holdout scan endpoints, the development segment was used to verify numerical viability. Its real-noise null had max-family p = 0.958984375. Seven 0.6-rad tangent injections were each the sole detected target with p = 1/4096. These are design diagnostics, not campaign results, and cannot be substituted for the holdout gates.

## Frozen nuisance and signal model

For each of LLN/HLN and forward/backward arms, development data fit

`p = b0 + b1 u + b2 cos(phi) + b3 sin(phi) + b4 u cos(phi) + b5 u sin(phi)`,

where `u` is time mapped to [-1,1] over the complete condition span. Scale is 1.4826 times the median absolute deviation of development residuals, with sample standard deviation only as a non-positive fallback.

At target frequency `f`, the two score columns are the fitted fringe derivative multiplied by `cos(2 pi f t)` and `sin(2 pi f t)`, with +1/2 for forward and -1/2 for backward. Nuisance columns are profiled by weighted least squares inside each analyzed segment.

The target family is the seven exact truth-NPZ frequencies corresponding to 0.1, 0.3, 1, 3, 10, 30 and 100 mHz. No extra frequency may be introduced after freeze.

## Familywise null calibration

The development residuals are circularly rotated condition-wise; forward/backward arms share the same rotation within a condition. LLN and HLN rotations are independently drawn with fixed seed `2026082506`. Exactly 4,095 nonzero rotations are evaluated. Each surrogate contributes the maximum score statistic across all seven frequencies.

For any observed statistic `T`, `p_FWER = (1 + count(T_null,max >= T)) / 4096`. A frequency is detected iff `p_FWER <= 0.05`. This is a conditional circular-rotation calibration; stationarity/exchangeability is an explicit assumption, not a universal false-alarm guarantee.

## Sealed challenge

After the preregistration commit:

1. verify the seed commitment;
2. derive deterministic opaque case IDs, case order and phases from domain-separated SHA-256;
3. construct eight holdout cases: one unchanged null and one injection at each target frequency;
4. use amplitude 0.60 rad, matching the scale of the upstream published phase modulations;
5. add only the first-order differential-phase tangent perturbation to authentic holdout excitation fractions;
6. write and hash `sealed_challenge.npz` and a manifest with no target mapping;
7. run the fixed scan and write `blind_predictions.json` before revealing the seed.

The synthetic component is only the declared signal perturbation. Noise samples and covariates are authentic AION observations.

## Terminal gates

- Gate 0: source and sealed-byte integrity pass.
- Gate N: the revealed null case has zero familywise detections.
- Gate S: for every injected case, the target is the maximum-statistic frequency, is the only detected frequency, and has global p <= 0.05.
- `PASS_BOUNDED`: Gate 0, Gate N and Gate S (7/7) pass.
- `FAIL_BOUNDED`: integrity passes but Gate N or any Gate S case fails. Every adverse case remains reported.
- `ABSTAIN_INTEGRITY`: source, commitment, case order or sealed hash fails; no scientific endpoint is promoted.

Amplitude estimates are descriptive and non-gating. No threshold, frequency, amplitude, split, nuisance basis, surrogate count or terminal rule may change after this commit.

## Mandatory NOT_ESTIMABLE claims

- independent repeated-instrument false-positive rate;
- continuous-band blind-search significance;
- dark-matter or gravitational-wave detection;
- nonlinear raw-HDF5 marginal-likelihood equivalence;
- transfer to AION-10 or AION-km.
