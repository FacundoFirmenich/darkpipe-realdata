# DarkPipe 0.17 preregistration — streaming object-level KiDS RAR

## Governing question

Can the public KiDS DR4 source table and the exactly reconstructed 106,843-lens
sample reproduce the Mistele et al. weak-lensing RAR when lens/source pairs are
accumulated without downloading the 17.7 GB source FITS, the exact spherical
deprojection is applied before stacking, and additive, cross and covariance
controls are retained?

This is an observational reconstruction.  It is not by itself evidence for a
plasma hyperstate, a dark-matter ontology or a modified-gravity mechanism.

## Frozen authentic inputs

- public source FITS: 17,712,469,440 bytes and 21,262,011 rows;
- lens payload: 106,843 rows, SHA-256
  `3c4a43f9516e438a9c35e098ddd3d37768180f9d84e08fb01d73924c899c2b0a`;
- complete native GAAP coverage: 1,239,422 of 1,239,422 KiDS-bright rows;
- selected-row SHA-256:
  `eaa41bda4a09a3f418129ed6b812f6922afedc7a2e1c38061a0bd1aa23c91fc0`;
- effective Eq. 10 Sigma-critical lookup SHA-256:
  `02700c57c9affa47630881b4f2f23023fd632ca4cd0a42c82c89ee78b9bd3da1`;
- 27 logarithmic bins from 0.003 to 11.94 Mpc/h70;
- flat cosmology H0=73 km/s/Mpc, Omega_m=0.2793;
- global multiplicative response `1+mu=0.98531`;
- Blind-C per-component shape dispersions
  `[0.270, 0.258, 0.273, 0.254, 0.270]`.

The pair accumulator must abort if native GAAP coverage or the 106,843 count
is not exact.  Incomplete reconstructions are evidence-bearing adverse runs,
never permitted pair inputs.

## Pair estimator and storage boundary

The source cuts, tomographic assignment, `z_B > z_l + 0.2`, Eq. 10 weights,
spin-2 tangential/cross rotation and radial geometry follow the published
method.  Each remote row partition produces only additive per-lens/per-radius
sufficient statistics.  Partitions are merged by exact array addition.  No
source catalogue or lens-source pair table is persisted locally.

The full signal scan is fixed to eight half-open source-row partitions whose
union is exactly `[0, 21262011)`.  Pair outputs cannot be interpreted until all
eight partitions pass their content hashes and merge without gaps or overlap.

## Frozen random-coordinate construction

Seed: `20260831017`.

The parent KiDS-bright population is `masked=0` and `0.1<z_ANN<0.5`, before
mass and isolation cuts.  It contains 900,778 objects, hence the requested
random count is exactly 45,038,900.  Its redshift histogram uses 80 linear bins
on `[0.1,0.5]`; every bin count is multiplied by 50 and redshifts are uniform
inside that bin.  Coordinates are uniform in solid angle inside the exact set
of source-catalogue `THELI_NAME` tiles intersected with the official DR4
observations table.  The expected tile count is 1006.

The exact tile-name list will be sealed from metadata emitted by the blind full
source scan before any tangential or cross result array is opened.  This is a
declared timing deviation from the ideal v0.13 order because an earlier source
selection scan had already occurred; no lensing value had been inspected when
the seed, population, histogram, count and selection rule were frozen.

Random-coordinate subtraction follows Eqs. 62–63 of Mistele et al.: the
stacked random ESD is subtracted from every lens ESD for ESD stacking, while
the deproject-first random acceleration is subtracted from every individual
lens acceleration for the preferred RAR.  A stack-first random branch is only
a sensitivity result.

## Covariance and acceptance

Statistical variances retain the published per-source shape dispersion and
pair weights.  A deterministic spatial jackknife supplies empirical
cross-lens covariance; its region map and count must be sealed before opening
the final RAR.  Cross and random controls are information-bearing gates: a
failure blocks model-facing comparison and is never tuned away.

The v0.13 reproduction-equivalence thresholds remain unchanged: all 15 central
points inside the corresponding published total one-sigma envelopes, median
absolute difference at most 0.05 dex, no residual monotonic trend at two-sided
Spearman `p<0.01`, and passing cross/random controls.  Before those gates, the
status is `OBJECT_LEVEL_REPRODUCTION_NOT_YET_ESTABLISHED`.

## Scientific ceiling

Even a successful RAR reproduction identifies an acceleration discrepancy,
not its mechanism.  The derived shadows `eta=log10(gobs/gbar)` and
`g_I=gobs-gbar` become admissible observational response variables only after
the controls pass.  The morphotopological plasma conjecture remains
`NOT_ESTIMABLE_MODEL_NOT_YET_DIFFERENTIALLY_PREDICTIVE` until it supplies a
signed, scaled and falsifiable prediction distinct from conventional model
families.
