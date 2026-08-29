# v0.11 multi-shadow selection — canonical research source

Date: 2026-08-26
Status: selection frozen for implementation; no official v0.11 result in this file.

## Governing question

Which real gravitational-lensing source can add a genuinely distinct
observational shadow to DarkPipe v0.10 while preserving the required chain

observables -> shadows of observables -> conditional derived inobservables

without falsely joining different objects, inventing radial baryonic profiles,
or turning a discrepancy into an ontology?

## Evidence slots

1. Observational independence from SPARC rotation kinematics.
2. Compatibility with the galaxy-scale acceleration jurisdiction.
3. Public, citable and legally reusable numerical values.
4. Covariance or an explicit limitation when covariance is unavailable.
5. Enough baryonic information to derive a signed discrepancy.
6. Projection method and its assumptions.
7. Small bounded storage footprint.
8. Typed non-identifiability and adverse/systematic regions.

## Primary-source findings

### Mistele et al. 2024 — selected

The final publisher article is CC BY 4.0 and publishes a 15-bin weak-lensing
RAR table containing log10(g_bar), log10(g_obs), statistical uncertainty and
interpolation/extrapolation systematic uncertainty. It uses KiDS-1000 sources
and KiDS-bright isolated lenses. The authors use the same stellar population
model as the kinematic relation and introduce an exact spherical-deprojection
identity:

g_obs(R) = 4 G integral_0^(pi/2) DeltaSigma(R/sin(theta)) dtheta.

The table extends the galaxy-scale RAR by roughly 2.5 dex. The lowest
acceleration tail is explicitly sensitive to extrapolation and isolation; the
paper warns that systematics become important below approximately
g_bar = 10^-14 m s^-2. The published table does not provide a full joint
covariance including baryonic systematics. The paper sometimes omits small
off-diagonal terms for its own simple chi-squared comparisons. DarkPipe
therefore may derive pointwise conditional shadows and a sensitivity envelope,
but not a joint SPARC-KiDS likelihood.

Primary sources:

- https://commons.case.edu/facultyworks/800/
- https://arxiv.org/abs/2310.15248
- https://doi.org/10.1088/1475-7516/2024/04/020

### Brouwer et al. 2021 — retained, not selected

This KiDS-1000 analysis is also observationally independent of SPARC and
publishes ESD profiles for its result figures. It constructed an analytic full
covariance at the ESD stage and explicitly accounts for sources appearing in
multiple bins. Its principal RAR conversion uses a singular-isothermal-sphere
approximation, with a more expensive piecewise-power-law cross-check. The
authors report sensitivity to circumgalactic baryons, stellar-mass systematics,
photometric-redshift isolation and the two-halo environment.

It is a valuable future source for rebuilding the deprojection from ESD and
recovering more covariance. It is not selected for this first v0.11 operator
because the later Mistele analysis supplies an exact deprojection, a baryonic
calibration aligned with SPARC and a compact final numerical table.

Primary sources:

- https://arxiv.org/abs/2106.11677
- http://kids.strw.leidenuniv.nl/sciencedata.php
- https://doi.org/10.1051/0004-6361/202040108

### Mistele et al. 2025 CLASH clusters — deferred jurisdiction

Zenodo record 15476959 contains non-parametric mass and density profiles for
20 CLASH clusters plus mass/density correlation matrices in only 182.4 kB.
The profiles are individual systems and the covariance support is better than
for the selected final KiDS RAR table.

This source cannot be folded into v0.11 as if it were another SPARC galaxy
channel. It is a cluster-scale jurisdiction. More decisively, its public
per-cluster CSV files contain lensing mass and density profiles, while the
repository's baryonic product contains total baryonic-mass estimates rather
than the radial M_b(r) needed to derive M_lens(r)-M_b(r) without importing
additional X-ray gas-profile assumptions. The paper itself emphasizes that
gas extrapolation beyond the reliable X-ray radius materially changes the
cluster BTFR/RAR position. That uncertainty is scientifically useful, not a
gap to fill with a fabricated profile.

Primary sources:

- https://zenodo.org/records/15476959
- https://doi.org/10.5281/zenodo.15476959
- https://arxiv.org/abs/2506.13716

## Ordinal decision matrix

Scores are 0–5 and are only a transparent selection aid. They do not measure
scientific truth. Weighted maximum: 80.

| Criterion | Weight | Mistele 2024 KiDS | Brouwer 2021 KiDS | Mistele 2025 CLASH |
|---|---:|---:|---:|---:|
| Independent observational channel | 3 | 5 | 5 | 5 |
| Galaxy-scale compatibility | 3 | 5 | 5 | 1 |
| Reusable numerical source | 2 | 5 | 3 | 5 |
| Covariance support | 2 | 2 | 4 | 5 |
| Radial baryonic discrepancy possible | 3 | 5 | 5 | 2 |
| Projection method | 2 | 5 | 3 | 5 |
| Bounded storage | 1 | 5 | 4 | 5 |
| **Weighted total / 80** |  | **74** | **69** | **59** |

## Frozen v0.11 interpretation

The selected source is Mistele et al. 2024 Table 1. The numerical source is a
CC BY 4.0 curated transcription, not raw KiDS images or catalogues.

For each published bin DarkPipe will derive:

- g_inobservable = 10^log_gobs - 10^log_gbar;
- eta = log_gobs - log_gbar = log10(g_obs/g_bar);
- a declared sensitivity envelope formed from the published statistical term,
  the published deprojection systematic and the separately reported fixed
  0.1 dex stellar-mass systematic.

Quadrature is an explicit sensitivity construction, not a probabilistic claim
that all systematic terms are independent Gaussian draws. The sign status is
conditional on published central g_bar; missing g_bar covariance remains a
limit.

The cross-shadow atlas compares each KiDS bin to galaxy-equal-weight SPARC
medians within a fixed +/-0.125 dex log10(g_bar) window. It is descriptive
only. A different object population and absent cross-covariance prohibit
calling it a replication, fusion or joint likelihood.

## Authority ceiling

Permitted: population-level effective acceleration discrepancy conditional on
the published lensing deprojection, baryonic model, spherical symmetry and
declared sensitivity envelope.

Not estimable:

- object-by-object SPARC/KiDS correspondence;
- independent confirmation of each SPARC profile;
- full covariance including baryonic systematics;
- intrinsic lens-to-lens scatter;
- cluster-scale continuity;
- particle identity, three-dimensional invisible density or plasma ontology;
- MOND versus Lambda-CDM adjudication;
- the physical mechanism of gravitation.

## Decision

Select Mistele et al. 2024 for v0.11. Retain Brouwer ESD as the route toward a
future covariance-aware re-deprojection. Retain CLASH as a separate
cluster-scale campaign that first requires a citable radial baryonic profile
or an explicitly bounded outer-radius operator. Do not merge either deferred
source into the present authority.
