from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
import re

import pytest

from darkpipe.drive_sharded_acquisition import (
    DRIVE_SHARDED_JURISDICTION,
    acquire_dataset_sharded,
    assert_drive_quota,
    plan_shards,
)
from darkpipe.object_recoverability import DatasetSpec
from darkpipe.remote_acquisition import AcquisitionError


class _Response(BytesIO):
    status = 206

    def __init__(self, payload: bytes, start: int, total: int):
        super().__init__(payload)
        self.headers = {
            "Content-Range": f"bytes {start}-{start + len(payload) - 1}/{total}"
        }

    def getcode(self) -> int:
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def _opener(payload: bytes, calls: list[tuple[int, int]]):
    def opener(request, timeout):
        assert timeout == 7.0
        match = re.fullmatch(r"bytes=(\d+)-(\d+)", request.headers["Range"])
        assert match
        start, stop = map(int, match.groups())
        calls.append((start, stop))
        return _Response(payload[start : stop + 1], start, len(payload))

    return opener


def _spec(payload: bytes) -> DatasetSpec:
    return DatasetSpec(
        dataset_id="drive-fixture",
        url="https://example.invalid/drive-fixture.bin",
        role="software-only byte fixture; never scientific evidence",
        kind="binary",
        expected_total_bytes=len(payload),
    )


def test_shard_plan_covers_each_byte_once() -> None:
    assert plan_shards(10, 4) == ((0, 0, 3), (1, 4, 7), (2, 8, 9))
    with pytest.raises(ValueError):
        plan_shards(0, 4)
    with pytest.raises(ValueError):
        plan_shards(10, 0)


def test_drive_quota_uses_remaining_bytes_plus_margin() -> None:
    gate = assert_drive_quota(
        expected_remaining_bytes=100,
        observed_drive_free_bytes=150,
        safety_margin_bytes=50,
    )
    assert gate["required_drive_free_bytes"] == 150
    with pytest.raises(AcquisitionError, match="quota gate failed"):
        assert_drive_quota(
            expected_remaining_bytes=100,
            observed_drive_free_bytes=149,
            safety_margin_bytes=50,
        )


def test_sharded_acquisition_is_exact_and_resumable(tmp_path: Path) -> None:
    payload = bytes(range(251)) * 11
    calls: list[tuple[int, int]] = []
    receipt = acquire_dataset_sharded(
        _spec(payload),
        tmp_path,
        acknowledge_upstream_terms=True,
        execution_jurisdiction=DRIVE_SHARDED_JURISDICTION,
        shard_bytes=512,
        timeout=7.0,
        opener=_opener(payload, calls),
    )
    assert receipt.shard_count == len(plan_shards(len(payload), 512))
    assert receipt.observed_bytes == len(payload)
    assert receipt.full_sha256 == hashlib.sha256(payload).hexdigest()
    assert receipt.complete_file_reassembled is False
    assert receipt.http_range_requests == receipt.shard_count

    manifest_path = tmp_path / "drive-fixture" / "shard-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "COMPLETE_BYTE_CUSTODY"
    assert len(manifest["shards"]) == receipt.shard_count

    def forbidden_opener(*_args, **_kwargs):
        raise AssertionError("verified shards must not be downloaded again")

    resumed = acquire_dataset_sharded(
        _spec(payload),
        tmp_path,
        acknowledge_upstream_terms=True,
        execution_jurisdiction=DRIVE_SHARDED_JURISDICTION,
        shard_bytes=512,
        timeout=7.0,
        opener=forbidden_opener,
    )
    assert resumed.reused_shards == receipt.shard_count
    assert resumed.http_range_requests == 0
    assert resumed.full_sha256 == receipt.full_sha256


def test_tampered_existing_shard_is_preserved_as_failure(tmp_path: Path) -> None:
    payload = b"0123456789abcdef" * 100
    receipt = acquire_dataset_sharded(
        _spec(payload),
        tmp_path,
        acknowledge_upstream_terms=True,
        execution_jurisdiction=DRIVE_SHARDED_JURISDICTION,
        shard_bytes=256,
        timeout=7.0,
        opener=_opener(payload, []),
    )
    manifest = json.loads(Path(receipt.manifest_path).read_text(encoding="utf-8"))
    first = Path(receipt.destination_directory) / manifest["shards"][0]["filename"]
    first.write_bytes(b"x" * first.stat().st_size)
    with pytest.raises(AcquisitionError, match="existing shard hash mismatch"):
        acquire_dataset_sharded(
            _spec(payload),
            tmp_path,
            acknowledge_upstream_terms=True,
            execution_jurisdiction=DRIVE_SHARDED_JURISDICTION,
            shard_bytes=256,
            timeout=7.0,
            opener=_opener(payload, []),
        )


def test_source_size_drift_aborts_without_completed_manifest(tmp_path: Path) -> None:
    payload = b"abcdefghij"
    spec = DatasetSpec(
        dataset_id="drift",
        url="https://example.invalid/drift.bin",
        role="software-only drift fixture",
        kind="binary",
        expected_total_bytes=len(payload) + 1,
    )
    with pytest.raises(AcquisitionError, match="source size drift"):
        acquire_dataset_sharded(
            spec,
            tmp_path,
            acknowledge_upstream_terms=True,
            execution_jurisdiction=DRIVE_SHARDED_JURISDICTION,
            shard_bytes=4,
            timeout=7.0,
            max_attempts=1,
            opener=_opener(payload, []),
        )
    manifest_path = tmp_path / "drift" / "shard-manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["status"] != "COMPLETE_BYTE_CUSTODY"
