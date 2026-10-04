#!/usr/bin/env python3
"""CLI Publication Tool for VISION-BALLING (Chapter 9).

Publishes local GPU analysis outputs (RTX 4060) to the secure cloud backend
(Cloudflare R2 + PostgreSQL on Railway) and generates a private coach access capability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("publish_analysis")

REQUIRED_ARTIFACTS = {
    "tactical_events.json": "application/json",
    "match_timeline.jsonl": "application/x-ndjson",
    "team_summary.json": "application/json",
    "event_graph.json": "application/json",
    "match_report.md": "text/markdown",
    "runtime.json": "application/json",
    "annotated.mp4": "video/mp4",
}


def compute_file_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def sanitize_runtime(runtime_raw: Dict[str, Any]) -> Dict[str, Any]:
    """Expurges local absolute paths from runtime.json, preserving only allowlisted metrics."""
    allowlist = {
        "device_name",
        "gpu_model",
        "inference_seconds",
        "processing_fps",
        "pipeline_mode",
        "frames_processed",
        "schema_version",
        "detector_model",
        "tracker_model",
    }
    return {k: v for k, v in runtime_raw.items() if k in allowlist}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish a local VISION-BALLING video analysis to private cloud portal."
    )
    parser.add_argument("--analysis-dir", required=True, type=Path, help="Directory containing analysis artifacts")
    parser.add_argument("--analysis-id", default=None, help="Explicit analysis ID (defaults to folder name)")
    parser.add_argument("--request-id", default=None, help="Beta request ID (e.g. beta_123456)")
    parser.add_argument("--version", default="v1", help="Publication version identifier (default: v1)")
    parser.add_argument(
        "--api-url",
        default=os.getenv("VB_API_URL", "http://localhost:8000"),
        help="Backend API base URL (e.g. https://api.vision-balling.fr or http://localhost:8000)",
    )
    parser.add_argument(
        "--publisher-token",
        default=os.getenv("VB_PUBLISHER_TOKEN", "dev-operator-token"),
        help="Operator secret token for authorization",
    )
    parser.add_argument("--notify", action="store_true", help="Send delivery email notification immediately")
    parser.add_argument("--recipient-email", default=None, help="Coach email address for delivery notification")
    parser.add_argument("--coach-name", default="Entraîneur", help="Coach full name for email greeting")
    parser.add_argument("--match-name", default=None, help="Descriptive match label (e.g. 'FC Nantes vs Rennes')")
    parser.add_argument("--dry-run", action="store_true", help="Validate artifacts and manifest without uploading")

    args = parser.parse_args()

    analysis_dir = args.analysis_dir.resolve()
    if not analysis_dir.is_dir():
        logger.error("Analysis directory does not exist: %s", analysis_dir)
        return 1

    analysis_id = args.analysis_id or analysis_dir.name
    logger.info("Preparing publication for analysis_id: '%s' from %s", analysis_id, analysis_dir)

    # 1. Verify and hash all 7 required artifacts
    artifacts_meta: Dict[str, Dict[str, Any]] = {}
    for filename, media_type in REQUIRED_ARTIFACTS.items():
        fpath = analysis_dir / filename
        if not fpath.is_file():
            logger.error("Missing required artifact: %s in %s", filename, analysis_dir)
            return 1
        sha256 = compute_file_sha256(fpath)
        size_bytes = fpath.stat().st_size
        artifacts_meta[filename] = {
            "name": filename,
            "sha256": sha256,
            "size_bytes": size_bytes,
            "media_type": media_type,
        }
        logger.info("  ✓ Artifact %-22s: %d bytes (SHA-256: %s...)", filename, size_bytes, sha256[:12])

    # 2. Parse runtime & summary to extract duration & fps
    runtime_path = analysis_dir / "runtime.json"
    try:
        with open(runtime_path, "r", encoding="utf-8") as f:
            runtime_data = json.load(f)
    except Exception as exc:
        logger.warning("Could not parse runtime.json: %s. Using default empty runtime.", exc)
        runtime_data = {}

    sanitized_rt = sanitize_runtime(runtime_data)

    # Read duration and fps from team_summary.json or runtime.json
    duration = float(runtime_data.get("duration_seconds") or 0.0)
    fps = float(runtime_data.get("fps") or 25.0)
    frame_count = int(runtime_data.get("frames_processed") or 0)

    summary_path = analysis_dir / "team_summary.json"
    if summary_path.is_file():
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                sdata = json.load(f)
                if not duration and "duration_seconds" in sdata:
                    duration = float(sdata["duration_seconds"])
        except Exception:
            pass

    manifest = {
        "schema_version": "1.0",
        "analysis_id": analysis_id,
        "version_id": args.version,
        "match_id": args.match_name or analysis_id,
        "request_id": args.request_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "video_duration_seconds": duration,
        "fps": fps,
        "frame_count": frame_count,
        "artifacts": artifacts_meta,
        "sanitized_runtime": sanitized_rt,
    }

    if args.dry_run:
        logger.info("=== DRY-RUN MODE: Manifest validated ===")
        print(json.dumps(manifest, indent=2))
        return 0

    api_url = args.api_url.rstrip("/")
    headers = {
        "Authorization": f"Bearer {args.publisher_token.strip()}",
        "Content-Type": "application/json",
    }

    # 3. Step 1: Initiate publication (acquire fencing token & staging upload targets)
    initiate_payload = {
        "analysis_id": analysis_id,
        "request_id": args.request_id,
        "version_id": args.version,
        "manifest": manifest,
    }

    logger.info("Initiating publication staging with %s/api/internal/publications/initiate...", api_url)
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(f"{api_url}/api/internal/publications/initiate", json=initiate_payload, headers=headers)
        if resp.status_code != 200:
            logger.error("Initiation failed (%d): %s", resp.status_code, resp.text)
            return 1
        init_data = resp.json()

    finalization_id = init_data["finalization_id"]
    fencing_token = init_data["fencing_token"]
    upload_targets = init_data.get("upload_targets", {})
    logger.info("  ✓ Staging registered (finalization_id=%s, fencing_token=%d)", finalization_id, fencing_token)

    # 4. Step 2: Upload artifacts to targets
    for filename, upload_url in upload_targets.items():
        fpath = analysis_dir / filename
        media_type = REQUIRED_ARTIFACTS[filename]
        logger.info("  -> Uploading %s (%d bytes)...", filename, fpath.stat().st_size)

        if upload_url.startswith("/"):
            # Internal backend endpoint fallback
            full_url = f"{api_url}{upload_url}"
        else:
            full_url = upload_url

        with open(fpath, "rb") as f:
            content = f.read()

        with httpx.Client(timeout=180.0) as client:
            upload_resp = client.put(full_url, content=content, headers={"Content-Type": media_type})
            if upload_resp.status_code not in (200, 201, 204):
                logger.error("Failed to upload %s (%d): %s", filename, upload_resp.status_code, upload_resp.text)
                return 1

    logger.info("  ✓ All 7 artifacts successfully uploaded.")

    # 5. Step 3: Finalize and promote to active publication
    finalize_payload = {
        "analysis_id": analysis_id,
        "version_id": args.version,
        "finalization_id": finalization_id,
        "fencing_token": fencing_token,
        "recipient_email": args.recipient_email,
        "coach_name": args.coach_name,
        "match_name": args.match_name or analysis_id,
        "notify": args.notify,
    }

    logger.info("Promoting publication to active state...")
    with httpx.Client(timeout=30.0) as client:
        fin_resp = client.post(f"{api_url}/api/internal/publications/finalize", json=finalize_payload, headers=headers)
        if fin_resp.status_code != 200:
            logger.error("Finalization failed (%d): %s", fin_resp.status_code, fin_resp.text)
            return 1
        fin_data = fin_resp.json()

    logger.info("==================================================================")
    logger.info("✅ PUBLICATION COMPLETED SUCCESSFULLY")
    logger.info("==================================================================")
    logger.info("Analysis ID : %s", fin_data["analysis_id"])
    logger.info("Version     : %s", fin_data["version_id"])
    logger.info("Status      : %s", fin_data["status"])
    logger.info("Published At: %s", fin_data["published_at"])
    logger.info("Private URL : %s", fin_data["access_url"])
    logger.info("Notification: %s", "Enqueued / Sent" if fin_data.get("notification_queued") else "Skipped")
    logger.info("==================================================================")

    return 0


if __name__ == "__main__":
    sys.exit(main())
