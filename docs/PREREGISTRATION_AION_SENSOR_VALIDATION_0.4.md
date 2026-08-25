# DarkPipe 0.4 preregistration: AION sensor-level validation

Preregistration ID: `DP-AION-0.4-20260825`

Status at commit: frozen before DarkPipe computes any endpoint reported below.

## Governing objective and jurisdiction

This campaign tests whether DarkPipe can ingest and adjudicate authentic differential atom-interferometer evidence with a fixed, auditable validation protocol. It is a software-and-instrument validation, not a search for a new physical signal.

The experimental source is the AION Collaboration tabletop differential interferometer using two vertically separated fermionic strontium-87 ensembles. The upstream article reports common-mode laser-noise rejection and recovery of intentionally injected coherent differential-phase modulations.

Authority ceiling: a passing result establishes correct custody and recovery of published instrumental controls within the selected AION record. It does not establish sensitivity of AION-10/AION-km, detect gravitational waves, detect ultralight dark matter, validate an astrophysical population model, or estimate a false-alarm rate for an unblinded discovery search.

## Frozen evidence

- Article: C. F. A. Baynham et al., “A prototype differential atom interferometer for fundamental physics”, Nature 654, 622–628 (2026), DOI `10.1038/s41586-026-10617-1`.
- Data/code record: Zenodo DOI `10.5281/zenodo.19592552`.
- Upstream archive: `data_analysis.zip`, 134,533,837 bytes, MD5 `f2898d155564d1ec9e11cdea17e76de6` as declared by Zenodo.
- Stream-selected manifest: 27 paths, SHA-256 `ED4D7768389A1775286AF1F45BC56384FB95B3E392EF6634D2EB9A3813BCE843`.
- Selected evidence: 27 files, 19,018,652 bytes.
- Selected-evidence inventory SHA-256: `d2382637d12b99252a3ede1c6109791d98277c04d0757c32e2b593c0847234bd`.

The 1,195,587,720-byte raw HDF5/code archive at Zenodo record `15166669` is outside this bounded campaign and was not downloaded.

## Licensing boundary

Zenodo labels the deposited record `CC-BY-4.0`; the archive also contains an MIT license for the upstream AION software bundle. DarkPipe preserves both facts: deposited data/derived evidence is attributed under the record’s CC BY 4.0 metadata, while upstream software remains under its bundled MIT notice. DarkPipe’s original code is licensed separately as `GPL-3.0-or-later`. No upstream bytes are relicensed by this project.

## Gate 0: integrity and schema

The campaign must abstain if any of the following occurs:

1. any selected file is absent or its SHA-256 differs from the frozen inventory;
2. CSV parsing with comment marker `#` fails;
3. a required column, dataset-to-file mapping, final MLE iteration, or truth-frequency NPZ field is absent;
4. an injected record has no finite timestamp span or fewer than 1,000 finite paired excitation measurements;
5. a derived array contains non-finite values;
6. fewer or more than seven injected-frequency datasets are matched one-to-one.

Timestamp reversals are counted and reported. They do not trigger silent row deletion or interpolation because endpoint E1 uses only the preserved minimum and maximum timestamps to define observation duration. Duplicate maxima in likelihood use the smallest `f_hz`, fixed before execution.

## Primary endpoint E1: injected-frequency recovery

Inputs:

- the seven AION injected-signal excitation CSV files, nominally spanning 0.1–100 mHz;
- `signal_fitting_results_by_frequency.csv`;
- the seven corresponding `precomputed_true_signals/*.npz` files.

For each dataset `d`:

1. retain only the maximum recorded MLE iteration for that dataset, following the upstream Figure 5a notebook;
2. define the recovered frequency `f_hat(d)` as the `f_hz` with maximum `fit_logL` (smallest frequency breaks an exact tie);
3. read the independently precomputed injected-signal frequency `f_true(d)` from the matching NPZ;
4. define duration `T(d) = max(timestamp) - min(timestamp)` from the corresponding excitation CSV;
5. calculate the resolution-normalized error `epsilon(d) = abs(f_hat(d) - f_true(d)) * T(d)`.

An individual recovery passes when `epsilon <= 1`, that is, when the estimate lies within one Fourier-resolution cell `1/T` of the independently recorded injected frequency. E1 passes only if all seven datasets pass. No frequency, dataset, or outlier may be removed after execution.

## Primary endpoint E2: HLN versus LLN differential-noise consistency

Inputs:

- low-laser-noise/nonrandomised excitation data: 28,309 shots;
- high-laser-noise/randomised excitation data: 28,314 shots;
- `sigma_delta_phi_nonrandomised.npy` and `sigma_delta_phi_randomised.npy`, each containing 8,000 upstream phase-uncertainty realizations;
- fixed block size: 141 shots, as specified in the article’s stability analysis.

For condition `j`, define:

- `m_j = mean(sigma_j) / sqrt(n_j / 141)`;
- `u_j = max(mean(sigma_j) - percentile16(sigma_j), percentile84(sigma_j) - mean(sigma_j)) / sqrt(n_j / 141)`.

Define `D = m_HLN - m_LLN`, `u_D = sqrt(u_HLN^2 + u_LLN^2)`, and the two-sided 95% normal interval `D ± 1.96 u_D`.

E2 passes if that interval includes zero. A pass means “no statistically resolved HLN–LLN excess within this upstream uncertainty representation”; it is not an equivalence proof and does not bound all systematics. The per-condition comparison with the published single-shot SQL `43.5(1.6) mrad` is secondary and descriptive, not a gate.

## Mandatory negative and abstaining results

The selected deposit does not contain a preregistered, blind, no-injection frequency scan with its full trials-calibrated null ensemble. Therefore:

- discovery-search false-positive rate: `NOT_ESTIMABLE`;
- global dark-matter or gravitational-wave significance: `NOT_ESTIMABLE`;
- sensitivity transfer from the 1 mm tabletop baseline to AION-10/AION-km: `NOT_ESTIMABLE`;
- independent reproduction of the complete upstream marginal-likelihood pipeline from raw HDF5: `NOT_ESTIMABLE`.

These are jurisdictional limits, not failed detections.

## Terminal decision rule

- `PASS_BOUNDED`: Gate 0 passes, E1 passes 7/7, and E2 passes.
- `FAIL_BOUNDED`: Gate 0 passes but E1 or E2 fails; every adverse dataset remains reported.
- `ABSTAIN_INTEGRITY`: Gate 0 fails; no scientific endpoint is promoted.

No threshold or rule may be changed after the preregistration commit. Any later exploratory analysis must be labelled exploratory and must not rewrite this decision.
