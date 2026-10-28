"""One-shot official submission with intent/receipt evidence and no automatic retry.

@author cylovelife
"""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pandas as pd

from aidd_agent.baseline import write_json
from aidd_agent.contracts import load_identities, validate_submission
from aidd_agent.sources import sha256_file, verify_data
from aidd_agent.vendor.openadmet.activity_validation import validate_activity_submission


def classify_response(response: object) -> tuple[str, str]:
    value = response.get("value") if isinstance(response, dict) else response
    if not isinstance(value, str):
        return "unknown", "Unrecognized platform response; inspect before retrying"
    if value.startswith("Submission received from "):
        return "received_pending_scoring", value
    if value.startswith("Error:"):
        return "rejected", value
    return "unknown", value


def submit_once(
    file: Path,
    data_dir: Path,
    receipt_dir: Path,
    username: str,
    method_url: str,
    expected_sha256: str,
) -> dict[str, object]:
    if receipt_dir.exists():
        raise ValueError("Receipt directory exists; inspect the prior attempt instead of retrying")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", username):
        raise ValueError("Provide the actual Hugging Face username")
    if sha256_file(file) != expected_sha256:
        raise ValueError("Prediction SHA256 differs from the reviewed artifact")
    verify_data(data_dir)
    test = load_identities(data_dir / "cyp-challenge-TEST-BLINDED.csv")
    validate_submission(pd.read_csv(file), test)
    valid, errors = validate_activity_submission(file, set(test["Molecule_Name"]))
    if not valid:
        raise ValueError(f"Official validator rejected predictions: {errors}")
    if not method_url.startswith("https://github.com/cylovelife/aidd-agent/"):
        raise ValueError("Method report must be a public versioned URL in this project")
    with httpx.Client(timeout=30, follow_redirects=True) as web:
        web.get(f"https://huggingface.co/{username}").raise_for_status()
        web.get(method_url).raise_for_status()
    # Only this explicitly invoked optional path imports the submission SDK.
    from gradio_client import Client, handle_file

    receipt_dir.mkdir(parents=True, exist_ok=False)
    intent = {
        "created_at": datetime.now(UTC).isoformat(),
        "username": username,
        "alias": "aidd-agent",
        "anonymous": True,
        "track": "Regression Prediction",
        "method_url": method_url,
        "file_sha256": expected_sha256,
        "proprietary_data": False,
        "open_source_code": True,
        "publication_opt_in": False,
        "optional_contact_fields": "not supplied",
    }
    write_json(receipt_dir / "intent.json", intent)
    try:
        client = Client(
            "https://openadmet-cyp-challenge.hf.space",
            verbose=False,
            analytics_enabled=False,
            httpx_kwargs={"timeout": 60.0},
            download_files=str(receipt_dir / "downloads"),
        )
        response = client.submit(
            username,
            "aidd-agent",
            True,
            "",
            "",
            "",
            "",
            method_url,
            False,
            False,
            True,
            "Regression Prediction",
            handle_file(str(file.resolve())),
            api_name="/submit_predictions",
        ).result(timeout=180)
    except Exception as error:
        write_json(
            receipt_dir / "outcome-unknown.json",
            {"status": "unknown", "error_type": type(error).__name__, "automatic_retry": False},
        )
        raise RuntimeError("Submission outcome uncertain; inspect before any retry") from error
    status, message = classify_response(response)
    receipt = {
        **intent,
        "responded_at": datetime.now(UTC).isoformat(),
        "status": status,
        "message": message,
        "official_score": None,
    }
    write_json(receipt_dir / "receipt.json", receipt)
    return receipt


def match_scored_entry(
    frame: pd.DataFrame, alias: str, method_url: str
) -> dict[str, object] | None:
    required = {"Username", "Model Report Link", "Rank", "MA-ST-RAE", "Submitted"}
    if frame.empty or not required.issubset(frame.columns):
        raise ValueError("Official leaderboard is empty or has an unexpected schema")
    matching = frame.loc[frame["Username"].eq(alias) & frame["Model Report Link"].eq(method_url)]
    if matching.empty:
        return None
    if len(matching) != 1:
        raise ValueError("Ambiguous leaderboard identity: multiple matching entries")
    row = matching.iloc[0]
    score = float(row["MA-ST-RAE"])
    rank = int(row["Rank"])
    if not 0 <= score < float("inf") or rank < 1:
        raise ValueError("Invalid official score or rank")
    return {
        "rank": rank,
        "leaderboard_entries": len(frame),
        "ma_st_rae": score,
        "submitted": str(row["Submitted"]),
        "alias": alias,
        "method_url": method_url,
        "leaderboard_scope": "live public regression leaderboard, not final ranking",
    }


def check_leaderboard(receipt_dir: Path) -> dict[str, object]:
    from gradio_client import Client

    with (receipt_dir / "receipt.json").open() as stream:
        receipt = json.load(stream)
    client = Client(
        "https://openadmet-cyp-challenge.hf.space",
        verbose=False,
        analytics_enabled=False,
        httpx_kwargs={"timeout": 60.0},
        download_files=str(receipt_dir / "leaderboard-downloads"),
    )
    path = client.submit(api_name="/partial").result(timeout=90)
    if not isinstance(path, str):
        raise ValueError("Unexpected official leaderboard download response")
    entry = match_scored_entry(pd.read_csv(path), receipt["alias"], receipt["method_url"])
    now = datetime.now(UTC)
    result: dict[str, object] = {
        "checked_at": now.isoformat(),
        "status": "scored" if entry is not None else "not_yet_on_leaderboard",
        "entry": entry,
        "leaderboard_file": path,
        "leaderboard_sha256": sha256_file(Path(path)),
    }
    write_json(receipt_dir / f"leaderboard-{now.strftime('%Y%m%dT%H%M%S%fZ')}.json", result)
    return result
