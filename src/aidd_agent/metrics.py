"""Validated point-estimate wrapper around the unmodified official ST-RAE.

@author cylovelife
"""

import numpy as np
from numpy.typing import NDArray

from aidd_agent.vendor.openadmet.custom_scoring_functions import rae_soft_threshold_absolute_error


def score_endpoint(
    truth: NDArray[np.float64],
    prediction: NDArray[np.float64],
    lower: NDArray[np.float64],
    upper: NDArray[np.float64],
) -> dict[str, float]:
    arrays = (truth, prediction, lower, upper)
    if any(a.ndim != 1 or a.shape != truth.shape for a in arrays) or truth.size < 2:
        raise ValueError("Metric arrays must have the same non-empty one-dimensional shape")
    if not all(np.isfinite(a).all() for a in arrays):
        raise ValueError("Metric inputs must be finite")
    if ((lower > truth) | (truth > upper)).any():
        raise ValueError("Invalid credible bounds")
    mean = float(np.mean(truth))
    denominator = np.maximum(mean - upper, 0).sum() + np.maximum(lower - mean, 0).sum()
    if denominator <= 0:
        raise ValueError("ST-RAE denominator is zero; validation cannot rank models")
    result = float(
        rae_soft_threshold_absolute_error(truth, prediction, y_true_lower=lower, y_true_upper=upper)
    )
    return {"st_rae": result, "mae": float(np.abs(truth - prediction).mean())}
