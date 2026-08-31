# DarkPipe v0.17 — adverse native-GAAP provenance ledger

Three reruns exposed that the v0.16 reconstruction executable could write a
pair payload even when its supplement set was incomplete.  They are retained
as causal evidence, not deleted or reinterpreted:

| rerun | native coverage | native selection | delta from 106,843 | cause |
|---|---:|---:|---:|---|
| `MAG_AUTO<20` plus wrong supplement family | 1,170,882 / 1,239,422 | 103,600 | -3,243 | truncated TAP parent and incomplete supplement provenance |
| `MAG_AUTO<21` plus 80-row family only | 1,239,150 / 1,239,422 | 106,876 | +33 | missing complementary 272 rows |
| `MAG_AUTO<21` plus 272-row family only | 1,239,342 / 1,239,422 | 106,766 | -77 | missing complementary 80 rows |

The successful reconstruction uses both disjoint supplement families: 55 FITS
parts containing 272 rows and 16 FITS parts containing 80 rows.  It reaches
1,239,422/1,239,422 native-GAAP rows, reproduces exactly 106,843 selected
lenses and emits payload SHA-256
`3c4a43f9516e438a9c35e098ddd3d37768180f9d84e08fb01d73924c899c2b0a`.

The repair is operational: `require_authoritative_native_selection` now raises
before writing any pair input unless both complete coverage and the published
count are exact.  These adverse outcomes therefore improve the provenance and
authority boundary; they do not constitute lensing results.
