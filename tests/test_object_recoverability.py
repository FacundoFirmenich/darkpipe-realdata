from __future__ import annotations

from io import BytesIO

from darkpipe.object_recoverability import (
    DEFAULT_DATASETS,
    DatasetSpec,
    evaluate_recoverability,
    parse_fits_bintable_header,
    probe_dataset,
)


def _card(key: str, value: str | int | None = None) -> bytes:
    if value is None:
        text = key
    elif isinstance(value, str):
        text = f"{key:<8}= '{value}'"
    else:
        text = f"{key:<8}= {value:>20}"
    return text.ljust(80).encode("ascii")


def _header(cards: list[bytes]) -> bytes:
    payload = b"".join([*cards, _card("END")])
    return payload.ljust(((len(payload) + 2879) // 2880) * 2880, b" ")


def _minimal_fits(rows: int, columns: tuple[str, ...]) -> bytes:
    primary = _header([_card("SIMPLE", "T")])
    extension_cards = [
        _card("XTENSION", "BINTABLE"),
        _card("NAXIS1", 8 * len(columns)),
        _card("NAXIS2", rows),
        _card("TFIELDS", len(columns)),
    ]
    for index, column in enumerate(columns, start=1):
        extension_cards.append(_card(f"TTYPE{index}", column))
    return primary + _header(extension_cards)


class _Response(BytesIO):
    status = 206

    def __init__(self, payload: bytes, total: int):
        super().__init__(payload)
        self.headers = {
            "Content-Range": f"bytes 0-{len(payload) - 1}/{total}",
            "Content-Length": str(len(payload)),
        }

    def getcode(self) -> int:
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def test_parse_fits_binary_table_header() -> None:
    payload = _minimal_fits(12, ("ID", "Z_B", "weight"))
    parsed = parse_fits_bintable_header(payload)
    assert parsed["rows"] == 12
    assert parsed["declared_fields"] == 3
    assert parsed["columns"] == ["ID", "Z_B", "weight"]


def test_probe_is_structural_and_bounded() -> None:
    spec = DatasetSpec(
        dataset_id="fixture",
        url="https://example.invalid/catalog.fits",
        role="structural unit-test fixture; never scientific evidence",
        kind="fits_bintable",
        expected_total_bytes=999,
        expected_rows=12,
        required_columns=("ID", "Z_B", "weight"),
    )
    payload = _minimal_fits(12, spec.required_columns)

    def opener(_request, timeout):
        assert timeout == 3.0
        return _Response(payload, spec.expected_total_bytes)

    result = probe_dataset(spec, timeout=3.0, opener=opener)
    assert result["probe_status"] == "AVAILABLE_SCHEMA_VERIFIED"
    assert result["byte_range_supported"] is True
    assert result["sample_bytes_read"] == len(payload)


def test_recoverability_requires_every_input() -> None:
    probes = [
        {
            "probe_status": "AVAILABLE_SCHEMA_VERIFIED",
            "expected_total_bytes": 10,
        },
        {
            "probe_status": "AVAILABLE_SCHEMA_OR_SIZE_DRIFT",
            "expected_total_bytes": 20,
        },
    ]
    summary = evaluate_recoverability(probes)
    assert summary["all_public_inputs_verified"] is False
    assert summary["scientific_authority"] == "PRECOMPUTE_GATE_ONLY_NO_SCIENTIFIC_RESULT"


def test_default_surface_is_remote_scale() -> None:
    total = sum(spec.expected_total_bytes for spec in DEFAULT_DATASETS)
    assert total == 18_059_551_240
    assert total > 16 * 1024**3
