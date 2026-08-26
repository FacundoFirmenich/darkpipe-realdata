"""Population-level weak-lensing shadow and cross-jurisdiction atlas.

This module derives conditional effective discrepancies from a published
weak-lensing RAR. It does not fuse individual SPARC galaxies with the stacked
KiDS population and does not identify the discrepancy with any ontology.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


AUTHORITY = (
    "DERIVED_EFFECTIVE_INOBSERVABLE_CONDITIONAL_POPULATION_LEVEL_"
    "NOT_ONTOLOGIZED"
)
DECISION = (
    "SECOND_GALAXY_SCALE_LENSING_SHADOW_AVAILABLE_"
    "NO_OBJECT_LEVEL_FUSION"
)
MISTELE_ARTICLE_DOI = "10.1088/1475-7516/2024/04/020"
MISTELE_SOURCE_URL = "https://commons.case.edu/facultyworks/800/"
TAIL_THRESHOLD_LOG10_GBAR = -14.0
NORMAL_95 = 1.959963984540054

LENSING_COLUMNS = [
    "log10_gbar_m_s2",
    "log10_gobs_m_s2",
    "sigma_stat_log10_gobs",
    "sigma_deprojection_systematic_log10_gobs",
]


@dataclass(frozen=True)
class MultiShadowConfig:
    stellar_mass_systematic_log10_gobs: float = 0.10
    normal_95_multiplier: float = NORMAL_95
    overlap_half_width_dex: float = 0.125
    minimum_overlap_galaxies: int = 5
    tail_threshold_log10_gbar: float = TAIL_THRESHOLD_LOG10_GBAR


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_lensing_rar_table(path: Path) -> pd.DataFrame:
    """Load and strictly validate the 15-bin CC-BY-4.0 transcription."""
    frame = pd.read_csv(Path(path))
    if list(frame.columns) != LENSING_COLUMNS:
        raise ValueError(f"unexpected lensing columns: {list(frame.columns)!r}")
    if len(frame) != 15:
        raise ValueError(f"expected 15 published lensing bins, found {len(frame)}")
    values = frame.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("lensing table contains non-finite values")
    if (frame[[LENSING_COLUMNS[2], LENSING_COLUMNS[3]]] < 0.0).any().any():
        raise ValueError("lensing uncertainties must be non-negative")
    gbar = frame["log10_gbar_m_s2"].to_numpy()
    if not np.all(np.diff(gbar) < 0.0):
        raise ValueError("published lensing bins must be strictly decreasing")
    return frame.copy()


def derive_lensing_inobservables(
    lensing: pd.DataFrame,
    config: MultiShadowConfig,
) -> pd.DataFrame:
    """Derive a signed shadow with a non-probabilistic sensitivity envelope."""
    if config.stellar_mass_systematic_log10_gobs < 0.0:
        raise ValueError("stellar-mass systematic must be non-negative")
    if config.normal_95_multiplier <= 0.0:
        raise ValueError("normal_95_multiplier must be positive")
    frame = lensing.copy()
    log_gbar = frame["log10_gbar_m_s2"].to_numpy(dtype=float)
    log_gobs = frame["log10_gobs_m_s2"].to_numpy(dtype=float)
    stat = frame["sigma_stat_log10_gobs"].to_numpy(dtype=float)
    deprojection = frame[
        "sigma_deprojection_systematic_log10_gobs"
    ].to_numpy(dtype=float)
    combined = np.sqrt(
        stat**2
        + deprojection**2
        + config.stellar_mass_systematic_log10_gobs**2
    )
    low_log_gobs = log_gobs - config.normal_95_multiplier * combined
    high_log_gobs = log_gobs + config.normal_95_multiplier * combined
    gbar = np.power(10.0, log_gbar)
    gobs = np.power(10.0, log_gobs)
    low = np.power(10.0, low_log_gobs) - gbar
    high = np.power(10.0, high_log_gobs) - gbar
    status = np.where(
        low > 0.0,
        "POSITIVE_CONDITIONAL_SENSITIVITY_ENVELOPE_95",
        np.where(
            high < 0.0,
            "NEGATIVE_CONDITIONAL_SENSITIVITY_ENVELOPE_95",
            "SIGN_AMBIGUOUS_CONDITIONAL_SENSITIVITY_ENVELOPE_95",
        ),
    )
    reliability = np.where(
        log_gbar < config.tail_threshold_log10_gbar,
        "LOW_ACCELERATION_TAIL_SYSTEMATICS_DOMINANT",
        "DECLARED_PRIMARY_RANGE",
    )
    result = pd.DataFrame(
        {
            "lensing_bin": np.arange(1, len(frame) + 1, dtype=int),
            "log10_gbar_m_s2": log_gbar,
            "log10_gobs_m_s2": log_gobs,
            "eta_log10_gobs_over_gbar": log_gobs - log_gbar,
            "gbar_m_s2": gbar,
            "gobs_m_s2": gobs,
            "g_inobservable_m_s2": gobs - gbar,
            "g_inobservable_envelope95_low_m_s2": low,
            "g_inobservable_envelope95_high_m_s2": high,
            "sigma_stat_log10_gobs": stat,
            "sigma_deprojection_systematic_log10_gobs": deprojection,
            "sigma_stellar_mass_systematic_log10_gobs": (
                config.stellar_mass_systematic_log10_gobs
            ),
            "sigma_combined_sensitivity_log10_gobs": combined,
            "inobservable_status": status,
            "reliability_jurisdiction": reliability,
            "authority": AUTHORITY,
        }
    )
    if not np.isfinite(
        result.select_dtypes(include=[np.number]).to_numpy()
    ).all():
        raise ValueError("non-finite value in lensing derivation")
    return result


def load_checked_sparc_profiles(path: Path) -> pd.DataFrame:
    """Load the immutable checked v0.10 surface needed for comparison."""
    frame = pd.read_csv(Path(path))
    required = {
        "galaxy",
        "g_observed_p50_m_s2",
        "g_baryonic_p50_m_s2",
        "authority",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"checked SPARC profiles missing columns: {missing}")
    if frame.empty or frame["galaxy"].isna().any():
        raise ValueError("checked SPARC profile surface is empty or malformed")
    return frame.copy()


def build_cross_shadow_atlas(
    lensing_profiles: pd.DataFrame,
    sparc_profiles: pd.DataFrame,
    config: MultiShadowConfig,
) -> pd.DataFrame:
    """Compare central shadows without constructing a joint likelihood."""
    if config.overlap_half_width_dex <= 0.0:
        raise ValueError("overlap_half_width_dex must be positive")
    sparc = sparc_profiles.copy()
    gbar = sparc["g_baryonic_p50_m_s2"].to_numpy(dtype=float)
    gobs = sparc["g_observed_p50_m_s2"].to_numpy(dtype=float)
    valid = np.isfinite(gbar) & np.isfinite(gobs) & (gbar > 0.0) & (gobs > 0.0)
    sparc = sparc.loc[valid, ["galaxy"]].copy()
    sparc["log10_gbar_m_s2"] = np.log10(gbar[valid])
    sparc["eta"] = np.log10(gobs[valid]) - np.log10(gbar[valid])

    rows: list[dict[str, Any]] = []
    for point in lensing_profiles.itertuples(index=False):
        center = float(point.log10_gbar_m_s2)
        inside = sparc.loc[
            sparc["log10_gbar_m_s2"].between(
                center - config.overlap_half_width_dex,
                center + config.overlap_half_width_dex,
                inclusive="both",
            )
        ]
        per_galaxy = inside.groupby("galaxy", sort=True)["eta"].median()
        n_galaxies = int(len(per_galaxy))
        estimable = n_galaxies >= config.minimum_overlap_galaxies
        if estimable:
            values = per_galaxy.to_numpy(dtype=float)
            median = float(np.median(values))
            q16, q84 = np.quantile(values, [0.16, 0.84])
            delta = float(point.eta_log10_gobs_over_gbar) - median
            comparison_status = "DESCRIPTIVE_OVERLAP_NO_JOINT_LIKELIHOOD"
        else:
            median = math.nan
            q16 = math.nan
            q84 = math.nan
            delta = math.nan
            comparison_status = "NOT_ESTIMABLE_INSUFFICIENT_SPARC_OVERLAP"
        rows.append(
            {
                "lensing_bin": int(point.lensing_bin),
                "log10_gbar_m_s2": center,
                "lensing_eta_log10_gobs_over_gbar": float(
                    point.eta_log10_gobs_over_gbar
                ),
                "sparc_points_in_window": int(len(inside)),
                "sparc_galaxies_in_window": n_galaxies,
                "sparc_galaxy_equal_weight_eta_median": median,
                "sparc_galaxy_equal_weight_eta_q16": float(q16),
                "sparc_galaxy_equal_weight_eta_q84": float(q84),
                "lensing_minus_sparc_eta_dex": delta,
                "comparison_status": comparison_status,
                "authority": "DESCRIPTIVE_CROSS_JURISDICTION_NO_FUSION",
            }
        )
    return pd.DataFrame(rows)


def summarize_multishadow(
    lensing_profiles: pd.DataFrame,
    atlas: pd.DataFrame,
    config: MultiShadowConfig,
    source_receipts: dict[str, Any],
) -> dict[str, Any]:
    statuses = lensing_profiles["inobservable_status"].value_counts().to_dict()
    reliability = lensing_profiles[
        "reliability_jurisdiction"
    ].value_counts().to_dict()
    overlap = atlas[
        atlas["comparison_status"]
        == "DESCRIPTIVE_OVERLAP_NO_JOINT_LIKELIHOOD"
    ]
    return {
        "schema": "darkpipe.multishadow.v1",
        "campaign_id": "DP-MULTISHADOW-0.11-20260826",
        "created_utc": _utc_now(),
        "decision": DECISION,
        "authority": AUTHORITY,
        "lensing_bins": int(len(lensing_profiles)),
        "status_counts": {key: int(value) for key, value in statuses.items()},
        "reliability_counts": {
            key: int(value) for key, value in reliability.items()
        },
        "descriptive_overlap_bins": int(len(overlap)),
        "non_estimable_overlap_bins": int(len(atlas) - len(overlap)),
        "median_absolute_descriptive_eta_difference_dex": (
            None
            if overlap.empty
            else float(
                np.median(np.abs(overlap["lensing_minus_sparc_eta_dex"]))
            )
        ),
        "config": asdict(config),
        "source_receipts": source_receipts,
        "observable_face": [
            "published population-level weak-lensing log10(g_obs)",
            "published population-level baryonic log10(g_bar)",
            "checked v0.10 SPARC central profiles",
        ],
        "shadow_face": [
            "signed g_obs minus g_bar at each lensing bin",
            "logarithmic excess eta = log10(g_obs/g_bar)",
            "descriptive cross-jurisdiction eta difference",
        ],
        "derived_inobservable": (
            "population-level effective acceleration discrepancy conditional "
            "on the published weak-lensing deprojection, baryonic mass model, "
            "spherical symmetry, and declared sensitivity envelope"
        ),
        "not_estimable": [
            "object-by-object SPARC and KiDS correspondence",
            "joint SPARC-KiDS likelihood or independent confirmation",
            "full covariance including baryonic systematics",
            "intrinsic galaxy-by-galaxy lensing scatter",
            "dark-matter particle identity or density profile",
            "MOND or Lambda-CDM adjudication",
            "gravity mechanism",
            "plasma-hyperstate ontology",
            "cluster-scale extension",
        ],
    }
