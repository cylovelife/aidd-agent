"""Leakage and scientific decision boundaries for auxiliary-assay transfer.

@author cylovelife
"""

import numpy as np
import pandas as pd
import pytest

from aidd_agent.contracts import TARGETS
from aidd_agent.features import MolecularFeatures
from aidd_agent.transfer import run_transfer
from aidd_agent.transfer_models import crossfit_screen, fit_transfer_candidates
from aidd_agent.transfer_validation import (
    choose_transfer_models,
    confirmation_gate,
    development_splits,
    freeze_confirmation,
    paired_bootstrap,
)


def test_outer_auxiliary_mutation_cannot_change_training_or_query_prediction():
    rng = np.random.default_rng(4)
    x = rng.normal(size=(18, 5))
    k = x @ x.T
    aux = rng.normal(size=(18, 4))
    groups = np.array([f"g{i // 2}" for i in range(18)])
    fit, query = np.arange(14), np.arange(14, 18)
    first, predicted, trace = crossfit_screen(k, k, aux, groups, fit, query)
    changed = aux.copy()
    changed[query] = 99999
    second, again, _ = crossfit_screen(k, k, changed, groups, fit, query)
    np.testing.assert_allclose(first, second)
    np.testing.assert_allclose(predicted, again)
    for row in trace:
        assert set(row["aux_fit"]).isdisjoint(query)
        assert set(groups[row["aux_fit"]]).isdisjoint(groups[row["valid"]])
    assert np.isfinite(first).all()


def test_missing_auxiliary_rows_get_predictions_without_invented_labels():
    rng = np.random.default_rng(8)
    x = rng.normal(size=(18, 5))
    aux = rng.normal(size=(18, 4))
    aux[0] = np.nan
    groups = np.array([f"g{i}" for i in range(18)])
    pred, _, trace = crossfit_screen(
        x @ x.T, x @ x.T, aux, groups, np.arange(15), np.arange(15, 18)
    )
    assert np.isfinite(pred).all()
    assert np.isnan(aux[0]).all()
    assert all(0 not in row["aux_fit"] for row in trace)


def score(st=1.0, low=1.0, high=1.0):
    return {
        "st_rae": st,
        "low_distance": low,
        "high_distance": high,
        "measured_n": 200,
        "low_n": 30,
        "high_n": 170,
    }


def test_good_average_cannot_hide_low_activity_failure():
    baseline = {f"CYP{i}": score() for i in range(4)}
    baseline["CYP2D6_pIC50_direct_inhibition"] = score()
    candidate = {t: score(0.8, 0.7, 0.9) for t in baseline}
    assert confirmation_gate(baseline, candidate, -0.01)[0]
    candidate["CYP2D6_pIC50_direct_inhibition"] = score(0.8, 1.1, 0.7)
    assert not confirmation_gate(baseline, candidate, -0.01)[0]
    candidate["CYP2D6_pIC50_direct_inhibition"] = score(0.8, 0.7, 0.9)
    assert not confirmation_gate(baseline, candidate, 0.01)[0]


def test_development_selection_keeps_baseline_if_auxiliary_transfer_hurts_low_group():
    target = "CYP2D6_pIC50_direct_inhibition"
    rows = [
        {"endpoint": target, "model": "baseline", **score()},
        {"endpoint": target, "model": "screen_linear", **score(0.8, 1.1, 0.7)},
    ]
    assert choose_transfer_models(rows)[target] == "baseline"


def test_crossfit_refuses_too_few_groups():
    with pytest.raises(ValueError, match="groups"):
        crossfit_screen(
            np.eye(5),
            np.eye(5),
            np.ones((5, 4)),
            np.array(["same"] * 5),
            np.arange(4),
            np.array([4]),
        )


def test_confirmation_groups_never_enter_any_development_partition():
    frame = pd.DataFrame({t: np.linspace(2, 7, 600) for t in TARGETS})
    groups = np.array([f"g{i}" for i in range(600)])
    pool, heldout, seed = freeze_confirmation(frame, groups)
    assert 31415 <= seed < 31425
    for split in development_splits(frame, groups, pool, np.eye(600)):
        assert set(split.fit).isdisjoint(heldout)
        assert set(split.valid).isdisjoint(heldout)
        assert set(split.fit).isdisjoint(split.valid)
        if split.scaffold_disjoint:
            assert set(groups[split.fit]).isdisjoint(groups[split.valid])
        else:
            anchors = frame.loc[pool, TARGETS[0]].nlargest(25).index
            assert set(anchors).issubset(split.fit)


def test_pls_transfer_excludes_outer_auxiliary_measurements():
    rng = np.random.default_rng(11)
    x = rng.uniform(size=(80, 32))
    features = MolecularFeatures(
        x, x, rng.uniform(size=(80, 20)), tuple(f"d{i}" for i in range(20))
    )
    aux = x[:, :4] + rng.normal(scale=0.1, size=(80, 4))
    frame = pd.DataFrame({t: 2 + x[:, 0] * 4 for t in TARGETS})
    groups = np.array([f"g{i}" for i in range(80)])
    kernel = {"counts": x @ x.T}
    fit, query = np.arange(64), np.arange(64, 80)
    first, _, _ = fit_transfer_candidates(
        frame,
        aux,
        groups,
        features,
        features,
        kernel,
        kernel,
        fit,
        query,
        requested=frozenset({"screen_pls"}),
    )
    changed = aux.copy()
    changed[query] = 999
    second, _, _ = fit_transfer_candidates(
        frame,
        changed,
        groups,
        features,
        features,
        kernel,
        kernel,
        fit,
        query,
        requested=frozenset({"screen_pls"}),
    )
    for target in TARGETS:
        np.testing.assert_allclose(first["screen_pls"][target], second["screen_pls"][target])


def test_experiment_refuses_to_overwrite_before_reading_inputs(tmp_path):
    with pytest.raises(ValueError, match="already exists"):
        run_transfer(tmp_path / "missing", tmp_path / "missing", tmp_path)


def test_gate_rejects_nonfinite_scores():
    target = "CYP2D6_pIC50_direct_inhibition"
    assert not confirmation_gate({target: score()}, {target: score(float("nan"))}, -0.1)[0]


def test_paired_group_bootstrap_recognizes_gain_on_synthetic_observed_labels():
    truth = np.linspace(2.0, 7.0, 200)
    frame = pd.DataFrame({t: truth for t in TARGETS})
    for target in TARGETS:
        frame[target + "_conf_low"] = truth - 0.1
        frame[target + "_conf_high"] = truth + 0.1
    groups = np.array([f"g{i // 4}" for i in range(len(truth))])
    baseline = {t: np.full(len(truth), truth.mean()) for t in TARGETS}
    candidate = {t: truth.copy() for t in TARGETS}
    result = paired_bootstrap(frame, groups, baseline, candidate, np.arange(len(truth)))
    assert result["resamples"] == 1000
    assert result["macro_difference_percentile_95"][1] < -0.9
