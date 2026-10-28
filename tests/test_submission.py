"""Platform receipt states and duplicate-attempt protection.

@author cylovelife
"""

import pandas as pd
import pytest

from aidd_agent.submission import classify_response, match_scored_entry, submit_once


def test_received_is_pending_and_errors_are_not_success():
    status, _ = classify_response({"value": "Submission received from 'aidd-agent' for the track."})
    assert status == "received_pending_scoring"
    assert classify_response("Error: File contains NaN")[0] == "rejected"
    assert classify_response({"unexpected": 1})[0] == "unknown"


def test_existing_attempt_is_not_retried(tmp_path):
    with pytest.raises(ValueError, match="prior attempt"):
        submit_once(tmp_path / "absent.csv", tmp_path, tmp_path, "cylovelife", "", "")


def test_score_matching_requires_alias_and_exact_method_url():
    frame = pd.DataFrame(
        {
            "Username": ["aidd-agent", "other"],
            "Model Report Link": ["https://wrong", "https://expected"],
            "Rank": [1, 2],
            "MA-ST-RAE": [0.2, 0.3],
            "Submitted": ["2026-10-28 11:17 UTC"] * 2,
        }
    )
    assert match_scored_entry(frame, "aidd-agent", "https://expected") is None
    frame.loc[0, "Model Report Link"] = "https://expected"
    entry = match_scored_entry(frame, "aidd-agent", "https://expected")
    assert entry is not None
    assert entry["rank"] == 1
    assert entry["ma_st_rae"] == 0.2
    frame.loc[0, "MA-ST-RAE"] = float("nan")
    with pytest.raises(ValueError, match="Invalid official"):
        match_scored_entry(frame, "aidd-agent", "https://expected")
