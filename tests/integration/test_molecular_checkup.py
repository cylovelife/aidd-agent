"""Learning tool: structural identity, chemistry, invalid input and real artifacts.

@author cylovelife
"""

import json
import xml.etree.ElementTree as ET

import pytest

from aidd_agent.molecular_checkup import describe_smiles, run_checkup


def test_equivalent_strings_and_isomers_are_not_confused():
    ethanol = describe_smiles("CCO")
    reverse = describe_smiles("OCC")
    ether = describe_smiles("COC")
    assert ethanol.canonical_smiles == reverse.canonical_smiles
    assert ethanol.calculated_logp == pytest.approx(reverse.calculated_logp, abs=1e-12)
    assert ethanol.tpsa == pytest.approx(reverse.tpsa, abs=1e-12)
    assert ethanol.formula == ether.formula == "C2H6O"
    assert ethanol.molecular_weight == pytest.approx(46.069, abs=0.01)
    assert ethanol.canonical_smiles != ether.canonical_smiles
    assert (ethanol.hbd, ether.hbd) == (1, 0)
    assert ethanol.atom_count == 3


def test_charge_fragments_and_stereochemistry_are_preserved():
    salt = describe_smiles("CC(=O)[O-].[Na+]")
    ion = describe_smiles("CC(=O)[O-]")
    assert salt.fragment_count == 2 and salt.formal_charge == 0
    assert ion.formal_charge == -1
    assert "." in salt.canonical_smiles
    a = describe_smiles("C[C@H](O)C(=O)O")
    b = describe_smiles("C[C@@H](O)C(=O)O")
    assert a.canonical_smiles != b.canonical_smiles


@pytest.mark.parametrize("smiles", ["", " ", "C1CC", "C(C)(C)(C)(C)C", "CCO extra"])
def test_invalid_smiles_fail_explicitly(smiles):
    with pytest.raises(ValueError, match="SMILES"):
        describe_smiles(smiles)


def test_batch_keeps_invalid_rows_and_excludes_duplicate_identity_neighbors(tmp_path):
    rows = [
        {"id": "ethanol", "smiles": "CCO"},
        {"id": "reverse", "smiles": "OCC"},
        {"id": "ether", "smiles": "COC"},
        {"id": "bad<script>", "smiles": "C1CC"},
    ]
    output = tmp_path / "report"
    result = run_checkup(rows, output)
    assert result["valid_count"] == 3 and result["invalid_count"] == 1
    records = json.loads((output / "molecules.json").read_text())
    assert records[1]["input_smiles"] == "OCC"
    assert records[3]["error"] and records[3]["description"] is None
    assert result["duplicate_identity_groups"] == [["ethanol", "reverse"]]
    assert [n["id"] for n in records[0]["neighbors"]] == ["ether"]
    ET.parse(output / "molecule-000.svg")
    assert (output / "structures.png").read_bytes().startswith(b"\x89PNG")
    html = (output / "index.html").read_text()
    assert "bad&lt;script&gt;" in html and "<script>" not in html
    before = (output / "molecules.json").read_bytes()
    with pytest.raises(FileExistsError):
        run_checkup(rows, output)
    assert (output / "molecules.json").read_bytes() == before


def test_chirality_changes_fingerprint_without_changing_identity(tmp_path):
    rows = [
        {"id": "a", "smiles": "C[C@H](O)C(=O)O"},
        {"id": "b", "smiles": "C[C@@H](O)C(=O)O"},
    ]
    for flag in (False, True):
        output = tmp_path / str(flag)
        result = run_checkup(rows, output, use_chirality=flag)
        assert result["duplicate_identity_groups"] == []
    plain = json.loads((tmp_path / "False/molecules.json").read_text())
    chiral = json.loads((tmp_path / "True/molecules.json").read_text())
    assert plain[0]["neighbors"][0]["tanimoto"] == 1
    assert chiral[0]["neighbors"][0]["tanimoto"] < 1


def test_invalid_batch_identifiers_do_not_create_output(tmp_path):
    with pytest.raises(ValueError, match="unique"):
        run_checkup([{"id": "x", "smiles": "CCO"}] * 2, tmp_path / "duplicate")
    assert not (tmp_path / "duplicate").exists()


def test_all_invalid_structures_still_produce_an_explicit_report(tmp_path):
    output = tmp_path / "all-invalid"
    result = run_checkup([{"id": "empty", "smiles": ""}], output)
    assert result["valid_count"] == 0 and result["invalid_count"] == 1
    assert (output / "index.html").exists()
    assert not (output / "structures.png").exists()
    assert json.loads((output / "molecules.json").read_text())[0]["error"]
