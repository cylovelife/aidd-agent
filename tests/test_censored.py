"""One-sided observations remain inequalities and source rows cannot leak into validation.

@author cylovelife
"""

import numpy as np
import pytest
from scipy.optimize import check_grad

from aidd_agent.censored import fit_interval_model, interval_huber, interval_objective


def test_one_sided_loss_does_not_impute_a_target_at_the_bound():
    low = np.array([-np.inf, -np.inf, 2.0, 2.0])
    high = np.array([4.0, 4.0, np.inf, np.inf])
    loss, gradient = interval_huber(np.array([1.0, 5.0, 5.0, 1.0]), low, high)
    assert loss[0] == 0 and gradient[0] == 0
    assert loss[2] == 0 and gradient[2] == 0
    assert gradient[1] > 0 and gradient[3] < 0
    with pytest.raises(ValueError):
        interval_huber(np.zeros(1), np.array([np.nan]), np.ones(1))
    with pytest.raises(ValueError):
        interval_huber(np.zeros(1), np.array([2.0]), np.ones(1))


def test_censored_source_objective_gradient_matches_finite_differences():
    rng = np.random.default_rng(31)
    x = rng.normal(size=(6, 4))
    kernel = x @ x.T + np.eye(6) * 0.1
    basis = np.linalg.cholesky(kernel)
    lower = np.array([1.0, 2.0, 3.0, -np.inf, -np.inf, -np.inf])
    upper = np.array([1.3, 2.3, 3.3, 1.0, 2.0, 3.0])
    sources = np.array([-1, -1, -1, 0, 0, 0])
    weights = np.array([1.0, 1.0, 1.0, 0.25, 0.25, 0.25])
    params = rng.normal(size=8)

    def objective(p):
        return interval_objective(p, basis, lower, upper, weights, sources, 1)

    assert check_grad(lambda p: objective(p)[0], lambda p: objective(p)[1], params) < 1e-5


def test_real_fit_handles_exact_and_censored_observations_with_source_offset():
    x = np.linspace(0, 1, 35)[:, None]
    kernel = np.exp(-((x - x.T) ** 2) / 0.08)
    truth = 3 + 2 * x[:, 0]
    lower = truth.copy()
    upper = truth.copy()
    lower[-5:] = -np.inf
    upper[-5:] = 5.0
    sources = np.full(35, -1)
    sources[-5:] = 0
    model = fit_interval_model(kernel, lower, upper, np.ones(35), sources)
    pred = model.predict(kernel)
    assert np.isfinite(pred).all()
    assert np.abs(pred[:30] - truth[:30]).mean() < 0.15
    assert model.converged
    assert len(model.source_offsets) == 1


def test_missing_or_unbounded_observations_cannot_silently_enter_training():
    with pytest.raises(ValueError, match="bound"):
        fit_interval_model(
            np.eye(3), np.full(3, -np.inf), np.full(3, np.inf), np.ones(3), np.full(3, -1)
        )
