"""RDKit graph parsing, public descriptors, fingerprints and drawings.

@author cylovelife
"""

import math
from collections.abc import Sequence

from rdkit import Chem, rdBase
from rdkit.Chem import Crippen, Descriptors, rdFingerprintGenerator, rdMolDescriptors
from rdkit.Chem.Draw import rdMolDraw2D

from aidd_agent.domain.molecules import (
    FingerprintConfig,
    InvalidSmiles,
    MolecularAnalysis,
    MoleculeDescription,
    MoleculeSample,
)


def _parse(smiles: str) -> Chem.Mol:
    if not isinstance(smiles, str) or not smiles.strip():
        raise InvalidSmiles("SMILES must be a non-empty string")
    text = smiles.strip()
    if any(c.isspace() for c in text):
        raise InvalidSmiles("SMILES must not contain a name or internal whitespace")
    params = Chem.SmilesParserParams()
    # RDKit's property setter stubs currently misdeclare these boolean attributes.
    params.parseName = False  # type: ignore[assignment]
    params.allowCXSMILES = False  # type: ignore[assignment]
    with rdBase.BlockLogs():
        mol = Chem.MolFromSmiles(text, params)
    if mol is None or mol.GetNumAtoms() == 0:
        raise InvalidSmiles("Invalid SMILES: structure parsing or valence check failed")
    return mol


def _describe(mol: Chem.Mol) -> MoleculeDescription:
    result = MoleculeDescription(
        canonical_smiles=Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True),
        formula=rdMolDescriptors.CalcMolFormula(mol),
        atom_count=mol.GetNumAtoms(),
        heavy_atom_count=mol.GetNumHeavyAtoms(),
        fragment_count=len(Chem.GetMolFrags(mol)),
        formal_charge=sum(atom.GetFormalCharge() for atom in mol.GetAtoms()),
        # These two public descriptors are exported dynamically by RDKit.
        molecular_weight=float(Descriptors.MolWt(mol)),  # type: ignore[attr-defined]
        calculated_logp=float(Crippen.MolLogP(mol)),  # type: ignore[attr-defined]
        hbd=rdMolDescriptors.CalcNumHBD(mol),
        hba=rdMolDescriptors.CalcNumHBA(mol),
        tpsa=float(rdMolDescriptors.CalcTPSA(mol)),
        rotatable_bonds=rdMolDescriptors.CalcNumRotatableBonds(mol),
        ring_count=rdMolDescriptors.CalcNumRings(mol),
    )
    if not all(
        math.isfinite(v) for v in (result.molecular_weight, result.calculated_logp, result.tpsa)
    ):
        raise ValueError("Nonfinite molecular descriptors")
    return result


def describe_smiles(smiles: str) -> MoleculeDescription:
    return _describe(_parse(smiles))


def analyze_smiles(smiles: str, config: FingerprintConfig) -> MolecularAnalysis:
    mol = _parse(smiles)
    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=config.radius, fpSize=config.bits, includeChirality=config.include_chirality
    )
    return MolecularAnalysis(_describe(mol), frozenset(generator.GetFingerprint(mol).GetOnBits()))


def draw_svg(smiles: str) -> str:
    drawer = rdMolDraw2D.MolDraw2DSVG(320, 220)
    drawer.DrawMolecule(_parse(smiles))
    drawer.FinishDrawing()
    return str(drawer.GetDrawingText())


def draw_grid(samples: Sequence[MoleculeSample]) -> bytes:
    rows = (len(samples) + 2) // 3
    grid = rdMolDraw2D.MolDraw2DCairo(960, rows * 220, 320, 220)
    grid.DrawMolecules([_parse(s.smiles) for s in samples], legends=[s.id for s in samples])
    grid.FinishDrawing()
    return bytes(grid.GetDrawingText())
