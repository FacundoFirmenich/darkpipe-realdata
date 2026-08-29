from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re

import pytest

from darkpipe.object_recoverability import DatasetSpec
from darkpipe.remote_acquisition import (
    AcquisitionError,
    REMOTE_JURISDICTION,
    acquire_dataset,
)


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


def _opener_for(payload: bytes):
    def opener(request, timeout):
        assert timeout == 7.0
        value = request.headers["Range"]
        match = re.fullmatch(r"bytes=(\d+)-(\d+)", value)
        assert match
        start, stop = map(int, match.groups())
        return _Response(payload[start : stop + 1], start, len(payload))

    return opener


def _spec(payload: bytes) -> DatasetSpec:
    return DatasetSpec(
        dataset_id="fixture",
        url="https://example.invalid/fixture.bin",
        role="unit-test byte fixture; never scientific evidence",
        kind="binary",
        expected_total_bytes=len(payload),
    )


def test_resumable_acquisition_has_exact_bytes_and_receipt(tmp_path: Path) -> None:
    payload = bytes(range(251)) * 9
    partial = tmp_path / "fixture.bin.partial"
    partial.write_bytes(payload[:317])

    receipt = acquire_dataset(
        _spec(payload),
        tmp_path,
        acknowledge_upstream_terms=True,
        execution_jurisdiction=REMOTE_JURISDICTION,
        chunk_bytes=128,
        timeout=7.0,
        opener=_opener_for(payload),
    )

    assert (tmp_path / "fixture.bin").read_bytes() == payload
    assert not partial.exists()
    assert receipt.observed_bytes == len(payload)
    assert receipt.resumed_from_bytes == 317
    assert len(receipt.sha256) == 64
    assert receipt.license_reasserted is False
    assert (tmp_path / "fixture.bin.receipt.json").is_file()


def test_acquisition_refuses_unacknowledged_or_local_execution(tmp_path: Path) -> None:
    payload = b"real bytes are not needed for this refusal test"
    with pytest.raises(AcquisitionError, match="acknowledgement"):
        acquire_dataset(
            _spec(payload),
            tmp_path,
            acknowledge_upstream_terms=False,
            execution_jurisdiction=REMOTE_JURISDICTION,
            opener=_opener_for(payload),
        )
    with pytest.raises(AcquisitionError, match="local heavy"):
        acquire_dataset(
            _spec(payload),
            tmp_path,
            acknowledge_upstream_terms=True,
            execution_jurisdiction="LOCAL",
            opener=_opener_for(payload),
        )


def test_source_size_drift_is_information_bearing_failure(tmp_path: Path) -> None:
    payload = b"abcdefghij"
    spec = DatasetSpec(
        dataset_id="drift",
        url="https://example.invalid/drift.bin",
        role="drift fixture",
        kind="binary",
        expected_total_bytes=len(payload) + 1,
    )
    with pytest.raises(AcquisitionError, match="source size drift"):
        acquire_dataset(
            spec,
            tmp_path,
            acknowledge_upstream_terms=True,
            execution_jurisdiction=REMOTE_JURISDICTION,
            chunk_bytes=4,
            timeout=7.0,
            opener=_opener_for(payload),
            max_attempts=1,
        )
