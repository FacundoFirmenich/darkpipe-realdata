"""Build a cross-platform manifest from exact Git index blobs."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_REL = "evidence/repository_file_manifest.json"


def _git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def index_paths() -> list[str]:
    payload = _git("ls-files", "-z")
    return sorted(
        path.decode("utf-8")
        for path in payload.split(b"\0")
        if path and path.decode("utf-8") != MANIFEST_REL
    )


def index_blob(path: str) -> bytes:
    return _git("show", f":{path}")


def build() -> dict:
    files = []
    total = 0
    for path in index_paths():
        payload = index_blob(path)
        total += len(payload)
        files.append(
            {
                "path": path,
                "byte_count": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    if len(files) < 90 or total < 1_000_000:
        raise RuntimeError(f"manifest sanity failure: files={len(files)}, bytes={total}")
    return {
        "schema_version": "1.1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "byte_domain": "exact Git index blobs; independent of checkout EOL normalization",
        "file_count": len(files),
        "total_bytes": total,
        "exclusions": [
            "evidence/repository_file_manifest.json (self)",
            "ignored private native threads",
            "ignored generated run directories",
        ],
        "files": files,
    }


def main() -> None:
    target = ROOT / MANIFEST_REL
    target.write_text(
        json.dumps(build(), indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(target)


if __name__ == "__main__":
    main()
