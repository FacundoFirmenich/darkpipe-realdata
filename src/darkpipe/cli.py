"""DarkPipe command-line interface."""
import argparse
import json
from pathlib import Path

from .aion import EVIDENCE_DIRECTORY, run_aion_validation
from .aion_blind import (
    analyze_blind_challenge,
    prepare_blind_challenge,
    reveal_blind_challenge,
)
from .pipeline import run_live
from .provenance import write_bytes
from .sources import fetch_hapi


def _read_seed(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8").strip()


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="darkpipe", description="Real-data-first environmental and sensor validation"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run the bounded live NOAA-USGS foreground pipeline")
    run.add_argument("--output", default="darkpipe_run")
    run.add_argument("--station", default="BOU")
    run.add_argument("--raw-retention", choices=("full", "hash-only"), default="full")

    hapi = sub.add_parser("hapi", help="acquire one bounded HAPI dataset")
    hapi.add_argument("--provider", choices=("intermagnet", "nasa_cdaweb"), required=True)
    hapi.add_argument("--dataset", required=True)
    hapi.add_argument("--start", required=True)
    hapi.add_argument("--stop", required=True)
    hapi.add_argument("--output", required=True)

    aion = sub.add_parser("aion-validate", help="run preregistered AION sensor validation")
    aion.add_argument("--evidence", default=str(Path("evidence") / EVIDENCE_DIRECTORY))
    aion.add_argument("--output", default="darkpipe_aion_run")

    blind_prepare = sub.add_parser("aion-blind-prepare", help="seal the v0.6 holdout challenge")
    blind_prepare.add_argument("--evidence", default=str(Path("evidence") / EVIDENCE_DIRECTORY))
    blind_prepare.add_argument("--campaign", required=True)
    blind_prepare.add_argument("--seed-file", required=True)
    blind_prepare.add_argument("--preregistration-commit", required=True)

    blind_analyze = sub.add_parser("aion-blind-analyze", help="predict sealed v0.6 cases without the seed")
    blind_analyze.add_argument("--evidence", default=str(Path("evidence") / EVIDENCE_DIRECTORY))
    blind_analyze.add_argument("--campaign", required=True)

    blind_reveal = sub.add_parser("aion-blind-reveal", help="verify seed and adjudicate v0.6")
    blind_reveal.add_argument("--campaign", required=True)
    blind_reveal.add_argument("--seed-file", required=True)

    args = parser.parse_args(argv)
    if args.command == "run":
        result = run_live(args.output, args.station, args.raw_retention == "full")
        payload = {"status": "ok", "output": str(Path(args.output).resolve()), "rows": result["analysis"]["aligned_finite_rows"]}
    elif args.command == "hapi":
        source = fetch_hapi(args.provider, args.dataset, args.start, args.stop)
        target = Path(args.output)
        target.mkdir(parents=True, exist_ok=True)
        write_bytes(target / "info.json", source.artifacts[0].content)
        write_bytes(target / "data.json", source.artifacts[1].content)
        source.frame.to_csv(target / "data.csv", index=False)
        payload = {"status": "ok", "rows": len(source.frame), "sha256": source.artifacts[1].sha256}
    elif args.command == "aion-validate":
        result = run_aion_validation(args.evidence, args.output)
        payload = {"status": result["decision"], "output": str(Path(args.output).resolve()), "gate_0": result["gate_0"]["passed"], "e1_passed": result.get("endpoint_e1", {}).get("passed"), "e2_passed": result.get("endpoint_e2", {}).get("passed")}
    elif args.command == "aion-blind-prepare":
        result = prepare_blind_challenge(args.evidence, args.campaign, _read_seed(args.seed_file), args.preregistration_commit)
        payload = {"status": "SEALED", "campaign": str(Path(args.campaign).resolve()), "case_count": result["case_count"], "sha256": result["challenge_file"]["sha256"], "mapping_disclosed": result["mapping_disclosed"]}
    elif args.command == "aion-blind-analyze":
        result = analyze_blind_challenge(args.evidence, args.campaign)
        payload = {"status": "PREDICTED_BLIND", "campaign": str(Path(args.campaign).resolve()), "case_count": len(result["cases"]), "mapping_accessed": result["mapping_accessed"]}
    else:
        result = reveal_blind_challenge(args.campaign, _read_seed(args.seed_file))
        payload = {"status": result["decision"], "campaign": str(Path(args.campaign).resolve()), "null_passed": result["gates"]["null_holdout"]["passed"], "signals_passed": result["gates"]["signal_identification"]["passed_count"]}
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
