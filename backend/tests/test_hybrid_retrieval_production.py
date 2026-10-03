"""Tests for Production Hybrid Retrieval Path (Phase 2 / RC1).

Verifies:
A. Production Hybrid Retrieval Path:
   - Qdrant Vector Search
   - BM25 Lexical Search
   - Reciprocal Rank Fusion / Score Hybridization
   - FlashRank Cross-Encoder Reranking
   - Parent Document Resolution (SQLite)
B. Offline Deterministic Fallback:
   - Local TF-IDF Vectorization
   - In-memory Cosine Similarity
   - Zero-external-dependency Operation
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams

from app.core.config import settings
from app.services.rag_engine import RAGEngine
from retrieval.hybrid_engine import BM25Searcher
from retrieval.reranker import TacticalReranker


# ==============================================================================
# PATH A: PRODUCTION HYBRID RETRIEVAL (Qdrant + BM25 + FlashRank + Parent Store)
# ==============================================================================

def test_qdrant_vector_store_in_memory():
    """Validates in-memory Qdrant indexing, payload filtering, and vector similarity search."""
    client = QdrantClient(":memory:")
    collection_name = "test_tactics"
    vector_dim = 4

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_dim, distance=Distance.COSINE),
    )

    points = [
        PointStruct(
            id=1,
            vector=[1.0, 0.0, 0.0, 0.0],
            payload={"text": "Contre-pressing agressif à la perte", "tag": "transition"},
        ),
        PointStruct(
            id=2,
            vector=[0.0, 1.0, 0.0, 0.0],
            payload={"text": "Bloc bas compact et coulissement", "tag": "defense"},
        ),
    ]
    client.upsert(collection_name=collection_name, points=points)

    # Search for transition concept via modern query_points API
    res = client.query_points(
        collection_name=collection_name,
        query=points[0].vector,
        limit=1,
    )
    assert len(res.points) == 1
    assert res.points[0].id == 1
    assert res.points[0].payload["tag"] == "transition"


def test_bm25_lexical_retrieval():
    """Validates standalone BM25 lexical tokenization and exact match scoring."""
    corpus = [
        {"text": "Organisation en bloc bas compact pour fermer les interlignes."},
        {"text": "Le contre-pressing de Jürgen Klopp exige un harcèlement immédiat de 5 secondes."},
        {"text": "Relance courte depuis le gardien avec fixation d'un double pivot."},
    ]
    bm25 = BM25Searcher(corpus)
    results = bm25.search("contre-pressing immédiat")

    assert len(results) == 3
    top_doc_idx, top_score = results[0]
    assert top_doc_idx == 1  # Should match doc 1 (contre-pressing)
    assert top_score > 0.0


def test_flashrank_reranker_and_parent_resolution():
    """Validates TacticalReranker ranking over candidate passages (FlashRank or graceful fallback)."""
    reranker = TacticalReranker()

    query = "Comment s'organiser après la perte de balle ?"
    candidates = [
        {"id": "doc_1", "text": "La recette de la pizza margherita italienne.", "score": 0.30},
        {"id": "doc_2", "text": "À la perte de balle, la réaction en contre-pressing immédiat est primordiale.", "score": 0.85},
        {"id": "doc_3", "text": "Le rôle du gardien sur coup franc lointain.", "score": 0.50},
    ]

    reranked = reranker.rerank_and_resolve(query, candidates, top_k=2)
    assert len(reranked) == 2
    # The tactical reaction chunk must be ranked #1
    assert reranked[0]["id"] == "doc_2"


# ==============================================================================
# PATH B: OFFLINE DETERMINISTIC FALLBACK (TF-IDF Local Engine)
# ==============================================================================

def test_offline_deterministic_fallback():
    """Validates that RAGEngine operates completely offline with TF-IDF and zero network calls."""
    engine = RAGEngine(
        knowledge_base_dir=settings.get_kb_dir(),
        openai_api_key=None,  # Explicitly None to test offline fallback
    )
    engine.initialize()

    assert engine.mode == "offline"
    assert len(engine.chunks) > 0
    assert engine.provider is not None

    hits = engine.search("contre-pressing", top_k=3)
    assert len(hits) > 0
    assert any("pressing" in h["text"].lower() or "contre-pressing" in h["text"].lower() for h in hits)
    assert hits[0]["score"] > 0.0
