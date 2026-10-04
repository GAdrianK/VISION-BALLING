from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import BASE_DIR
from app.services.match_evidence_store import MatchEvidenceRegistry, MatchEvidenceStore
from app.services.publication_service import PublicationService, get_publication_service
from app.services.r2_storage import R2StorageService, get_r2_storage

logger = logging.getLogger(__name__)

DEFAULT_EVIDENCE_CACHE_DIR = BASE_DIR / "data" / "evidence_cache"


@dataclass(frozen=True)
class EvidenceVersionSpec:
    analysis_id: str
    version_id: str = "v1"
    evidence_sha256: Optional[str] = None


class EvidenceResolver:
    """Multi-tier resolver for verified tactical evidence:
    
    L1: In-memory store cache (MatchEvidenceRegistry)
    L2: Local disk cache (data/evidence_cache/{analysis_id}/{version_id})
    L3: Cloud storage (Cloudflare R2) via PublicationService
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        pub_service: Optional[PublicationService] = None,
        r2_storage: Optional[R2StorageService] = None,
    ) -> None:
        self.cache_dir = cache_dir or DEFAULT_EVIDENCE_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.pub_service = pub_service or get_publication_service()
        self.r2 = r2_storage or get_r2_storage()

    def resolve_evidence_dir(self, analysis_id: str) -> Path:
        """Resolves the authoritative local directory containing tactical evidence for analysis_id.
        
        Raises FileNotFoundError if evidence cannot be resolved.
        NEVER falls back to demo data for real matches.
        """
        # 1. Check if public demo analysis
        from app.api.video_analysis import is_demo_analysis
        if is_demo_analysis(analysis_id):
            demo_dir = Path("docs/experiments/exp25_outputs").resolve()
            if (demo_dir / "tactical_events.json").is_file():
                return demo_dir
            # Fallback relative to project root
            root_demo = BASE_DIR.parent / "docs" / "experiments" / "exp25_outputs"
            if (root_demo / "tactical_events.json").is_file():
                return root_demo.resolve()
            return demo_dir

        # 2. Check local video results directory (e.g. running on GPU machine or local test)
        local_result_dir = BASE_DIR / "data" / "video_results" / analysis_id
        if (local_result_dir / "tactical_events.json").is_file():
            return local_result_dir

        # 3. Check L2 cache directory
        l2_dir = self.cache_dir / analysis_id / "v1"
        if (l2_dir / "tactical_events.json").is_file():
            return l2_dir

        # 4. Resolve via PublicationService & R2
        pub = self.pub_service.get_publication(analysis_id)
        if pub and pub.get("status") == "PUBLISHED":
            version_id = pub.get("version_id", "v1")
            target_dir = self.cache_dir / analysis_id / version_id
            target_dir.mkdir(parents=True, exist_ok=True)

            artifacts = pub.get("artifacts", {})
            required_files = [
                "tactical_events.json",
                "match_timeline.jsonl",
                "team_summary.json",
                "event_graph.json",
                "match_report.md",
            ]

            all_downloaded = True
            for fname in required_files:
                local_fpath = target_dir / fname
                if local_fpath.is_file():
                    continue

                art_info = artifacts.get(fname)
                if not art_info or not art_info.get("s3_key"):
                    all_downloaded = False
                    break

                try:
                    s3_key = art_info["s3_key"]
                    self.r2.download_file(s3_key, local_fpath)
                    # Verify sha256
                    with open(local_fpath, "rb") as f:
                        file_hash = hashlib.sha256(f.read()).hexdigest()
                    if file_hash != art_info["sha256"]:
                        logger.error("Hash mismatch for %s in %s", fname, analysis_id)
                        local_fpath.unlink(missing_ok=True)
                        all_downloaded = False
                        break
                except Exception as exc:
                    logger.error("Failed to download %s from R2 for %s: %s", fname, analysis_id, exc)
                    all_downloaded = False
                    break

            if all_downloaded and (target_dir / "tactical_events.json").is_file():
                return target_dir

        raise FileNotFoundError(
            f"Preuves tactiques introuvables pour l'analyse '{analysis_id}'. "
            f"L'analyse n'est ni une démo, ni disponible localement, ni publiée sur le cloud."
        )

    def get_or_load_store(self, analysis_id: str) -> MatchEvidenceStore:
        """Resolves evidence directory and returns cached or loaded MatchEvidenceStore."""
        ev_dir = self.resolve_evidence_dir(analysis_id)
        return MatchEvidenceRegistry.get_or_load(analysis_id, evidence_dir=ev_dir)


_global_evidence_resolver: Optional[EvidenceResolver] = None


def get_evidence_resolver() -> EvidenceResolver:
    global _global_evidence_resolver
    if _global_evidence_resolver is None:
        _global_evidence_resolver = EvidenceResolver()
    return _global_evidence_resolver
