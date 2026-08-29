# DarkPipe 0.14 — remote acquisition and object-level compute gate

Status: `FROZEN_BEFORE_FULL_INPUT_ACQUISITION`  
Campaign: `DP-REMOTE-OBJ-0.14`

## Governing objective

Move from v0.13's proof that the public KiDS inputs are structurally recoverable
to an evidence-preserving remote acquisition and an object-level weak-lensing
calculation. No full catalogue may be stored on the user's workstation.

This release candidate separates three authorities:

1. **G1 byte custody**: exact remote files, byte counts, SHA-256 receipts and
   restartable transfer.
2. **G2 compute-kernel validity**: pair geometry, critical surface density,
   individual-lens ESD, cross channel and deproject-before-stack operator.
3. **G3 scientific reconstruction**: survey selections, calibrated source
   redshift distributions, random coordinates, multiplicative calibration,
   isolation selection and published-RAR equivalence.

The current implementation targets G1 and the reusable numerical part of G2.
It does not claim that G3 has run.

## Frozen G1 protocol

The acquisition command must run on a remote filesystem with at least 40 GiB
free and must receive both:

- `--execution-jurisdiction REMOTE_COMPUTE_AND_STORAGE_ONLY`
- `--acknowledge-upstream-terms`

The acknowledgement records the operator's decision; it does not relicense
KiDS products. Downloads use 64 MiB HTTP ranges by default. Each completed
range is flushed with `fsync`; a JSON checkpoint is replaced atomically.
Resume begins from the exact partial-file byte count. A change in total source
size is an adverse drift and aborts the acquisition. Only after expected size
and full-file SHA-256 are established is `.partial` atomically renamed.

A completed receipt records source URL, expected and observed size, digest,
time, resume offset, request count, authority and licensing boundary. Partial
files remain operational state and are never admitted as scientific inputs.

## Frozen G2 kernel

For a lens-source pair, the critical surface density is

\[
\Sigma_{\rm crit}=
\frac{c^2}{4\pi G}\frac{D_s}{D_lD_{ls}},
\]

and foreground or equal-redshift pairs receive infinite critical density and
therefore zero statistical contribution. Tangential and 45-degree cross
ellipticities are rotated from the source ellipticity using the pair position
angle.

The pair weight is

\[
W_{ls}=w_s\Sigma_{\rm crit}^{-2}.
\]

For each lens and radial bin, the implementation accumulates

\[
\Delta\Sigma_l=
\frac{\sum_s W_{ls}\Sigma_{\rm crit}\epsilon_{t,ls}}
     {\sum_s W_{ls}(1+m_s)}.
\]

The identical operator applied to the cross component is a null channel, not a
secondary signal. Invalid, foreground and non-positive-weight pairs are typed
out rather than silently imputed.

The spherical transform is applied separately to each lens:

\[
g_{{\rm obs},l}(R)=4G\int_0^{\pi/2}
\Delta\Sigma_l(R/\sin\theta)\,d\theta,
\]

then evaluated at

\[
R_l(g_{\rm bar})=\sqrt{GM_{b,l}/g_{\rm bar}},
\]

and only then stacked. Inner and outer extrapolation slopes are mandatory
preregistered arguments. The software contains no hidden slope defaults.

## Tests and their limits

Structural byte fixtures verify resume, size-drift rejection and custody
receipts. Analytic numerical tests verify foreground rejection, spin-2
rotation, pair accumulation, separation of the cross channel and the exact
deprojection of a \(\Delta\Sigma\propto R^{-1}\) profile. These controlled
fixtures are legitimate software tests and are not scientific observations.

## G3 blockers preserved

Scientific reconstruction remains blocked until all are fixed and executed:

- remote filesystem/VPS identity and capacity receipt;
- complete G1 input receipts;
- exact KiDS source tomographic assignment and calibrated n(z) integration;
- survey mask and isolation implementation;
- frozen random-coordinate seed, footprint and redshift construction;
- published multiplicative-shear calibration convention;
- object-selection and attrition ledger;
- random and cross-null acceptance gates;
- comparison with the published 15-bin RAR.

Until then the scientific state is
`OBJECT_LEVEL_SCIENTIFIC_RECONSTRUCTION_NOT_YET_EXECUTED`.

## Model boundary

Even successful G1–G3 would reconstruct a lensing relation; it would not
identify the proposed morphotopological plasma system. Model comparison remains
`NOT_ESTIMABLE_MODEL_NOT_YET_DIFFERENTIALLY_PREDICTIVE` until the signed,
scaled and falsifiable differential contract created in v0.13 is completed
before joint-map inspection.
