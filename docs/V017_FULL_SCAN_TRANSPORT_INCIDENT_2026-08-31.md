# KiDS v0.17 full-scan transport incident — 2026-08-31

## Observed result

The first exact eight-partition GitHub Actions scan, run `33393229975`, did not
complete. Partitions `04` and `07` terminated after the public KiDS server
closed an HTTP range connection without a response. The traceback in both jobs
ended in `requests.exceptions.ConnectionError` with `RemoteDisconnected`.

This is an operational transport failure. It is not evidence of a FITS layout
change, a source-selection discrepancy, a lens-selection discrepancy, a
pair-geometry defect, or a scientific result. Successful partitions remain
independent additive sufficient statistics and are not invalidated by these two
failures.

## Repair and preserved boundary

The bounded FITS range reader now retries only request exceptions and HTTP
`429`, `500`, `502`, `503`, and `504`, for at most six attempts with exponential
backoff. Every successful response must still be an exact HTTP `206`, must carry
the expected `Content-Range`, and must contain the exact requested byte count.
Any structural mismatch aborts immediately and is never converted into a
transport retry.

The workflow can now select exact partition labels for repair runs and uploads
the latest checkpoint even when a computation step fails. This allows failed
work to be inspected or resumed without re-running valid partitions and without
persisting the 17.7 GB public source catalogue on local disk.

The merger also enforces the blind ordering explicitly: it reads and validates
only partition metadata first, requires the frozen eight contiguous intervals,
cross-partition invariants, and the exact 988-`THELI_NAME` union, and only then opens
the tangential/cross sufficient-statistic arrays. An incomplete surface cannot
reach the numerical merge layer.

## Cross-run radial-edge divergence

After transport repair, all eight row partitions completed. The metadata-first
merge then found that `numpy.geomspace(0.003, 11.94, 28)` had produced one-ULP
differences in two radial edges across otherwise equivalent GitHub runners.
No signal array was opened by the merger. The difference is numerically tiny,
but the available sufficient statistics cannot prove that no pair lay in the
one-ULP interval, so the eight-part surface is preserved as adverse and is not
promoted.

The 28 edges are now frozen as explicit float64 literals and their little-endian
binary SHA-256 is part of every partition and merge invariant. A complete new
eight-part scan is required; tolerance-based retrospective merging is forbidden.

## Survey-footprint versus THELI-pointing distinction

The clean rerun then exposed a second adverse metadata result: its complete
SOM-gold `THELI_NAME` union contains 988 reduction pointings, not 1006 survey
tiles. The numerical arrays were again not opened. The official DR4 multi-band
catalogue download manifest contains exactly 1006 entries; every one of the 988
THELI names maps inside that set, while 18 official survey tiles do not occur as
distinct THELI identifiers. The current observations table additionally lists
nine fields outside the frozen 1006-entry release manifest.

The two geometries are therefore no longer conflated. A complete signal scan
must prove the 988-THELI surface. Random coordinates use the independent exact
1006-tile official survey footprint required by the published method. Neither
count is relaxed or retrospectively fitted to the signal.

## Authority boundary

The repair authorizes a targeted re-execution of failed transport partitions.
It does not authorize merging to `main`, publishing a release, inspecting
blinded signal arrays prematurely, or making a RAR, dark-matter, plasma, or
cosmological claim. Scientific authority remains closed until all eight exact
partitions, the frozen 1006-tile random catalogue, random subtraction,
covariance, deprojection, and equivalence gates are complete.
