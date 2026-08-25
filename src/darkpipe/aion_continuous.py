"""Split-sample continuous AION search with measured environmental controls.

The campaign searches authentic AION control observations. It does not encode a
physical coupling model for the morphotopological plasma-hyperstate conjecture and
cannot promote an unexplained sensor candidate to a physical detection.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .aion import validate_aion_evidence
from .aion_blind import (
    ARMS,
    CONDITIONS,
    GROUPS,
    _build_design,
    _circular_correlations,
    _fit_development_models,
    _fringe_derivative,
    _load_controls,
    _nuisance_basis,
    _scan,
)
from .provenance import file_record, sha256_file, utc_now, write_bytes, write_json
from .sources import fetch_hapi, parse_hapi

CAMPAIGN_ID = "DP-AION-CONTINUOUS-0.7-20260825"
FREQUENCY_MIN_HZ = 1.0e-4
FREQUENCY_MAX_HZ = 7.5e-2
GRID_OVERSAMPLING = 1
MAX_CANDIDATES = 8
EXCLUSION_RAYLEIGH_CELLS = 2
ENGINEERING_PROBE_FREQUENCIES_HZ = (1.0e-4, 1.2345e-3, 3.0e-2, 9.9e-2)
ENGINEERING_EXCLUSION_RAYLEIGH_CELLS = 2
NULL_SURROGATES = 4095
FAMILY_ALPHA = 0.05
CALIBRATION_SEED = 2026082507
ENVIRONMENT_PERMUTATIONS = 4095
ENVIRONMENT_SEED = 2026082517
ENVIRONMENT_BLOCKS = 8
MIN_VALID_ENVIRONMENT_BLOCKS = 6
PHASE_INFORMATION_QUANTILE = 0.10
HAD_DATASET = "had/best-avail/PT1S/xyzf"
OMNI_DATASET = "OMNI_HRO2_1MIN"
OMNI_NYQUIST_HZ = 1.0 / 120.0
HAD_COMPONENTS = ("Field_Vector_0", "Field_Vector_1", "Field_Vector_2", "Field_Magnitude")
OMNI_COMPONENTS = ("F", "BZ_GSM", "flow_speed", "proton_density", "Pressure", "Beta", "SYM_H", "AE_INDEX")


def _group_scan_state(
    controls: dict[str, dict[str, Any]], models: dict[str, Any], subset: str
) -> list[dict[str, np.ndarray]]:
    states = []
    for condition, arm in GROUPS:
        info = controls[condition]
        frame = info[subset]
        key = f"{condition}_{arm}"
        scale = float(models[key]["scale"])
        x = _nuisance_basis(frame, info["bounds"]) / scale
        y = frame[f"excitation_fraction_{arm}"].to_numpy(float) / scale
        beta, *_ = np.linalg.lstsq(x, y, rcond=None)
        residual = y - x @ beta
        derivative = _fringe_derivative(frame, info["bounds"], models[key]["beta"])
        sign = 0.5 if arm == "forward" else -0.5
        amplitude = sign * derivative / scale
        states.append(
            {
                "time": frame["timestamp"].to_numpy(float),
                "amplitude": amplitude,
                "x": x,
                "x_gram_inverse": np.linalg.pinv(x.T @ x, rcond=1.0e-12),
                "residual": residual,
            }
        )
    return states


def score_frequency_family(
    controls: dict[str, dict[str, Any]],
    models: dict[str, Any],
    subset: str,
    frequencies_hz: np.ndarray,
    *,
    batch_size: int = 48,
) -> np.ndarray:
    """Return exact profiled two-quadrature score statistics in bounded batches."""
    frequencies = np.asarray(frequencies_hz, dtype=float)
    if frequencies.ndim != 1 or len(frequencies) == 0:
        raise ValueError("frequencies_hz must be a non-empty vector")
    if np.any(~np.isfinite(frequencies)) or np.any(frequencies <= 0):
        raise ValueError("frequencies_hz must contain finite positive values")
    states = _group_scan_state(controls, models, subset)
    statistics = np.empty(len(frequencies), dtype=float)

    for start in range(0, len(frequencies), batch_size):
        stop = min(start + batch_size, len(frequencies))
        batch = frequencies[start:stop]
        width = len(batch)
        score = np.zeros((width, 2), dtype=float)
        gram = np.zeros((width, 2, 2), dtype=float)

        for state in states:
            phase = 2.0 * math.pi * np.outer(state["time"] - state["time"].min(), batch)
            zc = state["amplitude"][:, None] * np.cos(phase)
            zs = state["amplitude"][:, None] * np.sin(phase)
            pc = state["x"].T @ zc
            ps = state["x"].T @ zs
            inverse = state["x_gram_inverse"]
            score[:, 0] += zc.T @ state["residual"]
            score[:, 1] += zs.T @ state["residual"]
            gram[:, 0, 0] += np.sum(zc * zc, axis=0) - np.einsum(
                "ib,ij,jb->b", pc, inverse, pc
            )
            gram[:, 1, 1] += np.sum(zs * zs, axis=0) - np.einsum(
                "ib,ij,jb->b", ps, inverse, ps
            )
            cross = np.sum(zc * zs, axis=0) - np.einsum(
                "ib,ij,jb->b", pc, inverse, ps
            )
            gram[:, 0, 1] += cross
            gram[:, 1, 0] += cross

        det = gram[:, 0, 0] * gram[:, 1, 1] - gram[:, 0, 1] ** 2
        valid = det > np.finfo(float).eps * np.maximum(
            gram[:, 0, 0] * gram[:, 1, 1], 1.0
        )
        values = np.full(width, np.nan)
        numerator = (
            gram[:, 1, 1] * score[:, 0] ** 2
            - 2.0 * gram[:, 0, 1] * score[:, 0] * score[:, 1]
            + gram[:, 0, 0] * score[:, 1] ** 2
        )
        values[valid] = numerator[valid] / det[valid]
        statistics[start:stop] = values
    return statistics


def _development_cadence(
    controls: dict[str, dict[str, Any]],
) -> dict[str, dict[str, float]]:
    result = {}
    for condition in CONDITIONS:
        timestamps = controls[condition]["development"]["timestamp"].to_numpy(float)
        intervals = np.diff(timestamps)
        positive = intervals[np.isfinite(intervals) & (intervals > 0)]
        if len(positive) == 0:
            raise ValueError(f"{condition} has no positive development intervals")
        median = float(np.median(positive))
        result[condition] = {
            "median_interval_seconds": median,
            "nominal_median_nyquist_hz": 0.5 / median,
            "irregular_sampling": True,
        }
    return result


def _continuous_grid(controls: dict[str, dict[str, Any]], subset: str) -> tuple[np.ndarray, dict[str, float]]:
    start = min(float(controls[c][subset]["timestamp"].min()) for c in CONDITIONS)
    stop = max(float(controls[c][subset]["timestamp"].max()) for c in CONDITIONS)
    duration = stop - start
    if duration <= 0:
        raise ValueError("non-positive campaign duration")
    rayleigh = 1.0 / duration
    step = rayleigh / GRID_OVERSAMPLING
    first = int(math.ceil(FREQUENCY_MIN_HZ / step))
    last = int(math.floor(FREQUENCY_MAX_HZ / step))
    frequencies = np.arange(first, last + 1, dtype=float) * step
    return frequencies, {
        "start_unix": start,
        "stop_unix": stop,
        "duration_seconds": duration,
        "rayleigh_hz": rayleigh,
        "step_hz": step,
    }


def _select_candidates(
    frequencies: np.ndarray, statistics: np.ndarray, rayleigh_hz: float
) -> list[dict[str, Any]]:
    if len(frequencies) != len(statistics):
        raise ValueError("frequency/statistic length mismatch")
    finite = np.isfinite(statistics)
    local = np.zeros(len(statistics), dtype=bool)
    if len(statistics) >= 3:
        local[1:-1] = (
            finite[1:-1]
            & (statistics[1:-1] >= statistics[:-2])
            & (statistics[1:-1] > statistics[2:])
        )
    indices = np.flatnonzero(local)
    order = sorted(indices, key=lambda i: (-float(statistics[i]), float(frequencies[i])))
    selected: list[int] = []
    exclusion = EXCLUSION_RAYLEIGH_CELLS * rayleigh_hz
    for index in order:
        if any(
            abs(float(frequencies[index]) - probe) < ENGINEERING_EXCLUSION_RAYLEIGH_CELLS * rayleigh_hz
            for probe in ENGINEERING_PROBE_FREQUENCIES_HZ
        ):
            continue
        if all(abs(float(frequencies[index] - frequencies[other])) >= exclusion for other in selected):
            selected.append(int(index))
        if len(selected) == MAX_CANDIDATES:
            break
    return [
        {
            "candidate_id": f"c{rank:03d}",
            "rank": rank,
            "grid_index": index,
            "frequency_hz": float(frequencies[index]),
            "development_statistic": float(statistics[index]),
        }
        for rank, index in enumerate(selected, start=1)
    ]


def _write_discovery_figure(
    frequencies: np.ndarray, statistics: np.ndarray, candidates: list[dict[str, Any]], path: Path
) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 5.0), constrained_layout=True)
    ax.plot(frequencies * 1.0e3, statistics, color="#264653", linewidth=0.65)
    if candidates:
        ax.scatter(
            [item["frequency_hz"] * 1.0e3 for item in candidates],
            [item["development_statistic"] for item in candidates],
            color="#d1495b",
            s=35,
            zorder=3,
            label="frozen candidates",
        )
        ax.legend()
    ax.set_xscale("log")
    ax.set(
        xlabel="Frequency [mHz]",
        ylabel="Profiled score statistic",
        title="AION development-only continuous scan",
    )
    fig.savefig(path, dpi=180)
    plt.close(fig)


def discover_continuous_candidates(
    evidence_root: str | Path, campaign_dir: str | Path, preregistration_commit: str
) -> dict[str, Any]:
    """Scan development bytes only and freeze a bounded candidate family."""
    if len(preregistration_commit) < 7:
        raise ValueError("preregistration_commit must identify the frozen Git commit")
    evidence = Path(evidence_root)
    target = Path(campaign_dir)
    target.mkdir(parents=True, exist_ok=True)
    gate = validate_aion_evidence(evidence)
    if not gate["passed"]:
        raise ValueError(f"AION integrity gate failed: {gate['failures']}")
    controls = _load_controls(evidence)
    models = _fit_development_models(controls)
    frequencies, grid = _continuous_grid(controls, "development")
    statistics = score_frequency_family(controls, models, "development", frequencies)
    candidates = _select_candidates(frequencies, statistics, grid["rayleigh_hz"])
    payload = {
        "schema_version": "1.0",
        "campaign_id": CAMPAIGN_ID,
        "generated_at_utc": utc_now(),
        "stage": "DEVELOPMENT_DISCOVERY_ONLY",
        "preregistration_commit": preregistration_commit,
        "holdout_endpoints_accessed": False,
        "source": {
            condition: {
                "sha256": controls[condition]["sha256"],
                "rows": controls[condition]["rows"],
                "development_rows": len(controls[condition]["development"]),
                "holdout_rows": len(controls[condition]["holdout"]),
            }
            for condition in CONDITIONS
        },
        "grid": {
            **grid,
            "frequency_min_hz": FREQUENCY_MIN_HZ,
            "frequency_max_hz": FREQUENCY_MAX_HZ,
            "count": int(len(frequencies)),
            "oversampling": GRID_OVERSAMPLING,
        },
        "development_cadence": _development_cadence(controls),
        "selection_rule": {
            "maximum_candidates": MAX_CANDIDATES,
            "local_maximum": "left >= and right strictly lower",
            "minimum_separation_rayleigh_cells": EXCLUSION_RAYLEIGH_CELLS,
            "engineering_probe_frequencies_hz": list(ENGINEERING_PROBE_FREQUENCIES_HZ),
            "engineering_exclusion_rayleigh_cells": ENGINEERING_EXCLUSION_RAYLEIGH_CELLS,
            "threshold_used": False,
            "tie_break": "higher statistic, then lower frequency",
        },
        "candidates": candidates,
    }
    write_json(target / "discovery_candidates.json", payload)
    _write_discovery_figure(
        frequencies, statistics, candidates, target / "development_continuous_scan.png"
    )
    return payload


def _family_null_calibration(
    design: dict[str, Any], candidate_ids: tuple[str, ...]
) -> dict[str, Any]:
    rng = np.random.default_rng(CALIBRATION_SEED)
    residual = design["residual"]
    shifts = {}
    for condition in CONDITIONS:
        sl = design["slices"][f"{condition}_forward"]
        shifts[condition] = rng.integers(1, sl.stop - sl.start, size=NULL_SURROGATES)
    statistics = np.empty((NULL_SURROGATES, len(candidate_ids)), dtype=float)
    for index, candidate_id in enumerate(candidate_ids):
        item = design["signals"][candidate_id]
        score = np.zeros((NULL_SURROGATES, 2), dtype=float)
        for condition in CONDITIONS:
            correlation = None
            for arm in ARMS:
                sl = design["slices"][f"{condition}_{arm}"]
                current = _circular_correlations(item["zr"][sl], residual[sl])
                correlation = current if correlation is None else correlation + current
            score += correlation[shifts[condition]]
        statistics[:, index] = np.einsum(
            "bi,ij,bj->b", score, item["gram_inverse"], score
        )
    maximum = statistics.max(axis=1)
    allowed = int(math.floor(FAMILY_ALPHA * (NULL_SURROGATES + 1) - 1.0))
    return {
        "surrogates": NULL_SURROGATES,
        "alpha": FAMILY_ALPHA,
        "seed": CALIBRATION_SEED,
        "method": "paired-arm condition-wise circular rotations of holdout residuals",
        "critical_max_statistic": float(np.sort(maximum)[::-1][allowed]),
        "max_statistics": maximum,
    }


def _global_p(statistic: float, null_maximum: np.ndarray) -> float:
    return float(
        (1 + np.count_nonzero(null_maximum >= statistic)) / (len(null_maximum) + 1)
    )


def _phase_proxy(
    controls: dict[str, dict[str, Any]], models: dict[str, Any], subset: str
) -> pd.DataFrame:
    parts = []
    for condition in CONDITIONS:
        info = controls[condition]
        frame = info[subset]
        residuals = {}
        coefficients = {}
        scales = {}
        for arm in ARMS:
            key = f"{condition}_{arm}"
            x = _nuisance_basis(frame, info["bounds"])
            y = frame[f"excitation_fraction_{arm}"].to_numpy(float)
            beta, *_ = np.linalg.lstsq(x, y, rcond=None)
            residuals[arm] = y - x @ beta
            derivative = _fringe_derivative(frame, info["bounds"], models[key]["beta"])
            coefficients[arm] = (0.5 if arm == "forward" else -0.5) * derivative
            scales[arm] = float(models[key]["scale"])
        information = sum(
            (coefficients[arm] / scales[arm]) ** 2 for arm in ARMS
        )
        numerator = sum(
            coefficients[arm] * residuals[arm] / scales[arm] ** 2 for arm in ARMS
        )
        threshold = float(np.nanquantile(information, PHASE_INFORMATION_QUANTILE))
        valid = np.isfinite(numerator) & np.isfinite(information) & (information >= threshold)
        parts.append(
            pd.DataFrame(
                {
                    "time": pd.to_datetime(
                        frame.loc[valid, "timestamp"].to_numpy(float), unit="s", utc=True
                    ),
                    "phase_proxy": numerator[valid] / information[valid],
                    "weight": information[valid],
                    "condition": condition,
                }
            )
        )
    return pd.concat(parts, ignore_index=True).sort_values("time").reset_index(drop=True)


def _load_hapi_receipt(info_path: Path, data_path: Path) -> pd.DataFrame:
    info = json.loads(info_path.read_text(encoding="utf-8"))
    data = json.loads(data_path.read_text(encoding="utf-8"))
    data["parameters"] = info["parameters"]
    frame = parse_hapi(data)
    for parameter in info["parameters"][1:]:
        name = str(parameter["name"])
        fill = parameter.get("fill")
        if fill is None:
            continue
        columns = [name] if name in frame else [column for column in frame if column.startswith(f"{name}_")]
        fills = fill if isinstance(fill, list) else [fill]
        if len(fills) == 1 and len(columns) > 1:
            fills = fills * len(columns)
        for column, raw_fill in zip(columns, fills, strict=False):
            try:
                fill_value = float(raw_fill)
            except (TypeError, ValueError):
                continue
            numeric = pd.to_numeric(frame[column], errors="coerce")
            frame.loc[
                np.isclose(numeric.to_numpy(float), fill_value, rtol=0.0, atol=1.0e-12),
                column,
            ] = np.nan
    return frame


def _environment_frames(
    target: Path, start: pd.Timestamp, stop: pd.Timestamp
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    directory = target / "environment"
    directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "had_info": directory / "had_info.json",
        "had_data": directory / "had_data.json",
        "omni_info": directory / "omni_info.json",
        "omni_data": directory / "omni_data.json",
    }
    if all(path.exists() for path in paths.values()):
        had = _load_hapi_receipt(paths["had_info"], paths["had_data"])
        omni = _load_hapi_receipt(paths["omni_info"], paths["omni_data"])
    else:
        had_source = fetch_hapi(
            "intermagnet", HAD_DATASET, start, stop, max_bytes=80_000_000
        )
        omni_source = fetch_hapi(
            "nasa_cdaweb", OMNI_DATASET, start, stop, max_bytes=25_000_000
        )
        for name, artifact in (
            ("had_info", had_source.artifacts[0]),
            ("had_data", had_source.artifacts[1]),
            ("omni_info", omni_source.artifacts[0]),
            ("omni_data", omni_source.artifacts[1]),
        ):
            write_bytes(paths[name], artifact.content)
        had = _load_hapi_receipt(paths["had_info"], paths["had_data"])
        omni = _load_hapi_receipt(paths["omni_info"], paths["omni_data"])
    for frame in (had, omni):
        for column in frame.columns:
            if column != "time":
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
                frame.loc[frame[column].abs() >= 99_990.0, column] = np.nan
    records = [file_record(path, target) for path in paths.values()]
    return had, omni, records


def _complex_coefficient(
    time_seconds: np.ndarray,
    values: np.ndarray,
    weights: np.ndarray,
    frequency_hz: float,
    origin: float,
) -> complex:
    valid = (
        np.isfinite(time_seconds)
        & np.isfinite(values)
        & np.isfinite(weights)
        & (weights > 0)
    )
    if np.count_nonzero(valid) < 8:
        return complex(np.nan, np.nan)
    time = time_seconds[valid]
    value = values[valid]
    weight = weights[valid]
    span = float(time.max() - time.min())
    coordinate = np.zeros_like(time) if span <= 0 else 2.0 * (time - time.min()) / span - 1.0
    x = np.column_stack([np.ones(len(time)), coordinate])
    root_weight = np.sqrt(weight)
    beta, *_ = np.linalg.lstsq(x * root_weight[:, None], value * root_weight, rcond=None)
    residual = value - x @ beta
    phase = np.exp(-2j * math.pi * frequency_hz * (time - origin))
    return complex(np.sum(weight * residual * phase) / math.sqrt(float(weight.sum())))


def _block_coefficients(
    frame: pd.DataFrame,
    value_columns: tuple[str, ...],
    frequencies: dict[str, float],
    edges: np.ndarray,
    *,
    weight_column: str | None,
    minimum_rows: int,
) -> dict[str, dict[str, np.ndarray]]:
    time = frame["time"].astype("int64").to_numpy(float) / 1.0e9
    origin = float(edges[0])
    output: dict[str, dict[str, np.ndarray]] = {}
    for candidate_id, frequency in frequencies.items():
        output[candidate_id] = {}
        for column in value_columns:
            values = frame[column].to_numpy(float)
            coefficients = []
            for left, right in zip(edges[:-1], edges[1:], strict=True):
                mask = (time >= left) & (time < right)
                if np.count_nonzero(mask) < minimum_rows:
                    coefficients.append(complex(np.nan, np.nan))
                    continue
                weights = (
                    frame.loc[mask, weight_column].to_numpy(float)
                    if weight_column
                    else np.ones(np.count_nonzero(mask), dtype=float)
                )
                coefficients.append(
                    _complex_coefficient(
                        time[mask], values[mask], weights, frequency, origin
                    )
                )
            output[candidate_id][column] = np.asarray(coefficients, dtype=complex)
    return output


def _coherence(first: np.ndarray, second: np.ndarray) -> float:
    valid = (
        np.isfinite(first.real)
        & np.isfinite(first.imag)
        & np.isfinite(second.real)
        & np.isfinite(second.imag)
    )
    if np.count_nonzero(valid) < MIN_VALID_ENVIRONMENT_BLOCKS:
        return float("nan")
    a = first[valid]
    b = second[valid]
    denominator = float(np.vdot(a, a).real * np.vdot(b, b).real)
    if denominator <= 0:
        return float("nan")
    return float(abs(np.vdot(a, b)) ** 2 / denominator)


def _environment_gate(
    proxy: pd.DataFrame,
    had: pd.DataFrame,
    omni: pd.DataFrame,
    detected_frequencies: dict[str, float],
) -> dict[str, Any]:
    start = proxy["time"].min().timestamp()
    stop = proxy["time"].max().timestamp()
    edges = np.linspace(start, stop + 1.0e-6, ENVIRONMENT_BLOCKS + 1)
    aion_coefficients = _block_coefficients(
        proxy,
        ("phase_proxy",),
        detected_frequencies,
        edges,
        weight_column="weight",
        minimum_rows=100,
    )
    had_columns = tuple(column for column in HAD_COMPONENTS if column in had)
    had_coefficients = _block_coefficients(
        had,
        had_columns,
        detected_frequencies,
        edges,
        weight_column=None,
        minimum_rows=1_000,
    )
    observed = []
    for candidate_id in detected_frequencies:
        aion = aion_coefficients[candidate_id]["phase_proxy"]
        for component in had_columns:
            value = _coherence(aion, had_coefficients[candidate_id][component])
            if np.isfinite(value):
                observed.append(
                    {
                        "candidate_id": candidate_id,
                        "component": component,
                        "coherence": value,
                    }
                )
    if not observed:
        return {
            "status": "NOT_ESTIMABLE",
            "reason": "fewer than six valid common spectral blocks",
            "associations": [],
            "omni_context": [],
        }

    rng = np.random.default_rng(ENVIRONMENT_SEED)
    permutations = np.asarray(
        [rng.permutation(ENVIRONMENT_BLOCKS) for _ in range(ENVIRONMENT_PERMUTATIONS)]
    )
    null_maximum = np.zeros(ENVIRONMENT_PERMUTATIONS, dtype=float)
    for permutation_index, permutation in enumerate(permutations):
        maximum = 0.0
        for item in observed:
            aion = aion_coefficients[item["candidate_id"]]["phase_proxy"]
            field = had_coefficients[item["candidate_id"]][item["component"]][permutation]
            value = _coherence(aion, field)
            if np.isfinite(value):
                maximum = max(maximum, value)
        null_maximum[permutation_index] = maximum
    for item in observed:
        item["familywise_p"] = _global_p(item["coherence"], null_maximum)
        item["associated"] = item["familywise_p"] <= FAMILY_ALPHA

    omni_columns = tuple(column for column in OMNI_COMPONENTS if column in omni)
    omni_in_band = {
        candidate_id: frequency
        for candidate_id, frequency in detected_frequencies.items()
        if frequency <= OMNI_NYQUIST_HZ
    }
    omni_context = []
    if omni_in_band and omni_columns:
        omni_coefficients = _block_coefficients(
            omni,
            omni_columns,
            omni_in_band,
            edges,
            weight_column=None,
            minimum_rows=30,
        )
        for candidate_id in omni_in_band:
            aion = aion_coefficients[candidate_id]["phase_proxy"]
            for component in omni_columns:
                value = _coherence(aion, omni_coefficients[candidate_id][component])
                if np.isfinite(value):
                    omni_context.append(
                        {
                            "candidate_id": candidate_id,
                            "component": component,
                            "coherence": value,
                            "role": "context_only_not_veto",
                        }
                    )
    supported = any(item["associated"] for item in observed)
    return {
        "status": "SUPPORTED" if supported else "CONTRADICTED",
        "method": "eight-block complex coherence with block-pair permutation FWER",
        "blocks": ENVIRONMENT_BLOCKS,
        "minimum_valid_blocks": MIN_VALID_ENVIRONMENT_BLOCKS,
        "permutations": ENVIRONMENT_PERMUTATIONS,
        "seed": ENVIRONMENT_SEED,
        "associations": observed,
        "omni_context": omni_context,
        "omni_nyquist_hz": OMNI_NYQUIST_HZ,
    }


def _render_report(report: dict[str, Any]) -> str:
    rows = "\n".join(
        f"| {item['candidate_id']} | {item['frequency_hz'] * 1e3:.6g} | "
        f"{item['statistic']:.6g} | {item['familywise_p']:.6g} | "
        f"{'sí' if item['detected'] else 'no'} |"
        for item in report["holdout_confirmation"]
    )
    claims = "\n".join(
        f"- {item['claim_id']}: **{item['status']}** - {item['scope']}"
        for item in report["claim_ledger"]
    )
    return f"""# Cierre sustantivo — DarkPipe AION continuo 0.7

Decisión: **{report['decision']}**.

## Resultado observado

La banda continua se exploró únicamente en desarrollo; sus candidatos quedaron
fijados antes de evaluar el holdout. La tabla contiene p-valores familiares
obtenidos mediante rotaciones circulares del holdout sobre la familia congelada.

| Candidato | Frecuencia [mHz] | Estadístico | p FWER | Confirmado |
|---|---:|---:|---:|---|
{rows or '| - | - | - | - | no hubo máximos elegibles |'}

Estado del contraste geomagnético regional: **{report['environment']['status']}**.
Hartland es un control ambiental medido; OMNI se conserva como contexto
heliosférico y no actúa como veto causal.
Hartland es un observatorio regional, no un magnetómetro co-localizado con AION;
su no asociación no excluye perturbaciones estrictamente locales.

## Significado

NO_HOLDOUT_CANDIDATE significa que ningún pico seleccionado en desarrollo se
replicó bajo la regla congelada. LOCAL_GEOMAGNETIC_ASSOCIATION significa que
al menos un candidato confirmado comparte coherencia por bloques con Hartland.
UNEXPLAINED_SENSOR_CANDIDATE describe una anomalía instrumental que superó
este gate y no quedó asociada a Hartland; no identifica su naturaleza física.

## Autoridad de claims

{claims}

La campaña reutiliza una sola época AION y no contiene un modelo físico que
conecte el sistema morfotopológico de hiperestados plásmicos con observables de
borde gravitatorios. Por ello
una detección física y una tasa de falsa
alarma entre campañas independientes permanecen NOT_ESTIMABLE.
"""


def _write_confirmation_figure(report: dict[str, Any], path: Path) -> None:
    items = report["holdout_confirmation"]
    fig, ax = plt.subplots(figsize=(9.5, 4.8), constrained_layout=True)
    if items:
        values = [item["statistic"] for item in items]
        colors = ["#2a9d8f" if item["detected"] else "#9aa0a6" for item in items]
        ax.bar(range(len(items)), values, color=colors)
        ax.axhline(
            report["calibration"]["critical_max_statistic"],
            color="black",
            linestyle="--",
            label="FWER 5%",
        )
        ax.set_xticks(
            range(len(items)), [item["candidate_id"] for item in items], rotation=45
        )
        ax.legend()
    ax.set(
        xlabel="Frozen development candidate",
        ylabel="Holdout score statistic",
        title="AION continuous-search split-sample confirmation",
    )
    fig.savefig(path, dpi=180)
    plt.close(fig)


def confirm_continuous_candidates(
    evidence_root: str | Path, campaign_dir: str | Path, candidate_commit: str
) -> dict[str, Any]:
    """Confirm the frozen family on holdout and condition survivors on environment."""
    if len(candidate_commit) < 7:
        raise ValueError("candidate_commit must identify the candidate-freeze Git commit")
    evidence = Path(evidence_root)
    target = Path(campaign_dir)
    discovery_path = target / "discovery_candidates.json"
    discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
    if discovery.get("holdout_endpoints_accessed") is not False:
        raise ValueError("discovery boundary is not intact")
    gate = validate_aion_evidence(evidence)
    if not gate["passed"]:
        raise ValueError(f"AION integrity gate failed: {gate['failures']}")
    controls = _load_controls(evidence)
    models = _fit_development_models(controls)
    candidate_ids = tuple(item["candidate_id"] for item in discovery["candidates"])
    frequencies = {
        item["candidate_id"]: float(item["frequency_hz"])
        for item in discovery["candidates"]
    }
    if candidate_ids:
        design = _build_design(controls, models, "holdout", frequencies)
        calibration = _family_null_calibration(design, candidate_ids)
        null_maximum = calibration.pop("max_statistics")
        scan = _scan(design["base_y"], design)
    else:
        calibration = {
            "surrogates": NULL_SURROGATES,
            "seed": CALIBRATION_SEED,
            "family_alpha": FAMILY_ALPHA,
            "critical_max_statistic": None,
            "status": "NOT_APPLICABLE_NO_ELIGIBLE_DEVELOPMENT_CANDIDATE",
        }
        null_maximum = np.array([], dtype=float)
        scan = []
    confirmation = []
    for item in scan:
        p_value = _global_p(item["statistic"], null_maximum)
        confirmation.append(
            {
                "candidate_id": item["dataset_id"],
                "frequency_hz": item["frequency_hz"],
                "statistic": item["statistic"],
                "quadrature_rad": item["quadrature_rad"],
                "amplitude_rad": item["amplitude_rad"],
                "familywise_p": p_value,
                "detected": p_value <= FAMILY_ALPHA,
            }
        )
    detected = {
        item["candidate_id"]: item["frequency_hz"]
        for item in confirmation
        if item["detected"]
    }
    environment_records: list[dict[str, Any]] = []
    if detected:
        proxy = _phase_proxy(controls, models, "holdout")
        start = proxy["time"].min()
        stop = proxy["time"].max() + pd.Timedelta(seconds=1)
        try:
            had, omni, environment_records = _environment_frames(target, start, stop)
            environment = _environment_gate(proxy, had, omni, detected)
        except Exception as error:
            environment = {
                "status": "NOT_ESTIMABLE",
                "reason": f"{type(error).__name__}: {error}",
                "associations": [],
                "omni_context": [],
            }
    else:
        environment = {
            "status": "NOT_APPLICABLE",
            "reason": "no holdout candidate survived the frozen FWER gate",
            "associations": [],
            "omni_context": [],
        }

    if not detected:
        decision = "NO_HOLDOUT_CANDIDATE"
    elif environment["status"] == "SUPPORTED":
        decision = "LOCAL_GEOMAGNETIC_ASSOCIATION"
    elif environment["status"] == "CONTRADICTED":
        decision = "UNEXPLAINED_SENSOR_CANDIDATE"
    else:
        decision = "CANDIDATE_ENVIRONMENT_NOT_ESTIMABLE"

    claims = [
        {
            "claim_id": "split_sample_continuous_search_executed",
            "status": "SUPPORTED",
            "scope": "development scan and nonempty-family holdout confirmation on one AION epoch",
        },
        {
            "claim_id": "holdout_candidate_in_frozen_family",
            "status": "SUPPORTED" if detected else "CONTRADICTED",
            "scope": f"{len(detected)}/{len(confirmation)} candidates passed familywise alpha 0.05",
        },
        {
            "claim_id": "local_geomagnetic_association",
            "status": environment["status"],
            "scope": "regional Hartland one-second block coherence; association is not causation",
        },
        {
            "claim_id": "independent_epoch_replication",
            "status": "NOT_ESTIMABLE",
            "scope": "v0.7 reuses the single 2025-12-19/22 AION control epoch",
        },
        {
            "claim_id": "morphotopological_plasma_hyperstate_hypothesis",
            "status": "NOT_ESTIMABLE",
            "scope": "no specific physical coupling model or independent replication",
        },
        {
            "claim_id": "frequency_band_75_to_100_mhz",
            "status": "NOT_ESTIMABLE",
            "scope": "excluded above the lower development median-cadence nominal Nyquist",
        },
    ]
    report = {
        "schema_version": "1.0",
        "campaign_id": CAMPAIGN_ID,
        "generated_at_utc": utc_now(),
        "decision": decision,
        "preregistration_commit": discovery["preregistration_commit"],
        "candidate_commit": candidate_commit,
        "discovery_file_sha256": sha256_file(discovery_path),
        "candidate_family_size": len(candidate_ids),
        "calibration": calibration,
        "holdout_confirmation": confirmation,
        "environment": environment,
        "environment_source_files": environment_records,
        "claim_ceiling": "single-epoch split-sample sensor candidate with measured environmental classification",
        "claim_ledger": claims,
    }
    write_json(target / "report.json", report)
    (target / "report.md").write_text(_render_report(report), encoding="utf-8", newline="\n")
    _write_confirmation_figure(report, target / "holdout_confirmation.png")
    files = [
        file_record(path, target)
        for path in sorted(target.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    ]
    write_json(
        target / "manifest.json",
        {
            "schema_version": "1.0",
            "campaign_id": CAMPAIGN_ID,
            "generated_at_utc": utc_now(),
            "files": files,
        },
    )
    return report
