#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Mapping


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalise_answer(answer: Mapping[str, Any], question: Mapping[str, Any]) -> tuple[dict[str, float], Any]:
    qtype = question["type"]
    if qtype in {"choice", "score"}:
        labels = list(question["criteria"])
        raw = answer.get("probabilities") or {}
        values = {label: max(0.0, float(raw.get(label, 0.0))) for label in labels}
        total = sum(values.values())
        if total <= 0:
            values = {label: 1.0 / len(labels) for label in labels}
        else:
            values = {label: value / total for label, value in values.items()}
        prediction = answer.get("choice") if qtype == "choice" else str(answer.get("score"))
        if prediction not in labels:
            prediction = max(values, key=values.get)
        return values, prediction
    raw = answer.get("noul")
    probability = float(raw if raw is not None else answer.get("confidence", 0.5))
    probability = min(1.0, max(0.0, probability))
    return {"true": probability, "false": 1.0 - probability}, probability >= 0.5


def state_for(pair: Mapping[str, Any], language: str) -> str:
    return (
        f"CLAIM: {pair['claim_' + language]}\n"
        f"PASSAGE: {pair['passage_' + language]}\n"
        f"SOURCE_ROLE: {pair['passage_source_id']}\n"
        f"DOMAIN: {pair['domain']}\n"
        f"TRANSLATION_STATUS: {pair['translation_status']}"
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    import torch
    import laya
    from laya import Router

    pairs = read_jsonl(args.pairs)
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    questions = contract["questions"]
    args.output.mkdir(parents=True, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    router = Router(device=device)
    load_started = time.perf_counter()
    router.preload(args.checkpoints)
    load_ms = (time.perf_counter() - load_started) * 1000
    rows: list[dict[str, Any]] = []
    for checkpoint in args.checkpoints:
        for pair in pairs:
            for language in ("es", "en"):
                started = time.perf_counter()
                error = None
                result = None
                try:
                    result = router.predict(state_for(pair, language), questions, model=checkpoint)
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"[:1000]
                latency_ms = (time.perf_counter() - started) * 1000
                answers = (result or {}).get("answers") or {}
                for question_id, question in questions.items():
                    answer = answers.get(question_id)
                    if not answer:
                        rows.append({"item_id": pair["item_id"], "domain": pair["domain"], "candidate_role_hint": pair["candidate_role_hint"], "language": language, "checkpoint": checkpoint, "question_id": question_id, "primitive": question["type"], "ok": False, "latency_ms": latency_ms, "error": error or "MISSING_ANSWER"})
                        continue
                    distribution, prediction = normalise_answer(answer, question)
                    rows.append({"item_id": pair["item_id"], "domain": pair["domain"], "candidate_role_hint": pair["candidate_role_hint"], "language": language, "checkpoint": checkpoint, "question_id": question_id, "primitive": question["type"], "ok": error is None, "latency_ms": latency_ms, "prediction": prediction, "distribution": distribution, "raw_answer": answer, "error": error})
                args.output.joinpath("bilingual_shadow_outputs.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    status = {"attempted": True, "completed": all(row.get("ok") for row in rows), "provider": "laya", "provider_version": getattr(laya, "__version__", "unknown"), "device": device, "load_ms": load_ms, "checkpoints": args.checkpoints, "pairs": len(pairs), "languages": ["es", "en"], "question_count": len(questions), "output_records": len(rows), "failures": sum(not row.get("ok") for row in rows), "gold_status": "NOT_FROZEN", "translation_status": "MODEL_TRANSLATION_PENDING_HUMAN_REVIEW", "provider_has_authority": False, "automatic_execution": False, "automatic_publication": False}
    (args.output / "bilingual_shadow_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--checkpoints", nargs="+", default=["english", "multilingual", "typed-decisions"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
