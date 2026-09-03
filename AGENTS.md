# VISION-BALLING Agent Guidelines

## Mission

VISION-BALLING is a football computer-vision project focused on:
- Player and ball detection
- Multi-object tracking
- Reproducible evaluation
- Football video analysis
- Benchmark datasets
- Golden validation datasets

## Core Development Rules

- Make the smallest correct change satisfying the task.
- Do not refactor unrelated code.
- Reuse existing abstractions and dependencies before adding new ones.
- Never fabricate metrics, annotations, datasets, test results, or benchmark results.
- Reproducibility and evaluation correctness take priority over code brevity.

## Repository Exploration

Before editing:
1. Inspect git status and branch.
2. Search relevant symbols/files first (`grep_search`, `find_by_name`).
3. Read only files necessary for the task (`view_file` with line slices).

Avoid recursive exploration of:
- Datasets (`data/`, `data/golden/`, `data/manifests/`)
- Videos and sources (`data/golden/sources/`, `data/golden/assets/`)
- Model weights
- Runs and outputs (`data/golden/runs/`)
- Virtual environments (`.venv/`, `backend/.venv/`)
- Cache directories (`.pytest_cache/`, `__pycache__/`)

Prefer targeted search and `git diff` rather than repeatedly reading large files.
Delegate broad repository exploration to the built-in `research` subagent to conserve context window.

## ML / Computer Vision Safeguards

Never simplify away:
- Reproducibility settings (random seeds, determinism flags)
- Deterministic execution parameters (FPS-aware timing, frame indexing)
- Dataset validation (checksums, schema contracts, partition policies)
- Metric correctness (HOTA, AssA, DetA, mAP, precision/recall)
- Evaluation checks and split policies (`golden_eval` must NEVER leak into training)
- Experiment metadata and benchmark comparability
- Input validation at trust boundaries

Do not alter model, tracking, or evaluation semantics merely to reduce code size.

## Ponytail Intensity Policy

- **Backend / Frontend / Tooling**: Ponytail Full (favor standard library, native APIs, minimal code).
- **ML / Tracking / Evaluation / Benchmarks / Datasets**: Ponytail Lite (maintain rigorous validation, typed contracts, defensive assertions, and determinism).
- **Aggressive simplification (Ultra)**: Only when explicitly requested by the user.
- **Experimental research architecture**: Ponytail may be temporarily disabled.
- **Inviolable constraint**: Ponytail must never simplify away reproducibility, validation, metric correctness, benchmark integrity, or necessary error handling.

## Testing

- Run targeted tests first (e.g. specific test file or test case).
- On Windows, always pass `--basetemp` inside a safe project-relative directory (e.g., `data/golden/pytest-temp`) if temp permissions cause `[WinError 5]`.
- Run broader tests when appropriate before completing a chapter or substantial feature.
- Never weaken, bypass, or mock out tests merely to make them pass.

## Git

- Never reset or force-push.
- Never delete unrelated work or working tree files.
- Never commit or push unless explicitly requested.
- Keep all changes strictly scoped to the active mission.

## Completion Output

Report concisely:
- Files changed
- Tests executed and commands used
- Validation results and key metrics
- Remaining blockers or manual gates (e.g. CVAT instance requirement)
- Clean, summarized logs instead of raw terminal dumps
