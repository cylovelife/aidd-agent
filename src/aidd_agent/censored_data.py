"""Hash-locked manual primary-evidence decisions and global molecular exclusions.

@author cylovelife
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from aidd_agent.censored import interval_huber
from aidd_agent.external_data import leakage_identity
from aidd_agent.sources import sha256_file


def load_reviewed_bounds(
    audit_dir: Path, official_smiles: list[str]
) -> tuple[pd.DataFrame, dict[str, Any]]:
    lock = json.loads((audit_dir / "audit-lock.json").read_text())
    if lock.get("schema_version") != 1:
        raise ValueError("Unsupported primary-evidence audit schema")
    for name, digest in lock["files"].items():
        if sha256_file(Path(name)) != digest:
            raise ValueError("Primary-evidence hash mismatch: " + name)
    for name, digest in lock["artifacts"].items():
        if sha256_file(audit_dir / name) != digest:
            raise ValueError("Reviewed artifact hash mismatch: " + name)
    reviewed = pd.read_csv(audit_dir / "reviewed.csv")
    admitted = pd.read_csv(audit_dir / "admitted.csv")
    if (
        len(reviewed) != lock["reviewed_n"]
        or not reviewed.activity_id.is_unique
        or reviewed.decision.value_counts().to_dict() != lock["decisions"]
        or len(admitted) != lock["admitted_n"]
        or not admitted.activity_id.is_unique
        or set(admitted.activity_id)
        != set(reviewed.loc[reviewed.decision.eq("admit_censored"), "activity_id"])
    ):
        raise ValueError("Reviewed/admitted observation coverage mismatch")
    original = reviewed.set_index("activity_id").loc[admitted.activity_id]
    if not np.array_equal(original.canonical_smiles.to_numpy(), admitted.smiles.to_numpy()):
        raise ValueError("Admitted molecular identity differs from reviewed evidence")
    if (
        admitted.empty
        or admitted[["source", "smiles", "evidence"]].isna().any().any()
        or not admitted.weight.eq(0.25).all()
    ):
        raise ValueError("Missing source/structure/evidence or unexpected external weight")
    lower, upper = admitted.lower.to_numpy(float), admitted.upper.to_numpy(float)
    interval_huber(np.zeros(len(admitted)), lower, upper)
    if (np.isneginf(lower) & np.isposinf(upper)).any():
        raise ValueError("Unbounded external observation")
    keys = [leakage_identity(s) for s in official_smiles]
    official_parents, official_scaffolds = {k[0] for k in keys}, {k[1] for k in keys}
    admitted[["parent", "scaffold"]] = [leakage_identity(s) for s in admitted.smiles]
    parent_overlap = admitted.parent.isin(official_parents)
    scaffold_overlap = admitted.scaffold.isin(official_scaffolds)
    keep = ~(parent_overlap | scaffold_overlap)
    retained = admitted.loc[keep].reset_index(drop=True)
    # Citation/assay duplicates must be resolved by the primary-source review, never averaged here.
    if retained.parent.duplicated().any():
        raise ValueError("Duplicate reviewed parent requires explicit provenance adjudication")
    if retained.empty:
        raise ValueError("No reviewed bounds survive global identity/scaffold exclusion")
    return retained, dict(
        audit_sha256=sha256_file(audit_dir / "audit-lock.json"),
        reviewed_n=len(reviewed),
        decisions=lock["decisions"],
        admitted_before_exclusion=len(admitted),
        official_parent_overlap_rows=int(parent_overlap.sum()),
        official_scaffold_overlap_rows=int(scaffold_overlap.sum()),
        excluded_rows=int((~keep).sum()),
        retained_n=len(retained),
        retained_sources=int(retained.source.nunique()),
        retained_parents=int(retained.parent.nunique()),
        retained_scaffolds=int(retained.scaffold.nunique()),
        official_keys=keys,
    )
