"""Public assay semantics and conservative molecular leakage exclusions.

@author cylovelife
"""

import numpy as np
import pandas as pd
import pytest

from aidd_agent.external_data import (
    chembl_observation,
    collapse_classes,
    leakage_identity,
    pubchem_observation,
)


def chembl(**changes):
    row = dict(
        target_chembl_id="CHEMBL289",
        target_organism="Homo sapiens",
        standard_type="IC50",
        standard_units="nM",
        standard_flag=1,
        standard_value="100000",
        standard_relation=">",
        data_validity_comment=None,
        potential_duplicate=0,
        assay_description="Inhibition of human CYP2D6 using bufuralol",
        canonical_smiles="CCO",
        activity_id=1,
        assay_chembl_id="A1",
        document_chembl_id="D1",
    )
    return row | changes


def test_censored_ic50_reverses_direction_without_becoming_exact_label():
    row = chembl_observation(chembl())
    assert row["p_relation"] == "<" and row["p_bound"] == 4
    assert row["class_label"] == 0 and np.isnan(row["exact_pIC50"])
    row = chembl_observation(chembl(standard_relation="<", standard_value="10000"))
    assert row["p_relation"] == ">" and row["class_label"] == 1
    row = chembl_observation(chembl(standard_relation=">", standard_value="1000"))
    assert np.isnan(row["class_label"])
    row = chembl_observation(chembl(standard_relation="=", standard_value="200000"))
    assert row["exact_pIC50"] == pytest.approx(3.69897)


def test_assay_conditions_and_invalid_units_are_quarantined():
    for changes in (
        {"standard_units": "min"},
        {"potential_duplicate": 1},
        {"standard_value": "0"},
        {"standard_value": "nan"},
        {"assay_description": "Time-dependent inhibition after preincubation"},
        {"target_organism": "Rattus norvegicus"},
        {"data_validity_comment": "Potential transcription error"},
    ):
        assert chembl_observation(chembl(**changes))["accepted"] is False


def test_pubchem_inactive_is_not_zero_potency_or_panel_label():
    row = {
        "PUBCHEM_SID": "1",
        "PUBCHEM_CID": "2",
        "PUBCHEM_EXT_DATASOURCE_SMILES": "CCO",
        "PUBCHEM_ACTIVITY_OUTCOME": "Inactive",
        "Phenotype": "Inactive",
        "Potency": np.nan,
    }
    parsed = pubchem_observation(row)
    assert parsed["class_label"] == 0 and np.isnan(parsed["exact_pIC50"])
    assert not pubchem_observation(row | {"Phenotype": "Activator"})["accepted"]
    assert not pubchem_observation(
        row | {"PUBCHEM_ACTIVITY_OUTCOME": "Inconclusive", "Phenotype": "Inhibitor"}
    )["accepted"]
    with pytest.raises(ValueError, match="891"):
        pubchem_observation(row, aid=1851)


def test_salt_charge_stereo_and_tautomers_share_conservative_key():
    assert leakage_identity("CC[NH+](CC)CC.[Cl-]") == leakage_identity("CCN(CC)CC")
    assert leakage_identity("C[C@H](O)CC") == leakage_identity("C[C@@H](O)CC")
    assert leakage_identity("O=c1cccc[nH]1") == leakage_identity("Oc1ccccn1")
    assert leakage_identity("CCCCCCCCCCCCCCCC[N+](C)(C)C.[Cl-]") == leakage_identity(
        "CCCCCCCCCCCCCCCC[N+](C)(C)C"
    )
    assert leakage_identity("O=C(O[C@H]1C[C@H]2CC[C@@H](C1)[N+]21CCCC1)C(O)(c1ccccc1)c1ccccc1")
    with pytest.raises(ValueError, match="SMILES"):
        leakage_identity("not a molecule")


def test_conflicting_measurements_are_removed_as_entire_parent_group():
    rows = pd.DataFrame(
        dict(
            source=["a", "a", "a", "a", "b"],
            parent=["x", "x", "y", "y", "x"],
            class_label=[0, 1, 0, 0, 1],
            smiles=["C"] * 5,
        )
    )
    result, count = collapse_classes(rows)
    assert count == 1
    assert set(zip(result.source, result.parent, strict=True)) == {("a", "y"), ("b", "x")}
