"""Resumable, evidence-preserving acquisition for DarkPipe remote inputs.

This module is intentionally filesystem-target agnostic.  It refuses to start
unless the caller declares a remote execution jurisdiction, acknowledges the
upstream terms, and the target filesystem has the preregistered free capacity.
It never treats a partial file as a scientific input.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from typing import Any, Callable, Iterable
from urllib.request import Request, urlopen

from .object_recoverability import DEFAULT_DATASETS, DatasetSpec


REMOTE_JURISDICTION = "REMOTE_COMPUTE_AND_STORAGE_ONLY"
ACQUISITION_AUTHORITY = "BYTE_CUSTODY_ONLY_NO_SCIENTIFIC_RESULT"
DEFAULT_CHUNK_BYTES = 64 * 1024 * 1024
DEFAULT_MIN_FREE_GIB = 40


class AcquisitionError(RuntimeError):
    """Raised when byte custody cannot be established exactly."""


@dataclass(frozen=True)
class AcquisitionReceipt:
    dataset_id: str
    source_url: str
    destination: str
    expected_bytes: int
    observed_bytes: int
    sha256: str
    completed_at_utc: str
    resumed_from_bytes: int
    http_range_requests: int
    authority: str = ACQUISITION_AUTHORITY
    upstream_terms_acknowledged: bool = True
    license_reasserted: bool = False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path, *, block_bytes: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(block_bytes):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def assert_remote_capacity(
    root: Path,
    *,
    expected_input_bytes: int,
    minimum_free_gib: int = DEFAULT_MIN_FREE_GIB,
    execution_jurisdiction: str,
) -> dict[str, int | str]:
    if execution_jurisdiction != REMOTE_JURISDICTION:
        raise AcquisitionError(
            "acquisition refused: execution jurisdiction must be "
            f"{REMOTE_JURISDICTION}"
        )
    root.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(root)
    required = max(expected_input_bytes, minimum_free_gib * 1024**3)
    if usage.free < required:
        raise AcquisitionError(
            f"remote capacity gate failed: free={usage.free}, required={required}"
        )
    return {
        "root": str(root.resolve()),
        "free_bytes": usage.free,
        "required_bytes": required,
        "execution_jurisdiction": execution_jurisdiction,
    }


def _content_range_total(headers: Any) -> int | None:
    value = headers.get("Content-Range") or headers.get("content-range")
    if not value or "/" not in value:
        return None
    suffix = value.rsplit("/", 1)[1]
    return int(suffix) if suffix.isdigit() else None


def _read_range(
    url: str,
    start: int,
    stop: int,
    *,
    timeout: float,
    opener: Callable[..., Any],
) -> tuple[bytes, int | None, int]:
    request = Request(
        url,
        headers={
            "Range": f"bytes={start}-{stop}",
            "User-Agent": "DarkPipe-v0.14-remote-acquisition",
            "Accept-Encoding": "identity",
        },
    )
    with opener(request, timeout=timeout) as response:
        status = int(getattr(response, "status", response.getcode()))
        payload = response.read(stop - start + 1)
        total = _content_range_total(response.headers)
    if status != 206:
        raise AcquisitionError(f"range request returned HTTP {status}, expected 206")
    if total is None:
        raise AcquisitionError("range response omitted a usable Content-Range total")
    expected = stop - start + 1
    if len(payload) != expected:
        raise AcquisitionError(
            f"short range read at {start}: received={len(payload)}, expected={expected}"
        )
    return payload, total, status


def acquire_dataset(
    spec: DatasetSpec,
    root: Path,
    *,
    acknowledge_upstream_terms: bool,
    execution_jurisdiction: str,
    chunk_bytes: int = DEFAULT_CHUNK_BYTES,
    timeout: float = 180.0,
    max_attempts: int = 4,
    opener: Callable[..., Any] = urlopen,
) -> AcquisitionReceipt:
    """Download one immutable input with restartable range requests and receipt."""

    if not acknowledge_upstream_terms:
        raise AcquisitionError("upstream acknowledgement is required")
    if execution_jurisdiction != REMOTE_JURISDICTION:
        raise AcquisitionError("local heavy acquisition is prohibited")
    if chunk_bytes <= 0:
        raise ValueError("chunk_bytes must be positive")

    root.mkdir(parents=True, exist_ok=True)
    suffix = Path(spec.url).name or f"{spec.dataset_id}.bin"
    final_path = root / suffix
    partial_path = root / f"{suffix}.partial"
    state_path = root / f"{suffix}.partial.json"
    receipt_path = root / f"{suffix}.receipt.json"

    if final_path.exists():
        observed = final_path.stat().st_size
        if observed != spec.expected_total_bytes:
            raise AcquisitionError(
                f"existing final file has wrong size: {observed} != "
                f"{spec.expected_total_bytes}"
            )
        digest = _sha256_file(final_path)
        receipt = AcquisitionReceipt(
            dataset_id=spec.dataset_id,
            source_url=spec.url,
            destination=str(final_path.resolve()),
            expected_bytes=spec.expected_total_bytes,
            observed_bytes=observed,
            sha256=digest,
            completed_at_utc=_utc_now(),
            resumed_from_bytes=observed,
            http_range_requests=0,
        )
        _write_json_atomic(receipt_path, asdict(receipt))
        return receipt

    resumed_from = partial_path.stat().st_size if partial_path.exists() else 0
    if resumed_from > spec.expected_total_bytes:
        raise AcquisitionError("partial file exceeds the frozen expected size")

    requests_made = 0
    with partial_path.open("ab") as stream:
        offset = resumed_from
        while offset < spec.expected_total_bytes:
            stop = min(offset + chunk_bytes, spec.expected_total_bytes) - 1
            last_error: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    payload, total, _ = _read_range(
                        spec.url,
                        offset,
                        stop,
                        timeout=timeout,
                        opener=opener,
                    )
                    requests_made += 1
                    if total != spec.expected_total_bytes:
                        raise AcquisitionError(
                            f"source size drift: {total} != {spec.expected_total_bytes}"
                        )
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                    offset += len(payload)
                    _write_json_atomic(
                        state_path,
                        {
                            "dataset_id": spec.dataset_id,
                            "source_url": spec.url,
                            "partial_path": str(partial_path.resolve()),
                            "completed_bytes": offset,
                            "expected_bytes": spec.expected_total_bytes,
                            "updated_at_utc": _utc_now(),
                            "authority": ACQUISITION_AUTHORITY,
                        },
                    )
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt < max_attempts:
                        time.sleep(min(2 ** (attempt - 1), 8))
            if last_error is not None:
                raise AcquisitionError(
                    f"range acquisition failed at offset {offset}"
                ) from last_error

    observed = partial_path.stat().st_size
    if observed != spec.expected_total_bytes:
        raise AcquisitionError(
            f"completed partial has wrong size: {observed} != {spec.expected_total_bytes}"
        )
    digest = _sha256_file(partial_path)
    os.replace(partial_path, final_path)
    state_path.unlink(missing_ok=True)

    receipt = AcquisitionReceipt(
        dataset_id=spec.dataset_id,
        source_url=spec.url,
        destination=str(final_path.resolve()),
        expected_bytes=spec.expected_total_bytes,
        observed_bytes=observed,
        sha256=digest,
        completed_at_utc=_utc_now(),
        resumed_from_bytes=resumed_from,
        http_range_requests=requests_made,
    )
    _write_json_atomic(receipt_path, asdict(receipt))
    return receipt


def acquire_default_inputs(
    root: Path,
    *,
    acknowledge_upstream_terms: bool,
    execution_jurisdiction: str,
    datasets: Iterable[DatasetSpec] = DEFAULT_DATASETS,
    chunk_bytes: int = DEFAULT_CHUNK_BYTES,
) -> dict[str, Any]:
    selected = tuple(datasets)
    expected = sum(item.expected_total_bytes for item in selected)
    capacity = assert_remote_capacity(
        root,
        expected_input_bytes=expected,
        execution_jurisdiction=execution_jurisdiction,
    )
    receipts = [
        acquire_dataset(
            item,
            root,
            acknowledge_upstream_terms=acknowledge_upstream_terms,
            execution_jurisdiction=execution_jurisdiction,
            chunk_bytes=chunk_bytes,
        )
        for item in selected
    ]
    payload = {
        "campaign": "DP-REMOTE-OBJ-0.14",
        "generated_at_utc": _utc_now(),
        "authority": ACQUISITION_AUTHORITY,
        "capacity_gate": capacity,
        "receipts": [asdict(item) for item in receipts],
        "all_inputs_complete": len(receipts) == len(selected),
        "scientific_result": False,
        "next_gate": "OBJECT_LEVEL_LENS_SOURCE_RECONSTRUCTION",
    }
    _write_json_atomic(root / "acquisition_manifest.json", payload)
    return payload


__all__ = [
    "ACQUISITION_AUTHORITY",
    "AcquisitionError",
    "AcquisitionReceipt",
    "DEFAULT_CHUNK_BYTES",
    "DEFAULT_MIN_FREE_GIB",
    "REMOTE_JURISDICTION",
    "acquire_dataset",
    "acquire_default_inputs",
    "assert_remote_capacity",
]
