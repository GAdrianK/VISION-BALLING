# VISION-BALLING agent rules

- Inspect only files relevant to the requested task.
- Use rg before opening large files.
- Do not load datasets, weights, videos or generated reports into context.
- Prefer the smallest behavior-preserving diff.
- Do not refactor unrelated code.
- Measure performance before optimizing.
- Run targeted tests during development.
- Before completion, run:
  - pytest backend/tests
  - ruff check backend scripts
  - git diff --check
- Summarize command output; do not paste complete logs unless an error requires it.
- Never commit datasets, videos, model weights or benchmark outputs.
- Never commit, push or merge without explicit permission.
