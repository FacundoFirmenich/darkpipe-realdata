"""Preregisterable independent-epoch AION search on historical RID34056."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import h5py
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .aion_blind import (
    ARMS,
    CONDITIONS,
    GROUPS,
    _build_design,
    _circular_correlations,
    _fit_development_models,
    _group_signal_columns,
    _scan,
)
from .aion_continuous import score_frequency_family
from .provenance import file_record, utc_now, write_json

CAMPAIGN_ID = "DP-AION-INDEPENDENT-0.8-20260825"
DEVELOPMENT_FRACTION = 0.40
FREQUENCY_FLOOR_HZ = 1.0e-4
FREQUENCY_CEILING_HZ = 7.5e-2
NYQUIST_SAFETY_FACTOR = 0.90
MAX_CANDIDATES = 8
SEPARATION_RAYLEIGH_CELLS = 2
NULL_SURROGATES = 4095
FAMILY_ALPHA = 0.05
CONFIRMATION_SEED = 2026082508
POWER_SEED = 2026082518
POWER_FREQUENCIES_HZ = (
    1.0e-4,
    3.0e-4,
    1.0e-3,
    3.0e-3,
    1.0e-2,
    3.0e-2,
    1.0e-1,
)
POWER_AMPLITUDES_RAD = (0.3, 0.6, 1.2)
POWER_PHASES = 16
MIN_SUBSET_ROWS = 1000
EXPECTED_ROWS = 22839
PREFIX = "datasets/ndscan.rid_34056.points."
PATHS = {
    "phi_turns": PREFIX + "axis_0",
    "condition": PREFIX + "axis_1",
    "timestamp": PREFIX + "channel_timestamp_utc",
    "excitation_fraction_forward": (
        PREFIX + "channel_excitation_fraction_forward"
    ),
    "excitation_fraction_backward": (
        PREFIX + "channel_excitation_fraction_backward"
    ),
    "atom_number_forward": PREFIX + "channel_atom_number_forward",
    "atom_number_backward": PREFIX + "channel_atom_number_backward",
}
MONITORS = {
    "rigol_counter_frequency": (
        PREFIX + "channel_rigol_counter_frequency"
    ),
    "blue_IJD1_relocker_num_relocks": (
        PREFIX + "channel_blue_IJD1_relocker_num_relocks"
    ),
    "blue_IJD2_relocker_num_relocks": (
        PREFIX + "channel_blue_IJD2_relocker_num_relocks"
    ),
    "blue_IJD3_relocker_num_relocks": (
        PREFIX + "channel_blue_IJD3_relocker_num_relocks"
    ),
    "red_IJD1_relocker_num_relocks": (
        PREFIX + "channel_red_IJD1_relocker_num_relocks"
    ),
}
CONDITION_VALUES = {"lln": 0, "hln": 2}


def _take(dataset: h5py.Dataset, indices: np.ndarray) -> np.ndarray:
    indices = np.asarray(indices, dtype=np.int64)
    source_order = np.argsort(indices, kind="stable")
    inverse = np.argsort(source_order, kind="stable")
    return np.asarray(dataset[indices[source_order]])[inverse]


def _index_plan(handle: h5py.File) -> dict[str, Any]:
    phi = np.asarray(handle[PATHS["phi_turns"]])
    condition = np.asarray(handle[PATHS["condition"]])
    timestamp = np.asarray(handle[PATHS["timestamp"]])
    if not (len(phi) == len(condition) == len(timestamp) == EXPECTED_ROWS):
        raise ValueError("RID34056 structural row count mismatch")
    structural = (
        np.isfinite(phi)
        & np.isfinite(condition)
        & np.isfinite(timestamp)
        & (phi >= 0.0)
        & (phi <= 1.0)
        & np.isin(condition, list(CONDITION_VALUES.values()))
    )
    result: dict[str, Any] = {
        "total_rows": int(len(phi)),
        "structural_rows": int(np.count_nonzero(structural)),
        "conditions": {},
    }
    for name, value in CONDITION_VALUES.items():
        indices = np.flatnonzero(structural & (condition == value))
        order = np.argsort(timestamp[indices], kind="stable")
        indices = indices[order]
        split = int(math.floor(DEVELOPMENT_FRACTION * len(indices)))
        if split < MIN_SUBSET_ROWS or len(indices) - split < MIN_SUBSET_ROWS:
            raise ValueError(f"insufficient chronological rows for {name}")
        result["conditions"][name] = {
            "all": indices,
            "development": indices[:split],
            "holdout": indices[split:],
            "bounds": (
                float(timestamp[indices].min()),
                float(timestamp[indices].max()),
            ),
            "timestamp_reversals_source": int(
                np.count_nonzero(np.diff(timestamp[np.flatnonzero(
                    structural & (condition == value)
                )]) <= 0)
            ),
        }
    return result


def _exact_mode(values: np.ndarray) -> tuple[Any, float]:
    values = np.asarray(values)
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        raise ValueError("monitor has no finite development values")
    unique, counts = np.unique(finite, return_counts=True)
    index = int(np.flatnonzero(counts == counts.max())[0])
    share = float(counts[index] / len(finite))
    if share < 0.50:
        raise ValueError("monitor has no majority development mode")
    return unique[index].item(), share


def _monitor_references(
    handle: h5py.File, plan: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    references: dict[str, dict[str, Any]] = {}
    for condition in CONDITIONS:
        indices = plan["conditions"][condition]["development"]
        references[condition] = {}
        for name, path in MONITORS.items():
            value, share = _exact_mode(_take(handle[path], indices))
            references[condition][name] = {
                "value": value,
                "development_share": share,
            }
    return references


def _frame(
    handle: h5py.File,
    indices: np.ndarray,
    references: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    values = {
        name: _take(handle[path], indices)
        for name, path in PATHS.items()
        if name not in {"condition"}
    }
    monitor_values = {
        name: _take(handle[path], indices)
        for name, path in MONITORS.items()
    }
    quality = (
        np.isfinite(values["phi_turns"])
        & np.isfinite(values["timestamp"])
        & np.isfinite(values["excitation_fraction_forward"])
        & np.isfinite(values["excitation_fraction_backward"])
        & np.isfinite(values["atom_number_forward"])
        & np.isfinite(values["atom_number_backward"])
        & (values["phi_turns"] >= 0.0)
        & (values["phi_turns"] <= 1.0)
        & (values["excitation_fraction_forward"] >= 0.0)
        & (values["excitation_fraction_forward"] <= 1.0)
        & (values["excitation_fraction_backward"] >= 0.0)
        & (values["excitation_fraction_backward"] <= 1.0)
        & (values["atom_number_forward"] > 0.0)
        & (values["atom_number_backward"] > 0.0)
    )
    monitor_rejections: dict[str, int] = {}
    for name, vector in monitor_values.items():
        modal = references[name]["value"]
        accepted = np.isfinite(vector) & (vector == modal)
        monitor_rejections[name] = int(np.count_nonzero(~accepted))
        quality &= accepted
    duplicate = pd.Series(values["timestamp"]).duplicated(
        keep="first"
    ).to_numpy()
    quality &= ~duplicate
    frame = pd.DataFrame(
        {
            "timestamp": values["timestamp"][quality],
            "phi": 2.0 * math.pi * values["phi_turns"][quality],
            "excitation_fraction_forward": values[
                "excitation_fraction_forward"
            ][quality],
            "excitation_fraction_backward": values[
                "excitation_fraction_backward"
            ][quality],
        }
    ).sort_values("timestamp", kind="stable").reset_index(drop=True)
    if len(frame) < MIN_SUBSET_ROWS:
        raise ValueError("quality filtering left insufficient subset rows")
    return frame, {
        "input_rows": int(len(indices)),
        "accepted_rows": int(len(frame)),
        "rejected_rows": int(len(indices) - len(frame)),
        "duplicate_timestamp_rows": int(np.count_nonzero(duplicate)),
        "monitor_rejections": monitor_rejections,
    }


def load_controls(
    source: str | Path, *, include_holdout: bool
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    controls: dict[str, dict[str, Any]] = {}
    quality: dict[str, Any] = {}
    with h5py.File(source, "r") as handle:
        plan = _index_plan(handle)
        references = _monitor_references(handle, plan)
        for condition in CONDITIONS:
            info = plan["conditions"][condition]
            development, development_quality = _frame(
                handle, info["development"], references[condition]
            )
            controls[condition] = {
                "rows": int(len(info["all"])),
                "bounds": info["bounds"],
                "development": development,
            }
            quality[condition] = {
                "source_rows": int(len(info["all"])),
                "timestamp_reversals_source": info[
                    "timestamp_reversals_source"
                ],
                "monitor_references": references[condition],
                "development": development_quality,
            }
            if include_holdout:
                holdout, holdout_quality = _frame(
                    handle, info["holdout"], references[condition]
                )
                controls[condition]["holdout"] = holdout
                quality[condition]["holdout"] = holdout_quality
    return controls, {
        "structural": {
            "total_rows": plan["total_rows"],
            "structural_rows": plan["structural_rows"],
        },
        "conditions": quality,
        "holdout_excitation_values_accessed": include_holdout,
    }


def adaptive_grid(
    controls: dict[str, dict[str, Any]], subset: str
) -> tuple[np.ndarray, dict[str, Any]]:
    starts = [
        float(controls[c][subset]["timestamp"].min())
        for c in CONDITIONS
    ]
    stops = [
        float(controls[c][subset]["timestamp"].max())
        for c in CONDITIONS
    ]
    duration = max(stops) - min(starts)
    if duration <= 0:
        raise ValueError("non-positive search duration")
    cadence: dict[str, float] = {}
    nyquist: dict[str, float] = {}
    for condition in CONDITIONS:
        intervals = np.diff(
            controls[condition][subset]["timestamp"].to_numpy(float)
        )
        positive = intervals[np.isfinite(intervals) & (intervals > 0)]
        if len(positive) == 0:
            raise ValueError("no positive sampling intervals")
        cadence[condition] = float(np.median(positive))
        nyquist[condition] = 0.5 / cadence[condition]
    upper = min(
        FREQUENCY_CEILING_HZ,
        NYQUIST_SAFETY_FACTOR * min(nyquist.values()),
    )
    rayleigh = 1.0 / duration
    first = int(math.ceil(FREQUENCY_FLOOR_HZ / rayleigh))
    last = int(math.floor(upper / rayleigh))
    frequencies = np.arange(first, last + 1, dtype=float) * rayleigh
    if len(frequencies) < 3:
        raise ValueError("adaptive frequency grid is empty")
    return frequencies, {
        "start_unix": min(starts),
        "stop_unix": max(stops),
        "duration_seconds": duration,
        "rayleigh_hz": rayleigh,
        "frequency_min_hz": float(frequencies[0]),
        "frequency_max_hz": float(frequencies[-1]),
        "nominal_median_cadence_seconds": cadence,
        "nominal_median_nyquist_hz": nyquist,
        "nyquist_safety_factor": NYQUIST_SAFETY_FACTOR,
        "count": int(len(frequencies)),
    }


def select_candidates(
    frequencies: np.ndarray,
    statistics: np.ndarray,
    rayleigh_hz: float,
) -> list[dict[str, Any]]:
    finite = np.isfinite(statistics)
    local = np.zeros(len(statistics), dtype=bool)
    local[1:-1] = (
        finite[1:-1]
        & (statistics[1:-1] >= statistics[:-2])
        & (statistics[1:-1] > statistics[2:])
    )
    order = sorted(
        np.flatnonzero(local),
        key=lambda index: (
            -float(statistics[index]),
            float(frequencies[index]),
        ),
    )
    selected: list[int] = []
    separation = SEPARATION_RAYLEIGH_CELLS * rayleigh_hz
    tolerance = 16.0 * np.finfo(float).eps * max(
        float(np.max(np.abs(frequencies))), 1.0
    )
    for index in order:
        if all(
            abs(float(frequencies[index] - frequencies[other]))
            >= separation - tolerance
            for other in selected
        ):
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


def _family_null(
    design: dict[str, Any],
    candidate_ids: tuple[str, ...],
    *,
    seed: int,
) -> dict[str, Any]:
    if not candidate_ids:
        return {
            "surrogates": NULL_SURROGATES,
            "seed": seed,
            "critical_max_statistic": None,
            "max_statistics": np.empty(0),
        }
    rng = np.random.default_rng(seed)
    residual = design["residual"]
    shifts = {}
    for condition in CONDITIONS:
        sl = design["slices"][f"{condition}_forward"]
        shifts[condition] = rng.integers(
            1, sl.stop - sl.start, size=NULL_SURROGATES
        )
    statistics = np.empty(
        (NULL_SURROGATES, len(candidate_ids)), dtype=float
    )
    for column, candidate_id in enumerate(candidate_ids):
        item = design["signals"][candidate_id]
        score = np.zeros((NULL_SURROGATES, 2), dtype=float)
        for condition in CONDITIONS:
            correlation = None
            for arm in ARMS:
                sl = design["slices"][f"{condition}_{arm}"]
                current = _circular_correlations(
                    item["zr"][sl], residual[sl]
                )
                correlation = (
                    current
                    if correlation is None
                    else correlation + current
                )
            score += correlation[shifts[condition]]
        statistics[:, column] = np.einsum(
            "bi,ij,bj->b",
            score,
            item["gram_inverse"],
            score,
        )
    maximum = statistics.max(axis=1)
    allowed = int(
        math.floor(FAMILY_ALPHA * (NULL_SURROGATES + 1) - 1.0)
    )
    return {
        "surrogates": NULL_SURROGATES,
        "seed": seed,
        "method": (
            "paired-arm condition-wise nonzero circular rotations"
        ),
        "critical_max_statistic": float(
            np.sort(maximum)[::-1][allowed]
        ),
        "max_statistics": maximum,
    }


def _family_p(statistic: float, maximum: np.ndarray) -> float:
    return float(
        (1 + np.count_nonzero(maximum >= statistic))
        / (len(maximum) + 1)
    )


def development_power(
    controls: dict[str, dict[str, Any]],
    models: dict[str, Any],
    grid: dict[str, Any],
) -> dict[str, Any]:
    frequencies = {
        f"p{index:02d}": frequency
        for index, frequency in enumerate(POWER_FREQUENCIES_HZ)
        if grid["frequency_min_hz"]
        <= frequency
        <= grid["frequency_max_hz"]
    }
    design = _build_design(
        controls, models, "development", frequencies
    )
    ids = tuple(frequencies)
    null = _family_null(design, ids, seed=POWER_SEED)
    rows = []
    phase_grid = (
        2.0 * math.pi * np.arange(POWER_PHASES) / POWER_PHASES
    )
    columns = {
        candidate_id: _group_signal_columns(
            controls, models, "development", frequency
        )
        for candidate_id, frequency in frequencies.items()
    }
    for candidate_id, frequency in frequencies.items():
        for amplitude in POWER_AMPLITUDES_RAD:
            detections = 0
            identifications = 0
            for phase in phase_grid:
                quadrature = amplitude * np.array(
                    [math.cos(phase), math.sin(phase)]
                )
                injected = design["base_y"].copy()
                for key, sl in design["slices"].items():
                    injected[sl] += (
                        columns[candidate_id][key] @ quadrature
                    )
                scan = {
                    item["dataset_id"]: item["statistic"]
                    for item in _scan(injected, design)
                }
                winner = min(
                    scan,
                    key=lambda key: (-scan[key], frequencies[key]),
                )
                passed = (
                    scan[candidate_id]
                    >= null["critical_max_statistic"]
                )
                detections += int(passed)
                identifications += int(
                    passed and winner == candidate_id
                )
            rows.append(
                {
                    "frequency_hz": frequency,
                    "amplitude_rad": amplitude,
                    "phases": POWER_PHASES,
                    "familywise_detection_power": (
                        detections / POWER_PHASES
                    ),
                    "correct_identification_power": (
                        identifications / POWER_PHASES
                    ),
                }
            )
    return {
        "kind": "FIXED_FAMILY_TANGENT_INJECTION_POWER",
        "synthetic_component": (
            "declared first-order differential-phase perturbation only"
        ),
        "authentic_component": (
            "RID34056 development noise, timestamps and phase steps"
        ),
        "frequency_family_hz": list(frequencies.values()),
        "amplitudes_rad": list(POWER_AMPLITUDES_RAD),
        "phase_count": POWER_PHASES,
        "null_surrogates": NULL_SURROGATES,
        "critical_max_statistic": null[
            "critical_max_statistic"
        ],
        "rows": rows,
        "limit": (
            "not continuous-search power and not a physical coupling limit"
        ),
    }


def _discovery_figure(
    frequencies: np.ndarray,
    statistics: np.ndarray,
    candidates: list[dict[str, Any]],
    path: Path,
) -> None:
    fig, ax = plt.subplots(
        figsize=(10.5, 5.0), constrained_layout=True
    )
    ax.plot(
        frequencies * 1.0e3,
        statistics,
        color="#264653",
        linewidth=0.7,
    )
    ax.scatter(
        [item["frequency_hz"] * 1.0e3 for item in candidates],
        [item["development_statistic"] for item in candidates],
        color="#c44536",
        s=32,
        label="frozen candidates",
    )
    ax.set_xscale("log")
    ax.set(
        xlabel="Frequency [mHz]",
        ylabel="Profiled score statistic",
        title="RID34056 development-only independent-epoch scan",
    )
    if candidates:
        ax.legend()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def discover(
    source: str | Path,
    output: str | Path,
    source_receipt: dict[str, Any],
    preregistration_commit: str,
) -> dict[str, Any]:
    if len(preregistration_commit) < 7:
        raise ValueError("preregistration commit is required")
    target = Path(output)
    target.mkdir(parents=True, exist_ok=True)
    controls, quality = load_controls(
        source, include_holdout=False
    )
    models = _fit_development_models(controls)
    frequencies, grid = adaptive_grid(controls, "development")
    statistics = score_frequency_family(
        controls, models, "development", frequencies
    )
    candidates = select_candidates(
        frequencies, statistics, grid["rayleigh_hz"]
    )
    report = {
        "schema_version": "1.0",
        "campaign_id": CAMPAIGN_ID,
        "stage": "DEVELOPMENT_DISCOVERY_ONLY",
        "generated_at_utc": utc_now(),
        "preregistration_commit": preregistration_commit,
        "source": source_receipt,
        "source_license": (
            "NO_MACHINE_READABLE_REUSE_LICENSE_DECLARED"
        ),
        "independence": {
            "from_v07_acquisition_epoch": True,
            "same_AION_instrument_family": True,
            "rid": 34056,
            "run_date": "2024-12-13",
        },
        "quality": quality,
        "grid": grid,
        "selection_rule": {
            "maximum_candidates": MAX_CANDIDATES,
            "minimum_separation_rayleigh_cells": (
                SEPARATION_RAYLEIGH_CELLS
            ),
            "threshold_used": False,
            "tie_break": "higher statistic, then lower frequency",
        },
        "candidates": candidates,
        "power": development_power(controls, models, grid),
        "holdout_excitation_values_accessed": False,
        "claim_ceiling": (
            "independent-epoch detector and false-candidate validation"
        ),
    }
    write_json(target / "discovery.json", report)
    _discovery_figure(
        frequencies,
        statistics,
        candidates,
        target / "development_scan.png",
    )
    write_json(
        target / "manifest.json",
        {
            "campaign_id": CAMPAIGN_ID,
            "files": [
                file_record(path, target)
                for path in sorted(target.iterdir())
                if path.is_file() and path.name != "manifest.json"
            ],
        },
    )
    return report


def _confirmation_figure(
    rows: list[dict[str, Any]], path: Path
) -> None:
    fig, ax = plt.subplots(
        figsize=(9.5, 4.8), constrained_layout=True
    )
    if rows:
        x = np.arange(len(rows))
        ax.bar(
            x,
            [item["holdout_statistic"] for item in rows],
            color=[
                "#2a9d8f" if item["confirmed"] else "#7a8793"
                for item in rows
            ],
        )
        ax.set_xticks(
            x,
            [item["candidate_id"] for item in rows],
        )
    ax.set(
        xlabel="Frozen development candidate",
        ylabel="Holdout statistic",
        title="RID34056 independent-epoch holdout",
    )
    fig.savefig(path, dpi=180)
    plt.close(fig)


def confirm(
    source: str | Path,
    output: str | Path,
    source_receipt: dict[str, Any],
    discovery_path: str | Path,
    candidate_commit: str,
) -> dict[str, Any]:
    if len(candidate_commit) < 7:
        raise ValueError("candidate commit is required")
    discovery = json.loads(
        Path(discovery_path).read_text(encoding="utf-8")
    )
    if discovery.get("campaign_id") != CAMPAIGN_ID:
        raise ValueError("candidate campaign mismatch")
    candidates = discovery.get("candidates", [])
    if source_receipt.get("sha256") != discovery.get(
        "source", {}
    ).get("sha256"):
        raise ValueError("confirmation source SHA-256 mismatch")
    target = Path(output)
    target.mkdir(parents=True, exist_ok=True)
    controls, quality = load_controls(
        source, include_holdout=bool(candidates)
    )
    rows: list[dict[str, Any]] = []
    if candidates:
        models = _fit_development_models(controls)
        family = {
            item["candidate_id"]: float(item["frequency_hz"])
            for item in candidates
        }
        design = _build_design(
            controls, models, "holdout", family
        )
        observed = {
            item["dataset_id"]: item
            for item in _scan(design["base_y"], design)
        }
        null = _family_null(
            design, tuple(family), seed=CONFIRMATION_SEED
        )
        for candidate in candidates:
            item = observed[candidate["candidate_id"]]
            p_value = _family_p(
                item["statistic"], null["max_statistics"]
            )
            rows.append(
                {
                    **candidate,
                    "holdout_statistic": item["statistic"],
                    "holdout_amplitude_rad": item["amplitude_rad"],
                    "holdout_phase_rad": item["phase_rad"],
                    "familywise_p": p_value,
                    "confirmed": p_value <= FAMILY_ALPHA,
                }
            )
        critical = null["critical_max_statistic"]
    else:
        critical = None
    confirmed = [item for item in rows if item["confirmed"]]
    decision = (
        "INDEPENDENT_EPOCH_SENSOR_CANDIDATE"
        if confirmed
        else "NO_INDEPENDENT_HOLDOUT_CANDIDATE"
    )
    report = {
        "schema_version": "1.0",
        "campaign_id": CAMPAIGN_ID,
        "stage": "FROZEN_FAMILY_HOLDOUT_CONFIRMATION",
        "generated_at_utc": utc_now(),
        "preregistration_commit": discovery[
            "preregistration_commit"
        ],
        "candidate_commit": candidate_commit,
        "source": source_receipt,
        "quality": quality,
        "family_alpha": FAMILY_ALPHA,
        "null_surrogates": NULL_SURROGATES,
        "critical_max_statistic": critical,
        "holdout_confirmation": rows,
        "confirmed_count": len(confirmed),
        "decision": decision,
        "cross_epoch_update": {
            "v07_decision": "NO_HOLDOUT_CANDIDATE",
            "v08_decision": decision,
            "independent_epochs_observed": 2,
            "false_positive_rate": "NOT_ESTIMABLE",
        },
        "not_estimable": [
            "morphotopological plasma-hyperstate conjecture",
            "dark-matter or gravitational-wave detection",
            "physical coupling or exclusion limit",
            "independent-instrument transfer",
            "false-positive rate from only two epochs",
            "continuous-search physical power",
        ],
        "claim_ceiling": (
            "independent-epoch split-sample sensor candidate only"
        ),
    }
    write_json(target / "report.json", report)
    _confirmation_figure(
        rows, target / "holdout_confirmation.png"
    )
    write_json(
        target / "manifest.json",
        {
            "campaign_id": CAMPAIGN_ID,
            "files": [
                file_record(path, target)
                for path in sorted(target.iterdir())
                if path.is_file() and path.name != "manifest.json"
            ],
        },
    )
    return report

