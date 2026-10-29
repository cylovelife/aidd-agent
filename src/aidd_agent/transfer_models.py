"""Fold-safe auxiliary screening predictions and bounded transfer candidates.

@author cylovelife
"""

from typing import TypedDict

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.cross_decomposition import PLSRegression
from sklearn.kernel_ridge import KernelRidge
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from aidd_agent.contracts import TARGETS
from aidd_agent.features import MolecularFeatures
from aidd_agent.optimization import BLEND, predict_candidate

TRANSFER_CANDIDATES = ("baseline", "screen_linear", "screen_residual", "screen_blend", "screen_pls")
BASELINE = dict(zip(TARGETS, ("hist_descriptors", "blend", "svr_bits_1", "blend"), strict=True))


class ExclusionTrace(TypedDict):
    fold: int | str
    aux_fit: list[int]
    valid: list[int]


def predict_screen(
    kernel: NDArray,
    cross: NDArray,
    auxiliary: NDArray,
    allowed: NDArray[np.int64],
    query: NDArray[np.int64],
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    rows = allowed[np.isfinite(auxiliary[allowed]).all(axis=1)]
    if len(rows) < 3:
        raise ValueError("Too few auxiliary observations in the permitted fit partition")
    center = auxiliary[rows].mean(axis=0)
    model = KernelRidge(alpha=1, kernel="precomputed")
    model.fit(kernel[np.ix_(rows, rows)], auxiliary[rows] - center)
    return np.asarray(model.predict(cross[np.ix_(query, rows)]) + center), rows


def crossfit_screen(
    kernel: NDArray,
    cross: NDArray,
    auxiliary: NDArray,
    groups: NDArray,
    fit: NDArray[np.int64],
    query: NDArray[np.int64],
) -> tuple[NDArray[np.float64], NDArray[np.float64], list[ExclusionTrace]]:
    if len(set(groups[fit])) < 3:
        raise ValueError("At least three fit groups are required for auxiliary crossfitting")
    oof = np.full((len(fit), 4), np.nan)
    trace: list[ExclusionTrace] = []
    for fold, (inner_fit, inner_valid) in enumerate(
        GroupKFold(n_splits=3).split(fit, groups=groups[fit])
    ):
        train, valid = fit[inner_fit], fit[inner_valid]
        if set(groups[train]) & set(groups[valid]):
            raise ValueError("Auxiliary inner groups overlap")
        oof[inner_valid], rows = predict_screen(kernel, kernel, auxiliary, train, valid)
        trace.append({"fold": fold, "aux_fit": rows.tolist(), "valid": valid.tolist()})
    prediction, rows = predict_screen(kernel, cross, auxiliary, fit, query)
    trace.append({"fold": "outer_fit", "aux_fit": rows.tolist(), "valid": []})
    if not np.isfinite(oof).all():
        raise ValueError("Incomplete auxiliary out-of-fold coverage")
    return oof, prediction, trace


def fit_transfer_candidates(
    frame: pd.DataFrame,
    auxiliary: NDArray,
    groups: NDArray,
    features: MolecularFeatures,
    other: MolecularFeatures,
    kernels: dict[str, NDArray],
    cross: dict[str, NDArray],
    fit: NDArray[np.int64],
    query: NDArray[np.int64],
    requested: frozenset[str] | None = None,
) -> tuple[dict[str, dict[str, NDArray]], NDArray, list[ExclusionTrace]]:
    requested = frozenset(TRANSFER_CANDIDATES) if requested is None else requested
    if not requested or not requested.issubset(TRANSFER_CANDIDATES):
        raise ValueError("Unknown or empty transfer candidate request")
    predictions: dict[str, dict[str, NDArray]] = {
        name: {} for name in TRANSFER_CANDIDATES if name in requested
    }
    oof, screen, trace = crossfit_screen(
        kernels["counts"], cross["counts"], auxiliary, groups, fit, query
    )
    latent_fit, latent_query = None, None
    if "screen_pls" in requested:
        aux_fit = fit[np.isfinite(auxiliary[fit]).all(axis=1)]
        scaler = StandardScaler().fit(features.hybrid[aux_fit])
        target_scaler = StandardScaler().fit(auxiliary[aux_fit])
        pls = PLSRegression(n_components=16, scale=False, max_iter=100, tol=1e-6)
        pls.fit(
            scaler.transform(features.hybrid[aux_fit]), target_scaler.transform(auxiliary[aux_fit])
        )
        latent_fit = pls.transform(scaler.transform(features.hybrid[fit]))
        latent_query = pls.transform(scaler.transform(other.hybrid[query]))
    for target in TARGETS:
        positions = np.flatnonzero(frame.loc[fit, target].notna().to_numpy())
        rows = fit[positions]
        if len(rows) < 50:
            raise ValueError(f"Too few measured fit labels: {target}")
        y = frame.loc[rows, target].to_numpy(float)
        base = None
        if requested & {"baseline", "screen_blend"}:
            name = BASELINE[target]
            members = BLEND if name == "blend" else {name: 1.0}
            base = np.asarray(
                sum(
                    weight
                    * predict_candidate(
                        member,
                        features,
                        rows,
                        other,
                        query,
                        kernels,
                        cross,
                        y,
                        frame.loc[rows, target + "_conf_low"].to_numpy(float),
                        frame.loc[rows, target + "_conf_high"].to_numpy(float),
                    )
                    for member, weight in members.items()
                )
            )
            if "baseline" in requested:
                predictions["baseline"][target] = base
        if requested & {"screen_linear", "screen_residual", "screen_blend"}:
            linear = make_pipeline(StandardScaler(), Ridge(alpha=10))
            linear.fit(oof[positions], y)
            pred = np.asarray(linear.predict(screen))
            if "screen_linear" in requested:
                predictions["screen_linear"][target] = pred
            if requested & {"screen_residual", "screen_blend"}:
                residual = y - linear.predict(oof[positions])
                center = float(residual.mean())
                krr = KernelRidge(alpha=1, kernel="precomputed")
                krr.fit(kernels["counts"][np.ix_(rows, rows)], residual - center)
                corrected = pred + krr.predict(cross["counts"][np.ix_(query, rows)]) + center
                if "screen_residual" in requested:
                    predictions["screen_residual"][target] = np.asarray(corrected)
                if "screen_blend" in requested:
                    assert base is not None
                    predictions["screen_blend"][target] = 0.5 * base + 0.5 * corrected
        if "screen_pls" in requested:
            assert latent_fit is not None and latent_query is not None
            head = make_pipeline(StandardScaler(), Ridge(alpha=10))
            head.fit(latent_fit[positions], y)
            predictions["screen_pls"][target] = np.asarray(head.predict(latent_query))
    if not all(
        np.isfinite(pred).all() for model in predictions.values() for pred in model.values()
    ):
        raise ValueError("Non-finite transfer predictions")
    return predictions, screen, trace
