# Source endpoints verified on 2026-08-25

| Provider | Endpoint | Live status | Role |
|---|---|---:|---|
| NOAA SWPC | https://services.swpc.noaa.gov/json/rtsw/rtsw_mag_1m.json | 200 | Default one-minute magnetic product |
| NOAA SWPC | https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json | 200 | Default one-minute plasma product |
| NOAA SWPC | https://services.swpc.noaa.gov/products/geospace/propagated-solar-wind-1-hour.json | 200 | Probe only; not default because propagated timestamps can exceed current adjusted terrestrial availability |
| NOAA SWPC | https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json | 200 | Optional planetary K product |
| USGS | https://geomag.usgs.gov/ws/openapi.json | 200 | Current API contract |
| USGS | https://geomag.usgs.gov/ws/data/ | 200 | Default BOU XYZF time series |
| INTERMAGNET/BGS | https://imag-data.bgs.ac.uk/GIN_V1/hapi/capabilities | 200 | HAPI capability contract |
| NASA CDAWeb | https://cdaweb.gsfc.nasa.gov/hapi/capabilities | 200 | HAPI capability contract |

The inherited v0.2 routes products/solar-wind/mag-7-day.json and products/solar-wind/plasma-7-day.json both returned 404 on 2026-08-25. They are deliberately not used. This is a provider-evolution finding, not evidence that earlier snapshots were fabricated.

Catalog checks found 3,074 INTERMAGNET and 3,631 NASA CDAWeb datasets. DarkPipe queries explicit dataset IDs and never downloads a full catalog during a normal run.
