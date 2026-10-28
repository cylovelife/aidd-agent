# OpenADMET CYP 2026 — first regression baseline

Participant: `cylovelife` (individual). Public implementation: [cylovelife/aidd-agent](https://github.com/cylovelife/aidd-agent). Initial experiment: 2026-10-28. Track: Direct Inhibition Regression only.

## Data and disclosure

This entry uses only the public official inhibition training set from [openadmet/cyp-challenge-train-test](https://huggingface.co/datasets/openadmet/cyp-challenge-train-test), revision `d7eb3c973dca01aad8e33c91c29e5123fd925d8f`. It uses no proprietary data, no external training data and no pretrained model. Dataset card: Apache-2.0. Input hashes are recorded in [data-manifest.json](data-manifest.json).

There are 4,905 training molecules and 750 blinded test molecules. Canonical RDKit SMILES were unique within both sets, with no exact canonical train/test overlap. Canonicalization does not strip salts, neutralize molecules or alter the original submission SMILES. Missing endpoint labels are excluded independently rather than imputed as negatives or zeros. Assay confidence intervals are used for evaluation only, never as predictive features.

## Representation and validation

- RDKit Morgan fingerprints: radius 2, 2,048 bits.
- One fixed 80/20 group holdout using seed 42. Groups are Bemis–Murcko scaffolds (without chirality); acyclic molecules use canonical molecule identity. Identical canonical molecules and scaffold groups cannot cross partitions.
- 3,931 molecules fall in the fitting partition and 974 in validation. Measured-label counts vary by endpoint.
- This is a development split used for model selection, **not** an independent sealed test. The analog-expansion distribution of the official test may differ substantially from this scaffold holdout. This split also does not guarantee low similarity between every pair of molecules in different partitions.

## Finite model budget and results

Three fixed candidates were evaluated without a hyperparameter search:

| Candidate | Parameters | Macro ST-RAE point estimate ↓ |
|---|---|---:|
| Training median | Independent constant for each endpoint | 0.974824 |
| Morgan + Ridge | alpha=10, solver=lsqr | 1.005436 |
| Morgan + ExtraTrees | 160 trees, min_samples_leaf=2, max_features=0.7, seed=42 | 1.049333 |

ST-RAE uses the unmodified official function from [CYP-Challenge-Tutorial](https://github.com/OpenADMET/CYP-Challenge-Tutorial), commit `832ae6d6447b07c2c71059de34d07f1130388247`, including tolerance in both numerator and mean-reference denominator. Local values are full-holdout **point estimates**, not the official leaderboard's 1,000-bootstrap averages. Four endpoints are equally macro-averaged.

The Ridge model was selected among the two nonconstant model candidates and then refitted independently for each endpoint on all measured training labels. The constant model remains a local reference: the live platform prohibits constant or near-constant predictions. The selected model did **not** beat the median reference on this holdout; this entry establishes a reproducible participation baseline and does not demonstrate a general predictive improvement.

## Submitted artifact and reproduction

The 750-row CSV preserves official Molecule_Name/SMILES pairs and supplies all four finite prediction columns. It passes the vendored official activity validator and stricter local identity, row-count and live-platform nonconstant checks.

- Prediction SHA256: `a500cdab26d27142a840a785643b71e3356388dd9a3600c8296e298977f5b47c`.
- Two local runs produced byte-identical prediction files and identical validation scores.
- Python 3.12, locked dependencies in `uv.lock`; detailed versions and per-endpoint results in [run-2026-10-28.md](run-2026-10-28.md).
- Reproduce with the commands in the repository [README](../README.md), using a new output directory.

No official score is claimed in this report until the corresponding platform receipt has been recorded. Subsequent changes will distinguish local experiments, received submissions, scored submissions and final rankings.
