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
- Tests cover input/schema failures, molecule split isolation, official metric semantics and submission identity/finite-value validation. Unit tests do not access the network.
- Each run gets a fresh output directory. Failures retain diagnostic evidence; do not overwrite raw inputs or the last valid submission. Rerunning preparation must verify existing hashes.
- GitHub synchronization is authorized; commits use the verified personal GitHub identity. External submission uses the user's actual HF identity and the reviewed method report.
