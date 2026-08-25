from pathlib import Path

import h5py
import numpy as np

from darkpipe.aion_independent import (
    SOURCE_FILENAME,
    SOURCE_MD5,
    SOURCE_SIZE_BYTES,
    ZENODO_RECORD_ID,
    _source_entry,
    inventory_hdf5,
)


def test_frozen_source_metadata_gate():
    record = {
        "id": ZENODO_RECORD_ID,
        "files": [
            {
                "key": SOURCE_FILENAME,
                "size": SOURCE_SIZE_BYTES,
                "checksum": f"md5:{SOURCE_MD5}",
                "links": {
                    "content": "https://example.invalid/source"
                },
            }
        ],
    }
    assert _source_entry(record)["key"] == SOURCE_FILENAME


def test_inventory_records_schema_but_not_values(tmp_path: Path):
    source = tmp_path / "schema.h5"
    with h5py.File(source, "w") as handle:
        group = handle.create_group("datasets")
        group.attrs["private_value"] = 17
        group.create_dataset(
            "phase", data=np.array([17.25, 18.5])
        )
    result = inventory_hdf5(source)
    assert result["endpoint_values_read"] is False
    assert result["dataset_count"] == 1
    assert result["datasets"][0]["path"] == "datasets/phase"
    assert result["datasets"][0]["shape"] == [2]
    assert "17.25" not in str(result)
    assert "18.5" not in str(result)
    assert "private_value" in str(result)
    assert "'17'" not in str(result)
