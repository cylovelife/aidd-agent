"""Fold-safe regularization and bounded readout input contracts.

@author cylovelife
"""

import numpy as np
import pytest

from aidd_agent.readout import fit_head


def test_clipped_head_bounds_extrapolation_without_changing_fit_scaler():
    x = np.array([[0.0, 0.0], [1.0, 0.01], [2.0, 0.0], [3.0, 0.01]])
    y = np.array([4.0, 5.0, 6.0, 7.0])
    query = np.array([[1.0, 1000.0]])
    plain, _, _ = fit_head(x, y, query, "replay")
    clipped, _, stats = fit_head(x, y, query, "clip5_ridge10")
    assert abs(clipped[0] - y.mean()) < abs(plain[0] - y.mean())
    assert stats["query_max_abs_input"] <= 5
    query2 = np.vstack([query, [1e9, 1e9]])
    repeated, _, _ = fit_head(x, y, query2, "clip5_ridge10")
    np.testing.assert_allclose(clipped, repeated[:1])


def test_regularization_and_input_validation():
    x = np.arange(24, dtype=float).reshape(8, 3)
    y = np.arange(8, dtype=float)
    _, _, original = fit_head(x, y, x, "replay")
    _, _, regularized = fit_head(x, y, x, "ridge1000")
    assert regularized["coef_l2"] < original["coef_l2"]
    with pytest.raises(ValueError):
        fit_head(x, y, x, "unknown")
    with pytest.raises(ValueError):
        fit_head(x, y * np.nan, x, "replay")
