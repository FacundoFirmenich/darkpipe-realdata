"""Projection-aware spectral primitives; diagnostics, not detection claims."""
import numpy as np
from scipy import signal

def project_nuisance(y,design):
    target=np.asarray(y,float);matrix=np.asarray(design,float)
    if target.ndim!=1: raise ValueError("y must be one-dimensional")
    if matrix.ndim==1: matrix=matrix[:,None]
    if matrix.shape[0]!=target.size: raise ValueError("design/y length mismatch")
    valid=np.isfinite(target)&np.all(np.isfinite(matrix),axis=1)
    if valid.sum()<=matrix.shape[1]+2: raise ValueError("insufficient observations")
    x=np.column_stack((np.ones(valid.sum()),matrix[valid]));beta,*_=np.linalg.lstsq(x,target[valid],rcond=None)
    residual=np.full(target.shape,np.nan);residual[valid]=target[valid]-x@beta
    return residual,beta

def one_sided_periodogram(y,dt):
    values=np.asarray(y,float);values=values[np.isfinite(values)]
    if values.size<16: raise ValueError("at least 16 observations required")
    return signal.periodogram(signal.detrend(values),fs=1/dt,scaling="density")
def welch_psd(y,dt):
    values=np.asarray(y,float);values=values[np.isfinite(values)]
    if values.size<16: raise ValueError("at least 16 observations required")
    n=max(16,2**int(np.floor(np.log2(min(256,values.size)))))
    return signal.welch(signal.detrend(values),fs=1/dt,window="hann",nperseg=n,noverlap=n//2,detrend=False,scaling="density")
def whittle_loglikelihood(periodogram,spectral_density):
    obs=np.asarray(periodogram,float);model=np.asarray(spectral_density,float)
    if obs.shape!=model.shape: raise ValueError("shape mismatch")
    valid=np.isfinite(obs)&np.isfinite(model)&(model>0)
    if not valid.any(): raise ValueError("no positive finite spectral bins")
    return float(-np.sum(np.log(model[valid])+obs[valid]/model[valid]))
def whittle_baseline_score(y,dt):
    f,p=one_sided_periodogram(y,dt);fw,s=welch_psd(y,dt);model=np.interp(f,fw,s,left=np.nan,right=np.nan);positive=f>0
    floor=np.nanmedian(model[positive])*1e-12;model=np.maximum(model,floor if np.isfinite(floor) and floor>0 else np.finfo(float).tiny)
    return {"constant_free_loglikelihood":whittle_loglikelihood(p[positive],model[positive]),"frequency_bin_count":int(positive.sum()),"min_frequency_hz":float(f[positive].min()),"max_frequency_hz":float(f[positive].max())}
