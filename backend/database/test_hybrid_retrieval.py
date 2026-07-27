import sys
from pathlib import Path

# Ajout du dossier backend au sys.path pour permettre les imports absolus
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from retrieval.query_rewriter import QueryRewriter
from retrieval.hybrid_engine import HybridSearchEngine
from retrieval.reranker import TacticalReranker
from database.indexer import run_indexing
from database.vector_store import VectorStoreManager
from app.core.config import settings

def run_advanced_retrieval_test(question: str):
    print("==================================================")
    print("      FOOTBALL IQ - MOTEUR DE RECHERCHE AVANCÉ     ")
    print("==================================================")
    print(f"Question Utilisateur : '{question}'\n")

    # 1. Indexation automatique si base vide
    v_store = VectorStoreManager()
    should_index = False
    if settings.QDRANT_URL == ":memory:":
        should_index = True
    else:
        try:
            info = v_store.client.get_collection(v_store.collection_name)
            if info.points_count == 0:
                should_index = True
        except Exception:
            should_index = True
            
    if should_index:
        print("Collection Qdrant vide ou en mémoire. Indexation des données brutes...")
        run_indexing()
        print("\nIndexation terminée.\n")

    # 2. Initialisation des composants
    rewriter = QueryRewriter()
    hybrid_engine = HybridSearchEngine()
    reranker = TacticalReranker()

    # 3. Query Rewriting (Multi-Query)
    print("1. [LLM Query Rewriter] Réécriture de la requête...")
    rewrite_res = rewriter.rewrite(question)
    rewritten_queries = rewrite_res["variations"]
    print(f"   Requêtes générées ({len(rewritten_queries)}) :")
    for idx, req in enumerate(rewritten_queries):
        print(f"   [{idx + 1}] {req}")
    print()

    # 4. Recherche Hybride Multi-requête
    print("2. [Hybrid Engine] Recherche hybride vectorielle et lexicale (BM25)...")
    merged_candidates = {}
    
    for sub_query in rewritten_queries:
        print(f"   -> Recherche pour : '{sub_query}'")
        candidates = hybrid_engine.search(sub_query, top_k=10)
        
        for cand in candidates:
            cand_id = cand["id"]
            if cand_id not in merged_candidates:
                merged_candidates[cand_id] = cand
            else:
                # Garder le meilleur score hybride parmi toutes les sous-requêtes
                if cand["scores"]["hybrid"] > merged_candidates[cand_id]["scores"]["hybrid"]:
                    merged_candidates[cand_id] = cand
                    
    candidate_list = list(merged_candidates.values())
    print(f"   -> {len(candidate_list)} chunks enfants uniques récoltés au total.")
    print()

    # 5. Reranking (FlashRank) & Résolution Parent-Child (SQLite)
    print("3. [Tactical Reranker] Reranking et extraction des documents parents...")
    final_results = reranker.rerank_and_resolve(question, candidate_list, top_k=3)
    
    print("\n==================================================")
    print("              RÉSULTATS DE RECHERCHE TOP 3        ")
    print("==================================================")
    
    for idx, item in enumerate(final_results):
        scores = item["scores"]
        meta = item["metadata"]
        parent = item["parent_context"]
        
        print(f"\n[RANG {item['final_rank']}] Score Rerank: {scores['rerank']:.4f} (Score Hybride: {scores['hybrid']:.4f})")
        print(f"Fichier Source Enfant : {meta['source']}")
        print(f"Tags tactiques        : {meta['tags_tactiques']}")
        print(f"Type de chunk         : {meta['type_chunk']}")
        print(f"Extrait du Texte Enfant :\n{item['text'][:250]}...")
        
        print(f"\n---> [SQLite Parent Document] : {parent['source']}")
        print(f"     Longueur du Parent : {len(parent['content'])} caractères")
        print(f"     Extrait du Parent (150 premiers caractères) :\n{parent['content'][:150].strip()}...")
        print("-" * 50)
        
    print("\n==================================================")
    print("              FIN DU PIPELINE RETRIEVAL           ")
    print("==================================================")

if __name__ == "__main__":
    test_question = "Comment Paris gère le contre-pressing de l'OM ?"
    if len(sys.argv) > 1:
        test_question = " ".join(sys.argv[1:])
    run_advanced_retrieval_test(test_question)
