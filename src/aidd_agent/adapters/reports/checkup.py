"""Serialize inspection results and write a fresh local static report.

@author cylovelife
"""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict
from html import escape
from pathlib import Path

from aidd_agent.adapters.rdkit.molecules import draw_grid, draw_svg
from aidd_agent.domain.molecules import CheckupResult, FingerprintConfig


def _write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")


def write_report(
    result: CheckupResult, output: Path, provenance: Mapping[str, object]
) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=False)
    records, cards = [], []
    valid_samples = []
    for index, row in enumerate(result.records):
        description = row.analysis.description if row.analysis is not None else None
        records.append(
            {
                "id": row.sample.id,
                "input_smiles": row.sample.smiles,
                "description": asdict(description) if description is not None else None,
                "error": row.error,
                "neighbors": [asdict(n) for n in row.neighbors],
            }
        )
        if description is None:
            cards.append(
                f"<article><h2>{escape(row.sample.id)}</h2>"
                f"<pre>{escape(row.sample.smiles)}</pre>"
                f"<p class='error'>{escape(row.error or '')}</p></article>"
            )
            continue
        valid_samples.append(row.sample)
        svg_name = f"molecule-{index:03d}.svg"
        (output / svg_name).write_text(draw_svg(row.sample.smiles), encoding="utf-8")
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
            f"<article><h2>{escape(row.sample.id)}</h2>"
            f"<pre>{escape(row.sample.smiles)}</pre><img src='{svg_name}' alt='分子结构'>"
            f"<table>{fields}</table><p>{warning}</p></article>"
        )
    if valid_samples:
        (output / "structures.png").write_bytes(draw_grid(valid_samples))
    _write_json(output / "molecules.json", records)
    neighbor_html = "".join(
        f"<li>{escape(str(row['id']))}: {escape(json.dumps(row['neighbors']))}</li>"
        for row in records
        if row["description"] is not None
    )
    html = _render_html(cards, neighbor_html, result.fingerprint)
    (output / "index.html").write_text(html, encoding="utf-8")
    report: dict[str, object] = {
        **provenance,
        "schema_version": 2,
        "input_count": len(result.records),
        "valid_count": len(valid_samples),
        "invalid_count": len(result.records) - len(valid_samples),
        "duplicate_identity_groups": [list(ids) for ids in result.duplicate_identity_groups],
        "fingerprint": asdict(result.fingerprint),
        "input_sha256": hashlib.sha256(
            json.dumps(
                [asdict(row.sample) for row in result.records], ensure_ascii=False, sort_keys=True
            ).encode()
        ).hexdigest(),
        "artifact_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir())
        },
    }
    _write_json(output / "report.json", report)
    return report


def _render_html(cards: list[str], neighbor_html: str, fingerprint: FingerprintConfig) -> str:
    return (
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
        f"<p>Morgan radius={fingerprint.radius}, {fingerprint.bits}bits, "
        f"includeChirality={fingerprint.include_chirality}</p>"
        f"<main>{''.join(cards)}</main><h2>结构近邻</h2><ul>{neighbor_html}</ul></html>"
    )
