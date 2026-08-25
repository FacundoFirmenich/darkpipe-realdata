"""Observed-data alignment and projection-aware foreground diagnostics."""
import numpy as np
import pandas as pd
from scipy import signal,stats
from .whittle import project_nuisance,welch_psd,whittle_baseline_score

def _residual(values):
    x=np.asarray(values,float);x=x[np.isfinite(x)]
    if x.size<20: raise ValueError("at least 20 residuals required")
    med=float(np.median(x));mad=float(np.median(abs(x-med)));rs=1.4826*mad;n=stats.normaltest(x)
    return {"count":int(x.size),"mean":float(x.mean()),"standard_deviation":float(x.std(ddof=1)),"median":med,"mad":mad,"skewness":float(stats.skew(x,bias=False)),"excess_kurtosis":float(stats.kurtosis(x,fisher=True,bias=False)),"normaltest_statistic":float(n.statistic),"normaltest_pvalue":float(n.pvalue),"robust_three_sigma_tail_fraction":float(np.mean(abs(x-med)>3*rs)) if rs>0 else 0.0}
def _lag(x,y,max_lag=15):
    x=np.asarray(x,float);y=np.asarray(y,float);rows=[]
    for lag in range(-max_lag,max_lag+1):
        xa,ya=(x[-lag:],y[:lag]) if lag<0 else ((x[:-lag],y[lag:]) if lag>0 else (x,y));valid=np.isfinite(xa)&np.isfinite(ya)
        r=float(np.corrcoef(xa[valid],ya[valid])[0,1]) if valid.sum()>=8 else float("nan");rows.append({"lag_minutes":lag,"correlation":r,"pair_count":int(valid.sum())})
    finite=[row for row in rows if np.isfinite(row["correlation"])];best=max(finite,key=lambda row:abs(row["correlation"])) if finite else None
    return {"scan":rows,"max_absolute_correlation":best}
def _coherence(x,y,dt=60):
    valid=np.isfinite(x)&np.isfinite(y);a=np.asarray(x)[valid];b=np.asarray(y)[valid]
    if a.size<16: raise ValueError("at least 16 pairs required")
    n=max(16,2**int(np.floor(np.log2(min(128,a.size)))));f,c=signal.coherence(signal.detrend(a),signal.detrend(b),fs=1/dt,nperseg=n);pos=f>0;i=np.flatnonzero(pos)[int(np.nanargmax(c[pos]))]
    return {"max_coherence":float(c[i]),"frequency_at_max_hz":float(f[i]),"positive_frequency_bin_count":int(pos.sum()),"nperseg":int(n)}
def align_environment(noaa,geomag,tolerance_seconds=75):
    left=geomag.copy().sort_values("time");right=noaa.copy().sort_values("time");right=right.rename(columns={c:f"sw_{c}" for c in right if c!="time"})
    merged=pd.merge_asof(left,right,on="time",direction="nearest",tolerance=pd.Timedelta(seconds=tolerance_seconds))
    if "F" not in merged: raise ValueError("geomagnetic F required")
    merged["geomag_dF_dt_nT_per_min"]=pd.to_numeric(merged["F"],errors="coerce").diff();return merged
def projection_aware_diagnostics(aligned):
    cols=[f"sw_{c}" for c in ("bz","bt","speed","density") if f"sw_{c}" in aligned]
    if len(cols)<2: raise ValueError("two solar-wind nuisance channels required")
    work=aligned[["time","geomag_dF_dt_nT_per_min",*cols]].copy()
    for c in work.columns[1:]: work[c]=pd.to_numeric(work[c],errors="coerce")
    finite=work.dropna()
    if len(finite)<32: raise ValueError(f"insufficient aligned finite rows: {len(finite)} < 32")
    y=finite["geomag_dF_dt_nT_per_min"].to_numpy(float);design=finite[cols].to_numpy(float);scale=np.std(design,axis=0,ddof=1);scale[scale==0]=1;z=(design-design.mean(axis=0))/scale;res,beta=project_nuisance(y,z);finite=finite.assign(projected_residual_nT_per_min=res);driver=finite["sw_bz"].to_numpy(float) if "sw_bz" in finite else design[:,0]
    f,s=welch_psd(res,60)
    result={"jurisdiction":"environmental foreground characterization; not a dark-sector detection test","aligned_finite_rows":int(len(finite)),"time_start_utc":finite.time.min().isoformat(),"time_stop_utc":finite.time.max().isoformat(),"target":"first difference of USGS geomagnetic F at one-minute cadence","nuisance_channels":cols,"projection_coefficients":{"intercept":float(beta[0]),**{c:float(v) for c,v in zip(cols,beta[1:],strict=True)}},"residual_diagnostics":_residual(res),"whittle_baseline":whittle_baseline_score(res,60),"bz_to_geomag_lag_scan":_lag(driver,y),"bz_to_geomag_coherence":_coherence(driver,y),"residual_welch_psd":{"frequency_hz":f.tolist(),"density":s.tolist(),"units":"(nT/min)^2/Hz"}}
    return result,finite
