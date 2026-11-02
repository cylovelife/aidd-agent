"""Label-free molecular inspection for the first AIDD learning project.

@author cylovelife
"""

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from html import escape
from pathlib import Path

from rdkit import Chem, DataStructs, rdBase
from rdkit.Chem import Crippen, Descriptors, rdFingerprintGenerator, rdMolDescriptors
from rdkit.Chem.Draw import rdMolDraw2D


@dataclass(frozen=True)
class MoleculeDescription:
    canonical_smiles: str
    formula: str
    atom_count: int
    heavy_atom_count: int
    fragment_count: int
    formal_charge: int
    molecular_weight: float
    calculated_logp: float
    hbd: int
    hba: int
    tpsa: float
    rotatable_bonds: int
    ring_count: int


def _parse(smiles: str) -> Chem.Mol:
    if not isinstance(smiles, str) or not smiles.strip():
        raise ValueError("SMILES must be a non-empty string")
    text = smiles.strip()
    if any(c.isspace() for c in text):
        raise ValueError("SMILES must not contain a name or internal whitespace")
    params = Chem.SmilesParserParams()
    # RDKit's property setter stubs currently misdeclare these boolean attributes.
    params.parseName = False  # type: ignore[assignment]
    params.allowCXSMILES = False  # type: ignore[assignment]
    with rdBase.BlockLogs():
        mol = Chem.MolFromSmiles(text, params)
    if mol is None or mol.GetNumAtoms() == 0:
        raise ValueError("Invalid SMILES: structure parsing or valence check failed")
    return mol


def _describe(mol: Chem.Mol) -> MoleculeDescription:
    result = MoleculeDescription(
        canonical_smiles=Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True),
        formula=rdMolDescriptors.CalcMolFormula(mol),
        atom_count=mol.GetNumAtoms(),
        heavy_atom_count=mol.GetNumHeavyAtoms(),
        fragment_count=len(Chem.GetMolFrags(mol)),
        formal_charge=sum(atom.GetFormalCharge() for atom in mol.GetAtoms()),
        # These two public descriptors are exported dynamically by RDKit.
        molecular_weight=float(Descriptors.MolWt(mol)),  # type: ignore[attr-defined]
        calculated_logp=float(Crippen.MolLogP(mol)),  # type: ignore[attr-defined]
        hbd=rdMolDescriptors.CalcNumHBD(mol),
        hba=rdMolDescriptors.CalcNumHBA(mol),
        tpsa=float(rdMolDescriptors.CalcTPSA(mol)),
        rotatable_bonds=rdMolDescriptors.CalcNumRotatableBonds(mol),
        ring_count=rdMolDescriptors.CalcNumRings(mol),
    )
    if not all(
        math.isfinite(v) for v in (result.molecular_weight, result.calculated_logp, result.tpsa)
    ):
        raise ValueError("Nonfinite molecular descriptors")
    return result


def describe_smiles(smiles: str) -> MoleculeDescription:
    """Inspect the whole input graph, preserving fragments, charges and stereo."""
    return _describe(_parse(smiles))


def _write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")


def run_checkup(
    samples: Sequence[Mapping[str, str]],
    output: Path,
    *,
    use_chirality: bool = False,
    top_k: int = 3,
) -> dict[str, object]:
    """Write a fresh static report; invalid molecules remain visible in the ledger."""
    if not 1 <= len(samples) <= 200 or not 1 <= top_k <= 20:
        raise ValueError("Use 1..200 samples and top_k between 1 and 20")
    ids = []
    for sample in samples:
        if (
            not isinstance(sample, Mapping)
            or not isinstance(sample.get("id"), str)
            or not sample["id"].strip()
            or not isinstance(sample.get("smiles"), str)
        ):
            raise ValueError("Each sample requires string id and smiles")
        ids.append(sample["id"])
    if len(set(ids)) != len(ids):
        raise ValueError("Sample ids must be unique")
    output.mkdir(parents=True, exist_ok=False)
    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=2, fpSize=2048, includeChirality=use_chirality
    )
    records: list[dict[str, object]] = []
    valid: dict[int, tuple[Chem.Mol, MoleculeDescription]] = {}
    identities: dict[str, list[str]] = {}
    cards = []
    for index, sample in enumerate(samples):
        record: dict[str, object] = {
            "id": sample["id"],
            "input_smiles": sample["smiles"],
            "description": None,
            "error": None,
            "neighbors": [],
        }
        try:
            mol = _parse(sample["smiles"])
        except ValueError as error:
            record["error"] = str(error)
            cards.append(
                f"<article><h2>{escape(sample['id'])}</h2>"
                f"<pre>{escape(sample['smiles'])}</pre>"
                f"<p class='error'>{escape(str(error))}</p></article>"
            )
        else:
            description = _describe(mol)
            valid[index] = mol, description
            identities.setdefault(description.canonical_smiles, []).append(sample["id"])
            record["description"] = asdict(description)
            drawer = rdMolDraw2D.MolDraw2DSVG(320, 220)
            drawer.DrawMolecule(mol)
            drawer.FinishDrawing()
            svg_name = f"molecule-{index:03d}.svg"
            (output / svg_name).write_text(drawer.GetDrawingText(), encoding="utf-8")
            warning = (
                "多片段：数值针对完整输入图；未去盐，logP不作该盐的实测分配系数解释。"
                if description.fragment_count > 1
                else "描述符由结构计算；未使用实验活性标签。"
            )
            fields = "".join(
                f"<tr><th>{escape(key)}</th><td>{escape(str(value))}</td></tr>"
                for key, value in asdict(description).items()
            )
            cards.append(
                f"<article><h2>{escape(sample['id'])}</h2>"
                f"<pre>{escape(sample['smiles'])}</pre><img src='{svg_name}' alt='分子结构'>"
                f"<table>{fields}</table><p>{warning}</p></article>"
            )
        records.append(record)
    fingerprints = {i: generator.GetFingerprint(mol) for i, (mol, _) in valid.items()}
    for index, (_, description) in valid.items():
        ranked = sorted(
            (
                (float(DataStructs.TanimotoSimilarity(fingerprints[index], fingerprints[j])), j)
                for j, (_, other) in valid.items()
                if other.canonical_smiles != description.canonical_smiles
            ),
            key=lambda pair: (-pair[0], pair[1]),
        )
        seen: set[str] = set()
        neighbors = []
        for similarity, j in ranked:
            identity = valid[j][1].canonical_smiles
            if identity in seen:
                continue
            seen.add(identity)
            neighbors.append({"id": samples[j]["id"], "tanimoto": similarity})
            if len(neighbors) == top_k:
                break
        records[index]["neighbors"] = neighbors
    if valid:
        rows = (len(valid) + 2) // 3
        grid = rdMolDraw2D.MolDraw2DCairo(960, rows * 220, 320, 220)
        grid.DrawMolecules([mol for mol, _ in valid.values()], legends=[ids[i] for i in valid])
        grid.FinishDrawing()
        (output / "structures.png").write_bytes(grid.GetDrawingText())
    _write_json(output / "molecules.json", records)
    neighbor_html = "".join(
        f"<li>{escape(str(row['id']))}: {escape(json.dumps(row['neighbors']))}</li>"
        for row in records
        if row["description"] is not None
    )
    html = (
        "<!doctype html><html lang='zh-CN'><meta charset='utf-8'>"
        "<title>分子体检学习报告</title><style>body{font:16px system-ui;max-width:1100px;"
        "margin:30px auto;padding:16px;background:#f6f8fa;color:#18202a}main{display:grid;"
        "grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:20px}article{background:"
        "white;padding:20px;border:1px solid #ddd;border-radius:10px}img{max-width:100%}"
        "table{font-size:14px;width:100%;border-collapse:collapse}th,td{text-align:left;"
        "border-bottom:1px solid #eee;padding:5px;overflow-wrap:anywhere}pre{white-space:"
        "pre-wrap}.error{color:#a21b18}li{margin:8px 0}</style><h1>分子体检：结构与表示</h1>"
        "<p>MolWt单位g/mol，TPSA单位Å²；MolLogP为计算值，不是logD或实验测量。"
        "canonical SMILES保留电荷/片段/已指定手性，不代表跨版本通用化学身份。"
        "近邻排除同一规范结构，按结构身份去重；相似度不等于活性相同。</p>"
        f"<p>Morgan radius=2, 2048bits, includeChirality={use_chirality}</p>"
        f"<main>{''.join(cards)}</main><h2>结构近邻</h2><ul>{neighbor_html}</ul></html>"
    )
    (output / "index.html").write_text(html, encoding="utf-8")
    result: dict[str, object] = {
        "rdkit_version": rdBase.rdkitVersion,
        "input_count": len(samples),
        "valid_count": len(valid),
        "invalid_count": len(samples) - len(valid),
        "duplicate_identity_groups": [v for v in identities.values() if len(v) > 1],
        "fingerprint": {"radius": 2, "bits": 2048, "include_chirality": use_chirality},
        "input_sha256": hashlib.sha256(
            json.dumps(list(samples), ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest(),
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "artifact_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir())
        },
    }
    _write_json(output / "report.json", result)
    return result
