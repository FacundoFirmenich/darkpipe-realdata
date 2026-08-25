"""Reproduce or stage the DarkPipe 0.6 AION blinded holdout campaign."""
import argparse
import json
from pathlib import Path

from darkpipe.aion import EVIDENCE_DIRECTORY
from darkpipe.aion_blind import analyze_blind_challenge, prepare_blind_challenge, reveal_blind_challenge

ROOT = Path(__file__).parent
CHECKED = ROOT / "evidence" / "aion_blind_holdout_2026-08-25"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("reproduce", "prepare", "analyze", "reveal"), default="reproduce")
    parser.add_argument("--evidence", default=str(ROOT / "evidence" / EVIDENCE_DIRECTORY))
    parser.add_argument("--campaign", default="darkpipe_aion_blind_reproduction")
    parser.add_argument("--seed-file")
    parser.add_argument("--preregistration-commit", default="dbd2da7")
    args = parser.parse_args()
    campaign = Path(args.campaign)
    if args.seed_file:
        seed = Path(args.seed_file).read_text(encoding="utf-8").strip()
    elif args.mode == "reproduce":
        seed = json.loads((CHECKED / "seed_reveal.json").read_text(encoding="utf-8"))["seed_hex"]
    else:
        seed = None
    if args.mode in ("reproduce", "prepare"):
        if seed is None:
            raise SystemExit("--seed-file is required before reveal")
        prepare_blind_challenge(args.evidence, campaign, seed, args.preregistration_commit)
    if args.mode in ("reproduce", "analyze"):
        analyze_blind_challenge(args.evidence, campaign)
    if args.mode in ("reproduce", "reveal"):
        if seed is None:
            raise SystemExit("--seed-file is required for reveal")
        report = reveal_blind_challenge(campaign, seed)
        print(json.dumps({"decision": report["decision"], "campaign": str(campaign.resolve())}))
    else:
        print(json.dumps({"status": args.mode.upper(), "campaign": str(campaign.resolve())}))


if __name__ == "__main__":
    main()
