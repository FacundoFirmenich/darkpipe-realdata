"""Remote, non-downloading recoverability gate for the KiDS object-level RAR.

The gate reads only bounded HTTP byte ranges.  It validates the real public
FITS headers and the compact redshift-distribution tarball, but deliberately
does not download the 18 GB input surface or perform scientific inference.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO
import re
import tarfile
from typing import Any, Callable, Mapping
from urllib.request import Request, urlopen


PRECOMPUTE_AUTHORITY = "PRECOMPUTE_GATE_ONLY_NO_SCIENTIFIC_RESULT"
RECOVERABILITY_READY = (
    "SUFFICIENT_IN_PRINCIPLE_FOR_REMOTE_OBJECT_LEVEL_RECONSTRUCTION"
)
EXACT_REPRODUCTION_LIMIT = (
    "PARTIAL_RANDOM_CATALOG_AND_OPERATIONAL_GGL_CODE_NOT_IN_PUBLIC_RESULT_BUNDLE"
)
LOCAL_EXECUTION_POLICY = "REMOTE_ONLY_LOCAL_HEAVY_DOWNLOAD_PROHIBITED"


@dataclass(frozen=True)
class DatasetSpec:
    dataset_id: str
    url: str
    role: str
    kind: str
    expected_total_bytes: int
    expected_rows: int | None = None
    required_columns: tuple[str, ...] = ()
    required_tar_members: int | None = None
    reuse_boundary: str = (
        "PUBLIC_DOWNLOAD_ACKNOWLEDGEMENT_REQUIRED_LICENSE_NOT_REASSERTED"
    )


DEFAULT_DATASETS: tuple[DatasetSpec, ...] = (
    DatasetSpec(
        dataset_id="kids1000_som_gold_sources",
        url=(
            "https://kids.strw.leidenuniv.nl/DR4/data_files/"
            "KiDS_DR4.1_ugriZYJHKs_SOM_gold_WL_cat.fits"
        ),
        role="source positions, ellipticities, photometric redshifts and lensfit weights",
        kind="fits_bintable",
        expected_total_bytes=17_712_469_440,
        expected_rows=21_262_011,
        required_columns=(
            "ALPHA_J2000",
            "DELTA_J2000",
            "Z_B",
            "e1",
            "e2",
            "weight",
            "SG_FLAG",
            "SG2DPHOT",
            "CLASS_STAR",
            "IMAFLAGS_ISO",
            "MASK",
        ),
    ),
    DatasetSpec(
        dataset_id="kids_dr4_bright_lenses",
        url=(
            "https://kids.strw.leidenuniv.nl/DR4/data_files/"
            "KiDS_DR4_brightsample.fits"
        ),
        role="lens positions, ANNz2 redshifts and masks",
        kind="fits_bintable",
        expected_total_bytes=89_259_840,
        expected_rows=1_239_422,
        required_columns=(
            "ID",
            "RAJ2000",
            "DECJ2000",
            "MAG_AUTO_CALIB",
            "zphot_ANNz2",
            "MASK",
            "masked",
        ),
    ),
    DatasetSpec(
        dataset_id="kids_dr4_bright_lens_properties",
        url=(
            "https://kids.strw.leidenuniv.nl/DR4/data_files/"
            "KiDS_DR4_brightsample_LePhare.fits"
        ),
        role="lens stellar-mass posterior summaries and photometric properties",
        kind="fits_bintable",
        expected_total_bytes=257_817_600,
        expected_rows=1_239_422,
        required_columns=(
            "ID",
            "RAJ2000",
            "DECJ2000",
            "REDSHIFT",
            "MASS_MED",
            "MASS_INF",
            "MASS_SUP",
            "MASS_BEST",
        ),
    ),
    DatasetSpec(
        dataset_id="kids1000_som_n_of_z",
        url=(
            "https://kids.strw.leidenuniv.nl/DR4/data_files/"
            "KiDS1000_SOM_N_of_Z.tar.gz"
        ),
        role="five public tomographic source-redshift distributions",
        kind="tar_gzip",
        expected_total_bytes=4_360,
        required_tar_members=5,
    ),
)


class RecoverabilityProbeError(RuntimeError):
    """Raised when a bounded public-input probe cannot be adjudicated."""


def _header_cards(blob: bytes, start: int) -> tuple[list[str], int]:
    cards: list[str] = []
    position = start
    while position + 80 <= len(blob):
        card = blob[position : position + 80].decode("ascii", "replace")
        cards.append(card)
        position += 80
        if card.startswith("END"):
            padded_cards = ((len(cards) + 35) // 36) * 36
            return cards, start + padded_cards * 80
    raise RecoverabilityProbeError("bounded range does not contain a complete FITS header")


def _fits_value(card: str) -> str:
    return card[10:80].split("/", 1)[0].strip().strip("'").strip()


def parse_fits_bintable_header(blob: bytes) -> dict[str, Any]:
    """Parse the first FITS binary-table header from a bounded prefix."""

    if not blob.startswith(b"SIMPLE"):
        raise RecoverabilityProbeError("payload does not start with a FITS SIMPLE card")
    _, extension_start = _header_cards(blob, 0)
    extension, _ = _header_cards(blob, extension_start)
    metadata: dict[str, str] = {}
    columns: list[str] = []
    for card in extension:
        keyword = card[:8].strip()
        if keyword in {"XTENSION", "NAXIS1", "NAXIS2", "TFIELDS"}:
            metadata[keyword] = _fits_value(card)
        elif keyword.startswith("TTYPE"):
            columns.append(_fits_value(card))
    if metadata.get("XTENSION") != "BINTABLE":
        raise RecoverabilityProbeError("first FITS extension is not BINTABLE")
    return {
        "row_bytes": int(metadata["NAXIS1"]),
        "rows": int(metadata["NAXIS2"]),
        "declared_fields": int(metadata["TFIELDS"]),
        "columns": columns,
    }


def _total_from_headers(headers: Mapping[str, str]) -> int | None:
    content_range = headers.get("Content-Range") or headers.get("content-range")
    if content_range:
        match = re.search(r"/(\d+)$", content_range)
        if match:
            return int(match.group(1))
    content_length = headers.get("Content-Length") or headers.get("content-length")
    return int(content_length) if content_length and content_length.isdigit() else None


def _read_bounded(
    spec: DatasetSpec,
    *,
    timeout: float,
    opener: Callable[..., Any],
) -> tuple[int, Mapping[str, str], bytes]:
    requested_bytes = 262_144 if spec.kind == "fits_bintable" else 65_536
    request = Request(
        spec.url,
        headers={
            "Range": f"bytes=0-{requested_bytes - 1}",
            "User-Agent": "DarkPipe-v0.13-object-recoverability",
        },
    )
    with opener(request, timeout=timeout) as response:
        status = int(getattr(response, "status", response.getcode()))
        headers = response.headers
        payload = response.read(requested_bytes)
    return status, headers, payload


def probe_dataset(
    spec: DatasetSpec,
    *,
    timeout: float = 90.0,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    """Validate one live input by bounded range, size and structural schema."""

    status, headers, payload = _read_bounded(spec, timeout=timeout, opener=opener)
    total_bytes = _total_from_headers(headers)
    result: dict[str, Any] = {
        **asdict(spec),
        "http_status": status,
        "byte_range_supported": status == 206,
        "sample_bytes_read": len(payload),
        "observed_total_bytes": total_bytes,
        "total_size_matches": total_bytes == spec.expected_total_bytes,
        "schema_matches": False,
        "missing_columns": [],
    }

    if status not in {200, 206}:
        result["probe_status"] = "UNAVAILABLE_HTTP_STATUS"
        return result

    if spec.kind == "fits_bintable":
        header = parse_fits_bintable_header(payload)
        columns = set(header["columns"])
        missing = sorted(set(spec.required_columns) - columns)
        rows_match = spec.expected_rows is None or header["rows"] == spec.expected_rows
        result.update(
            {
                "fits_header": header,
                "missing_columns": missing,
                "rows_match": rows_match,
                "schema_matches": not missing and rows_match,
            }
        )
    elif spec.kind == "tar_gzip":
        if total_bytes is None or len(payload) < total_bytes:
            raise RecoverabilityProbeError("small n(z) archive was not returned in full")
        with tarfile.open(fileobj=BytesIO(payload[:total_bytes]), mode="r:gz") as archive:
            members = [member for member in archive.getmembers() if member.isfile()]
        member_names = [member.name for member in members]
        expected = spec.required_tar_members
        result.update(
            {
                "tar_members": member_names,
                "tar_member_count": len(member_names),
                "schema_matches": expected is None or len(member_names) == expected,
            }
        )
    else:
        raise RecoverabilityProbeError(f"unsupported dataset kind: {spec.kind}")

    result["probe_status"] = (
        "AVAILABLE_SCHEMA_VERIFIED"
        if result["total_size_matches"] and result["schema_matches"]
        else "AVAILABLE_SCHEMA_OR_SIZE_DRIFT"
    )
    return result


def evaluate_recoverability(probes: list[dict[str, Any]]) -> dict[str, Any]:
    verified = all(item["probe_status"] == "AVAILABLE_SCHEMA_VERIFIED" for item in probes)
    total_bytes = sum(int(item["expected_total_bytes"]) for item in probes)
    return {
        "all_public_inputs_verified": verified,
        "dataset_count": len(probes),
        "expected_raw_input_bytes": total_bytes,
        "expected_raw_input_gib": total_bytes / (1024**3),
        "recoverability": (
            RECOVERABILITY_READY
            if verified
            else "NOT_READY_PUBLIC_INPUT_PROBE_FAILED_OR_DRIFTED"
        ),
        "exact_reproduction": EXACT_REPRODUCTION_LIMIT,
        "local_execution_policy": LOCAL_EXECUTION_POLICY,
        "minimum_remote_scratch_recommendation_gib": 40,
        "scientific_authority": PRECOMPUTE_AUTHORITY,
        "next_gate": (
            "REMOTE_STREAMED_LENS_SOURCE_RECONSTRUCTION_WITH_INDEPENDENT_RANDOMS"
            if verified
            else "RESOLVE_INPUT_AVAILABILITY_OR_SCHEMA_DRIFT"
        ),
    }


def probe_default_inputs(*, timeout: float = 90.0) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    probes = [probe_dataset(spec, timeout=timeout) for spec in DEFAULT_DATASETS]
    return probes, evaluate_recoverability(probes)


__all__ = [
    "DEFAULT_DATASETS",
    "DatasetSpec",
    "EXACT_REPRODUCTION_LIMIT",
    "LOCAL_EXECUTION_POLICY",
    "PRECOMPUTE_AUTHORITY",
    "RECOVERABILITY_READY",
    "RecoverabilityProbeError",
    "evaluate_recoverability",
    "parse_fits_bintable_header",
    "probe_dataset",
    "probe_default_inputs",
]
