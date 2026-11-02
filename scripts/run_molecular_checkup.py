"""Run the local learning report with examples or explicitly supplied SMILES.

@author cylovelife
"""

import argparse
import json
from pathlib import Path

from aidd_agent.molecular_checkup import run_checkup

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--input", type=Path)
    source.add_argument("--smiles", nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--chirality", action="store_true")
    args = parser.parse_args()
    if args.smiles:
        samples = [{"id": f"query_{i}", "smiles": s} for i, s in enumerate(args.smiles)]
    else:
        path = args.input or Path("examples/learning/molecules.json")
        samples = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(samples, list):
            parser.error("Input JSON must be a list of {id, smiles} records")
    print(json.dumps(run_checkup(samples, args.output, use_chirality=args.chirality), indent=2))
