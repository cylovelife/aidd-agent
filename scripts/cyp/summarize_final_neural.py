"""Reconcile the last experiment, including inner split and provenance boundaries.

@author cylovelife
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from aidd_agent.contracts import TARGETS
from aidd_agent.readout import ROUND7, read_context
from aidd_agent.sources import sha256_file
from aidd_agent.transfer_validation import endpoint_statistics


def summarize(run: Path) -> dict[str, object]:
    data, _, assignments, provenance = read_context()
    old = json.loads(Path("docs/round7-result.json").read_text())
    if any(
        sha256_file(ROUND7 / name) != digest for name, digest in old["artifacts_sha256"].items()
    ):
        raise ValueError("Prior experiment artifacts changed")
    stored = pd.read_csv(run / "development-validation.csv")
    parts = pd.read_csv(ROUND7 / "confirmation-split.csv")
    heldout = set(parts.index[parts.partition.eq("confirmation")])
    trace = json.loads((run / "training-trace.json").read_text())
    for row in trace:
        saved_trace = run / f"{row['split']}-{row['model']}-trace.json"
        if json.loads(saved_trace.read_text()) != row:
            raise ValueError("Per-candidate trace missing or inconsistent")
        fit, valid = set(row["outer_fit"]), set(row["outer_valid"])
        expected = assignments.loc[assignments.split.eq(row["split"])]
        if fit != set(expected.loc[expected.partition.eq("fit"), "index"]) or valid != set(
            expected.loc[expected.partition.eq("valid"), "index"]
        ):
            raise ValueError("Frozen outer partition drift")
        a, b = set(row["inner_fit"]), set(row["inner_valid"])
        if (fit | valid) & heldout or fit & valid or a & b or (a | b) != fit:
            raise ValueError("Training/query/confirmation exclusion failure")
        if set(data.encoded.groups[list(a)]) & set(data.encoded.groups[list(b)]):
            raise ValueError("Inner scaffold exclusion failure")
        if row["best_epoch"] not in (4, 8, 12):
            raise ValueError("Unregistered stopping epoch")
    error = 0.0
    for split, rows in assignments.groupby("split"):
        valid = rows.loc[rows.partition.eq("valid"), "index"].to_numpy(int)
        frame = pd.read_csv(run / f"{split}-predictions.csv")
        if frame.Molecule_Name.tolist() != data.molecules.loc[valid, "Molecule_Name"].tolist():
            raise ValueError("Prediction identity/order drift")
        for model in stored.model.unique():
            for target in TARGETS:
                y = data.molecules.loc[valid, target].to_numpy(float)
                low = data.molecules.loc[valid, target + "_conf_low"].to_numpy(float)
                high = data.molecules.loc[valid, target + "_conf_high"].to_numpy(float)
                pred = frame[model + ":" + target].to_numpy(float)
                mask = np.isfinite(y)
                if not np.isfinite(pred).all():
                    raise ValueError("Nonfinite predictions")
                metrics = endpoint_statistics(y[mask], pred[mask], low[mask], high[mask])
                prior = stored.loc[
                    stored.split.eq(split) & stored.model.eq(model) & stored.endpoint.eq(target)
                ].iloc[0]
                for metric in ("st_rae", "mae", "low_distance", "high_distance"):
                    error = max(error, abs(float(metrics[metric]) - float(prior[metric])))
    protocol = json.loads((run / "protocol.json").read_text())
    if any(sha256_file(Path(p)) != digest for p, digest in protocol["source_sha256"].items()):
        raise ValueError("Run source hash mismatch")
    if sha256_file(Path("docs/final-round-plan.md")) != protocol["plan_sha256"]:
        raise ValueError("Plan hash mismatch")
    if sha256_file(Path("uv.lock")) != protocol["uv_lock_sha256"]:
        raise ValueError("Dependency lock mismatch")
    if error > 1e-10:
        raise ValueError("Metric reconciliation failed")
    return {
        "report": json.loads((run / "report.json").read_text()),
        "provenance": provenance,
        "means": stored.groupby(["model", "endpoint"])[["st_rae", "low_distance", "high_distance"]]
        .mean()
        .reset_index()
        .to_dict("records"),
        "macro_st_rae": stored.groupby("model").st_rae.mean().to_dict(),
        "best_epochs": [{k: r[k] for k in ("split", "model", "best_epoch")} for r in trace],
        "max_reconciliation_error": error,
        "exclusion_and_hash_checks_passed": True,
        "confirmation_opened": (run / "confirmation-opened.json").exists(),
        "blind_csv_exists": (run / "regression.csv").exists(),
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
