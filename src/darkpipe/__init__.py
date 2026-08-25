"""DarkPipe real-data-first environmental and sensor validation."""
from .aion import run_aion_validation, validate_aion_evidence
from .analysis import projection_aware_diagnostics
from .sources import fetch_hapi, fetch_noaa_solar_wind, fetch_usgs_geomag
from .whittle import whittle_loglikelihood

__version__ = "0.4.0"
__all__ = [
    "fetch_noaa_solar_wind",
    "fetch_usgs_geomag",
    "fetch_hapi",
    "projection_aware_diagnostics",
    "whittle_loglikelihood",
    "validate_aion_evidence",
    "run_aion_validation",
]
