import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from openai import OpenAI
from app.core.config import settings
from app.services.rag_engine import RAGEngine
from app.services.query_classifier import QueryClassifier
from app.schemas.chat import ChatMode, ChatRequest, ChatResponse, SourceReference

# Dossier des prompts
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

class ChatService:
    """
    Service de Chat orchestrant la recherche RAG et la génération LLM
    selon différents profils d'assistance footballistique.
    """
    def __init__(self, rag_engine: RAGEngine, openai_api_key: Optional[str] = None, gemini_api_key: Optional[str] = None):
        self.rag_engine = rag_engine
        self.api_key = openai_api_key
        self.gemini_api_key = gemini_api_key
        self.openrouter_key = settings.openrouter_key
        self.use_openrouter = self.openrouter_key and not self.openrouter_key.startswith("mock-") and len(self.openrouter_key.strip()) > 0
        self.prompts: Dict[ChatMode, str] = {}
        self.classifier = QueryClassifier()
        self._load_prompts()

    def _load_prompts(self):
        """
        Charge les fichiers de prompts système depuis le disque.
        """
        modes_files = {
            ChatMode.COACH: "coach_prompt.txt",
            ChatMode.ANALYST: "analyst_prompt.txt",
            ChatMode.FAN: "fan_prompt.txt"
        }
        
        for mode, filename in modes_files.items():
            path = PROMPTS_DIR / filename
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        self.prompts[mode] = f.read().strip()
                except Exception as e:
                    print(f"Erreur de chargement du prompt {filename} : {e}")
                    self.prompts[mode] = self._get_fallback_prompt_text(mode)
            else:
                self.prompts[mode] = self._get_fallback_prompt_text(mode)

    def _get_fallback_prompt_text(self, mode: ChatMode) -> str:
        """
        Prompts de secours codés en dur au cas où les fichiers texte soient absents.
        """
        if mode == ChatMode.COACH:
            return "Tu es un coach tactique de football. Reste structuré, concret et technique."
        elif mode == ChatMode.ANALYST:
            return "Tu es un analyste vidéo tactique. Sois clinique, objectif et analytique."
        else:
            return "Tu es un supporter passionné. Sois enthousiaste et familier."

    def generate_response(self, request: ChatRequest) -> ChatResponse:
        # 1. Classification de la requête
        classification = self.classifier.classify(request.message)
        
        # 2. Routage selon le type de requête
        if classification["type"] == "greeting":
            # Salutation simple sans RAG
            answer = "Salut ! Je suis Football IQ Assistant. Tu peux me demander une analyse tactique, une séance d'entraînement ou une explication football."
            
            if request.mode == ChatMode.COACH:
                answer = "### 📋 Salut Coach !\nBienvenue dans votre espace tactique. Comment puis-je vous aider aujourd'hui ? Demandez-moi des schémas de relance, des séances d'entraînement spécifiques ou des consignes collectives."
            elif request.mode == ChatMode.FAN:
                answer = "### 📣 Salut l'ami !\nInstalle-toi bien dans le virage. De quelle tactique de légende ou de quel joueur clé veux-tu qu'on discute aujourd'hui ?"
            elif request.mode == ChatMode.ANALYST:
                answer = "### 🔍 Bonjour de la cabine d'analyse !\nPrêt à décortiquer les circuits de passes, les transitions rapides et l'organisation des blocs de jeu. Quelle phase souhaitez-vous étudier ?"
                
            return ChatResponse(
                answer=answer,
                mode=request.mode,
                sources=[]
            )
            
        elif classification["type"] == "out_of_scope":
            # Hors-sujet sans RAG
            return ChatResponse(
                answer="Je n’ai pas assez d’informations dans la base actuelle pour répondre précisément.",
                mode=request.mode,
                sources=[]
            )
            
        # 3. Recherche RAG guidée par l'intention
        search_results = self.rag_engine.search(request.message, top_k=3, query_metadata=classification)
        
        # Formater les sources Pydantic
        sources = [
            SourceReference(
                text=res["text"],
                source=res["source"],
                score=res["score"]
            )
            for res in search_results
        ]
        
        # 2. Récupérer le prompt système correspondant au mode
        system_prompt = self.prompts.get(request.mode, self._get_fallback_prompt_text(request.mode))
        
        # 3. Construire le contexte pour le prompt utilisateur
        rag_context = ""
        if search_results:
            rag_context = "\n\n".join([
                f"--- EXTRAIT SOURCE: {res['source']} ---\n{res['text']}"
                for res in search_results
            ])
            
        user_prompt = f"""[CONTEXTE DE LA BASE DE CONNAISSANCES TACTIQUES]
{rag_context if rag_context else "Aucun document tactique pertinent trouvé dans la base de connaissances."}

[CONSIGNE CRITIQUE]
Base-toi uniquement sur le contexte ci-dessus si présent pour répondre à la question. Ne sors pas du cadre footballistique.

[MESSAGE DE L'UTILISATEUR]
{request.message}"""

        # 4. Génération (OpenRouter, Gemini, OpenAI ou Fallback Mock local)
        use_openrouter = self.use_openrouter
        use_gemini = self.gemini_api_key and not self.gemini_api_key.startswith("mock-") and len(self.gemini_api_key.strip()) > 0
        use_openai = self.api_key and not self.api_key.startswith("mock-") and len(self.api_key.strip()) > 0

        if use_openrouter:
            try:
                client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=self.openrouter_key
                )
                
                messages = [{"role": "system", "content": system_prompt}]
                if request.history:
                    for h in request.history[-5:]:
                        messages.append({"role": h.role, "content": h.content})
                        
                messages.append({"role": "user", "content": user_prompt})
                
                try:
                    response = client.chat.completions.create(
                        model="qwen/qwen-2.5-72b-instruct:free",
                        messages=messages,
                        temperature=0.2
                    )
                    answer = response.choices[0].message.content
                    return ChatResponse(
                        answer=answer,
                        mode=request.mode,
                        sources=sources
                    )
                except Exception as e:
                    print(f"[WARNING] Erreur OpenRouter Qwen gratuit dans le chat : {e}. Tentative avec la version payante.")
                    response = client.chat.completions.create(
                        model="qwen/qwen-2.5-72b-instruct",
                        messages=messages,
                        temperature=0.2
                    )
                    answer = response.choices[0].message.content
                    return ChatResponse(
                        answer=answer,
                        mode=request.mode,
                        sources=sources
                    )
            except Exception as e2:
                print(f"Erreur lors de l'appel OpenRouter dans le chat : {e2}.")
                if not use_gemini and not use_openai:
                    raise e2

        if use_gemini and not use_openrouter:
            try:
                from google import genai
                from google.genai import types
                
                client = genai.Client(api_key=self.gemini_api_key)
                
                # Construire les messages pour le chat completion
                contents = []
                if request.history:
                    for h in request.history[-5:]:
                        # Associer le role correct pour Gemini ('model' ou 'user')
                        role = "model" if h.role == "assistant" else h.role
                        contents.append(types.Content(
                            role=role,
                            parts=[types.Part.from_text(text=h.content)]
                        ))
                
                # Ajouter le message utilisateur courant
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=user_prompt)]
                ))
                
                response = client.models.generate_content(
                    model="gemini-flash-latest",
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.2
                    )
                )
                
                answer = response.text
                return ChatResponse(
                    answer=answer,
                    mode=request.mode,
                    sources=sources
                )
            except Exception as e:
                print(f"Erreur lors de l'appel Gemini : {e}.")
                raise e

        if use_openai and not use_gemini and not use_openrouter: # ou si gemini/openrouter ont échoué
            try:
                client = OpenAI(api_key=self.api_key)
                
                # Construire les messages pour le chat completion
                messages = [{"role": "system", "content": system_prompt}]
                
                # Ajouter l'historique s'il existe (limité aux 5 derniers messages pour éviter de saturer la fenêtre)
                if request.history:
                    for h in request.history[-5:]:
                        messages.append({"role": h.role, "content": h.content})
                        
                messages.append({"role": "user", "content": user_prompt})
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.2
                )
                
                answer = response.choices[0].message.content
                return ChatResponse(
                    answer=answer,
                    mode=request.mode,
                    sources=sources
                )
            except Exception as e:
                print(f"Erreur lors de l'appel OpenAI : {e}. Bascule sur le fallback local mock.")

        # Fallback Mock enrichi
        answer = self._generate_mock_response(request.mode, request.message, sources)
        return ChatResponse(
            answer=answer,
            mode=request.mode,
            sources=sources
        )

    def _is_query_in_sources(self, query: str, sources: List[SourceReference]) -> bool:
        """
        Vérifie si la requête contient au moins un terme significatif présent dans les sources.
        Supports automatic hyphenation/de-hyphenation for formations.
        """
        import re
        # Normaliser et nettoyer la requête
        query_clean = re.sub(r"[^\w\s-]", " ", query.lower())
        query_tokens = [t for t in query_clean.split() if len(t) > 1]
        
        # Stop words français courants
        stop_words = {
            "le", "la", "les", "de", "des", "un", "une", "du", "en", "pour", "dans", "avec", 
            "est", "sont", "ce", "c'est", "qu'est", "que", "qui", "qu", "comment", "pourquoi", 
            "quelle", "quelles", "quel", "quels", "explique", "expliques", "moi", "nous", 
            "vous", "je", "tu", "il", "elle", "ils", "elles", "mon", "ton", "son", "ma", "ta", 
            "sa", "mes", "tes", "ses", "et", "ou", "mais", "donc", "or", "ni", "car", "sur", 
            "se", "sa", "ses", "ce", "ces", "cette", "cet", "par", "aux", "au", "aussi", "faire",
            "fait", "a", "ont", "avoir", "etre", "être"
        }
        
        meaningful_tokens = [t for t in query_tokens if t not in stop_words]
        
        if not meaningful_tokens:
            return False
            
        # Combiner le texte des sources pour la recherche
        source_text_combined = " ".join([s.text.lower() for s in sources])
        source_text_clean = re.sub(r"[^\w\s-]", " ", source_text_combined)
        
        # Extraire les tokens de la source pour une comparaison directe
        source_tokens = set(source_text_clean.split())
        # Ajouter les variantes sans tiret (ex: 4-3-3 -> 433)
        for t in list(source_tokens):
            if '-' in t:
                source_tokens.add(t.replace('-', ''))
                
        for token in meaningful_tokens:
            # Correspondance directe dans les tokens normalisés
            if token in source_tokens:
                return True
                
            # Correspondance regex standard
            pattern = r'\b' + re.escape(token) + r'\b'
            if re.search(pattern, source_text_clean):
                return True
                
            # Si le token recherché est "433", chercher aussi "4-3-3"
            if token.isdigit() and len(token) in [3, 4]:
                with_hyphens = "-".join(list(token))
                if with_hyphens in source_tokens:
                    return True
                pattern_hyphens = r'\b' + re.escape(with_hyphens) + r'\b'
                if re.search(pattern_hyphens, source_text_clean):
                    return True
                
        return False

    def _generate_mock_response(self, mode: ChatMode, query: str, sources: List[SourceReference]) -> str:
        """
        Génère une réponse simulée à partir des sources RAG sans inventer d'information.
        """
        if not sources or not self._is_query_in_sources(query, sources):
            return "Je n’ai pas assez d’informations dans la base actuelle pour répondre précisément."
            
        import re
        
        # 1. Analyser et extraire les informations des sources
        paragraphs = []
        consignes = []
        exercices = []
        
        for src in sources:
            text = src.text
            # Séparer le texte par lignes
            lines = text.split("\n")
            
            content_lines = []
            is_exercise_context = False
            
            for line in lines:
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                if line_stripped.startswith("[") and line_stripped.endswith("]"):
                    # C'est un header de métadonnées, on l'utilise pour savoir si c'est un exercice
                    if any(kw in line_stripped.lower() for kw in ["séance d'entraînement", "exercice", "jeu final", "bloc"]):
                        is_exercise_context = True
                    continue
                
                content_lines.append(line)
                
            # Parcourir les lignes de contenu pour classer les éléments
            for line in content_lines:
                line_stripped = line.strip()
                # Si c'est une puce ou liste
                if line_stripped.startswith("*") or line_stripped.startswith("-") or (len(line_stripped) > 2 and line_stripped[0].isdigit() and line_stripped[1:3] == ". "):
                    # Nettoyer la puce sans toucher aux marqueurs de gras markdown (**)
                    cleaned_line = re.sub(r'^(\s*[\*\-]\s+|\s*\d+\.\s+)', '', line_stripped).strip()
                    # Si c'est dans un contexte d'exercice ou contient des mots-clés d'exercice
                    if is_exercise_context or any(kw in line_stripped.lower() for kw in ["structure :", "règles :", "objectif :"]):
                        exercices.append(line_stripped)
                    else:
                        consignes.append(cleaned_line)
                else:
                    # C'est du texte normal/paragraphe (ignorer les titres de premier niveau)
                    if not line_stripped.startswith("#"):
                        paragraphs.append(line_stripped)

        # Nettoyer et dédoublonner
        consignes = list(dict.fromkeys(consignes))[:4]
        exercices = list(dict.fromkeys(exercices))
        
        # Construire l'explication (Analyse) à partir des paragraphes
        explanation = ""
        if paragraphs:
            # Filtrer pour ne garder que les lignes textuelles sans puces
            clean_paragraphs = [p for p in paragraphs if not p.startswith("*") and not p.startswith("-")]
            if clean_paragraphs:
                explanation = "\n\n".join(clean_paragraphs[:2])
            else:
                explanation = "\n\n".join(paragraphs[:2])
        
        if not explanation:
            if consignes:
                explanation = " ".join(consignes[:2])
            else:
                explanation = "Principes tactiques documentés dans nos bases."
                
        # Limiter la longueur de l'explication et ajouter la référence
        ref_suffix = f" (source: {sources[0].source})"
        explanation = explanation + ref_suffix

        # Formater selon le mode
        if mode == ChatMode.COACH:
            # Section Exercice Recommandé
            if exercices:
                # Reconstruire la structure d'exercice proprement
                exercice_text = "\n".join(exercices[:5])
            else:
                exercice_text = "[Aucun exercice spécifique n'est référencé dans notre base de données tactique pour ce sujet. Nous restons sur les principes de jeu généraux.]"
                
            # Section Consignes
            if consignes:
                consignes_text = "\n".join([f"{i+1}. {c}" for i, c in enumerate(consignes)])
            else:
                consignes_text = "1. Appliquer les principes de positionnement décrits dans les sources."
                
            return f"""### 📋 Analyse du Coach
{explanation}

### 🏃‍♂️ Consignes du Terrain
{consignes_text}

### ⚽ Exercice Recommandé
{exercice_text}"""

        elif mode == ChatMode.ANALYST:
            # Forces / Faiblesses
            forces_faiblesses = []
            for src in sources:
                if any(kw in src.text.lower() for kw in ["avantages", "forces", "risques", "faiblesses", "perte", "panique", "isolement"]):
                    for line in src.text.split("\n"):
                        if any(k in line.lower() for k in ["avantage", "force", "risque", "faiblesse", "perte", "panique", "isolement"]):
                            forces_faiblesses.append(line.strip())
                            
            if forces_faiblesses:
                forces_text = "\n".join(forces_faiblesses[:3])
            else:
                forces_text = "[Non documenté spécifiquement dans les sources tactiques]"
                
            sources_list = "\n".join([f"- {name}" for name in list(dict.fromkeys([s.source for s in sources]))])
            
            return f"""### 🔍 Observations Structurelles
{explanation}

### ⚖️ Forces/Faiblesses du Système
{forces_text}

### 📄 Fichiers tactiques analysés
{sources_list}"""

        else: # Fan Passionné (vulgarisé sans caricature)
            focus_parts = []
            for c in consignes[:2]:
                focus_parts.append(f"- {c}")
            focus_text = "\n".join(focus_parts) if focus_parts else "[Non documenté spécifiquement dans les sources tactiques]"
            
            return f"""### 📣 L'Avis des Fans
{explanation}

### ⭐️ Le Focus du Match
{focus_text}"""
