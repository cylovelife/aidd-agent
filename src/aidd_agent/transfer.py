"""Reproducible third-round transfer experiment with a conservative upload gate.

@author cylovelife
"""

import hashlib
import importlib.metadata
import json
import resource
import time
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from aidd_agent.auxiliary import AuxiliaryData, load_auxiliary
from aidd_agent.baseline import write_json
from aidd_agent.contracts import IDENTIFIERS, TARGETS, validate_submission
from aidd_agent.features import MolecularFeatures, extract_features, tanimoto_kernel
from aidd_agent.optimization import check_budget
from aidd_agent.sources import sha256_file
from aidd_agent.transfer_models import TRANSFER_CANDIDATES, CandidateFitter, fit_transfer_candidates
from aidd_agent.transfer_validation import (
    TWO_D6,
    ScoreRecord,
    TransferSplit,
    choose_transfer_models,
    confirmation_gate,
    development_splits,
    endpoint_statistics,
    freeze_confirmation,
    paired_bootstrap,
)
from aidd_agent.vendor.openadmet.activity_validation import validate_activity_submission


def cached_features(data: AuxiliaryData, directory: Path) -> MolecularFeatures:
    identity = {
        "smiles": data.molecules.SMILES.tolist(),
        "feature_source_sha256": sha256_file(Path("src/aidd_agent/features.py")),
        "rdkit": importlib.metadata.version("rdkit"),
    }
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (digest + ".npz")
    meta = directory / (digest + ".json")
    if path.exists() != meta.exists():
        raise ValueError("Incomplete feature cache; inspect it instead of overwriting")
    if path.exists():
        with meta.open() as stream:
            info = json.load(stream)
        if info["sha256"] != sha256_file(path) or info["identity_sha256"] != digest:
            raise ValueError("Feature cache provenance/hash mismatch")
        with np.load(path, allow_pickle=False) as arrays:
            return MolecularFeatures(
                arrays["bits"],
                arrays["counts"],
                arrays["descriptors"],
                tuple(info["descriptor_names"]),
            )
    features = extract_features(data.molecules.SMILES.tolist())
    with path.open("xb") as stream:
        np.savez_compressed(
            stream, bits=features.bits, counts=features.counts, descriptors=features.descriptors
        )
    write_json(
        meta,
        {
            "sha256": sha256_file(path),
            "identity_sha256": digest,
            "descriptor_names": features.descriptor_names,
            "scope": "Deterministic label-free features; no fitted parameters or labels",
        },
    )
    return features


def split_audit(data: AuxiliaryData, split: TransferSplit, kernel: np.ndarray) -> dict[str, object]:
    if set(data.encoded.canonical[i] for i in split.fit) & set(
        data.encoded.canonical[i] for i in split.valid
    ):
        raise ValueError("Outer molecule identities overlap")
    overlap = len(set(data.encoded.groups[split.fit]) & set(data.encoded.groups[split.valid]))
    if split.scaffold_disjoint and overlap:
        raise ValueError("Outer scaffold groups overlap")
    return {
        "name": split.name,
        "fit_n": len(split.fit),
        "valid_n": len(split.valid),
        "scaffold_group_overlap": overlap,
        "nearest_fit_tanimoto_quantiles": np.quantile(
            kernel[np.ix_(split.valid, split.fit)].max(axis=1), [0, 0.25, 0.5, 0.75, 1]
        ).tolist(),
        "labels": {
            t: {
                "fit": int(data.molecules.loc[split.fit, t].notna().sum()),
                "valid": int(data.molecules.loc[split.valid, t].notna().sum()),
                "valid_low": int(data.molecules.loc[split.valid, t].lt(4).sum()),
            }
            for t in TARGETS
        },
    }


def evaluate_predictions(
    data: AuxiliaryData,
    split: TransferSplit,
    predictions: dict[str, dict[str, np.ndarray]],
) -> list[ScoreRecord]:
    records: list[ScoreRecord] = []
    for name, by_target in predictions.items():
        for target, prediction in by_target.items():
            measured = data.molecules.loc[split.valid, target].notna().to_numpy()
            rows = split.valid[measured]
            metrics = endpoint_statistics(
                data.molecules.loc[rows, target].to_numpy(float),
                prediction[measured],
                data.molecules.loc[rows, target + "_conf_low"].to_numpy(float),
                data.molecules.loc[rows, target + "_conf_high"].to_numpy(float),
            )
            records.append({"split": split.name, "model": name, "endpoint": target, **metrics})
    return records


def run_transfer(
    data_dir: Path,
    aux_dir: Path,
    output_dir: Path,
    neural: bool = False,
) -> dict[str, object]:
    started = time.monotonic()
    if output_dir.exists():
        raise ValueError("Output directory already exists; preserve the previous experiment")
    data = load_auxiliary(data_dir, aux_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    predictor: CandidateFitter = fit_transfer_candidates
    candidates: tuple[str, ...] = TRANSFER_CANDIDATES
    dependencies: tuple[str, ...] = ("numpy", "pandas", "rdkit", "scikit-learn", "scipy")
    if neural:
        from aidd_agent.neural_transfer import NEURAL_CANDIDATES, fit_neural_candidates

        def progress(record: dict[str, object]) -> None:
            with (output_dir / "neural-training.jsonl").open("a") as stream:
                json.dump(
                    {**record, "elapsed_seconds": time.monotonic() - started},
                    stream,
                    allow_nan=False,
                )
                stream.write("\n")

        predictor = partial(fit_neural_candidates, deadline=started + 1700, progress=progress)
        candidates = NEURAL_CANDIDATES
        dependencies = (*dependencies, "torch")
    protocol = {
        "created_at": datetime.now(UTC).isoformat(),
        "candidates": candidates,
        "stage": "B" if neural else "A",
        "plan_sha256": sha256_file(
            Path("docs/round3b-plan.md" if neural else "docs/round3-plan.md")
        ),
        "audit": data.audit,
        "source_sha256": {
            str(p): sha256_file(p) for p in sorted(Path("src/aidd_agent").rglob("*.py"))
        },
        "uv_lock_sha256": sha256_file(Path("uv.lock")),
        "dependencies": {n: importlib.metadata.version(n) for n in dependencies},
        "scope": (
            "This-round independent confirmation after development selection; "
            "not historically untouched or equivalent to blind labels"
        ),
        "threads": 2,
        "max_seconds": 1700 if neural else 1800,
        "max_rss_bytes": 4 * 1024**3,
    }
    write_json(output_dir / "protocol.json", protocol)
    pool, confirmation, seed = freeze_confirmation(data.molecules, data.encoded.groups)
    partitions = data.molecules[list(IDENTIFIERS)].copy()
    partitions["group"] = data.encoded.groups
    partitions["partition"] = "development"
    partitions.loc[confirmation, "partition"] = "confirmation"
    partitions.to_csv(output_dir / "confirmation-split.csv", index=False)
    if neural and sha256_file(output_dir / "confirmation-split.csv") != (
        "f9fa599c6d3f9536aa1d6c4e7cef9ea47f6159fba03950f994be34a3abb6104a"
    ):
        raise ValueError("Stage B must preserve the exact unopened Stage A confirmation partition")
    write_json(
        output_dir / "confirmation-lock.json",
        {
            "seed": seed,
            "split_sha256": sha256_file(output_dir / "confirmation-split.csv"),
            "opened": False,
            "development_pool_rows": len(pool),
            "confirmation_rows": len(confirmation),
        },
    )
    records: list[ScoreRecord] = []
    with threadpool_limits(limits=2):
        features = cached_features(data, Path("state/cache/round3-features"))
        kernels = {
            "bits": tanimoto_kernel(features.bits, features.bits),
            "counts": tanimoto_kernel(features.counts, features.counts),
        }
        splits = development_splits(data.molecules, data.encoded.groups, pool, kernels["bits"])
        audits = [split_audit(data, s, kernels["bits"]) for s in splits]
        write_json(output_dir / "development-audit.json", audits)
        assignment: list[dict[str, object]] = []
        for split in splits:
            assignment.extend(
                {"split": split.name, "index": int(i), "partition": "fit"} for i in split.fit
            )
            assignment.extend(
                {"split": split.name, "index": int(i), "partition": "valid"} for i in split.valid
            )
        pd.DataFrame(assignment).to_csv(output_dir / "development-splits.csv", index=False)
        for split in splits:
            check_budget(started)
            predictions, screen, trace = predictor(
                data.molecules,
                data.screen,
                data.encoded.groups,
                features,
                features,
                kernels,
                kernels,
                split.fit,
                split.valid,
            )
            write_json(output_dir / (split.name + "-exclusion-trace.json"), trace)
            screen_measured = np.isfinite(data.screen[split.valid]).all(axis=1)
            if screen is not None:
                write_json(
                    output_dir / (split.name + "-screen-validation.json"),
                    {
                        "rows": int(screen_measured.sum()),
                        "rmse_per_cyp": np.sqrt(
                            np.mean(
                                (
                                    screen[screen_measured]
                                    - data.screen[split.valid][screen_measured]
                                )
                                ** 2,
                                axis=0,
                            )
                        ).tolist(),
                        "scope": (
                            "Auxiliary log2fc error only; never labels for missing direct pIC50"
                        ),
                    },
                )
            records.extend(evaluate_predictions(data, split, predictions))
            pd.DataFrame(records).to_csv(output_dir / "development-validation.csv", index=False)
            out = data.molecules.loc[split.valid, list(IDENTIFIERS)].copy()
            for name, by_target in predictions.items():
                for target, pred in by_target.items():
                    out[name + ":" + target] = pred
            out.to_csv(output_dir / (split.name + "-predictions.csv"), index=False)
            check_budget(started)
        selected = choose_transfer_models(records)
        write_json(
            output_dir / "selection.json",
            {
                "selected": selected,
                "selected_at": datetime.now(UTC).isoformat(),
                "confirmation_read_for_selection": False,
            },
        )
        eligible = False
        reasons = ["development_no_eligible_2d6_model"]
        confirmation_result: dict[str, object] = {"opened": False}
        if selected[TWO_D6] != "baseline":
            split = TransferSplit("confirmation", pool, confirmation, True)
            write_json(
                output_dir / "confirmation-opened.json",
                {
                    "opened_at": datetime.now(UTC).isoformat(),
                    "selection_sha256": sha256_file(output_dir / "selection.json"),
                    "audit": split_audit(data, split, kernels["bits"]),
                },
            )
            predictions, screen, trace = predictor(
                data.molecules,
                data.screen,
                data.encoded.groups,
                features,
                features,
                kernels,
                kernels,
                pool,
                confirmation,
                requested=frozenset({"baseline", *selected.values()}),
            )
            chosen = {t: predictions[n][t] for t, n in selected.items()}
            pair = {"baseline": predictions["baseline"], "chosen": chosen}
            rows = evaluate_predictions(data, split, pair)
            write_json(output_dir / "confirmation-exclusion-trace.json", trace)
            bootstrap = paired_bootstrap(
                data.molecules, data.encoded.groups, predictions["baseline"], chosen, confirmation
            )
            base_metrics = {row["endpoint"]: row for row in rows if row["model"] == "baseline"}
            chosen_metrics = {row["endpoint"]: row for row in rows if row["model"] == "chosen"}
            upper = float(np.asarray(bootstrap["macro_difference_percentile_95"])[1])
            eligible, reasons = confirmation_gate(base_metrics, chosen_metrics, upper)
            confirmation_result = {"opened": True, "metrics": rows, "bootstrap": bootstrap}
            write_json(output_dir / "confirmation-evaluation.json", confirmation_result)
            check_budget(started)
        submission: dict[str, object] | None = None
        if eligible:
            query = extract_features(data.test.SMILES.tolist())
            cross = {
                "bits": tanimoto_kernel(query.bits, features.bits),
                "counts": tanimoto_kernel(query.counts, features.counts),
            }
            final, _, trace = predictor(
                data.molecules,
                data.screen,
                data.encoded.groups,
                features,
                query,
                kernels,
                cross,
                np.arange(len(data.molecules)),
                np.arange(len(data.test)),
                requested=frozenset(selected.values()),
            )
            out = data.test[list(IDENTIFIERS)].copy()
            for target, name in selected.items():
                out[target] = final[name][target]
            validate_submission(out, data.test)
            path = output_dir / "regression.csv"
            out.to_csv(path, index=False)
            validate_submission(pd.read_csv(path), data.test)
            valid, errors = validate_activity_submission(
                path, expected_ids=set(data.test.Molecule_Name)
            )
            if not valid:
                raise ValueError(f"Official validator rejected transfer artifact: {errors}")
            submission = {
                "path": str(path),
                "sha256": sha256_file(path),
                "official_validator": True,
            }
            write_json(output_dir / "full-fit-exclusion-trace.json", trace)
        report: dict[str, object] = {
            "stage": "B" if neural else "A",
            "submission_eligible": eligible,
            "gate_reasons": reasons,
            "selected": selected,
            "confirmation": confirmation_result,
            "submission": submission,
            "platform_submission": "not_submitted",
            "audit": data.audit,
            "elapsed_seconds": time.monotonic() - started,
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "protocol_sha256": sha256_file(output_dir / "protocol.json"),
            "interpretation": "No blind improvement is claimed; failed local gates prohibit upload",
        }
        check_budget(started)
        write_json(output_dir / "report.json", report)
    return report
