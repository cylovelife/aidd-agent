"""Molecular inspection values, independent of chemistry and storage libraries.

@author cylovelife
"""

from dataclasses import dataclass


class InvalidSmiles(ValueError):
    """The supplied notation cannot represent an accepted molecular graph."""


@dataclass(frozen=True)
class MoleculeSample:
    id: str
    smiles: str


@dataclass(frozen=True)
class FingerprintConfig:
    radius: int = 2
    bits: int = 2048
    include_chirality: bool = False


@dataclass(frozen=True)
class MoleculeDescription:
    canonical_smiles: str
    formula: str
    atom_count: int
    heavy_atom_count: int
    fragment_count: int
    formal_charge: int
    molecular_weight: float
    calculated_logp: float
    hbd: int
    hba: int
    tpsa: float
    rotatable_bonds: int
    ring_count: int


@dataclass(frozen=True)
class MolecularAnalysis:
    description: MoleculeDescription
    fingerprint_bits: frozenset[int]


@dataclass(frozen=True)
class Neighbor:
    id: str
    tanimoto: float


@dataclass(frozen=True)
class MoleculeInspection:
    sample: MoleculeSample
    analysis: MolecularAnalysis | None
    error: str | None
    neighbors: tuple[Neighbor, ...] = ()


@dataclass(frozen=True)
class CheckupResult:
    records: tuple[MoleculeInspection, ...]
    fingerprint: FingerprintConfig
    duplicate_identity_groups: tuple[tuple[str, ...], ...]


def tanimoto(left: frozenset[int], right: frozenset[int]) -> float:
    """Jaccard/Tanimoto similarity for nonempty molecular bit fingerprints."""
    union = left | right
    if not union:
        raise ValueError("Cannot compare two empty molecular fingerprints")
    return len(left & right) / len(union)
