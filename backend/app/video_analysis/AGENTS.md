# Video Analysis Sub-module Agent Rules

- Respect exact SoccerNet evaluation standards (Action Spotting tolerance windows, mAP@tight/loose, Camera Calibration metrics, 2D/3D Tracking IoU).
- Keep video frame processing strictly generator-based / streaming to prevent RAM leaks; do not load full video tensors or raw frame arrays into context.
- Benchmark metric modifications must preserve mathematical exactness across all benchmark adapters (`benchmark_adapters.py`, `benchmark_metrics.py`).
- Run targeted tests for video pipeline changes (`pytest backend/tests/test_benchmark_sprint2_1.py` or dedicated video tests) before executing the full suite.
