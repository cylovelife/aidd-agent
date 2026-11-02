"""Archive public CYP2D6 source responses without replacing existing artifacts.

@author cylovelife
"""

import argparse
import hashlib
import io
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("state/data/cyp2d6-public"))
    parser.add_argument("--lock-file", type=Path, default=Path("docs/round4-sources-lock.json"))
    args = parser.parse_args()
    lock = json.loads(args.lock_file.read_text())
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=False)
    with httpx.Client(timeout=httpx.Timeout(90, connect=15), follow_redirects=True) as client:
        response = client.get(lock["concise_url"])
        with (output / "discovery.csv").open("xb") as stream:
            stream.write(response.content)
        response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest() != lock["concise_sha256"]:
            raise ValueError("Public source discovery changed; retain evidence and audit drift")
    concise = pd.read_csv(io.BytesIO(response.content))
    sids = concise.SID.astype(int).tolist()
    if len(sids) != lock["pubchem_expected_sids_n"] or len(set(sids)) != len(sids):
        raise ValueError("PubChem source identity coverage changed")
    tasks = []
    for offset in range(0, len(sids), 500):
        subset = ",".join(map(str, sids[offset : offset + 500]))
        tasks.append(
            (
                f"pubchem-891-{offset:05d}.csv",
                "https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay/aid/891/CSV?sid=" + subset,
            )
        )
    for offset in range(0, lock["chembl_expected_total"], 1000):
        tasks.append(
            (
                f"chembl-2d6-{offset:05d}.json",
                "https://www.ebi.ac.uk/chembl/api/data/activity.json?"
                f"target_chembl_id=CHEMBL289&standard_type=IC50&limit=1000&offset={offset}",
            )
        )
    tasks.extend(
        [
            (
                "pubchem-891-description.json",
                "https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay/aid/891/description/JSON",
            ),
            ("chembl-status.json", "https://www.ebi.ac.uk/chembl/api/data/status.json"),
            ("chembl-target.json", "https://www.ebi.ac.uk/chembl/api/data/target/CHEMBL289.json"),
        ]
    )
    with httpx.Client(timeout=httpx.Timeout(90, connect=15), follow_redirects=True) as client:
        expected = {r["name"]: r["sha256"] for r in lock["files"]}

        def fetch(task: tuple[str, str]) -> dict[str, object]:
            name, url = task
            response = client.get(url)
            with (output / name).open("xb") as stream:
                stream.write(response.content)
            response.raise_for_status()
            if hashlib.sha256(response.content).hexdigest() != expected[name]:
                raise ValueError(
                    "Raw source changed: " + name + "; retain evidence and audit drift"
                )
            print(name, len(response.content), flush=True)
            return dict(
                name=name,
                url=url,
                sha256=hashlib.sha256(response.content).hexdigest(),
                bytes=len(response.content),
                status=response.status_code,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            records = list(executor.map(fetch, tasks))
    with (output / "manifest.json").open("x") as stream:
        json.dump(
            dict(
                fetched_at=datetime.now(UTC).isoformat(),
                files=records,
                chembl_expected_total=lock["chembl_expected_total"],
                pubchem_expected_sids=sids,
                source_discovery=dict(url=lock["concise_url"], sha256=lock["concise_sha256"]),
            ),
            stream,
            indent=2,
        )


if __name__ == "__main__":
    main()
