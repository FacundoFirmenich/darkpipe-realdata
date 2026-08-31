"""Bounded-memory HTTP range reader for fixed-width FITS binary tables.

The reader is intentionally narrower than ``astropy.io.fits``: it supports the
fixed-width scalar/vector column types needed by the public KiDS catalogues and
never materializes the remote table or an analysis-sized local cache.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Iterator, Mapping, Sequence

import numpy as np
import requests


FITS_BLOCK = 2880
CARD_BYTES = 80
RANGE_READER_AUTHORITY = "BYTE_STREAM_DECODER_ONLY_NO_SCIENTIFIC_RESULT"


class FitsRangeError(RuntimeError):
    """Raised when remote bytes do not satisfy the declared FITS structure."""


@dataclass(frozen=True)
class FitsColumn:
    index: int
    name: str
    form: str
    unit: str | None
    repeat: int
    code: str
    offset: int
    width: int


@dataclass(frozen=True)
class FitsBinaryTableLayout:
    data_start: int
    row_bytes: int
    rows: int
    fields: tuple[FitsColumn, ...]
    pcount: int

    def by_name(self) -> dict[str, FitsColumn]:
        return {field.name: field for field in self.fields}


def _header(blob: bytes, start: int) -> tuple[list[str], int]:
    cards: list[str] = []
    cursor = start
    while cursor + CARD_BYTES <= len(blob):
        card = blob[cursor : cursor + CARD_BYTES].decode("ascii", "replace")
        cards.append(card)
        cursor += CARD_BYTES
        if card.startswith("END"):
            used = len(cards) * CARD_BYTES
            return cards, start + math.ceil(used / FITS_BLOCK) * FITS_BLOCK
    raise FitsRangeError("bounded prefix does not contain a complete FITS header")


def _value(card: str) -> str:
    return card[10:80].split("/", 1)[0].strip().strip("'").strip()


def _cards_dict(cards: Sequence[str]) -> dict[str, str]:
    return {card[:8].strip(): _value(card) for card in cards if card[8:10] == "= "}


_TFORM_RE = re.compile(r"^(?P<repeat>\d*)(?P<code>[LXBIJKAEDCMPQ])(?:\([^)]*\))?$")


def _field_width(repeat: int, code: str) -> int:
    if code == "X":
        return math.ceil(repeat / 8)
    per_value = {
        "L": 1,
        "B": 1,
        "I": 2,
        "J": 4,
        "K": 8,
        "A": 1,
        "E": 4,
        "D": 8,
        "C": 8,
        "M": 16,
        "P": 8,
        "Q": 16,
    }[code]
    return repeat * per_value


def _primary_data_bytes(metadata: Mapping[str, str]) -> int:
    naxis = int(metadata.get("NAXIS", "0"))
    if naxis == 0:
        return 0
    elements = 1
    for axis in range(1, naxis + 1):
        elements *= int(metadata[f"NAXIS{axis}"])
    bitpix = abs(int(metadata["BITPIX"]))
    groups = int(metadata.get("GCOUNT", "1"))
    pcount = int(metadata.get("PCOUNT", "0"))
    return ((elements * bitpix // 8 + pcount) * groups + FITS_BLOCK - 1) // FITS_BLOCK * FITS_BLOCK


def parse_bintable_layout(prefix: bytes) -> FitsBinaryTableLayout:
    """Parse the first binary-table extension from a complete bounded prefix."""

    if not prefix.startswith(b"SIMPLE"):
        raise FitsRangeError("payload is not a FITS primary HDU")
    primary_cards, primary_header_end = _header(prefix, 0)
    primary = _cards_dict(primary_cards)
    extension_start = primary_header_end + _primary_data_bytes(primary)
    extension_cards, data_start = _header(prefix, extension_start)
    metadata = _cards_dict(extension_cards)
    if metadata.get("XTENSION") != "BINTABLE":
        raise FitsRangeError("first extension is not BINTABLE")

    row_bytes = int(metadata["NAXIS1"])
    rows = int(metadata["NAXIS2"])
    field_count = int(metadata["TFIELDS"])
    fields: list[FitsColumn] = []
    offset = 0
    for index in range(1, field_count + 1):
        name = metadata.get(f"TTYPE{index}")
        form = metadata.get(f"TFORM{index}")
        if name is None or form is None:
            raise FitsRangeError(f"missing TTYPE/TFORM for field {index}")
        match = _TFORM_RE.fullmatch(form.replace(" ", ""))
        if not match:
            raise FitsRangeError(f"unsupported TFORM {form!r} for {name!r}")
        repeat = int(match.group("repeat") or "1")
        code = match.group("code")
        width = _field_width(repeat, code)
        fields.append(
            FitsColumn(
                index=index,
                name=name,
                form=form,
                unit=metadata.get(f"TUNIT{index}"),
                repeat=repeat,
                code=code,
                offset=offset,
                width=width,
            )
        )
        offset += width
    if offset != row_bytes:
        raise FitsRangeError(f"field widths sum to {offset}, NAXIS1 declares {row_bytes}")
    return FitsBinaryTableLayout(
        data_start=data_start,
        row_bytes=row_bytes,
        rows=rows,
        fields=tuple(fields),
        pcount=int(metadata.get("PCOUNT", "0")),
    )


def _numpy_dtype(field: FitsColumn) -> np.dtype:
    mapping = {
        "B": np.dtype("u1"),
        "I": np.dtype(">i2"),
        "J": np.dtype(">i4"),
        "K": np.dtype(">i8"),
        "E": np.dtype(">f4"),
        "D": np.dtype(">f8"),
        "C": np.dtype(">c8"),
        "M": np.dtype(">c16"),
    }
    if field.code not in mapping:
        raise FitsRangeError(f"column {field.name!r} has non-numeric TFORM {field.form!r}")
    return mapping[field.code]


def decode_columns(
    payload: bytes,
    layout: FitsBinaryTableLayout,
    names: Sequence[str],
) -> dict[str, np.ndarray]:
    """Decode selected fixed-width columns from one whole-row payload."""

    if len(payload) % layout.row_bytes:
        raise FitsRangeError("payload is not aligned to complete FITS rows")
    row_count = len(payload) // layout.row_bytes
    by_name = layout.by_name()
    output: dict[str, np.ndarray] = {}
    for name in names:
        if name not in by_name:
            raise FitsRangeError(f"column not found: {name}")
        field = by_name[name]
        if field.code in {"A", "L"}:
            dtype = np.dtype(f"S{field.repeat}")
            view = np.ndarray(
                shape=(row_count,),
                dtype=dtype,
                buffer=payload,
                offset=field.offset,
                strides=(layout.row_bytes,),
            )
            output[name] = view.copy()
            continue
        dtype = _numpy_dtype(field)
        if field.repeat == 1:
            view = np.ndarray(
                shape=(row_count,),
                dtype=dtype,
                buffer=payload,
                offset=field.offset,
                strides=(layout.row_bytes,),
            )
        else:
            view = np.ndarray(
                shape=(row_count, field.repeat),
                dtype=dtype,
                buffer=payload,
                offset=field.offset,
                strides=(layout.row_bytes, dtype.itemsize),
            )
        output[name] = np.asarray(view, dtype=dtype.newbyteorder("=")).copy()
    return output


def decode_numeric_columns(
    payload: bytes,
    layout: FitsBinaryTableLayout,
    names: Sequence[str],
) -> dict[str, np.ndarray]:
    """Backward-compatible numeric-only entry point."""

    selected = layout.by_name()
    non_numeric = [name for name in names if name in selected and selected[name].code in {"A", "L", "X", "P", "Q"}]
    if non_numeric:
        raise FitsRangeError(f"non-numeric columns requested: {non_numeric}")
    return decode_columns(payload, layout, names)


def _get_exact_range(
    session: requests.Session,
    url: str,
    start: int,
    stop: int,
    *,
    total_bytes: int,
    timeout: tuple[float, float],
) -> bytes:
    with session.get(
        url,
        headers={"Range": f"bytes={start}-{stop}", "Accept-Encoding": "identity"},
        stream=True,
        timeout=timeout,
    ) as response:
        if response.status_code != 206:
            raise FitsRangeError(f"HTTP {response.status_code}; exact 206 range required")
        expected_range = f"bytes {start}-{stop}/{total_bytes}"
        if response.headers.get("Content-Range") != expected_range:
            raise FitsRangeError(
                f"Content-Range {response.headers.get('Content-Range')!r} != {expected_range!r}"
            )
        payload = response.content
    if len(payload) != stop - start + 1:
        raise FitsRangeError("short HTTP range")
    return payload


def read_remote_layout(
    url: str,
    *,
    total_bytes: int,
    prefix_bytes: int = 262_144,
    session: requests.Session | None = None,
) -> FitsBinaryTableLayout:
    own_session = session is None
    active = session or requests.Session()
    active.headers.update({"User-Agent": "DarkPipe/0.16 FITS-range-reader"})
    try:
        prefix = _get_exact_range(
            active,
            url,
            0,
            prefix_bytes - 1,
            total_bytes=total_bytes,
            timeout=(30.0, 180.0),
        )
        return parse_bintable_layout(prefix)
    finally:
        if own_session:
            active.close()


def iter_remote_numeric_columns(
    url: str,
    *,
    total_bytes: int,
    names: Sequence[str],
    target_chunk_bytes: int = 64 * 1024 * 1024,
    start_row: int = 0,
    session: requests.Session | None = None,
) -> Iterator[tuple[int, dict[str, np.ndarray]]]:
    """Yield ``(first_row, columns)`` chunks without a persistent local cache."""

    own_session = session is None
    active = session or requests.Session()
    active.headers.update({"User-Agent": "DarkPipe/0.16 FITS-range-reader"})
    try:
        layout = read_remote_layout(
            url, total_bytes=total_bytes, session=active
        )
        rows_per_chunk = max(1, target_chunk_bytes // layout.row_bytes)
        if start_row < 0 or start_row > layout.rows:
            raise FitsRangeError(f"start_row outside table: {start_row}")
        for first_row in range(start_row, layout.rows, rows_per_chunk):
            row_count = min(rows_per_chunk, layout.rows - first_row)
            start = layout.data_start + first_row * layout.row_bytes
            stop = start + row_count * layout.row_bytes - 1
            payload = _get_exact_range(
                active,
                url,
                start,
                stop,
                total_bytes=total_bytes,
                timeout=(30.0, 900.0),
            )
            yield first_row, decode_columns(payload, layout, names)
    finally:
        if own_session:
            active.close()


__all__ = [
    "FITS_BLOCK",
    "FitsBinaryTableLayout",
    "FitsColumn",
    "FitsRangeError",
    "RANGE_READER_AUTHORITY",
    "decode_numeric_columns",
    "decode_columns",
    "iter_remote_numeric_columns",
    "parse_bintable_layout",
    "read_remote_layout",
]
