"""Behavioral contracts for chemical splits, metrics and submissions.

@author cylovelife
"""

import numpy as np
import pandas as pd
import pytest

from aidd_agent.chemistry import encode_molecules, split_groups
from aidd_agent.contracts import TARGETS, load_training, validate_submission
from aidd_agent.metrics import score_endpoint


def submission_pair():
    test = pd.DataFrame({"SMILES": ["CCO", "CCN", "CCC"], "Molecule_Name": ["a", "b", "c"]})
    prediction = test.copy()
    for col in TARGETS:
        prediction[col] = [3.0, 5.0, 6.0]
    return test, prediction


def test_submission_retains_identity_and_fails_corruption():
    test, pred = submission_pair()
    validate_submission(pred, test, expected_rows=3)
    bad = pred.copy()
    bad.loc[0, "SMILES"] = "CCCl"
    with pytest.raises(ValueError, match="SMILES"):
        validate_submission(bad, test, expected_rows=3)
    bad = pred.copy()
    bad.loc[0, TARGETS[0]] = np.inf
    with pytest.raises(ValueError, match="finite"):
        validate_submission(bad, test, expected_rows=3)
    with pytest.raises(ValueError, match="rows"):
        validate_submission(pred, test)


def test_submission_fails_duplicates_constants_extra_columns_and_wrong_ids():
    test, pred = submission_pair()
    bad = pred.copy()
    bad.loc[1, "Molecule_Name"] = "a"
    with pytest.raises(ValueError, match="unique"):
        validate_submission(bad, test, expected_rows=3)
    bad = pred.copy()
    bad[TARGETS[0]] = 4.0
    with pytest.raises(ValueError, match="constant"):
        validate_submission(bad, test, expected_rows=3)
    bad[TARGETS[0]] = [4.0, 4.005, 4.01]
    with pytest.raises(ValueError, match="constant"):
        validate_submission(bad, test, expected_rows=3)
    with pytest.raises(ValueError, match="columns"):
        validate_submission(pred.assign(unexpected=0), test, expected_rows=3)
    bad = pred.copy()
    bad.loc[0, "Molecule_Name"] = "unknown"
    with pytest.raises(ValueError, match="identities"):
        validate_submission(bad, test, expected_rows=3)


def test_molecular_scaffolds_and_canonical_duplicates_stay_together():
    smiles = ["CCO", "OCC", "c1ccccc1O", "c1ccccc1N", "C1CCCCC1", "CCN", "CCC"]
    encoded = encode_molecules(smiles)
    assert encoded.canonical[0] == encoded.canonical[1]
    assert encoded.groups[2] == encoded.groups[3]
    train, valid = split_groups(encoded.groups, seed=42)
    assert set(encoded.groups[train]).isdisjoint(encoded.groups[valid])
    assert len(train) + len(valid) == len(smiles)
    with pytest.raises(ValueError, match="SMILES"):
        encode_molecules(["this-is-not-a-molecule"])
    with pytest.raises(ValueError, match="groups"):
        split_groups(np.array(["same", "same"]), seed=42)


def test_metric_uses_tolerance_in_numerator_and_denominator():
    y = np.array([1.0, 5.0])
    low, high = y - 0.5, y + 0.5
    assert score_endpoint(y, np.array([1.2, 4.8]), low, high)["st_rae"] == 0.0
    assert score_endpoint(y, np.array([3.0, 3.0]), low, high)["st_rae"] == 1.0
    assert score_endpoint(y, np.array([0.0, 6.0]), low, high)["st_rae"] == pytest.approx(1 / 3)
    with pytest.raises(ValueError, match="denominator"):
        score_endpoint(np.ones(2), np.ones(2), np.ones(2), np.ones(2))
    with pytest.raises(ValueError, match="bounds"):
        score_endpoint(y, y, high, low)


def test_training_keeps_missing_targets_and_rejects_invalid_bounds(tmp_path):
    frame = pd.DataFrame({"SMILES": ["CCO", "CCN"], "Molecule_Name": ["a", "b"]})
    for col in TARGETS:
        frame[col] = [5.0, np.nan]
        frame[col + "_conf_low"] = [4.0, np.nan]
        frame[col + "_conf_high"] = [6.0, np.nan]
    path = tmp_path / "train.csv"
    frame.to_csv(path, index=False)
    assert load_training(path)[TARGETS[0]].isna().sum() == 1
    frame.loc[0, TARGETS[0] + "_conf_low"] = 7
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="bounds"):
        load_training(path)
