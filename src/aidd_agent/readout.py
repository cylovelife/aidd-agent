"""Hash-verified CheMeleon readout diagnosis without confirmation evaluation.

@author cylovelife
"""

import importlib.metadata
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from aidd_agent.auxiliary import AuxiliaryData, load_auxiliary
from aidd_agent.baseline import write_json
from aidd_agent.contracts import TARGETS
from aidd_agent.features import tanimoto_kernel
from aidd_agent.optimization import check_budget
from aidd_agent.representation import fingerprint_features, model_predictions, select_development
from aidd_agent.sources import sha256_file
from aidd_agent.transfer import evaluate_predictions
from aidd_agent.transfer_validation import (
    ScoreRecord,
    TransferSplit,
    confirmation_gate,
    endpoint_statistics,
    paired_bootstrap,
)

ROUND7 = Path("state/runs/20261101-round7-01")
EMBEDDING_KEY = "6050a0492bac8893a3347025bb28a3dde9b02a7e1417a925688710dabd210a35"


def read_context() -> tuple[AuxiliaryData, NDArray, pd.DataFrame, dict[str, object]]:
    data = load_auxiliary(Path("state/data/cyp"), Path("state/data/cyp-aux"))
    cache = Path("state/cache/round7-chemeleon") / EMBEDDING_KEY
    meta = json.loads(cache.with_suffix(".json").read_text())
    path = cache.with_suffix(".npy")
    if sha256_file(path) != meta["sha256"] or meta["smiles"] != data.molecules.SMILES.tolist():
        raise ValueError("Embedding identity/hash mismatch")
    if (
        meta["weights_sha256"]
        != json.loads(Path("docs/round7-sources-lock.json").read_text())["sha256"]
    ):
        raise ValueError("Checkpoint provenance mismatch")
    if meta["source_sha256"] != sha256_file(Path("src/aidd_agent/representation.py")):
        raise ValueError("Encoder source drift")
    if any(importlib.metadata.version(n) != v for n, v in meta["dependencies"].items()):
        raise ValueError("Encoder dependency drift")
    x = np.load(path, allow_pickle=False)
    if x.shape != (len(data.molecules), 2048) or not np.isfinite(x).all():
        raise ValueError("Invalid embedding matrix")
    assignments = pd.read_csv(ROUND7 / "development-splits.csv")
    parts = pd.read_csv(ROUND7 / "confirmation-split.csv")
    heldout = set(parts.index[parts.partition.eq("confirmation")])
    if heldout & set(assignments["index"]):
        raise ValueError("Confirmation in development")
    return (
        data,
        x,
        assignments,
        {
            "embedding_sha256": meta["sha256"],
            "embedding_metadata_sha256": sha256_file(cache.with_suffix(".json")),
            "source_run_protocol_sha256": sha256_file(ROUND7 / "protocol.json"),
            "development_splits_sha256": sha256_file(ROUND7 / "development-splits.csv"),
            "confirmation_sha256": sha256_file(ROUND7 / "confirmation-split.csv"),
        },
    )


def diagnose(output: Path) -> dict[str, object]:
    if output.exists():
        raise ValueError("Fresh diagnostic directory required")
    data, x, assignments, provenance = read_context()
    output.mkdir(parents=True)
    write_json(
        output / "protocol.json",
        {
            **provenance,
            "plan_sha256": sha256_file(Path("docs/round8-diagnostic-plan.md")),
            "source_sha256": sha256_file(Path(__file__)),
            "uv_lock_sha256": sha256_file(Path("uv.lock")),
            "diagnosis_only": True,
            "new_candidate_fits": 0,
        },
    )
    records = []
    started = time.monotonic()
    with threadpool_limits(limits=2):
        for split, rows in assignments.groupby("split", sort=False):
            train = rows.loc[rows.partition.eq("fit"), "index"].to_numpy(int)
            valid = rows.loc[rows.partition.eq("valid"), "index"].to_numpy(int)
            saved = pd.read_csv(ROUND7 / f"{split}-chemeleon-predictions.csv")
            if saved.Molecule_Name.tolist() != data.molecules.loc[valid, "Molecule_Name"].tolist():
                raise ValueError("Saved prediction ordering mismatch")
            for target in TARGETS:
                y = data.molecules[target].to_numpy(float)
                fit, query = train[np.isfinite(y[train])], valid[np.isfinite(y[valid])]
                scaler = StandardScaler().fit(x[fit])
                z, q = scaler.transform(x[fit]), scaler.transform(x[query])
                model = Ridge(alpha=10, solver="lsqr").fit(z, y[fit])
                p, train_p = model.predict(q), model.predict(z)
                reference = saved["chemeleon:" + target].to_numpy(float)[np.isfinite(y[valid])]
                replay_error = float(np.max(np.abs(p - reference)))
                if replay_error > 1e-9:
                    raise ValueError("Cannot replay round-seven predictions")
                metrics = {}
                for part, indices, pred in (("fit", fit, train_p), ("valid", query, p)):
                    low = data.molecules.loc[indices, target + "_conf_low"].to_numpy(float)
                    high = data.molecules.loc[indices, target + "_conf_high"].to_numpy(float)
                    metrics[part] = endpoint_statistics(y[indices], pred, low, high)
                record = {
                    "split": split,
                    "endpoint": target,
                    "fit_n": len(fit),
                    "valid_n": len(query),
                    "replay_max_abs_error": replay_error,
                    "metrics": metrics,
                    "fit_rmse": float(np.sqrt(np.mean((train_p - y[fit]) ** 2))),
                    "valid_rmse": float(np.sqrt(np.mean((p - y[query]) ** 2))),
                    "fit_prediction_range": [float(train_p.min()), float(train_p.max())],
                    "valid_prediction_range": [float(p.min()), float(p.max())],
                    "training_label_range": [float(y[fit].min()), float(y[fit].max())],
                    "constant_fit_dimensions": int((scaler.var_ == 0).sum()),
                    "scale_quantiles": np.quantile(scaler.scale_, [0, 0.01, 0.5, 0.99, 1]).tolist(),
                    "fit_abs_z_quantiles": np.quantile(np.abs(z), [0.5, 0.99, 1]).tolist(),
                    "valid_abs_z_quantiles": np.quantile(np.abs(q), [0.5, 0.99, 1]).tolist(),
                    "valid_fraction_abs_z_gt10": float((np.abs(q) > 10).mean()),
                    "coef_l2": float(np.linalg.norm(model.coef_)),
                }
                records.append(record)
                check_budget(started)
    report = {
        "rows": records,
        "confirmation_evaluated": False,
        "embedding_shape": list(x.shape),
        "embedding_range": [float(x.min()), float(x.max())],
        "all_zero_dimensions": int((x == 0).all(axis=0).sum()),
        "elapsed_seconds": time.monotonic() - started,
    }
    write_json(output / "report.json", report)
    return report


HEADS = ("replay", "ridge1000", "clip5_ridge10", "clip5_ridge1000")


def fit_head(
    x: NDArray, y: NDArray, query: NDArray, name: str
) -> tuple[NDArray, NDArray, dict[str, float]]:
    if name not in HEADS:
        raise ValueError("Unknown frozen readout")
    if not np.isfinite(x).all() or not np.isfinite(y).all() or not np.isfinite(query).all():
        raise ValueError("Finite readout inputs/fit labels required")
    if x.ndim != 2 or query.ndim != 2 or x.shape[1] != query.shape[1] or len(x) != len(y):
        raise ValueError("Readout input shape mismatch")
    scaler = StandardScaler().fit(x)
    z, q = scaler.transform(x), scaler.transform(query)
    if name.startswith("clip5"):
        z, q = np.clip(z, -5, 5), np.clip(q, -5, 5)
    model = Ridge(alpha=1000 if name.endswith("1000") else 10, solver="lsqr").fit(z, y)
    return (
        np.asarray(model.predict(q)),
        np.asarray(model.predict(z)),
        {
            "coef_l2": float(np.linalg.norm(model.coef_)),
            "query_max_abs_input": float(np.abs(q).max()),
            "fit_max_abs_input": float(np.abs(z).max()),
        },
    )


def readout_predictions(
    data: AuxiliaryData, x: NDArray, split: TransferSplit, names: tuple[str, ...]
) -> tuple[dict[str, dict[str, NDArray]], list[dict[str, object]]]:
    predictions: dict[str, dict[str, NDArray]] = {name: {} for name in names}
    diagnostics: list[dict[str, object]] = []
    for name in names:
        for target in TARGETS:
            y = data.molecules[target].to_numpy(float)
            fit = split.fit[np.isfinite(y[split.fit])]
            p, train_p, stats = fit_head(x[fit], y[fit], x[split.valid], name)
            predictions[name][target] = p
            diagnostics.append(
                {
                    "split": split.name,
                    "model": name,
                    "endpoint": target,
                    "fit_rmse": float(np.sqrt(np.mean((train_p - y[fit]) ** 2))),
                    "prediction_min": float(p.min()),
                    "prediction_max": float(p.max()),
                    **stats,
                }
            )
    return predictions, diagnostics


def run_readout(output: Path) -> dict[str, object]:
    if output.exists():
        raise ValueError("Fresh experiment directory required")
    data, x, assignments, provenance = read_context()
    plan = Path("docs/round8-plan.md")
    if not plan.is_file():
        raise ValueError("Freeze the follow-up plan first")
    output.mkdir(parents=True)
    write_json(
        output / "protocol.json",
        {
            **provenance,
            "heads": HEADS,
            "plan_sha256": sha256_file(plan),
            "source_sha256": {
                str(p): sha256_file(p) for p in sorted(Path("src/aidd_agent").rglob("*.py"))
            },
            "uv_lock_sha256": sha256_file(Path("uv.lock")),
            "diagnostic_report_sha256": sha256_file(
                Path("state/runs/20261101-round8-diagnostic-01/report.json")
            ),
            "baseline_predictions_sha256": {
                str(p): sha256_file(p) for p in ROUND7.glob("*-predictions.csv")
            },
        },
    )
    started = time.monotonic()
    records: list[ScoreRecord] = []
    training_diagnostics: list[dict[str, object]] = []
    with threadpool_limits(limits=2):
        for name, rows in assignments.groupby("split", sort=False):
            fit = rows.loc[rows.partition.eq("fit"), "index"].to_numpy(int)
            valid = rows.loc[rows.partition.eq("valid"), "index"].to_numpy(int)
            split = TransferSplit(str(name), fit, valid, str(name) != "analog_expansion")
            pred, diag = readout_predictions(data, x, split, HEADS)
            training_diagnostics.extend(diag)
            saved = pd.read_csv(ROUND7 / f"{name}-predictions.csv")
            replay = pd.read_csv(ROUND7 / f"{name}-chemeleon-predictions.csv")
            expected = data.molecules.loc[valid, "Molecule_Name"].tolist()
            if (
                saved.Molecule_Name.tolist() != expected
                or replay.Molecule_Name.tolist() != expected
            ):
                raise ValueError("Original prediction identity drift")
            pred["baseline"] = {t: saved["baseline:" + t].to_numpy(float) for t in TARGETS}
            for target in TARGETS:
                np.testing.assert_allclose(
                    pred["replay"][target], replay["chemeleon:" + target], rtol=0, atol=1e-9
                )
            records.extend(evaluate_predictions(data, split, pred))
            frame = data.molecules.loc[valid, ["Molecule_Name", "SMILES"]].copy()
            for model, by_target in pred.items():
                for target, p in by_target.items():
                    frame[model + ":" + target] = p
            frame.to_csv(output / f"{name}-predictions.csv", index=False)
            check_budget(started)
        pd.DataFrame(records).to_csv(output / "development-validation.csv", index=False)
        write_json(output / "training-diagnostics.json", training_diagnostics)
        selected, development_pass = select_development(records)
        write_json(
            output / "selection.json", {"selected": selected, "development_pass": development_pass}
        )
        eligible, reasons = False, ["development_gate_failed"]
        if development_pass:
            if list(Path("state/runs").glob("*/confirmation-opened.json")):
                raise ValueError("Existing confirmation opening prohibits reuse")
            parts = pd.read_csv(ROUND7 / "confirmation-split.csv")
            fit = parts.index[parts.partition.eq("development")].to_numpy(int)
            valid = parts.index[parts.partition.eq("confirmation")].to_numpy(int)
            write_json(
                output / "confirmation-opened.json",
                {"selection_sha256": sha256_file(output / "selection.json")},
            )
            split = TransferSplit("confirmation", fit, valid, True)
            heads = tuple(dict.fromkeys(n for n in selected.values() if n != "baseline"))
            new, _ = readout_predictions(data, x, split, heads)
            f = fingerprint_features(data.molecules.SMILES.tolist(), "baseline")
            k = {
                "bits": tanimoto_kernel(f.bits, f.bits),
                "counts": tanimoto_kernel(f.counts, f.counts),
            }
            old = model_predictions(data, split, {"baseline": f}, {"baseline": k})["baseline"]
            chosen = {
                t: old[t] if selected[t] == "baseline" else new[selected[t]][t] for t in TARGETS
            }
            metrics = evaluate_predictions(data, split, {"baseline": old, "chosen": chosen})
            bootstrap = paired_bootstrap(data.molecules, data.encoded.groups, old, chosen, valid)
            eligible, reasons = confirmation_gate(
                {r["endpoint"]: r for r in metrics if r["model"] == "baseline"},
                {r["endpoint"]: r for r in metrics if r["model"] == "chosen"},
                float(np.asarray(bootstrap["macro_difference_percentile_95"])[1]),
            )
            write_json(
                output / "confirmation-evaluation.json",
                {"metrics": metrics, "bootstrap": bootstrap},
            )
        report: dict[str, object] = {
            "selected": selected,
            "development_pass": development_pass,
            "submission_eligible": eligible,
            "gate_reasons": reasons,
            "confirmation_opened": development_pass,
            "elapsed_seconds": time.monotonic() - started,
            "platform_submission": "not_submitted",
        }
        write_json(output / "report.json", report)
        return report
