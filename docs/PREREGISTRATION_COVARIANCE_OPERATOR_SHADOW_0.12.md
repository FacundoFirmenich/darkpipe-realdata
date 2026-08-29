# DarkPipe 0.12 preregistration — covariance-aware operator shadow

Status: `FROZEN_BEFORE_RESULT_INSPECTION` for the declared source, operator family, status rules, abstentions, and expected artifacts. Campaign: `DP-COVOP-0.12-20260829`.

## Governing question

Does the population-level weak-lensing acceleration surface remain numerically stable when the published SIS conversion is replaced by a discretized spherical deprojection integral and the **full published joint ESD covariance** is propagated through the paired operator difference?

This is an upstream operator-sensitivity question. It is not a dark-matter, modified-gravity, or plasma-hyperstate test, and it does not re-estimate the RAR stacked in baryonic-acceleration coordinates.

## Frozen data surface

Upstream: Brouwer et al. (2021), KiDS-1000 science-data release, CC BY 4.0. Selected files and SHA-256:

| File | SHA-256 |
|---|---|
| `README.txt` | `b3680580696c5dbf5671c700d5e8f90fbfd1dc614fa7e3e07b2f66d1624e8645` |
| `Fig-3_Lensing-rotation-curves_Massbin-1.txt` | `cd8171d248a5c660701c2fcfb5f39eea01ae57b5b9ec2bae233e5aef77e7d78e` |
| `Fig-3_Lensing-rotation-curves_Massbin-2.txt` | `279d82e4faee34041221b617f0ce9cfc97966c431616c94608b0983e60421ae7` |
| `Fig-3_Lensing-rotation-curves_Massbin-3.txt` | `88eca49e85504c1eb6ce11e09edcdda37c0903dd678f2207ed4bca4fa31f7a22` |
| `Fig-3_Lensing-rotation-curves_Massbin-4.txt` | `05853565ae193347adff22f8aec58c50f80b2e22866fb9c532137c6f198a79e1` |
| `Fig-3_Lensing-rotation-curves_Massbins_covmatrix.txt` | `e2568b34578a4752c4cdc25c23cd38c896ac1c5e0477cce3fe8d7b32e4954445` |

The four profiles contain 15 radii each. The covariance has 3,600 cells and must reconstruct a symmetric positive-definite 60×60 matrix after dividing every cell by the published multiplicative-bias product. The corrected diagonal must agree with `(error / bias)^2` to relative error below `2e-4`.

## Frozen operators

The published baseline is

\[
g_{\rm SIS}(R)=4G\,\Delta\Sigma(R).
\]

The conditional stack-first alternative is

\[
g_{\rm exact}^{\rm stack-first}(R)
=4G\int_0^{\pi/2}\Delta\Sigma^{\rm stacked}
\!\left(\frac{R}{\sin\theta}\right)d\theta.
\]

The integral is represented by a linear matrix `A` on the 15 published radii using 512-point Gauss–Legendre quadrature. Central interpolation is linear in physical radius. The central tail is SIS, `DeltaSigma(R > Rmax) = DeltaSigma(Rmax) Rmax/R`; the zero and flat tails form a sensitivity envelope. Quadratic interpolation with the SIS tail is the interpolation stress test. The flat tail is an intentionally extreme diagnostic boundary, not an asymptotically admissible physical model.

The unit conversion is reproduced from the upstream README: `4 * 4.52e-30 * 3.086e16` m s⁻² per `(h70 M_sun pc⁻²)`.

## Frozen covariance propagation

For corrected ESD vector `x`, covariance `C`, identity `I`, and block-diagonal deprojection matrix `A`:

\[
g_{\rm SIS}=Kx,\qquad g_{\rm exact}=KAx,
\]

\[
C_{\rm exact}=K^2ACA^T,
\qquad
C_{\rm exact-SIS}=K^2(A-I)C(A-I)^T.
\]

The paired per-bin statistic is `(g_exact - g_SIS) / sqrt(diag(C_exact-SIS))`. No diagonal-only substitute is allowed.

## Frozen status rules

For each of 60 bins:

- `NOT_ESTIMABLE_NONPOSITIVE_OR_DEGENERATE` if either central acceleration is non-positive or the paired variance is degenerate.
- `OPERATOR_DIFFERENCE_UNRESOLVED_SYSTEMATICS` if the larger of the tail half-span and the absolute quadratic–linear shift is at least as large as the central exact–SIS difference.
- Otherwise `OPERATOR_DIFFERENCE_RESOLVED_CONDITIONAL_95` when the absolute paired statistic is at least 1.9599639845.
- Otherwise `OPERATOR_DIFFERENCE_STATISTICALLY_UNRESOLVED_95`.

The published cross ESD is reported only as `ESD_x / tangential_error`. It cannot receive a global p-value because no cross-component covariance is published in this release.

## Mandatory abstentions and authority ceiling

The radial profiles are already stacked. Mistele et al. (2024) show that deproject-after-stack is not generally equal to deproject-before-stack when normalized lens weights vary with radius, although the two were close in their KiDS application. Therefore the output authority is `DERIVED_OPERATOR_SENSITIVITY_CONDITIONAL_STACK_FIRST_FULL_PUBLISHED_ESD_COVARIANCE_NOT_ONTOLOGIZED`.

Transfer to the Brouwer RAR table is fixed as `NOT_ESTIMABLE_DIFFERENT_STACKING_COORDINATE_NO_OBJECT_LEVEL_WEIGHTS`: the RAR is stacked at fixed `g_bar`, while these profiles are stacked at fixed physical radius. No result may be described as an exact object-level deprojection, independent confirmation, joint likelihood, model adjudication, gravity mechanism, or detection of a plasma hyperstate.

## Expected artifacts

- `covariance_operator_shadow.csv`
- `covariance_operator_matrices.npz`
- `covariance_operator_shadow.png`
- `summary.json`
- `SUBSTANTIVE_CLOSURE_ES.md`
- `manifest.json`
