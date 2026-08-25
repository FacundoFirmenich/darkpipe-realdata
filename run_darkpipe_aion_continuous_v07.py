"""Stage the DarkPipe 0.7 continuous/environmental campaign."""
import argparse
import json
from pathlib import Path

from darkpipe.aion import EVIDENCE_DIRECTORY
from darkpipe.aion_continuous import (
    confirm_continuous_candidates,
    discover_continuous_candidates,
)

ROOT = Path(__file__).parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("discover", "confirm"), required=True)
    parser.add_argument(
        "--evidence", default=str(ROOT / "evidence" / EVIDENCE_DIRECTORY)
    )
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--preregistration-commit")
    parser.add_argument("--candidate-commit")
    args = parser.parse_args()

    if args.mode == "discover":
        if not args.preregistration_commit:
            raise SystemExit("--preregistration-commit is required for discovery")
        result = discover_continuous_candidates(
            args.evidence, args.campaign, args.preregistration_commit
        )
        payload = {
            "status": "CANDIDATES_FROZEN_FOR_COMMIT",
            "campaign": str(Path(args.campaign).resolve()),
            "candidate_count": len(result["candidates"]),
            "holdout_endpoints_accessed": result["holdout_endpoints_accessed"],
        }
    else:
        if not args.candidate_commit:
            raise SystemExit("--candidate-commit is required for confirmation")
        result = confirm_continuous_candidates(
            args.evidence, args.campaign, args.candidate_commit
        )
        payload = {
            "status": result["decision"],
            "campaign": str(Path(args.campaign).resolve()),
            "confirmed_count": sum(
                item["detected"] for item in result["holdout_confirmation"]
            ),
            "environment": result["environment"]["status"],
        }
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
