"""Primary-evidence integrity, normalized exclusions, fit isolation and frozen selection gates.

@author cylovelife
"""

import json

import numpy as np
import pandas as pd
import pytest

from aidd_agent.censored_data import load_reviewed_bounds
from aidd_agent.censored_transfer import fit_candidates, select_censored
from aidd_agent.sources import sha256_file
from aidd_agent.transfer_validation import TWO_D6


def test_primary_bounds_are_hash_locked_and_exclude_all_official_parent_scaffolds(tmp_path):
    smiles = ["CC[NH+](CC)CC.[Cl-]", "Oc1ccccc1", "CC(=O)O"]
    reviewed = pd.DataFrame(
        dict(activity_id=[1, 2, 3], canonical_smiles=smiles, decision="admit_censored")
    )
    admitted = pd.DataFrame(
        dict(
            activity_id=[1, 2, 3],
            smiles=smiles,
            source="study",
            evidence="SI",
            lower=-np.inf,
            upper=4.0,
            weight=0.25,
        )
    )
    reviewed.to_csv(tmp_path / "reviewed.csv", index=False)
    admitted.to_csv(tmp_path / "admitted.csv", index=False)
    proof = tmp_path / "si.txt"
    proof.write_text("primary observation")
    lock = dict(
        schema_version=1,
        reviewed_n=3,
        admitted_n=3,
        decisions={"admit_censored": 3},
        files={str(proof): sha256_file(proof)},
        artifacts={n: sha256_file(tmp_path / n) for n in ("reviewed.csv", "admitted.csv")},
    )
    (tmp_path / "audit-lock.json").write_text(json.dumps(lock))
    retained, audit = load_reviewed_bounds(tmp_path, ["CCN(CC)CC", "Nc1ccccc1"])
    assert retained.activity_id.tolist() == [3]
    assert audit["official_parent_overlap_rows"] == 1
    assert audit["official_scaffold_overlap_rows"] == 2
    proof.write_text("changed conclusion")
    with pytest.raises(ValueError, match="evidence hash mismatch"):
        load_reviewed_bounds(tmp_path, ["CCN(CC)CC"])


def test_query_labels_intervals_and_normalized_parent_cannot_enter_fitting():
    rng = np.random.default_rng(91)
    n, ext_n = 36, 2
    x = rng.uniform(size=(n + ext_n, 8))
    k = np.exp(-np.sum((x[:, None] - x[None, :]) ** 2, axis=2))
    y = 3 + x[:n, 0]
    frame = pd.DataFrame({TWO_D6: y, TWO_D6 + "_conf_low": y - 0.1, TWO_D6 + "_conf_high": y + 0.1})
    external = pd.DataFrame(dict(source=["s"] * ext_n, lower=-np.inf, upper=4.0, weight=0.25))
    parents = np.array([str(i) for i in range(n)])
    parents[0] = parents[30]
    fit, query = np.arange(30), np.arange(30, n)
    predictions, trace = fit_candidates(frame, k, external, parents, fit, query)
    frame.loc[query, :] = 999
    changed, _ = fit_candidates(frame, k, external, parents, fit, query)
    for name in predictions:
        np.testing.assert_allclose(predictions[name], changed[name], atol=1e-12)
    assert 0 not in trace["fit"]
    assert set(trace["fit"]).isdisjoint(query)
    assert trace["interval_transfer"]["external_fit_n"] == 2
    assert len(trace["interval_transfer"]["source_offsets"]) == 1
    assert trace["interval_control"]["external_fit_n"] == 0


def test_selection_requires_overall_low_high_and_two_split_wins():
    records = []
    for split in ("a", "b", "c"):
        for name, st, low, high in (
            ("baseline", 1.0, 1.0, 1.0),
            ("interval_control", 0.96, 0.89, 1.04),
            ("interval_transfer", 0.98, 0.8, 1.01),
            ("interval_blend", 0.99, 0.88, 1.0),
            ("control_blend_diagnostic", 0.7, 0.7, 0.7),
        ):
            records.append(
                dict(
                    split=split,
                    model=name,
                    st_rae=st,
                    low_distance=low,
                    high_distance=high,
                    low_n=20,
                    high_n=60,
                )
            )
    assert select_censored(records) == "interval_control"
    for row in records:
        if row["model"] == "interval_control":
            row["high_distance"] = 1.06
    assert select_censored(records) == "baseline"
    for row in records:
        if row["model"] == "interval_control":
            row["high_distance"] = 1.0
            row["low_n"] = 0 if row["split"] == "c" else 20
    assert select_censored(records) == "baseline"
