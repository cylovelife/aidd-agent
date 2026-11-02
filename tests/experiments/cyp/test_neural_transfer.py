"""Optional CPU neural loss and fit-only preprocessing contracts.

@author cylovelife
"""

# ruff: noqa: E402 -- optional dependency must be checked before importing its adapter.

import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")

from aidd_agent.contracts import TARGETS
from aidd_agent.features import MolecularFeatures
from aidd_agent.neural_transfer import balanced_weights, masked_potency_loss, prepare_neural_data


def test_missing_labels_do_not_contribute_loss_or_gradient():
    prediction = torch.ones((2, 4), requires_grad=True)
    truth = torch.full((2, 4), float("nan"))
    truth[0, 0] = 3
    weights = torch.ones((2, 4))
    loss = masked_potency_loss(prediction, truth, truth - 0.1, truth + 0.1, weights)
    assert torch.isfinite(loss)
    loss.backward()
    assert prediction.grad[0, 0] != 0
    assert torch.count_nonzero(prediction.grad) == 1


def test_stratum_balance_uses_observed_targets_and_caps_weights():
    y = np.full((100, 4), 5.0)
    y[0] = 2
    y[1, 0] = np.nan
    weights = balanced_weights(y)
    assert weights[0, 0] == 5
    assert weights[1, 0] == 0
    assert weights[2, 0] < 1


def test_preprocessing_ignores_query_labels_and_query_auxiliary():
    rng = np.random.default_rng(7)
    x = rng.uniform(size=(20, 8))
    d = rng.normal(size=(20, 4))
    features = MolecularFeatures(x, x, d, ("a", "b", "c", "d"))
    frame = pd.DataFrame({t: rng.uniform(2, 7, 20) for t in TARGETS})
    for t in TARGETS:
        frame[t + "_conf_low"] = frame[t] - 0.1
        frame[t + "_conf_high"] = frame[t] + 0.1
    auxiliary = rng.normal(size=(20, 4))
    fit = np.arange(15)
    query = np.arange(15, 20)
    first = prepare_neural_data(frame, auxiliary, features, features, fit, query)
    changed = frame.copy()
    changed.loc[query, list(TARGETS)] = 999
    auxiliary[query] = 999
    second = prepare_neural_data(changed, auxiliary, features, features, fit, query)
    np.testing.assert_allclose(first.target_mean, second.target_mean)
    np.testing.assert_allclose(first.auxiliary_mean, second.auxiliary_mean)
    torch.testing.assert_close(first.x, second.x)
    torch.testing.assert_close(first.truth, second.truth)
