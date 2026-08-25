#!/usr/bin/env python3
"""Run the preregistered DarkPipe 0.9 GPS network campaign."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys

import numpy as np

from darkpipe.gps_network import (
    SearchConfig,
    Segment,
    clock_difference_matrix,
    covariance_weight,
    daily_segments,
    datetime_to_jpl_second,
    exact_rank_pvalue,
    fetch_gzip_text,
    fit_background,
    inject_plane_impulse,
    jpl_second_to_datetime,
    parse_clock_tdp,
    parse_position_goa,
    position_snapshot,
    product_url,
    search_segment,
    select_nodes,
    slice_matrix,
    sobol_velocity_bank,
    standardize_matrix,
    wilson_lower_bound,
)
from darkpipe.provenance import utc_now, write_json

BACKGROUND_DAYS = tuple(date(2024, 10, 31) + timedelta(days=i) for i in range(42))
BACKGROUND_STARTS = ("00:15", "08:00", "15:45")
TARGET_START = datetime(2024, 12, 13, 20, 10, 45, 136597, tzinfo=timezone.utc)
TARGET_SPLIT = datetime(2024, 12, 14, 0, 0, 0, tzinfo=timezone.utc)
TARGET_STOP = datetime(2024, 12, 14, 3, 37, 16, 434186, tzinfo=timezone.utc)
TARGET_DURATIONS = (
    (TARGET_SPLIT - TARGET_START).total_seconds(),
    (TARGET_STOP - TARGET_SPLIT).total_seconds(),
)


def load_day(day: date, config: SearchConfig):
    clock_text, clock_receipt = fetch_gzip_text(
        product_url(day, "hr.tdp"), max_bytes=config.download_limit_bytes
    )
    position_text, position_receipt = fetch_gzip_text(
        product_url(day, "pos"), max_bytes=config.download_limit_bytes
    )
    clock = parse_clock_tdp(clock_text)
    position = parse_position_goa(position_text)
    matrix = clock_difference_matrix(clock, cadence_seconds=config.cadence_seconds)
    del clock_text, position_text, clock
    return matrix, position, [clock_receipt.to_dict(), position_receipt.to_dict()]


def segment_payload(
    segment: Segment,
    matrix,
    position,
    nodes,
    location,
    scale,
):
    start = datetime_to_jpl_second(segment.start)
    stop = datetime_to_jpl_second(segment.stop)
    part = slice_matrix(matrix, start, stop)
    times, standardized = standardize_matrix(part, nodes, location, scale)
    center = 0.5 * (start + stop)
    positions = position_snapshot(position, nodes, center)
    return times, standardized, positions, start, stop


def random_velocity(rng: np.random.Generator, config: SearchConfig) -> np.ndarray:
    speed = float(
        np.exp(
            rng.uniform(
                np.log(config.velocity_min_km_s),
                np.log(config.velocity_max_km_s),
            )
        )
    )
    direction = rng.normal(size=3)
    direction /= np.linalg.norm(direction)
    return direction * speed


def write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def calibrate(output: Path, config: SearchConfig) -> int:
    output.mkdir(parents=True, exist_ok=True)
    day_cache = {}
    receipts = []
    entries = []
    raw_matrices = []

    for day_index, day in enumerate(BACKGROUND_DAYS):
        matrix, position, day_receipts = load_day(day, config)
        day_cache[day] = (matrix, position)
        receipts.extend(day_receipts)
        schedule_start = BACKGROUND_STARTS[day_index % len(BACKGROUND_STARTS)]
        segments = daily_segments(day, (schedule_start,), TARGET_DURATIONS)
        for part_index in range(2):
            segment = segments[part_index]
            start = datetime_to_jpl_second(segment.start)
            stop = datetime_to_jpl_second(segment.stop)
            part = slice_matrix(matrix, start, stop)
            raw_matrices.append(part)
            entries.append(
                {
                    "day": day,
                    "block_index": day_index,
                    "part_index": part_index,
                    "segment": segment,
                    "part": part,
                    "schedule_start_utc": schedule_start,
                }
            )

    nodes = select_nodes(
        raw_matrices,
        coverage_min=config.coverage_min,
        min_nodes=config.min_nodes,
    )
    location, scale, covariance = fit_background(raw_matrices, nodes)
    weight = covariance_weight(covariance)
    bank = sobol_velocity_bank(config)

    prepared = []
    part_hits = []
    for entry in entries:
        matrix, position = day_cache[entry["day"]]
        segment = entry["segment"]
        times, standardized, positions, start, stop = segment_payload(
            segment, matrix, position, nodes, location, scale
        )
        hit = search_segment(
            times,
            standardized,
            positions,
            bank,
            weight,
            start_second=start,
            stop_second=stop,
            guard_seconds=config.guard_seconds,
        )
        prepared.append(
            {
                **entry,
                "times": times,
                "standardized": standardized,
                "positions": positions,
                "start": start,
                "stop": stop,
                "baseline_hit": hit,
            }
        )
        part_hits.append(
            {
                "label": segment.label,
                "block_index": entry["block_index"],
                "part_index": entry["part_index"],
                **hit.to_dict(),
            }
        )

    null_maxima = []
    for block_index, day in enumerate(BACKGROUND_DAYS):
        matching = [
            item["baseline_hit"].statistic
            for item in prepared
            if item["day"] == day and item["block_index"] == block_index
        ]
        if len(matching) != 2:
            raise ValueError("background day did not retain both split parts")
        null_maxima.append(float(max(matching)))

    rng = np.random.default_rng(config.seed + 1)
    power = []
    for amplitude in config.injection_amplitudes:
        detected = 0
        localized = 0
        joint = 0
        for _ in range(config.injection_trials):
            entry = prepared[int(rng.integers(0, len(prepared)))]
            low = entry["start"] + config.guard_seconds
            high = entry["stop"] - config.guard_seconds
            center = float(rng.uniform(low, high))
            velocity = random_velocity(rng, config)
            injected = inject_plane_impulse(
                entry["standardized"],
                entry["times"],
                entry["positions"],
                velocity,
                center,
                float(amplitude),
            )
            hit = search_segment(
                entry["times"],
                injected,
                entry["positions"],
                bank,
                weight,
                start_second=entry["start"],
                stop_second=entry["stop"],
                guard_seconds=config.guard_seconds,
            )
            pvalue = exact_rank_pvalue(hit.statistic, null_maxima)
            is_detected = pvalue <= config.alpha
            is_localized = (
                abs(hit.center_second - center)
                <= config.localization_tolerance_seconds
            )
            detected += int(is_detected)
            localized += int(is_localized)
            joint += int(is_detected and is_localized)
        power.append(
            {
                "amplitude_robust_sigma": float(amplitude),
                "trials": config.injection_trials,
                "detected": detected,
                "temporally_localized": localized,
                "joint_successes": joint,
                "joint_rate": joint / config.injection_trials,
                "joint_wilson_95_lower": wilson_lower_bound(
                    joint, config.injection_trials
                ),
            }
        )

    highest = power[-1]
    power_gate = highest["joint_wilson_95_lower"] >= 0.80
    result = {
        "schema": "darkpipe.gps_network.calibration.v1",
        "campaign_id": config.campaign_id,
        "created_utc": utc_now(),
        "stage": "CALIBRATION_BACKGROUND_ONLY",
        "target_opened": False,
        "config": config.to_dict(),
        "background_days": [day.isoformat() for day in BACKGROUND_DAYS],
        "background_starts_utc": list(BACKGROUND_STARTS),
        "target_part_durations_seconds": list(TARGET_DURATIONS),
        "selected_nodes": nodes,
        "selected_node_count": len(nodes),
        "null_family": "42 daily maxima with one non-overlapping block per day; each maximum spans both split parts, all centers, signs, and velocity templates",
        "null_maxima": null_maxima,
        "part_hits": part_hits,
        "power": power,
        "power_gate": power_gate,
        "gate_threshold": "largest-amplitude joint Wilson 95% lower bound >= 0.80",
        "decision": (
            "CALIBRATION_GREEN_TARGET_MAY_OPEN"
            if power_gate
            else "ABSTAIN_INSUFFICIENT_POWER_TARGET_MUST_REMAIN_CLOSED"
        ),
        "receipts": receipts,
        "claim_ceiling": "Calibration certifies only sensitivity of the frozen GPS network operator to declared standardized impulses.",
        "not_estimable": [
            "dark matter",
            "plasma hyperstates",
            "gravity mechanism",
            "physical coupling",
            "clock-species-specific response",
        ],
    }
    write_json(output / "calibration_result.json", result)
    state_payload = {
        "schema": "darkpipe.gps_network.calibration_state.v1",
        "campaign_id": config.campaign_id,
        "config": config.to_dict(),
        "power_gate": power_gate,
        "nodes": nodes,
        "location": location.tolist(),
        "scale": scale.tolist(),
        "covariance": covariance.tolist(),
        "null_maxima": list(null_maxima),
    }
    write_json(output / "calibration_state.json", state_payload)
    np.savez_compressed(
        output / "calibration_state.npz",
        nodes=np.asarray(nodes),
        location=location,
        scale=scale,
        covariance=covariance,
        null_maxima=np.asarray(null_maxima),
        config_json=np.asarray(json.dumps(config.to_dict(), sort_keys=True)),
        power_gate=np.asarray(power_gate),
    )
    report = f"""# DarkPipe 0.9 - calibracion GPS

Decision: **{result['decision']}**.

La calibracion uso exclusivamente 42 bloques autenticos anteriores a la
ventana objetivo, con {len(nodes)} relojes GPS seleccionados por cobertura. El
maximo familiar de cada bloque incluye ambos tramos, todos los centros, ambos
signos y las {config.template_count} velocidades prospectivas.

En la amplitud de calibracion mas alta ({highest['amplitude_robust_sigma']}
sigmas robustas), la recuperacion conjunta deteccion-localizacion fue
{highest['joint_successes']}/{highest['trials']}; limite inferior Wilson 95%:
{highest['joint_wilson_95_lower']:.4f}. La ventana objetivo no fue abierta.

Esto no calibra materia oscura ni la conjetura plasmatica. Calibra solamente
la capacidad del operador congelado para recuperar el impulso estandarizado
declarado sobre fondo GPS autentico.
"""
    write_markdown(output / "CALIBRATION_CLOSURE_ES.md", report)
    return 0 if power_gate else 3


def load_state(path: Path, config: SearchConfig):
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("schema") != "darkpipe.gps_network.calibration_state.v1":
        raise ValueError("unsupported calibration-state schema")
    if state.get("campaign_id") != config.campaign_id:
        raise ValueError("calibration campaign differs from frozen target campaign")
    if state.get("config") != config.to_dict():
        raise ValueError("calibration config differs from frozen target config")
    if not bool(state.get("power_gate")):
        raise ValueError("power gate is not green; target must remain closed")
    nodes = [str(value) for value in state["nodes"]]
    location = np.asarray(state["location"], dtype=float)
    scale = np.asarray(state["scale"], dtype=float)
    covariance = np.asarray(state["covariance"], dtype=float)
    null_maxima = np.asarray(state["null_maxima"], dtype=float)
    count = len(nodes)
    if (
        location.shape != (count,)
        or scale.shape != (count,)
        or covariance.shape != (count, count)
        or null_maxima.shape != (42,)
    ):
        raise ValueError("calibration-state array shape mismatch")
    if not all(
        np.isfinite(value).all()
        for value in (location, scale, covariance, null_maxima)
    ):
        raise ValueError("non-finite calibration-state value")
    return nodes, location, scale, covariance, null_maxima


def target(output: Path, config: SearchConfig, state_path: Path) -> int:
    output.mkdir(parents=True, exist_ok=True)
    nodes, location, scale, covariance, null_maxima = load_state(state_path, config)
    weight = covariance_weight(covariance)
    bank = sobol_velocity_bank(config)
    segments = (
        Segment("target-a", TARGET_START, TARGET_SPLIT),
        Segment("target-b", TARGET_SPLIT, TARGET_STOP),
    )
    days = (date(2024, 12, 13), date(2024, 12, 14))
    receipts = []
    hits = []

    for day, segment in zip(days, segments, strict=True):
        matrix, position, day_receipts = load_day(day, config)
        receipts.extend(day_receipts)
        times, standardized, positions, start, stop = segment_payload(
            segment, matrix, position, nodes, location, scale
        )
        hit = search_segment(
            times,
            standardized,
            positions,
            bank,
            weight,
            start_second=start,
            stop_second=stop,
            guard_seconds=config.guard_seconds,
        )
        hits.append({"segment": segment.label, **hit.to_dict()})

    winning = max(hits, key=lambda item: item["statistic"])
    pvalue = exact_rank_pvalue(winning["statistic"], null_maxima)
    candidate = pvalue <= config.alpha
    decision = (
        "GPS_NETWORK_TRANSIENT_CANDIDATE"
        if candidate
        else "NO_GPS_NETWORK_TRANSIENT_CANDIDATE"
    )
    result = {
        "schema": "darkpipe.gps_network.target.v1",
        "campaign_id": config.campaign_id,
        "created_utc": utc_now(),
        "stage": "TARGET_OPENED_ONCE_AFTER_GREEN_POWER_GATE",
        "target_window_utc": [TARGET_START.isoformat(), TARGET_STOP.isoformat()],
        "split_reason": "JPL products and first differences are processed within their UTC product day; no cross-day difference.",
        "hits": hits,
        "winning_hit": {
            **winning,
            "center_utc": jpl_second_to_datetime(
                winning["center_second"]
            ).isoformat(),
        },
        "null_count": int(len(null_maxima)),
        "exact_familywise_rank_p": pvalue,
        "alpha": config.alpha,
        "decision": decision,
        "receipts": receipts,
        "claim_ceiling": "A GPS clock-network transient candidate/no-candidate within the frozen operator, velocity bank, and UTC window.",
        "not_estimable": [
            "dark matter",
            "plasma hyperstates",
            "gravity mechanism",
            "physical coupling or exclusion limits",
            "cross-instrument confirmation of AION",
        ],
    }
    write_json(output / "target_result.json", result)
    report = f"""# DarkPipe 0.9 - cierre objetivo GPS

Decision: **{decision}**.

El maximo observado del operador prospectivo fue {winning['statistic']:.6g};
su p exacto por rango, ya corregido sobre ambos tramos, centros, signos y
plantillas, fue {pvalue:.6f} con {len(null_maxima)} maximos de fondo autentico.

La decision solo pertenece a la red de relojes GPS y a la ventana congelada.
No valida ni refuta materia oscura, gravedad emergente, hiperestados plasmicos
ni un acoplamiento fisico; esos niveles siguen NOT_ESTIMABLE.
"""
    write_markdown(output / "TARGET_CLOSURE_ES.md", report)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("calibrate", "target"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--calibration-state", type=Path)
    args = parser.parse_args()
    config = SearchConfig()
    try:
        if args.stage == "calibrate":
            return calibrate(args.output, config)
        if args.calibration_state is None:
            raise ValueError("--calibration-state is required for target")
        return target(args.output, config, args.calibration_state)
    except Exception as exc:
        args.output.mkdir(parents=True, exist_ok=True)
        failure = {
            "schema": "darkpipe.gps_network.failure.v1",
            "campaign_id": config.campaign_id,
            "created_utc": utc_now(),
            "stage": args.stage,
            "decision": "ABSTAIN_INTEGRITY_OR_POWER",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "target_authority": (
                "CLOSED" if args.stage == "calibrate" else "OPEN_ATTEMPT_FAILED"
            ),
        }
        write_json(args.output / "failure_result.json", failure)
        print(json.dumps(failure, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
