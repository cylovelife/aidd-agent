"""Audited single-concentration observations, kept separate from direct potency.

@author cylovelife
"""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from aidd_agent.chemistry import EncodedMolecules, encode_molecules
from aidd_agent.contracts import IDENTIFIERS, TARGETS, load_identities, load_training
from aidd_agent.sources import DATASET_REVISION, sha256_file, verify_data

SINGLE_FILE = "cyp-challenge-single-concentration-TRAIN.csv"
SINGLE_SHA256 = "cf275440aa33d10b16e7a3a19f1b196d59dc379052175ab79b47ca43db663c7a"
ISOFORMS = tuple(t.split("_")[0] for t in TARGETS)


@dataclass(frozen=True)
class AuxiliaryData:
    molecules: pd.DataFrame
    screen: NDArray[np.float64]
    encoded: EncodedMolecules
    test: pd.DataFrame
    audit: dict[str, object]


def load_auxiliary(data_dir: Path, aux_dir: Path) -> AuxiliaryData:
    main_manifest = verify_data(data_dir)
    path = aux_dir / SINGLE_FILE
    if sha256_file(path) != SINGLE_SHA256:
        raise ValueError("Single-concentration raw hash mismatch")
    with (aux_dir / "manifest.json").open() as stream:
        manifest = json.load(stream)
    if manifest.get("revision") != DATASET_REVISION:
        raise ValueError("Unexpected auxiliary revision")
    main = load_training(data_dir / "cyp-challenge-TRAIN_inhibition.csv")
    test = load_identities(data_dir / "cyp-challenge-TEST-BLINDED.csv")
    if len(test) != 750 or any(t in test and test[t].notna().any() for t in TARGETS):
        raise ValueError("Expected official blinded test identities")
    single = pd.read_csv(path)
    required = {*IDENTIFIERS, "enzyme", "concentration_M", "log2fc_estimate", "log2fc_std_error"}
    if not required.issubset(single.columns):
        raise ValueError("Auxiliary columns missing")
    if single.duplicated(["Molecule_Name", "enzyme"]).any():
        raise ValueError("Duplicate molecule/enzyme auxiliary observation")
    if set(single.enzyme) != set(ISOFORMS):
        raise ValueError("Unexpected auxiliary enzyme")
    values = single[["concentration_M", "log2fc_estimate", "log2fc_std_error"]].to_numpy(float)
    if not np.isfinite(values).all() or (values[:, (0, 2)] <= 0).any():
        raise ValueError("Invalid auxiliary measurement")
    if not np.allclose(values[:, 0], 4.95049505e-5, rtol=0, atol=1e-12):
        raise ValueError("Unexpected single-concentration assay dose")
    identities = single[list(IDENTIFIERS)].drop_duplicates()
    if not identities.Molecule_Name.is_unique:
        raise ValueError("Conflicting auxiliary molecule structures")
    common = main[list(IDENTIFIERS)].merge(identities, on="Molecule_Name")
    if common.SMILES_x.ne(common.SMILES_y).any():
        raise ValueError("Auxiliary structure differs from main identity")
    extra = identities.loc[~identities.Molecule_Name.isin(main.Molecule_Name)]
    molecules = pd.concat([main, extra], ignore_index=True)
    encoded = encode_molecules(molecules.SMILES.tolist())
    test_encoded = encode_molecules(test.SMILES.tolist())
    if set(encoded.canonical) & set(test_encoded.canonical):
        raise ValueError("Auxiliary/main identities overlap the blinded test")
    pivot = single.pivot(index="Molecule_Name", columns="enzyme", values="log2fc_estimate")
    screen = pivot.reindex(index=molecules.Molecule_Name, columns=ISOFORMS).to_numpy(float)
    if not (np.isfinite(screen).all(axis=1) | np.isnan(screen).all(axis=1)).all():
        raise ValueError("Expected complete four-enzyme auxiliary panels or no panel")
    audit = {
        "main_manifest": main_manifest,
        "auxiliary_revision": DATASET_REVISION,
        "auxiliary_sha256": SINGLE_SHA256,
        "molecules": len(molecules),
        "unique_canonical": len(set(encoded.canonical)),
        "test_canonical_overlap": 0,
        "screen_rows": len(single),
        "complete_screen_molecules": int(np.isfinite(screen).all(axis=1).sum()),
        "measured_direct": {t: int(molecules[t].notna().sum()) for t in TARGETS},
        "additional_direct_labels": 0,
        "scope": "Single-concentration readouts are auxiliary outcomes, never imputed pIC50 labels",
    }
    return AuxiliaryData(molecules, screen, encoded, test, audit)
