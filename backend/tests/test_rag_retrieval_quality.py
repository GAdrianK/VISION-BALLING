import pytest
from app.services.rag_engine import RAGEngine
from app.services.query_classifier import QueryClassifier
from app.core.config import settings

def test_rag_retrieval_quality_defend_vs_attack():
    engine = RAGEngine(
        knowledge_base_dir=settings.get_kb_dir(),
        openai_api_key="mock-testing-key"
    )
    engine.initialize()
    classifier = QueryClassifier()

    # 1. Tester "comment défendre un bloc bas ?"
    query_defend = "comment défendre un bloc bas ?"
    classif_defend = classifier.classify(query_defend)
    assert classif_defend["intent"] == "defend"
    
    results_defend = engine.search(query_defend, top_k=5, query_metadata=classif_defend)
    assert len(results_defend) > 0
    
    # Les premiers résultats doivent provenir de bloc_bas.md, transition_defensive_repli.md ou analyse_video_coulissement_bloc.md
    top_sources_defend = [res["source"] for res in results_defend[:2]]
    assert any(src in ["bloc_bas.md", "transition_defensive_repli.md", "analyse_video_coulissement_bloc.md", "analyse_video_cpa_defensifs.md"] for src in top_sources_defend)
    
    # Et le premier résultat ne doit pas être un document d'attaque pur
    assert results_defend[0]["source"] != "principe_desequilibrer_bloc_bas.md"

    # 2. Tester "comment attaquer un bloc bas ?"
    query_attack = "comment attaquer un bloc bas ?"
    classif_attack = classifier.classify(query_attack)
    assert classif_attack["intent"] == "attack"
    
    results_attack = engine.search(query_attack, top_k=5, query_metadata=classif_attack)
    assert len(results_attack) > 0
    
    top_sources_attack = [res["source"] for res in results_attack[:2]]
    assert any(src in ["principe_desequilibrer_bloc_bas.md", "phase_offensive_jeu_couloirs.md", "phase_offensive_centres_surface.md", "phase_offensive_fixation_axiale.md"] for src in top_sources_attack)
    
    # Et le premier résultat ne doit pas être un document de défense pur
    assert results_attack[0]["source"] not in ["bloc_bas.md", "transition_defensive_repli.md"]

def test_rag_retrieval_specific_topics():
    engine = RAGEngine(
        knowledge_base_dir=settings.get_kb_dir(),
        openai_api_key="mock-testing-key"
    )
    engine.initialize()
    classifier = QueryClassifier()

    # "comment sortir du pressing haut ?" -> sortie_balle.md ou relance
    q1 = "comment sortir du pressing haut ?"
    res1 = engine.search(q1, top_k=3, query_metadata=classifier.classify(q1))
    assert any(src in ["sortie_balle.md", "formation_433.md", "formation_343.md", "roles_modernes.md", "analyse_video_pressing_haut.md", "pressing_haut.md"] for src in [r["source"] for r in res1])

    # "explique-moi un faux 9" -> roles_modernes.md ou rôles/formations
    q2 = "explique-moi un faux 9"
    res2 = engine.search(q2, top_k=3, query_metadata=classifier.classify(q2))
    assert any(src in ["roles_modernes.md", "formation_433.md", "formation_343.md", "player_roles_offensive_faux_9.md"] for src in [r["source"] for r in res2])


def test_problem_oriented_retrieval():
    engine = RAGEngine(
        knowledge_base_dir=settings.get_kb_dir(),
        openai_api_key="mock-testing-key"
    )
    engine.initialize()
    classifier = QueryClassifier()

    # Case 1: "Je joue en 4-3-3 mais mon équipe perd trop de ballons à la relance. Que faire ?"
    q1 = "Je joue en 4-3-3 mais mon équipe perd trop de ballons à la relance. Que faire ?"
    res1 = engine.search(q1, top_k=5, query_metadata=classifier.classify(q1))
    sources1 = [r["source"] for r in res1]
    idx_sortie = sources1.index("sortie_balle.md") if "sortie_balle.md" in sources1 else 999
    idx_433 = sources1.index("formation_433.md") if "formation_433.md" in sources1 else 999
    assert idx_sortie < idx_433, f"sortie_balle.md ({idx_sortie}) should be preferred over formation_433.md ({idx_433})"

    # Case 2: "Je joue en 3-5-2 mais je n’arrive pas à presser haut"
    q2 = "Je joue en 3-5-2 mais je n’arrive pas à presser haut"
    res2 = engine.search(q2, top_k=5, query_metadata=classifier.classify(q2))
    sources2 = [r["source"] for r in res2]
    idx_pressing = sources2.index("pressing_haut.md") if "pressing_haut.md" in sources2 else 999
    idx_352 = sources2.index("formation_352.md") if "formation_352.md" in sources2 else 999
    assert idx_pressing < idx_352, f"pressing_haut.md ({idx_pressing}) should be preferred over formation_352.md ({idx_352})"

    # Case 3: "Je joue en 4-4-2 mais je prends trop de buts entre les lignes"
    q3 = "Je joue en 4-4-2 mais je prends trop de buts entre les lignes"
    res3 = engine.search(q3, top_k=5, query_metadata=classifier.classify(q3))
    sources3 = [r["source"] for r in res3]
    idx_442 = sources3.index("formation_442.md") if "formation_442.md" in sources3 else 999
    idx_solutions = [sources3.index(src) for src in ["bloc_bas.md", "tactics_defensive_compacite_bloc.md"] if src in sources3]
    assert len(idx_solutions) > 0, f"No defensive solution document returned in top 5: {sources3}"
    assert min(idx_solutions) < idx_442, f"Defensive solutions should be preferred over formation_442.md ({idx_442})"

    # Case 4: "Comment jouer en 4-3-3 ?"
    q4 = "Comment jouer en 4-3-3 ?"
    res4 = engine.search(q4, top_k=3, query_metadata=classifier.classify(q4))
    assert res4[0]["source"] == "formation_433.md", f"formation_433.md should be rank 1, got {res4[0]['source']}"


