"""Canonical and legacy command interfaces share the same calculation contract.

@author cylovelife
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from aidd_agent.entrypoints.checkup import main

ROOT = Path(__file__).resolve().parents[2]


def test_module_and_legacy_script_commands_have_identical_records(tmp_path):
    commands = [
        [sys.executable, "-m", "aidd_agent.entrypoints.checkup"],
        [sys.executable, str(ROOT / "scripts/run_molecular_checkup.py")],
    ]
    results = []
    for i, command in enumerate(commands):
        output = tmp_path / str(i)
        result = subprocess.run(
            [*command, "--smiles", "CCO", "COC", "--output", str(output)],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        )
        manifest = json.loads(result.stdout)
        assert manifest["schema_version"] == 2 and len(manifest["source_files_sha256"]) == 5
        results.append(json.loads((output / "molecules.json").read_text()))
    assert results[0] == results[1]


def test_command_rejects_bad_json_schema_without_creating_output(tmp_path):
    input_path = tmp_path / "samples.json"
    input_path.write_text('[{"id":"x","smiles":123}]')
    output = tmp_path / "output"
    with pytest.raises(SystemExit) as error:
        main(["--input", str(input_path), "--output", str(output)])
    assert error.value.code == 2
    assert not output.exists()


@pytest.mark.parametrize("name", ["run_final_neural.py", "run_readout.py", "fetch_cyp2d6.py"])
def test_existing_cyp_script_compatibility_entry_still_accepts_help(name):
    if name == "run_final_neural.py" and importlib.util.find_spec("torch") is None:
        pytest.skip("Optional neural script requires torch")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name), "--help"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "usage:" in result.stdout
