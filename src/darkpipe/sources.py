"""Official real-data adapters."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any
import pandas as pd
from .http import FetchArtifact,fetch_json
NOAA_SOLAR_WIND_1H="https://services.swpc.noaa.gov/products/geospace/propagated-solar-wind-1-hour.json"
NOAA_PLANETARY_K="https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
NOAA_RTSW_MAG="https://services.swpc.noaa.gov/json/rtsw/rtsw_mag_1m.json"
NOAA_RTSW_WIND="https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json"
USGS_GEOMAG_DATA="https://geomag.usgs.gov/ws/data/"
USGS_COMCAT="https://earthquake.usgs.gov/fdsnws/event/1/query"
ZENODO_RECORD="https://zenodo.org/api/records/{record_id}"
HAPI_BASES={"intermagnet":"https://imag-data.bgs.ac.uk/GIN_V1/hapi","nasa_cdaweb":"https://cdaweb.gsfc.nasa.gov/hapi"}
@dataclass(frozen=True)
class SourceFrame:
    frame:pd.DataFrame;artifact:FetchArtifact;source_name:str
@dataclass(frozen=True)
class SourceBundle:
    frame:pd.DataFrame;artifacts:tuple[FetchArtifact,...];source_name:str

def _numeric(frame,excluded):
    out=frame.copy()
    for c in out.columns:
        if c not in excluded: out[c]=pd.to_numeric(out[c],errors="coerce")
    return out

def parse_noaa_tabular(payload:Any)->pd.DataFrame:
    if not isinstance(payload,list) or len(payload)<2 or not isinstance(payload[0],list): raise ValueError("NOAA payload is not a header-plus-rows table")
    header=list(map(str,payload[0]));rows=payload[1:]
    if any(not isinstance(r,list) or len(r)!=len(header) for r in rows): raise ValueError("NOAA row width mismatch")
    frame=pd.DataFrame(rows,columns=header);tc="propagated_time_tag" if "propagated_time_tag" in frame else "time_tag"
    if tc not in frame: raise ValueError("NOAA timestamp missing")
    frame["time"]=pd.to_datetime(frame[tc],utc=True,errors="coerce");frame=_numeric(frame,{"time","time_tag","propagated_time_tag"})
    frame=frame.dropna(subset=["time"]).sort_values("time").drop_duplicates("time",keep="last").reset_index(drop=True)
    if frame.empty: raise ValueError("NOAA yielded no valid rows")
    return frame

def fetch_noaa_solar_wind():
    artifact=fetch_json(NOAA_SOLAR_WIND_1H,max_bytes=1_000_000);return SourceFrame(parse_noaa_tabular(artifact.payload),artifact,"NOAA SWPC propagated solar wind")
def fetch_noaa_kp():
    artifact=fetch_json(NOAA_PLANETARY_K,max_bytes=1_000_000);return SourceFrame(parse_noaa_tabular(artifact.payload),artifact,"NOAA SWPC planetary K index")

def parse_usgs_geomag(payload:Any)->pd.DataFrame:
    if not isinstance(payload,dict) or payload.get("type")!="Timeseries": raise ValueError("USGS payload is not Timeseries")
    times=payload.get("times");series=payload.get("values")
    if not isinstance(times,list) or not isinstance(series,list): raise ValueError("USGS times/values missing")
    data={"time":pd.to_datetime(times,utc=True,errors="coerce")}
    for item in series:
        if not isinstance(item,dict) or "id" not in item or "values" not in item: raise ValueError("USGS series malformed")
        if len(item["values"])!=len(times): raise ValueError(f"USGS length mismatch: {item['id']}")
        data[str(item["id"])]=pd.to_numeric(pd.Series(item["values"]),errors="coerce")
    frame=pd.DataFrame(data).dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
    if frame.empty: raise ValueError("USGS yielded no valid rows")
    return frame

def _iso(value:str|datetime|pd.Timestamp):
    stamp=pd.Timestamp(value);stamp=stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
    return stamp.isoformat().replace("+00:00","Z")
def fetch_usgs_geomag(start,stop,*,station="BOU",elements=("X","Y","Z","F"),data_type="adjusted",sampling_period_seconds=60):
    a,b=_iso(start),_iso(stop)
    if pd.Timestamp(b)<=pd.Timestamp(a): raise ValueError("stop must be later than start")
    params={"id":station.upper(),"starttime":a,"endtime":b,"elements":",".join(elements),"sampling_period":sampling_period_seconds,"type":data_type,"format":"json"}
    artifact=fetch_json(USGS_GEOMAG_DATA,params=params,max_bytes=5_000_000)
    return SourceFrame(parse_usgs_geomag(artifact.payload),artifact,f"USGS Geomagnetism {station.upper()}")

def parse_hapi(payload):
    params=payload.get("parameters");rows=payload.get("data")
    if not isinstance(params,list) or not isinstance(rows,list): raise ValueError("HAPI parameters/data missing")
    names=[str(p.get("name",f"p{i}")) for i,p in enumerate(params)];records=[]
    for row in rows:
        if not isinstance(row,list) or len(row)!=len(names): raise ValueError("HAPI row width mismatch")
        rec={}
        for name,value in zip(names,row,strict=True):
            if isinstance(value,list): rec.update({f"{name}_{i}":v for i,v in enumerate(value)})
            else: rec[name]=value
        records.append(rec)
    frame=pd.DataFrame(records);first=names[0]
    if first not in frame: raise ValueError("HAPI time missing")
    frame=frame.rename(columns={first:"time"});frame["time"]=pd.to_datetime(frame["time"],utc=True,errors="coerce");frame=_numeric(frame,{"time"})
    return frame.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
def fetch_hapi(provider,dataset_id,start,stop):
    if provider not in HAPI_BASES: raise ValueError(f"unknown HAPI provider: {provider}")
    base=HAPI_BASES[provider]
    info=fetch_json(base+"/info",params={"id":dataset_id},max_bytes=2_000_000)
    data=fetch_json(base+"/data",params={"id":dataset_id,"time.min":_iso(start),"time.max":_iso(stop),"format":"json"},max_bytes=10_000_000)
    combined=dict(data.payload);combined["parameters"]=info.payload.get("parameters")
    return SourceBundle(parse_hapi(combined),(info,data),f"HAPI {provider}:{dataset_id}")
def fetch_zenodo_metadata(record_id): return fetch_json(ZENODO_RECORD.format(record_id=record_id),max_bytes=2_000_000)

def fetch_noaa_rtsw():
    """Fetch and merge the bounded NOAA real-time solar-wind magnetic/plasma products."""
    mag=fetch_json(NOAA_RTSW_MAG,max_bytes=3_000_000);wind=fetch_json(NOAA_RTSW_WIND,max_bytes=4_000_000)
    m=pd.DataFrame(mag.payload);w=pd.DataFrame(wind.payload)
    required_mag={"time_tag","bt","bz_gsm"};required_wind={"time_tag","proton_speed","proton_density"}
    if not required_mag.issubset(m.columns) or not required_wind.issubset(w.columns): raise ValueError("NOAA RTSW schema changed")
    m["time"]=pd.to_datetime(m.time_tag,utc=True,errors="coerce");w["time"]=pd.to_datetime(w.time_tag,utc=True,errors="coerce")
    m=m[["time","bt","bz_gsm"]].rename(columns={"bz_gsm":"bz"});w=w[["time","proton_speed","proton_density"]].rename(columns={"proton_speed":"speed","proton_density":"density"})
    m=_numeric(m,{"time"}).dropna(subset=["time"]).sort_values("time");w=_numeric(w,{"time"}).dropna(subset=["time"]).sort_values("time")
    frame=pd.merge_asof(m,w,on="time",direction="nearest",tolerance=pd.Timedelta(seconds=45)).dropna(subset=["bt","bz","speed","density"]).drop_duplicates("time").reset_index(drop=True)
    if len(frame)<60: raise ValueError(f"NOAA RTSW yielded only {len(frame)} complete rows")
    return SourceBundle(frame,(mag,wind),"NOAA SWPC RTSW magnetic and plasma")