"""Bounded source-specific external classification and fold-safe potency calibration.

@author cylovelife
"""

import importlib.metadata
import json
import resource
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from threadpoolctl import threadpool_limits

from aidd_agent.auxiliary import load_auxiliary
from aidd_agent.baseline import write_json
from aidd_agent.chemistry import encode_molecules, split_groups
from aidd_agent.contracts import IDENTIFIERS, TARGETS, validate_submission
from aidd_agent.external_data import (
    exclude_official,
    leakage_identity,
    load_public_observations,
    verify_public_raw,
)
from aidd_agent.features import extract_features, tanimoto_kernel
from aidd_agent.optimization import BLEND, check_budget, predict_candidate
from aidd_agent.sources import sha256_file
from aidd_agent.transfer import cached_features, split_audit
from aidd_agent.transfer_models import BASELINE
from aidd_agent.transfer_validation import (
    TWO_D6,
    EndpointMetrics,
    TransferSplit,
    confirmation_gate,
    development_splits,
    endpoint_statistics,
    freeze_confirmation,
    paired_bootstrap,
)
from aidd_agent.vendor.openadmet.activity_validation import validate_activity_submission

DESCRIPTORS = (
    "MolWt",
    "MolLogP",
    "TPSA",
    "NumHDonors",
    "NumHAcceptors",
    "NumRotatableBonds",
    "RingCount",
    "FractionCSP3",
)
CANDIDATES = ("baseline", "calibration_control", "external_calibration", "external_blend")


def purge_fit(fit: NDArray, query: NDArray, parents: NDArray) -> NDArray[np.int64]:
    return np.asarray(fit[~np.isin(parents[fit], parents[query])], dtype=np.int64)


def fit_calibrators(
    frame: pd.DataFrame,
    kernel: NDArray,
    descriptors: NDArray,
    external: NDArray,
    groups: NDArray,
    parents: NDArray,
    fit: NDArray,
    query: NDArray,
) -> tuple[dict[str, NDArray], list[dict[str, Any]]]:
    fit = purge_fit(fit, query, parents)
    fit = fit[frame.loc[fit, TWO_D6].notna().to_numpy()]
    if len(fit) < 30 or len(set(groups[fit])) < 3:
        raise ValueError("Insufficient official fit labels/groups for calibration")
    oof = np.full(len(fit), np.nan)
    trace = []
    for fold, (a, b) in enumerate(GroupKFold(3).split(fit, groups=groups[fit])):
        train, valid = purge_fit(fit[a], fit[b], parents), fit[b]
        model = SVR(C=1, epsilon=0.1, kernel="precomputed", cache_size=256)
        model.fit(kernel[np.ix_(train, train)], frame.loc[train, TWO_D6].to_numpy(float))
        oof[b] = model.predict(kernel[np.ix_(valid, train)])
        trace.append(dict(fold=fold, fit=train.tolist(), valid=valid.tolist()))
    model = SVR(C=1, epsilon=0.1, kernel="precomputed", cache_size=256)
    model.fit(kernel[np.ix_(fit, fit)], frame.loc[fit, TWO_D6].to_numpy(float))
    base = model.predict(kernel[np.ix_(query, fit)])
    trace.append(dict(fold="outer", fit=fit.tolist(), valid=query.tolist()))
    if not np.isfinite(oof).all():
        raise ValueError("Incomplete baseline OOF coverage")
    train_x = np.column_stack([oof, descriptors[fit]])
    query_x = np.column_stack([base, descriptors[query]])
    predictions = {"baseline": base}
    for name, a, b in (
        ("calibration_control", train_x, query_x),
        (
            "external_calibration",
            np.column_stack([train_x, external[fit]]),
            np.column_stack([query_x, external[query]]),
        ),
    ):
        calibrator = make_pipeline(StandardScaler(), Ridge(alpha=10))
        calibrator.fit(a, frame.loc[fit, TWO_D6].to_numpy(float))
        predictions[name] = np.asarray(calibrator.predict(b))
    predictions["external_blend"] = (base + predictions["external_calibration"]) / 2
    return predictions, trace


def select_external(records: list[dict[str, Any]]) -> str:
    frame = pd.DataFrame(records)
    means = frame.groupby("model")[["st_rae", "low_distance", "high_distance"]].mean()
    base, control = means.loc["baseline"], means.loc["calibration_control"]
    eligible = []
    for name in ("external_calibration", "external_blend"):
        rows = frame.loc[frame.model.eq(name)]
        mean = means.loc[name]
        wins = sum(
            float(str(r.st_rae))
            < float(
                np.asarray(
                    frame.loc[frame.model.eq("baseline") & frame.split.eq(r.split), "st_rae"]
                )[0]
            )
            for r in rows.itertuples()
        )
        if (
            len(rows) == 3
            and rows.low_n.gt(0).all()
            and rows.high_n.gt(0).all()
            and np.isfinite(rows[["st_rae", "low_distance", "high_distance"]]).all().all()
            and mean.st_rae <= base.st_rae * 0.97
            and mean.st_rae < control.st_rae
            and mean.low_distance <= base.low_distance * 0.9
            and mean.high_distance <= base.high_distance * 1.05
            and wins >= 2
        ):
            eligible.append(name)
    return (
        min(eligible, key=lambda n: float(np.asarray(means.loc[n, "st_rae"]).item()))
        if eligible
        else "baseline"
    )


def fit_public_models(
    classes: pd.DataFrame,
    main_bits: NDArray,
    output: Path,
) -> tuple[NDArray, list[LogisticRegression]]:
    encoded = encode_molecules(classes.smiles.tolist())
    models, signals, diagnostics = [], [], []
    for source in ("pubchem891", "chembl37"):
        rows = np.flatnonzero(classes.source.eq(source).to_numpy())
        y = classes.loc[rows, "class_label"].to_numpy(int)
        groups = classes.loc[rows, "scaffold"].to_numpy(str)
        fit, valid = split_groups(groups, 5151)
        if min(np.bincount(y[fit], minlength=2)) < 10 or len(set(y[valid])) != 2:
            raise ValueError("External source lacks class coverage: " + source)
        model = LogisticRegression(
            C=1, solver="liblinear", max_iter=500, class_weight="balanced", random_state=5151
        )
        model.fit(encoded.fingerprints[rows[fit]], y[fit])
        if np.max(model.n_iter_) >= 500:
            raise ValueError("External classifier did not converge")
        pred = model.decision_function(encoded.fingerprints[rows[valid]])
        diagnostics.append(
            dict(
                source=source,
                fit_n=len(fit),
                valid_n=len(valid),
                auroc=float(roc_auc_score(y[valid], pred)),
                balanced_accuracy=float(balanced_accuracy_score(y[valid], pred >= 0)),
                scaffold_overlap=0,
                fit=rows[fit].tolist(),
                valid=rows[valid].tolist(),
            )
        )
        model.fit(encoded.fingerprints[rows], y)
        if np.max(model.n_iter_) >= 500:
            raise ValueError("Full external classifier did not converge")
        signals.append(model.decision_function(main_bits))
        models.append(model)
    write_json(output / "external-validation.json", diagnostics)
    return np.column_stack(signals), models


def audit_public(data_dir: Path, aux_dir: Path, public_dir: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise ValueError("Output directory already exists")
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    data = load_auxiliary(data_dir, aux_dir)
    observations = load_public_observations(public_dir)
    classes, exclusion = exclude_official(
        observations, data.molecules.SMILES.tolist() + data.test.SMILES.tolist()
    )
    observations.to_csv(output / "observations.csv", index=False)
    classes.to_csv(output / "allowed-classes.csv", index=False)
    main_keys = [leakage_identity(s) for s in data.molecules.SMILES]
    pd.DataFrame(main_keys, columns=["parent", "scaffold"]).to_csv(
        output / "official-keys.csv", index=False
    )
    accepted = observations.loc[observations.accepted]
    summary = dict(
        raw_by_source=observations.groupby("source").size().to_dict(),
        accepted_by_source=accepted.groupby("source").size().to_dict(),
        retained_by_source=[
            dict(
                source=s,
                n=len(g),
                active=int(g.class_label.sum()),
                inactive=int(g.class_label.eq(0).sum()),
            )
            for s, g in classes.groupby("source")
        ],
        exact_low=int(accepted.exact_pIC50.lt(4).sum()),
        censored_low_upper=int(
            (accepted.p_relation.isin(["<", "<="]) & accepted.p_bound.le(4)).sum()
        ),
        exclusion=exclusion,
        elapsed_seconds=time.monotonic() - started,
        raw_manifest_sha256=sha256_file(public_dir / "manifest.json"),
        main_audit=data.audit,
        source_sha256=sha256_file(Path(__file__).with_name("external_data.py")),
        audit_runner_sha256=sha256_file(Path(__file__)),
        artifacts={
            n: sha256_file(output / n)
            for n in ("observations.csv", "allowed-classes.csv", "official-keys.csv")
        },
        semantics="External classes and censoring are not new official direct pIC50 labels",
    )
    write_json(output / "summary.json", summary)
    return summary


def run_external(
    data_dir: Path, aux_dir: Path, public_dir: Path, audit_dir: Path, output: Path
) -> dict[str, Any]:
    if output.exists():
        raise ValueError("Output directory already exists")
    started = time.monotonic()
    verify_public_raw(public_dir)
    summary = json.loads((audit_dir / "summary.json").read_text())
    if summary["raw_manifest_sha256"] != sha256_file(public_dir / "manifest.json") or summary[
        "source_sha256"
    ] != sha256_file(Path(__file__).with_name("external_data.py")):
        # audit_public stores the data-parser hash below; reject stale semantics.
        raise ValueError("External audit source/raw hash mismatch")
    for name, digest in summary["artifacts"].items():
        if sha256_file(audit_dir / name) != digest:
            raise ValueError("External audit artifact hash mismatch")
    data = load_auxiliary(data_dir, aux_dir)
    if data.audit != summary["main_audit"]:
        raise ValueError("External audit official data identity mismatch")
    classes = pd.read_csv(audit_dir / "allowed-classes.csv")
    keys = pd.read_csv(audit_dir / "official-keys.csv")
    if len(keys) != len(data.molecules):
        raise ValueError("Official parent-key row count mismatch")
    parents = keys.parent.to_numpy(str)
    output.mkdir(parents=True, exist_ok=False)
    protocol = dict(
        created_at=datetime.now(UTC).isoformat(),
        candidates=CANDIDATES,
        plan_sha256=sha256_file(Path("docs/round4-plan.md")),
        audit_sha256=sha256_file(audit_dir / "summary.json"),
        sources={str(p): sha256_file(p) for p in sorted(Path("src/aidd_agent").rglob("*.py"))},
        uv_lock_sha256=sha256_file(Path("uv.lock")),
        dependencies={
            n: importlib.metadata.version(n)
            for n in ("numpy", "pandas", "rdkit", "scikit-learn", "scipy")
        },
        max_seconds=1800,
        max_rss_bytes=4 * 1024**3,
        threads=2,
    )
    write_json(output / "protocol.json", protocol)
    with threadpool_limits(limits=2):
        features = cached_features(data, Path("state/cache/round3-features"))
        kernel = tanimoto_kernel(features.bits, features.bits)
        pool, confirmation, seed = freeze_confirmation(data.molecules, data.encoded.groups)
        partitions = data.molecules[list(IDENTIFIERS)].copy()
        partitions["group"] = data.encoded.groups
        partitions["partition"] = "development"
        partitions.loc[confirmation, "partition"] = "confirmation"
        partitions.to_csv(output / "confirmation-partition.csv", index=False)
        expected = "f9fa599c6d3f9536aa1d6c4e7cef9ea47f6159fba03950f994be34a3abb6104a"
        if sha256_file(output / "confirmation-partition.csv") != expected:
            raise ValueError("Round 4 must preserve the Stage A confirmation partition")
        pool = purge_fit(pool, confirmation, parents)
        signals, models = fit_public_models(classes, features.bits, output)
        desc = features.descriptors[:, [features.descriptor_names.index(n) for n in DESCRIPTORS]]
        records = []
        audits = []
        splits = development_splits(data.molecules, data.encoded.groups, pool, kernel)
        for split in splits:
            fit = purge_fit(split.fit, split.valid, parents)
            predictions, trace = fit_calibrators(
                data.molecules,
                kernel,
                desc,
                signals,
                data.encoded.groups,
                parents,
                fit,
                split.valid,
            )
            audits.append(
                split_audit(
                    data,
                    TransferSplit(split.name, fit, split.valid, split.scaffold_disjoint),
                    kernel,
                )
            )
            out = data.molecules.loc[split.valid, list(IDENTIFIERS)].copy()
            measured = data.molecules.loc[split.valid, TWO_D6].notna().to_numpy()
            rows = split.valid[measured]
            for name, pred in predictions.items():
                out[name] = pred
                records.append(
                    dict(
                        split=split.name,
                        model=name,
                        endpoint=TWO_D6,
                        **endpoint_statistics(
                            data.molecules.loc[rows, TWO_D6].to_numpy(float),
                            pred[measured],
                            data.molecules.loc[rows, TWO_D6 + "_conf_low"].to_numpy(float),
                            data.molecules.loc[rows, TWO_D6 + "_conf_high"].to_numpy(float),
                        ),
                    )
                )
            out.to_csv(output / (split.name + "-predictions.csv"), index=False)
            write_json(output / (split.name + "-trace.json"), trace)
            pd.DataFrame(records).to_csv(output / "development.csv", index=False)
            check_budget(started)
        selected = select_external(records)
        write_json(output / "selection.json", dict(selected=selected, confirmation_read=False))
        write_json(
            output / "split-audit.json",
            dict(
                seed=seed,
                splits=audits,
                confirmation_n=len(confirmation),
                development_n=len(pool),
                confirmation_parent_overlap=0,
                original_confirmation_sha256=expected,
                partition_sha256=sha256_file(output / "confirmation-partition.csv"),
            ),
        )
        eligible = False
        reasons = ["development_no_eligible_external_model"]
        confirmed: dict[str, Any] = {"opened": False}
        # Confirmation is evaluated once only after fixed development selection.
        if selected != "baseline":
            write_json(
                output / "confirmation-opened.json",
                dict(
                    opened_at=datetime.now(UTC).isoformat(),
                    selection_sha256=sha256_file(output / "selection.json"),
                ),
            )
            predictions, _ = fit_calibrators(
                data.molecules,
                kernel,
                desc,
                signals,
                data.encoded.groups,
                parents,
                pool,
                confirmation,
            )
            count_kernel = tanimoto_kernel(features.counts, features.counts)
            kernels = {"bits": kernel, "counts": count_kernel}
            baseline, chosen = {}, {}
            for target in TARGETS:
                if target == TWO_D6:
                    baseline[target] = predictions["baseline"]
                    chosen[target] = predictions[selected]
                    continue
                fit = pool[data.molecules.loc[pool, target].notna().to_numpy()]
                members = BLEND if BASELINE[target] == "blend" else {BASELINE[target]: 1.0}
                unchanged_pred = sum(
                    w
                    * predict_candidate(
                        n,
                        features,
                        fit,
                        features,
                        confirmation,
                        kernels,
                        kernels,
                        data.molecules.loc[fit, target].to_numpy(float),
                        data.molecules.loc[fit, target + "_conf_low"].to_numpy(float),
                        data.molecules.loc[fit, target + "_conf_high"].to_numpy(float),
                    )
                    for n, w in members.items()
                )
                baseline[target] = np.asarray(unchanged_pred)
                chosen[target] = np.asarray(unchanged_pred)
            metrics: dict[str, dict[str, EndpointMetrics]] = {}
            for name, predictions_by_target in (("baseline", baseline), ("chosen", chosen)):
                metrics[name] = {}
                for target in TARGETS:
                    mask = data.molecules.loc[confirmation, target].notna().to_numpy()
                    rows = confirmation[mask]
                    metrics[name][target] = endpoint_statistics(
                        data.molecules.loc[rows, target].to_numpy(float),
                        predictions_by_target[target][mask],
                        data.molecules.loc[rows, target + "_conf_low"].to_numpy(float),
                        data.molecules.loc[rows, target + "_conf_high"].to_numpy(float),
                    )
            bootstrap = paired_bootstrap(
                data.molecules, data.encoded.groups, baseline, chosen, confirmation
            )
            eligible, reasons = confirmation_gate(
                metrics["baseline"],
                metrics["chosen"],
                float(np.asarray(bootstrap["macro_difference_percentile_95"])[1]),
            )
            confirmed = dict(opened=True, metrics=metrics, bootstrap=bootstrap)
            write_json(output / "confirmation-evaluation.json", confirmed)
            check_budget(started)
        submission = None
        if eligible:
            query_features = extract_features(data.test.SMILES.tolist())
            combined_bits = np.vstack([features.bits, query_features.bits])
            combined_kernel = tanimoto_kernel(combined_bits, combined_bits)
            combined_desc = np.vstack(
                [
                    desc,
                    query_features.descriptors[
                        :, [features.descriptor_names.index(n) for n in DESCRIPTORS]
                    ],
                ]
            )
            combined_signals = np.vstack(
                [
                    signals,
                    np.column_stack(
                        [model.decision_function(query_features.bits) for model in models]
                    ),
                ]
            )
            combined_frame = pd.concat([data.molecules, data.test], ignore_index=True)
            test_encoded = encode_molecules(data.test.SMILES.tolist())
            combined_groups = np.concatenate([data.encoded.groups, test_encoded.groups])
            combined_parents = np.concatenate(
                [parents, [leakage_identity(s)[0] for s in data.test.SMILES]]
            )
            all_fit = np.arange(len(data.molecules))
            all_query = np.arange(len(data.molecules), len(combined_frame))
            final, trace = fit_calibrators(
                combined_frame,
                combined_kernel,
                combined_desc,
                combined_signals,
                combined_groups,
                combined_parents,
                all_fit,
                all_query,
            )
            out = data.test[list(IDENTIFIERS)].copy()
            out[TWO_D6] = final[selected]
            fit_allowed = purge_fit(all_fit, all_query, combined_parents)
            kernels = {"bits": kernel, "counts": tanimoto_kernel(features.counts, features.counts)}
            cross = {
                "bits": tanimoto_kernel(query_features.bits, features.bits),
                "counts": tanimoto_kernel(query_features.counts, features.counts),
            }
            for target in TARGETS:
                if target == TWO_D6:
                    continue
                fit = fit_allowed[data.molecules.loc[fit_allowed, target].notna().to_numpy()]
                members = BLEND if BASELINE[target] == "blend" else {BASELINE[target]: 1.0}
                out[target] = sum(
                    w
                    * predict_candidate(
                        n,
                        features,
                        fit,
                        query_features,
                        np.arange(len(data.test)),
                        kernels,
                        cross,
                        data.molecules.loc[fit, target].to_numpy(float),
                        data.molecules.loc[fit, target + "_conf_low"].to_numpy(float),
                        data.molecules.loc[fit, target + "_conf_high"].to_numpy(float),
                    )
                    for n, w in members.items()
                )
            validate_submission(out, data.test)
            path = output / "regression.csv"
            out.to_csv(path, index=False)
            validate_submission(pd.read_csv(path), data.test)
            valid, errors = validate_activity_submission(
                path, expected_ids=set(data.test.Molecule_Name)
            )
            if not valid:
                raise ValueError(f"Official validator rejected external predictions: {errors}")
            submission = dict(path=str(path), sha256=sha256_file(path), official_validator=True)
            write_json(output / "full-fit-trace.json", trace)
        check_budget(started)
        report = dict(
            submission_eligible=eligible,
            selected=selected,
            gate_reasons=reasons,
            confirmation=confirmed,
            platform_submission="not_submitted",
            submission=submission,
            elapsed_seconds=time.monotonic() - started,
            peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            external_audit_sha256=protocol["audit_sha256"],
            protocol_sha256=sha256_file(output / "protocol.json"),
        )
        write_json(output / "report.json", report)
    return report
