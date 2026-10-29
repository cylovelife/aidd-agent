"""Matched CPU neural controls with masked assay losses and nested early stopping.

@author cylovelife
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

import numpy as np
import pandas as pd
import torch
from numpy.typing import NDArray
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import StandardScaler
from torch import Tensor, nn
from torch.nn import functional as functional

from aidd_agent.contracts import TARGETS
from aidd_agent.features import MolecularFeatures
from aidd_agent.metrics import score_endpoint
from aidd_agent.transfer_models import ExclusionTrace, fit_transfer_candidates

NEURAL_CANDIDATES = ("baseline", "direct_mlp", "joint_mlp")
LOGGER = logging.getLogger(__name__)


class NeuralTrace(ExclusionTrace):
    candidate: str
    seed: int
    best_epoch: int


@dataclass(frozen=True)
class NeuralData:
    x: Tensor
    query: Tensor
    truth: Tensor
    lower: Tensor
    upper: Tensor
    weights: Tensor
    auxiliary: Tensor
    target_mean: NDArray
    target_std: NDArray
    auxiliary_mean: NDArray
    auxiliary_std: NDArray


class AssayNetwork(nn.Module):
    def __init__(self, inputs: int, joint: bool) -> None:
        super().__init__()
        self.joint = joint
        self.layers = nn.Sequential(
            nn.Linear(inputs, 128),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 8 if joint else 4),
        )
        final = cast(nn.Linear, self.layers[-1])
        nn.init.zeros_(final.bias)

    def forward(self, x: Tensor) -> Tensor:
        return cast(Tensor, self.layers(x))


def balanced_weights(values: NDArray) -> NDArray[np.float32]:
    weights = np.zeros_like(values, dtype=np.float32)
    for column in range(values.shape[1]):
        measured = np.isfinite(values[:, column])
        low, high = measured & (values[:, column] < 4), measured & (values[:, column] >= 4)
        if low.any() and high.any():
            weights[low, column] = min(5, 0.5 * measured.sum() / low.sum())
            weights[high, column] = min(5, 0.5 * measured.sum() / high.sum())
        else:
            weights[measured, column] = 1
    return weights


def masked_potency_loss(
    prediction: Tensor,
    truth: Tensor,
    lower: Tensor,
    upper: Tensor,
    weights: Tensor,
) -> Tensor:
    terms = []
    for column in range(4):
        measured = torch.isfinite(truth[:, column])
        if not bool(measured.any()):
            continue
        p, y = prediction[measured, column], truth[measured, column]
        lo, hi = lower[measured, column], upper[measured, column]
        w = weights[measured, column]
        if not bool(torch.isfinite(lo).all() & torch.isfinite(hi).all()):
            raise ValueError("Measured neural labels need finite interval bounds")
        point = functional.smooth_l1_loss(p, y, beta=0.5, reduction="none")
        distance = torch.relu(lo - p) + torch.relu(p - hi)
        interval = functional.smooth_l1_loss(
            distance, torch.zeros_like(distance), beta=0.5, reduction="none"
        )
        terms.append((w * (point + interval) * 0.5).sum() / w.sum())
    return torch.stack(terms).mean() if terms else prediction.sum() * 0


def masked_screen_loss(prediction: Tensor, auxiliary: Tensor) -> Tensor:
    terms = []
    for column in range(4):
        measured = torch.isfinite(auxiliary[:, column])
        if bool(measured.any()):
            terms.append(
                functional.smooth_l1_loss(
                    prediction[measured, column], auxiliary[measured, column], beta=0.5
                )
            )
    return torch.stack(terms).mean() if terms else prediction.sum() * 0


def prepare_neural_data(
    frame: pd.DataFrame,
    auxiliary: NDArray,
    features: MolecularFeatures,
    other: MolecularFeatures,
    fit: NDArray[np.int64],
    query: NDArray[np.int64],
) -> NeuralData:
    descriptor_scaler = StandardScaler().fit(features.descriptors[fit])
    x = np.hstack(
        (
            features.counts[fit],
            np.clip(descriptor_scaler.transform(features.descriptors[fit]), -5, 5),
        )
    )
    q = np.hstack(
        (other.counts[query], np.clip(descriptor_scaler.transform(other.descriptors[query]), -5, 5))
    )
    y = frame.loc[fit, list(TARGETS)].to_numpy(float)
    mean, std = np.nanmean(y, axis=0), np.nanstd(y, axis=0)
    amean, astd = np.nanmean(auxiliary[fit], axis=0), np.nanstd(auxiliary[fit], axis=0)
    if (
        not np.isfinite([mean, std, amean, astd]).all()
        or (std <= 1e-6).any()
        or (astd <= 1e-6).any()
    ):
        raise ValueError("Neural fit partition lacks variable measured tasks")
    low = frame.loc[fit, [t + "_conf_low" for t in TARGETS]].to_numpy(float)
    high = frame.loc[fit, [t + "_conf_high" for t in TARGETS]].to_numpy(float)

    def tensor(values: NDArray) -> Tensor:
        return torch.from_numpy(np.ascontiguousarray(values, dtype=np.float32))

    return NeuralData(
        tensor(x),
        tensor(q),
        tensor((y - mean) / std),
        tensor((low - mean) / std),
        tensor((high - mean) / std),
        tensor(balanced_weights(y)),
        tensor((auxiliary[fit] - amean) / astd),
        mean,
        std,
        amean,
        astd,
    )


def predict_neural(model: AssayNetwork, data: NeuralData) -> tuple[NDArray, NDArray | None]:
    model.eval()
    with torch.no_grad():
        prediction = model(data.query).numpy().astype(float)
    potency = prediction[:, :4] * data.target_std + data.target_mean
    screen = prediction[:, 4:] * data.auxiliary_std + data.auxiliary_mean if model.joint else None
    return potency, screen


def train_network(
    data: NeuralData,
    joint: bool,
    seed: int,
    epochs: int,
    deadline: float,
    validation: tuple[pd.DataFrame, NDArray[np.int64]] | None = None,
) -> tuple[AssayNetwork, int]:
    torch.manual_seed(seed)
    model = AssayNetwork(data.x.shape[1], joint)
    torch.manual_seed(seed + 1000)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.0001)
    rng = np.random.default_rng(seed)
    best_score, best_epoch, stale = float("inf"), 10, 0
    for epoch in range(1, epochs + 1):
        if time.monotonic() > deadline:
            raise RuntimeError("Neural stage exhausted frozen wall-time budget")
        model.train()
        for batch in np.array_split(
            rng.permutation(len(data.x)), max(1, int(np.ceil(len(data.x) / 256)))
        ):
            prediction = model(data.x[batch])
            loss = masked_potency_loss(
                prediction[:, :4],
                data.truth[batch],
                data.lower[batch],
                data.upper[batch],
                data.weights[batch],
            )
            if joint:
                loss = loss + 0.5 * masked_screen_loss(prediction[:, 4:], data.auxiliary[batch])
            if not bool(torch.isfinite(loss)):
                raise FloatingPointError("Non-finite neural training loss")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=5)
            optimizer.step()
        if validation is not None and epoch % 10 == 0:
            frame, valid = validation
            prediction, _ = predict_neural(model, data)
            scores = []
            for column, target in enumerate(TARGETS):
                measured = frame.loc[valid, target].notna().to_numpy()
                rows = valid[measured]
                if len(rows) < 20:
                    raise ValueError("Inner stopping partition lacks measured endpoint labels")
                scores.append(
                    score_endpoint(
                        frame.loc[rows, target].to_numpy(float),
                        prediction[measured, column],
                        frame.loc[rows, target + "_conf_low"].to_numpy(float),
                        frame.loc[rows, target + "_conf_high"].to_numpy(float),
                    )["st_rae"]
                )
            score = float(np.mean(scores))
            if score < best_score:
                best_score, best_epoch, stale = score, epoch, 0
            else:
                stale += 1
            if epoch >= 30 and stale >= 3:
                break
    return model, best_epoch if validation is not None else epochs


def fit_neural_candidates(
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
    *,
    deadline: float,
    progress: Callable[[dict[str, object]], None] | None = None,
) -> tuple[dict[str, dict[str, NDArray]], NDArray | None, list[ExclusionTrace]]:
    requested = frozenset(NEURAL_CANDIDATES) if requested is None else requested
    if not requested or not requested.issubset(NEURAL_CANDIDATES):
        raise ValueError("Unknown neural candidate request")
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    result: dict[str, dict[str, NDArray]] = {}
    trace: list[ExclusionTrace] = []
    screen = None
    if "baseline" in requested:
        result, screen, trace = fit_transfer_candidates(
            frame,
            auxiliary,
            groups,
            features,
            other,
            kernels,
            cross,
            fit,
            query,
            requested=frozenset({"baseline"}),
        )
    inner_fit, inner_valid = next(
        GroupShuffleSplit(n_splits=1, test_size=0.15, random_state=101).split(
            fit, groups=groups[fit]
        )
    )
    train, valid = fit[inner_fit], fit[inner_valid]
    if set(groups[train]) & set(groups[valid]):
        raise ValueError("Neural early-stop groups overlap")
    inner = prepare_neural_data(frame, auxiliary, features, features, train, valid)
    full = prepare_neural_data(frame, auxiliary, features, other, fit, query)
    for name in ("direct_mlp", "joint_mlp"):
        if name not in requested:
            continue
        potency_members, screen_members = [], []
        for seed in (17, 29):
            _, best_epoch = train_network(
                inner, name == "joint_mlp", seed, 200, deadline, validation=(frame, valid)
            )
            model, _ = train_network(full, name == "joint_mlp", seed, best_epoch, deadline)
            prediction, aux_prediction = predict_neural(model, full)
            potency_members.append(prediction)
            if aux_prediction is not None:
                screen_members.append(aux_prediction)
            for label, allowed, heldout in (
                ("inner", train, valid),
                ("refit", fit, np.array([], dtype=int)),
            ):
                observed = (
                    allowed[np.isfinite(auxiliary[allowed]).all(axis=1)]
                    if name == "joint_mlp"
                    else np.array([], dtype=int)
                )
                record: NeuralTrace = {
                    "fold": label,
                    "aux_fit": observed.tolist(),
                    "valid": heldout.tolist(),
                    "candidate": name,
                    "seed": seed,
                    "best_epoch": best_epoch,
                }
                trace.append(record)
            if progress is not None:
                progress(
                    {
                        "candidate": name,
                        "seed": seed,
                        "best_epoch": best_epoch,
                        "fit_rows": len(fit),
                    }
                )
            LOGGER.info(
                "Neural candidate=%s seed=%s best_epoch=%s completed", name, seed, best_epoch
            )
        mean = np.mean(potency_members, axis=0)
        result[name] = {target: mean[:, column] for column, target in enumerate(TARGETS)}
        if screen_members:
            screen = np.mean(screen_members, axis=0)
    if not all(np.isfinite(p).all() for candidate in result.values() for p in candidate.values()):
        raise ValueError("Neural predictions must be finite")
    return result, screen, trace
