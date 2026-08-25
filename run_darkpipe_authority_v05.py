"""Run DarkPipe 0.5 AION validation with the typed authority receipt."""
import argparse
import json
from pathlib import Path

from darkpipe.aion import EVIDENCE_DIRECTORY, run_aion_validation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence",
        default=str(Path(__file__).parent / "evidence" / EVIDENCE_DIRECTORY),
    )
    parser.add_argument("--output", default="darkpipe_authority_v05_run")
    args = parser.parse_args()
    result = run_aion_validation(args.evidence, args.output)
    records = result["authority"]["claim_ledger"]["records"]
    print(
        json.dumps(
            {
                "decision": result["decision"],
                "software_version": result["software_version"],
                "output": str(Path(args.output).resolve()),
                "claim_statuses": {
                    item["claim_id"]: item["status"] for item in records
                },
                "automatic_promotion": result["authority"]["claim_ledger"][
                    "automatic_promotion"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
