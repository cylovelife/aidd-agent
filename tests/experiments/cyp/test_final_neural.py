"""Masked gradients and matched frozen/partial adaptation contracts.

@author cylovelife
"""

import time

import numpy as np
import pandas as pd
import pytest

from aidd_agent.contracts import TARGETS

torch = pytest.importorskip("torch")

from aidd_agent.final_neural import PotencyHead, fit_candidate, masked_loss  # noqa: E402


def test_missing_targets_have_zero_gradient():
    p = torch.tensor([[0.0, 1.0, 2.0, 3.0]], requires_grad=True)
    y = torch.tensor([[1.0, float("nan"), 2.0, float("nan")]])
    loss = masked_loss(p, y, y - 0.1, y + 0.1)
    loss.backward()
    assert p.grad[0, 1] == 0 and p.grad[0, 3] == 0
    assert p.grad[0, 0] != 0
    assert torch.isfinite(loss)


def test_layernorm_is_per_molecule_not_fit_on_query_population():
    torch.manual_seed(17)
    head = PotencyHead().eval()
    x = torch.rand(2, 2048)
    with torch.no_grad():
        first = head(x)
        other = head(torch.cat((x, torch.ones(1, 2048) * 1e6)))
    torch.testing.assert_close(first, other[:2])
    assert first.shape == (2, 4)


def test_frozen_training_does_not_use_query_labels_or_intervals():
    x = np.random.default_rng(8).normal(size=(68, 2048))
    frame = pd.DataFrame({t: np.linspace(2, 7, 68) for t in TARGETS})
    for t in TARGETS:
        frame[t + "_conf_low"] = frame[t] - 0.2
        frame[t + "_conf_high"] = frame[t] + 0.2
    fit, query = np.arange(64), np.arange(64, 68)
    a, _, _ = fit_candidate(frame, x, fit, query, False, 1, time.monotonic() + 30)
    changed = frame.copy()
    changed.loc[query, :] = -1e6
    b, _, _ = fit_candidate(changed, x, fit, query, False, 1, time.monotonic() + 30)
    np.testing.assert_array_equal(a, b)


def test_measured_target_with_missing_interval_fails_explicitly():
    p = torch.zeros(1, 4, requires_grad=True)
    y = torch.ones(1, 4)
    with pytest.raises(ValueError, match="finite intervals"):
        masked_loss(p, y, y * float("nan"), y)
