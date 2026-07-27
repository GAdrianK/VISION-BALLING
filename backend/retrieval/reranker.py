import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any

# Ajout du dossier backend au sys.path pour permettre les imports absolus
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from database.parent_store import ParentStoreManager

logger = logging.getLogger(__name__)

class TacticalReranker:
    """
    Reranker tactique utilisant la bibliothèque légère FlashRank (cross-encoder)
    pour ré-estimer la pertinence absolue des chunks par rapport à la question.
    Intègre également la résolution des documents parents SQLite.
    """
    def __init__(self):
        self.parent_store = ParentStoreManager()
        self.has_flashrank = False
        
        # Initialisation de FlashRank
        try:
            from flashrank import Ranker
            # Utilisation d'un dossier cache local dans le workspace pour éviter les conflits de droits
            cache_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "flashrank_cache"))
            os.makedirs(cache_dir, exist_ok=True)
            
            logger.info("Chargement du modèle de reranking FlashRank...")
            self.ranker = Ranker(model_name="ms-marco-MiniLM-L-6-v2", cache_dir=cache_dir)
            self.has_flashrank = True
            logger.info("Modèle FlashRank chargé avec succès.")
        except Exception as e:
            logger.warning(f"Impossible d'importer ou de charger FlashRank ({e}). Fallback sur le tri par scores hybrides.")
            self.ranker = None

    def rerank_and_resolve(self, query: str, candidates: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Ré-estime la pertinence des candidats et récupère les documents parents depuis SQLite.
        """
        if not candidates:
            return []

        # 1. Sélection du top candidates pour le reranker (généralement 15-20 max)
        candidate_pool = candidates[:20]
        
        ranked_pool = []
        if self.has_flashrank and self.ranker:
            try:
                from flashrank import RerankRequest
                
                # Formatage attendu par FlashRank
                passages = []
                for cand in candidate_pool:
                    passages.append({
                        "id": cand["id"],
                        "text": cand["text"],
                        "meta": cand["metadata"]
                    })
                
                request = RerankRequest(query=query, passages=passages)
                results = self.ranker.rerank(request)
                
                # Créer une map des scores rerankés
                score_map = {res["id"]: res["score"] for res in results}
                
                # Mettre à jour les objets candidats originaux avec le score de reranking
                for cand in candidate_pool:
                    cand_id = cand["id"]
                    if cand_id in score_map:
                        cand_copy = cand.copy()
                        cand_copy["scores"] = cand["scores"].copy()
                        cand_copy["scores"]["rerank"] = float(score_map[cand_id])
                        ranked_pool.append(cand_copy)
                        
                # Trier par score rerank
                ranked_pool.sort(key=lambda x: x["scores"]["rerank"], reverse=True)
                
            except Exception as e:
                logger.error(f"Erreur lors du reranking via FlashRank: {e}. Fallback sur les scores hybrides.")
                ranked_pool = []

        # Si FlashRank a échoué ou n'est pas disponible, on conserve les scores de fusion hybride
        if not ranked_pool:
            for cand in candidate_pool:
                cand_copy = cand.copy()
                cand_copy["scores"] = cand["scores"].copy()
                cand_copy["scores"]["rerank"] = cand["scores"]["hybrid"]
                ranked_pool.append(cand_copy)
            ranked_pool.sort(key=lambda x: x["scores"]["rerank"], reverse=True)

        # Prendre le Top K final
        final_top = ranked_pool[:top_k]

        # 2. Résolution des documents parents depuis SQLite
        for rank, item in enumerate(final_top):
            parent_id = item["parent_id"]
            parent_text = ""
            parent_source = item["metadata"]["source"]
            
            if parent_id:
                parent_data = self.parent_store.get_parent(parent_id)
                if parent_data:
                    parent_source, parent_text = parent_data
                else:
                    logger.warning(f"Document parent {parent_id} introuvable dans SQLite.")
            
            item["parent_context"] = {
                "parent_id": parent_id,
                "source": parent_source,
                "content": parent_text
            }
            item["final_rank"] = rank + 1

        return final_top
