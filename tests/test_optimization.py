"""Scientific boundaries for the frozen second-round experiment.

@author cylovelife
"""

import numpy as np
import pytest

from aidd_agent.chemistry import encode_molecules, split_groups
from aidd_agent.features import extract_features, tanimoto_kernel
from aidd_agent.optimization import (
    MAX_SECONDS,
    SEEDS,
    check_budget,
    interval_targets,
    predict_candidate,
    select_candidates,
)


def test_features_keep_equivalent_molecules_and_reject_invalid_input():
    features = extract_features(["CCO", "OCC", "c1ccccc1N"])
    for values in (features.bits, features.counts, features.descriptors):
        np.testing.assert_allclose(values[0], values[1])
        assert np.isfinite(values).all()
    assert features.bits.shape == (3, 2048)
    assert len(features.descriptor_names) == features.descriptors.shape[1]
    with pytest.raises(ValueError, match="SMILES"):
        extract_features(["bad-molecule"])


def test_tanimoto_kernel_avoids_integer_overflow_and_rejects_empty_vectors():
    x = np.ones((2, 2048), dtype=np.uint8)
    np.testing.assert_allclose(tanimoto_kernel(x, x), np.ones((2, 2)))
    with pytest.raises(ValueError, match="nonzero"):
        tanimoto_kernel(np.zeros((1, 3)), np.ones((1, 3)))
    with pytest.raises(ValueError, match="nonnegative"):
        tanimoto_kernel(np.array([[-1.0, 2]]), np.ones((1, 2)))


def test_interval_endpoint_replication_matches_interval_distance():
    lower, upper = np.array([1.0, 3.0]), np.array([2.0, 5.0])
    indices, target, weights = interval_targets(lower, upper)
    for pred in (np.array([0.0, 4.0]), np.array([1.5, 6.0])):
        endpoint_loss = np.sum(weights * abs(pred[indices] - target))
        distance = np.sum(np.maximum(lower - pred, 0) + np.maximum(pred - upper, 0))
        assert endpoint_loss == pytest.approx(distance + np.sum(upper - lower) / 2)
    with pytest.raises(ValueError, match="bounds"):
        interval_targets(upper, lower)


def test_real_interval_svr_fits_separated_chemical_intervals():
    features = extract_features(["CCO", "c1ccccc1", "CCN"])
    kernel = tanimoto_kernel(features.counts, features.counts)
    prediction = predict_candidate(
        "interval_svr",
        features,
        np.array([0, 1]),
        features,
        np.array([0, 1]),
        {"counts": kernel},
        {"counts": kernel},
        np.array([1.5, 4.5]),
        np.array([1.0, 4.0]),
        np.array([2.0, 5.0]),
    )
    assert np.all(prediction >= np.array([1.0, 4.0]) - 1e-3)
    assert np.all(prediction <= np.array([2.0, 5.0]) + 1e-3)


def test_selection_uses_all_splits_and_requires_real_gain():
    scores = {
        "a": {"median": 1.0, "ridge": 1.1, "svr_counts": 0.8},
        "b": {"median": 1.0, "ridge": 0.9, "svr_counts": 0.7},
    }
    selected, gate = select_candidates(scores)
    assert selected == {"a": "svr_counts", "b": "svr_counts"}
    assert gate
    scores["a"]["svr_counts"] = 1.1
    scores["b"]["svr_counts"] = 0.9
    assert not select_candidates(scores)[1]


def test_every_frozen_split_keeps_scaffolds_and_duplicates_together():
    encoded = encode_molecules(["CCO", "OCC", "CCN", "CCC", "c1ccccc1O", "c1ccccc1N"])
    for seed in SEEDS:
        fit, valid = split_groups(encoded.groups, seed)
        assert set(encoded.groups[fit]).isdisjoint(encoded.groups[valid])


def test_fit_rejects_missing_labels_and_budget_exhaustion():
    features = extract_features(["CCO", "CCN", "CCC"])
    with pytest.raises(ValueError, match="measured"):
        predict_candidate(
            "ridge",
            features,
            np.array([0, 1]),
            features,
            np.array([2]),
            {},
            {},
            np.array([1.0, np.nan]),
            np.zeros(2),
            np.ones(2),
        )
    import time

    with pytest.raises(RuntimeError, match="wall-time"):
        check_budget(time.monotonic() - MAX_SECONDS - 1)
