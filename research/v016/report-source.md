# DarkPipe v0.16 source report — KiDS object reconstruction and RAR shadow

## Scope

This report fixes the primary-source basis for a bounded-memory reconstruction
of the KiDS lens/source selection used by Mistele et al. and for the derived
effective inobservable

\[
\eta=\log_{10}(g_{\rm obs}/g_{\rm bar}).
\]

It does not identify the physical nature of the inferred acceleration excess.

## Primary data surfaces

The [official KiDS-1000 weak-lensing catalogue page](https://kids.strw.leidenuniv.nl/DR4/KiDS-1000_shearcatalogue.php)
publishes the SOM-gold source catalogue and its five tomographic redshift
distributions.  The [official KiDS-bright page](https://kids.strw.leidenuniv.nl/DR4/brightsample.php)
publishes the 1,239,422-row lens redshift catalogue and the aligned LePhare
properties table.  That page defines `masked == 0` as the default lens mask,
documents the LePhare fluxscale correction, and states the `h^-2` luminosity
scaling of stellar masses.  KiDS public data products are distributed under
[CC BY 4.0 with acknowledgement and citation requirements](https://kids.strw.leidenuniv.nl/acknowledgements.php).
The native GAAP recovery uses ESO's official programmatic catalogue surface,
table `KiDS_DR4_0_ugriZYJHKs_cat_fits_V3`, through
[`https://archive.eso.org/tap_cat/sync`](https://archive.eso.org/tap_cat/sync).

## Analysis protocol from the papers

[Mistele et al. (2024)](https://arxiv.org/pdf/2310.15248) specify the lens cuts
`masked=0`, `0.1 < z_ANN < 0.5`, a 4 Mpc/h70 three-dimensional isolation
criterion against neighbours with at least ten per cent of the lens stellar
mass, and `log10(M*/Msun) < 11.1`, yielding 106,843 lenses.  They specify the
source cuts `SG_FLAG=1`, `SG2DPHOT=0`, `CLASS_STAR<0.5`, `IMAFLAGS_ISO=0`,
`MASK & 28668 = 0`, and the pair cut `Z_B,source > z_ANN,lens + 0.2`.

The same paper gives the exact spherical deprojection

\[
g_{\rm obs}(R)=4G\int_0^{\pi/2}\Delta\Sigma(R/\sin\theta)\,d\theta,
\]

the source-redshift and lens-redshift integration used for the critical surface
density, the 27 radial bins, the random-coordinate subtraction, the cross-shear
null channel, and the 15-bin published RAR used by this release.

[Brouwer et al. (2021)](https://arxiv.org/pdf/2106.11677) document the parent
isolation method, the proper critical surface density, proper transverse
separations, lensing weights, and the validation limit caused by photometric
redshift and flux-limit effects.  Their reported isolation accuracy is about
80 per cent; this is an adverse methodological boundary, not a removable
software error.

## What v0.16 establishes from real bytes

The source catalogue is held privately in Drive as 185 contiguous logical
ranges covering exactly 17,712,469,440 bytes.  Every range has a SHA-256 source
receipt and exact Drive object binding.  Two redundant objects are preserved
as adverse custody evidence.  The active Drive connector exposes file size and
identity but not a content hash, so v0.16 uses a partition-manifest root rather
than claiming an unavailable native Drive checksum or a linear full-file
SHA-256.

The HTTP-range FITS decoder verifies status 206, `Content-Range`, row width,
row count, field offsets, selected numeric/string decoding, and complete-row
alignment.  The two KiDS-bright tables align exactly by all 1,239,422 IDs and
to the declared coordinate/redshift tolerances.

The complete source-selection pass inspected all 21,262,011 rows and retained
19,109,925 after the declared star/quality/mask/finite-positive-weight gates.
The five best-fit tomographic counts are 1,727,608; 3,442,980; 5,624,220;
4,006,695; and 4,308,422.  Global shape-weighted means are
`<e1>=6.848058e-5` and `<e2>=5.402572e-4`; these are additive-bias diagnostics,
not a lensing detection.

The five official SOM `n(z)` tables were downloaded from the KiDS release
surface.  The v0.16 estimator now implements Eq. 10 of Mistele et al.: a
Gaussian lens-redshift uncertainty with `sigma=0.02*(1+z_ANN)`, the published
flat cosmology (`Omega_m=0.2793`, `H0=73 km/s/Mpc`), and source distributions
renormalized on `[z_l,infinity)`.  Across lens redshifts 0.1–0.5 and the five
tomographic bins, the effective critical surface density is finite and ranges
from 3.047e15 to 9.010e15 Msun/Mpc2.  This closes the calibration kernel, not
the pair accumulation or the scientific RAR reproduction.

The first physically concurrent-distance reconstruction returned 153,879
lenses, not 106,843.  That failed gate is retained as immutable adverse
evidence.  The successor analysis queried native `MAG_GAAP_u/r` photometry from
the official ESO catalogue service, first as a compact `MAG_AUTO < 21` table and
then as exact coordinate-box recovery for the 352 residual bright objects.  All
1,239,422 KiDS-bright rows matched within 0.5 arcsec; every row had finite native
GAAP photometry and no LePhare-derived fallback remained.  Under the
legacy-style angular-diameter-distance Cartesian isolation geometry, the result
is exactly 106,843 lenses (delta zero).  Neither the 4 Mpc/h70 radius nor the
mass threshold was tuned.  This closes the operational lens-selection gate and
identifies the earlier discrepancy as the conjunction of non-native photometry
and a different distance convention; it is not a weak-lensing measurement.
The public repository carries the exact TAP queries, source hashes and compact
receipts, but not the opaque FITS fragments or NumPy selection vectors; those
remain local/private and are regenerated from the official data service.

From the published real 15-bin RAR, v0.16 derives `eta` from 0.76 to 2.17 dex,
equivalent to an effective acceleration enhancement from 5.75 to 147.91 over
the tabulated range.  Every bin has positive effective excess acceleration.
The diagonal-weighted descriptive slope is 0.511; it is not a global fit claim
because the cross-bin covariance is unavailable.  A reference MOND-shaped
mapping has a median residual of 0.008 dex, but neither this agreement nor the
acceleration excess identifies an ontology.

## Evidence boundary and next gate

The published bin-level inobservable is real.  The lens selection, full source
attrition and effective critical-density kernel are now independently closed;
a from-scratch object-level RAR is not.  The decisive remaining surface is the
full lens-source pair accumulation with footprint-matched random subtraction,
cross-shear null and covariance.  Only after that gate may a predeclared
plasma-sensitive shadow be joined and compared under an explicit
forward-prediction contract.  Lensing alone cannot decide between particle
dark matter, a concrete modified-gravity realization, baryonic systematics, or
the project's morphotopological plasma conjecture.
