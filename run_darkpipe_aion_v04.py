"""Run the preregistered DarkPipe 0.4 AION validation from a source checkout."""
import argparse
import json
from pathlib import Path

from darkpipe.aion import EVIDENCE_DIRECTORY, run_aion_validation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", default=str(Path(__file__).parent / "evidence" / EVIDENCE_DIRECTORY))
    parser.add_argument("--output", default="darkpipe_aion_run")
    args = parser.parse_args()
    result = run_aion_validation(args.evidence, args.output)
    print(json.dumps({"decision": result["decision"], "output": str(Path(args.output).resolve())}))


if __name__ == "__main__":
    main()
