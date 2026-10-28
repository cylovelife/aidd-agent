"""Finite-budget CYP regression experiment and reproducible submission artifact.

@author cylovelife
"""

import importlib.metadata
import json
import platform
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge
from threadpoolctl import threadpool_limits

from aidd_agent.chemistry import encode_molecules, split_groups
from aidd_agent.contracts import (
    IDENTIFIERS,
    TARGETS,
    load_identities,
    load_training,
    validate_submission,
)
from aidd_agent.metrics import score_endpoint
from aidd_agent.sources import sha256_file, verify_data
from aidd_agent.vendor.openadmet.activity_validation import validate_activity_submission

MODELS = ("median", "ridge", "extra_trees")


def make_model(name: str) -> DummyRegressor | Ridge | ExtraTreesRegressor:
    if name == "median":
        return DummyRegressor(strategy="median")
    if name == "ridge":
        return Ridge(alpha=10.0, solver="lsqr")
    if name == "extra_trees":
        return ExtraTreesRegressor(
            n_estimators=160, min_samples_leaf=2, max_features=0.7, random_state=42, n_jobs=2
        )
    raise ValueError(f"Unknown fixed candidate: {name}")


def write_json(path: Path, content: object) -> None:
    with path.open("x") as stream:
        json.dump(content, stream, indent=2, allow_nan=False)
        stream.write("\n")


def run_baseline(data_dir: Path, output_dir: Path) -> dict[str, object]:
    started = time.monotonic()
    manifest = verify_data(data_dir)
    train = load_training(data_dir / "cyp-challenge-TRAIN_inhibition.csv")
    test = load_identities(data_dir / "cyp-challenge-TEST-BLINDED.csv")
    if len(test) != 750:
        raise ValueError("Official test file must contain 750 molecules")
    if any(col in test and test[col].notna().any() for col in TARGETS):
        raise ValueError("Test labels are not blinded; refuse this first blind experiment")
    output_dir.mkdir(parents=True, exist_ok=False)
    protocol = {
        "created_at": datetime.now(UTC).isoformat(),
        "data_manifest": manifest,
        "seed": 42,
        "split": "Bemis-Murcko scaffold groups; canonical identity for acyclic molecules; 80/20",
        "features": "RDKit Morgan radius=2, 2048 bits; no target or assay features",
        "candidate_budget": list(MODELS),
        "selection": "minimum macro point-estimate ST-RAE among nonconstant model candidates",
        "metric_scope": "official endpoint function; point estimate without leaderboard bootstrap",
        "python": platform.python_version(),
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "pandas", "scikit-learn", "scipy", "rdkit")
        },
        "uv_lock_sha256": sha256_file(Path("uv.lock")),
        "source_sha256": {
            str(path): sha256_file(path) for path in sorted(Path("src/aidd_agent").rglob("*.py"))
        },
    }
    write_json(output_dir / "protocol.json", protocol)
    encoded = encode_molecules(train["SMILES"].tolist())
    test_encoded = encode_molecules(test["SMILES"].tolist())
    fit_indices, validation_indices = split_groups(encoded.groups, seed=42)
    split = train[list(IDENTIFIERS)].copy()
    split["canonical_smiles"] = encoded.canonical
    split["group"] = encoded.groups
    split["partition"] = "train"
    split.loc[validation_indices, "partition"] = "validation"
    split.to_csv(output_dir / "split.csv", index=False)
    audit = {
        "train_rows": len(train),
        "test_rows": len(test),
        "train_unique_canonical": len(set(encoded.canonical)),
        "test_unique_canonical": len(set(test_encoded.canonical)),
        "train_test_canonical_overlap": len(set(encoded.canonical) & set(test_encoded.canonical)),
        "scaffold_group_overlap": len(
            set(encoded.groups[fit_indices]) & set(encoded.groups[validation_indices])
        ),
        "training_partition_rows": len(fit_indices),
        "validation_partition_rows": len(validation_indices),
        "endpoint_measured_rows": {col: int(train[col].notna().sum()) for col in TARGETS},
        "split_sha256": sha256_file(output_dir / "split.csv"),
    }
    write_json(output_dir / "data-audit.json", audit)
    records = []
    candidates: dict[str, float] = {}
    with threadpool_limits(limits=2):
        for model_name in MODELS:
            endpoint_scores = []
            for col in TARGETS:
                measured = train[col].notna().to_numpy()
                fit = fit_indices[measured[fit_indices]]
                valid = validation_indices[measured[validation_indices]]
                if len(fit) < 50 or len(valid) < 20:
                    raise ValueError(f"Insufficient measured labels for frozen split: {col}")
                model = make_model(model_name)
                model.fit(encoded.fingerprints[fit], train.loc[fit, col].to_numpy(dtype=float))
                prediction = model.predict(encoded.fingerprints[valid])
                scores = score_endpoint(
                    train.loc[valid, col].to_numpy(dtype=float),
                    np.asarray(prediction, dtype=float),
                    train.loc[valid, col + "_conf_low"].to_numpy(dtype=float),
                    train.loc[valid, col + "_conf_high"].to_numpy(dtype=float),
                )
                endpoint_scores.append(scores["st_rae"])
                records.append(
                    {
                        "model": model_name,
                        "endpoint": col,
                        "train_n": len(fit),
                        "validation_n": len(valid),
                        **scores,
                    }
                )
            candidates[model_name] = float(np.mean(endpoint_scores))
        # Constant predictions are explicitly prohibited by the live submission backend.
        selected = min((name for name in MODELS if name != "median"), key=candidates.__getitem__)
        output = test[list(IDENTIFIERS)].copy()
        for col in TARGETS:
            measured = train[col].notna().to_numpy()
            model = make_model(selected)
            model.fit(
                encoded.fingerprints[measured], train.loc[measured, col].to_numpy(dtype=float)
            )
            output[col] = model.predict(test_encoded.fingerprints)
    validate_submission(output, test)
    submission = output_dir / "regression.csv"
    output.to_csv(submission, index=False)
    # Verify the actual serialized file, not only its in-memory predecessor.
    validate_submission(pd.read_csv(submission), test)
    official_valid, errors = validate_activity_submission(
        submission, expected_ids=set(test["Molecule_Name"])
    )
    if not official_valid:
        raise ValueError(f"Official validator rejected predictions: {errors}")
    pd.DataFrame(records).to_csv(output_dir / "validation.csv", index=False)
    summary: dict[str, object] = {
        "selected_model": selected,
        "macro_st_rae_point_estimates": candidates,
        "audit": audit,
        "protocol": protocol,
        "official_validator": {"valid": official_valid, "errors": errors},
        "submission": {
            "path": str(submission),
            "sha256": sha256_file(submission),
            "rows": len(output),
        },
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "platform_submission": "not_submitted",
        "interpretation": "Development holdout only; not an independent or official blind score.",
    }
    write_json(output_dir / "report.json", summary)
    return summary
