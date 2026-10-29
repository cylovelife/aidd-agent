"""Frozen selection, analogue stress tests and one-use confirmation boundaries.

@author cylovelife
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypedDict

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from aidd_agent.chemistry import split_groups
from aidd_agent.contracts import TARGETS
from aidd_agent.metrics import score_endpoint

TWO_D6 = "CYP2D6_pIC50_direct_inhibition"


class EndpointMetrics(TypedDict):
    st_rae: float
    mae: float
    measured_n: int
    low_n: int
    high_n: int
    low_distance: float | None
    high_distance: float | None
    low_bias: float | None
    high_bias: float | None


class ScoreRecord(EndpointMetrics):
    endpoint: str
    model: str
    split: str


@dataclass(frozen=True)
class TransferSplit:
    name: str
    fit: NDArray[np.int64]
    valid: NDArray[np.int64]
    scaffold_disjoint: bool


def freeze_confirmation(
    frame: pd.DataFrame,
    groups: NDArray[np.str_],
) -> tuple[NDArray[np.int64], NDArray[np.int64], int]:
    for seed in range(31415, 31425):
        fit, valid = split_groups(groups, seed)
        if int(frame.loc[valid, TWO_D6].lt(4).sum()) < 20:
            continue
        if all(int(frame.loc[valid, t].notna().sum()) >= 100 for t in TARGETS):
            return fit, valid, seed
    raise ValueError("Frozen confirmation seed budget has insufficient measured labels/groups")


def development_splits(
    frame: pd.DataFrame,
    groups: NDArray[np.str_],
    pool: NDArray[np.int64],
    kernel: NDArray,
) -> list[TransferSplit]:
    result = []
    for seed in (73, 74):
        fit, valid = split_groups(groups[pool], seed)
        result.append(TransferSplit(f"scaffold_{seed}", pool[fit], pool[valid], True))
    anchors: list[int] = []
    for t in (TARGETS[0], TARGETS[1], TARGETS[3]):
        ordered = frame.loc[pool, t].dropna().sort_values(ascending=False, kind="stable")
        anchors.extend(int(i) for i in ordered.index[:25])
    anchors = list(dict.fromkeys(anchors))
    anchor_set = set(anchors)
    valid_set: set[int] = set()
    for anchor in anchors:
        ordered_indices = pool[np.argsort(-kernel[anchor, pool], kind="stable")]
        count = 0
        for index in ordered_indices:
            item = int(index)
            if item in anchor_set or item in valid_set:
                continue
            valid_set.add(item)
            count += 1
            if count == 10:
                break
    valid = np.array(sorted(valid_set), dtype=np.int64)
    fit = np.array([i for i in pool if i not in valid_set], dtype=np.int64)
    if len(valid) < 100 or not anchor_set.issubset(set(fit)):
        raise ValueError("Analogue expansion split lacks sufficient neighbors/retained anchors")
    result.append(TransferSplit("analog_expansion", fit, valid, False))
    return result


def endpoint_statistics(
    truth: NDArray,
    prediction: NDArray,
    lower: NDArray,
    upper: NDArray,
) -> EndpointMetrics:
    scored = score_endpoint(truth, prediction, lower, upper)
    distance = np.maximum(lower - prediction, 0) + np.maximum(prediction - upper, 0)
    low = truth < 4
    return {
        "st_rae": scored["st_rae"],
        "mae": scored["mae"],
        "measured_n": len(truth),
        "low_n": int(low.sum()),
        "high_n": int((~low).sum()),
        "low_distance": float(distance[low].mean()) if low.any() else None,
        "high_distance": float(distance[~low].mean()) if (~low).any() else None,
        "low_bias": float((prediction[low] - truth[low]).mean()) if low.any() else None,
        "high_bias": float((prediction[~low] - truth[~low]).mean()) if (~low).any() else None,
    }


def choose_transfer_models(records: list[ScoreRecord]) -> dict[str, str]:
    frame = pd.DataFrame(records)
    fields = ["st_rae", "low_distance", "high_distance"]
    means = frame.groupby(["endpoint", "model"])[fields].mean()
    selected = {}
    for target in frame.endpoint.unique():
        base = means.loc[(target, "baseline")]
        eligible = ["baseline"]
        for name in frame.model.unique():
            if name == "baseline":
                continue
            row = means.loc[(target, name)]
            low_factor = 0.9 if target == TWO_D6 else 1.05
            if (
                np.isfinite(row).all()
                and row.st_rae <= base.st_rae * 0.97
                and row.low_distance <= base.low_distance * low_factor
                and row.high_distance <= base.high_distance * 1.05
            ):
                eligible.append(name)
        selected[str(target)] = min(
            eligible, key=lambda n: float(np.asarray(means.loc[(target, n), "st_rae"]).item())
        )
    return selected


def confirmation_gate(
    baseline: Mapping[str, EndpointMetrics],
    candidate: Mapping[str, EndpointMetrics],
    bootstrap_upper: float,
) -> tuple[bool, list[str]]:
    reasons = []
    if set(baseline) != set(candidate):
        return False, ["inconsistent_endpoint_coverage"]
    if any(not np.isfinite(row["st_rae"]) for row in (*baseline.values(), *candidate.values())):
        return False, ["nonfinite_confirmation_score"]
    if np.mean([v["st_rae"] for v in candidate.values()]) > 0.95 * np.mean(
        [v["st_rae"] for v in baseline.values()]
    ):
        reasons.append("macro_gain_below_5_percent")
    for t, base in baseline.items():
        row = candidate[t]
        if row["measured_n"] < 100:
            reasons.append(f"insufficient_measured:{t}")
        if row["st_rae"] > base["st_rae"] * 1.05:
            reasons.append(f"endpoint_degradation:{t}")
    base, row = baseline[TWO_D6], candidate[TWO_D6]
    if row["low_n"] < 20:
        reasons.append("insufficient_2d6_low")
    if row["st_rae"] > base["st_rae"] * 0.95:
        reasons.append("2d6_gain_below_5_percent")
    new_low, old_low = row["low_distance"], base["low_distance"]
    if (
        new_low is None
        or old_low is None
        or not np.isfinite([new_low, old_low]).all()
        or new_low > old_low * 0.9
    ):
        reasons.append("2d6_low_gain_below_10_percent")
    new_high, old_high = row["high_distance"], base["high_distance"]
    if (
        new_high is None
        or old_high is None
        or not np.isfinite([new_high, old_high]).all()
        or new_high > old_high * 1.05
    ):
        reasons.append("2d6_high_degradation")
    if not np.isfinite(bootstrap_upper) or bootstrap_upper >= 0:
        reasons.append("bootstrap_does_not_establish_gain")
    return not reasons, reasons


def paired_bootstrap(
    frame: pd.DataFrame,
    groups: NDArray[np.str_],
    baseline: dict[str, NDArray],
    candidate: dict[str, NDArray],
    valid: NDArray[np.int64],
) -> dict[str, object]:
    unique, inverse = np.unique(groups[valid], return_inverse=True)
    rng = np.random.default_rng(20261029)
    arrays = []
    for target in TARGETS:
        measured = frame.loc[valid, target].notna().to_numpy()
        rows = valid[measured]
        arrays.append(
            (
                inverse[measured],
                frame.loc[rows, target].to_numpy(float),
                frame.loc[rows, target + "_conf_low"].to_numpy(float),
                frame.loc[rows, target + "_conf_high"].to_numpy(float),
                baseline[target][measured],
                candidate[target][measured],
            )
        )
    differences = []
    for _ in range(1000):
        weights = rng.multinomial(len(unique), np.full(len(unique), 1 / len(unique)))
        endpoint_differences = []
        for group, truth, lower, upper, old, new in arrays:
            w = weights[group]
            if w.sum() == 0:
                break
            mean = np.average(truth, weights=w)
            denominator = np.sum(w * (np.maximum(lower - mean, 0) + np.maximum(mean - upper, 0)))
            if denominator <= 0:
                break
            new_error = np.maximum(lower - new, 0) + np.maximum(new - upper, 0)
            old_error = np.maximum(lower - old, 0) + np.maximum(old - upper, 0)
            endpoint_differences.append(float(np.sum(w * (new_error - old_error)) / denominator))
        if len(endpoint_differences) == len(TARGETS):
            differences.append(float(np.mean(endpoint_differences)))
    if len(differences) < 950:
        raise ValueError("Insufficient valid bootstrap resamples")
    return {
        "resamples": len(differences),
        "rng_seed": 20261029,
        "macro_difference_percentile_95": np.quantile(differences, [0.025, 0.975]).tolist(),
        "scope": "This-round confirmation only, not a proof of blind-distribution equivalence",
    }
