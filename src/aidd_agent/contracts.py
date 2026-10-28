"""Official CYP data and submission contracts.

@author cylovelife
"""

from pathlib import Path

import numpy as np
import pandas as pd

TARGETS = tuple(
    f"{isoform}_pIC50_direct_inhibition" for isoform in ("CYP1A2", "CYP2C9", "CYP2D6", "CYP3A4")
)
IDENTIFIERS = ("SMILES", "Molecule_Name")
MIN_PREDICTION_STD = 0.01  # Live platform config.py, checked 2026-10-28.


def load_identities(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if not set(IDENTIFIERS).issubset(frame.columns):
        raise ValueError("Missing identity columns")
    if frame.empty or frame[list(IDENTIFIERS)].isna().any().any():
        raise ValueError("Empty data or missing identities")
    if not frame["Molecule_Name"].is_unique:
        raise ValueError("Molecule_Name must be unique")
    for column in IDENTIFIERS:
        if (
            not frame[column]
            .map(lambda value: isinstance(value, str) and bool(value.strip()))
            .all()
        ):
            raise ValueError(f"Invalid identity column: {column}")
    return frame


def load_training(path: Path) -> pd.DataFrame:
    frame = load_identities(path)
    required = [name for col in TARGETS for name in (col, col + "_conf_low", col + "_conf_high")]
    if not set(required).issubset(frame.columns):
        raise ValueError("Missing training labels or credible bounds")
    for col in TARGETS:
        for name in (col, col + "_conf_low", col + "_conf_high"):
            frame[name] = pd.to_numeric(frame[name], errors="raise")
        measured = frame[col].notna()
        values = frame.loc[measured, [col, col + "_conf_low", col + "_conf_high"]].to_numpy()
        if not np.isfinite(values).all():
            raise ValueError(f"Non-finite measured labels/bounds: {col}")
        if ((values[:, 1] > values[:, 0]) | (values[:, 0] > values[:, 2])).any():
            raise ValueError(f"Invalid credible bounds: {col}")
    return frame


def validate_submission(
    predictions: pd.DataFrame,
    test: pd.DataFrame,
    expected_rows: int = 750,
) -> None:
    if len(predictions) != expected_rows or len(test) != expected_rows:
        raise ValueError(f"Expected exactly {expected_rows} rows")
    if set(predictions.columns) != set((*IDENTIFIERS, *TARGETS)):
        raise ValueError("Submission columns do not match the regression contract")
    if predictions[list(IDENTIFIERS)].isna().any().any():
        raise ValueError("Missing submission identities")
    if not predictions["Molecule_Name"].is_unique or not test["Molecule_Name"].is_unique:
        raise ValueError("Molecule_Name must be unique")
    if set(predictions["Molecule_Name"]) != set(test["Molecule_Name"]):
        raise ValueError("Submission identities differ from the official test set")
    ordered = predictions.set_index("Molecule_Name").loc[test["Molecule_Name"]]
    if ordered["SMILES"].tolist() != test["SMILES"].tolist():
        raise ValueError("Submission SMILES do not match official molecule identities")
    for col in TARGETS:
        values = pd.to_numeric(predictions[col], errors="raise").to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError(f"Predictions must be finite: {col}")
        if np.unique(values).size < 2 or np.std(values, ddof=1) < MIN_PREDICTION_STD:
            raise ValueError(f"Platform rejects constant or near-constant predictions: {col}")
