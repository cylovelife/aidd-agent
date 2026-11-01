"""Representation ablation contracts on real molecular inputs.

@author cylovelife
"""

import numpy as np
import pytest

from aidd_agent.contracts import TARGETS
from aidd_agent.representation import (
    embedding_prediction,
    fingerprint_features,
    run_representation,
    select_development,
)


def test_chirality_is_the_only_new_discriminator():
    smiles = ["C[C@H](O)F", "C[C@@H](O)F"]
    plain = fingerprint_features(smiles, "baseline")
    chiral = fingerprint_features(smiles, "chiral_r2")
    np.testing.assert_array_equal(plain.bits[0], plain.bits[1])
    assert not np.array_equal(chiral.bits[0], chiral.bits[1])
    np.testing.assert_array_equal(plain.descriptors, chiral.descriptors)


def test_invalid_structure_and_variant_fail():
    with pytest.raises(ValueError):
        fingerprint_features(["not-a-molecule"], "radius3")
    with pytest.raises(ValueError):
        fingerprint_features(["CCO"], "unknown")


def test_embedding_regressor_fits_only_training_rows():
    x = np.array([[1.0, 2.0], [2.0, 1.0], [3.0, 5.0], [1e6, -1e6]])
    y = np.array([4.0, 5.0, 6.0, np.nan])
    fit, query = np.array([0, 1, 2]), np.array([3])
    a = embedding_prediction(x, x, y, fit, query)
    y[3] = -1e9
    np.testing.assert_allclose(a, embedding_prediction(x, x, y, fit, query))
    with pytest.raises(ValueError):
        embedding_prediction(x * np.nan, x, y, fit, query)


def test_development_requires_consistent_2d6_gain_and_macro_gain():
    records = []
    for split in ("a", "b", "c"):
        for target in TARGETS:
            for model in ("baseline", "radius3"):
                metric = 1.0 if model == "baseline" else 0.8
                records.append(
                    dict(
                        endpoint=target,
                        model=model,
                        split=split,
                        st_rae=metric,
                        low_distance=metric,
                        high_distance=metric,
                        measured_n=100,
                        low_n=25,
                        high_n=75,
                        mae=metric,
                        low_bias=0.0,
                        high_bias=0.0,
                    )
                )
    selected, eligible = select_development(records)
    assert eligible and set(selected.values()) == {"radius3"}
    for row in records:
        if row["model"] == "radius3" and row["endpoint"] == TARGETS[2]:
            row["low_distance"] = 1.01
    assert not select_development(records)[1]


def test_missing_or_existing_artifacts_fail_before_data_access(tmp_path):
    output = tmp_path / "new"
    with pytest.raises(ValueError, match="checkpoint required"):
        run_representation(tmp_path, tmp_path, output, tmp_path / "missing")
    assert not output.exists()
    with pytest.raises(ValueError, match="Fresh output"):
        run_representation(tmp_path, tmp_path, tmp_path, tmp_path / "missing")
