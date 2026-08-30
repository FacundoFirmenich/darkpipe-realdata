# DarkPipe 0.15 — Google Drive sharded custody

Status: FROZEN_BEFORE_FULL_INPUT_ACQUISITION  
Campaign: DP-DRIVE-SHARDS-0.15

## Correction to the v0.14 storage assumption

The 40 GiB v0.14 gate mixed two distinct requirements: durable byte custody and
a monolithic scientific scratch filesystem. Google Drive can provide the first
without allocating 40 GiB on the user's workstation or on a VPS.

The four frozen KiDS inputs total 18,059,551,240 bytes (16.819 GiB). A fresh
Drive acquisition requires that amount plus a 1 GiB safety margin: approximately
17.819 GiB of observed free Drive quota. On resume, only the undeclared remainder
plus the margin is required.

## Frozen transport

Each dataset is divided into independent 256 MiB HTTP ranges by default. Every
range is written directly to the mounted Drive destination as a partial shard,
flushed, size-checked, SHA-256 hashed and atomically renamed. The manifest is
updated transactionally after each admitted shard.

A rerun verifies the size and SHA-256 of every manifest-authorized shard before
reusing it. Missing, modified, orphaned or geometrically inconsistent shards
abort rather than being silently repaired. Upstream total-size drift also
aborts. At completion the implementation reads the ordered shards without
reassembling them and computes both:

- the SHA-256 of the original logical byte stream;
- a canonical manifest-root SHA-256 over source identity, geometry and shard
  digests.

The complete catalogue is never created on the user's local disk. The bounded
working payload is one shard in process memory; the temporary shard lives in
Drive next to its final name.

## Quota evidence and authority

The caller must supply an observed free-byte value obtained from Google Drive
API storageQuota and must declare USER_GOOGLE_DRIVE_SHARDED_CUSTODY. The value
is recorded as supplied observational evidence, not confused with capability or
permission.

Running the Colab transfer cell records acknowledgement of upstream terms. It
does not relicense or redistribute KiDS products. Raw shards remain private in
the user's Drive unless the user independently changes sharing.

## What this solves

This removes the unidentified 40 GiB VPS as a prerequisite for G1 byte custody.
The acquisition survives Colab interruption because complete shards and the
manifest persist in Drive. Re-running the notebook continues at the first
missing shard.

## What this does not solve

Drive shards are a custody representation, not yet an analysis-optimized
catalogue. Google Drive is high-latency and lacks the random-access semantics
needed for efficient FITS table analysis. Object-level science still requires a
second, separately validated gate that streams the logical file or converts it
into analysis-ready sky/tomographic partitions without moving the full source
catalogue onto the workstation.

No KiDS bytes have been acquired by CI. No RAR has been reconstructed. The
scientific state remains
OBJECT_LEVEL_SCIENTIFIC_RECONSTRUCTION_NOT_YET_EXECUTED and the
plasma-morphotopological conjecture remains
NOT_ESTIMABLE_MODEL_NOT_YET_DIFFERENTIALLY_PREDICTIVE.

## Tests

Controlled byte fixtures test exact sharding, tail geometry, quota arithmetic,
resume without redownload, full logical SHA-256, manifest-root custody, tamper
rejection and source-size drift. They validate software behavior only and are
not observational evidence.
