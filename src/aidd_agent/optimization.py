"""Frozen, bounded CYP candidate comparison with no leaderboard-based selection.

@author cylovelife
"""

import importlib.metadata
import resource
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.kernel_ridge import KernelRidge
from sklearn.linear_model import Ridge
from sklearn.svm import SVR
from threadpoolctl import threadpool_limits

from aidd_agent.baseline import write_json
from aidd_agent.chemistry import encode_molecules, split_groups
from aidd_agent.contracts import (
    IDENTIFIERS,
    TARGETS,
    load_identities,
    load_training,
    validate_submission,
)
from aidd_agent.features import MolecularFeatures, extract_features, tanimoto_kernel
from aidd_agent.metrics import score_endpoint
from aidd_agent.sources import sha256_file, verify_data
from aidd_agent.vendor.openadmet.activity_validation import validate_activity_submission

SEEDS = (42, 43, 44)
CANDIDATES = (
    "median",
    "ridge",
    "svr_bits_1",
    "svr_bits_10",
    "svr_counts",
    "krr_counts",
    "interval_svr",
    "extra_hybrid",
    "hist_descriptors",
    "blend",
)
BLEND = {"svr_counts": 0.5, "extra_hybrid": 0.25, "hist_descriptors": 0.25}
MAX_SECONDS = 1800
MAX_RSS_BYTES = 4 * 1024**3  # macOS resource.ru_maxrss is bytes.


def interval_targets(
    lower: NDArray,
    upper: NDArray,
) -> tuple[NDArray[np.int64], NDArray[np.float64], NDArray[np.float64]]:
    if (
        lower.ndim != 1
        or lower.shape != upper.shape
        or not lower.size
        or not np.isfinite(lower).all()
        or not np.isfinite(upper).all()
        or (lower > upper).any()
    ):
        raise ValueError("Invalid interval bounds")
    indices = np.tile(np.arange(len(lower), dtype=np.int64), 2)
    return indices, np.concatenate((lower, upper)).astype(float), np.full(len(indices), 0.5)


def select_candidates(
    scores: dict[str, dict[str, float]],
) -> tuple[dict[str, str], bool]:
    if not scores or any(
        not np.isfinite(list(values.values())).all() for values in scores.values()
    ):
        raise ValueError("Candidate scores must be finite and nonempty")
    selected = {
        target: min((name for name in values if name != "median"), key=values.__getitem__)
        for target, values in scores.items()
    }
    chosen = float(np.mean([scores[t][name] for t, name in selected.items()]))
    ridge = float(np.mean([v["ridge"] for v in scores.values()]))
    median = float(np.mean([v["median"] for v in scores.values()]))
    return selected, chosen <= ridge * 0.95 and chosen < median


def predict_candidate(
    name: str,
    features: MolecularFeatures,
    fit: NDArray[np.int64],
    other: MolecularFeatures,
    valid: NDArray[np.int64],
    kernels: dict[str, NDArray],
    cross_kernels: dict[str, NDArray],
    y: NDArray,
    lower: NDArray,
    upper: NDArray,
) -> NDArray[np.float64]:
    if not (np.isfinite(y).all() and len(y) == len(fit)):
        raise ValueError("Fit only measured finite endpoint labels")
    if name == "median":
        return np.full(len(valid), np.median(y))
    if name == "ridge":
        model = Ridge(alpha=10, solver="lsqr")
        return np.asarray(model.fit(features.bits[fit], y).predict(other.bits[valid]))
    if name in ("extra_hybrid", "hist_descriptors"):
        if name == "extra_hybrid":
            trees = ExtraTreesRegressor(
                n_estimators=240,
                min_samples_leaf=3,
                max_features=0.5,
                random_state=42,
                n_jobs=2,
            )
            return np.asarray(trees.fit(features.hybrid[fit], y).predict(other.hybrid[valid]))
        hist = HistGradientBoostingRegressor(
            loss="absolute_error",
            max_iter=200,
            max_leaf_nodes=15,
            learning_rate=0.05,
            l2_regularization=2,
            early_stopping=False,
            random_state=42,
        )
        return np.asarray(hist.fit(features.descriptors[fit], y).predict(other.descriptors[valid]))
    kernel_name = "bits" if name.startswith("svr_bits") else "counts"
    matrix = kernels[kernel_name][np.ix_(fit, fit)]
    cross = cross_kernels[kernel_name][np.ix_(valid, fit)]
    if name == "krr_counts":
        # Center with the fit labels only; the kernel model has no intercept.
        center = float(np.mean(y))
        return np.asarray(
            KernelRidge(alpha=1, kernel="precomputed").fit(matrix, y - center).predict(cross)
            + center
        )
    if name == "interval_svr":
        indices, target, weights = interval_targets(lower, upper)
        interval_model = SVR(C=5, epsilon=0, kernel="precomputed", cache_size=256)
        interval_model.fit(matrix[np.ix_(indices, indices)], target, sample_weight=weights)
        return np.asarray(interval_model.predict(cross[:, indices]))
    if name not in ("svr_counts", "svr_bits_1", "svr_bits_10"):
        raise ValueError(f"Unknown frozen candidate: {name}")
    svr = SVR(
        C=1 if name == "svr_bits_1" else 10, epsilon=0.1, kernel="precomputed", cache_size=256
    )
    return np.asarray(svr.fit(matrix, y).predict(cross))


def check_budget(started: float) -> None:
    if time.monotonic() - started > MAX_SECONDS:
        raise RuntimeError("Frozen wall-time budget exceeded; inspect partial artifacts")
    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > MAX_RSS_BYTES:
        raise RuntimeError("Frozen memory budget exceeded; inspect partial artifacts")


def run_optimization(data_dir: Path, output_dir: Path) -> dict[str, object]:
    started = time.monotonic()
    manifest = verify_data(data_dir)
    train = load_training(data_dir / "cyp-challenge-TRAIN_inhibition.csv")
    test = load_identities(data_dir / "cyp-challenge-TEST-BLINDED.csv")
    if len(test) != 750 or any(col in test and test[col].notna().any() for col in TARGETS):
        raise ValueError("Expected 750 blinded official test identities")
    output_dir.mkdir(parents=True, exist_ok=False)
    protocol = {
        "created_at": datetime.now(UTC).isoformat(),
        "data_manifest": manifest,
        "seeds": SEEDS,
        "candidates": CANDIDATES,
        "blend_weights": BLEND,
        "plan_sha256": sha256_file(Path("docs/round2-plan.md")),
        "uv_lock_sha256": sha256_file(Path("uv.lock")),
        "source_sha256": {
            str(p): sha256_file(p) for p in sorted(Path("src/aidd_agent").rglob("*.py"))
        },
        "dependencies": {
            n: importlib.metadata.version(n)
            for n in ("numpy", "pandas", "rdkit", "scikit-learn", "scipy")
        },
        "max_seconds": MAX_SECONDS,
        "max_rss_bytes": MAX_RSS_BYTES,
        "threads": 2,
        "selection": (
            "per-endpoint minimum mean ST-RAE over three scaffold development splits; "
            "exclude median"
        ),
        "scope": "Development selection, including reused seed 42; not independent test evidence",
    }
    write_json(output_dir / "protocol.json", protocol)
    encoded = encode_molecules(train.SMILES.tolist())
    test_encoded = encode_molecules(test.SMILES.tolist())
    if set(encoded.canonical) & set(test_encoded.canonical):
        raise ValueError("Training/test molecule identity overlap")
    records: list[dict[str, object]] = []
    predictions: list[pd.DataFrame] = []
    splits = []
    for seed in SEEDS:
        fit, valid = split_groups(encoded.groups, seed)
        split = pd.DataFrame(
            {
                "seed": seed,
                "Molecule_Name": train.Molecule_Name,
                "canonical_smiles": encoded.canonical,
                "group": encoded.groups,
                "partition": "train",
            }
        )
        split.loc[valid, "partition"] = "validation"
        splits.append(split)
    pd.concat(splits).to_csv(output_dir / "splits.csv", index=False)
    with threadpool_limits(limits=2):
        features = extract_features(train.SMILES.tolist())
        test_features = extract_features(test.SMILES.tolist())
        write_json(
            output_dir / "features.json",
            {
                "descriptors": features.descriptor_names,
                "bits": 2048,
                "counts": "log1p Morgan count 2048",
                "radius": 2,
            },
        )
        kernels = {
            "bits": tanimoto_kernel(features.bits, features.bits),
            "counts": tanimoto_kernel(features.counts, features.counts),
        }
        cross = {
            "bits": tanimoto_kernel(test_features.bits, features.bits),
            "counts": tanimoto_kernel(test_features.counts, features.counts),
        }
        audit = {
            "train_rows": len(train),
            "test_rows": len(test),
            "canonical_overlap": 0,
            "test_nearest_train_bit_tanimoto_quantiles": np.quantile(
                cross["bits"].max(axis=1), [0, 0.25, 0.5, 0.75, 1]
            ).tolist(),
            "measured_labels": {t: int(train[t].notna().sum()) for t in TARGETS},
        }
        write_json(output_dir / "audit.json", audit)
        for seed in SEEDS:
            fit_all, valid_all = split_groups(encoded.groups, seed)
            for target in TARGETS:
                measured = train[target].notna().to_numpy()
                fit, valid = fit_all[measured[fit_all]], valid_all[measured[valid_all]]
                if len(fit) < 50 or len(valid) < 20:
                    raise ValueError(f"Insufficient measured labels: {seed}/{target}")
                y = train.loc[fit, target].to_numpy(dtype=float)
                lower = train.loc[fit, target + "_conf_low"].to_numpy(dtype=float)
                upper = train.loc[fit, target + "_conf_high"].to_numpy(dtype=float)
                cached: dict[str, NDArray] = {}
                for name in CANDIDATES:
                    check_budget(started)
                    begin = time.monotonic()
                    pred = (
                        sum(cached[n] * w for n, w in BLEND.items())
                        if name == "blend"
                        else predict_candidate(
                            name, features, fit, features, valid, kernels, kernels, y, lower, upper
                        )
                    )
                    cached[name] = np.asarray(pred)
                    scores = score_endpoint(
                        train.loc[valid, target].to_numpy(dtype=float),
                        cached[name],
                        train.loc[valid, target + "_conf_low"].to_numpy(dtype=float),
                        train.loc[valid, target + "_conf_high"].to_numpy(dtype=float),
                    )
                    records.append(
                        {
                            "seed": seed,
                            "endpoint": target,
                            "model": name,
                            "fit_n": len(fit),
                            "valid_n": len(valid),
                            **scores,
                            "seconds": time.monotonic() - begin,
                        }
                    )
                    predictions.append(
                        pd.DataFrame(
                            {
                                "seed": seed,
                                "endpoint": target,
                                "model": name,
                                "Molecule_Name": train.loc[valid, "Molecule_Name"].to_numpy(),
                                "prediction": cached[name],
                            }
                        )
                    )
                # Preserve completed endpoint evidence if a later candidate fails or exceeds budget.
                pd.DataFrame(records).to_csv(output_dir / "validation.csv", index=False)
        pd.concat(predictions).to_csv(output_dir / "validation-predictions.csv", index=False)
        frame = pd.DataFrame(records)
        means = frame.groupby(["endpoint", "model"]).st_rae.mean().unstack()
        scores_by_target = {
            t: {n: float(np.asarray(means.loc[t, n]).item()) for n in CANDIDATES} for t in TARGETS
        }
        selected, gate = select_candidates(scores_by_target)
        write_json(
            output_dir / "selection.json",
            {"selected": selected, "gate": gate, "means": scores_by_target},
        )
        if not gate:
            raise ValueError("Frozen improvement gate failed; do not replace the prior submission")
        output = test[list(IDENTIFIERS)].copy()
        for target, name in selected.items():
            fit = np.flatnonzero(train[target].notna().to_numpy())
            needed = BLEND if name == "blend" else {name: 1.0}
            output[target] = sum(
                weight
                * predict_candidate(
                    member,
                    features,
                    fit,
                    test_features,
                    np.arange(len(test)),
                    kernels,
                    cross,
                    train.loc[fit, target].to_numpy(dtype=float),
                    train.loc[fit, target + "_conf_low"].to_numpy(dtype=float),
                    train.loc[fit, target + "_conf_high"].to_numpy(dtype=float),
                )
                for member, weight in needed.items()
            )
            check_budget(started)
    validate_submission(output, test)
    path = output_dir / "regression.csv"
    output.to_csv(path, index=False)
    validate_submission(pd.read_csv(path), test)
    official_valid, errors = validate_activity_submission(
        path, expected_ids=set(test.Molecule_Name)
    )
    if not official_valid:
        raise ValueError(f"Official validator rejected predictions: {errors}")
    report = {
        "selected": selected,
        "gate": gate,
        "mean_scores": scores_by_target,
        "macro_selected": float(np.mean([scores_by_target[t][n] for t, n in selected.items()])),
        "macro_ridge": float(means.ridge.mean()),
        "macro_median": float(means["median"].mean()),
        "submission_sha256": sha256_file(path),
        "splits_sha256": sha256_file(output_dir / "splits.csv"),
        "elapsed_seconds": time.monotonic() - started,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "official_validator": {"valid": official_valid, "errors": errors},
        "platform_submission": "not_submitted",
        "scope": protocol["scope"],
        "audit": audit,
    }
    write_json(output_dir / "report.json", report)
    return report
