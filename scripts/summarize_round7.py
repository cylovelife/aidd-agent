"""Reconcile saved round-seven predictions without fitting or opening confirmation.

@author cylovelife
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from aidd_agent.auxiliary import load_auxiliary
from aidd_agent.contracts import TARGETS
from aidd_agent.features import tanimoto_kernel
from aidd_agent.representation import CANDIDATES, fingerprint_features
from aidd_agent.sources import sha256_file
from aidd_agent.transfer_validation import endpoint_statistics


def summarize(run: Path) -> dict[str, object]:
    data = load_auxiliary(Path("state/data/cyp"), Path("state/data/cyp-aux"))
    features = fingerprint_features(data.molecules.SMILES.tolist(), "baseline")
    partitions = pd.read_csv(run / "confirmation-split.csv")
    confirmation = set(partitions.index[partitions.partition.eq("confirmation")])
    assignments = pd.read_csv(run / "development-splits.csv")
    stored = pd.read_csv(run / "development-validation.csv")
    strata = []
    max_error = 0.0
    for name, rows in assignments.groupby("split"):
        fit = rows.loc[rows.partition.eq("fit"), "index"].to_numpy(int)
        valid = rows.loc[rows.partition.eq("valid"), "index"].to_numpy(int)
        if (set(fit) | set(valid)) & confirmation or set(fit) & set(valid):
            raise ValueError("Partition overlap")
        if set(data.encoded.canonical[i] for i in fit) & set(
            data.encoded.canonical[i] for i in valid
        ):
            raise ValueError("Molecule overlap")
        nearest = tanimoto_kernel(features.bits[valid], features.bits[fit]).max(axis=1)
        first = pd.read_csv(run / f"{name}-predictions.csv")
        second = pd.read_csv(run / f"{name}-chemeleon-predictions.csv")
        expected = data.molecules.loc[valid, "Molecule_Name"].tolist()
        if first.Molecule_Name.tolist() != expected or second.Molecule_Name.tolist() != expected:
            raise ValueError("Prediction identity/order mismatch")
        for model in CANDIDATES:
            source = second if model == "chemeleon" else first
            for target in TARGETS:
                y = data.molecules.loc[valid, target].to_numpy(float)
                low = data.molecules.loc[valid, target + "_conf_low"].to_numpy(float)
                high = data.molecules.loc[valid, target + "_conf_high"].to_numpy(float)
                pred = source[model + ":" + target].to_numpy(float)
                measured = np.isfinite(y)
                if not np.isfinite(pred).all():
                    raise ValueError("Nonfinite predictions")
                recomputed = endpoint_statistics(
                    y[measured], pred[measured], low[measured], high[measured]
                )
                row = stored.loc[
                    stored.split.eq(name) & stored.model.eq(model) & stored.endpoint.eq(target)
                ].iloc[0]
                for metric in ("st_rae", "mae", "low_distance", "high_distance"):
                    max_error = max(max_error, abs(float(recomputed[metric]) - float(row[metric])))
                for label, mask in (
                    ("similarity_lt_0.4", nearest < 0.4),
                    ("similarity_0.4_to_0.6", (nearest >= 0.4) & (nearest < 0.6)),
                    ("similarity_ge_0.6", nearest >= 0.6),
                ):
                    use = measured & mask
                    distance = np.maximum(low[use] - pred[use], 0) + np.maximum(
                        pred[use] - high[use], 0
                    )
                    strata.append(
                        {
                            "split": name,
                            "model": model,
                            "endpoint": target,
                            "stratum": label,
                            "n": int(use.sum()),
                            "interval_distance": float(distance.mean()) if use.any() else None,
                        }
                    )
    if max_error > 1e-10:
        raise ValueError("Saved metrics do not reconcile")
    means = (
        stored.groupby(["model", "endpoint"])[["st_rae", "low_distance", "high_distance"]]
        .mean()
        .reset_index()
        .to_dict("records")
    )
    return {
        "report": json.loads((run / "report.json").read_text()),
        "means": means,
        "similarity_strata": strata,
        "reconciliation_max_abs_error": max_error,
        "confirmation_partition_sha256": sha256_file(run / "confirmation-split.csv"),
        "artifacts_sha256": {p.name: sha256_file(p) for p in sorted(run.glob("*")) if p.is_file()},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.run)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
