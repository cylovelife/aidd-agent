"""Executable boundaries for evolving code and frozen research compatibility.

@author cylovelife
"""

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_inner_layers_have_only_standard_library_and_inward_dependencies():
    layers = ("domain", "application", "adapters", "entrypoints")
    for layer in layers:
        for path in (ROOT / "src/aidd_agent" / layer).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.ImportFrom):
                    assert node.level == 0, f"Use explicit package imports in {path}"
                    modules = [node.module or ""]
                elif isinstance(node, ast.Import):
                    modules = [n.name for n in node.names]
                else:
                    continue
                for name in modules:
                    if name.startswith("aidd_agent."):
                        allowed = {
                            "domain": ("domain",),
                            "application": ("domain", "application"),
                            "adapters": ("domain", "adapters"),
                            "entrypoints": layers,
                        }[layer]
                        assert name.split(".")[1] in allowed, (path, name)
                    elif layer in ("domain", "application"):
                        assert name.partition(".")[0] in sys.stdlib_module_names, (path, name)
                        assert name.partition(".")[0] not in {
                            "pathlib",
                            "os",
                            "io",
                            "socket",
                            "urllib",
                            "http",
                            "subprocess",
                        }, (path, name)


def test_inner_imports_do_not_load_chemistry_ml_or_network_clients():
    command = (
        "import sys; import aidd_agent.application.checkup; import aidd_agent.domain.molecules; "
        "assert not {'rdkit','torch','sklearn','httpx','pandas'} & set(sys.modules)"
    )
    subprocess.run([sys.executable, "-I", "-c", command], check=True, cwd=ROOT)


def test_frozen_cyp_sources_and_protocols_keep_original_bytes():
    manifest = json.loads((ROOT / "docs/engineering/cyp-preservation.json").read_text())
    for name, expected in (manifest["sha256"] | manifest["relocated_sha256"]).items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
