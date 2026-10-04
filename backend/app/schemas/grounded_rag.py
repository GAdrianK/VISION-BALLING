"""Grounded Tactical RAG Schemas (EXP-26 / Chapter 8).

Defines Pydantic models for:
- Query classification scopes
- Grounded match claims and evidence citations
- Grounded match answers with strict epistemic separation
- Match context packs passed to synthesis
- Match report requests and structured reports
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class QueryScope(str, Enum):
    """Scope of tactical query defining the authoritative source."""
    GENERAL_FOOTBALL = "GENERAL_FOOTBALL"        # General tactical theory -> Knowledge Base only
    MATCH_FACT = "MATCH_FACT"                    # Exact factual event in analyzed video -> Match Evidence Store
    MATCH_TIMELINE = "MATCH_TIMELINE"            # Chronology / interval query -> Match Timeline
    MATCH_EXPLANATION = "MATCH_EXPLANATION"      # Why/how a match event happened -> Match Evidence + Graph + KB concept
    MATCH_COMPARISON = "MATCH_COMPARISON"        # Team comparison across aggregates -> Team Tactical Summary
    UNSUPPORTED = "UNSUPPORTED"                  # Unsupported metrics (xG, score, MOTM, coach plan) -> Abstain


class MatchClaim(BaseModel):
    """Individual atomic claim within a generated response."""
    text: str
    event_ids: List[str] = Field(default_factory=list)
    semantic_level: str                          # LEVEL_1_PHYSICAL_FACT, LEVEL_2_STRUCTURAL_INFERENCE, LEVEL_3_TACTICAL_CANDIDATE
    confidence: float
    is_verified: bool = True


class GroundedMatchAnswer(BaseModel):
    """Complete grounded answer with epistemic separation and citations."""
    answer: str
    query: str
    query_scope: QueryScope
    analysis_id: str
    confidence: float = 0.0
    semantic_level: str = "LEVEL_1_PHYSICAL_FACT"
    match_claims: List[MatchClaim] = Field(default_factory=list)
    evidence_citations: List[str] = Field(default_factory=list)
    knowledge_citations: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    observations_du_match: List[str] = Field(default_factory=list)
    interpretations_tactiques: List[str] = Field(default_factory=list)
    connaissances_generales: List[str] = Field(default_factory=list)
    limites: List[str] = Field(default_factory=list)
    coverage_note: str = ""
    is_abstention: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)


class MatchContextPack(BaseModel):
    """Epistemically structured context provided for response synthesis."""
    query: str
    query_scope: QueryScope
    analysis_id: str
    verified_facts: List[Dict[str, Any]] = Field(default_factory=list)          # LEVEL 1
    structural_inferences: List[Dict[str, Any]] = Field(default_factory=list)   # LEVEL 2
    tactical_candidates: List[Dict[str, Any]] = Field(default_factory=list)     # LEVEL 3
    event_relations: List[Dict[str, Any]] = Field(default_factory=list)         # Graph edges
    team_aggregates: Dict[str, Any] = Field(default_factory=dict)               # Team summaries with reliability bands
    limitations: List[str] = Field(default_factory=list)
    knowledge_sources: List[Dict[str, Any]] = Field(default_factory=list)       # General KB chunks
    has_conflict: bool = False
    conflict_notes: List[str] = Field(default_factory=list)


class VideoAnalysisQueryRequest(BaseModel):
    """API request payload for grounded tactical query on an analyzed video."""
    query: str
    mode: str = "analyst"                        # coach, analyst, fan
    max_evidence_events: int = 8
    include_knowledge_base: bool = True


class MatchReportResponse(BaseModel):
    """API response containing full grounded match report."""
    analysis_id: str
    sequence_id: str
    markdown_report: str
    total_events: int
    grounded_sentence_count: int
    unsupported_sentence_count: int
    grounded_ratio: float
    team_reliability: Dict[str, Any]
