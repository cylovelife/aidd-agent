"""Pinned public dataset acquisition with immutable local files.

@author cylovelife
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

DATASET_REVISION = "d7eb3c973dca01aad8e33c91c29e5123fd925d8f"
DATASET_REPO = "openadmet/cyp-challenge-train-test"
DATA_FILES = ("README.md", "cyp-challenge-TRAIN_inhibition.csv", "cyp-challenge-TEST-BLINDED.csv")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_data(directory: Path) -> dict[str, object]:
    with (directory / "manifest.json").open() as stream:
        manifest = json.load(stream)
    if manifest.get("revision") != DATASET_REVISION or manifest.get("repo_id") != DATASET_REPO:
        raise ValueError("Unexpected dataset revision or repository")
    records = manifest.get("files", [])
    if {item["name"] for item in records} != set(DATA_FILES) or len(records) != len(DATA_FILES):
        raise ValueError("Incomplete dataset manifest")
    for item in records:
        path = directory / item["name"]
        if sha256_file(path) != item["sha256"]:
            raise ValueError(f"Raw input hash mismatch: {item['name']}")
    return dict(manifest)


def download_data(directory: Path) -> dict[str, object]:
    if (directory / "manifest.json").exists():
        return verify_data(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if any(directory.iterdir()):
        raise ValueError("Incomplete existing data directory; use a fresh directory")
    records = []
    timeout = httpx.Timeout(connect=15, read=60, write=30, pool=15)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for name in DATA_FILES:
            url = (
                f"https://huggingface.co/datasets/{DATASET_REPO}/resolve/{DATASET_REVISION}/{name}"
            )
            response = client.get(url)
            response.raise_for_status()
            path = directory / name
            with path.open("xb") as stream:
                stream.write(response.content)
            records.append(
                {
                    "name": name,
                    "url": url,
                    "sha256": sha256_file(path),
                    "bytes": path.stat().st_size,
                }
            )
    manifest = {
        "repo_id": DATASET_REPO,
        "revision": DATASET_REVISION,
        "downloaded_at": datetime.now(UTC).isoformat(),
        "files": records,
    }
    with (directory / "manifest.json").open("x") as stream:
        json.dump(manifest, stream, indent=2)
    return verify_data(directory)
