"""Reconcile frozen readout predictions and provenance without additional fitting.

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
    prior = json.loads(Path("docs/round7-result.json").read_text())
    for name, digest in prior["artifacts_sha256"].items():
        if sha256_file(ROUND7 / name) != digest:
            raise ValueError("Round-seven artifacts changed")
    stored = pd.read_csv(run / "development-validation.csv")
    error = 0.0
    for split, rows in assignments.groupby("split"):
        valid = rows.loc[rows.partition.eq("valid"), "index"].to_numpy(int)
        frame = pd.read_csv(run / f"{split}-predictions.csv")
        if frame.Molecule_Name.tolist() != data.molecules.loc[valid, "Molecule_Name"].tolist():
            raise ValueError("Identity/order mismatch")
        for model in stored.model.unique():
            for target in TARGETS:
                y = data.molecules.loc[valid, target].to_numpy(float)
                p = frame[model + ":" + target].to_numpy(float)
                low = data.molecules.loc[valid, target + "_conf_low"].to_numpy(float)
                high = data.molecules.loc[valid, target + "_conf_high"].to_numpy(float)
                measured = np.isfinite(y)
                metrics = endpoint_statistics(
                    y[measured], p[measured], low[measured], high[measured]
                )
                saved = stored.loc[
                    stored.split.eq(split) & stored.model.eq(model) & stored.endpoint.eq(target)
                ].iloc[0]
                for metric in ("st_rae", "mae", "low_distance", "high_distance"):
                    error = max(error, abs(float(metrics[metric]) - float(saved[metric])))
    if error > 1e-10:
        raise ValueError("Metrics reconciliation failed")
    protocol = json.loads((run / "protocol.json").read_text())
    if not all(sha256_file(Path(p)) == digest for p, digest in protocol["source_sha256"].items()):
        raise ValueError("Experiment source changed")
    if sha256_file(Path("docs/round8-plan.md")) != protocol["plan_sha256"]:
        raise ValueError("Follow-up plan changed")
    if sha256_file(Path("uv.lock")) != protocol["uv_lock_sha256"]:
        raise ValueError("Dependency lock changed")
    diagnostic = Path("state/runs/20261101-round8-diagnostic-01")
    diagnostic_protocol = json.loads((diagnostic / "protocol.json").read_text())
    if (
        sha256_file(Path("state/sources/round8/diagnostic-readout.py"))
        != diagnostic_protocol["source_sha256"]
    ):
        raise ValueError("Diagnostic source snapshot changed")
    if sha256_file(Path("docs/round8-diagnostic-plan.md")) != diagnostic_protocol["plan_sha256"]:
        raise ValueError("Diagnostic plan changed")
    means = (
        stored.groupby(["model", "endpoint"])[["st_rae", "low_distance", "high_distance"]]
        .mean()
        .reset_index()
    )
    return {
        "report": json.loads((run / "report.json").read_text()),
        "provenance": provenance,
        "means": means.to_dict("records"),
        "macro_st_rae": stored.groupby("model").st_rae.mean().to_dict(),
        "max_reconciliation_error": error,
        "old_artifacts_unchanged": True,
        "source_and_plan_hashes_match": True,
        "confirmation_opened": (run / "confirmation-opened.json").exists(),
        "blind_csv_exists": (run / "regression.csv").exists(),
        "artifacts_sha256": {p.name: sha256_file(p) for p in sorted(run.glob("*")) if p.is_file()},
        "diagnostic_protocol": diagnostic_protocol,
        "diagnostic_report_sha256": sha256_file(diagnostic / "report.json"),
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
