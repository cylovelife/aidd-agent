"""External predictions remain features; held-out official labels cannot train calibration.

@author cylovelife
"""

import numpy as np
import pandas as pd

from aidd_agent.external_data import exclude_official, leakage_identity
from aidd_agent.external_transfer import fit_calibrators, purge_fit, select_external
from aidd_agent.transfer_validation import TWO_D6


def test_global_external_exclusion_includes_parent_and_scaffold():
    smiles = ["CC[NH+](CC)CC.[Cl-]", "CCN(CC)CC", "Oc1ccccc1", "CC(=O)O"]
    keys = [leakage_identity(s) for s in smiles]
    f = pd.DataFrame(
        dict(
            smiles=smiles,
            parent=[k[0] for k in keys],
            scaffold=[k[1] for k in keys],
            accepted=True,
            source="pubchem891",
            class_label=[0, 0, 1, 0],
        )
    )
    kept, audit = exclude_official(f, ["CCN(CC)CC", "Nc1ccccc1"])
    assert kept.smiles.tolist() == ["CC(=O)O"]
    assert audit["official_parent_overlap_rows"] == 2
    assert audit["official_scaffold_overlap_rows"] == 3


def test_purge_removes_normalized_parent_variants_from_training():
    parents = np.array(["a", "b", "c", "a", "d"])
    np.testing.assert_array_equal(purge_fit(np.arange(3), np.array([3, 4]), parents), [1, 2])


def test_official_query_label_mutation_cannot_change_calibrated_prediction():
    rng = np.random.default_rng(19)
    n = 60
    x = rng.uniform(size=(n, 15))
    k = x @ x.T
    f = pd.DataFrame({TWO_D6: 2 + 4 * x[:, 0]})
    groups = np.array([f"g{i}" for i in range(n)])
    first, trace = fit_calibrators(
        f, k, x[:, :8], x[:, 8:10], groups, groups, np.arange(45), np.arange(45, 60)
    )
    f.loc[45:, TWO_D6] = 999
    again, _ = fit_calibrators(
        f, k, x[:, :8], x[:, 8:10], groups, groups, np.arange(45), np.arange(45, 60)
    )
    for name in first:
        np.testing.assert_allclose(first[name], again[name])
    assert all(set(row["fit"]).isdisjoint(np.arange(45, 60)) for row in trace)


def test_external_must_beat_identical_calibration_control_and_all_strata_exist():
    def row(model, st, low, high):
        return dict(
            split="s",
            endpoint=TWO_D6,
            model=model,
            st_rae=st,
            low_distance=low,
            high_distance=high,
            low_n=20,
            high_n=100,
        )

    records = []
    for split in ("s1", "s2", "s3"):
        records.extend(
            [
                r | {"split": split}
                for r in [
                    row("baseline", 1, 1, 1),
                    row("calibration_control", 0.7, 0.7, 0.8),
                    row("external_calibration", 0.8, 0.8, 0.9),
                    row("external_blend", 0.9, 0.9, 1),
                ]
            ]
        )
    assert select_external(records) == "baseline"
    for r in records:
        if r["model"] == "external_calibration":
            r["st_rae"] = 0.6
    assert select_external(records) == "external_calibration"
    records[-2]["low_n"] = 0
    assert select_external(records) == "baseline"
