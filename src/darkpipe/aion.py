"""Preregistered AION differential atom-interferometer validation.

DarkPipe original code: GPL-3.0-or-later. Upstream AION evidence keeps its
own CC-BY-4.0/MIT licensing boundary under the evidence directory.
"""
from __future__ import annotations

import json
import math
from pathlib import Path, PurePosixPath
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .authority import aion_authority_payload
from .provenance import file_record, sha256_file, utc_now, write_json

CAMPAIGN_ID = "DP-AION-0.4-20260825"
PREREGISTRATION_COMMIT = "f2da008"
EVIDENCE_DIRECTORY = "aion_sensor_validation_2026-08-25"
INJECTIONS = (
    "0p1_mhz",
    "0p3_mhz",
    "1_mhz",
    "3_mhz",
    "10_mhz",
    "30_mhz",
    "100_mhz",
)
REQUIRED_EXCITATION_COLUMNS = {
    "timestamp",
    "excitation_fraction_forward",
    "excitation_fraction_backward",
    "fluorescence_counts_forward",
    "fluorescence_counts_backward",
}
REQUIRED_MLE_COLUMNS = {
    "dataset_frequency_hz",
    "dataset_filename",
    "f_hz",
    "fit_A_rad",
    "fit_delta0_rad",
    "fit_phi_rad",
    "fit_logL",
    "iteration",
}


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, comment="#", low_memory=False)


def _manifest(root: Path) -> dict[str, Any]:
    return json.loads((root / "source_manifest.json").read_text(encoding="utf-8"))


def _entry_for_stored(manifest: dict[str, Any], suffix: str) -> dict[str, Any]:
    matches = [entry for entry in manifest["entries"] if entry["stored_path"].endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"Expected one manifest entry ending in {suffix!r}; found {len(matches)}")
    return matches[0]


def _finite_excitation(frame: pd.DataFrame) -> pd.DataFrame:
    columns = sorted(REQUIRED_EXCITATION_COLUMNS)
    return frame.loc[np.isfinite(frame[columns]).all(axis=1), columns]


def validate_aion_evidence(evidence_root: str | Path) -> dict[str, Any]:
    """Validate frozen bytes, schemas, mappings and preregistered Gate 0."""
    root = Path(evidence_root)
    failures: list[str] = []
    diagnostics: dict[str, Any] = {"files": [], "injections": []}
    try:
        manifest = _manifest(root)
    except Exception as error:
        return {
            "passed": False,
            "failure_count": 1,
            "failures": [f"source_manifest unreadable: {type(error).__name__}: {error}"],
            "diagnostics": diagnostics,
        }

    entries = manifest.get("entries", [])
    if len(entries) != 27:
        failures.append(f"expected 27 selected entries; found {len(entries)}")
    for entry in entries:
        path = root / entry["stored_path"]
        item = {"path": entry["stored_path"], "expected_sha256": entry["sha256"]}
        if not path.is_file():
            item["status"] = "missing"
            failures.append(f"missing selected file: {entry['stored_path']}")
        else:
            item.update(byte_count=path.stat().st_size, sha256=sha256_file(path))
            if item["byte_count"] != entry["byte_count"]:
                item["status"] = "byte_count_mismatch"
                failures.append(f"byte-count mismatch: {entry['stored_path']}")
            elif item["sha256"] != entry["sha256"]:
                item["status"] = "sha256_mismatch"
                failures.append(f"SHA-256 mismatch: {entry['stored_path']}")
            else:
                item["status"] = "ok"
        diagnostics["files"].append(item)

    if failures:
        return {
            "passed": False,
            "failure_count": len(failures),
            "failures": failures,
            "diagnostics": diagnostics,
        }

    try:
        mle = pd.read_csv(root / "upstream" / "mle_scan.csv", low_memory=False)
        missing_mle = REQUIRED_MLE_COLUMNS.difference(mle.columns)
        if missing_mle:
            failures.append(f"MLE columns absent: {sorted(missing_mle)}")
        if not np.isfinite(mle[["f_hz", "fit_logL", "iteration"]]).all().all():
            failures.append("MLE grid contains non-finite required values")

        mle_names = set(mle["dataset_filename"].astype(str))
        for dataset_id in INJECTIONS:
            raw_entry = _entry_for_stored(manifest, f"injection_{dataset_id}.csv")
            truth_entry = _entry_for_stored(manifest, f"truth_{dataset_id}.npz")
            raw_name = PurePosixPath(raw_entry["original_path"]).name
            frame = _read_csv(root / raw_entry["stored_path"])
            missing = REQUIRED_EXCITATION_COLUMNS.difference(frame.columns)
            finite = _finite_excitation(frame) if not missing else pd.DataFrame()
            timestamp = finite["timestamp"] if not finite.empty else pd.Series(dtype=float)
            duration = float(timestamp.max() - timestamp.min()) if len(timestamp) else math.nan
            reversals = int((frame["timestamp"].diff().dropna() <= 0).sum()) if "timestamp" in frame else None
            truth_path = root / truth_entry["stored_path"]
            with np.load(truth_path, allow_pickle=False) as truth:
                truth_fields = set(truth.files)
                truth_frequency = float(truth["frequency"]) if "frequency" in truth_fields else math.nan
                truth_finite = all(np.isfinite(np.asarray(truth[key])).all() for key in truth.files)
            group = mle.loc[mle["dataset_filename"].astype(str) == raw_name]
            if missing:
                failures.append(f"required excitation columns absent for {dataset_id}: {sorted(missing)}")
            if len(finite) < 1000:
                failures.append(f"fewer than 1000 finite paired rows for {dataset_id}: {len(finite)}")
            if not np.isfinite(duration) or duration <= 0:
                failures.append(f"non-positive finite duration for {dataset_id}")
            if raw_name not in mle_names or group.empty:
                failures.append(f"MLE mapping absent for {dataset_id}: {raw_name}")
            elif group["iteration"].isna().all():
                failures.append(f"final MLE iteration absent for {dataset_id}")
            if "frequency" not in truth_fields or not np.isfinite(truth_frequency):
                failures.append(f"truth-frequency field absent/non-finite for {dataset_id}")
            if not truth_finite:
                failures.append(f"truth NPZ contains non-finite values for {dataset_id}")
            diagnostics["injections"].append(
                {
                    "dataset_id": dataset_id,
                    "original_filename": raw_name,
                    "rows": int(len(frame)),
                    "finite_paired_rows": int(len(finite)),
                    "duration_s": duration,
                    "timestamp_nonmonotonic_steps": reversals,
                    "truth_frequency_hz": truth_frequency,
                    "mle_rows": int(len(group)),
                    "mle_iterations": int(group["iteration"].nunique()) if not group.empty else 0,
                }
            )

        if len(mle_names) != 7:
            failures.append(f"expected exactly seven MLE datasets; found {len(mle_names)}")

        controls = {"lln": 28309, "hln": 28314}
        for label, expected_rows in controls.items():
            frame = _read_csv(root / "upstream" / f"control_{label}.csv")
            missing = REQUIRED_EXCITATION_COLUMNS.difference(frame.columns)
            if missing:
                failures.append(f"control {label} columns absent: {sorted(missing)}")
            if len(frame) != expected_rows:
                failures.append(f"control {label} expected {expected_rows} rows; found {len(frame)}")
            diagnostics[f"control_{label}"] = {
                "rows": int(len(frame)),
                "timestamp_nonmonotonic_steps": int((frame["timestamp"].diff().dropna() <= 0).sum()),
            }

        for label in ("lln", "hln"):
            array = np.load(root / "upstream" / f"sigma_{label}.npy", allow_pickle=False)
            if array.shape != (8000,):
                failures.append(f"sigma_{label} expected shape [8000]; found {list(array.shape)}")
            if not np.isfinite(array).all():
                failures.append(f"sigma_{label} contains non-finite values")
            diagnostics[f"sigma_{label}"] = {"shape": list(array.shape), "dtype": str(array.dtype)}
    except Exception as error:
        failures.append(f"schema/mapping exception: {type(error).__name__}: {error}")

    return {
        "passed": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "diagnostics": diagnostics,
    }


def _noise_summary(values: np.ndarray, shots: int) -> dict[str, float]:
    block_size = 141.0
    mean = float(np.mean(values))
    p16, p84 = np.percentile(values, [16, 84])
    scale = math.sqrt(shots / block_size)
    return {
        "realizations": int(values.size),
        "shots": shots,
        "block_size_shots": int(block_size),
        "block_level_mean_rad": mean,
        "whole_dataset_rad": mean / scale,
        "whole_dataset_uncertainty_rad": max(mean - float(p16), float(p84) - mean) / scale,
    }


def _authority_markdown(report: dict[str, Any]) -> str:
    records = report.get("authority", {}).get("claim_ledger", {}).get("records", [])
    if not records:
        return "## Autoridad observacional\n\nNo se generó ledger de autoridad."
    rows = "\n".join(
        f"| {item['claim_id']} | {item['kind']} | {item['status']} |"
        for item in records
    )
    return (
        "## Autoridad observacional\n\n"
        "| Claim | Tipo | Estado |\n|---|---|---|\n"
        f"{rows}\n\n"
        "La promoción automática está desactivada. Un estado NOT_ESTIMABLE "
        "se conserva con blockers; no equivale a cero ni a refutación."
    )

def _render_markdown(report: dict[str, Any]) -> str:
    authority_section = _authority_markdown(report)
    if report["decision"] == "ABSTAIN_INTEGRITY":
        failures = "\n".join(f"- {item}" for item in report["gate_0"]["failures"])
        return f"""# DarkPipe 0.4 — recibo AION

Decisión preregistrada: **ABSTAIN_INTEGRITY**.

La custodia o el contrato de datos falló antes de promover resultados científicos. No se calculan ni se reinterpretan E1/E2.

{failures}

{authority_section}
"""
    rows = "\n".join(
        f"| {item['dataset_id']} | {1e3*item['truth_frequency_hz']:.6g} | {1e3*item['recovered_frequency_hz']:.6g} | {item['resolution_normalized_error']:.6g} | {'PASS' if item['passed'] else 'FAIL'} |"
        for item in report["endpoint_e1"]["datasets"]
    )
    noise = report["endpoint_e2"]
    limits = "\n".join(f"- {item}: `NOT_ESTIMABLE`" for item in report["not_estimable"])
    return f"""# DarkPipe 0.4 — validación instrumental AION

Decisión preregistrada: **{report['decision']}**.

## Qué se ha probado

DarkPipe verificó 27/27 archivos seleccionados del depósito AION, evaluó la recuperación de siete modulaciones de fase intencionalmente inyectadas y comparó los derivados de incertidumbre de fase diferencial con bajo y alto ruido láser. Es una validación acotada de evidencia instrumental real; no es una detección de materia oscura ni de ondas gravitacionales.

## E1 — recuperación de frecuencia

| Dataset | f verdadera (mHz) | f recuperada (mHz) | error × T | decisión |
|---|---:|---:|---:|---|
{rows}

E1: **{'PASS' if report['endpoint_e1']['passed'] else 'FAIL'}** ({report['endpoint_e1']['passed_count']}/7 dentro de una celda de Fourier).

## E2 — consistencia HLN frente a LLN

- Diferencia HLN−LLN: {1e6*noise['difference_rad']:.6g} µrad.
- Incertidumbre combinada: {1e6*noise['difference_uncertainty_rad']:.6g} µrad.
- IC normal bilateral 95%: [{1e6*noise['ci95_rad'][0]:.6g}, {1e6*noise['ci95_rad'][1]:.6g}] µrad.
- E2: **{'PASS' if noise['passed'] else 'FAIL'}**; el intervalo {'incluye' if noise['passed'] else 'no incluye'} cero.

Un PASS sólo significa que no se resuelve un exceso HLN–LLN dentro de esta representación upstream de incertidumbre. No demuestra equivalencia ni agota sistemáticos.

## Límites obligatorios

{limits}

{authority_section}

Consulte `report.json`, `validation.png`, `manifest.json` y el preregistro `DP-AION-0.4-20260825` para los números, hashes y reglas exactas.
"""


def _write_figure(report: dict[str, Any], path: Path) -> None:
    e1 = report["endpoint_e1"]["datasets"]
    e2 = report["endpoint_e2"]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2), constrained_layout=True)
    truth = np.array([item["truth_frequency_hz"] for item in e1])
    recovered = np.array([item["recovered_frequency_hz"] for item in e1])
    axes[0].loglog(truth, recovered, "o", color="#1f4e79")
    bounds = [min(truth.min(), recovered.min()) * 0.8, max(truth.max(), recovered.max()) * 1.2]
    axes[0].plot(bounds, bounds, "k--", linewidth=1)
    axes[0].set(xlabel="Injected frequency [Hz]", ylabel="Recovered frequency [Hz]", title="Frequency recovery")
    epsilon = np.array([item["resolution_normalized_error"] for item in e1])
    axes[1].bar(range(len(e1)), epsilon, color=["#2a9d8f" if item["passed"] else "#9b2226" for item in e1])
    axes[1].axhline(1.0, color="black", linestyle="--", linewidth=1)
    axes[1].set_xticks(range(len(e1)), [item["dataset_id"] for item in e1], rotation=45, ha="right")
    axes[1].set(ylabel=r"$|\hat f-f_{true}|T$", title="Preregistered E1")
    conditions = [e2["lln"], e2["hln"]]
    values = 1e6 * np.array([item["whole_dataset_rad"] for item in conditions])
    errors = 1e6 * np.array([item["whole_dataset_uncertainty_rad"] for item in conditions])
    axes[2].errorbar([0, 1], values, yerr=errors, fmt="o", capsize=5, color="#5a189a")
    axes[2].set_xticks([0, 1], ["LLN", "HLN"])
    axes[2].set(ylabel="Whole-dataset phase uncertainty [µrad]", title="Preregistered E2")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_aion_validation(evidence_root: str | Path, output: str | Path) -> dict[str, Any]:
    """Run the frozen DP-AION-0.4-20260825 decision rule and write a receipt."""
    root = Path(evidence_root)
    target = Path(output)
    target.mkdir(parents=True, exist_ok=True)
    gate = validate_aion_evidence(root)
    base: dict[str, Any] = {
        "schema_version": "1.0",
        "campaign_id": CAMPAIGN_ID,
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "software_version": "0.5.0",
        "generated_at_utc": utc_now(),
        "source_manifest_sha256": sha256_file(root / "source_manifest.json") if (root / "source_manifest.json").is_file() else None,
        "gate_0": gate,
        "claim_ceiling": "bounded software-and-instrument validation; not a dark-matter or gravitational-wave detection",
        "not_estimable": [
            "blind-search false-positive rate",
            "global dark-matter or gravitational-wave significance",
            "transfer to AION-10 or AION-km sensitivity",
            "independent full raw-HDF5 marginal-likelihood reproduction",
        ],
    }
    if not gate["passed"]:
        base["decision"] = "ABSTAIN_INTEGRITY"
        base["authority"] = aion_authority_payload(base)
        write_json(target / "report.json", base)
        (target / "report.md").write_text(_render_markdown(base), encoding="utf-8")
    else:
        manifest = _manifest(root)
        mle = pd.read_csv(root / "upstream" / "mle_scan.csv", low_memory=False)
        recoveries = []
        for dataset_id in INJECTIONS:
            raw_entry = _entry_for_stored(manifest, f"injection_{dataset_id}.csv")
            raw_name = PurePosixPath(raw_entry["original_path"]).name
            frame = _read_csv(root / raw_entry["stored_path"])
            finite = _finite_excitation(frame)
            duration = float(finite["timestamp"].max() - finite["timestamp"].min())
            group = mle.loc[mle["dataset_filename"].astype(str) == raw_name]
            final_iteration = int(group["iteration"].max())
            final = group.loc[group["iteration"] == final_iteration].copy()
            peak_logl = float(final["fit_logL"].max())
            peak = final.loc[final["fit_logL"] == peak_logl].sort_values("f_hz", kind="stable").iloc[0]
            with np.load(root / "upstream" / f"truth_{dataset_id}.npz", allow_pickle=False) as truth:
                true_frequency = float(truth["frequency"])
            recovered_frequency = float(peak["f_hz"])
            epsilon = abs(recovered_frequency - true_frequency) * duration
            recoveries.append(
                {
                    "dataset_id": dataset_id,
                    "original_filename": raw_name,
                    "rows": int(len(frame)),
                    "finite_paired_rows": int(len(finite)),
                    "duration_s": duration,
                    "median_cadence_s": float(finite["timestamp"].diff().median()),
                    "timestamp_nonmonotonic_steps": int((frame["timestamp"].diff().dropna() <= 0).sum()),
                    "final_iteration": final_iteration,
                    "final_iteration_grid_points": int(len(final)),
                    "truth_frequency_hz": true_frequency,
                    "recovered_frequency_hz": recovered_frequency,
                    "absolute_error_hz": abs(recovered_frequency - true_frequency),
                    "fourier_resolution_hz": 1.0 / duration,
                    "resolution_normalized_error": epsilon,
                    "peak_log_likelihood": peak_logl,
                    "passed": bool(epsilon <= 1.0),
                }
            )
        e1_passed = sum(item["passed"] for item in recoveries)
        lln = _noise_summary(np.load(root / "upstream" / "sigma_lln.npy", allow_pickle=False), 28309)
        hln = _noise_summary(np.load(root / "upstream" / "sigma_hln.npy", allow_pickle=False), 28314)
        difference = hln["whole_dataset_rad"] - lln["whole_dataset_rad"]
        difference_uncertainty = math.hypot(
            hln["whole_dataset_uncertainty_rad"], lln["whole_dataset_uncertainty_rad"]
        )
        ci = [difference - 1.96 * difference_uncertainty, difference + 1.96 * difference_uncertainty]
        e2_passed = bool(ci[0] <= 0.0 <= ci[1])
        for condition in (lln, hln):
            sql = 0.0435 / math.sqrt(condition["shots"])
            sql_uncertainty = 0.0016 / math.sqrt(condition["shots"])
            condition["published_sql_rad"] = sql
            condition["published_sql_uncertainty_rad"] = sql_uncertainty
            condition["minus_sql_rad"] = condition["whole_dataset_rad"] - sql
            condition["minus_sql_combined_uncertainty_rad"] = math.hypot(
                condition["whole_dataset_uncertainty_rad"], sql_uncertainty
            )
        base.update(
            endpoint_e1={
                "rule": "all seven abs(f_hat-f_true)*T <= 1",
                "passed": e1_passed == 7,
                "passed_count": int(e1_passed),
                "total_count": 7,
                "datasets": recoveries,
            },
            endpoint_e2={
                "rule": "two-sided 95% normal interval for HLN-LLN includes zero",
                "passed": e2_passed,
                "lln": lln,
                "hln": hln,
                "difference_rad": difference,
                "difference_uncertainty_rad": difference_uncertainty,
                "ci95_rad": ci,
                "z_score": difference / difference_uncertainty,
            },
        )
        base["decision"] = "PASS_BOUNDED" if e1_passed == 7 and e2_passed else "FAIL_BOUNDED"
        base["authority"] = aion_authority_payload(base)
        write_json(target / "report.json", base)
        (target / "report.md").write_text(_render_markdown(base), encoding="utf-8")
        _write_figure(base, target / "validation.png")
    files = [file_record(path, target) for path in sorted(target.iterdir()) if path.is_file() and path.name != "manifest.json"]
    write_json(
        target / "manifest.json",
        {
            "schema_version": "1.0",
            "campaign_id": CAMPAIGN_ID,
            "generated_at_utc": utc_now(),
            "files": files,
        },
    )
    return base
