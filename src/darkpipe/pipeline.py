"""End-to-end bounded live pipeline."""
from pathlib import Path
import pandas as pd
from . import __version__
from .analysis import align_environment,projection_aware_diagnostics
from .authority import environmental_authority_payload
from .provenance import file_record,utc_now,write_bytes,write_json
from .report import render_markdown,write_figure
from .sources import fetch_noaa_rtsw,fetch_usgs_geomag

def _csv(path,frame):
    path.parent.mkdir(parents=True,exist_ok=True);frame.to_csv(path,index=False);return file_record(path,path.parent.parent)
def run_live(output,station="BOU",retain_raw=True,hours=24):
    root=Path(output);root.mkdir(parents=True,exist_ok=True);started=utc_now();solar=fetch_noaa_rtsw();stop=solar.frame.time.max();start=max(solar.frame.time.min(),stop-pd.Timedelta(hours=hours));solar_frame=solar.frame.loc[solar.frame.time.between(start,stop)].copy();geomag=fetch_usgs_geomag(start,stop,station=station);raw=[]
    if retain_raw:
        for name,artifact in zip(("noaa_rtsw_mag.json","noaa_rtsw_wind.json"),solar.artifacts,strict=True): raw.append(write_bytes(root/"raw"/name,artifact.content))
        raw.append(write_bytes(root/"raw"/"usgs_geomag.json",geomag.artifact.content))
    data_records=[_csv(root/"data"/"noaa_solar_wind.csv",solar_frame),_csv(root/"data"/"usgs_geomag.csv",geomag.frame)]
    aligned=align_environment(solar_frame,geomag.frame);analysis,finite=projection_aware_diagnostics(aligned);data_records.append(_csv(root/"data"/"aligned_observations.csv",finite));write_figure(finite,root/"analysis"/"diagnostics.png")
    source_rows=[{"name":solar.source_name,**a.provenance()} for a in solar.artifacts]+[{"name":geomag.source_name,**geomag.artifact.provenance()}]
    report={"schema_version":"1.0","run":{"software_version":__version__,"started_at_utc":started,"finished_at_utc":utc_now(),"station":station.upper(),"requested_hours":hours,"raw_retention":"full" if retain_raw else "hash-only","raw_byte_count":sum(a.byte_count for a in solar.artifacts)+geomag.artifact.byte_count},"sources":source_rows,"analysis":analysis}
    report["authority"]=environmental_authority_payload(analysis,station=station,source_refs=(row["sha256"] for row in source_rows))
    write_json(root/"analysis"/"report.json",report);(root/"analysis"/"report.md").write_text(render_markdown(report),encoding="utf-8");files=[]
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name!="manifest.json": files.append(file_record(p,root))
    write_json(root/"manifest.json",{"schema_version":"1.0","generated_at_utc":utc_now(),"software_version":__version__,"source_artifacts":source_rows,"files":files});return report
