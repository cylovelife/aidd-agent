"""Finite-budget interval supervision; primary evidence and confirmation stay separately gated.

@author cylovelife
"""

import importlib.metadata
import resource
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.svm import SVR
from threadpoolctl import threadpool_limits

from aidd_agent.auxiliary import load_auxiliary
from aidd_agent.baseline import write_json
from aidd_agent.censored import fit_interval_model
from aidd_agent.censored_data import load_reviewed_bounds
from aidd_agent.contracts import IDENTIFIERS, TARGETS, validate_submission
from aidd_agent.external_data import leakage_identity
from aidd_agent.external_transfer import purge_fit
from aidd_agent.features import MolecularFeatures, extract_features, tanimoto_kernel
from aidd_agent.optimization import BLEND, MAX_SECONDS, check_budget, predict_candidate
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

CANDIDATES = ("baseline", "interval_control", "interval_transfer", "interval_blend")
PARTITION_SHA256 = "f9fa599c6d3f9536aa1d6c4e7cef9ea47f6159fba03950f994be34a3abb6104a"


def fit_candidates(
    frame: pd.DataFrame,
    kernel: NDArray,
    external: pd.DataFrame,
    parents: NDArray,
    fit: NDArray,
    query: NDArray,
    deadline: float | None = None,
) -> tuple[dict[str, NDArray], dict[str, Any]]:
    """Kernel indices are official rows followed by reviewed external rows; query labels unread."""
    fit = purge_fit(fit, query, parents)
    fit = fit[frame.loc[fit, TWO_D6].notna().to_numpy()]
    if len(fit) < 2 or kernel.shape != (len(frame) + len(external),) * 2:
        raise ValueError("Insufficient official fit labels or incompatible external kernel")
    base = SVR(C=1, epsilon=0.1, kernel="precomputed", cache_size=256)
    base.fit(kernel[np.ix_(fit, fit)], frame.loc[fit, TWO_D6].to_numpy(float))
    result = {"baseline": base.predict(kernel[np.ix_(query, fit)])}
    lower = frame.loc[fit, TWO_D6 + "_conf_low"].to_numpy(float)
    upper = frame.loc[fit, TWO_D6 + "_conf_high"].to_numpy(float)
    ext_indices = len(frame) + np.arange(len(external), dtype=np.int64)
    codes, names = pd.factorize(external.source, sort=True)
    trace: dict[str, Any] = dict(fit=fit.tolist(), query=query.tolist(), sources=names.tolist())
    for name, include in (("interval_control", False), ("interval_transfer", True)):
        indices = np.concatenate([fit, ext_indices]) if include else fit
        lo = np.concatenate([lower, external.lower.to_numpy(float)]) if include else lower
        hi = np.concatenate([upper, external.upper.to_numpy(float)]) if include else upper
        weights = (
            np.concatenate([np.ones(len(fit)), external.weight.to_numpy(float)])
            if include
            else np.ones(len(fit))
        )
        sources = (
            np.concatenate([np.full(len(fit), -1), codes]) if include else np.full(len(fit), -1)
        )
        model = fit_interval_model(
            kernel[np.ix_(indices, indices)], lo, hi, weights, sources, deadline
        )
        result[name] = model.predict(kernel[np.ix_(query, indices)])
        trace[name] = dict(
            converged=model.converged,
            iterations=model.iterations,
            objective=model.objective,
            gradient_inf=model.gradient_inf,
            source_offsets=model.source_offsets.tolist(),
            official_fit_n=len(fit),
            external_fit_n=len(ext_indices) if include else 0,
        )
    result["interval_blend"] = (result["baseline"] + result["interval_transfer"]) / 2
    # Prespecified ablation only, never an additional selection candidate.
    result["control_blend_diagnostic"] = (result["baseline"] + result["interval_control"]) / 2
    if not all(np.isfinite(p).all() for p in result.values()):
        raise ValueError("Non-finite interval prediction")
    return result, trace


def select_censored(records: list[dict[str, Any]]) -> str:
    f = pd.DataFrame(records)
    fields = ["st_rae", "low_distance", "high_distance"]
    means = f.groupby("model")[fields].mean()
    baseline = f.loc[f.model.eq("baseline")].set_index("split")
    if len(baseline) != 3 or not baseline.index.is_unique:
        raise ValueError("Expected three unique baseline development splits")
    base = means.loc["baseline"]
    eligible = []
    for name in CANDIDATES[1:]:
        rows = f.loc[f.model.eq(name)]
        mean = means.loc[name]
        if (
            len(rows) == 3
            and set(rows.split) == set(baseline.index)
            and rows.low_n.gt(0).all()
            and rows.high_n.gt(0).all()
            and np.isfinite(rows[fields]).all().all()
            and mean.st_rae <= base.st_rae * 0.97
            and mean.low_distance <= base.low_distance * 0.9
            and mean.high_distance <= base.high_distance * 1.05
            and sum(
                float(str(r.st_rae))
                < float(np.asarray(baseline.loc[str(r.split), "st_rae"]).item())
                for r in rows.itertuples()
            )
            >= 2
        ):
            eligible.append(name)
    return (
        min(eligible, key=lambda n: float(np.asarray(means.loc[n, "st_rae"]).item()))
        if eligible
        else "baseline"
    )


def fixed_other_targets(
    frame: pd.DataFrame,
    features: MolecularFeatures,
    fit_pool: NDArray,
    query_features: MolecularFeatures,
    query: NDArray,
    kernels: dict[str, NDArray],
    cross: dict[str, NDArray],
) -> dict[str, NDArray]:
    predictions = {}
    for target in TARGETS:
        if target == TWO_D6:
            continue
        fit = fit_pool[frame.loc[fit_pool, target].notna().to_numpy()]
        members = BLEND if BASELINE[target] == "blend" else {BASELINE[target]: 1.0}
        predictions[target] = np.asarray(
            sum(
                weight
                * predict_candidate(
                    name,
                    features,
                    fit,
                    query_features,
                    query,
                    kernels,
                    cross,
                    frame.loc[fit, target].to_numpy(float),
                    frame.loc[fit, target + "_conf_low"].to_numpy(float),
                    frame.loc[fit, target + "_conf_high"].to_numpy(float),
                )
                for name, weight in members.items()
            )
        )
    return predictions


def run_censored(
    data_dir: Path,
    aux_dir: Path,
    audit_dir: Path,
    output: Path,
    *,
    plan_file: Path = Path("docs/round5-plan.md"),
) -> dict[str, Any]:
    if output.exists():
        raise ValueError("Output directory already exists")
    plan_digest = sha256_file(plan_file)
    started = time.monotonic()
    data = load_auxiliary(data_dir, aux_dir)
    external, audit = load_reviewed_bounds(
        audit_dir, data.molecules.SMILES.tolist() + data.test.SMILES.tolist()
    )
    parents = np.array([k[0] for k in audit.pop("official_keys")[: len(data.molecules)]])
    output.mkdir(parents=True, exist_ok=False)
    external.to_csv(output / "retained-bounds.csv", index=False)
    write_json(output / "data-audit.json", audit | dict(official=data.audit))
    protocol = dict(
        created_at=datetime.now(UTC).isoformat(),
        candidates=CANDIDATES,
        plan_file=str(plan_file),
        plan_sha256=plan_digest,
        audit_sha256=audit["audit_sha256"],
        retained_sha256=sha256_file(output / "retained-bounds.csv"),
        sources={str(p): sha256_file(p) for p in sorted(Path("src/aidd_agent").rglob("*.py"))},
        uv_lock_sha256=sha256_file(Path("uv.lock")),
        dependencies={
            n: importlib.metadata.version(n)
            for n in ("numpy", "pandas", "rdkit", "scikit-learn", "scipy")
        },
        max_seconds=MAX_SECONDS,
        max_rss_bytes=4 * 1024**3,
        threads=2,
    )
    write_json(output / "protocol.json", protocol)
    with threadpool_limits(limits=2):
        features = cached_features(data, Path("state/cache/round3-features"))
        external_features = extract_features(external.smiles.tolist())
        all_bits = np.vstack([features.bits, external_features.bits])
        kernel = tanimoto_kernel(all_bits, all_bits)
        official_kernel = kernel[: len(data.molecules), : len(data.molecules)]
        pool, confirmation, seed = freeze_confirmation(data.molecules, data.encoded.groups)
        partitions = data.molecules[list(IDENTIFIERS)].copy()
        partitions["group"] = data.encoded.groups
        partitions["partition"] = "development"
        partitions.loc[confirmation, "partition"] = "confirmation"
        partitions.to_csv(output / "confirmation-partition.csv", index=False)
        if sha256_file(output / "confirmation-partition.csv") != PARTITION_SHA256:
            raise ValueError("Round 5 must preserve the original sealed confirmation partition")
        pool = purge_fit(pool, confirmation, parents)
        records, audits = [], []
        for split in development_splits(data.molecules, data.encoded.groups, pool, official_kernel):
            fit = purge_fit(split.fit, split.valid, parents)
            predictions, trace = fit_candidates(
                data.molecules, kernel, external, parents, fit, split.valid, started + MAX_SECONDS
            )
            audits.append(
                split_audit(
                    data,
                    TransferSplit(split.name, fit, split.valid, split.scaffold_disjoint),
                    official_kernel,
                )
            )
            out = data.molecules.loc[split.valid, list(IDENTIFIERS)].copy()
            mask = data.molecules.loc[split.valid, TWO_D6].notna().to_numpy()
            rows = split.valid[mask]
            for name, prediction in predictions.items():
                out[name] = prediction
                records.append(
                    dict(
                        split=split.name,
                        model=name,
                        **endpoint_statistics(
                            data.molecules.loc[rows, TWO_D6].to_numpy(float),
                            prediction[mask],
                            data.molecules.loc[rows, TWO_D6 + "_conf_low"].to_numpy(float),
                            data.molecules.loc[rows, TWO_D6 + "_conf_high"].to_numpy(float),
                        ),
                    )
                )
            out.to_csv(output / (split.name + "-predictions.csv"), index=False)
            write_json(output / (split.name + "-trace.json"), trace)
            pd.DataFrame(records).to_csv(output / "development.csv", index=False)
            check_budget(started)
        selected = select_censored(records)
        write_json(output / "selection.json", dict(selected=selected, confirmation_read=False))
        write_json(
            output / "split-audit.json",
            dict(
                seed=seed,
                splits=audits,
                confirmation_n=len(confirmation),
                development_n=len(pool),
                confirmation_parent_overlap=int(
                    len(set(parents[pool]) & set(parents[confirmation]))
                ),
                partition_sha256=PARTITION_SHA256,
            ),
        )
        eligible, reasons = False, ["development_no_eligible_censored_model"]
        confirmed: dict[str, Any] = dict(opened=False)
        kernels = {"bits": official_kernel}
        if selected != "baseline":
            write_json(
                output / "confirmation-opened.json",
                dict(
                    opened_at=datetime.now(UTC).isoformat(),
                    selection_sha256=sha256_file(output / "selection.json"),
                ),
            )
            predictions, trace = fit_candidates(
                data.molecules, kernel, external, parents, pool, confirmation, started + MAX_SECONDS
            )
            write_json(output / "confirmation-fit-trace.json", trace)
            kernels["counts"] = tanimoto_kernel(features.counts, features.counts)
            fixed = fixed_other_targets(
                data.molecules, features, pool, features, confirmation, kernels, kernels
            )
            base_predictions = fixed | {TWO_D6: predictions["baseline"]}
            chosen_predictions = fixed | {TWO_D6: predictions[selected]}
            metrics: dict[str, dict[str, EndpointMetrics]] = {}
            for name, by_target in (("baseline", base_predictions), ("chosen", chosen_predictions)):
                metrics[name] = {}
                for target in TARGETS:
                    mask = data.molecules.loc[confirmation, target].notna().to_numpy()
                    rows = confirmation[mask]
                    metrics[name][target] = endpoint_statistics(
                        data.molecules.loc[rows, target].to_numpy(float),
                        by_target[target][mask],
                        data.molecules.loc[rows, target + "_conf_low"].to_numpy(float),
                        data.molecules.loc[rows, target + "_conf_high"].to_numpy(float),
                    )
            bootstrap = paired_bootstrap(
                data.molecules,
                data.encoded.groups,
                base_predictions,
                chosen_predictions,
                confirmation,
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
            # Append test identities/features only; external indices move after test rows.
            query_features = extract_features(data.test.SMILES.tolist())
            combined_frame = pd.concat([data.molecules, data.test], ignore_index=True)
            combined_parents = np.concatenate(
                [parents, [leakage_identity(s)[0] for s in data.test.SMILES]]
            )
            bits = np.vstack([features.bits, query_features.bits, external_features.bits])
            full_kernel = tanimoto_kernel(bits, bits)
            fit = purge_fit(
                np.arange(len(data.molecules)),
                np.arange(len(data.molecules), len(combined_frame)),
                combined_parents,
            )
            final, trace = fit_candidates(
                combined_frame,
                full_kernel,
                external,
                combined_parents,
                fit,
                np.arange(len(data.molecules), len(combined_frame)),
                started + MAX_SECONDS,
            )
            write_json(output / "full-fit-trace.json", trace)
            if "counts" not in kernels:
                kernels["counts"] = tanimoto_kernel(features.counts, features.counts)
            cross = {
                "bits": tanimoto_kernel(query_features.bits, features.bits),
                "counts": tanimoto_kernel(query_features.counts, features.counts),
            }
            out = data.test[list(IDENTIFIERS)].copy()
            out[TWO_D6] = final[selected]
            for target, prediction in fixed_other_targets(
                data.molecules,
                features,
                fit,
                query_features,
                np.arange(len(data.test)),
                kernels,
                cross,
            ).items():
                out[target] = prediction
            validate_submission(out, data.test)
            path = output / "regression.csv"
            out.to_csv(path, index=False)
            validate_submission(pd.read_csv(path), data.test)
            valid, errors = validate_activity_submission(path, set(data.test.Molecule_Name))
            if not valid:
                raise ValueError(f"Official validator rejected interval predictions: {errors}")
            submission = dict(path=str(path), sha256=sha256_file(path), official_validator=True)
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
            protocol_sha256=sha256_file(output / "protocol.json"),
            artifacts={
                str(p.name): sha256_file(p) for p in sorted(output.glob("*")) if p.is_file()
            },
        )
        write_json(output / "report.json", report)
    return report
