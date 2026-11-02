"""Compatibility API; new code uses domain/application/adapters/entrypoints.

@author cylovelife
"""

from collections.abc import Mapping, Sequence
from pathlib import Path

from aidd_agent.domain.molecules import MoleculeDescription


def describe_smiles(smiles: str) -> MoleculeDescription:
    from aidd_agent.adapters.rdkit.molecules import describe_smiles as describe

    return describe(smiles)


def run_checkup(
    samples: Sequence[Mapping[str, str]],
    output: Path,
    *,
    use_chirality: bool = False,
    top_k: int = 3,
) -> dict[str, object]:
    from aidd_agent.entrypoints.checkup import create_report

    return create_report(samples, output, use_chirality=use_chirality, top_k=top_k)
