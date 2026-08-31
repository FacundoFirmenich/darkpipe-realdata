# DarkPipe v0.17 — preregistration of the KiDS orientation diagnostic

## Reason for the diagnostic

The first authentic object-level RAR fails to reproduce the Mistele et al.
(2024) Table 1 surface.  The raw SIS, stack-first branch also fails by about one
dex, so the failure is upstream of exact deprojection.  The official KiDS weak
lensing documentation explicitly warns that the sign of catalog `e2` depends
on the angle convention adopted in the RA/Dec frame.  A wrong sign would rotate
a true tangential pattern into a `cos(4 phi)` pattern and largely cancel it.

## Frozen data slice

Before inspecting any convention result, the diagnostic fixes eight disjoint
intervals of 12,500 authentic source rows, beginning at
`floor(i * 21262011 / 8)` for `i=0,...,7`.  Thus 100,000 rows are read by exact
HTTP byte ranges across the full source-table ordering.  The FITS is never
stored locally.  Lens selection, source cuts, radial edges, Sigma-critical
lookup and multiplicative response remain identical to the completed signal
surface.

## Frozen conventions

With `phi` measured counter-clockwise from local east and with basis terms
`e1*cos(2phi)`, `e1*sin(2phi)`, `e2*cos(2phi)`, `e2*sin(2phi)`, the following
four transformations are evaluated without fitting a free rotation:

1. `east_ccw_catalog_e2_as_math`: the current implementation.
2. `east_ccw_catalog_e2_sign_flipped`: the documented KiDS `e2` sign transform.
3. `north_ccw_catalog_e2_as_math`: angle measured from north.
4. `north_ccw_catalog_e2_sign_flipped`: north reference plus the `e2` transform.

The four candidates reduce to two tangential amplitudes up to overall sign, but
all are retained so that axis origin and catalog sign are explicit rather than
silently conflated.

## Decision rule and jurisdiction

For each convention, the same raw SIS stack-first RAR is built on the published
Mistele Table 1 `g_bar` grid.  The diagnostic reports positive-bin count,
median absolute log difference where both values are positive, published-envelope
coverage, and the cross-channel maximum diagonal z-score.  A convention is a
repair candidate only if it materially improves the authentic tangential
amplitude while retaining a cross channel compatible with zero.  This bounded
slice can localize a convention defect; it cannot validate the final RAR,
replace the full source scan, replace the frozen 50x random control, or support
any plasma/dark-matter interpretation.

Authority: `PREREGISTERED_BOUNDED_ORIENTATION_DIAGNOSTIC_NO_SCIENTIFIC_ADJUDICATION`.

## Escalation fixed after the bounded result and before the full-basis scan

The 100,000-row diagnostic was too noisy to select a convention: none passed
reproduction and its current-convention curve was itself inconsistent with the
completed 21,262,011-row result.  The eight original full partitions were then
recovered and their exact merge was verified bit for bit; all eight remained
adverse.  This justifies one full rescan that retains the four orientation basis
terms.  The escalation does not alter any source, lens, weight, cut or radial
bin and does not overwrite the historical pair surface.

Before opening that full result, a convention is fixed as a **repair candidate**
only if it (a) improves the current convention's median absolute log difference
by at least 0.30 dex in the exact RAR, (b) has at least 13 positive central bins,
and (c) retains `max(abs(cross/diagonal_sigma)) < 3`.  This is a localization
gate, not the final reproduction gate and not permission to interpret the RAR.
