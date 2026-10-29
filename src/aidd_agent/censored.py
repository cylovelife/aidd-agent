"""Convex RKHS interval regression with explicit one-sided bounds and assay offsets.

@author cylovelife
"""

import time
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.linalg import solve_triangular
from scipy.optimize import minimize


@dataclass(frozen=True)
class IntervalModel:
    alpha: NDArray[np.float64]
    intercept: float
    source_offsets: NDArray[np.float64]
    converged: bool
    iterations: int
    objective: float
    gradient_inf: float

    def predict(self, cross_kernel: NDArray) -> NDArray[np.float64]:
        return np.asarray(cross_kernel @ self.alpha + self.intercept)


def interval_huber(
    prediction: NDArray,
    lower: NDArray,
    upper: NDArray,
    delta: float = 0.1,
) -> tuple[NDArray, NDArray]:
    if (
        prediction.ndim != 1
        or prediction.shape != lower.shape
        or lower.shape != upper.shape
        or not np.isfinite(prediction).all()
        or np.isnan(lower).any()
        or np.isnan(upper).any()
        or (lower > upper).any()
        or np.isposinf(lower).any()
        or np.isneginf(upper).any()
        or not np.isfinite(delta)
        or delta <= 0
    ):
        raise ValueError("Invalid prediction/interval bounds")
    residual = prediction - np.clip(prediction, lower, upper)
    absolute = np.abs(residual)
    return (
        np.where(absolute <= delta, 0.5 * residual**2 / delta, absolute - 0.5 * delta),
        np.clip(residual / delta, -1.0, 1.0),
    )


def interval_objective(
    parameters: NDArray,
    basis: NDArray,
    lower: NDArray,
    upper: NDArray,
    weights: NDArray,
    sources: NDArray,
    source_n: int,
) -> tuple[float, NDArray]:
    n = len(lower)
    w = parameters[:n]
    intercept = parameters[n]
    offsets = parameters[n + 1 :]
    auxiliary = sources >= 0
    prediction = basis @ w + intercept
    prediction[auxiliary] += offsets[sources[auxiliary]]
    losses, derivative = interval_huber(prediction, lower, upper)
    derivative = derivative * weights
    value = 0.5 * (w @ w + offsets @ offsets) + weights @ losses
    offset_gradient = np.bincount(
        sources[auxiliary], weights=derivative[auxiliary], minlength=source_n
    )
    gradient = np.concatenate(
        [w + basis.T @ derivative, [derivative.sum()], offsets + offset_gradient]
    )
    return float(value), gradient


def fit_interval_model(
    kernel: NDArray,
    lower: NDArray,
    upper: NDArray,
    weights: NDArray,
    sources: NDArray,
    deadline: float | None = None,
) -> IntervalModel:
    n = len(lower)
    if (
        n < 2
        or kernel.shape != (n, n)
        or weights.shape != (n,)
        or sources.shape != (n,)
        or not np.isfinite(kernel).all()
        or not np.isfinite(weights).all()
        or (weights <= 0).any()
        or not np.allclose(kernel, kernel.T, atol=1e-10, rtol=0)
        or not np.issubdtype(sources.dtype, np.integer)
        or (sources < -1).any()
    ):
        raise ValueError("Invalid interval model arrays")
    interval_huber(np.zeros(n), lower, upper)
    if (np.isneginf(lower) & np.isposinf(upper)).any():
        raise ValueError("Observation has no finite bound")
    official = sources < 0
    if (
        not official.any()
        or not np.isfinite(lower[official]).all()
        or not np.isfinite(upper[official]).all()
    ):
        raise ValueError("Official interval anchors must have finite bounds")
    source_n = int(sources.max()) + 1 if (sources >= 0).any() else 0
    if source_n and set(sources[sources >= 0]) != set(range(source_n)):
        raise ValueError("Source indices must be contiguous")
    basis = np.linalg.cholesky(kernel + np.eye(n) * 1e-8)
    parameters = np.zeros(n + 1 + source_n)
    parameters[n] = np.median((lower[official] + upper[official]) / 2)

    def objective(p: NDArray) -> tuple[float, NDArray]:
        if deadline is not None and time.monotonic() > deadline:
            raise RuntimeError("Censored experiment time budget exceeded")
        return interval_objective(p, basis, lower, upper, weights, sources, source_n)

    result = minimize(
        objective,
        parameters,
        method="L-BFGS-B",
        jac=True,
        options=dict(maxiter=2000, ftol=1e-10, gtol=1e-5),
    )
    if not result.success or not np.isfinite(result.x).all():
        raise RuntimeError(f"Interval optimizer did not converge: {result.message}")
    alpha = solve_triangular(basis.T, result.x[:n], lower=False)
    return IntervalModel(
        alpha,
        float(result.x[n]),
        np.asarray(result.x[n + 1 :]),
        bool(result.success),
        int(result.nit),
        float(result.fun),
        float(np.abs(result.jac).max()),
    )
