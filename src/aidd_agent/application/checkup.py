"""Inspect a batch and rank distinct structural neighbors without performing I/O.

@author cylovelife
"""

from collections.abc import Callable, Sequence
from dataclasses import replace

from aidd_agent.domain.molecules import (
    CheckupResult,
    FingerprintConfig,
    InvalidSmiles,
    MolecularAnalysis,
    MoleculeInspection,
    MoleculeSample,
    Neighbor,
    tanimoto,
)

MoleculeAnalyzer = Callable[[str, FingerprintConfig], MolecularAnalysis]
DEFAULT_FINGERPRINT = FingerprintConfig()


def inspect_molecules(
    samples: Sequence[MoleculeSample],
    analyzer: MoleculeAnalyzer,
    *,
    fingerprint: FingerprintConfig = DEFAULT_FINGERPRINT,
    top_k: int = 3,
) -> CheckupResult:
    """Preserve invalid rows; only notation failures are recoverable row errors."""
    if not 1 <= len(samples) <= 200 or not 1 <= top_k <= 20:
        raise ValueError("Use 1..200 samples and top_k between 1 and 20")
    if any(not sample.id.strip() for sample in samples):
        raise ValueError("Sample ids must be nonempty")
    if len({sample.id for sample in samples}) != len(samples):
        raise ValueError("Sample ids must be unique")
    if fingerprint.radius < 0 or fingerprint.bits < 1:
        raise ValueError("Invalid fingerprint configuration")
    records = []
    identities: dict[str, list[str]] = {}
    for sample in samples:
        try:
            analysis = analyzer(sample.smiles, fingerprint)
        except InvalidSmiles as error:
            records.append(MoleculeInspection(sample, None, str(error)))
        else:
            records.append(MoleculeInspection(sample, analysis, None))
            identities.setdefault(analysis.description.canonical_smiles, []).append(sample.id)
    for i, record in enumerate(records):
        if record.analysis is None:
            continue
        ranked = sorted(
            (
                (tanimoto(record.analysis.fingerprint_bits, other.analysis.fingerprint_bits), j)
                for j, other in enumerate(records)
                if other.analysis is not None
                and other.analysis.description.canonical_smiles
                != record.analysis.description.canonical_smiles
            ),
            key=lambda pair: (-pair[0], pair[1]),
        )
        seen: set[str] = set()
        neighbors = []
        for similarity, j in ranked:
            other = records[j]
            assert other.analysis is not None
            identity = other.analysis.description.canonical_smiles
            if identity in seen:
                continue
            seen.add(identity)
            neighbors.append(Neighbor(other.sample.id, similarity))
            if len(neighbors) == top_k:
                break
        records[i] = replace(record, neighbors=tuple(neighbors))
    return CheckupResult(
        tuple(records),
        fingerprint,
        tuple(tuple(ids) for ids in identities.values() if len(ids) > 1),
    )
