"""Run DarkPipe 0.8 independent-epoch stages with ephemeral raw custody."""
import argparse
import json
from pathlib import Path

from darkpipe.aion_independent import (
    SOURCE_FILENAME,
    download_source,
    fetch_source_record,
)
from darkpipe.provenance import utc_now, write_json
from darkpipe.aion_independent_search import confirm, discover


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=("discover", "confirm"), required=True
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--scratch", required=True)
    parser.add_argument("--preregistration-commit")
    parser.add_argument("--candidate-commit")
    parser.add_argument("--discovery")
    args = parser.parse_args()
    output = Path(args.output)
    scratch = Path(args.scratch)
    output.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)
    raw = scratch / SOURCE_FILENAME
    try:
        record = fetch_source_record(output / "zenodo_record.json")
        receipt = download_source(record, raw)
        receipt.update(
            {
                "record_id": int(record["id"]),
                "filename": SOURCE_FILENAME,
                "raw_retained": False,
            }
        )
        if args.mode == "discover":
            if not args.preregistration_commit:
                raise SystemExit(
                    "--preregistration-commit is required"
                )
            result = discover(
                raw,
                output,
                receipt,
                args.preregistration_commit,
            )
        else:
            if not args.candidate_commit or not args.discovery:
                raise SystemExit(
                    "--candidate-commit and --discovery are required"
                )
            result = confirm(
                raw,
                output,
                receipt,
                args.discovery,
                args.candidate_commit,
            )
    except (OSError, ValueError, KeyError) as error:
        result = {
            "schema_version": "1.0",
            "stage": "INTEGRITY_ABSTENTION",
            "generated_at_utc": utc_now(),
            "decision": "ABSTAIN_INTEGRITY",
            "error_type": type(error).__name__,
            "error": str(error),
            "raw_retained": False,
        }
        write_json(output / "failure_receipt.json", result)
    finally:
        raw.unlink(missing_ok=True)
    print(
        json.dumps(
            {
                "stage": result["stage"],
                "decision": result.get("decision"),
                "candidate_count": len(
                    result.get(
                        "candidates",
                        result.get("holdout_confirmation", []),
                    )
                ),
                "raw_retained": raw.exists(),
            }
        )
    )


if __name__ == "__main__":
    main()
