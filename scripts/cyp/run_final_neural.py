"""Run the predeclared last-round resource probe or matched neural experiment.

@author cylovelife
"""

import argparse
import json
from pathlib import Path

from aidd_agent.final_neural import resource_probe, run_final

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("probe", "run"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.stage == "probe":
        resource_probe(args.output)
    else:
        print(json.dumps(run_final(args.output), indent=2, allow_nan=False))
