"""
Signal extraction utilities for time-series analysis.

Implements Lomb-Scargle periodogram-based frequency and phase extraction
for unevenly sampled time series data.
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class FrequencyExtractionResult:
    """Results from Lomb-Scargle frequency extraction."""

    frequency: float  # Hz
    fitted_amplitude: float  # Fitted signal amplitude
    fitted_amplitude_err: float  # Uncertainty in fitted amplitude
    fitted_offset: float  # Fitted signal offset/mean
    fitted_offset_err: float  # Uncertainty in fitted offset
    fitted_phase: float  # radians
    fitted_phase_err: float  # radians
    signal_mean: float  # Initial estimate of signal mean
    signal_amplitude: float  # Initial estimate of signal amplitude
    freqs: np.ndarray  # Full periodogram frequencies (Hz)
    pgram: np.ndarray  # Full periodogram power
