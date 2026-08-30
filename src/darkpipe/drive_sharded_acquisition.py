"""Google-Drive-sharded, resumable byte custody for DarkPipe inputs.

The module stores each immutable HTTP byte range as an independently hashed
file in a mounted Google Drive directory. It never creates a complete local
catalogue and never treats a shard or a custody receipt as scientific evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Callable, Iterable
from urllib.request import urlopen

from .object_recoverability import DEFAULT_DATASETS, DatasetSpec
from .remote_acquisition import (
    AcquisitionError,
    _read_range,
    _utc_now,
    _write_json_atomic,
)


DRIVE_SHARDED_JURISDICTION = "USER_GOOGLE_DRIVE_SHARDED_CUSTODY"
DRIVE_SHARD_AUTHORITY = "BYTE_CUSTODY_SHARDED_DRIVE_ONLY_NO_SCIENTIFIC_RESULT"
DEFAULT_DRIVE_SHARD_BYTES = 256 * 1024 * 1024
DEFAULT_DRIVE_SAFETY_MARGIN_BYTES = 1024**3
MANIFEST_SCHEMA = "darkpipe.drive-shards.v1"


@dataclass(frozen=True)
class DriveDatasetReceipt:
    dataset_id: str
    source_url: str
    destination_directory: str
    expected_bytes: int
    observed_bytes: int
    shard_bytes: int
    shard_count: int
    reused_shards: int
    http_range_requests: int
    full_sha256: str
    manifest_root_sha256: str
    manifest_path: str
    completed_at_utc: str
    execution_jurisdiction: str = DRIVE_SHARDED_JURISDICTION
    authority: str = DRIVE_SHARD_AUTHORITY
    upstream_terms_acknowledged: bool = True
    license_reasserted: bool = False
    complete_file_reassembled: bool = False


def plan_shards(total_bytes: int, shard_bytes: int) -> tuple[tuple[int, int, int], ...]:
    if total_bytes <= 0:
        raise ValueError("total_bytes must be positive")
    if shard_bytes <= 0:
        raise ValueError("shard_bytes must be positive")
    count = (total_bytes + shard_bytes - 1) // shard_bytes
    return tuple(
        (
            index,
            index * shard_bytes,
            min((index + 1) * shard_bytes, total_bytes) - 1,
        )
        for index in range(count)
    )


def assert_drive_quota(
    *,
    expected_remaining_bytes: int,
    observed_drive_free_bytes: int,
    safety_margin_bytes: int = DEFAULT_DRIVE_SAFETY_MARGIN_BYTES,
) -> dict[str, int | str]:
    if expected_remaining_bytes < 0:
        raise ValueError("expected_remaining_bytes cannot be negative")
    if observed_drive_free_bytes < 0:
        raise ValueError("observed_drive_free_bytes cannot be negative")
    if safety_margin_bytes < 0:
        raise ValueError("safety_margin_bytes cannot be negative")
    required = expected_remaining_bytes + safety_margin_bytes
    if observed_drive_free_bytes < required:
        raise AcquisitionError(
            "Google Drive quota gate failed: "
            f"free={observed_drive_free_bytes}, required={required}"
        )
    return {
        "quota_source": "GOOGLE_DRIVE_API_VALUE_SUPPLIED_BY_CALLER",
        "observed_drive_free_bytes": observed_drive_free_bytes,
        "expected_remaining_bytes": expected_remaining_bytes,
        "safety_margin_bytes": safety_margin_bytes,
        "required_drive_free_bytes": required,
    }


def _sha256_file(path: Path, block_bytes: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(block_bytes):
            digest.update(chunk)
    return digest.hexdigest()


def _shard_name(index: int, count: int, start: int, stop: int) -> str:
    return (
        f"shard-{index:05d}-of-{count:05d}-"
        f"{start:012d}-{stop:012d}.bin"
    )


def _identity(spec: DatasetSpec, shard_bytes: int) -> dict[str, Any]:
    return {
        "dataset_id": spec.dataset_id,
        "source_url": spec.url,
        "expected_total_bytes": spec.expected_total_bytes,
        "shard_bytes": shard_bytes,
    }


def _new_manifest(spec: DatasetSpec, shard_bytes: int) -> dict[str, Any]:
    return {
        "schema_version": MANIFEST_SCHEMA,
        **_identity(spec, shard_bytes),
        "authority": DRIVE_SHARD_AUTHORITY,
        "execution_jurisdiction": DRIVE_SHARDED_JURISDICTION,
        "status": "IN_PROGRESS",
        "shards": [],
        "updated_at_utc": _utc_now(),
    }


def _load_manifest(path: Path, spec: DatasetSpec, shard_bytes: int) -> dict[str, Any]:
    if not path.exists():
        return _new_manifest(spec, shard_bytes)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AcquisitionError(f"cannot read shard manifest: {path}") from exc
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise AcquisitionError("shard manifest schema mismatch")
    for key, value in _identity(spec, shard_bytes).items():
        if manifest.get(key) != value:
            raise AcquisitionError(f"shard manifest identity mismatch: {key}")
    shards = manifest.get("shards")
    if not isinstance(shards, list):
        raise AcquisitionError("shard manifest has no valid shards list")
    indexes = [entry.get("index") for entry in shards]
    if len(indexes) != len(set(indexes)):
        raise AcquisitionError("shard manifest contains duplicate indexes")
    return manifest


def _manifest_root(manifest: dict[str, Any]) -> str:
    payload = {
        key: manifest[key]
        for key in (
            "schema_version",
            "dataset_id",
            "source_url",
            "expected_total_bytes",
            "shard_bytes",
        )
    }
    payload["shards"] = [
        {
            key: entry[key]
            for key in (
                "index",
                "start",
                "stop",
                "observed_bytes",
                "sha256",
                "filename",
            )
        }
        for entry in sorted(manifest["shards"], key=lambda item: item["index"])
    ]
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validate_existing_shard(
    directory: Path,
    entry: dict[str, Any],
    *,
    index: int,
    start: int,
    stop: int,
    count: int,
) -> Path:
    expected_name = _shard_name(index, count, start, stop)
    expected_bytes = stop - start + 1
    if (
        entry.get("index") != index
        or entry.get("start") != start
        or entry.get("stop") != stop
        or entry.get("filename") != expected_name
        or entry.get("observed_bytes") != expected_bytes
    ):
        raise AcquisitionError(f"shard manifest geometry mismatch at index {index}")
    path = directory / expected_name
    if not path.is_file():
        raise AcquisitionError(f"shard manifest references missing file: {expected_name}")
    if path.stat().st_size != expected_bytes:
        raise AcquisitionError(f"existing shard size mismatch: {expected_name}")
    digest = _sha256_file(path)
    if digest != entry.get("sha256"):
        raise AcquisitionError(f"existing shard hash mismatch: {expected_name}")
    return path


def _full_sha256(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        with path.open("rb") as stream:
            while chunk := stream.read(8 * 1024 * 1024):
                digest.update(chunk)
    return digest.hexdigest()


def acquire_dataset_sharded(
    spec: DatasetSpec,
    root: Path,
    *,
    acknowledge_upstream_terms: bool,
    execution_jurisdiction: str,
    shard_bytes: int = DEFAULT_DRIVE_SHARD_BYTES,
    timeout: float = 180.0,
    max_attempts: int = 4,
    opener: Callable[..., Any] = urlopen,
) -> DriveDatasetReceipt:
    """Acquire one dataset as independently verified Drive-resident shards."""

    if not acknowledge_upstream_terms:
        raise AcquisitionError("upstream acknowledgement is required")
    if execution_jurisdiction != DRIVE_SHARDED_JURISDICTION:
        raise AcquisitionError("Drive-sharded custody jurisdiction is required")
    layout = plan_shards(spec.expected_total_bytes, shard_bytes)
    count = len(layout)
    directory = root / spec.dataset_id
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "shard-manifest.json"
    receipt_path = directory / "dataset-receipt.json"
    manifest = _load_manifest(manifest_path, spec, shard_bytes)
    by_index = {int(entry["index"]): entry for entry in manifest["shards"]}

    reused = 0
    requests_made = 0
    ordered_paths: list[Path] = []

    for index, start, stop in layout:
        existing = by_index.get(index)
        if existing is not None:
            ordered_paths.append(
                _validate_existing_shard(
                    directory,
                    existing,
                    index=index,
                    start=start,
                    stop=stop,
                    count=count,
                )
            )
            reused += 1
            continue

        name = _shard_name(index, count, start, stop)
        final_path = directory / name
        temporary_path = directory / f"{name}.partial"
        if final_path.exists():
            raise AcquisitionError(
                f"orphan shard exists without manifest authority: {name}"
            )

        last_error: Exception | None = None
        payload: bytes | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                payload, total, _ = _read_range(
                    spec.url,
                    start,
                    stop,
                    timeout=timeout,
                    opener=opener,
                )
                requests_made += 1
                if total != spec.expected_total_bytes:
                    raise AcquisitionError(
                        f"source size drift: {total} != {spec.expected_total_bytes}"
                    )
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                if attempt < max_attempts:
                    time.sleep(min(2 ** (attempt - 1), 8))
        if last_error is not None:
            if isinstance(last_error, AcquisitionError):
                raise last_error
            raise AcquisitionError(
                f"Drive shard acquisition failed at index {index}"
            ) from last_error
        if payload is None:
            raise AcquisitionError(f"no payload returned for shard {index}")

        with temporary_path.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if temporary_path.stat().st_size != stop - start + 1:
            raise AcquisitionError(f"written shard size mismatch: {name}")
        digest = _sha256_file(temporary_path)
        os.replace(temporary_path, final_path)
        entry = {
            "index": index,
            "start": start,
            "stop": stop,
            "observed_bytes": stop - start + 1,
            "sha256": digest,
            "filename": name,
            "completed_at_utc": _utc_now(),
        }
        manifest["shards"].append(entry)
        manifest["shards"].sort(key=lambda item: item["index"])
        manifest["updated_at_utc"] = _utc_now()
        manifest["status"] = "IN_PROGRESS"
        _write_json_atomic(manifest_path, manifest)
        by_index[index] = entry
        ordered_paths.append(final_path)

    observed = sum(path.stat().st_size for path in ordered_paths)
    if observed != spec.expected_total_bytes:
        raise AcquisitionError(
            f"sharded dataset has wrong total size: {observed} != "
            f"{spec.expected_total_bytes}"
        )
    full_digest = _full_sha256(ordered_paths)
    root_digest = _manifest_root(manifest)
    manifest.update(
        {
            "status": "COMPLETE_BYTE_CUSTODY",
            "observed_total_bytes": observed,
            "full_sha256": full_digest,
            "manifest_root_sha256": root_digest,
            "updated_at_utc": _utc_now(),
            "complete_file_reassembled": False,
            "scientific_result": False,
        }
    )
    _write_json_atomic(manifest_path, manifest)

    receipt = DriveDatasetReceipt(
        dataset_id=spec.dataset_id,
        source_url=spec.url,
        destination_directory=str(directory.resolve()),
        expected_bytes=spec.expected_total_bytes,
        observed_bytes=observed,
        shard_bytes=shard_bytes,
        shard_count=count,
        reused_shards=reused,
        http_range_requests=requests_made,
        full_sha256=full_digest,
        manifest_root_sha256=root_digest,
        manifest_path=str(manifest_path.resolve()),
        completed_at_utc=_utc_now(),
    )
    _write_json_atomic(receipt_path, asdict(receipt))
    return receipt


def declared_completed_bytes(
    root: Path,
    *,
    datasets: Iterable[DatasetSpec],
    shard_bytes: int,
) -> int:
    total = 0
    for spec in datasets:
        path = root / spec.dataset_id / "shard-manifest.json"
        if not path.exists():
            continue
        manifest = _load_manifest(path, spec, shard_bytes)
        for entry in manifest["shards"]:
            shard_path = path.parent / str(entry.get("filename", ""))
            observed = int(entry.get("observed_bytes", -1))
            if shard_path.is_file() and observed >= 0 and shard_path.stat().st_size == observed:
                total += observed
    return total


def acquire_default_inputs_to_drive(
    root: Path,
    *,
    observed_drive_free_bytes: int,
    acknowledge_upstream_terms: bool,
    execution_jurisdiction: str,
    datasets: Iterable[DatasetSpec] = DEFAULT_DATASETS,
    shard_bytes: int = DEFAULT_DRIVE_SHARD_BYTES,
    safety_margin_bytes: int = DEFAULT_DRIVE_SAFETY_MARGIN_BYTES,
) -> dict[str, Any]:
    selected = tuple(datasets)
    expected_total = sum(spec.expected_total_bytes for spec in selected)
    declared_existing = declared_completed_bytes(
        root,
        datasets=selected,
        shard_bytes=shard_bytes,
    )
    quota = assert_drive_quota(
        expected_remaining_bytes=expected_total - declared_existing,
        observed_drive_free_bytes=observed_drive_free_bytes,
        safety_margin_bytes=safety_margin_bytes,
    )
    receipts = [
        acquire_dataset_sharded(
            spec,
            root,
            acknowledge_upstream_terms=acknowledge_upstream_terms,
            execution_jurisdiction=execution_jurisdiction,
            shard_bytes=shard_bytes,
        )
        for spec in selected
    ]
    payload = {
        "campaign": "DP-DRIVE-SHARDS-0.15",
        "generated_at_utc": _utc_now(),
        "authority": DRIVE_SHARD_AUTHORITY,
        "execution_jurisdiction": DRIVE_SHARDED_JURISDICTION,
        "quota_gate": quota,
        "expected_total_bytes": expected_total,
        "declared_existing_bytes_at_start": declared_existing,
        "receipts": [asdict(receipt) for receipt in receipts],
        "all_inputs_complete": len(receipts) == len(selected),
        "complete_files_reassembled": False,
        "local_heavy_dataset_file_created": False,
        "scientific_result": False,
        "next_gate": "STREAM_OR_PARTITION_SHARDS_FOR_OBJECT_LEVEL_RECONSTRUCTION",
    }
    _write_json_atomic(root / "drive-acquisition-manifest.json", payload)
    return payload


__all__ = [
    "DEFAULT_DRIVE_SAFETY_MARGIN_BYTES",
    "DEFAULT_DRIVE_SHARD_BYTES",
    "DRIVE_SHARD_AUTHORITY",
    "DRIVE_SHARDED_JURISDICTION",
    "DriveDatasetReceipt",
    "acquire_dataset_sharded",
    "acquire_default_inputs_to_drive",
    "assert_drive_quota",
    "declared_completed_bytes",
    "plan_shards",
]
