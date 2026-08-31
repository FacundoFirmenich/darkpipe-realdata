from __future__ import annotations

import numpy as np
import pytest

from darkpipe.fits_range_table import (
    FitsRangeError,
    decode_columns,
    decode_numeric_columns,
    parse_bintable_layout,
)


def _card(keyword: str, value: str | None = None) -> bytes:
    text = keyword if value is None else f"{keyword:<8}= {value}"
    return text.ljust(80).encode("ascii")


def _header(cards: list[bytes]) -> bytes:
    body = b"".join(cards + [_card("END")])
    return body + b" " * ((-len(body)) % 2880)


def _fixture() -> tuple[bytes, bytes]:
    primary = _header([_card("SIMPLE", "T"), _card("BITPIX", "8"), _card("NAXIS", "0")])
    extension = _header(
        [
            _card("XTENSION", "'BINTABLE'"),
            _card("BITPIX", "8"),
            _card("NAXIS", "2"),
            _card("NAXIS1", "16"),
            _card("NAXIS2", "2"),
            _card("PCOUNT", "0"),
            _card("GCOUNT", "1"),
            _card("TFIELDS", "3"),
            _card("TTYPE1", "'RA'"),
            _card("TFORM1", "'1D'"),
            _card("TUNIT1", "'deg'"),
            _card("TTYPE2", "'E'"),
            _card("TFORM2", "'1E'"),
            _card("TTYPE3", "'MASK'"),
            _card("TFORM3", "'1J'"),
        ]
    )
    rows = bytearray(32)
    np.ndarray((2,), dtype=">f8", buffer=rows, offset=0, strides=(16,))[:] = [1.5, 2.5]
    np.ndarray((2,), dtype=">f4", buffer=rows, offset=8, strides=(16,))[:] = [-0.2, 0.3]
    np.ndarray((2,), dtype=">i4", buffer=rows, offset=12, strides=(16,))[:] = [7, 9]
    return primary + extension, bytes(rows)


def test_parse_and_decode_selected_columns() -> None:
    prefix, rows = _fixture()
    layout = parse_bintable_layout(prefix)
    assert layout.data_start == 5760
    assert layout.row_bytes == 16
    assert layout.rows == 2
    assert [(f.name, f.offset, f.width) for f in layout.fields] == [
        ("RA", 0, 8),
        ("E", 8, 4),
        ("MASK", 12, 4),
    ]
    decoded = decode_numeric_columns(rows, layout, ["RA", "E", "MASK"])
    np.testing.assert_allclose(decoded["RA"], [1.5, 2.5])
    np.testing.assert_allclose(decoded["E"], [-0.2, 0.3])
    np.testing.assert_array_equal(decoded["MASK"], [7, 9])


def test_rejects_partial_row_payload() -> None:
    prefix, rows = _fixture()
    with pytest.raises(FitsRangeError, match="complete FITS rows"):
        decode_numeric_columns(rows[:-1], parse_bintable_layout(prefix), ["RA"])


def test_decodes_fixed_width_strings() -> None:
    primary = _header([_card("SIMPLE", "T"), _card("BITPIX", "8"), _card("NAXIS", "0")])
    extension = _header(
        [
            _card("XTENSION", "'BINTABLE'"),
            _card("BITPIX", "8"),
            _card("NAXIS", "2"),
            _card("NAXIS1", "5"),
            _card("NAXIS2", "2"),
            _card("PCOUNT", "0"),
            _card("GCOUNT", "1"),
            _card("TFIELDS", "1"),
            _card("TTYPE1", "'ID'"),
            _card("TFORM1", "'5A'"),
        ]
    )
    layout = parse_bintable_layout(primary + extension)
    decoded = decode_columns(b"A001 B002 ", layout, ["ID"])
    np.testing.assert_array_equal(decoded["ID"], [b"A001 ", b"B002 "])
