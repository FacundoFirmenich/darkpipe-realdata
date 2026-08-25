"""Seed-committed AION holdout replay on authentic control noise.

DarkPipe original code: GPL-3.0-or-later. Upstream AION evidence keeps its
CC-BY-4.0/MIT licensing boundary under the evidence directory.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .aion import INJECTIONS, validate_aion_evidence
from .provenance import file_record, sha256_file, utc_now, write_json

CAMPAIGN_ID = "DP-AION-BLIND-0.6-20260825"
DEVELOPMENT_FRACTION = 0.40
INJECTION_AMPLITUDE_RAD = 0.60
NULL_SURROGATES = 4095
FAMILY_ALPHA = 0.05
CALIBRATION_SEED = 2026082506
CONDITIONS = ("lln", "hln")
ARMS = ("forward", "backward")
GROUPS = tuple((condition, arm) for condition in CONDITIONS for arm in ARMS)
NUISANCE_COLUMNS = 6


def seed_commitment(seed_hex: str) -> str:
    """Return the SHA-256 commitment to a 256-bit hexadecimal seed."""
    try:
        raw = bytes.fromhex(seed_hex)
    except ValueError as error:
        raise ValueError("seed must be hexadecimal") from error
    if len(raw) != 32:
        raise ValueError("seed must encode exactly 32 bytes")
    return hashlib.sha256(raw).hexdigest()


def _digest(seed: bytes, domain: str) -> bytes:
    return hashlib.sha256(seed + b"\x00" + domain.encode("utf-8")).digest()


def _challenge_plan(seed_hex: str, frequencies: dict[str, float]) -> list[dict[str, Any]]:
    seed = bytes.fromhex(seed_hex)
    labels = ["null", *INJECTIONS]
    labels.sort(key=lambda label: _digest(seed, f"order:{label}"))
    plan = []
    for index, label in enumerate(labels):
        case_id = _digest(seed, f"case:{index}").hex()[:16]
        phase_int = int.from_bytes(_digest(seed, f"phase:{label}")[:8], "big")
        phase = 2.0 * math.pi * phase_int / 2**64
        plan.append({"case_id": case_id, "label": label, "target_frequency_hz": None if label == "null" else frequencies[label], "phase_rad": None if label == "null" else phase})
    return plan


def _load_controls(evidence_root: Path) -> dict[str, dict[str, Any]]:
    controls: dict[str, dict[str, Any]] = {}
    for condition in CONDITIONS:
        path = evidence_root / "upstream" / f"control_{condition}.csv"
        frame = pd.read_csv(path, comment="#", low_memory=False)
        reversals = int((frame["timestamp"].diff().dropna() <= 0).sum())
        frame = frame.sort_values("timestamp", kind="stable").reset_index(drop=True)
        split = int(math.floor(DEVELOPMENT_FRACTION * len(frame)))
        if split < 1000 or len(frame) - split < 1000:
            raise ValueError(f"insufficient rows after split for {condition}")
        bounds = (float(frame["timestamp"].min()), float(frame["timestamp"].max()))
        controls[condition] = {"path": path, "sha256": sha256_file(path), "rows": int(len(frame)), "timestamp_reversals_raw": reversals, "bounds": bounds, "development": frame.iloc[:split].copy(), "holdout": frame.iloc[split:].copy()}
    return controls


def _time_coordinate(frame: pd.DataFrame, bounds: tuple[float, float]) -> np.ndarray:
    lo, hi = bounds
    return 2.0 * (frame["timestamp"].to_numpy(float) - lo) / (hi - lo) - 1.0


def _nuisance_basis(frame: pd.DataFrame, bounds: tuple[float, float]) -> np.ndarray:
    phi = frame["phi"].to_numpy(float)
    u = _time_coordinate(frame, bounds)
    return np.column_stack([np.ones(len(frame)), u, np.cos(phi), np.sin(phi), u * np.cos(phi), u * np.sin(phi)])


def _robust_scale(residual: np.ndarray) -> float:
    centered = residual - np.median(residual)
    scale = 1.4826 * float(np.median(np.abs(centered)))
    if not np.isfinite(scale) or scale <= 0:
        scale = float(np.std(residual, ddof=1))
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("non-positive residual scale")
    return scale


def _fit_development_models(controls: dict[str, dict[str, Any]]) -> dict[str, Any]:
    models: dict[str, Any] = {}
    for condition, arm in GROUPS:
        info = controls[condition]
        frame = info["development"]
        x = _nuisance_basis(frame, info["bounds"])
        y = frame[f"excitation_fraction_{arm}"].to_numpy(float)
        beta, *_ = np.linalg.lstsq(x, y, rcond=None)
        residual = y - x @ beta
        models[f"{condition}_{arm}"] = {"beta": beta, "scale": _robust_scale(residual), "development_rms": float(np.sqrt(np.mean(residual**2)))}
    return models


def _fringe_derivative(frame: pd.DataFrame, bounds: tuple[float, float], beta: np.ndarray) -> np.ndarray:
    phi = frame["phi"].to_numpy(float)
    u = _time_coordinate(frame, bounds)
    return -beta[2] * np.sin(phi) + beta[3] * np.cos(phi) - beta[4] * u * np.sin(phi) + beta[5] * u * np.cos(phi)


def _target_frequencies(evidence_root: Path) -> dict[str, float]:
    frequencies = {}
    for dataset_id in INJECTIONS:
        with np.load(evidence_root / "upstream" / f"truth_{dataset_id}.npz", allow_pickle=False) as truth:
            frequencies[dataset_id] = float(truth["frequency"])
    return frequencies


def _group_signal_columns(controls: dict[str, dict[str, Any]], models: dict[str, Any], subset: str, frequency_hz: float) -> dict[str, np.ndarray]:
    result = {}
    for condition, arm in GROUPS:
        info = controls[condition]
        frame = info[subset]
        derivative = _fringe_derivative(frame, info["bounds"], models[f"{condition}_{arm}"]["beta"])
        sign = 0.5 if arm == "forward" else -0.5
        time = frame["timestamp"].to_numpy(float)
        phase = 2.0 * math.pi * frequency_hz * (time - time.min())
        result[f"{condition}_{arm}"] = sign * derivative[:, None] * np.column_stack([np.cos(phase), np.sin(phase)])
    return result


def _build_design(controls: dict[str, dict[str, Any]], models: dict[str, Any], subset: str, frequencies: dict[str, float]) -> dict[str, Any]:
    lengths = [len(controls[condition][subset]) for condition, _ in GROUPS]
    offsets = np.cumsum([0, *lengths])
    rows = int(offsets[-1])
    x0 = np.zeros((rows, NUISANCE_COLUMNS * len(GROUPS)), dtype=float)
    y = np.empty(rows, dtype=float)
    scales = np.empty(rows, dtype=float)
    slices: dict[str, slice] = {}
    for group_index, (condition, arm) in enumerate(GROUPS):
        frame = controls[condition][subset]
        sl = slice(int(offsets[group_index]), int(offsets[group_index + 1]))
        key = f"{condition}_{arm}"
        slices[key] = sl
        x0[sl, group_index * NUISANCE_COLUMNS:(group_index + 1) * NUISANCE_COLUMNS] = _nuisance_basis(frame, controls[condition]["bounds"])
        y[sl] = frame[f"excitation_fraction_{arm}"].to_numpy(float)
        scales[sl] = models[key]["scale"]
    xw = x0 / scales[:, None]
    yw = y / scales
    beta0, *_ = np.linalg.lstsq(xw, yw, rcond=None)
    residual = yw - xw @ beta0
    z_items = {}
    for dataset_id, frequency in frequencies.items():
        by_group = _group_signal_columns(controls, models, subset, frequency)
        z = np.empty((rows, 2), dtype=float)
        for key, sl in slices.items():
            z[sl] = by_group[key]
        zw = z / scales[:, None]
        nuisance_projection, *_ = np.linalg.lstsq(xw, zw, rcond=None)
        zr = zw - xw @ nuisance_projection
        gram = zr.T @ zr
        if np.linalg.cond(gram) > 1e12:
            raise ValueError(f"ill-conditioned signal design for {dataset_id}")
        z_items[dataset_id] = {"frequency_hz": frequency, "zr": zr, "gram_inverse": np.linalg.inv(gram)}
    return {"xw": xw, "scales": scales, "base_y": y, "residual": residual, "slices": slices, "signals": z_items}


def _scan(y: np.ndarray, design: dict[str, Any]) -> list[dict[str, Any]]:
    yw = y / design["scales"]
    xw = design["xw"]
    beta0, *_ = np.linalg.lstsq(xw, yw, rcond=None)
    residual = yw - xw @ beta0
    results = []
    for dataset_id, item in design["signals"].items():
        score = item["zr"].T @ residual
        quadrature = item["gram_inverse"] @ score
        statistic = float(score @ quadrature)
        results.append({"dataset_id": dataset_id, "frequency_hz": item["frequency_hz"], "statistic": statistic, "quadrature_rad": quadrature.tolist(), "amplitude_rad": float(np.linalg.norm(quadrature)), "phase_rad": float(math.atan2(quadrature[1], quadrature[0]))})
    return results


def _circular_correlations(z: np.ndarray, residual: np.ndarray) -> np.ndarray:
    return np.fft.ifft(np.conj(np.fft.fft(z, axis=0)) * np.fft.fft(residual)[:, None], axis=0).real


def _null_calibration(design: dict[str, Any]) -> dict[str, Any]:
    rng = np.random.default_rng(CALIBRATION_SEED)
    residual = design["residual"]
    condition_shifts = {}
    for condition in CONDITIONS:
        sl = design["slices"][f"{condition}_forward"]
        condition_shifts[condition] = rng.integers(1, sl.stop - sl.start, size=NULL_SURROGATES)
    statistics = np.empty((NULL_SURROGATES, len(INJECTIONS)), dtype=float)
    for frequency_index, dataset_id in enumerate(INJECTIONS):
        item = design["signals"][dataset_id]
        total_score = np.zeros((NULL_SURROGATES, 2), dtype=float)
        for condition in CONDITIONS:
            corr = None
            for arm in ARMS:
                sl = design["slices"][f"{condition}_{arm}"]
                arm_corr = _circular_correlations(item["zr"][sl], residual[sl])
                corr = arm_corr if corr is None else corr + arm_corr
            total_score += corr[condition_shifts[condition]]
        statistics[:, frequency_index] = np.einsum("bi,ij,bj->b", total_score, item["gram_inverse"], total_score)
    max_statistics = statistics.max(axis=1)
    allowed = int(math.floor(FAMILY_ALPHA * (NULL_SURROGATES + 1) - 1.0))
    return {"surrogates": NULL_SURROGATES, "alpha": FAMILY_ALPHA, "seed": CALIBRATION_SEED, "method": "paired-arm condition-wise circular rotations of development residuals", "critical_max_statistic": float(np.sort(max_statistics)[::-1][allowed]), "max_statistics": max_statistics}


def _global_p(statistic: float, null_max: np.ndarray) -> float:
    return float((1 + np.count_nonzero(null_max >= statistic)) / (len(null_max) + 1))


def prepare_blind_challenge(evidence_root: str | Path, campaign_dir: str | Path, seed_hex: str, preregistration_commit: str) -> dict[str, Any]:
    """Seal eight unlabeled holdout cases after the preregistration commit exists."""
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
    frequencies = _target_frequencies(evidence)
    plan = _challenge_plan(seed_hex, frequencies)
    case_ids = np.array([item["case_id"] for item in plan])
    arrays: dict[str, Any] = {"case_ids": case_ids}
    signal_columns = {dataset_id: _group_signal_columns(controls, models, "holdout", frequency) for dataset_id, frequency in frequencies.items()}
    for condition, arm in GROUPS:
        key = f"{condition}_{arm}"
        base = controls[condition]["holdout"][f"excitation_fraction_{arm}"].to_numpy(float)
        cases = []
        for item in plan:
            values = base.copy()
            if item["label"] != "null":
                phase = item["phase_rad"]
                quadrature = INJECTION_AMPLITUDE_RAD * np.array([math.cos(phase), math.sin(phase)])
                values += signal_columns[item["label"]][key] @ quadrature
            cases.append(values)
        arrays[key] = np.stack(cases)
    challenge_path = target / "sealed_challenge.npz"
    np.savez_compressed(challenge_path, **arrays)
    manifest = {
        "schema_version": "1.0", "campaign_id": CAMPAIGN_ID, "created_at_utc": utc_now(),
        "preregistration_commit": preregistration_commit, "seed_commitment_sha256": seed_commitment(seed_hex),
        "mapping_disclosed": False, "case_count": len(plan), "case_ids": case_ids.tolist(),
        "challenge_file": file_record(challenge_path, target),
        "source": {condition: {"path": str(controls[condition]["path"].relative_to(evidence)).replace("\\", "/"), "sha256": controls[condition]["sha256"], "rows": controls[condition]["rows"], "development_rows": len(controls[condition]["development"]), "holdout_rows": len(controls[condition]["holdout"]), "raw_timestamp_reversals": controls[condition]["timestamp_reversals_raw"]} for condition in CONDITIONS},
        "injection_model": {"kind": "first-order tangent differential-phase perturbation", "amplitude_rad": INJECTION_AMPLITUDE_RAD, "forward_sign": 0.5, "backward_sign": -0.5, "frequency_family": list(INJECTIONS)},
    }
    write_json(target / "sealed_manifest.json", manifest)
    return manifest


def analyze_blind_challenge(evidence_root: str | Path, campaign_dir: str | Path) -> dict[str, Any]:
    """Emit fixed-grid predictions without access to the seed or target mapping."""
    evidence = Path(evidence_root)
    target = Path(campaign_dir)
    manifest = json.loads((target / "sealed_manifest.json").read_text(encoding="utf-8"))
    challenge_path = target / manifest["challenge_file"]["path"]
    if sha256_file(challenge_path) != manifest["challenge_file"]["sha256"]:
        raise ValueError("sealed challenge hash mismatch")
    controls = _load_controls(evidence)
    models = _fit_development_models(controls)
    frequencies = _target_frequencies(evidence)
    calibration = _null_calibration(_build_design(controls, models, "development", frequencies))
    holdout_design = _build_design(controls, models, "holdout", frequencies)
    null_max = calibration.pop("max_statistics")
    with np.load(challenge_path, allow_pickle=False) as challenge:
        case_ids = challenge["case_ids"].astype(str).tolist()
        if case_ids != manifest["case_ids"]:
            raise ValueError("sealed case-id order mismatch")
        cases = []
        for case_index, case_id in enumerate(case_ids):
            y = np.concatenate([challenge[f"{condition}_{arm}"][case_index] for condition, arm in GROUPS])
            scan = _scan(y, holdout_design)
            for item in scan:
                item["familywise_p"] = _global_p(item["statistic"], null_max)
                item["detected"] = item["familywise_p"] <= FAMILY_ALPHA
            peak = max(scan, key=lambda item: (item["statistic"], -INJECTIONS.index(item["dataset_id"])))
            cases.append({"case_id": case_id, "peak_dataset_id": peak["dataset_id"], "peak_frequency_hz": peak["frequency_hz"], "max_statistic": peak["statistic"], "global_p": _global_p(peak["statistic"], null_max), "detected_dataset_ids": [item["dataset_id"] for item in scan if item["detected"]], "scan": scan})
    payload = {"schema_version": "1.0", "campaign_id": CAMPAIGN_ID, "generated_at_utc": utc_now(), "preregistration_commit": manifest["preregistration_commit"], "seed_commitment_sha256": manifest["seed_commitment_sha256"], "mapping_accessed": False, "calibration": calibration, "cases": cases}
    write_json(target / "blind_predictions.json", payload)
    return payload


def _render_report(report: dict[str, Any]) -> str:
    rows = []
    for item in report["cases"]:
        truth = "NULL" if item["label"] == "null" else item["label"]
        detected = ",".join(item["prediction"]["detected_dataset_ids"]) or "none"
        rows.append(f"| {item['case_id']} | {truth} | {item['prediction']['peak_dataset_id']} | {item['prediction']['global_p']:.6g} | {detected} | {'PASS' if item['passed'] else 'FAIL'} |")
    claims = "\n".join(f"- {item['claim_id']}: **{item['status']}** — {item['scope']}" for item in report["claim_ledger"])
    return f"""# DarkPipe 0.6 — replay holdout AION sellado

Decisión: **{report['decision']}**.

El mapa de ocho casos se comprometió mediante SHA-256 después del commit de prerregistro y se reveló sólo después de escribir las predicciones. El fondo de ruido procede de los controles LLN/HLN AION auténticos; únicamente la perturbación de fase diferencial es sintética y está declarada.

| Caso | Verdad revelada | Pico predicho | p global | Frecuencias detectadas | Gate |
|---|---|---|---:|---|---|
{chr(10).join(rows)}

- Gate nulo holdout: **{'PASS' if report['gates']['null_holdout']['passed'] else 'FAIL'}**.
- Gate de identificación: **{'PASS' if report['gates']['signal_identification']['passed'] else 'FAIL'}** ({report['gates']['signal_identification']['passed_count']}/7).
- Calibración: {report['calibration']['surrogates']} rotaciones circulares de residuo de desarrollo, alfa familiar {report['calibration']['alpha']}.

## Autoridad de claims

{claims}

El resultado no es una detección física, no estima una búsqueda continua ni una tasa frecuentista de falsa alarma sobre repeticiones instrumentales independientes.
"""


def _write_figure(report: dict[str, Any], path: Path) -> None:
    cases = report["cases"]
    values = [item["prediction"]["max_statistic"] for item in cases]
    colors = ["#6c757d" if item["label"] == "null" else ("#2a9d8f" if item["passed"] else "#9b2226") for item in cases]
    fig, ax = plt.subplots(figsize=(10, 4.8), constrained_layout=True)
    ax.bar(range(len(cases)), values, color=colors)
    ax.axhline(report["calibration"]["critical_max_statistic"], color="black", linestyle="--", label="FWER 5% critical")
    ax.set_xticks(range(len(cases)), ["NULL" if item["label"] == "null" else item["label"] for item in cases], rotation=45, ha="right")
    ax.set(ylabel="Maximum score statistic", xlabel="Revealed challenge", title="AION fixed-family blind holdout replay")
    ax.legend()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def reveal_blind_challenge(campaign_dir: str | Path, seed_hex: str) -> dict[str, Any]:
    """Verify the seed, reveal targets and adjudicate the frozen terminal rule."""
    target = Path(campaign_dir)
    manifest = json.loads((target / "sealed_manifest.json").read_text(encoding="utf-8"))
    predictions = json.loads((target / "blind_predictions.json").read_text(encoding="utf-8"))
    if seed_commitment(seed_hex) != manifest["seed_commitment_sha256"]:
        raise ValueError("seed does not satisfy the sealed commitment")
    frequencies = {item["dataset_id"]: item["frequency_hz"] for item in predictions["cases"][0]["scan"]}
    plan = _challenge_plan(seed_hex, frequencies)
    if [item["case_id"] for item in plan] != manifest["case_ids"]:
        raise ValueError("revealed plan does not match sealed case IDs")
    prediction_by_id = {item["case_id"]: item for item in predictions["cases"]}
    revealed_cases = []
    null_pass = False
    signal_passes = 0
    for truth in plan:
        prediction = prediction_by_id[truth["case_id"]]
        if truth["label"] == "null":
            passed = len(prediction["detected_dataset_ids"]) == 0
            null_pass = passed
        else:
            passed = prediction["peak_dataset_id"] == truth["label"] and prediction["detected_dataset_ids"] == [truth["label"]] and prediction["global_p"] <= FAMILY_ALPHA
            signal_passes += int(passed)
        revealed_cases.append({**truth, "prediction": prediction, "passed": bool(passed)})
    signals_pass = signal_passes == len(INJECTIONS)
    decision = "PASS_BOUNDED" if null_pass and signals_pass else "FAIL_BOUNDED"
    claims = [
        {"claim_id": "fixed_grid_single_holdout_false_alarm", "status": "SUPPORTED" if null_pass else "CONTRADICTED", "scope": "one seed-committed null replay over seven fixed AION frequencies"},
        {"claim_id": "fixed_grid_signal_identification_0p6rad", "status": "SUPPORTED" if signals_pass else "CONTRADICTED", "scope": f"{signal_passes}/7 tangent-space injections identified in this holdout"},
        {"claim_id": "independent_repeated_false_positive_rate", "status": "NOT_ESTIMABLE", "scope": "one reused holdout background is not an independent repeated campaign"},
        {"claim_id": "continuous_band_blind_search", "status": "NOT_ESTIMABLE", "scope": "only seven preregistered target frequencies were tested"},
        {"claim_id": "dark_matter_or_gravitational_wave_detection", "status": "NOT_ESTIMABLE", "scope": "signals are declared software injections, not unknown physical events"},
        {"claim_id": "nonlinear_raw_likelihood_equivalence", "status": "NOT_ESTIMABLE", "scope": "the injected perturbation is the first-order fringe tangent model"},
    ]
    report = {
        "schema_version": "1.0", "campaign_id": CAMPAIGN_ID, "generated_at_utc": utc_now(), "decision": decision,
        "preregistration_commit": manifest["preregistration_commit"], "seed_commitment_sha256": manifest["seed_commitment_sha256"],
        "calibration": predictions["calibration"],
        "gates": {"integrity": {"passed": True}, "null_holdout": {"passed": null_pass, "total": 1}, "signal_identification": {"passed": signals_pass, "passed_count": signal_passes, "total": len(INJECTIONS)}},
        "cases": revealed_cases, "claim_ceiling": "fixed seven-frequency software detector validation on one authentic AION control holdout", "claim_ledger": claims,
    }
    write_json(target / "seed_reveal.json", {"seed_hex": seed_hex, "commitment_sha256": manifest["seed_commitment_sha256"], "revealed_at_utc": utc_now()})
    write_json(target / "report.json", report)
    (target / "report.md").write_text(_render_report(report), encoding="utf-8", newline="\n")
    _write_figure(report, target / "blind_validation.png")
    files = [file_record(path, target) for path in sorted(target.iterdir()) if path.is_file() and path.name != "manifest.json"]
    write_json(target / "manifest.json", {"schema_version": "1.0", "campaign_id": CAMPAIGN_ID, "generated_at_utc": utc_now(), "files": files})
    return report
