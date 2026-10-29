# aidd-agent

## Scope and sources

- Independent personal AIDD competition project. First task: OpenADMET CYP Direct Inhibition regression; execution order and actual status live in `docs/competition-plan.md`.
- Official source links and audited participation/submission constraints live in `docs/cyp-rules.md`. Pin dataset and tutorial revisions in each run; recheck rules before external submission.
- `pyproject.toml` and `uv.lock` define the Python environment; implementation uses `src/aidd_agent/`, tests use `tests/`. No dependency on quant-agent code, data or accounts.

## Research invariants

- Raw downloads are immutable, hashed and stored under ignored `state/`; never infer missing labels as zero or use test labels/leaderboard feedback for model selection.
- The first run uses only official public training data. Choose split, finite candidate budget and metrics before fitting. Keep identical molecules together; report local validation separately from official blind scores.
- Submission must match the official test identities, original SMILES and all four target columns, with 750 unique rows and finite predictions. Invalid input fails explicitly.
- Never claim registration, accepted submission, score or final rank without a corresponding platform receipt. Check the latest submission, not historical best, before replacing it.
- Credentials and optional personal contact details remain outside Git. Models, raw data, predictions, receipts and caches stay in `state/`; tracked reports contain only necessary summaries and artifact hashes.
- Use one real Hugging Face account for the team. Respect the 12-hour submission limit and disclose proprietary data/open-source status accurately.

## Verification and recovery

- Verified commands: `uv sync --frozen`, `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/aidd_agent`. The optional submission SDK uses `uv sync --frozen --group submission`.
- Optional CPU neural experiments use `uv sync --frozen --group neural` and `uv run --group neural pytest`; ordinary commands do not require PyTorch. Auxiliary-transfer protocols and evaluated outcomes live in `docs/round3-plan.md`, `docs/round3b-plan.md`, and `docs/round3-results.md`.
- Public CYP2D6 source acquisition is `uv run python scripts/fetch_cyp2d6.py`; `docs/round4-sources-lock.json` pins response hashes. `aidd audit-external` audits immutable sources before `aidd external` can fit. Assay/censoring semantics, global molecular exclusions and gates live in `docs/round4-plan.md`; outcomes live in `docs/round4-results.md`. External assay outcomes never become exact official pIC50 labels.
- Primary-paper/SI review of the 79 quarantined low records is locked in `docs/round5-evidence-lock.json`; the local manual evidence ledger remains in `state/sources/round5/locked-audit/`. `aidd censored --audit-dir ... --output-dir ...` verifies evidence hashes before interval fitting. Frozen decisions and negative results live in `docs/round5-plan.md` and `docs/round5-results.md`; two admitted inequalities do not restore exact labels.
- Round6 primary-source follow-up is locked in `docs/round6-evidence-lock.json`; use `aidd censored --plan-file docs/round6-plan.md --audit-dir state/sources/round6/locked-audit --output-dir ...`. Curcumin remains quarantined; four new source-native inequalities retain assay/structure limitations. Outcomes and source availability are recorded in `docs/round6-results.md`.
- Tests cover input/schema failures, molecule split isolation, official metric semantics and submission identity/finite-value validation. Unit tests do not access the network.
- Each run gets a fresh output directory. Failures retain diagnostic evidence; do not overwrite raw inputs or the last valid submission. Rerunning preparation must verify existing hashes.
- GitHub synchronization is authorized; commits use the verified personal GitHub identity. External submission uses the user's actual HF identity and the reviewed method report.
