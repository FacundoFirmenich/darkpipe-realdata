# Deep research — DarkPipe 0.13 object-level recoverability and differential gate

Date: 2026-08-29. Scope: primary sources and live bounded endpoint probes only.

## Decision

The v0.12 abstention is narrowed from “no object-level weights” to a two-part
finding:

1. **Scientific reconstruction is feasible in principle.** The public KiDS
   surface contains the lens catalogue, lens stellar-mass catalogue, source
   shear catalogue and the five redshift distributions needed to recompute
   lens-source weights and individual-lens ESD profiles.
2. **Exact historical reproduction is not established.** The high-level
   Brouwer release contains stacked profiles and covariances, not the exact
   random-coordinate catalogue. Its linked KiDS-GGL repository currently
   returns 404. A new calculation can therefore be independently reproducible,
   but it must not claim byte-identical reproduction of the authors' pipeline.

This selects a remote object-level reconstruction gate as the next executable
campaign. It rejects another algebraic remapping of the 60 already-stacked
radial points.

## Primary evidence

The [KiDS-1000 source-catalogue page](https://kids.strw.leidenuniv.nl/DR4/KiDS-1000_shearcatalogue.php)
publishes a 16 GB FITS table with 21,262,011 sources and documents the sky
coordinates, `Z_B`, ellipticities `e1/e2`, lensfit `weight`, masks and quality
fields. It also publishes the five tomographic `n(z)` distributions.

The [KiDS DR4 bright-galaxy page](https://kids.strw.leidenuniv.nl/DR4/brightsample.php)
publishes an 85 MB lens catalogue and a 246 MB LePhare-properties catalogue.
Together they provide IDs, positions, ANNz2 redshifts, masking, photometry and
stellar-mass posterior summaries for 1,239,422 rows.

[Brouwer et al. (2021)](https://arxiv.org/html/2106.11677v1) define the
lens-source weight as `W_ls = w_s Sigma_crit^-2`, construct radial bins for
each individual lens from its baryonic mass, and publish the final ESD result
bundle. They also show that model-facing interpretation is sensitive to
isolation, baryonic mass and circumgalactic gas.

[Mistele et al. (2024)](https://arxiv.org/html/2310.15248) explicitly use the
public KiDS-1000 SOM-gold sources and KiDS-bright lenses. Appendix B gives the
object-level estimator, lens weights, deproject-before-stack operator and the
mapping `R_l(g_bar)`. The paper states that stack-before-deproject is not exact
when normalized weights vary with radius, and uses 45 million regenerated
random coordinates for additive-bias subtraction.

Live HTTP range probes on 2026-08-29 returned `206 Partial Content` and FITS
magic for all three catalogues:

| Input | Observed bytes | Rows from live FITS header | Fields |
|---|---:|---:|---:|
| SOM-gold sources | 17,712,469,440 | 21,262,011 | 193 |
| KiDS-bright lenses | 89,259,840 | 1,239,422 | 8 |
| KiDS-bright LePhare | 257,817,600 | 1,239,422 | 39 |
| SOM `n(z)` archive | 4,360 | 5 member files | — |

The total raw surface is 18,059,551,240 bytes (16.819 GiB). Only bounded
prefixes were read; the catalogues were not downloaded to local disk.

## Differential-signature boundary

Weak lensing constrains a gravitational mass/acceleration surface under the
stated lensing and symmetry assumptions; it does not identify the material
ontology producing that surface. Brouwer's own comparison shows that one
Lambda-CDM realization (MICE) can reproduce the RAR while another (BAHAMAS)
differs, and Mistele shows that isolation and baryonic calibration can alter
the apparent early/late-type split. Thus a lensing RAR alone cannot adjudicate
Lambda-CDM, MOND, or the morphotopological plasma conjecture.

The next model-facing gate must condition the derived inobservable
`eta = log10(g_obs/g_bar)` on conventional nuisances and add at least one
plasma-sensitive shadow. Public candidates exist, but each has a different
jurisdiction:

- [Planck full-mission Compton-y maps](https://irsa.ipac.caltech.edu/data/Planck/release_3/all-sky-maps/ysz_index.html)
  trace integrated thermal-electron pressure, with public noise splits and
  masks, but coarse angular resolution.
- [eROSITA-DE DR1](https://erosita.mpe.mpg.de/dr1/) provides public X-ray
  catalogues/products for one Galactic hemisphere; the main catalogue alone
  has about 930,000 sources and therefore incomplete sky jurisdiction.
- The [LoTSS DR2 RM grid](https://arxiv.org/abs/2301.07697) contains 2,461
  rotation measures over 5,720 square degrees (about 0.43 per square degree),
  useful for a sparse environmental magnetic-field shadow but not dense
  object-by-object coverage of a million KiDS lenses.

A correlation with any of these proxies would be necessary evidence for a
plasma-linked effect but not sufficient evidence for the proposed ontology:
ordinary gas physics, feedback, environment, selection and modified-gravity
external-field effects can induce related structure. The conjecture therefore
remains `NOT_ESTIMABLE_MODEL_NOT_YET_DIFFERENTIALLY_PREDICTIVE` until it fixes
at least a sign or order relation, scale dependence, invariance/interaction
pattern and decisive adverse outcome before inspecting the joint data.

## Next action

Run the object-level reconstruction on remote scratch storage using streamed
spatial indexing; do not materialize all lens-source pairs. Freeze independent
random-coordinate generation before the run. Only after the published RAR is
recovered within the preregistered engineering gate should a separate blinded
multi-proxy differential campaign be authorized.

