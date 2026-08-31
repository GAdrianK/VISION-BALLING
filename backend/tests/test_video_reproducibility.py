from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.video_analysis.reproducibility import (
    GIT_SHA_ENV,
    ModelIdentity,
    build_analysis_key,
    build_canonical_config,
    canonical_config_json,
    resolve_git_sha,
    resolve_model_identity,
)
from app.video_analysis.schemas import (
    AnalysisJob,
    AnalysisResult,
    JobStatus,
    PipelineMetadata,
    VideoMetadata,
)


def _settings(**overrides) -> Settings:
    values = {
        "VIDEO_DETECTOR": "yolo",
        "VIDEO_MODEL_PATH": "weights.pt",
        "VIDEO_MODEL_PROFILE": "coco",
        "VIDEO_PERSON_CONFIDENCE_THRESHOLD": 0.45,
        "VIDEO_BALL_CONFIDENCE_THRESHOLD": 0.25,
        "VIDEO_FRAME_SAMPLE_RATE": 3,
        "VIDEO_TRACKING_ENABLED": True,
        "VIDEO_TRACKER": "iou",
        "VIDEO_PRESERVE_AUDIO": True,
    }
    values.update(overrides)
    return Settings(**values)


def _model(checksum: str = "a" * 64) -> ModelIdentity:
    return ModelIdentity(
        detector_name="yolo",
        detector_version="8.3.0",
        model_id="weights.pt",
        model_checksum=checksum,
    )


def _config(
    settings: Settings,
    model: ModelIdentity | None = None,
    *,
    pipeline_version: str = "0.3.0",
) -> dict:
    tracker_name = settings.VIDEO_TRACKER if settings.VIDEO_TRACKING_ENABLED else "none"
    return build_canonical_config(
        settings,
        model or _model(),
        tracker_name=tracker_name,
        tracker_version="1.0",
        pipeline_version=pipeline_version,
    )


def _key(
    settings: Settings,
    model: ModelIdentity | None = None,
    *,
    pipeline_version: str = "0.3.0",
) -> str:
    identity = model or _model()
    return build_analysis_key(
        "source-sha",
        identity.model_checksum,
        _config(settings, identity, pipeline_version=pipeline_version),
        pipeline_version=pipeline_version,
    )


def test_canonical_json_and_analysis_key_ignore_dict_order():
    config = _config(_settings())
    reordered = dict(reversed(list(config.items())))
    reordered["detector"] = dict(reversed(list(config["detector"].items())))

    assert canonical_config_json(config) == canonical_config_json(reordered)
    assert build_analysis_key("source", "model", config) == build_analysis_key(
        "source", "model", reordered
    )


def test_same_source_and_configuration_produce_same_analysis_key():
    assert _key(_settings()) == _key(_settings())


def test_threshold_change_produces_a_different_analysis_key():
    assert _key(_settings()) != _key(
        _settings(VIDEO_PERSON_CONFIDENCE_THRESHOLD=0.55)
    )


def test_tracker_change_produces_a_different_analysis_key():
    assert _key(_settings()) != _key(_settings(VIDEO_TRACKER="none"))


def test_sampling_change_produces_a_different_analysis_key():
    assert _key(_settings()) != _key(_settings(VIDEO_FRAME_SAMPLE_RATE=5))


def test_pipeline_version_change_produces_a_different_analysis_key():
    settings = _settings()
    assert _key(settings, pipeline_version="0.3.0") != _key(
        settings, pipeline_version="0.4.0"
    )


def test_video_normalizer_change_produces_a_different_analysis_key():
    settings = _settings()
    ffmpeg_config = build_canonical_config(
        settings,
        _model(),
        tracker_name="iou",
        tracker_version="1.0",
        video_backend="ffmpeg",
        ffmpeg_version="ffmpeg 8.0",
    )
    fallback_config = build_canonical_config(
        settings,
        _model(),
        tracker_name="iou",
        tracker_version="1.0",
        video_backend="opencv",
    )

    assert build_analysis_key("source", "model", ffmpeg_config) != (
        build_analysis_key("source", "model", fallback_config)
    )


def test_model_checksum_change_produces_a_different_analysis_key():
    first = _model()
    second = replace(first, model_checksum="b" * 64)
    assert _key(_settings(), first) != _key(_settings(), second)


def test_real_model_file_checksum_is_cached_and_path_free(tmp_path: Path):
    weights = tmp_path / "private" / "weights.pt"
    weights.parent.mkdir()
    weights.write_bytes(b"first model")
    cache: dict[tuple[str, int, int], str] = {}
    settings = _settings(VIDEO_MODEL_PATH=str(weights))
    metadata = {"name": "yolo", "version": "8.3.0", "model_id": str(weights)}

    first = resolve_model_identity(
        settings, metadata, backend_root=tmp_path, checksum_cache=cache
    )
    second = resolve_model_identity(
        settings, metadata, backend_root=tmp_path, checksum_cache=cache
    )

    assert first == second
    assert first.model_id == "weights.pt"
    assert first.model_checksum == hashlib.sha256(b"first model").hexdigest()
    assert len(cache) == 1
    assert str(tmp_path) not in canonical_config_json(_config(settings, first))

    weights.write_bytes(b"second model with different size")
    changed = resolve_model_identity(
        settings, metadata, backend_root=tmp_path, checksum_cache=cache
    )
    assert changed.model_checksum != first.model_checksum
    assert len(cache) == 1


def test_git_sha_environment_override_has_priority(monkeypatch: pytest.MonkeyPatch):
    expected = "A" * 40
    monkeypatch.setenv(GIT_SHA_ENV, expected)
    monkeypatch.setattr(
        "app.video_analysis.reproducibility.subprocess.run",
        lambda *args, **kwargs: pytest.fail("git ne doit pas être appelé"),
    )

    assert resolve_git_sha() == expected.lower()


def test_git_sha_uses_repository_when_available(monkeypatch: pytest.MonkeyPatch):
    expected = "b" * 40
    monkeypatch.delenv(GIT_SHA_ENV, raising=False)

    def fake_run(command, **kwargs):
        assert command[:2] == ["git", "-C"]
        assert kwargs["shell"] is False
        return SimpleNamespace(stdout=f"{expected}\n")

    monkeypatch.setattr(
        "app.video_analysis.reproducibility.subprocess.run", fake_run
    )

    assert resolve_git_sha(repository_root=Path("repo")) == expected


def test_git_sha_is_unknown_when_git_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv(GIT_SHA_ENV, raising=False)

    def unavailable(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(
        "app.video_analysis.reproducibility.subprocess.run", unavailable
    )

    assert resolve_git_sha(repository_root=Path("repo")) == "unknown"


def test_reproducibility_structures_do_not_leak_api_keys():
    secrets = {
        "OPENAI_API_KEY": "openai-super-secret",
        "GEMINI_API_KEY": "gemini-super-secret",
        "GOOGLE_API_KEY": "google-super-secret",
        "OPENROUTER_API_KEY": "openrouter-super-secret",
        "APISPORTS_KEY": "sports-super-secret",
    }
    settings = _settings(**secrets)
    config = _config(settings)
    metadata = PipelineMetadata(
        detector="weights.pt",
        frame_interval=3,
        device="cpu",
        source_sha256="source",
        analysis_key=_key(settings),
        model_id="weights.pt",
        model_checksum="a" * 64,
        canonical_config=config,
    )
    job = AnalysisJob(
        analysis_id="analysis_test",
        match_id="match_test",
        source_sha256="source",
        analysis_key=metadata.analysis_key,
        pipeline=metadata,
    )
    result = AnalysisResult(
        analysis_id="analysis_test",
        match_id="match_test",
        status=JobStatus.COMPLETED,
        video=VideoMetadata(
            filename="source.mp4",
            duration_seconds=1,
            fps=25,
            width=320,
            height=240,
            frame_count=25,
        ),
        pipeline=metadata,
    )
    serialized = json.dumps(
        {
            "canonical_config": config,
            "analysis_key_inputs": config,
            "pipeline": metadata.model_dump(mode="json"),
            "job": job.model_dump(mode="json"),
            "result": result.model_dump(mode="json"),
        }
    )

    for name, value in secrets.items():
        assert name not in serialized
        assert value not in serialized
