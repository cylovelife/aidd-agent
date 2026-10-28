"""Immutable source manifests reject tampering and incomplete acquisitions.

@author cylovelife
"""

import json

import pytest

from aidd_agent.sources import (
    DATA_FILES,
    DATASET_REPO,
    DATASET_REVISION,
    download_data,
    sha256_file,
    verify_data,
)


def test_manifest_detects_tampered_inputs_without_network(tmp_path):
    records = []
    for name in DATA_FILES:
        path = tmp_path / name
        path.write_text("frozen fixture")
        records.append({"name": name, "sha256": sha256_file(path)})
    manifest = {"revision": DATASET_REVISION, "repo_id": DATASET_REPO, "files": records}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    assert verify_data(tmp_path)["revision"] == DATASET_REVISION
    assert download_data(tmp_path)["revision"] == DATASET_REVISION
    (tmp_path / DATA_FILES[0]).write_text("tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_data(tmp_path)


def test_incomplete_data_is_not_silently_overwritten(tmp_path):
    (tmp_path / "partial").write_text("preserve")
    with pytest.raises(ValueError, match="fresh directory"):
        download_data(tmp_path)
    assert (tmp_path / "partial").read_text() == "preserve"
