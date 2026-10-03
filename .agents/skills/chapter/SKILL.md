---
name: chapter
description: Standard development lifecycle workflow for VISION-BALLING project chapters (Checkpoint -> Research -> Plan -> Implementation -> Targeted validation -> Broader validation -> Review -> Final checkpoint).
---

# VISION-BALLING Chapter Workflow

This workflow structures every development chapter, sprint, and substantial feature milestone in VISION-BALLING into an 8-phase reproducible lifecycle.

## Phase 1: Checkpoint (Initial State Inspection)

Before modifying anything:
1. Verify Git branch: confirm active branch matches expectations.
2. Verify Git HEAD commit and hash.
3. Check working tree status: run `git status` to ensure a clean or well-understood baseline.
4. Verify relevant repository manifests, datasets, and frozen decisions:
   - Check `data/manifests/` and dataset locks if touching evaluation or pipelines.
   - Confirm anti-leakage policy (`golden_eval` strictly isolated from training).

## Phase 2: Research

Investigate without modifying code:
1. Identify relevant files, modules, and interfaces.
2. Delegate broad exploratory searches to the built-in `research` subagent to conserve token context.
3. Formulate and return:
   - Relevant files and line references
   - Proposed implementation path
   - Relevant existing tests and test coverage
   - Dependencies and constraints
   - Technical, regression, and anti-leakage risks

## Phase 3: Plan

Formulate a clear, scoped plan:
- **Goal**: Concise definition of the chapter's objective.
- **Expected files**: List of files to modify, create, or delete.
- **Tests**: Exact test commands and verification scripts to run.
- **Acceptance criteria**: Strict pass/fail gates (e.g. metrics, checksums, test outcomes).
- Obtain user confirmation or proceed according to planning mode policy.

## Phase 4: Implementation

Execute scoped modifications:
- Make only the smallest correct change satisfying the task.
- Adhere strictly to the Ponytail intensity tiers defined in [AGENTS.md](../../../AGENTS.md):
  - Backend / Tooling: Full
  - ML / Tracking / Evaluation / Datasets: Lite (never simplify away reproducibility, validation, or metrics)
- Do not refactor unrelated code or alter project formatting.
- Never fabricate data, metrics, annotations, or test passes.

## Phase 5: Targeted Validation

Run focused tests immediately:
- Execute unit tests directly covering the modified files.
- On Windows, always pass `--basetemp` inside a safe project-relative directory (e.g. `data/golden/pytest-temp`) if temp permissions cause `[WinError 5]`.
- Fix any immediate regressions or test failures before proceeding.

## Phase 6: Broader Validation

Validate system-wide stability:
- Run broader test suites or benchmark verification scripts (e.g., `verify_golden_videos.py`, `verify_internal_validation_dataset.py`, `test_video_pipeline.py`).
- Run relevant benchmark evaluations only after targeted tests pass.
- Do not run unrequested expensive ML training.

## Phase 7: Independent Review

Audit the complete diff:
- Inspect `git diff` carefully for extraneous edits or accidental deletions.
- For substantial modifications, invoke the `vision-reviewer` subagent to audit:
  1. Correctness
  2. Benchmark & evaluation integrity
  3. Regressions
  4. Dataset safety & anti-leakage
  5. Test validity
  6. Unnecessary complexity
  7. Performance & memory transfers

## Phase 8: Final Checkpoint & Handoff

Produce a concise completion report containing:
- Current branch and HEAD
- Files modified / created
- Implementation summary
- Targeted tests executed and results
- Broader / full tests executed and results
- Benchmark metrics (if applicable)
- Remaining blockers or manual gates (e.g., CVAT instance requirements)
- Git status (confirming working tree state)
- **Reminder**: Never commit or push unless explicitly requested by the user.
