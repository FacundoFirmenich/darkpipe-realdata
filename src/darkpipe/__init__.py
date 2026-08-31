"""DarkPipe real-data-first environmental and sensor validation.

Public symbols are loaded lazily so an independent analysis does not require
optional dependencies belonging only to a different campaign (for example,
HDF5 support for AION inventories).
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


__version__ = "0.17.0"

_EXPORTS: dict[str, tuple[str, str]] = {
    "fetch_noaa_solar_wind": (".sources", "fetch_noaa_solar_wind"),
    "fetch_usgs_geomag": (".sources", "fetch_usgs_geomag"),
    "fetch_hapi": (".sources", "fetch_hapi"),
    "projection_aware_diagnostics": (".analysis", "projection_aware_diagnostics"),
    "whittle_loglikelihood": (".whittle", "whittle_loglikelihood"),
    "AuthorityError": (".authority", "AuthorityError"),
    "ClaimKind": (".authority", "ClaimKind"),
    "ClaimLedger": (".authority", "ClaimLedger"),
    "ClaimRecord": (".authority", "ClaimRecord"),
    "ClaimStatus": (".authority", "ClaimStatus"),
    "ConducenceVector": (".authority", "ConducenceVector"),
    "ObservationEnvelope": (".authority", "ObservationEnvelope"),
    "ObservedDecoupling": (".authority", "ObservedDecoupling"),
    "validate_aion_evidence": (".aion", "validate_aion_evidence"),
    "run_aion_validation": (".aion", "run_aion_validation"),
    "prepare_blind_challenge": (".aion_blind", "prepare_blind_challenge"),
    "analyze_blind_challenge": (".aion_blind", "analyze_blind_challenge"),
    "reveal_blind_challenge": (".aion_blind", "reveal_blind_challenge"),
    "discover_continuous_candidates": (
        ".aion_continuous",
        "discover_continuous_candidates",
    ),
    "confirm_continuous_candidates": (
        ".aion_continuous",
        "confirm_continuous_candidates",
    ),
    "run_inventory": (".aion_independent", "run_inventory"),
    "discover_independent_epoch": (".aion_independent_search", "discover"),
    "confirm_independent_epoch": (".aion_independent_search", "confirm"),
    "MultiShadowConfig": (".multishadow", "MultiShadowConfig"),
    "load_lensing_rar_table": (".multishadow", "load_lensing_rar_table"),
    "derive_lensing_inobservables": (
        ".multishadow",
        "derive_lensing_inobservables",
    ),
    "build_cross_shadow_atlas": (".multishadow", "build_cross_shadow_atlas"),
    "summarize_multishadow": (".multishadow", "summarize_multishadow"),
    "CovarianceOperatorConfig": (
        ".covariance_operator_shadow",
        "CovarianceOperatorConfig",
    ),
    "build_deprojection_operator": (
        ".covariance_operator_shadow",
        "build_deprojection_operator",
    ),
    "derive_operator_shadow": (
        ".covariance_operator_shadow",
        "derive_operator_shadow",
    ),
    "DatasetSpec": (".object_recoverability", "DatasetSpec"),
    "RecoverabilityProbeError": (
        ".object_recoverability",
        "RecoverabilityProbeError",
    ),
    "probe_dataset": (".object_recoverability", "probe_dataset"),
    "probe_default_inputs": (".object_recoverability", "probe_default_inputs"),
    "evaluate_recoverability": (
        ".object_recoverability",
        "evaluate_recoverability",
    ),
    "AcquisitionError": (".remote_acquisition", "AcquisitionError"),
    "AcquisitionReceipt": (".remote_acquisition", "AcquisitionReceipt"),
    "acquire_dataset": (".remote_acquisition", "acquire_dataset"),
    "acquire_default_inputs": (".remote_acquisition", "acquire_default_inputs"),
    "assert_remote_capacity": (".remote_acquisition", "assert_remote_capacity"),
    "DriveDatasetReceipt": (".drive_sharded_acquisition", "DriveDatasetReceipt"),
    "acquire_dataset_sharded": (".drive_sharded_acquisition", "acquire_dataset_sharded"),
    "acquire_default_inputs_to_drive": (
        ".drive_sharded_acquisition",
        "acquire_default_inputs_to_drive",
    ),
    "assert_drive_quota": (".drive_sharded_acquisition", "assert_drive_quota"),
    "FlatLambdaCDM": (".object_lensing", "FlatLambdaCDM"),
    "sigma_critical_msun_mpc2": (".object_lensing", "sigma_critical_msun_mpc2"),
    "tangential_and_cross_ellipticity": (
        ".object_lensing",
        "tangential_and_cross_ellipticity",
    ),
    "accumulate_esd": (".object_lensing", "accumulate_esd"),
    "deproject_spherical_esd": (
        ".object_lensing",
        "deproject_spherical_esd",
    ),
    "fixed_gbar_radius_kpc": (".object_lensing", "fixed_gbar_radius_kpc"),
    "object_level_rar": (".object_lensing", "object_level_rar"),
    "integrate_piecewise_linear_profile": (
        ".kids_exact_deprojection",
        "integrate_piecewise_linear_profile",
    ),
    "deproject_individual_profiles": (
        ".kids_exact_deprojection",
        "deproject_individual_profiles",
    ),
    "stack_inverse_variance": (
        ".kids_exact_deprojection",
        "stack_inverse_variance",
    ),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
