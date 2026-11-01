"""Frozen round-seven representation ablations with one-use confirmation.

@author cylovelife
"""

import hashlib
import importlib.metadata
import json
import resource
import time
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from rdkit import Chem
from rdkit.Chem import rdFingerprintGenerator
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from aidd_agent.auxiliary import AuxiliaryData, load_auxiliary
from aidd_agent.baseline import write_json
from aidd_agent.contracts import IDENTIFIERS, TARGETS
from aidd_agent.features import MolecularFeatures, extract_features, tanimoto_kernel
from aidd_agent.optimization import BLEND, check_budget, predict_candidate
from aidd_agent.sources import sha256_file
from aidd_agent.transfer import evaluate_predictions, split_audit
from aidd_agent.transfer_models import BASELINE
from aidd_agent.transfer_validation import (
    TWO_D6,
    ScoreRecord,
    TransferSplit,
    choose_transfer_models,
    confirmation_gate,
    development_splits,
    freeze_confirmation,
    paired_bootstrap,
)

VARIANTS = ("baseline", "chiral_r2", "radius3", "feature_morgan")
CANDIDATES = (*VARIANTS, "chemeleon")
CONFIRMATION_SHA = "f9fa599c6d3f9536aa1d6c4e7cef9ea47f6159fba03950f994be34a3abb6104a"


def fingerprint_features(smiles: list[str], variant: str) -> MolecularFeatures:
    if variant not in VARIANTS:
        raise ValueError("Unknown fingerprint variant")
    base = extract_features(smiles)
    if variant == "baseline":
        return base
    options = {}
    if variant == "feature_morgan":
        options["atomInvariantsGenerator"] = rdFingerprintGenerator.GetMorganFeatureAtomInvGen()
    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=3 if variant == "radius3" else 2,
        fpSize=2048,
        includeChirality=variant == "chiral_r2",
        **options,
    )
    mols = [Chem.MolFromSmiles(s) for s in smiles]
    return MolecularFeatures(
        np.asarray([generator.GetFingerprintAsNumPy(m) for m in mols], dtype=float),
        np.log1p(np.asarray([generator.GetCountFingerprintAsNumPy(m) for m in mols], float)),
        base.descriptors,
        base.descriptor_names,
    )


def embedding_prediction(
    x: NDArray, other: NDArray, y: NDArray, fit: NDArray, query: NDArray
) -> NDArray:
    if not np.isfinite(x).all() or not np.isfinite(other).all():
        raise ValueError("Non-finite embeddings")
    model = make_pipeline(StandardScaler(), Ridge(alpha=10, solver="lsqr"))
    return np.asarray(model.fit(x[fit], y[fit]).predict(other[query]))


def chemeleon_embeddings(smiles: list[str], weights: Path, cache: Path) -> NDArray:
    """CPU-only frozen official message-passing weights; no labels or fine-tuning."""
    import torch
    from chemprop import data, featurizers, nn

    digest = hashlib.md5(weights.read_bytes(), usedforsecurity=False).hexdigest()
    if digest != "6a80b54fdb7de37ef0374d302f01e8ce":
        raise ValueError("Official CheMeleon checkpoint checksum mismatch")
    identity = {
        "smiles": smiles,
        "weights_sha256": sha256_file(weights),
        "source_sha256": sha256_file(Path(__file__)),
        "dependencies": {n: importlib.metadata.version(n) for n in ("chemprop", "rdkit", "torch")},
    }
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    cache.mkdir(parents=True, exist_ok=True)
    path, meta = cache / f"{key}.npy", cache / f"{key}.json"
    if path.exists() != meta.exists():
        raise ValueError("Incomplete embedding cache")
    if path.exists():
        if json.loads(meta.read_text())["sha256"] != sha256_file(path):
            raise ValueError("Embedding cache checksum mismatch")
        return np.load(path, allow_pickle=False)
    torch.set_num_threads(2)
    state = torch.load(weights, weights_only=True, map_location="cpu")
    mp = nn.BondMessagePassing(**state["hyper_parameters"])
    mp.load_state_dict(state["state_dict"], strict=True)
    mp.eval().requires_grad_(False)
    agg = nn.MeanAggregation()
    dataset = data.MoleculeDataset(
        [data.MoleculeDatapoint.from_smi(s) for s in smiles],
        featurizers.SimpleMoleculeMolGraphFeaturizer(),
    )
    loader = data.build_dataloader(dataset, batch_size=16, num_workers=0, shuffle=False)
    arrays = []
    started = time.monotonic()
    with torch.inference_mode():
        for batch in loader:
            arrays.append(agg(mp(batch.bmg), batch.bmg.batch).numpy())
            check_budget(started)
    result = np.concatenate(arrays).astype(float)
    if result.shape != (len(smiles), 2048) or not np.isfinite(result).all():
        raise ValueError("Unexpected CheMeleon embedding shape/value")
    with path.open("xb") as stream:
        np.save(stream, result, allow_pickle=False)
    write_json(
        meta,
        {**identity, "sha256": sha256_file(path), "elapsed_seconds": time.monotonic() - started},
    )
    return result


def model_predictions(
    data: AuxiliaryData,
    split: TransferSplit,
    features: dict[str, MolecularFeatures],
    kernels: dict[str, dict[str, NDArray]],
    embeddings: NDArray | None = None,
) -> dict[str, dict[str, NDArray]]:
    predictions: dict[str, dict[str, NDArray]] = {}
    for variant, feature in features.items():
        by_target = {}
        kernel = kernels[variant]
        for target in TARGETS:
            measured = data.molecules[target].notna().to_numpy()
            fit = split.fit[measured[split.fit]]
            y = data.molecules[target].to_numpy(float)[fit]
            low = data.molecules[target + "_conf_low"].to_numpy(float)[fit]
            high = data.molecules[target + "_conf_high"].to_numpy(float)[fit]
            name = BASELINE[target]
            names = BLEND if name == "blend" else {name: 1.0}
            by_target[target] = np.asarray(
                sum(
                    weight
                    * predict_candidate(
                        n, feature, fit, feature, split.valid, kernel, kernel, y, low, high
                    )
                    for n, weight in names.items()
                )
            )
        predictions[variant] = by_target
    if embeddings is not None:
        predictions["chemeleon"] = {}
        for target in TARGETS:
            measured = data.molecules[target].notna().to_numpy()
            fit = split.fit[measured[split.fit]]
            predictions["chemeleon"][target] = embedding_prediction(
                embeddings, embeddings, data.molecules[target].to_numpy(float), fit, split.valid
            )
    return predictions


def select_development(records: list[ScoreRecord]) -> tuple[dict[str, str], bool]:
    selected = choose_transfer_models(records)
    frame = pd.DataFrame(records)
    for target, name in selected.items():
        if name == "baseline":
            continue
        scores = frame.loc[frame.endpoint.eq(target)].pivot(
            index="split", columns="model", values="st_rae"
        )
        if int((scores[name] < scores.baseline).sum()) < 2:
            selected[target] = "baseline"
    means = frame.groupby(["endpoint", "model"]).st_rae.mean()
    old = np.mean([means.loc[(t, "baseline")] for t in TARGETS])
    new = np.mean([means.loc[(t, selected[t])] for t in TARGETS])
    eligible = selected[TWO_D6] != "baseline" and new <= old * 0.97
    return selected, bool(eligible)


def run_representation(
    data_dir: Path, aux_dir: Path, output: Path, weights: Path
) -> dict[str, object]:
    if output.exists():
        raise ValueError("Fresh output directory required")
    plan = Path("docs/round7-plan.md")
    if not plan.is_file() or not weights.is_file():
        raise ValueError("Frozen plan and checkpoint required before experiment")
    data = load_auxiliary(data_dir, aux_dir)
    output.mkdir(parents=True)
    write_json(
        output / "protocol.json",
        {
            "plan_sha256": sha256_file(plan),
            "candidates": CANDIDATES,
            "source_sha256": {
                str(p): sha256_file(p) for p in sorted(Path("src/aidd_agent").rglob("*.py"))
            },
            "uv_lock_sha256": sha256_file(Path("uv.lock")),
            "audit": data.audit,
            "weights_sha256": sha256_file(weights),
            "dependencies": {
                n: importlib.metadata.version(n)
                for n in ("rdkit", "numpy", "scikit-learn", "chemprop", "torch")
            },
            "threads": 2,
            "max_rss_bytes": 4 * 1024**3,
        },
    )
    pool, confirmation, seed = freeze_confirmation(data.molecules, data.encoded.groups)
    partitions = data.molecules[list(IDENTIFIERS)].copy()
    partitions["group"] = data.encoded.groups
    partitions["partition"] = "development"
    partitions.loc[confirmation, "partition"] = "confirmation"
    partitions.to_csv(output / "confirmation-split.csv", index=False)
    if sha256_file(output / "confirmation-split.csv") != CONFIRMATION_SHA:
        raise ValueError("Confirmation identity drift")
    write_json(
        output / "confirmation-lock.json",
        {"seed": seed, "opened": False, "sha256": CONFIRMATION_SHA},
    )
    started = time.monotonic()
    with threadpool_limits(limits=2):
        smiles = data.molecules.SMILES.tolist()
        features = {v: fingerprint_features(smiles, v) for v in VARIANTS}
        if len(features["baseline"].descriptor_names) != 217:
            raise ValueError("Descriptor registry drift")
        kernels = {
            v: {
                "bits": tanimoto_kernel(f.bits, f.bits),
                "counts": tanimoto_kernel(f.counts, f.counts),
            }
            for v, f in features.items()
        }
        # These kernels plus features consume <2GiB; discard variants before encoding if needed.
        splits = development_splits(
            data.molecules, data.encoded.groups, pool, kernels["baseline"]["bits"]
        )
        write_json(
            output / "development-audit.json",
            [split_audit(data, s, kernels["baseline"]["bits"]) for s in splits],
        )
        pd.DataFrame(
            [
                {"split": s.name, "index": int(i), "partition": part}
                for s in splits
                for part, indices in (("fit", s.fit), ("valid", s.valid))
                for i in indices
            ]
        ).to_csv(output / "development-splits.csv", index=False)
        records = []
        for split in splits:
            pred = model_predictions(data, split, features, kernels)
            records.extend(evaluate_predictions(data, split, pred))
            out = data.molecules.loc[split.valid, list(IDENTIFIERS)].copy()
            for name, targets in pred.items():
                for target, values in targets.items():
                    out[name + ":" + target] = values
            out.to_csv(output / (split.name + "-predictions.csv"), index=False)
            pd.DataFrame(records).to_csv(output / "development-validation.csv", index=False)
            check_budget(started)
        fingerprint_seconds = time.monotonic() - started
        encoding_started = time.monotonic()
        embeddings = chemeleon_embeddings(smiles, weights, Path("state/cache/round7-chemeleon"))
        for split in splits:
            pred = model_predictions(data, split, {}, {}, embeddings)
            records.extend(evaluate_predictions(data, split, pred))
            out = data.molecules.loc[split.valid, list(IDENTIFIERS)].copy()
            for target, values in pred["chemeleon"].items():
                out["chemeleon:" + target] = values
            out.to_csv(output / (split.name + "-chemeleon-predictions.csv"), index=False)
            check_budget(encoding_started)
        pd.DataFrame(records).to_csv(output / "development-validation.csv", index=False)
        selected, development_pass = select_development(records)
        write_json(
            output / "selection.json",
            {
                "selected": selected,
                "development_pass": development_pass,
                "confirmation_read": False,
            },
        )
        eligible, reasons = False, ["development_gate_failed"]
        if development_pass:
            prior = list(Path("state/runs").glob("*/confirmation-opened.json"))
            if prior:
                raise ValueError("Confirmation already opened in a previous run")
            write_json(
                output / "confirmation-opened.json",
                {"selection_sha256": sha256_file(output / "selection.json")},
            )
            split = TransferSplit("confirmation", pool, confirmation, True)
            pred = model_predictions(data, split, features, kernels, embeddings)
            chosen = {t: pred[selected[t]][t] for t in TARGETS}
            metrics = evaluate_predictions(
                data, split, {"baseline": pred["baseline"], "chosen": chosen}
            )
            bootstrap = paired_bootstrap(
                data.molecules, data.encoded.groups, pred["baseline"], chosen, confirmation
            )
            eligible, reasons = confirmation_gate(
                {r["endpoint"]: r for r in metrics if r["model"] == "baseline"},
                {r["endpoint"]: r for r in metrics if r["model"] == "chosen"},
                float(np.asarray(bootstrap["macro_difference_percentile_95"])[1]),
            )
            write_json(
                output / "confirmation-evaluation.json",
                {"metrics": metrics, "bootstrap": bootstrap},
            )
        report = {
            "selected": selected,
            "development_pass": development_pass,
            "submission_eligible": eligible,
            "gate_reasons": reasons,
            "confirmation_opened": development_pass,
            "fingerprint_seconds": fingerprint_seconds,
            "pretrained_seconds": time.monotonic() - encoding_started,
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "platform_submission": "not_submitted",
        }
        write_json(output / "report.json", report)
        # A successful gate hands off to full-fit/official validation, never an upload.
        return report
