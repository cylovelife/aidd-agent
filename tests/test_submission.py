"""Platform receipt states and duplicate-attempt protection.

@author cylovelife
"""

import pytest

from aidd_agent.submission import classify_response, submit_once


def test_received_is_pending_and_errors_are_not_success():
    status, _ = classify_response({"value": "Submission received from 'aidd-agent' for the track."})
    assert status == "received_pending_scoring"
    assert classify_response("Error: File contains NaN")[0] == "rejected"
    assert classify_response({"unexpected": 1})[0] == "unknown"


def test_existing_attempt_is_not_retried(tmp_path):
    with pytest.raises(ValueError, match="prior attempt"):
        submit_once(tmp_path / "absent.csv", tmp_path, tmp_path, "cylovelife", "", "")
