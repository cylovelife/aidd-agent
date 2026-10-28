"""Canonical molecule identities, Morgan fingerprints and scaffold splits.

@author cylovelife
"""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from rdkit import Chem
from rdkit.Chem import rdFingerprintGenerator
from rdkit.Chem.Scaffolds import MurckoScaffold
from sklearn.model_selection import GroupShuffleSplit


@dataclass(frozen=True)
class EncodedMolecules:
    fingerprints: NDArray[np.uint8]
    canonical: tuple[str, ...]
    groups: NDArray[np.str_]


def encode_molecules(smiles: Sequence[str]) -> EncodedMolecules:
    generator = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    canonical: list[str] = []
    groups: list[str] = []
    fingerprints: list[NDArray[np.uint8]] = []
    for index, text in enumerate(smiles):
        molecule = Chem.MolFromSmiles(text)
        if molecule is None or molecule.GetNumAtoms() == 0:
            raise ValueError(f"Invalid SMILES at row {index}")
        identity = Chem.MolToSmiles(molecule, canonical=True)
        scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=molecule, includeChirality=False)
        canonical.append(identity)
        groups.append("scaffold:" + scaffold if scaffold else "acyclic:" + identity)
        fingerprints.append(generator.GetFingerprintAsNumPy(molecule))
    if not fingerprints:
        raise ValueError("No molecules to encode")
    return EncodedMolecules(np.stack(fingerprints), tuple(canonical), np.array(groups))


def split_groups(
    groups: NDArray[np.str_], seed: int
) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    if len(set(groups)) < 2:
        raise ValueError("At least two molecule groups are required")
    train, valid = next(
        GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed).split(
            np.zeros(len(groups)), groups=groups
        )
    )
    if set(groups[train]) & set(groups[valid]):
        raise ValueError("Molecular groups overlap across training and validation")
    return train, valid
