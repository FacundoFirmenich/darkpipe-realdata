"""DarkPipe real-data-first foreground diagnostics."""
from .sources import fetch_noaa_solar_wind, fetch_usgs_geomag, fetch_hapi
from .analysis import projection_aware_diagnostics
from .whittle import whittle_loglikelihood
__version__="0.3.0"
__all__=["fetch_noaa_solar_wind","fetch_usgs_geomag","fetch_hapi","projection_aware_diagnostics","whittle_loglikelihood"]
