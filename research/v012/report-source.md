# Deep-research decision — DarkPipe 0.12

## Decision

The smallest authority-increasing increment after v0.11 is a **covariance-aware radial operator shadow** built from the four Brouwer et al. (2021) KiDS-1000 radial ESD profiles and their joint 60×60 covariance. It outranks adding another digitized acceleration curve because it tests an upstream transformation that conditions the weak-lensing shadow itself.

## Evidence comparison

| Candidate | Public surface | Gain | Blocking limitation | Decision |
|---|---|---|---|---|
| Brouwer 2021 radial ESD | 4×15 physical-radius profiles + joint 60×60 covariance + cross component | Full-covariance paired SIS/exact operator test | Already stacked; no per-lens profiles/weights | **Selected** |
| Brouwer 2021 RAR ESD | 15 `g_bar` bins + 15×15 covariance | Directly adjacent to v0.11 | Exact deprojection cannot be reconstructed from an aggregate `g_bar` stack | Retained, not used for false exactness |
| Mistele 2024 KiDS analysis | Exact spherical formula and systematic construction | Defines superior operator and stacking caveat | Public paper does not provide the object-level intermediate needed to reproduce deproject-first here | Method source |
| CLASH 2025 clusters | Cluster mass/density/correlation matrices | New scale and covariance | No matched radial baryonic profile; different cluster jurisdiction | Deferred |
| Strong-lens catalogues | Object-level lens candidates | Potential individual correspondence | Inner-scale, morphology-selected, model-dependent masses; no compact matched baryon+lensing covariance surface found | Deferred |

## Primary-source findings

The [KiDS science-data page](https://kids.strw.leidenuniv.nl/sciencedata.php) states that the release provides the ESD profiles corresponding to Brouwer et al. (2021), with the tarball and README. The [KiDS reuse policy](https://kids.strw.leidenuniv.nl/acknowledgements.php) licenses both public releases and high-level scientific-analysis products under CC BY 4.0 with attribution.

[Brouwer et al. (2021)](https://arxiv.org/abs/2106.11677) use `g_obs = 4G DeltaSigma` under the SIS approximation and publish a covariance that accounts for correlations when sources contribute to multiple bins. Weak lensing is necessarily statistical here because the individual distortions are small. The paper also warns that isolation failures and baryonic-mass calibration affect model-facing comparisons.

[Mistele et al. (2024)](https://arxiv.org/abs/2310.15248) derive `g_obs(R)=4G integral DeltaSigma(R/sin theta) dtheta`, under spherical symmetry and appropriate falloff. They explicitly distinguish deproject-before-stack from stack-before-deproject: the latter is not exact when normalized weights depend on radius, although both procedures were close for their KiDS application. They use interpolation and outer-tail alternatives as systematic checks and validate cross components as null diagnostics.

## Interpretation

The chosen experiment does not ask whether a named ontology is true. It asks how much of the weak-lensing acceleration surface is invariant to a better deprojection operator once the published covariance is respected. This is exactly a new shadow of an observable: the difference between two admissible mappings of the same measured ESD, together with the covariance and boundary-condition cost of that transformation.

The strict boundary is equally important. Since the selected profiles are stacked in physical radius and the v0.11 lensing RAR is stacked in `g_bar`, a numerical operator shift cannot be inserted into the old RAR bins. The correct output is a radial operator-sensitivity atlas plus an explicit abstention on RAR transfer. Object-level profiles or sufficient per-lens weights are the next evidence-critical acquisition.
