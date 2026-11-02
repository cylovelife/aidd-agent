"""Last bounded CYP experiment: matched frozen and final-projection tuning.

@author cylovelife
"""

import copy
import resource
import time
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import torch
from numpy.typing import NDArray
from sklearn.model_selection import GroupShuffleSplit
from threadpoolctl import threadpool_limits
from torch import Tensor, nn
from torch.nn import functional as F

from aidd_agent.baseline import write_json
from aidd_agent.contracts import TARGETS
from aidd_agent.features import tanimoto_kernel
from aidd_agent.metrics import score_endpoint
from aidd_agent.optimization import check_budget
from aidd_agent.readout import ROUND7, read_context
from aidd_agent.representation import fingerprint_features, model_predictions, select_development
from aidd_agent.sources import sha256_file
from aidd_agent.transfer import evaluate_predictions
from aidd_agent.transfer_validation import TransferSplit, confirmation_gate, paired_bootstrap

WEIGHTS = Path("state/sources/round7/chemeleon_mp.pt")
CHECKPOINT_SHA = "c376624d3407204e780a0ed13a9ac097cc9bb1c13ef89cdbc633c1715c183651"


def load_encoder(tune: bool) -> nn.Module:
    from chemprop import nn as cpnn

    if sha256_file(WEIGHTS) != CHECKPOINT_SHA:
        raise ValueError("Pretrained weights changed")
    checkpoint = torch.load(WEIGHTS, weights_only=True, map_location="cpu")
    encoder = cpnn.BondMessagePassing(**checkpoint["hyper_parameters"])
    encoder.load_state_dict(checkpoint["state_dict"], strict=True)
    encoder.requires_grad_(False)
    if tune:
        encoder.W_o.requires_grad_(True)
    return encoder


class PotencyHead(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.LayerNorm(2048, elementwise_affine=False),
            nn.Linear(2048, 64),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(64, 4),
        )

    def forward(self, values: Tensor) -> Tensor:
        return self.layers(values)


def masked_loss(pred: Tensor, truth: Tensor, lower: Tensor, upper: Tensor) -> Tensor:
    losses = []
    for column in range(4):
        keep = torch.isfinite(truth[:, column])
        if bool(keep.any()):
            p, y = pred[keep, column], truth[keep, column]
            lo, hi = lower[keep, column], upper[keep, column]
            if not bool(torch.isfinite(lo).all() & torch.isfinite(hi).all()):
                raise ValueError("Measured labels require finite intervals")
            outside = torch.relu(lo - p) + torch.relu(p - hi)
            losses.append(
                0.5
                * (
                    F.smooth_l1_loss(p, y, beta=0.5)
                    + F.smooth_l1_loss(outside, torch.zeros_like(outside), beta=0.5)
                )
            )
    return torch.stack(losses).mean() if losses else pred.sum() * 0


def graph_batches(smiles: list[str], batch_size: int = 32) -> list[Any]:
    from chemprop import data, featurizers

    dataset = data.MoleculeDataset(
        [data.MoleculeDatapoint.from_smi(s) for s in smiles],
        featurizers.SimpleMoleculeMolGraphFeaturizer(),
    )
    return list(data.build_dataloader(dataset, batch_size=batch_size, num_workers=0, shuffle=False))


def graph_embedding(encoder: nn.Module, batch: Any) -> Tensor:
    from chemprop import nn as cpnn

    return cpnn.MeanAggregation()(encoder(batch.bmg), batch.bmg.batch)


def resource_probe(output: Path) -> None:
    if output.exists():
        raise ValueError("Fresh probe output required")
    data, _, assignments, _ = read_context()
    allowed = assignments.loc[assignments.partition.eq("fit"), "index"].unique()[:128]
    smiles = data.molecules.loc[allowed, "SMILES"].tolist()
    torch.set_num_threads(2)
    torch.manual_seed(17)
    batches = graph_batches(smiles)
    encoder, head = load_encoder(True), PotencyHead()
    optimizer = torch.optim.AdamW(
        [
            {"params": head.parameters(), "lr": 1e-3},
            {"params": list(cast(nn.Module, encoder.W_o).parameters()), "lr": 1e-5},
        ],
        weight_decay=1e-4,
    )
    times = []
    for batch in batches:
        start = time.monotonic()
        p = head(graph_embedding(encoder, batch))
        optimizer.zero_grad(set_to_none=True)
        p.square().mean().backward()
        optimizer.step()
        times.append(time.monotonic() - start)
    write_json(
        output,
        {
            "molecules": len(smiles),
            "batch_size": 32,
            "batch_seconds": times,
            "seconds_per_batch": float(np.median(times)),
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "label_usage": "synthetic zero targets only; no CYP labels or validation score",
            "checkpoint_sha256": CHECKPOINT_SHA,
        },
    )


def fit_candidate(
    frame: pd.DataFrame,
    embeddings: NDArray,
    fit: NDArray,
    query: NDArray,
    tune: bool,
    epochs: int,
    deadline: float,
    evaluate_inner: bool = False,
) -> tuple[NDArray, int, list[dict[str, object]]]:
    torch.manual_seed(17)
    head = PotencyHead()
    encoder = load_encoder(True) if tune else None
    if encoder is not None:
        encoder.eval()
    torch.manual_seed(18)
    y = frame.loc[fit, list(TARGETS)].to_numpy(float)
    mean, std = np.nanmean(y, axis=0), np.nanstd(y, axis=0)
    if not np.isfinite([mean, std]).all() or (std <= 1e-6).any():
        raise ValueError("Insufficient fit-only task variation")
    lower = frame.loc[fit, [t + "_conf_low" for t in TARGETS]].to_numpy(float)
    upper = frame.loc[fit, [t + "_conf_high" for t in TARGETS]].to_numpy(float)
    truth, low, high = [
        torch.tensor((a - mean) / std, dtype=torch.float32) for a in (y, lower, upper)
    ]
    # Exact 32-row chunks preserve alignment with the sequential graph loader.
    chunks = [np.arange(i, min(i + 32, len(fit))) for i in range(0, len(fit), 32)]
    batches = graph_batches(frame.loc[fit, "SMILES"].tolist()) if tune else []
    query_batches = graph_batches(frame.loc[query, "SMILES"].tolist()) if tune else []
    x = torch.tensor(embeddings[fit], dtype=torch.float32)
    q = torch.tensor(embeddings[query], dtype=torch.float32)
    groups = [{"params": list(head.parameters()), "lr": 1e-3}]
    if encoder is not None:
        groups.append({"params": list(cast(nn.Module, encoder.W_o).parameters()), "lr": 1e-5})
    optimizer = torch.optim.AdamW(groups, weight_decay=1e-4)
    rng = np.random.default_rng(17)
    best, best_epoch, history = float("inf"), epochs, []

    def predict() -> NDArray:
        head.eval()
        with torch.no_grad():
            if encoder is None:
                raw = torch.cat([head(q[i : i + 32]) for i in range(0, len(q), 32)]).numpy()
            else:
                raw = torch.cat([head(graph_embedding(encoder, b)) for b in query_batches]).numpy()
        return raw.astype(float) * std + mean

    for epoch in range(1, epochs + 1):
        head.train()
        losses = []
        for i in rng.permutation(len(chunks)):
            if time.monotonic() > deadline:
                raise RuntimeError("Frozen 1800-second neural budget exhausted")
            indices = chunks[i]
            inputs = graph_embedding(encoder, batches[i]) if encoder is not None else x[indices]
            p = head(inputs)
            loss = masked_loss(p, truth[indices], low[indices], high[indices])
            if not bool(torch.isfinite(loss)):
                raise FloatingPointError("Nonfinite final-round loss")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            params = list(head.parameters()) + (
                list(cast(nn.Module, encoder.W_o).parameters()) if encoder is not None else []
            )
            nn.utils.clip_grad_norm_(params, 1)
            optimizer.step()
            losses.append(float(loss.detach()))
        entry: dict[str, object] = {"epoch": epoch, "train_loss": float(np.mean(losses))}
        if evaluate_inner and epoch in (4, 8, 12):
            pred = predict()
            scores = []
            for j, target in enumerate(TARGETS):
                measured = frame.loc[query, target].notna().to_numpy()
                rows = query[measured]
                if len(rows) < 20:
                    raise ValueError("Inner validation needs >=20 labels per endpoint")
                scores.append(
                    score_endpoint(
                        frame.loc[rows, target].to_numpy(float),
                        pred[measured, j],
                        frame.loc[rows, target + "_conf_low"].to_numpy(float),
                        frame.loc[rows, target + "_conf_high"].to_numpy(float),
                    )["st_rae"]
                )
            value = float(np.mean(scores))
            entry["inner_macro_st_rae"] = value
            if value < best:
                best, best_epoch = value, epoch
        history.append(entry)
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > 4 * 1024**3:
            raise RuntimeError("Frozen 4GiB budget exhausted")
    prediction = predict()
    if not np.isfinite(prediction).all():
        raise ValueError("Nonfinite final neural predictions")
    return prediction, best_epoch, history


def run_final(output: Path) -> dict[str, object]:
    if output.exists():
        raise ValueError("Fresh final-round directory required")
    data, x, assignments, provenance = read_context()
    plan = Path("docs/final-round-plan.md")
    if not plan.is_file():
        raise ValueError("Freeze final-round plan before fitting")
    output.mkdir(parents=True)
    write_json(
        output / "protocol.json",
        {
            **provenance,
            "plan_sha256": sha256_file(plan),
            "source_sha256": {
                str(p): sha256_file(p) for p in sorted(Path("src/aidd_agent").rglob("*.py"))
            },
            "uv_lock_sha256": sha256_file(Path("uv.lock")),
            "seed": 17,
            "max_epochs": 12,
            "max_seconds": 1800,
            "max_rss_bytes": 4 * 1024**3,
            "resource_probe_sha256": sha256_file(
                Path("state/sources/final-round/resource-probe.json")
            ),
        },
    )
    started = time.monotonic()
    deadline = started + 1800
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    records, trace = [], []
    with threadpool_limits(limits=2):
        for name, rows in assignments.groupby("split", sort=False):
            fit = rows.loc[rows.partition.eq("fit"), "index"].to_numpy(int)
            query = rows.loc[rows.partition.eq("valid"), "index"].to_numpy(int)
            split = TransferSplit(str(name), fit, query, str(name) != "analog_expansion")
            original = pd.read_csv(ROUND7 / f"{name}-predictions.csv")
            if (
                original.Molecule_Name.tolist()
                != data.molecules.loc[query, "Molecule_Name"].tolist()
            ):
                raise ValueError("Baseline identity mismatch")
            predictions = {
                "baseline": {t: original["baseline:" + t].to_numpy(float) for t in TARGETS}
            }
            inner_fit, inner_valid = next(
                GroupShuffleSplit(n_splits=1, test_size=0.15, random_state=101).split(
                    fit, groups=data.encoded.groups[fit]
                )
            )
            train, valid = fit[inner_fit], fit[inner_valid]
            if set(data.encoded.groups[train]) & set(data.encoded.groups[valid]):
                raise ValueError("Inner scaffold overlap")
            for candidate, tune in (("frozen_head", False), ("partial_tune", True)):
                _, epoch, history = fit_candidate(
                    data.molecules, x, train, valid, tune, 12, deadline, True
                )
                p, _, refit_history = fit_candidate(
                    data.molecules, x, fit, query, tune, epoch, deadline
                )
                predictions[candidate] = {t: p[:, i] for i, t in enumerate(TARGETS)}
                trace.append(
                    {
                        "split": str(name),
                        "model": candidate,
                        "best_epoch": epoch,
                        "inner_fit": train.tolist(),
                        "inner_valid": valid.tolist(),
                        "outer_fit": fit.tolist(),
                        "outer_valid": query.tolist(),
                        "inner_history": history,
                        "refit_history": refit_history,
                    }
                )
                write_json(output / f"{name}-{candidate}-trace.json", trace[-1])
                check_budget(started)
            records.extend(evaluate_predictions(data, split, predictions))
            out = data.molecules.loc[query, ["Molecule_Name", "SMILES"]].copy()
            for model, by_target in predictions.items():
                for target, p in by_target.items():
                    out[model + ":" + target] = p
            out.to_csv(output / f"{name}-predictions.csv", index=False)
            pd.DataFrame(records).to_csv(output / "development-validation.csv", index=False)
        write_json(output / "training-trace.json", trace)
        selected, development_pass = select_development(records)
        write_json(
            output / "selection.json", {"selected": selected, "development_pass": development_pass}
        )
        eligible, reasons = False, ["development_gate_failed"]
        if development_pass:
            if list(Path("state/runs").glob("*/confirmation-opened.json")):
                raise ValueError("Confirmation already opened")
            parts = pd.read_csv(ROUND7 / "confirmation-split.csv")
            fit = parts.index[parts.partition.eq("development")].to_numpy(int)
            valid = parts.index[parts.partition.eq("confirmation")].to_numpy(int)
            write_json(
                output / "confirmation-opened.json",
                {"selection_sha256": sha256_file(output / "selection.json")},
            )
            split = TransferSplit("confirmation", fit, valid, True)
            f = fingerprint_features(data.molecules.SMILES.tolist(), "baseline")
            k = {
                "bits": tanimoto_kernel(f.bits, f.bits),
                "counts": tanimoto_kernel(f.counts, f.counts),
            }
            old = model_predictions(data, split, {"baseline": f}, {"baseline": k})["baseline"]
            chosen = copy.deepcopy(old)
            for model in set(selected.values()) - {"baseline"}:
                inner_fit, inner_valid = next(
                    GroupShuffleSplit(n_splits=1, test_size=0.15, random_state=101).split(
                        fit, groups=data.encoded.groups[fit]
                    )
                )
                _, epoch, _ = fit_candidate(
                    data.molecules,
                    x,
                    fit[inner_fit],
                    fit[inner_valid],
                    model == "partial_tune",
                    12,
                    deadline,
                    True,
                )
                p, _, _ = fit_candidate(
                    data.molecules,
                    x,
                    fit,
                    valid,
                    model == "partial_tune",
                    epoch,
                    deadline,
                )
                for i, t in enumerate(TARGETS):
                    if selected[t] == model:
                        chosen[t] = p[:, i]
            metrics = evaluate_predictions(data, split, {"baseline": old, "chosen": chosen})
            boot = paired_bootstrap(data.molecules, data.encoded.groups, old, chosen, valid)
            eligible, reasons = confirmation_gate(
                {r["endpoint"]: r for r in metrics if r["model"] == "baseline"},
                {r["endpoint"]: r for r in metrics if r["model"] == "chosen"},
                float(np.asarray(boot["macro_difference_percentile_95"])[1]),
            )
            write_json(
                output / "confirmation-evaluation.json", {"metrics": metrics, "bootstrap": boot}
            )
        report = {
            "selected": selected,
            "development_pass": development_pass,
            "submission_eligible": eligible,
            "gate_reasons": reasons,
            "confirmation_opened": development_pass,
            "elapsed_seconds": time.monotonic() - started,
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "platform_submission": "not_submitted",
        }
        write_json(output / "report.json", report)
        return report
