---
name: vision-balling
description: Specialized procedures and constraints for football video analysis, YOLO, player detection, ball detection, tracking, SoccerNet, datasets, benchmarks, evaluation metrics, video pipelines, and computer-vision experiments.
---

# VISION-BALLING Project Skill

This skill governs domain-specific computer-vision, tracking, evaluation, and dataset integrity constraints. For repository-wide exploration, Ponytail tiers, testing, and git rules, refer to [AGENTS.md](../../../AGENTS.md). For end-to-end chapter execution, use [/chapter](../chapter/SKILL.md).

## 1. Detection

- **Class mappings**: Preserve all canonical object classes (`player`, `goalkeeper`, `referee`, `ball`, `ignore_person`, `ignore_region`). Never invent classes or collapse distinctions without an explicit design change.
- **Inference parameters**: Preserve confidence thresholds, IoU thresholds, and NMS semantics unless explicitly instructed to calibrate them.
- **Benchmark comparability**: Ensure evaluation parameters match established baselines so scores remain comparable across pipeline versions.
- **Metric reporting**: Explicitly report measured metric deltas (precision, recall, mAP@0.5, mAP@0.5:0.95); never assume or claim improvement without verified evaluation runs.

## 2. Tracking

- **Quality separation**: Strictly distinguish detection errors (missed objects, false positives) from association errors (ID switches, fragmentations).
- **Identity semantics**: Preserve local identity continuity within sequences. Never bridge tracks across discontinuous camera cuts or unverified occlusions without evidence.
- **Tracking metrics**: Verify relevant metrics when evaluating tracking pipelines: HOTA, DetA, AssA, IDF1, and ID switches (IDSW).
- **Coordinate & temporal conventions**: Maintain 0-based frame indexing, exact video FPS synchronization, and unscaled original-resolution bounding-box coordinates `[xtl, ytl, xbr, ybr]` or `[x, y, w, h]` strictly according to the format contract.

## 3. Evaluation

Never:
- Infer missing ground truth or fill blanks with heuristics.
- Fabricate annotations or use model predictions as ground truth.
- Silently ignore or drop malformed samples or corrupted frames.
- Alter metric definitions or thresholds to artificially inflate scores.

Always distinguish and evaluate:
- Detection: Precision, Recall, F1, mAP@0.5, mAP@0.5:0.95.
- Tracking: HOTA, DetA, AssA, IDF1, MOTA.
- Calibration & Events: Mean reprojection error, keypoint accuracy, event frame accuracy.

## 4. Datasets & Anti-Leakage Policy

- **Partition separation**: Keep public benchmark data (e.g. SoccerNet, Kaggle) strictly isolated from private golden validation data (`data/golden/`).
- **Zero leakage**: The golden dataset role is strictly `golden_eval`. No golden frames, videos, crops, annotations, or derived exports may ever enter training, validation splits, or fine-tuning pipelines.
- **Source media integrity**: Never modify, re-encode, or overwrite original golden source videos or raw lossless PNG media.
- **Validation gates**: Always validate paths, class names, frame UIDs (`golden_sha256:frame_index`), annotation schemas, and check for duplicates before freezing.

## 5. Performance & Hardware

- **Bottleneck-driven**: Measure and profile before optimizing. Do not introduce premature complexity.
- **GPU efficiency**:
  - Minimize unnecessary host-to-device (CPU <-> GPU) memory transfers.
  - Stream or batch video frames; never load entire multi-gigabyte videos into RAM at once.
  - Preserve deterministic execution (`torch.use_deterministic_algorithms`, fixed seeds) during benchmarking and evaluation.
