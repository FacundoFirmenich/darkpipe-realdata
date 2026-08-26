"""Tests for the v0.11 population-level weak-lensing multi-shadow operator."""

from pathlib import Path

import numpy as np
import pandas as pd

from darkpipe.multishadow import (
    AUTHORITY,
    DECISION,
    MultiShadowConfig,
    build_cross_shadow_atlas,
    derive_lensing_inobservables,
    load_lensing_rar_table,
    summarize_multishadow,
)


TABLE = Path("data/mistele2024_weak_lensing_rar_table1.csv")


def test_published_table_transcription_is_strict_and_finite():
    frame = load_lensing_rar_table(TABLE)
    assert len(frame) == 15
    assert np.isfinite(frame.to_numpy()).all()
    assert frame.iloc[0]["log10_gbar_m_s2"] == -11.41
    assert frame.iloc[-1]["sigma_deprojection_systematic_log10_gobs"] == 0.67


def test_lensing_shadow_is_signed_and_retains_tail_jurisdiction():
    source = load_lensing_rar_table(TABLE)
    derived = derive_lensing_inobservables(source, MultiShadowConfig())
    assert set(derived["authority"]) == {AUTHORITY}
    assert np.allclose(
        derived["g_inobservable_m_s2"],
        derived["gobs_m_s2"] - derived["gbar_m_s2"],
    )
    assert (
        derived["reliability_jurisdiction"]
        == "LOW_ACCELERATION_TAIL_SYSTEMATICS_DOMINANT"
    ).sum() == 4
    assert (
        derived["inobservable_status"]
        == "POSITIVE_CONDITIONAL_SENSITIVITY_ENVELOPE_95"
    ).all()


def test_cross_shadow_atlas_requires_galaxy_level_overlap():
    lensing = derive_lensing_inobservables(
        load_lensing_rar_table(TABLE), MultiShadowConfig()
    )
    sparc = pd.DataFrame(
        {
            "galaxy": [f"G{i}" for i in range(6)],
            "g_baryonic_p50_m_s2": [10.0**-11.41] * 6,
            "g_observed_p50_m_s2": [10.0**-10.70] * 6,
            "authority": ["TEST_CHECKED_SURFACE"] * 6,
        }
    )
    atlas = build_cross_shadow_atlas(lensing, sparc, MultiShadowConfig())
    assert (
        atlas.iloc[0]["comparison_status"]
        == "DESCRIPTIVE_OVERLAP_NO_JOINT_LIKELIHOOD"
    )
    assert (
        atlas.iloc[-1]["comparison_status"]
        == "NOT_ESTIMABLE_INSUFFICIENT_SPARC_OVERLAP"
    )
    assert atlas.iloc[0]["sparc_galaxies_in_window"] == 6


def test_summary_refuses_object_level_or_model_authority():
    lensing = derive_lensing_inobservables(
        load_lensing_rar_table(TABLE), MultiShadowConfig()
    )
    sparse = pd.DataFrame(
        {
            "galaxy": ["G0"],
            "g_baryonic_p50_m_s2": [10.0**-11.41],
            "g_observed_p50_m_s2": [10.0**-10.70],
            "authority": ["TEST_CHECKED_SURFACE"],
        }
    )
    atlas = build_cross_shadow_atlas(lensing, sparse, MultiShadowConfig())
    summary = summarize_multishadow(
        lensing, atlas, MultiShadowConfig(), {"schema": "test"}
    )
    assert summary["decision"] == DECISION
    assert "joint SPARC-KiDS likelihood or independent confirmation" in summary[
        "not_estimable"
    ]
    assert "MOND or Lambda-CDM adjudication" in summary["not_estimable"]
