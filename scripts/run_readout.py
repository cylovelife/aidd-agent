"""Execute the frozen diagnosis or follow-up; fresh output directories only.

@author cylovelife
"""

import argparse
import json
from pathlib import Path

from aidd_agent.readout import diagnose, run_readout

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("diagnose", "heads"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = diagnose(args.output_dir) if args.stage == "diagnose" else run_readout(args.output_dir)
    print(json.dumps(result, indent=2, allow_nan=False))
