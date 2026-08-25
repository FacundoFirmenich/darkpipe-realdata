# DarkPipe 0.8 endpoint-blind AION source inventory

Protocol ID: DP-AION-INDEPENDENT-INVENTORY-0.8-20260825

This preliminary gate establishes only whether the historical AION v1 HDF5 can
be acquired and parsed without storing it on the user's local disks. It is not
a scientific analysis or preregistration of a signal result.

- Source: Zenodo record 15166670, RID34056, collected 2024-12-13.
- Frozen file: `000034056-DifferentialClockInterferometryWithNoiseFrag.h5`.
- Frozen size: 564,439,752 bytes.
- Frozen MD5: `e7053ad0a8401c4198b4729feec8441c`.
- The source is downloaded only to the ephemeral GitHub Actions runner.
- The inventory records group and dataset paths, shapes, dtypes, chunks,
  compression and attribute schemas. It does not read dataset or attribute
  values.
- The raw HDF5 is deleted in a `finally` block and is never uploaded as an
  artifact or redistributed by DarkPipe.
- Zenodo exposes the record as open but declares no machine-readable reuse
  license. This protocol therefore preserves links and hashes only.

Adverse trace: run 32879047594 failed before downloading any HDF5 byte because
the current Zenodo API exposed the file URL under `links.self`, whereas the
first adapter expected `links.content`. PR 9 added explicit support for both
official representations plus a regression test. Run 32879655060 then passed
the full download, checksum, inventory, raw-removal and artifact gates in
3 minutes 6 seconds. The failed run remains public evidence.

The next scientific preregistration may be written only after this gate exposes
the exact storage schema. The 2024 endpoint values remain unopened until that
operator, quality rules, chronology, multiplicity correction and claim ceiling
are frozen in Git.
