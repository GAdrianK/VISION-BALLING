import os
import sys
import json
import re
import math
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

# Ajout du dossier backend au sys.path pour permettre les imports absolus
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from app.core.config import settings
from database.vector_store import VectorStoreManager
from app.services.embedding_provider import OpenAIEmbeddingProvider, GeminiEmbeddingProvider
from database.indexer import generate_deterministic_vector

from retrieval.query_rewriter import QueryRewriter
from database.indexer import generate_deterministic_vector

logger = logging.getLogger(__name__)

# =====================================================================
# IMPLÉMENTATION PURE PYTHON DE BM25 POUR ÉVITER LES ERREURS DE DÉPENDANCE
# =====================================================================
class BM25Searcher:
    """
    Implémentation standard de l'algorithme BM25 pour la recherche lexicale.
    """
    def __init__(self, corpus: List[Dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.corpus_size = len(corpus)
        
        # Pré-découpage en tokens
        self.tokenized_corpus = [self._tokenize(doc["text"]) for doc in corpus]
        
        # Calcul de la longueur moyenne des documents
        total_len = sum(len(doc) for doc in self.tokenized_corpus)
        self.avgdl = total_len / self.corpus_size if self.corpus_size > 0 else 0
        
        self.doc_freqs = []
        self.idf = {}
        self._initialize()

    def _tokenize(self, text: str) -> List[str]:
        # Nettoyage et tokenisation basiques (lettres, chiffres, tirets pour les schémas tactiques)
        text_clean = re.sub(r'[^\w\s-]', ' ', text.lower())
        return [word for word in text_clean.split() if len(word) > 1]

    def _initialize(self):
        df = {}
        for doc in self.tokenized_corpus:
            frequencies = {}
            for word in doc:
                frequencies[word] = frequencies.get(word, 0) + 1
            self.doc_freqs.append(frequencies)
            for word in frequencies:
                df[word] = df.get(word, 0) + 1

        for word, count in df.items():
            # Formule d'IDF classique lissée
            self.idf[word] = math.log((self.corpus_size - count + 0.5) / (count + 0.5) + 1.0)

    def search(self, query: str, indices_filter: List[int] = None) -> List[Tuple[int, float]]:
        """
        Calcule les scores BM25 pour tous les documents ou une sous-sélection (filtre).
        """
        query_tokens = self._tokenize(query)
        scores = []
        
        # Si aucun filtre d'indice, on parcourt tout
        target_indices = indices_filter if indices_filter is not None else range(self.corpus_size)
        
        for idx in target_indices:
            doc_freq = self.doc_freqs[idx]
            doc_len = len(self.tokenized_corpus[idx])
            score = 0.0
            
            for token in query_tokens:
                if token not in self.idf:
                    continue
                
                f = doc_freq.get(token, 0)
                if f > 0:
                    idf_val = self.idf[token]
                    numerator = f * (self.k1 + 1)
                    denominator = f + self.k1 * (1 - self.b + self.b * (doc_len / self.avgdl))
                    score += idf_val * (numerator / denominator)
            
            scores.append((idx, score))
            
        # Trier par score descendant
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores


# =====================================================================
# FONCTION DE FILTRAGE DES MÉTADONNÉES
# =====================================================================
def matches_metadata(metadata: Dict[str, Any], filter_dict: Dict[str, Any]) -> bool:
    """
    Vérifie si les métadonnées d'un chunk matchent le filtre spécifié.
    """
    if not filter_dict:
        return True
        
    for key, val in filter_dict.items():
        # Retirer le préfixe 'metadata.' éventuel
        clean_key = key.replace("metadata.", "")
        
        if clean_key not in metadata:
            return False
            
        chunk_val = metadata[clean_key]
        
        # Gestion des listes (ex: tag_tactique ou equipes)
        if isinstance(val, list):
            if isinstance(chunk_val, list):
                if not any(v in chunk_val for v in val):
                    return False
            else:
                if chunk_val not in val:
                    return False
        else:
            if isinstance(chunk_val, list):
                if val not in chunk_val:
                    return False
            else:
                if chunk_val != val:
                    return False
    return True


# =====================================================================
# MOTEUR DE RECHERCHE HYBRIDE PRINCIPAL
# =====================================================================
class HybridSearchEngine:
    """
    Moteur de recherche hybride combinant sémantique (Qdrant) et lexical (BM25).
    """
    def __init__(self):
        self.vector_store = VectorStoreManager()
        self.processed_dir = Path(settings.get_processed_data_dir())
        self.chunks_file = self.processed_dir / "chunks.jsonl"
        
        # Charger tous les chunks enfants pour BM25
        self.chunks: List[Dict[str, Any]] = []
        self._load_corpus()
        
        # Initialiser le searcher BM25
        if self.chunks:
            self.bm25 = BM25Searcher(self.chunks)
        else:
            self.bm25 = None
            logger.warning("Corpus vide ! BM25 ne sera pas opérationnel.")
            
        # Initialiser le bon provider d'embeddings
        gemini_key = settings.gemini_key
        self.use_gemini = gemini_key and not gemini_key.startswith("mock-") and len(gemini_key.strip()) > 0

        api_key = settings.OPENAI_API_KEY
        self.use_openai = api_key and not api_key.startswith("mock-") and len(api_key.strip()) > 0

        if self.use_gemini:
            self.emb_provider = GeminiEmbeddingProvider(api_key=gemini_key)
        elif self.use_openai:
            self.emb_provider = OpenAIEmbeddingProvider(api_key=api_key)
        else:
            self.emb_provider = None

        # Initialiser le Query Rewriter
        self.rewriter = QueryRewriter()

    def _load_corpus(self):
        if not self.chunks_file.exists():
            logger.warning(f"Fichier chunks {self.chunks_file} introuvable pour BM25.")
            return
            
        with open(self.chunks_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    self.chunks.append(json.loads(line))
        logger.info(f"Chargement de {len(self.chunks)} chunks pour l'index lexical BM25.")

    def search(
        self, 
        query: str, 
        top_k: int = 10, 
        filter_dict: dict = None,
        periode_cible: Optional[str] = None,
        intervalle_cible: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Exécute la recherche hybride avec réécriture et filtrage temporel.
        """
        if not self.chunks:
            return []

        # 1. Analyser la requête avec le rewriter (variations + extraction temporelle)
        rewrite_res = self.rewriter.rewrite(query)
        variations = rewrite_res["variations"]
        
        # Si non spécifiés explicitement en argument, on prend ce qu'a extrait le rewriter
        if periode_cible is None:
            periode_cible = rewrite_res["periode_cible"]
        if intervalle_cible is None:
            intervalle_cible = rewrite_res["intervalle_cible"]

        logger.info(f"[Hybrid Engine] Période cible: {periode_cible} | Intervalle cible: {intervalle_cible}")

        # Construire les filtres de métadonnées actifs (avec filtres temporels s'ils sont spécifiques)
        active_filter = dict(filter_dict) if filter_dict else {}
        if periode_cible != "global":
            active_filter["metadata.periode"] = periode_cible
        if intervalle_cible != "all":
            active_filter["metadata.intervalle_temps"] = intervalle_cible

        # 2. Recherche hybride pour chaque variation et fusion des candidats
        merged_candidates = {}

        for sub_query in variations:
            # Recherche Sémantique (Qdrant)
            try:
                if self.emb_provider:
                    query_vector = self.emb_provider.get_embedding(sub_query)
                else:
                    query_vector = generate_deterministic_vector(sub_query)
            except Exception as e:
                logger.error(f"Erreur vectorisation requête : {e}")
                query_vector = generate_deterministic_vector(sub_query)

            semantic_results = self.vector_store.search_semantic(
                query_vector=query_vector,
                top_k=min(300, len(self.chunks)),
                filter_dict=active_filter
            )
            
            semantic_map = {}
            for hit in semantic_results:
                point_id = hit.payload["metadata"]["id"]
                semantic_map[point_id] = {
                    "score": hit.score,
                    "text": hit.payload["text"],
                    "parent_id": hit.payload["parent_id"],
                    "metadata": hit.payload["metadata"]
                }

            # Recherche Lexicale (BM25)
            indices_filter = []
            for idx, doc in enumerate(self.chunks):
                if matches_metadata(doc["metadata"], active_filter):
                    indices_filter.append(idx)
                    
            bm25_results = []
            if self.bm25 and indices_filter:
                bm25_results = self.bm25.search(sub_query, indices_filter=indices_filter)

            bm25_map = {}
            for rank, (idx, score) in enumerate(bm25_results[:50]):
                doc = self.chunks[idx]
                point_id = doc["metadata"]["id"]
                bm25_map[point_id] = {
                    "score": score,
                    "text": doc["text"],
                    "parent_id": doc["metadata"].get("parent_id", ""),
                    "metadata": doc["metadata"]
                }

            # Fusion des scores (Min-Max Normalization) pour cette sous-requête
            all_ids = set(semantic_map.keys()).union(set(bm25_map.keys()))
            
            sem_scores = [val["score"] for val in semantic_map.values()]
            min_sem = min(sem_scores) if sem_scores else 0.0
            max_sem = max(sem_scores) if sem_scores else 1.0
            sem_range = (max_sem - min_sem) if (max_sem - min_sem) > 0 else 1.0

            lex_scores = [val["score"] for val in bm25_map.values()]
            min_lex = min(lex_scores) if lex_scores else 0.0
            max_lex = max(lex_scores) if lex_scores else 1.0
            lex_range = (max_lex - min_lex) if (max_lex - min_lex) > 0 else 1.0

            for pid in all_ids:
                if pid in semantic_map:
                    sem_raw = semantic_map[pid]["score"]
                    sem_norm = (sem_raw - min_sem) / sem_range
                    text = semantic_map[pid]["text"]
                    parent_id = semantic_map[pid]["parent_id"]
                    metadata = semantic_map[pid]["metadata"]
                else:
                    sem_raw = 0.0
                    sem_norm = 0.0
                    text = bm25_map[pid]["text"]
                    metadata = bm25_map[pid]["metadata"]
                    import uuid
                    parent_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, metadata["source"]))

                if pid in bm25_map:
                    lex_raw = bm25_map[pid]["score"]
                    lex_norm = (lex_raw - min_lex) / lex_range
                else:
                    lex_raw = 0.0
                    lex_norm = 0.0

                # Score hybride (70% Sémantique, 30% Lexical)
                hybrid_score = 0.7 * sem_norm + 0.3 * lex_norm
                
                candidate = {
                    "id": pid,
                    "text": text,
                    "parent_id": parent_id,
                    "metadata": metadata,
                    "scores": {
                        "semantic_raw": sem_raw,
                        "semantic_normalized": sem_norm,
                        "lexical_raw": lex_raw,
                        "lexical_normalized": lex_norm,
                        "hybrid": hybrid_score
                    }
                }

                # Garder le candidat avec le meilleur score hybride
                if pid not in merged_candidates or hybrid_score > merged_candidates[pid]["scores"]["hybrid"]:
                    merged_candidates[pid] = candidate

        # 3. Trier et retourner les résultats
        sorted_candidates = list(merged_candidates.values())
        sorted_candidates.sort(key=lambda x: x["scores"]["hybrid"], reverse=True)
        return sorted_candidates[:top_k]

