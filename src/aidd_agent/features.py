"""Label-free 2D molecular features and validated Tanimoto kernels.

@author cylovelife
"""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from rdkit import Chem
from rdkit.Chem import Descriptors, rdFingerprintGenerator


@dataclass(frozen=True)
class MolecularFeatures:
    bits: NDArray[np.float64]
    counts: NDArray[np.float64]
    descriptors: NDArray[np.float64]
    descriptor_names: tuple[str, ...]

    @property
    def hybrid(self) -> NDArray[np.float64]:
        return np.hstack((self.counts, self.descriptors))


def extract_features(smiles: Sequence[str]) -> MolecularFeatures:
    generator = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    # Version and exact names are saved in each run, including this pinned RDKit registry.
    functions = tuple(Descriptors._descList)
    bits, counts, descriptors = [], [], []
    for index, text in enumerate(smiles):
        mol = Chem.MolFromSmiles(text)
        if mol is None or mol.GetNumAtoms() == 0:
            raise ValueError(f"Invalid SMILES at row {index}")
        bits.append(generator.GetFingerprintAsNumPy(mol))
        counts.append(np.log1p(generator.GetCountFingerprintAsNumPy(mol).astype(float)))
        descriptors.append([function(mol) for _, function in functions])
    if not bits:
        raise ValueError("No molecules to encode")
    descriptor_array = np.asarray(descriptors, dtype=float)
    if not np.isfinite(descriptor_array).all():
        raise ValueError("Non-finite molecular descriptors; inspect before changing protocol")
    return MolecularFeatures(
        np.asarray(bits, dtype=float),
        np.asarray(counts),
        descriptor_array,
        tuple(name for name, _ in functions),
    )


def tanimoto_kernel(
    left: NDArray,
    right: NDArray,
) -> NDArray[np.float64]:
    a, b = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    if a.ndim != 2 or b.ndim != 2 or a.shape[1] != b.shape[1]:
        raise ValueError("Tanimoto inputs must be compatible matrices")
    if not np.isfinite(a).all() or not np.isfinite(b).all() or (a < 0).any() or (b < 0).any():
        raise ValueError("Tanimoto inputs must be finite and nonnegative")
    a2, b2 = np.sum(a * a, axis=1), np.sum(b * b, axis=1)
    if (a2 == 0).any() or (b2 == 0).any():
        raise ValueError("Tanimoto fingerprints must be nonzero")
    dot = a @ b.T
    return np.clip(dot / (a2[:, None] + b2[None, :] - dot), 0.0, 1.0)
