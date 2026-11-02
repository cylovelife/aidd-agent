"""Molecular checkup composition and installed command entry.

@author cylovelife
"""

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from aidd_agent.application.checkup import inspect_molecules
from aidd_agent.domain.molecules import FingerprintConfig, MoleculeSample


def parse_samples(raw: object) -> tuple[MoleculeSample, ...]:
    if not isinstance(raw, list):
        raise ValueError("Input JSON must be a list of {id, smiles} records")
    samples = []
    for row in raw:
        if not isinstance(row, Mapping):
            raise ValueError("Each sample requires string id and smiles")
        identity, smiles = row.get("id"), row.get("smiles")
        if not isinstance(identity, str) or not identity.strip() or not isinstance(smiles, str):
            raise ValueError("Each sample requires string id and smiles")
        samples.append(MoleculeSample(identity, smiles))
    return tuple(samples)


def create_report(
    samples: Sequence[Mapping[str, str]],
    output: Path,
    *,
    use_chirality: bool = False,
    top_k: int = 3,
) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(output)
    from aidd_agent.adapters.rdkit import molecules as chemistry
    from aidd_agent.adapters.reports import checkup as reports
    from aidd_agent.application import checkup as usecase
    from aidd_agent.domain import molecules as domain

    result = inspect_molecules(
        parse_samples(list(samples)),
        chemistry.analyze_smiles,
        fingerprint=FingerprintConfig(include_chirality=use_chirality),
        top_k=top_k,
    )
    package = Path(__file__).resolve().parents[1]
    sources = [
        Path(__file__),
        Path(usecase.__file__),
        Path(domain.__file__),
        Path(chemistry.__file__),
        Path(reports.__file__),
    ]
    provenance = {
        "rdkit_version": chemistry.rdBase.rdkitVersion,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_files_sha256": {
            "aidd_agent/" + p.resolve().relative_to(package).as_posix(): hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
            for p in sources
        },
    }
    return reports.write_report(result, output, provenance)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--input", type=Path)
    source.add_argument("--smiles", nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--chirality", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.smiles:
            samples = [{"id": f"query_{i}", "smiles": s} for i, s in enumerate(args.smiles)]
        else:
            path = args.input or Path("examples/learning/molecules.json")
            raw = json.loads(path.read_text(encoding="utf-8"))
            samples = [{"id": sample.id, "smiles": sample.smiles} for sample in parse_samples(raw)]
        result = create_report(samples, args.output, use_chirality=args.chirality)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
