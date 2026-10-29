"""Public CYP2D6 observations: assay semantics, censoring and leakage exclusions.

Data remain in state; ChEMBL37 is CC BY-SA 3.0, PubChem AID891 is deposited by NCATS.
@author cylovelife
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import rdMolHash
from rdkit.Chem.MolStandardize import rdMolStandardize
from rdkit.Chem.Scaffolds import MurckoScaffold

from aidd_agent.sources import sha256_file


@lru_cache(maxsize=50000)
def leakage_identity(smiles: str) -> tuple[str, str]:
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None or molecule.GetNumAtoms() == 0:
        raise ValueError("Invalid external SMILES")
    parent = rdMolStandardize.FragmentParent(molecule)
    parent = rdMolStandardize.Uncharger().uncharge(parent)
    Chem.SanitizeMol(parent)
    Chem.RemoveStereochemistry(parent)
    identity = rdMolHash.MolHash(Chem.Mol(parent), rdMolHash.HashFunction.HetAtomTautomerv2)
    # Remove bond-order dependence before pruning exocyclic atoms (e.g. pyridone/pyridinol).
    element_molecule = Chem.Mol(parent)
    for atom in element_molecule.GetAtoms():
        atom.SetIsAromatic(False)
        atom.SetNumExplicitHs(0)
        atom.SetNoImplicit(False)
    for bond in element_molecule.GetBonds():
        bond.SetIsAromatic(False)
        bond.SetBondType(Chem.BondType.SINGLE)
    # Preserve formal charge: stripping it makes quaternary nitrogen artificially pentavalent.
    Chem.SanitizeMol(element_molecule)
    core = MurckoScaffold.GetScaffoldForMol(element_molecule)
    scaffold = Chem.MolToSmiles(core) if core.GetNumAtoms() else ""
    return identity, "scaffold:" + scaffold if scaffold else "acyclic:" + identity


def chembl_observation(row: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = dict(
        source="chembl37",
        record_id=str(row.get("activity_id")),
        smiles=row.get("canonical_smiles"),
        assay_id=row.get("assay_chembl_id"),
        document_id=row.get("document_chembl_id"),
        description=row.get("assay_description"),
        original_relation=row.get("standard_relation"),
        original_value=row.get("standard_value"),
        original_units=row.get("standard_units"),
        accepted=False,
        reason="metadata_or_condition",
        p_relation=None,
        p_bound=np.nan,
        exact_pIC50=np.nan,
        class_label=np.nan,
    )
    description = str(row.get("assay_description") or "").lower()
    if not (
        row.get("target_chembl_id") == "CHEMBL289"
        and row.get("target_organism") == "Homo sapiens"
        and row.get("standard_type") == "IC50"
        and row.get("standard_units") == "nM"
        and row.get("standard_flag") == 1
        and row.get("potential_duplicate") == 0
        and row.get("data_validity_comment") in (None, "Manually validated")
        and "inhibit" in description
        and not re.search(
            r"time.?dependent|pre.?incubat|ic50.?shift|mechanism.?based|\btdi\b|kinact", description
        )
    ):
        return result
    raw_value = row.get("standard_value")
    value = pd.to_numeric(raw_value if raw_value is not None else np.nan, errors="coerce")
    relation = row.get("standard_relation")
    if not np.isfinite(value) or value <= 0 or relation not in ("=", ">", ">=", "<", "<="):
        return result | dict(reason="value_or_relation")
    bound = 9 - float(np.log10(value))
    reverse = {"=": "=", ">": "<", ">=": "<=", "<": ">", "<=": ">="}[relation]
    label = np.nan
    if relation == "=":
        label = float(bound >= 5)
    elif relation in (">", ">=") and bound < 5:
        label = 0.0
    elif relation == ">" and bound == 5:
        label = 0.0
    elif relation in ("<", "<=") and bound >= 5:
        label = 1.0
    return result | dict(
        accepted=True,
        reason="accepted",
        p_relation=reverse,
        p_bound=bound,
        exact_pIC50=bound if relation == "=" else np.nan,
        class_label=label,
    )


def pubchem_observation(row: dict[str, Any], aid: int = 891) -> dict[str, Any]:
    if aid != 891:
        raise ValueError("Only isoform-specific AID891 is supported; panel outcomes are not labels")
    phenotype, outcome = row.get("Phenotype"), row.get("PUBCHEM_ACTIVITY_OUTCOME")
    label = np.nan
    if phenotype == "Inactive" and outcome == "Inactive":
        label = 0.0
    if phenotype == "Inhibitor" and outcome == "Active":
        label = 1.0
    return dict(
        source="pubchem891",
        record_id=str(row.get("PUBCHEM_SID")),
        cid=row.get("PUBCHEM_CID"),
        smiles=row.get("PUBCHEM_EXT_DATASOURCE_SMILES"),
        assay_id="AID891",
        document_id="AID891",
        description=phenotype,
        original_relation=None,
        original_value=row.get("Potency"),
        original_units="uM AC50",
        outcome=outcome,
        phenotype=phenotype,
        curve=row.get("Curve_Description"),
        accepted=bool(np.isfinite(label)),
        reason="accepted" if np.isfinite(label) else "ambiguous_or_noninhibitor",
        p_relation=None,
        p_bound=np.nan,
        exact_pIC50=np.nan,
        class_label=label,
    )


def collapse_classes(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    labeled = frame.loc[frame.class_label.notna()].copy()
    counts = labeled.groupby(["source", "parent"]).class_label.nunique()
    conflicts = counts[counts > 1].index
    keep = ~pd.MultiIndex.from_frame(labeled[["source", "parent"]]).isin(conflicts)
    return labeled.loc[keep].drop_duplicates(["source", "parent"]).reset_index(drop=True), len(
        conflicts
    )


def verify_public_raw(directory: Path) -> dict[str, Any]:
    with (directory / "manifest.json").open() as stream:
        manifest = json.load(stream)
    names = [item["name"] for item in manifest["files"]]
    if len(names) != len(set(names)) or len(names) != 33:
        raise ValueError("Incomplete or duplicated public source manifest")
    for item in manifest["files"]:
        if Path(item["name"]).name != item["name"]:
            raise ValueError("Invalid raw filename")
        if sha256_file(directory / item["name"]) != item["sha256"]:
            raise ValueError("Public raw input hash mismatch: " + item["name"])
    status = json.loads((directory / "chembl-status.json").read_text())
    if status["chembl_db_version"] != "ChEMBL_37":
        raise ValueError("Unexpected ChEMBL version")
    return dict(manifest)


def load_public_observations(directory: Path) -> pd.DataFrame:
    manifest = verify_public_raw(directory)
    pubchem = pd.concat(
        [pd.read_csv(p, low_memory=False) for p in sorted(directory.glob("pubchem-891-*.csv"))],
        ignore_index=True,
    )
    pubchem = pubchem.loc[pd.to_numeric(pubchem.PUBCHEM_SID, errors="coerce").notna()]
    sids = pubchem.PUBCHEM_SID.astype(int)
    if not sids.is_unique or set(sids) != set(manifest["pubchem_expected_sids"]):
        raise ValueError("PubChem SID coverage mismatch")
    activities = []
    for path in sorted(directory.glob("chembl-2d6-*.json")):
        page = json.loads(path.read_text())
        if page["page_meta"]["total_count"] != manifest["chembl_expected_total"]:
            raise ValueError("ChEMBL API changed during acquisition")
        activities.extend(page["activities"])
    if len(activities) != manifest["chembl_expected_total"] or len(
        {row["activity_id"] for row in activities}
    ) != len(activities):
        raise ValueError("ChEMBL pagination missing or duplicated activities")
    observations = [
        pubchem_observation({str(k): v for k, v in row.items()})
        for row in pubchem.to_dict("records")
    ]
    observations.extend(chembl_observation(row) for row in activities)
    frame = pd.DataFrame(observations)
    parents, scaffolds = [], []
    for row in frame.itertuples():
        try:
            if not row.accepted or not isinstance(row.smiles, str):
                raise ValueError("Missing SMILES")
            parent, scaffold = leakage_identity(row.smiles)
        except ValueError:
            parent, scaffold = None, None
        parents.append(parent)
        scaffolds.append(scaffold)
    frame["parent"], frame["scaffold"] = parents, scaffolds
    frame.loc[frame.accepted & frame.parent.isna(), "reason"] = "invalid_molecular_identity"
    frame.loc[frame.parent.isna(), "accepted"] = False
    return frame


def exclude_official(
    observations: pd.DataFrame, official_smiles: list[str]
) -> tuple[pd.DataFrame, dict[str, int]]:
    keys = [leakage_identity(s) for s in official_smiles]
    parents, scaffolds = {k[0] for k in keys}, {k[1] for k in keys}
    exact = observations.parent.isin(parents)
    scaffold = observations.scaffold.isin(scaffolds)
    eligible = observations.accepted & observations.parent.notna()
    filtered = observations.loc[eligible & ~exact & ~scaffold].copy()
    classes, conflicts = collapse_classes(filtered)
    return classes, dict(
        accepted_before_exclusion=int(eligible.sum()),
        official_parent_overlap_rows=int((eligible & exact).sum()),
        official_scaffold_overlap_rows=int((eligible & scaffold).sum()),
        conflict_source_parent_groups=conflicts,
        retained_classes=len(classes),
    )
