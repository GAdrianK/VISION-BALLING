import pytest
from app.services.document_loader import DocumentLoader, MarkdownChunker
from app.services.embedding_provider import TFIDFEmbeddingProvider, get_cosine_similarity
from app.services.rag_engine import RAGEngine
from app.core.config import settings

def test_markdown_chunker():
    chunker = MarkdownChunker(target_chunk_words=50, min_chunk_words=10)
    sample_md = """# Titre Principal
## Section A
Ici un premier paragraphe court.
## Section B
Ici un second paragraphe de test un peu plus long pour valider le découpage.
### Subsection B1
Et un sous-bloc d'entraînement.
"""
    chunks = chunker.chunk_document(sample_md, "test.md")
    assert len(chunks) > 0
    # Vérifier que le format de chunk respecte la structure attendue
    first_chunk = chunks[0]
    assert "text" in first_chunk
    assert "source" in first_chunk
    assert "metadata" in first_chunk
    assert first_chunk["source"] == "test.md"
    assert first_chunk["metadata"]["document_title"] == "Titre Principal"

def test_tfidf_embedding_provider():
    provider = TFIDFEmbeddingProvider()
    docs = [
        "Le pivot est un point d'appui physique dos au but.",
        "Le double pivot assure l'équilibre défensif et la relance basse.",
        "Le pressing haut vise à harceler le gardien de but adverse."
    ]
    provider.fit(docs)
    
    # Vérifier que le vocabulaire et l'IDF sont calculés
    assert len(provider.vocabulary) > 0
    assert provider.is_fitted
    
    emb_pivot = provider.get_embedding("Le pivot")
    emb_pressing = provider.get_embedding("Le pressing haut")
    
    # Calculer similarité cosinus avec lui-même
    sim_self = get_cosine_similarity(emb_pivot, emb_pivot)
    assert pytest.approx(sim_self, 0.0001) == 1.0
    
    # Calculer similarité cosinus avec un autre
    sim_diff = get_cosine_similarity(emb_pivot, emb_pressing)
    assert sim_diff < 0.8  # Devrait être très faible car les vocabulaires diffèrent

def test_rag_engine_integration():
    # Instancier RAGEngine avec le répertoire de la base de connaissances
    engine = RAGEngine(
        knowledge_base_dir=settings.get_kb_dir(),
        openai_api_key="mock-testing-key"
    )
    engine.initialize()
    
    # Vérifier que le mode est bien TF-IDF (offline) en raison de la clé mock
    assert engine.mode == "offline"
    assert len(engine.chunks) > 0
    
    # Rechercher un concept de relance basse / pressing haut
    results = engine.search("comment sortir du pressing haut ?", top_k=3)
    assert len(results) > 0
    
    # Le premier résultat doit provenir de sortie_balle.md ou pressing_contre_pressing.md
    top_result = results[0]
    assert "text" in top_result
    assert "source" in top_result
    assert "score" in top_result
    assert "metadata" in top_result
    assert top_result["source"].endswith(".md")
