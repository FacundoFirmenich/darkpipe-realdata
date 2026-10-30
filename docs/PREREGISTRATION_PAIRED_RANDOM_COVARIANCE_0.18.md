# KiDS next gate: paired spatial covariance, 2026-10-30

Status: protocol fixed before the 50x control and corrected RAR are opened.
This is a candidate gate on the v0.17 line, not a completed science release.

## Governing evidence and retained adverse result

The v0.17 corrected east/e2-sign-flipped estimator reduces the observed median
log discrepancy to 0.0494255413 dex but only 10/15 exact-RAR central points lie
inside the published total one-sigma envelopes. The historical reproduction
gate remains false. The stratified 10,060-position random pilot is not the
frozen 45,038,900-position control. Its estimates cannot replace the latter.

Seed 20260831017, 1006 survey tiles, the 988 THELI source-pointing coverage,
80-bin lens-parent redshift allocation, source cuts, corrected spin-2 rotation,
27 radial bins, Sigma-critical lookup and deprojection/tail rules are retained.
No historical target or holdout is reopened for threshold tuning.

## Frozen input contract

`run_darkpipe_next_gate_v018.py` binds the exact bytes of the four admitted
configuration, source-index, Sigma-critical and orientation-receipt files.
It independently recomputes the row-run hash and exact [0, 21262011) coverage,
988 source pointings, 1006 random tiles and 45,038,900 allocation conservation.
An altered byte or missing input forces integrity abstention.

## Statistical contract

The corrected observable is D = S - R. Its covariance is

`C_D = C_S + C_R - C_SR - transpose(C_SR)`.

Use the same ordered, unique spatial exclusions for signal and control. The
exclusion map, its hash, region count, assignment method and source-deletion
policy must be committed before opening the corrected RAR. This document does
not assert that a suitable region map has already been constructed. A shared
ID or checksum cannot prove upstream spatial matching.

The paired implementation takes region-level additive sufficient sums, then
forms both leave-one-region-out estimators and subtracts each pair before
covariance calculation. The joint vector has four channel-major blocks: ESD,
cross ESD, deproject-first acceleration and cross acceleration. It retains
cross-channel and cross-radius covariance as well as S/R cross-covariance.

An estimable coordinate requires finite full estimates and finite values in
every signal and random replicate. One common column mask governs all blocks;
missing coordinates remain NaN. Pairwise deletion, zero-filling, diagonal-only
substitution and assuming signal/random independence are forbidden. No matrix
inverse, Hartlap factor, chi-square p-value or physical significance is inferred
automatically. The maximum rank is N_regions - 1; singularity remains visible.
The `(N-1)/N` delete-one normalization assumes an admitted comparable-area
region design. Unequal raw survey tiles cannot be silently treated as that
design; a justified map or an explicitly different estimator is required.

This is an empirical spatial covariance conditional on map and deletion policy.
It does not close calibration, mass modelling, redshift or tail systematics.
The existing random-centre-only jackknife remains a diagnostic of R, not C_D.
For a RAR stacked at fixed gbar the matched replicates must be constructed for
that same fixed-gbar estimator; a covariance on fixed physical radii cannot
be silently transferred to it.

## Remote execution contract

No full catalogue is downloaded onto the user's workstation. The full control
requires an explicitly admitted DarkPipe node, at least 40 GB free scratch,
one ephemeral 17,712,469,440-byte FITS, authenticated source provenance, compact
checkpointed reductions and a finite CPU-hour budget. A pre-authorized benchmark
has a hard 30-minute wall limit and precedes any full-campaign launch. Old pilot
scaling (231-417 hours per original partition) is retained as an uncertain cost
projection, not relabelled as a tile-local benchmark.

The historical VPS receipt is Jarvis-scoped and conveys no DarkPipe execution
authority. The public GitHub branch is for code/protocol tests; its CI does not
start the 50x campaign. Main and tariff-energy work are outside this change.

## Terminal decisions

- `ABSTAIN_INPUT_INTEGRITY`: a frozen input failed.
- `BLOCKED_EXECUTION_AND_PAIRED_COVARIANCE`: inputs verified; remote resource,
  full control or matched spatial replicates remain missing.
- A future full-result gate requires complete sealed 1006-tile/45,038,900
  control, validated spatial map and matching signal/control replicates.
  Passing software tests cannot substitute for any of these.

The v0.13/v0.17 reproduction thresholds remain unchanged. No mechanism,
dark-matter detection or plasma/morphotopological ontology is adjudicated here.

Sources: [Mistele et al., Appendix C.2](https://arxiv.org/html/2310.15248),
[GitHub Actions limits](https://docs.github.com/en/actions/reference/limits),
[runner specifications](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).
