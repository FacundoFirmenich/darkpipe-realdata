"""Observable-shadow to conditional-inobservable derivation for SPARC.

The module does not identify a dark-matter ontology. It reconstructs a signed,
spherical-equivalent effective acceleration and enclosed-mass profile from the
shadow between observed circular motion and measured baryonic mass models.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


SPARC_RECORD_ID = 16284118
SPARC_RECORD_URL = f"https://zenodo.org/api/records/{SPARC_RECORD_ID}"
SPARC_EXPECTED = {
    "SPARC_Lelli2016c.mrt": {
        "size": 28259,
        "md5": "6181df386bfc05868a3700c196e800da",
    },
    "MassModels_Lelli2016c.mrt": {
        "size": 269518,
        "md5": "fe6188538c3f5504f70f486ff6b4d29c",
    },
}
USER_AGENT = (
    "DarkPipe-Research/0.10 "
    "(+https://github.com/FacundoFirmenich/darkpipe-realdata)"
)
KPC_METRES = 3.085677581491367e19
ACCELERATION_FACTOR = 1.0e6 / KPC_METRES
G_ASTRO = 4.30091e-6  # kpc (km/s)^2 / solar mass
AUTHORITY = "DERIVED_EFFECTIVE_INOBSERVABLE_CONDITIONAL_NOT_ONTOLOGIZED"


@dataclass(frozen=True)
class SourceReceipt:
    name: str
    url: str
    byte_count: int
    md5: str
    sha256: str
    license: str
    retrieved_at_utc: str


@dataclass(frozen=True)
class DerivationConfig:
    draws: int = 4096
    seed: int = 20260826010
    quality_max: int = 2
    inclination_min_deg: float = 30.0
    maximum_fractional_velocity_error: float = 0.10
    disk_mass_to_light: float = 0.5
    bulge_mass_to_light: float = 0.7
    mass_to_light_sigma_dex: float = 0.11


def _session() -> requests.Session:
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _bounded_download(
    session: requests.Session,
    url: str,
    *,
    expected_size: int,
    maximum_bytes: int = 2_000_000,
) -> bytes:
    chunks: list[bytes] = []
    size = 0
    with session.get(url, timeout=60, stream=True) as response:
        response.raise_for_status()
        for chunk in response.iter_content(65536):
            if not chunk:
                continue
            size += len(chunk)
            if size > maximum_bytes:
                raise ValueError(f"source exceeded maximum_bytes: {url}")
            chunks.append(chunk)
    payload = b"".join(chunks)
    if len(payload) != expected_size:
        raise ValueError(
            f"source size mismatch for {url}: {len(payload)} != {expected_size}"
        )
    return payload


def fetch_sparc_sources(scratch: Path) -> tuple[dict[str, Path], dict[str, Any]]:
    """Fetch two bounded CC-BY-4.0 source tables and verify record metadata."""
    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=False)
    paths: dict[str, Path] = {}
    receipts: list[SourceReceipt] = []
    with _session() as session:
        response = session.get(SPARC_RECORD_URL, timeout=60)
        response.raise_for_status()
        record_bytes = response.content
        record = response.json()
        if int(record.get("id", -1)) != SPARC_RECORD_ID:
            raise ValueError("Zenodo record id mismatch")
        license_id = str(record.get("metadata", {}).get("license", {}).get("id", ""))
        if license_id.lower() != "cc-by-4.0":
            raise ValueError(f"unexpected SPARC record license: {license_id!r}")
        indexed = {item["key"]: item for item in record.get("files", [])}
        for name, expected in SPARC_EXPECTED.items():
            item = indexed.get(name)
            if item is None:
                raise ValueError(f"missing preregistered source file: {name}")
            checksum = str(item.get("checksum", ""))
            if checksum != f"md5:{expected['md5']}":
                raise ValueError(f"record checksum mismatch for {name}: {checksum}")
            if int(item.get("size", -1)) != expected["size"]:
                raise ValueError(f"record size mismatch for {name}")
            url = item["links"]["self"]
            payload = _bounded_download(
                session, url, expected_size=expected["size"]
            )
            md5 = hashlib.md5(payload, usedforsecurity=False).hexdigest()
            if md5 != expected["md5"]:
                raise ValueError(f"download MD5 mismatch for {name}")
            target = scratch / name
            target.write_bytes(payload)
            paths[name] = target
            receipts.append(
                SourceReceipt(
                    name=name,
                    url=url,
                    byte_count=len(payload),
                    md5=md5,
                    sha256=hashlib.sha256(payload).hexdigest(),
                    license=license_id,
                    retrieved_at_utc=_utc_now(),
                )
            )
    record_receipt = {
        "url": SPARC_RECORD_URL,
        "byte_count": len(record_bytes),
        "sha256": hashlib.sha256(record_bytes).hexdigest(),
        "license": license_id,
        "record_id": SPARC_RECORD_ID,
        "doi": record.get("doi"),
    }
    return paths, {
        "schema": "darkpipe.sparc.source_receipts.v1",
        "record": record_receipt,
        "files": [asdict(receipt) for receipt in receipts],
    }


def parse_sparc_sample(text: str) -> pd.DataFrame:
    """Parse the fixed-width SPARC galaxy table without trusting header offsets."""
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 19:
            continue
        galaxy = parts[0]
        try:
            distance = float(parts[2])
            distance_error = float(parts[3])
            inclination = float(parts[5])
            inclination_error = float(parts[6])
            quality = int(parts[17])
        except ValueError:
            continue
        rows.append(
            {
                "galaxy": galaxy,
                "distance_mpc": distance,
                "distance_error_mpc": distance_error,
                "inclination_deg": inclination,
                "inclination_error_deg": inclination_error,
                "quality": quality,
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty or frame["galaxy"].duplicated().any():
        raise ValueError("invalid or duplicate SPARC galaxy table")
    return frame.sort_values("galaxy").reset_index(drop=True)


def parse_sparc_mass_models(text: str) -> pd.DataFrame:
    """Parse the ten-column SPARC mass-model table."""
    rows: list[list[Any]] = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 10:
            continue
        try:
            numeric = [float(value) for value in parts[1:]]
        except ValueError:
            continue
        rows.append([parts[0], *numeric])
    columns = [
        "galaxy",
        "distance_model_mpc",
        "radius_kpc",
        "velocity_observed_km_s",
        "velocity_error_km_s",
        "velocity_gas_km_s",
        "velocity_disk_km_s",
        "velocity_bulge_km_s",
        "surface_brightness_disk",
        "surface_brightness_bulge",
    ]
    frame = pd.DataFrame(rows, columns=columns)
    if frame.empty:
        raise ValueError("empty SPARC mass-model table")
    return frame


def signed_square(value: np.ndarray | float) -> np.ndarray | float:
    """Preserve the sign convention of outward gas contributions."""
    return np.asarray(value) * np.abs(np.asarray(value))


def select_observable_points(
    mass_models: pd.DataFrame,
    galaxies: pd.DataFrame,
    config: DerivationConfig,
) -> pd.DataFrame:
    merged = mass_models.merge(galaxies, on="galaxy", how="left", validate="many_to_one")
    if merged["quality"].isna().any():
        missing = sorted(merged.loc[merged["quality"].isna(), "galaxy"].unique())
        raise ValueError(f"mass models without galaxy metadata: {missing[:5]}")
    fractional = (
        merged["velocity_error_km_s"] / merged["velocity_observed_km_s"].abs()
    )
    mask = (
        (merged["quality"] <= config.quality_max)
        & (merged["inclination_deg"] >= config.inclination_min_deg)
        & (merged["radius_kpc"] > 0)
        & (merged["velocity_observed_km_s"] > 0)
        & (merged["velocity_error_km_s"] > 0)
        & (fractional <= config.maximum_fractional_velocity_error)
    )
    selected = merged.loc[mask].copy()
    if selected.empty:
        raise ValueError("SPARC quality selection retained no observations")
    selected["fractional_velocity_error"] = fractional.loc[mask]
    return selected.sort_values(["galaxy", "radius_kpc"]).reset_index(drop=True)


def _bounded_normal(
    rng: np.random.Generator,
    mean: float,
    sigma: float,
    low: float,
    high: float,
    size: int,
) -> np.ndarray:
    if sigma <= 0:
        return np.full(size, mean, dtype=float)
    values = rng.normal(mean, sigma, size)
    invalid = (values <= low) | (values >= high)
    rounds = 0
    while invalid.any():
        values[invalid] = rng.normal(mean, sigma, int(invalid.sum()))
        invalid = (values <= low) | (values >= high)
        rounds += 1
        if rounds > 100:
            raise RuntimeError("bounded normal rejection did not converge")
    return values


def _quantiles(values: np.ndarray) -> dict[str, float]:
    q = np.quantile(values, [0.025, 0.16, 0.5, 0.84, 0.975])
    return {
        "p025": float(q[0]),
        "p16": float(q[1]),
        "p50": float(q[2]),
        "p84": float(q[3]),
        "p975": float(q[4]),
    }


def derive_shadow_inobservables(
    selected: pd.DataFrame,
    config: DerivationConfig,
) -> pd.DataFrame:
    """Lift observable kinematic shadows to conditional effective profiles."""
    if config.draws < 128:
        raise ValueError("draws must be at least 128")
    rng = np.random.default_rng(config.seed)
    output: list[dict[str, Any]] = []
    for galaxy, group in selected.groupby("galaxy", sort=True):
        meta = group.iloc[0]
        draws = config.draws
        distance = _bounded_normal(
            rng,
            float(meta["distance_mpc"]),
            float(meta["distance_error_mpc"]),
            1.0e-6,
            math.inf,
            draws,
        )
        inclination = _bounded_normal(
            rng,
            float(meta["inclination_deg"]),
            float(meta["inclination_error_deg"]),
            5.0,
            89.9,
            draws,
        )
        distance_ratio = distance / float(meta["distance_model_mpc"])
        inclination_ratio = math.sin(
            math.radians(float(meta["inclination_deg"]))
        ) / np.sin(np.deg2rad(inclination))
        upsilon_disk = 10.0 ** rng.normal(
            math.log10(config.disk_mass_to_light),
            config.mass_to_light_sigma_dex,
            draws,
        )
        upsilon_bulge = 10.0 ** rng.normal(
            math.log10(config.bulge_mass_to_light),
            config.mass_to_light_sigma_dex,
            draws,
        )

        for _, point in group.iterrows():
            vobs_native = rng.normal(
                float(point["velocity_observed_km_s"]),
                float(point["velocity_error_km_s"]),
                draws,
            )
            vobs = vobs_native * inclination_ratio
            radius = float(point["radius_kpc"]) * distance_ratio
            gas_v2 = float(signed_square(point["velocity_gas_km_s"])) * distance_ratio
            disk_v2 = (
                float(point["velocity_disk_km_s"]) ** 2
                * distance_ratio
                * upsilon_disk
            )
            bulge_v2 = (
                float(point["velocity_bulge_km_s"]) ** 2
                * distance_ratio
                * upsilon_bulge
            )
            baryonic_v2 = gas_v2 + disk_v2 + bulge_v2
            observed_v2 = vobs**2
            shadow_v2 = observed_v2 - baryonic_v2
            g_observed = observed_v2 / radius * ACCELERATION_FACTOR
            g_baryonic = baryonic_v2 / radius * ACCELERATION_FACTOR
            g_shadow = shadow_v2 / radius * ACCELERATION_FACTOR
            mass_shadow = shadow_v2 * radius / G_ASTRO

            p_positive = float(np.mean(g_shadow > 0.0))
            two_sided_sign_tail = max(
                2.0 * min(p_positive, 1.0 - p_positive),
                1.0 / (draws + 1.0),
            )
            sign_evidence_bits = -math.log2(two_sided_sign_tail)

            nominal_baryonic_v2 = (
                float(signed_square(point["velocity_gas_km_s"]))
                + config.disk_mass_to_light
                * float(point["velocity_disk_km_s"]) ** 2
                + config.bulge_mass_to_light
                * float(point["velocity_bulge_km_s"]) ** 2
            )
            closure_velocity = math.sqrt(max(nominal_baryonic_v2, 0.0))
            fixed_closure_cost_sigma = abs(
                float(point["velocity_observed_km_s"]) - closure_velocity
            ) / float(point["velocity_error_km_s"])

            gq = _quantiles(g_shadow)
            mq = _quantiles(mass_shadow)
            oq = _quantiles(g_observed)
            bq = _quantiles(g_baryonic)
            if gq["p025"] > 0:
                status = "POSITIVE_SIGNED_PROFILE_SUPPORTED_95"
            elif gq["p975"] < 0:
                status = "NEGATIVE_SIGNED_PROFILE_SUPPORTED_95"
            else:
                status = "SIGN_AMBIGUOUS_95"

            output.append(
                {
                    "galaxy": galaxy,
                    "quality": int(point["quality"]),
                    "radius_nominal_kpc": float(point["radius_kpc"]),
                    "fractional_velocity_error": float(
                        point["fractional_velocity_error"]
                    ),
                    "shadow_delta_v2_nominal_km2_s2": float(
                        float(point["velocity_observed_km_s"]) ** 2
                        - nominal_baryonic_v2
                    ),
                    "shadow_sign_probability_positive": p_positive,
                    "shadow_sign_evidence_bits": sign_evidence_bits,
                    "shadow_fixed_nuisance_closure_cost_sigma": (
                        fixed_closure_cost_sigma
                    ),
                    "g_observed_p50_m_s2": oq["p50"],
                    "g_baryonic_p50_m_s2": bq["p50"],
                    "g_inobservable_p025_m_s2": gq["p025"],
                    "g_inobservable_p16_m_s2": gq["p16"],
                    "g_inobservable_p50_m_s2": gq["p50"],
                    "g_inobservable_p84_m_s2": gq["p84"],
                    "g_inobservable_p975_m_s2": gq["p975"],
                    "mass_inobservable_p025_solar": mq["p025"],
                    "mass_inobservable_p16_solar": mq["p16"],
                    "mass_inobservable_p50_solar": mq["p50"],
                    "mass_inobservable_p84_solar": mq["p84"],
                    "mass_inobservable_p975_solar": mq["p975"],
                    "inobservable_status": status,
                    "authority": AUTHORITY,
                }
            )
    frame = pd.DataFrame(output)
    numeric = frame.select_dtypes(include=[np.number]).to_numpy()
    if not np.isfinite(numeric).all():
        raise ValueError("non-finite value in derived shadow/inobservable table")
    return frame


def summarize_derivation(
    profiles: pd.DataFrame,
    selected: pd.DataFrame,
    config: DerivationConfig,
    source_receipts: dict[str, Any],
    *,
    points_before_selection: int | None = None,
) -> dict[str, Any]:
    counts = profiles["inobservable_status"].value_counts().to_dict()
    galaxy_count = int(profiles["galaxy"].nunique())
    point_count = int(len(profiles))
    if galaxy_count < 20 or point_count < 500:
        decision = "ABSTAIN_INTEGRITY_INSUFFICIENT_REAL_OBSERVATIONS"
    else:
        decision = "DERIVED_CONDITIONAL_INOBSERVABLE_PROFILES_AVAILABLE"
    return {
        "schema": "darkpipe.observable_shadow_inobservable.v1",
        "campaign_id": "DP-OBS-SHADOW-INOBS-0.10-20260826",
        "created_utc": _utc_now(),
        "decision": decision,
        "authority": AUTHORITY,
        "observable_face": [
            "rotation radius",
            "observed circular velocity",
            "gas velocity contribution",
            "disk velocity contribution",
            "bulge velocity contribution",
        ],
        "shadow_face": [
            "signed squared-velocity discrepancy",
            "posterior sign support",
            "sign evidence cost in bits",
            "fixed-nuisance velocity transformation cost to baryonic closure",
        ],
        "derived_inobservable": (
            "signed spherical-equivalent effective acceleration and enclosed-"
            "mass discrepancy profiles conditional on Newtonian centripetal "
            "mapping and declared nuisance priors"
        ),
        "selection": {
            "quality_max": config.quality_max,
            "inclination_min_deg": config.inclination_min_deg,
            "maximum_fractional_velocity_error": (
                config.maximum_fractional_velocity_error
            ),
            "galaxies": galaxy_count,
            "points": point_count,
            "points_before_selection": int(
                len(selected)
                if points_before_selection is None
                else points_before_selection
            ),
        },
        "nuisance_model": asdict(config),
        "status_counts": {key: int(value) for key, value in counts.items()},
        "not_estimable": [
            "dark-matter particle identity or density profile",
            "MOND or Lambda-CDM adjudication",
            "plasma-hyperstate ontology",
            "gravity mechanism",
            "non-spherical three-dimensional mass distribution",
            "full factometric transformation cost with all systematics",
            "phase, multifractal, topological and genealogical shadow channels",
        ],
        "source_receipts": source_receipts,
    }
