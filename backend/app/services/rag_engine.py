import os
from typing import List, Dict, Any, Optional
from app.services.document_loader import DocumentLoader
from app.services.embedding_provider import (
    EmbeddingProvider,
    OpenAIEmbeddingProvider,
    TFIDFEmbeddingProvider,
    get_cosine_similarity
)

class RAGEngine:
    """
    Moteur RAG (Retrieval-Augmented Generation) local en mémoire.
    Charge, découpe, vectorise les fiches tactiques et recherche sémantiquement.
    """
    def __init__(self, knowledge_base_dir: str, openai_api_key: Optional[str] = None):
        self.kb_dir = knowledge_base_dir
        self.api_key = openai_api_key
        
        self.loader = DocumentLoader(self.kb_dir)
        self.chunks: List[Dict[str, Any]] = []
        self.embeddings: List[List[float]] = []
        self.provider: Optional[EmbeddingProvider] = None
        self.mode = "offline"  # ou "online" (OpenAI)

    def initialize(self):
        """
        Initialise le moteur RAG : charge les documents, sélectionne le provider d'embeddings
        et génère l'index en mémoire.
        """
        print(f"Initialisation du RAGEngine avec la base : {self.kb_dir}")
        self.chunks = self.loader.load_all_documents()
        
        if not self.chunks:
            print("Avertissement : Aucun document trouvé dans la base de connaissances.")
            return

        texts = [chunk["text"] for chunk in self.chunks]
        
        # Sélection du fournisseur d'embeddings
        use_openai = False
        if self.api_key and not self.api_key.startswith("mock-") and len(self.api_key.strip()) > 0:
            use_openai = True
            
        if use_openai:
            try:
                print("Sélection du mode : OpenAI Embeddings (En ligne)")
                openai_provider = OpenAIEmbeddingProvider(api_key=self.api_key)
                # Test de connexion rapide sur un mini-texte
                openai_provider.get_embedding("test")
                
                # Calculer les embeddings pour tous les chunks
                self.embeddings = openai_provider.get_embeddings(texts)
                self.provider = openai_provider
                self.mode = "online"
                print(f"Indexation réussie de {len(self.chunks)} chunks via OpenAI.")
                return
            except Exception as e:
                print(f"Erreur d'initialisation OpenAI : {e}. Bascule sur le fallback local TF-IDF.")
        
        # Fallback local TF-IDF (sans clé ou si OpenAI a échoué)
        print("Sélection du mode : TF-IDF Local (Hors-ligne)")
        tfidf_provider = TFIDFEmbeddingProvider()
        tfidf_provider.fit(texts)
        self.embeddings = tfidf_provider.get_embeddings(texts)
        self.provider = tfidf_provider
        self.mode = "offline"
        print(f"Indexation locale réussie de {len(self.chunks)} chunks via TF-IDF.")

    def search(self, query: str, top_k: int = 3, query_metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Recherche sémantique des chunks les plus proches de la requête avec scoring hybride par intentions.
        """
        if not self.chunks or not self.provider or not self.embeddings:
            return []

        try:
            # Calculer l'embedding de la requête
            query_vector = self.provider.get_embedding(query)
        except Exception as e:
            print(f"Erreur lors du calcul d'embedding de la requête : {e}")
            return []

        # Calculer le score de similarité pour chaque chunk
        results = []
        for idx, chunk in enumerate(self.chunks):
            chunk_vector = self.embeddings[idx]
            score = get_cosine_similarity(query_vector, chunk_vector)
            
            # Ajustement sémantique hybride
            if query_metadata:
                # 1. Intent/Phase de base
                q_intent = query_metadata.get("intent", "general")
                q_phase = query_metadata.get("phase", "general")
                
                chunk_intent = chunk["metadata"].get("intent", "general")
                chunk_phase = chunk["metadata"].get("phase", "general")
                
                # Check if query has a specific problem or phase to bypass generic formations intent boost
                entities = query_metadata.get("entities")
                has_problem_or_phase = False
                if entities:
                    if entities.get("problem") or entities.get("phase"):
                        has_problem_or_phase = True

                # Bonus/Pénalité d'Intention
                if q_intent != "general" and chunk_intent != "general":
                    if q_intent == "formations" and has_problem_or_phase:
                        # Skip formation intent boost since the query focuses on a problem/phase
                        pass
                    elif q_intent == chunk_intent:
                        score += 0.15
                    # Pénalités d'opposition directe (attack vs defend)
                    elif (q_intent == "attack" and chunk_intent == "defend") or (q_intent == "defend" and chunk_intent == "attack"):
                        score -= 0.35
                        
                # Bonus/Pénalité de Phase
                if q_phase != "general" and chunk_phase != "general":
                    if q_phase == chunk_phase:
                        score += 0.10
                    elif (q_phase == "offensive" and chunk_phase == "defensive") or (q_phase == "defensive" and chunk_phase == "offensive"):
                        score -= 0.20

                # 2. Entités tactiques fines
                if entities:
                    formation = entities.get("formation")
                    problem = entities.get("problem")
                    phase_entity = entities.get("phase")
                    goal = entities.get("goal")

                    chunk_text_lower = chunk["text"].lower()
                    chunk_source_lower = chunk["source"].lower()
                    chunk_keywords = [kw.lower() for kw in chunk["metadata"].get("keywords", [])]

                    # A. Match de formation (bonus +0.10)
                    if formation:
                        formation_clean = formation.replace("-", "")
                        if (formation in chunk_text_lower or 
                            formation_clean in chunk_text_lower or 
                            formation in chunk_keywords or 
                            formation_clean in chunk_keywords or 
                            formation in chunk_source_lower or 
                            formation_clean in chunk_source_lower):
                            score += 0.10

                    # B. Match de phase et problème (bonus fort problem + phase : total +0.75)
                    problem_matched = False
                    if problem:
                        problem_keywords = {
                            "pertes de balle": ["perdre", "perte", "perd", "déchet", "dechet"],
                            "manque d'occasions": ["occasion", "creer", "créer"],
                            "difficulté à défendre": ["defend", "défend", "buts", "encaiss", "transperce", "subit", "dédoubl", "dedoubl"],
                            "manque d'intensité": ["intensité", "intensite", "physique", "fatigue", "epuis", "épuis"],
                            "erreurs": ["erreur", "faute", "bavure"],
                            "isolement": ["isol"]
                        }
                        keywords = problem_keywords.get(problem, [])
                        if any(kw in chunk_text_lower or kw in chunk_keywords or kw in chunk_source_lower for kw in keywords):
                            problem_matched = True
                            score += 0.40
                            # Bonus si le problème est dans le nom du fichier
                            prob_clean = problem.replace(" ", "_")
                            if prob_clean in chunk_source_lower:
                                score += 0.20

                    phase_matched = False
                    if phase_entity:
                        phase_keywords = {
                            "relance": ["relance", "construction", "sortie de balle", "sortie de press", "ressortir", "build-up", "build up", "relancent", "sortie_balle"],
                            "pressing": ["pressing", "contre-press", "gegenpress", "chasser", "harcel", "presser haut"],
                            "transition": ["transition", "contre-attaq", "contre", "repli", "contre-defens", "rest defense", "défense préventive"],
                            "bloc bas": ["bloc bas", "bloc-bas", "defendre bas", "défendre bas", "entre les lignes", "interlignes"],
                            "attaque placée": ["attaque placee", "attaque placée", "possession", "circul"],
                            "finition": ["finition", "marquer", "tirer", "centre", "devant le but", "surface"]
                        }
                        keywords = phase_keywords.get(phase_entity, [])
                        if (any(kw in chunk_text_lower or kw in chunk_keywords or kw in chunk_source_lower for kw in keywords) or 
                            chunk_phase == phase_entity or 
                            chunk["metadata"].get("topic") == phase_entity):
                            phase_matched = True
                            score += 0.35
                            # Bonus si la phase est dans le nom du fichier
                            phase_clean = phase_entity.replace(" ", "_")
                            if phase_clean in chunk_source_lower:
                                score += 0.20

                    # C. Match de goal (bonus moyen +0.15)
                    if goal:
                        if goal == "préparer":
                            # Target exercises / sessions
                            if any(w in chunk_text_lower or w in chunk_source_lower for w in ["exercice", "séance", "seance", "entraînement", "entrainement"]):
                                score += 0.15
                        elif goal == "corriger":
                            # Target errors / fixes
                            if any(w in chunk_text_lower or w in chunk_source_lower for w in ["erreur", "correction", "terrain"]):
                                score += 0.15
                        elif goal == "défendre":
                            if any(w in chunk_text_lower or w in chunk_source_lower for w in ["défend", "defend", "défens", "defens"]):
                                score += 0.15
                        elif goal == "attaquer":
                            if any(w in chunk_text_lower or w in chunk_source_lower for w in ["attaqu", "offens"]):
                                score += 0.15
                        else:
                            goal_keywords = {
                                "améliorer": ["ameliorer", "améliorer", "optimiser", "principe", "animation"],
                                "comprendre": ["comprendre", "expliquer", "définition", "definition", "analyse"]
                            }
                            keywords = goal_keywords.get(goal, [])
                            if any(kw in chunk_text_lower for kw in keywords):
                                score += 0.15

                    # D. Pénalité document uniquement formationnel sans traitement du problème
                    is_formation_doc = chunk["source"].startswith("formation_") or chunk["source"].startswith("formations_")
                    if is_formation_doc and problem:
                        score -= 0.50
            
            # Clamping du score final pour l'affichage
            display_score = max(0.0, min(1.0, score))
            
            results.append({
                "text": chunk["text"],
                "source": chunk["source"],
                "score": round(display_score, 4),
                "unclamped_score": score,
                "metadata": chunk["metadata"]
            })
 
        # Trier par score non tronqué (unclamped) décroissant et renvoyer les top_k
        results.sort(key=lambda x: x["unclamped_score"], reverse=True)
        return results[:top_k]
