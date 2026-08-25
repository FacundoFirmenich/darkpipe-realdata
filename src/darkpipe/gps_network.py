"""Prospective covariance-aware GPS clock-network transient search.

This module uses native JPL final high-rate clock and orbit products. A
detector-level candidate never implies dark matter, plasma hyperstates,
gravity, or a physical coupling.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from typing import Iterable, Sequence
import gzip
import io
import math
import re

import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from scipy.stats import qmc
from sklearn.covariance import LedoitWolf

JPL_FINAL_BASE = "https://sideshow.jpl.nasa.gov/pub/JPL_GNSS_Products/Final"
JPL_USER_AGENT = "DarkPipe-Research/0.9 (+https://github.com/FacundoFirmenich/darkpipe-realdata)"
JPL_GPS_ORIGIN_UTC = datetime(2000, 1, 1, 11, 59, 47, tzinfo=timezone.utc)
UTC_LEAP_EFFECTIVE = (
    datetime(2006, 1, 1, tzinfo=timezone.utc),
    datetime(2009, 1, 1, tzinfo=timezone.utc),
    datetime(2012, 7, 1, tzinfo=timezone.utc),
    datetime(2015, 7, 1, tzinfo=timezone.utc),
    datetime(2017, 1, 1, tzinfo=timezone.utc),
)
CLOCK_RE = re.compile(r"^\.Satellite\.(GPS\d+)\.Clk\.Bias$")


@dataclass(frozen=True)
class SearchConfig:
    campaign_id: str = "DP-GPS-NETWORK-TRANSIENT-0.9-20260825"
    cadence_seconds: float = 30.0
    coverage_min: float = 0.98
    min_nodes: int = 20
    guard_seconds: float = 1200.0
    velocity_min_km_s: float = 53.7
    velocity_max_km_s: float = 770.0
    template_count: int = 256
    seed: int = 2026082509
    injection_trials: int = 128
    injection_amplitudes: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0)
    localization_tolerance_seconds: float = 120.0
    alpha: float = 0.05
    download_limit_bytes: int = 100_000_000

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["injection_amplitudes"] = list(self.injection_amplitudes)
        return payload


@dataclass(frozen=True)
class ProductReceipt:
    url: str
    compressed_bytes: int
    sha256: str
    media: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Segment:
    label: str
    start: datetime
    stop: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.stop.tzinfo is None:
            raise ValueError("segment datetimes must be timezone-aware")
        if self.stop <= self.start:
            raise ValueError("segment stop must be after start")


@dataclass(frozen=True)
class SearchHit:
    statistic: float
    center_second: float
    template_index: int
    velocity_km_s: float
    direction_xyz: tuple[float, float, float]

    def to_dict(self) -> dict:
        return asdict(self)


def product_url(day: date, kind: str) -> str:
    if kind not in {"hr.tdp", "pos"}:
        raise ValueError("kind must be 'hr.tdp' or 'pos'")
    suffix = "_hr.tdp.gz" if kind == "hr.tdp" else ".pos.gz"
    return f"{JPL_FINAL_BASE}/{day.year}/{day.isoformat()}{suffix}"


def _leaps_since_j2000(value_utc: datetime) -> int:
    return sum(value_utc >= instant for instant in UTC_LEAP_EFFECTIVE)


def datetime_to_jpl_second(value: datetime) -> float:
    """Convert UTC to continuous GPS seconds past J2000GPS."""

    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    value_utc = value.astimezone(timezone.utc)
    naive_elapsed = (value_utc - JPL_GPS_ORIGIN_UTC).total_seconds()
    return naive_elapsed + _leaps_since_j2000(value_utc)


def jpl_second_to_datetime(value: float) -> datetime:
    """Convert continuous J2000GPS seconds to UTC away from leap instants."""

    candidate = JPL_GPS_ORIGIN_UTC + timedelta(seconds=float(value))
    for _ in range(3):
        candidate = JPL_GPS_ORIGIN_UTC + timedelta(
            seconds=float(value) - _leaps_since_j2000(candidate)
        )
    return candidate


def fetch_gzip_text(
    url: str,
    *,
    timeout: tuple[float, float] = (15.0, 120.0),
    max_bytes: int = 100_000_000,
) -> tuple[str, ProductReceipt]:
    """Download a bounded gzip member with three finite HTTP attempts."""

    retry = Retry(
        total=2,
        connect=2,
        read=2,
        status=2,
        backoff_factor=1.0,
        status_forcelist=(404, 429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=True,
    )
    digest = sha256()
    buffer = io.BytesIO()
    total = 0
    with requests.Session() as session:
        session.mount("https://", HTTPAdapter(max_retries=retry))
        with session.get(
            url,
            stream=True,
            timeout=timeout,
            headers={"User-Agent": JPL_USER_AGENT, "Accept": "application/gzip"},
        ) as response:
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=1 << 20):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(f"download exceeds declared bound: {url}")
                digest.update(chunk)
                buffer.write(chunk)
    try:
        decoded = gzip.decompress(buffer.getvalue()).decode("ascii", errors="strict")
    except (gzip.BadGzipFile, UnicodeDecodeError) as exc:
        raise ValueError(f"invalid JPL gzip/ASCII product: {url}") from exc
    return decoded, ProductReceipt(
        url=url,
        compressed_bytes=total,
        sha256=digest.hexdigest(),
        media="application/gzip",
    )


def parse_clock_tdp(text: str) -> pd.DataFrame:
    rows: list[tuple[float, str, float, float]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        fields = line.split()
        if len(fields) != 5:
            continue
        match = CLOCK_RE.match(fields[4])
        if not match:
            continue
        try:
            rows.append(
                (float(fields[0]), match.group(1), float(fields[2]), float(fields[3]))
            )
        except ValueError as exc:
            raise ValueError(f"invalid clock row at line {line_number}") from exc
    if not rows:
        raise ValueError("no GPS satellite clock-bias rows found")
    frame = pd.DataFrame(rows, columns=["jpl_second", "node", "bias_m", "sigma_m"])
    numeric = frame[["jpl_second", "bias_m", "sigma_m"]].to_numpy()
    if not np.isfinite(numeric).all() or (frame["sigma_m"] < 0).any():
        raise ValueError("invalid clock numeric value")
    return frame.sort_values(["jpl_second", "node"], ignore_index=True)


def parse_position_goa(text: str) -> pd.DataFrame:
    rows: list[tuple[float, str, float, float, float]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        fields = line.split()
        if len(fields) < 7 or fields[0] != "E" or not fields[1].startswith("GPS"):
            continue
        try:
            rows.append(
                (
                    float(fields[2]),
                    fields[1],
                    float(fields[4]),
                    float(fields[5]),
                    float(fields[6]),
                )
            )
        except ValueError as exc:
            raise ValueError(f"invalid position row at line {line_number}") from exc
    if not rows:
        raise ValueError("no Earth-fixed GPS satellite positions found")
    frame = pd.DataFrame(
        rows, columns=["jpl_second", "node", "x_km", "y_km", "z_km"]
    )
    if not np.isfinite(frame[["jpl_second", "x_km", "y_km", "z_km"]].to_numpy()).all():
        raise ValueError("non-finite orbit value")
    return frame.sort_values(["jpl_second", "node"], ignore_index=True)


def clock_difference_matrix(
    clock: pd.DataFrame, *, cadence_seconds: float
) -> pd.DataFrame:
    pivot = clock.pivot(index="jpl_second", columns="node", values="bias_m").sort_index()
    times = pivot.index.to_numpy(dtype=float)
    differenced = pivot.diff()
    contiguous = np.r_[False, np.isclose(np.diff(times), cadence_seconds, atol=1e-6)]
    differenced.loc[~contiguous, :] = np.nan
    return differenced


def slice_matrix(
    matrix: pd.DataFrame, start_second: float, stop_second: float
) -> pd.DataFrame:
    return matrix.loc[(matrix.index >= start_second) & (matrix.index < stop_second)]


def select_nodes(
    matrices: Sequence[pd.DataFrame], *, coverage_min: float, min_nodes: int
) -> list[str]:
    if not matrices:
        raise ValueError("background matrices required")
    common = sorted(set.intersection(*(set(frame.columns) for frame in matrices)))
    selected: list[str] = []
    for node in common:
        observed = sum(int(frame[node].notna().sum()) for frame in matrices)
        possible = sum(int(len(frame)) for frame in matrices)
        if possible and observed / possible >= coverage_min:
            selected.append(node)
    if len(selected) < min_nodes:
        raise ValueError(
            f"integrity gate failed: {len(selected)} nodes below {min_nodes}"
        )
    return selected


def fit_background(
    matrices: Sequence[pd.DataFrame], nodes: Sequence[str]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    joined = pd.concat([frame.loc[:, nodes] for frame in matrices], axis=0)
    values = joined.to_numpy(dtype=float)
    location = np.nanmedian(values, axis=0)
    mad = np.nanmedian(np.abs(values - location), axis=0)
    scale = 1.4826 * mad
    bad = ~np.isfinite(scale) | (scale <= np.finfo(float).eps)
    if bad.any():
        raise ValueError(f"invalid robust scale for {int(bad.sum())} nodes")
    standardized = (values - location) / scale
    complete = standardized[np.isfinite(standardized).all(axis=1)]
    if complete.shape[0] < max(10 * len(nodes), 500):
        raise ValueError("insufficient complete background rows")
    covariance = LedoitWolf().fit(complete).covariance_
    if not np.isfinite(covariance).all():
        raise ValueError("non-finite covariance")
    return location, scale, covariance


def standardize_matrix(
    matrix: pd.DataFrame,
    nodes: Sequence[str],
    location: np.ndarray,
    scale: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    frame = matrix.loc[:, nodes]
    return frame.index.to_numpy(dtype=float), (frame.to_numpy(dtype=float) - location) / scale


def covariance_weight(covariance: np.ndarray) -> np.ndarray:
    ones = np.ones(covariance.shape[0], dtype=float)
    solved = np.linalg.solve(covariance, ones)
    normalizer = math.sqrt(float(ones @ solved))
    if not np.isfinite(normalizer) or normalizer <= 0:
        raise ValueError("invalid covariance normalization")
    return solved / normalizer


def sobol_velocity_bank(config: SearchConfig) -> np.ndarray:
    power = int(math.ceil(math.log2(config.template_count)))
    unit = qmc.Sobol(d=3, scramble=True, seed=config.seed).random_base2(power)
    unit = unit[: config.template_count]
    log_speed = np.log(config.velocity_min_km_s) + unit[:, 0] * (
        np.log(config.velocity_max_km_s) - np.log(config.velocity_min_km_s)
    )
    cos_theta = 2.0 * unit[:, 1] - 1.0
    phi = 2.0 * np.pi * unit[:, 2]
    sin_theta = np.sqrt(np.maximum(0.0, 1.0 - cos_theta * cos_theta))
    direction = np.column_stack(
        [sin_theta * np.cos(phi), sin_theta * np.sin(phi), cos_theta]
    )
    return direction * np.exp(log_speed)[:, None]


def position_snapshot(
    position: pd.DataFrame, nodes: Sequence[str], center_second: float
) -> np.ndarray:
    output = np.empty((len(nodes), 3), dtype=float)
    for index, node in enumerate(nodes):
        part = position.loc[position["node"] == node]
        if part.empty:
            raise ValueError(f"orbit missing for {node}")
        time = part["jpl_second"].to_numpy(dtype=float)
        if center_second < time[0] or center_second > time[-1]:
            raise ValueError(f"orbit does not cover center for {node}")
        for axis_index, axis in enumerate(("x_km", "y_km", "z_km")):
            output[index, axis_index] = np.interp(
                center_second, time, part[axis].to_numpy(dtype=float)
            )
    return output


def template_delays(position_km: np.ndarray, velocity_vectors: np.ndarray) -> np.ndarray:
    speeds = np.linalg.norm(velocity_vectors, axis=1)
    directions = velocity_vectors / speeds[:, None]
    centered = position_km - position_km.mean(axis=0, keepdims=True)
    return centered @ directions.T / speeds[None, :]


def score_template(
    times: np.ndarray,
    standardized: np.ndarray,
    delays: np.ndarray,
    weight: np.ndarray,
    centers: np.ndarray,
) -> np.ndarray:
    sampled = np.empty((len(centers), standardized.shape[1]), dtype=float)
    for node_index in range(standardized.shape[1]):
        sampled[:, node_index] = np.interp(
            centers + delays[node_index],
            times,
            standardized[:, node_index],
            left=np.nan,
            right=np.nan,
        )
    valid = np.isfinite(sampled).all(axis=1)
    score = np.full(len(centers), np.nan, dtype=float)
    score[valid] = sampled[valid] @ weight
    return score


def score_surface(
    times: np.ndarray,
    standardized: np.ndarray,
    delays: np.ndarray,
    weight: np.ndarray,
    centers: np.ndarray,
) -> np.ndarray:
    """Vectorized score for every center and every velocity template."""

    if len(times) < 2:
        raise ValueError("at least two time samples required")
    cadence = float(np.median(np.diff(times)))
    if not np.allclose(np.diff(times), cadence, atol=1e-6):
        raise ValueError("score surface requires a regular time grid")
    surface = np.zeros((len(centers), delays.shape[1]), dtype=float)
    valid = np.ones_like(surface, dtype=bool)
    for node_index in range(standardized.shape[1]):
        fractional = (
            centers[:, None] + delays[node_index][None, :] - times[0]
        ) / cadence
        lower = np.floor(fractional).astype(np.int64)
        fraction = fractional - lower
        inside = (lower >= 0) & (lower + 1 < len(times))
        safe = np.clip(lower, 0, len(times) - 2)
        column = standardized[:, node_index]
        sampled = column[safe] * (1.0 - fraction) + column[safe + 1] * fraction
        finite = inside & np.isfinite(sampled)
        valid &= finite
        surface += np.where(finite, sampled * weight[node_index], 0.0)
    surface[~valid] = np.nan
    return surface


def search_segment(
    times: np.ndarray,
    standardized: np.ndarray,
    position_km: np.ndarray,
    velocity_vectors: np.ndarray,
    weight: np.ndarray,
    *,
    start_second: float,
    stop_second: float,
    guard_seconds: float,
) -> SearchHit:
    centers = times[
        (times >= start_second + guard_seconds)
        & (times < stop_second - guard_seconds)
    ]
    if centers.size == 0:
        raise ValueError("guard removes all candidate centers")
    delays = template_delays(position_km, velocity_vectors)
    surface = score_surface(times, standardized, delays, weight, centers)
    if not np.isfinite(surface).any():
        raise ValueError("no finite template score")
    flat_index = int(np.nanargmax(np.abs(surface)))
    center_index, template_index = np.unravel_index(flat_index, surface.shape)
    vector = velocity_vectors[template_index]
    speed = float(np.linalg.norm(vector))
    return SearchHit(
        statistic=float(abs(surface[center_index, template_index])),
        center_second=float(centers[center_index]),
        template_index=int(template_index),
        velocity_km_s=speed,
        direction_xyz=tuple(float(v) for v in vector / speed),
    )


def exact_rank_pvalue(target: float, null_maxima: Sequence[float]) -> float:
    null = np.asarray(null_maxima, dtype=float)
    if null.size == 0 or not np.isfinite(null).all() or not np.isfinite(target):
        raise ValueError("finite target and non-empty finite null required")
    return float((1 + np.count_nonzero(null >= target)) / (null.size + 1))


def inject_plane_impulse(
    standardized: np.ndarray,
    times: np.ndarray,
    position_km: np.ndarray,
    velocity_vector: np.ndarray,
    center_second: float,
    amplitude: float,
) -> np.ndarray:
    output = standardized.copy()
    delays = template_delays(position_km, velocity_vector[None, :])[:, 0]
    cadence = float(np.median(np.diff(times)))
    for node_index, arrival in enumerate(center_second + delays):
        sample = int(np.argmin(np.abs(times - arrival)))
        if abs(times[sample] - arrival) <= 0.5 * cadence:
            output[sample, node_index] += amplitude
    return output


def wilson_lower_bound(
    successes: int, trials: int, z: float = 1.959963984540054
) -> float:
    if trials <= 0 or successes < 0 or successes > trials:
        raise ValueError("invalid binomial counts")
    proportion = successes / trials
    denominator = 1 + z * z / trials
    center = proportion + z * z / (2 * trials)
    radius = z * math.sqrt(
        proportion * (1 - proportion) / trials + z * z / (4 * trials * trials)
    )
    return float((center - radius) / denominator)


def daily_segments(
    day: date,
    starts_utc: Iterable[str],
    durations_seconds: Sequence[float],
) -> list[Segment]:
    output: list[Segment] = []
    for block_index, start_text in enumerate(starts_utc):
        hour, minute = (int(part) for part in start_text.split(":"))
        cursor = datetime(day.year, day.month, day.day, hour, minute, tzinfo=timezone.utc)
        for part_index, duration in enumerate(durations_seconds):
            stop = cursor + timedelta(seconds=float(duration))
            output.append(
                Segment(
                    label=f"{day.isoformat()}-b{block_index + 1}-p{part_index + 1}",
                    start=cursor,
                    stop=stop,
                )
            )
            cursor = stop
    return output
