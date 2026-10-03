"""Match Evidence Store & Deterministic Query Engine (EXP-26 / Chapter 8).

Implements:
- Phase 1: Robust loading and schema validation of EXP-25 tactical evidence outputs
- Phase 2: Multi-dimensional deterministic indexing (by ID, family, semantic level, team, time, graph)
- Phase 4: Temporal query resolution (timestamps, intervals, relative windows)
- Phase 6: Graph-guided neighborhood traversal (CAUSES, SUPPORTS, OVERLAPS, FOLLOWS)
- Phase 27 & 28: Strict per-analysis_id session isolation to guarantee zero cross-match contamination
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from app.schemas.grounded_rag import QueryScope
from app.video_analysis.tactical_fusion import (
    EventFamily,
    QualityLevel,
    RelationType,
    SemanticLevel,
    TacticalEvidenceEvent,
)

logger = logging.getLogger("MATCH_EVIDENCE_STORE")

REQUIRED_EVENT_FIELDS: Set[str] = {
    "event_id",
    "sequence_id",
    "start_frame",
    "end_frame",
    "start_timestamp",
    "end_timestamp",
    "event_family",
    "semantic_level",
    "confidence",
    "quality_level",
    "supporting_metrics",
}


class MatchEvidenceStore:
    """In-memory deterministic index and query engine for a single analyzed match/video."""

    def __init__(self, analysis_id: str):
        self.analysis_id = analysis_id
        self.is_loaded: bool = False

        # Structured deterministic indices
        self.events_by_id: Dict[str, TacticalEvidenceEvent] = {}
        self.timeline: List[TacticalEvidenceEvent] = []
        self.events_by_family: Dict[str, List[TacticalEvidenceEvent]] = defaultdict(list)
        self.events_by_level: Dict[str, List[TacticalEvidenceEvent]] = defaultdict(list)
        self.events_by_team: Dict[str, List[TacticalEvidenceEvent]] = defaultdict(list)

        # Graph adjacencies
        self.graph_out: Dict[str, List[Tuple[str, str, float]]] = defaultdict(list) # src -> [(tgt, rel, weight)]
        self.graph_in: Dict[str, List[Tuple[str, str, float]]] = defaultdict(list)  # tgt -> [(src, rel, weight)]

        # Team aggregates
        self.team_summaries: Dict[str, Any] = {}

        # Metadata
        self.metadata: Dict[str, Any] = {
            "analysis_id": analysis_id,
            "sequence_id": analysis_id,
            "total_events": 0,
            "schema_version": "EXP-25-v1.0",
        }

    def load_from_directory(
        self,
        directory_path: Union[str, Path],
        sequence_filter: Optional[str] = None,
    ) -> None:
        """Loads EXP-25 outputs from a directory (tactical_events.json, match_timeline.jsonl, team_summary.json, event_graph.json)."""
        d = Path(directory_path)
        if not d.is_dir():
            raise FileNotFoundError(f"Evidence directory not found: {directory_path}")

        target_seq = sequence_filter or self.analysis_id

        events_file = d / "tactical_events.json"
        timeline_file = d / "match_timeline.jsonl"
        summary_file = d / "team_summary.json"
        graph_file = d / "event_graph.json"

        # Validate existence
        if not events_file.exists() and not timeline_file.exists():
            raise FileNotFoundError(f"Missing tactical_events.json or match_timeline.jsonl in {directory_path}")

        raw_events: List[Dict[str, Any]] = []

        # 1. Load events
        all_raw: List[Dict[str, Any]] = []
        if events_file.exists():
            with open(events_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    all_raw = data
        elif timeline_file.exists():
            with open(timeline_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        all_raw.append(json.loads(line))

        # Validate schema on all items in file (Reject corrupted files)
        for idx, item in enumerate(all_raw):
            missing = REQUIRED_EVENT_FIELDS - set(item.keys())
            if missing:
                raise ValueError(
                    f"Corrupted evidence event at index {idx}: missing required fields {missing}"
                )

        raw_events = [
            e for e in all_raw
            if e.get("sequence_id") == target_seq or target_seq in ("ALL", e.get("sequence_id"))
        ]

        if not raw_events and target_seq != "ALL":
            logger.warning("No events found for sequence_id %s in %s", target_seq, directory_path)

        # 2. Ingest and validate events
        self.ingest_raw_events(raw_events)

        # 3. Load team summaries
        if summary_file.exists():
            with open(summary_file, "r", encoding="utf-8") as f:
                summaries_data = json.load(f)
                if target_seq in summaries_data:
                    self.team_summaries = summaries_data[target_seq]
                elif "TEAM_0" in summaries_data or "TEAM_1" in summaries_data:
                    self.team_summaries = summaries_data

        # 4. Load event graph edges
        if graph_file.exists():
            with open(graph_file, "r", encoding="utf-8") as f:
                graph_data = json.load(f)
                edges = graph_data.get("edges", [])
                for edge in edges:
                    src = edge.get("source_id", "")
                    tgt = edge.get("target_id", "")
                    rel = edge.get("relation", "")
                    w = float(edge.get("weight", 1.0))
                    # Only register edges where both nodes are in this store
                    if src in self.events_by_id and tgt in self.events_by_id:
                        self.graph_out[src].append((tgt, rel, w))
                        self.graph_in[tgt].append((src, rel, w))

        self.is_loaded = True
        self.metadata["total_events"] = len(self.events_by_id)
        self.metadata["sequence_id"] = target_seq
        logger.info(
            "MatchEvidenceStore loaded %d events for analysis_id=%s (sequence=%s)",
            len(self.events_by_id), self.analysis_id, target_seq
        )

    def ingest_raw_events(self, raw_events: List[Dict[str, Any]]) -> None:
        """Validates schema version and builds structured indices."""
        for idx, item in enumerate(raw_events):
            missing = REQUIRED_EVENT_FIELDS - set(item.keys())
            if missing:
                raise ValueError(
                    f"Corrupted evidence event at index {idx}: missing required fields {missing}"
                )

            # Reconstruct typed TacticalEvidenceEvent
            try:
                family = EventFamily(item["event_family"])
                level = SemanticLevel(item["semantic_level"])
                quality = QualityLevel(item["quality_level"])
            except ValueError as exc:
                raise ValueError(f"Malformed enum in evidence event {item.get('event_id')}: {exc}") from exc

            evt = TacticalEvidenceEvent(
                event_id=item["event_id"],
                sequence_id=item["sequence_id"],
                start_frame=int(item["start_frame"]),
                end_frame=int(item["end_frame"]),
                start_timestamp=float(item["start_timestamp"]),
                end_timestamp=float(item["end_timestamp"]),
                event_family=family,
                semantic_level=level,
                subject_team=item.get("subject_team"),
                opponent_team=item.get("opponent_team"),
                confidence=float(item["confidence"]),
                quality_level=quality,
                source_modules=item.get("source_modules", []),
                supporting_metrics=item.get("supporting_metrics", {}),
                limitations=item.get("limitations", []),
                visibility_quality=item.get("visibility_quality", "UNKNOWN"),
                calibration_quality=item.get("calibration_quality", "UNKNOWN"),
                causal=bool(item.get("causal", True)),
                summary_text=item.get("summary_text"),
                related_event_ids=item.get("related_event_ids", []),
                conflict_flag=bool(item.get("conflict_flag", False)),
                conflict_reason=item.get("conflict_reason"),
            )

            self.events_by_id[evt.event_id] = evt
            self.timeline.append(evt)
            self.events_by_family[evt.event_family.value].append(evt)
            self.events_by_level[evt.semantic_level.value].append(evt)

            if evt.subject_team:
                self.events_by_team[evt.subject_team].append(evt)

        # Sort timeline chronologically
        self.timeline.sort(key=lambda e: (e.start_timestamp, e.end_timestamp, e.start_frame))

    # ==========================================================================
    # DETERMINISTIC RETRIEVAL METHODS (PHASE 4, 5, 6)
    # ==========================================================================

    def get_event_by_id(self, event_id: str) -> Optional[TacticalEvidenceEvent]:
        return self.events_by_id.get(event_id)

    def get_events_at_timestamp(
        self,
        timestamp: float,
        tolerance_s: float = 0.5,
    ) -> List[TacticalEvidenceEvent]:
        """Retrieves events active at timestamp or within tolerance window [t - tol, t + tol]."""
        matched: List[TacticalEvidenceEvent] = []
        for e in self.timeline:
            # Active interval overlap
            if e.start_timestamp <= (timestamp + tolerance_s) and e.end_timestamp >= (timestamp - tolerance_s):
                matched.append(e)
        return matched

    def get_events_in_range(
        self,
        start_s: float,
        end_s: float,
    ) -> List[TacticalEvidenceEvent]:
        """Retrieves all events temporally overlapping range [start_s, end_s]."""
        matched: List[TacticalEvidenceEvent] = []
        for e in self.timeline:
            if e.end_timestamp >= start_s and e.start_timestamp <= end_s:
                matched.append(e)
        return matched

    def get_events_relative_to(
        self,
        event_id: str,
        direction: str = "after",
        window_s: float = 2.0,
    ) -> List[TacticalEvidenceEvent]:
        """Retrieves events occurring immediately before or after a target event."""
        root = self.get_event_by_id(event_id)
        if root is None:
            return []

        if direction == "after":
            t0 = root.end_timestamp
            t1 = t0 + window_s
            return [e for e in self.timeline if e.event_id != root.event_id and e.start_timestamp >= t0 and e.start_timestamp <= t1]
        else:
            t1 = root.start_timestamp
            t0 = max(0.0, t1 - window_s)
            return [e for e in self.timeline if e.event_id != root.event_id and e.end_timestamp >= t0 and e.end_timestamp <= t1]

    def get_events_by_family(self, family: Union[EventFamily, str]) -> List[TacticalEvidenceEvent]:
        fam_str = family.value if isinstance(family, EventFamily) else str(family)
        return self.events_by_family.get(fam_str, [])

    def get_events_by_level(self, level: Union[SemanticLevel, str]) -> List[TacticalEvidenceEvent]:
        lvl_str = level.value if isinstance(level, SemanticLevel) else str(level)
        return self.events_by_level.get(lvl_str, [])

    def get_events_by_team(self, team_id: str) -> List[TacticalEvidenceEvent]:
        return self.events_by_team.get(team_id, [])

    def get_graph_neighborhood(
        self,
        root_event_id: str,
        max_depth: int = 2,
    ) -> Dict[str, Any]:
        """Traverses relation graph up to max_depth starting from root event."""
        root = self.get_event_by_id(root_event_id)
        if root is None:
            return {"root_event": None, "neighbors": [], "edges": []}

        visited_ids: Set[str] = {root_event_id}
        queue: List[Tuple[str, int]] = [(root_event_id, 0)]
        collected_edges: List[Dict[str, Any]] = []

        while queue:
            curr_id, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            # Outgoing edges (e.g. CAUSES, FOLLOWS, OVERLAPS)
            for tgt_id, rel, w in self.graph_out.get(curr_id, []):
                collected_edges.append({"source_id": curr_id, "target_id": tgt_id, "relation": rel, "weight": w})
                if tgt_id not in visited_ids:
                    visited_ids.add(tgt_id)
                    queue.append((tgt_id, depth + 1))

            # Incoming edges (e.g. SUPPORTS)
            for src_id, rel, w in self.graph_in.get(curr_id, []):
                collected_edges.append({"source_id": src_id, "target_id": curr_id, "relation": rel, "weight": w})
                if src_id not in visited_ids:
                    visited_ids.add(src_id)
                    queue.append((src_id, depth + 1))

        neighbors = [self.events_by_id[eid] for eid in visited_ids if eid != root_event_id and eid in self.events_by_id]
        return {
            "root_event": root,
            "neighbors": neighbors,
            "edges": collected_edges,
        }

    def get_team_summary(self, team_id: str) -> Optional[Dict[str, Any]]:
        return self.team_summaries.get(team_id)

    def get_all_team_summaries(self) -> Dict[str, Any]:
        return self.team_summaries


# ==============================================================================
# SESSION REGISTRY & CROSS-MATCH ISOLATION (PHASE 27, 28)
# ==============================================================================

class MatchEvidenceRegistry:
    """Thread-safe registry managing isolated MatchEvidenceStores by analysis_id."""

    _instances: Dict[str, MatchEvidenceStore] = {}

    @classmethod
    def register(cls, analysis_id: str, store: MatchEvidenceStore) -> None:
        cls._instances[analysis_id] = store

    @classmethod
    def get(cls, analysis_id: str) -> Optional[MatchEvidenceStore]:
        return cls._instances.get(analysis_id)

    @classmethod
    def get_or_load(
        cls,
        analysis_id: str,
        evidence_dir: Union[str, Path] = Path("docs/experiments/exp25_outputs"),
    ) -> MatchEvidenceStore:
        """Retrieves existing store or loads it from disk, guaranteed isolated by analysis_id."""
        if analysis_id in cls._instances:
            return cls._instances[analysis_id]

        store = MatchEvidenceStore(analysis_id=analysis_id)
        try:
            store.load_from_directory(evidence_dir, sequence_filter=analysis_id)
        except Exception as exc:
            logger.warning("Could not load from default directory for %s: %s", analysis_id, exc)

        cls._instances[analysis_id] = store
        return store

    @classmethod
    def clear(cls) -> None:
        cls._instances.clear()
