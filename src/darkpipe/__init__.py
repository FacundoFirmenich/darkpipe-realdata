"""DarkPipe real-data-first environmental and sensor validation."""
from .aion import run_aion_validation, validate_aion_evidence
from .aion_blind import analyze_blind_challenge, prepare_blind_challenge, reveal_blind_challenge
from .aion_continuous import confirm_continuous_candidates, discover_continuous_candidates
from .aion_independent import run_inventory
from .aion_independent_search import confirm as confirm_independent_epoch
from .aion_independent_search import discover as discover_independent_epoch
from .analysis import projection_aware_diagnostics
from .authority import (
    AuthorityError, ClaimKind, ClaimLedger, ClaimRecord, ClaimStatus,
    ConducenceVector, ObservationEnvelope, ObservedDecoupling,
)
from .sources import fetch_hapi, fetch_noaa_solar_wind, fetch_usgs_geomag
from .whittle import whittle_loglikelihood

__version__ = "0.8.0"
__all__ = [
    "fetch_noaa_solar_wind",
    "fetch_usgs_geomag",
    "fetch_hapi",
    "projection_aware_diagnostics",
    "whittle_loglikelihood",
    "AuthorityError",
    "ClaimKind",
    "ClaimLedger",
    "ClaimRecord",
    "ClaimStatus",
    "ConducenceVector",
    "ObservationEnvelope",
    "ObservedDecoupling",
    "validate_aion_evidence",
    "run_aion_validation",
    "prepare_blind_challenge",
    "analyze_blind_challenge",
    "reveal_blind_challenge",
    "discover_continuous_candidates",
    "confirm_continuous_candidates",
    "run_inventory",
    "discover_independent_epoch",
    "confirm_independent_epoch",
]
