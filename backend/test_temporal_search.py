import os
import sys
from pathlib import Path

# Ajout du dossier backend au sys.path pour les imports
backend_dir = Path(__file__).resolve().parent
sys.path.append(str(backend_dir))

from retrieval.query_rewriter import QueryRewriter
from retrieval.hybrid_engine import HybridSearchEngine
from retrieval.reranker import TacticalReranker
from database.indexer import run_indexing
from database.vector_store import VectorStoreManager
from app.core.config import settings

def run_temporal_search_test():
    print("==================================================")
    print("      FOOTBALL IQ - TEST DE RECHERCHE TEMPORELLE   ")
    print("==================================================")

    # 1. S'assurer que les données sont indexées
    print("\n[Etape 1] Initialisation & Vérification de l'indexation...")
    v_store = VectorStoreManager()
    should_index = False
    
    # Si stockage persistant vide, on indexe
    try:
        info = v_store.client.get_collection(v_store.collection_name)
        if info.points_count == 0:
            should_index = True
    except Exception:
        should_index = True
    finally:
        try:
            v_store.client.close()
        except Exception:
            pass
        
    if should_index:
        print("-> Collection Qdrant vide ou non trouvée. Indexation en cours...")
        run_indexing()
    else:
        print(f"-> Base Qdrant OK ({info.points_count} points trouvés).")

    # 2. Initialiser les composants de recherche
    rewriter = QueryRewriter()
    hybrid_engine = HybridSearchEngine()
    reranker = TacticalReranker()

    # 3. Scénarios de test
    test_cases = [
        {
            "query": "Quels ont été les ajustements tactiques de Vitinha en PREMIÈRE mi-temps ?",
            "expected_periode": "1MT",
            "expected_minute_hint": "12",
            "description": "Test de détection Première Mi-temps (Vitinha à la 12')"
        },
        {
            "query": "Comment l'OM a bousculé Paris en FIN de match ?",
            "expected_periode": "2MT",
            "expected_minute_hint": "72",
            "description": "Test de détection Fin de match (OM à la 72')"
        }
    ]

    for idx, case in enumerate(test_cases):
        print(f"\n--------------------------------------------------")
        print(f"CAS DE TEST {idx + 1} : {case['description']}")
        print(f"Question : '{case['query']}'")
        print(f"--------------------------------------------------")

        # Extraction temporelle
        rewrite_res = rewriter.rewrite(case["query"])
        print(f"[REWRITER] Période cible extraite  : {rewrite_res['periode_cible']}")
        print(f"[REWRITER] Intervalle cible extrait : {rewrite_res['intervalle_cible']}")
        print(f"[REWRITER] Variations de requêtes   : {rewrite_res['variations']}")
        
        # Validation des filtres du rewriter
        assert rewrite_res["periode_cible"] == case["expected_periode"], \
            f"Erreur de détection de la période: attendu {case['expected_periode']}, obtenu {rewrite_res['periode_cible']}"

        # Recherche Hybride
        print("\n[Hybrid Engine] Recherche avec filtres temporels...")
        raw_results = hybrid_engine.search(case["query"], top_k=20)
        print(f"-> {len(raw_results)} chunks correspondants trouvés.")

        # Reranker & Résolution Parent-Child
        print("\n[Reranker] Reranking et résolution parents...")
        reranked_results = reranker.rerank_and_resolve(case["query"], raw_results, top_k=10)

        # Affichage et assertions sur les résultats
        found_minute_event = False
        for rank, res in enumerate(reranked_results):
            meta = res["metadata"]
            text = res["text"]
            parent = res["parent_context"]
            print(f"  [Rerank Rank {rank + 1}] Score: {res['scores']['rerank']:.4f}")
            print(f"  Période du chunk : {meta.get('periode')}")
            print(f"  Intervalle temps : {meta.get('intervalle_temps')}")
            print(f"  Source           : {meta.get('source')}")
            print(f"  Extrait          : {text[:200].strip()}...")
            print(f"  Parent Source    : {parent.get('source')}\n")

            # Assertions sur la conformité du filtre appliqué
            assert meta.get("periode") == case["expected_periode"], \
                f"Filtre temporel violé! Obtenu un chunk de période '{meta.get('periode')}' au lieu de '{case['expected_periode']}'"

            # Vérification de l'indice de la minute dans le texte
            if case["expected_minute_hint"] in text:
                found_minute_event = True

        assert found_minute_event, \
            f"L'événement clé attendu ({case['expected_minute_hint']}ème minute) n'a pas été trouvé dans le top des résultats!"
        
        print(f"====== [SUCCÈS] Cas de test {idx + 1} validé avec succès ! ======")

    print("\n==================================================")
    print("      TOUS LES TESTS TEMPORELS ONT RÉUSSI !       ")
    print("==================================================")

if __name__ == "__main__":
    run_temporal_search_test()
