"""Command-line entry points; network and filesystem effects are explicit.

@author cylovelife
"""

import argparse
import json
from pathlib import Path

import pandas as pd

from aidd_agent.baseline import run_baseline
from aidd_agent.contracts import load_identities, validate_submission
from aidd_agent.sources import download_data, verify_data
from aidd_agent.vendor.openadmet.activity_validation import validate_activity_submission


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("fetch", help="Download/verify the pinned public dataset")
    fetch.add_argument("--data-dir", type=Path, default=Path("state/data/cyp"))
    run = commands.add_parser("baseline", help="Run the frozen finite-budget regression protocol")
    run.add_argument("--data-dir", type=Path, default=Path("state/data/cyp"))
    run.add_argument("--output-dir", type=Path, required=True)
    optimize = commands.add_parser("optimize", help="Run the frozen second-round protocol")
    optimize.add_argument("--data-dir", type=Path, default=Path("state/data/cyp"))
    optimize.add_argument("--output-dir", type=Path, required=True)
    validate = commands.add_parser(
        "validate", help="Check identity, schema and upstream validation"
    )
    validate.add_argument("file", type=Path)
    validate.add_argument("--data-dir", type=Path, default=Path("state/data/cyp"))
    submit = commands.add_parser("submit", help="Perform one authorized official submission")
    submit.add_argument("file", type=Path)
    submit.add_argument("--data-dir", type=Path, default=Path("state/data/cyp"))
    submit.add_argument("--receipt-dir", type=Path, required=True)
    submit.add_argument("--username", required=True)
    submit.add_argument("--method-url", required=True)
    submit.add_argument("--sha256", required=True)
    check = commands.add_parser(
        "check", help="Read official score for an existing receipt; no upload"
    )
    check.add_argument("--receipt-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "fetch":
        result = download_data(args.data_dir)
    elif args.command == "baseline":
        result = run_baseline(args.data_dir, args.output_dir)
    elif args.command == "optimize":
        from aidd_agent.optimization import run_optimization

        result = run_optimization(args.data_dir, args.output_dir)
    elif args.command == "submit":
        from aidd_agent.submission import submit_once

        result = submit_once(
            args.file,
            args.data_dir,
            args.receipt_dir,
            args.username,
            args.method_url,
            args.sha256,
        )
    elif args.command == "check":
        from aidd_agent.submission import check_leaderboard

        result = check_leaderboard(args.receipt_dir)
    else:
        verify_data(args.data_dir)
        test = load_identities(args.data_dir / "cyp-challenge-TEST-BLINDED.csv")
        validate_submission(pd.read_csv(args.file), test)
        valid, errors = validate_activity_submission(args.file, set(test["Molecule_Name"]))
        if not valid:
            raise ValueError(f"Official validator rejected predictions: {errors}")
        result = {"valid": valid, "errors": errors}
    print(json.dumps(result, indent=2, allow_nan=False))
