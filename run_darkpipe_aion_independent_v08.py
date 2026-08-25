"""Run endpoint-blind source inventory for DarkPipe 0.8."""
import argparse
import json
from pathlib import Path

from darkpipe.aion_independent import run_inventory


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("inventory",), required=True)
    parser.add_argument("--workspace", required=True)
    args = parser.parse_args()
    result = run_inventory(Path(args.workspace))
    print(
        json.dumps(
            {
                "status": result["stage"],
                "endpoint_values_read": result["inventory"][
                    "endpoint_values_read"
                ],
                "dataset_count": result["inventory"]["dataset_count"],
                "raw_retained": result["raw_retained"],
            }
        )
    )


if __name__ == "__main__":
    main()
