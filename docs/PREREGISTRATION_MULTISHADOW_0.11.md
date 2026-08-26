# Preregistration: DarkPipe 0.11 galaxy-scale multi-shadow

Protocol ID: DP-MULTISHADOW-0.11-20260826
Date frozen: 2026-08-26
License of DarkPipe code: GPL-3.0-or-later
Status: deterministic source-informed derivation; not blind.

## Governing objective

Add a second observational shadow to the v0.10 SPARC kinematic discrepancy
using real weak gravitational lensing, then derive conditional inobservables
without fusing different objects or adjudicating a physical ontology.

## Frozen inputs

1. data/mistele2024_weak_lensing_rar_table1.csv
   - SHA-256:
     624c19f5f0edd2fca78bc94d108863a5f4b8f516ff15fe0ca65d7854b6ea55d0
   - 15 rows transcribed from Mistele et al. 2024 Table 1.
   - Source article DOI: 10.1088/1475-7516/2024/04/020.
   - Source license: CC BY 4.0.
   - This is a curated table, not raw KiDS survey data.

2. evidence/v010_shadow_inobservable/derived_inobservable_profiles.csv
   - SHA-256:
     aee55c110eb5dbe593a37e173633383c77f46251527678fc188d8ff4ce6e0977
   - Immutable checked v0.10 SPARC derived-profile surface.
   - Historical v0.10 authority remains unchanged.

Any hash, schema, row-count or finite-value mismatch is terminal
ABSTAIN_INPUT_INTEGRITY.

## Frozen lensing operator

For every published bin:

- g_bar = 10^log10_gbar;
- g_obs = 10^log10_gobs;
- signed inobservable: g_I = g_obs - g_bar;
- logarithmic shadow: eta = log10_gobs - log10_gbar.

The declared combined sensitivity scale in log10(g_obs) is:

sigma_sens = sqrt(sigma_stat^2 + sigma_deprojection^2 + 0.10^2).

The fixed 0.10 dex term is the source article's separately reported
stellar-mass systematic translated to log10(g_obs). Systematic terms are not
asserted to be independent Gaussian random variables. Multiplying sigma_sens
by 1.959963984540054 constructs a sensitivity envelope, not a posterior
credible interval.

Pointwise sign states:

- POSITIVE_CONDITIONAL_SENSITIVITY_ENVELOPE_95 when the lower envelope of
  g_I is greater than zero;
- NEGATIVE_CONDITIONAL_SENSITIVITY_ENVELOPE_95 when the upper envelope is
  less than zero;
- SIGN_AMBIGUOUS_CONDITIONAL_SENSITIVITY_ENVELOPE_95 otherwise.

The published central g_bar is held fixed because its complete uncertainty and
joint covariance are not available in Table 1. Every sign statement is
conditional on that restriction.

## Frozen reliability jurisdiction

Bins with log10(g_bar) < -14.0 receive
LOW_ACCELERATION_TAIL_SYSTEMATICS_DOMINANT.

All other bins receive DECLARED_PRIMARY_RANGE.

Tail bins are retained in every output. They are never silently discarded or
promoted to the primary jurisdiction.

## Frozen cross-shadow atlas

For each lensing bin, select v0.10 SPARC points within +/-0.125 dex in
log10(g_bar). Reduce those points first to one median eta per galaxy. Report
the median and 16th/84th quantiles across galaxies.

At least five SPARC galaxies are required for
DESCRIPTIVE_OVERLAP_NO_JOINT_LIKELIHOOD. Otherwise the bin is
NOT_ESTIMABLE_INSUFFICIENT_SPARC_OVERLAP.

No p-value, Bayes factor, regression fit, joint covariance, confirmation label
or object-level match may be calculated from this atlas.

## Terminal decision rule

If both input-integrity gates pass and all 15 lensing bins produce finite
derived values, report:

SECOND_GALAXY_SCALE_LENSING_SHADOW_AVAILABLE_NO_OBJECT_LEVEL_FUSION.

Otherwise abstain with the exact failed gate. This decision denotes a usable
second population-level observational shadow, not physical confirmation.

## Frozen outputs

- lensing_derived_inobservables.csv
- cross_shadow_atlas.csv
- multishadow_summary.json
- multishadow_atlas.png
- SUBSTANTIVE_CLOSURE_ES.md
- manifest.json

Raw KiDS survey files are neither downloaded nor retained. The compact CC BY
4.0 Table 1 transcription and attribution notice remain in the repository.

## Explicitly not estimable

- object-by-object SPARC and KiDS correspondence;
- independent confirmation of each SPARC profile;
- full covariance including baryonic systematics;
- intrinsic galaxy-by-galaxy lensing scatter;
- cluster-scale continuity;
- particle identity or three-dimensional invisible density;
- MOND versus Lambda-CDM adjudication;
- a mechanism of gravity;
- the morphotopological plasma-hyperstate conjecture.

## Chronology and non-blind status

The published table and its trends were necessarily visible during source
selection. This is not a blind campaign. The methodological protection is
chronological freezing of inputs, operator, thresholds, authority and outputs
before any repository-designated v0.11 execution is accepted as the checked
result. Exploratory reproductions must not be relabeled as that checked run.
