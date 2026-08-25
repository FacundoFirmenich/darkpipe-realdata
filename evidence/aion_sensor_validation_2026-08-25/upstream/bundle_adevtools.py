"""
Allan deviation calculators for standard and overalapping adevs with error bars matching Stable32

Adapted from https://github.com/amv213/Stable32-AllanTools/blob/master/Stable87.py
"""

import allantools
import numpy as np


def get_better_ade(tau, adev, tau0, N, alpha=0, d=2, overlapping=True, modified=False):
    """Calculate non-naive Allan deviation errors. Equivalent to Stable32.

    Ref:
        https://github.com/aewallin/allantools/blob/master/examples/ci_demo.py
        https://ntrs.nasa.gov/archive/nasa/casi.ntrs.nasa.gov/20050061319.pdf

    Args:
        tau (list of floats):           list of tau_values for which deviations were computed
        adev (list of floats):          list of ADEV (or another statistic) deviations
        tau0 (float):                   averaging factor;  average interval between measurements
        N (int):                        number of frequency observations
        alpha (int, optional):          +2,...,-4   noise type, either estimated or known
        d (int, optional):              statistic code: 1 first-difference variance, 2 allan variance, 3 hadamard
                                        variance
        overlapping (bool, optional):   True if overlapping statistic used. False if standard statistic used
        modified (bool, optional):      True if modified statistic used. False if standard statistic used.

    Returns:
        err_lo (list of floats):        non-naive lower 1-sigma confidence interval for each point over which deviations
                                        were computed
        err_high (list of floats):      non-naive higher 1-sigma confidence interval for each point over which deviations
                                        were computed
    """

    # Confidence-intervals for each (tau, adev) pair separately.
    cis = []
    for t, dev in zip(tau, adev):
        # Greenhalls EDF (Equivalent Degrees of Freedom)
        edf = allantools.edf_greenhall(
            alpha=alpha,
            d=d,
            m=t / tau0,
            N=N,
            overlapping=overlapping,
            modified=modified,
        )
        # with the known EDF we get CIs
        (lo, hi) = allantools.confidence_interval(dev=dev, edf=edf)
        cis.append((lo, hi))

    err_lo = np.array([d - ci[0] for (d, ci) in zip(adev, cis)])
    err_hi = np.array([ci[1] - d for (d, ci) in zip(adev, cis)])

    return err_lo, err_hi


def oadev(data, rate, scale=1, alpha=0, taus=None):
    """Calculate overlapping Allan deviation with non-naive errors, from frequency data file.

    Args:
        data (array):          1D array of (fractional frequency) data
        rate (float):          1/(time interval between data)
        scale (float, optional):    scaling factor for fractional frequency. Defaults to 1
        alpha (int, optional):      +2,...,-4   noise type, either estimated or known. Defaults to 0 to match Stable 32

    Returns:
        t2 (list of floats):                            list of tau_values for which deviations were computed
        ad_ff (list of floats):                         list of oadev deviations in fractional frequency units
        err_lo_ff (list of floats):                     list of non-naive lower 1-sigma errors for each point over which
                                                        deviations were computed
        err_hi_ff (list of floats):                     list of non-naive higher 1-sigma errors for each point over
                                                        which deviations were computed
        adn (list):                                     list of number of pairs in overlapping allan computation

    """

    (t2, ad, ade, adn) = allantools.oadev(
        data, rate=rate, data_type="freq", taus=taus
    )  # normal ODEV computation, giving naive 1/sqrt(N) errors

    # correct for deadtime ad/np.sqrt(B2*B3)
    # https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication1065.pdf | 5.15 Dead Time
    # TODO

    # Get correct (Stable32) errors
    avg_interval = 1 / rate
    err_lo, err_hi = get_better_ade(
        t2,
        ad,
        avg_interval,
        len(data),
        alpha=alpha,
        d=2,
        overlapping=True,
        modified=False,
    )

    ad_ff = ad * scale
    err_lo_ff = err_lo * scale
    err_hi_ff = err_hi * scale

    return t2, ad_ff, err_lo_ff, err_hi_ff, adn
