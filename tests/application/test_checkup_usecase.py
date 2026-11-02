"""Use-case decisions with an injected deterministic molecular capability.

@author cylovelife
"""

from dataclasses import replace

import pytest

from aidd_agent.application.checkup import inspect_molecules
from aidd_agent.domain.molecules import (
    FingerprintConfig,
    InvalidSmiles,
    MolecularAnalysis,
    MoleculeDescription,
    MoleculeSample,
)

DESCRIPTION = MoleculeDescription("a", "X", 1, 1, 1, 0, 1.0, 0.0, 0, 0, 0.0, 0, 0)


def analyze(text: str, config: FingerprintConfig) -> MolecularAnalysis:
    if text == "invalid":
        raise InvalidSmiles("Invalid SMILES")
    if text == "broken_backend":
        raise RuntimeError("Backend unavailable")
    identity = "a" if text == "alias" else text
    return MolecularAnalysis(replace(DESCRIPTION, canonical_smiles=identity), frozenset([1, 2]))


def test_identity_is_distinct_from_equal_fingerprint_and_ties_follow_input_order():
    samples = tuple(MoleculeSample(x, x) for x in ["a", "alias", "b", "c", "invalid"])
    result = inspect_molecules(samples, analyze, top_k=2)
    assert result.duplicate_identity_groups == (("a", "alias"),)
    assert [n.id for n in result.records[0].neighbors] == ["b", "c"]
    assert result.records[0].neighbors[0].tanimoto == 1
    assert result.records[-1].analysis is None and result.records[-1].error
    assert result.records[1].sample.smiles == "alias"


def test_unexpected_backend_failures_are_not_mislabeled_as_bad_molecules():
    with pytest.raises(RuntimeError, match="Backend unavailable"):
        inspect_molecules([MoleculeSample("x", "broken_backend")], analyze)


def test_duplicate_identifiers_are_rejected_before_chemistry_runs():
    with pytest.raises(ValueError, match="unique"):
        inspect_molecules([MoleculeSample("x", "broken_backend")] * 2, analyze)
