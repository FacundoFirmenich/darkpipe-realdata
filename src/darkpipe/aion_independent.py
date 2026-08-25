"""Cloud-first custody for the independent historical AION epoch.

The inventory stage is deliberately endpoint-blind: it records the HDF5
hierarchy and storage schema without reading dataset values.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import h5py

from .http import _session, fetch_json
from .provenance import file_record, utc_now, write_json

ZENODO_RECORD_ID = 15166670
SOURCE_FILENAME = "000034056-DifferentialClockInterferometryWithNoiseFrag.h5"
SOURCE_SIZE_BYTES = 564_439_752
SOURCE_MD5 = "e7053ad0a8401c4198b4729feec8441c"
MAX_SOURCE_BYTES = 570_000_000
CAMPAIGN_ID = "DP-AION-INDEPENDENT-0.8-20260825"


def _source_entry(record: dict[str, Any]) -> dict[str, Any]:
    if int(record.get("id", -1)) != ZENODO_RECORD_ID:
        raise ValueError("unexpected Zenodo record id")
    matches = [
        item
        for item in record.get("files", [])
        if item.get("key") == SOURCE_FILENAME
    ]
    if len(matches) != 1:
        raise ValueError("source HDF5 is absent or ambiguous in Zenodo metadata")
    item = matches[0]
    if int(item.get("size", -1)) != SOURCE_SIZE_BYTES:
        raise ValueError("Zenodo source size differs from the frozen value")
    if item.get("checksum") != f"md5:{SOURCE_MD5}":
        raise ValueError("Zenodo source checksum differs from the frozen value")
    return item


def fetch_source_record(output: str | Path) -> dict[str, Any]:
    artifact = fetch_json(
        f"https://zenodo.org/api/records/{ZENODO_RECORD_ID}",
        max_bytes=1_000_000,
    )
    record = artifact.payload
    _source_entry(record)
    write_json(output, record)
    return record


def download_source(record: dict[str, Any], target: str | Path) -> dict[str, Any]:
    """Stream the frozen source to an ephemeral path and verify it exactly."""
    item = _source_entry(record)
    url = item["links"]["content"]
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    md5 = hashlib.md5(usedforsecurity=False)
    sha256 = hashlib.sha256()
    size = 0
    try:
        with _session() as session:
            with session.get(url, timeout=(30, 180), stream=True) as response:
                response.raise_for_status()
                with path.open("wb") as handle:
                    for chunk in response.iter_content(1024 * 1024):
                        if not chunk:
                            continue
                        size += len(chunk)
                        if size > MAX_SOURCE_BYTES:
                            raise ValueError(
                                "source exceeded the frozen byte ceiling"
                            )
                        handle.write(chunk)
                        md5.update(chunk)
                        sha256.update(chunk)
        if size != SOURCE_SIZE_BYTES:
            raise ValueError(f"source byte count mismatch: {size}")
        if md5.hexdigest() != SOURCE_MD5:
            raise ValueError("source MD5 mismatch")
        return {
            "url": url,
            "byte_count": size,
            "md5": md5.hexdigest(),
            "sha256": sha256.hexdigest(),
        }
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _attribute_schema(
    attributes: h5py.AttributeManager,
) -> list[dict[str, Any]]:
    result = []
    for key in sorted(attributes.keys()):
        value = attributes[key]
        result.append(
            {
                "name": str(key),
                "dtype": str(
                    getattr(value, "dtype", type(value).__name__)
                ),
                "shape": list(getattr(value, "shape", ())),
            }
        )
    return result


def inventory_hdf5(source: str | Path) -> dict[str, Any]:
    """Inventory names and storage metadata without reading dataset values."""
    groups: list[dict[str, Any]] = []
    datasets: list[dict[str, Any]] = []
    with h5py.File(source, "r") as handle:
        root_attributes = _attribute_schema(handle.attrs)

        def visitor(
            name: str, item: h5py.Group | h5py.Dataset
        ) -> None:
            if isinstance(item, h5py.Dataset):
                datasets.append(
                    {
                        "path": name,
                        "shape": list(item.shape),
                        "dtype": str(item.dtype),
                        "chunks": (
                            None
                            if item.chunks is None
                            else list(item.chunks)
                        ),
                        "compression": item.compression,
                        "attributes": _attribute_schema(item.attrs),
                    }
                )
            else:
                groups.append(
                    {
                        "path": name,
                        "attributes": _attribute_schema(item.attrs),
                    }
                )

        handle.visititems(visitor)
    return {
        "endpoint_values_read": False,
        "root_attributes": root_attributes,
        "groups": groups,
        "datasets": datasets,
        "group_count": len(groups),
        "dataset_count": len(datasets),
    }


def run_inventory(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace)
    root.mkdir(parents=True, exist_ok=True)
    raw = root / SOURCE_FILENAME
    record_path = root / "zenodo_record.json"
    record = fetch_source_record(record_path)
    try:
        source = download_source(record, raw)
        schema = inventory_hdf5(raw)
        report = {
            "schema_version": "1.0",
            "campaign_id": CAMPAIGN_ID,
            "stage": "ENDPOINT_BLIND_SOURCE_INVENTORY",
            "generated_at_utc": utc_now(),
            "source": source,
            "source_record": file_record(record_path, root),
            "inventory": schema,
            "raw_retained": False,
            "claim_ceiling": (
                "source integrity and schema readability only"
            ),
        }
        write_json(root / "inventory.json", report)
        return report
    finally:
        raw.unlink(missing_ok=True)

