#!/usr/bin/env python3
"""Seal downloaded KiDS pair artifacts before removing transient copies."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_artifact(path: Path, root: Path) -> dict[str, object]:
    with np.load(path, allow_pickle=False) as values:
        metadata = json.loads(str(values["metadata_json"]))
        content_sha256 = str(values["content_sha256"])
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "file_sha256": file_sha256(path),
        "content_sha256": content_sha256,
        "start_row": int(metadata["start_row"]),
        "stop_row": int(metadata["stop_row"]),
        "complete": bool(metadata["complete"]),
        "radial_edges_sha256": metadata.get("radial_edges_sha256"),
        "lens_payload_sha256": metadata.get("lens_payload_sha256"),
        "sigma_lookup_sha256": metadata.get("sigma_lookup_sha256"),
        "authority": metadata.get("authority"),
        "diagnostics": metadata.get("diagnostics"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--classification", required=True)
    args = parser.parse_args()
    files = sorted(args.root.rglob("*.npz"))
    if not files:
        raise RuntimeError("no NPZ artifacts found to seal")
    artifacts = [inspect_artifact(path, args.root) for path in files]
    canonical = json.dumps(artifacts, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload = {
        "schema": "darkpipe.kids-pair-artifact-custody.v1",
        "sealed_at": datetime.now(timezone.utc).isoformat(),
        "github_actions_run_id": args.run_id,
        "classification": args.classification,
        "artifact_count": len(artifacts),
        "total_bytes": sum(int(item["bytes"]) for item in artifacts),
        "artifacts_sha256": hashlib.sha256(canonical).hexdigest(),
        "artifacts": artifacts,
        "authority": "BYTE_AND_METADATA_CUSTODY_NO_SCIENTIFIC_RESULT",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(args.output)
    print(json.dumps({key: payload[key] for key in payload if key != "artifacts"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
