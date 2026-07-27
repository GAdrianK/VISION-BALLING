import json
import logging
import re
from typing import List
from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

class QueryRewriter:
    """
    QueryRewriter utilise GPT-4o-mini pour réécrire et diversifier les requêtes tactiques
    afin d'optimiser le taux de rappel (Recall) lors de la recherche hybride.
    """
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.use_openai = self.api_key and not self.api_key.startswith("mock-") and len(self.api_key.strip()) > 0
        if self.use_openai:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None

    def rewrite(self, query: str) -> dict:
        """
        Réécrit la requête en variations et extrait la période et l'intervalle cibles.
        Retourne un dictionnaire contenant :
        - "variations": List[str]
        - "periode_cible": str ("1MT", "2MT", "prolongations", "global")
        - "intervalle_cible": str ("0-15", "15-30", ..., ou "all")
        """
        if not query.strip():
            return {
                "variations": [],
                "periode_cible": "global",
                "intervalle_cible": "all"
            }

        if self.use_openai and self.client:
            try:
                system_prompt = (
                    "Tu es un expert en tactique de football spécialisé dans l'ingénierie RAG.\n"
                    "Ton rôle est de prendre une question utilisateur sur le football et de générer :\n"
                    "1. 2 à 3 requêtes de recherche simplifiées ou variations sémantiques (mots-clés, concepts tactiques, équipes).\n"
                    "2. La période cible du match ('1MT', '2MT', 'prolongations', 'global') si elle est spécifiée ou induite.\n"
                    "3. L'intervalle de temps cible en minutes ('0-15', '15-30', '30-45', '45-60', '60-75', '75-90', '90+', 'all') si spécifié ou induit.\n\n"
                    "Règles d'induction temporelle :\n"
                    "- 'début de match', 'premières minutes', '12e minute' -> periode_cible='1MT', intervalle_cible='0-15' (ou intervalle correspondant)\n"
                    "- 'fin de match', 'dernières minutes', '72e minute' -> periode_cible='2MT', intervalle_cible='60-75' (ou intervalle correspondant)\n"
                    "- Si aucun élément temporel n'est détecté, utilise 'global' pour periode_cible et 'all' pour intervalle_cible.\n\n"
                    "Renvoie UNIQUEMENT un objet JSON avec les clés suivantes :\n"
                    "{\n"
                    "  \"variations\": [\"string\"],\n"
                    "  \"periode_cible\": \"string\",\n"
                    "  \"intervalle_cible\": \"string\"\n"
                    "}\n"
                    "Pas de markdown, pas d'explication."
                )

                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Génère le JSON pour cette question : '{query}'"}
                    ],
                    temperature=0.2,
                    max_tokens=150
                )
                
                content = response.choices[0].message.content.strip()
                # Nettoyer les balises de code markdown éventuelles
                content = re.sub(r"```json\s*", "", content)
                content = re.sub(r"\s*```", "", content)
                
                result = json.loads(content)
                if isinstance(result, dict) and "variations" in result:
                    # Assurer la présence des champs temporels par défaut
                    result.setdefault("periode_cible", "global")
                    result.setdefault("intervalle_cible", "all")
                    
                    # S'assurer que la requête d'origine est incluse
                    variations = result["variations"]
                    if query not in variations:
                        variations.insert(0, query)
                    result["variations"] = [v.strip() for v in variations if isinstance(v, str)]
                    return result
            except Exception as e:
                logger.error(f"Erreur lors du Query Rewriting via OpenAI: {e}. Utilisation du fallback local.")
        
        # Fallback déterministe local par règles (mode hors-ligne ou erreur)
        return self._fallback_rewrite(query)

    def _fallback_rewrite(self, query: str) -> dict:
        """
        Génère des variations et extrait des paramètres temporels basés sur des expressions régulières.
        """
        query_lower = query.lower()
        
        # 1. Extraction temporelle déterministe
        periode = "global"
        intervalle = "all"
        
        # Détection période
        if any(w in query_lower for w in ["1mt", "première mi-temps", "premiere mi-temps", "début de match", "debut de match", "premières minutes", "premieres minutes"]):
            periode = "1MT"
        elif any(w in query_lower for w in ["2mt", "deuxième mi-temps", "deuxieme mi-temps", "fin de match", "dernières minutes", "dernieres minutes"]):
            periode = "2MT"
        elif "prolongation" in query_lower:
            periode = "prolongations"
            
        # Détection intervalle via regex minute (ex: 12e, 12ème, 72', 72e)
        min_match = re.search(r"\b(\d{1,3})(?:e|ème)?\s*(?:minute|min|'|è)", query_lower)
        if min_match:
            minute = int(min_match.group(1))
            if minute <= 45:
                if periode == "global":
                    periode = "1MT"
                if minute <= 15:
                    intervalle = "0-15"
                elif minute <= 30:
                    intervalle = "15-30"
                else:
                    intervalle = "30-45"
            else:
                if periode == "global":
                    periode = "2MT"
                if minute <= 60:
                    intervalle = "45-60"
                elif minute <= 75:
                    intervalle = "60-75"
                elif minute <= 90:
                    intervalle = "75-90"
                else:
                    intervalle = "90+"
        else:
            # Heuristiques textuelles simples
            if any(w in query_lower for w in ["début de match", "debut de match", "premières minutes"]):
                intervalle = "0-15"
                if periode == "global":
                    periode = "1MT"
            elif any(w in query_lower for w in ["fin de match", "dernières minutes"]):
                intervalle = "60-75"
                if periode == "global":
                    periode = "2MT"

        # 2. Génération des variations
        variations = [query]
        
        # Extraction simplifiée de mots tactiques clés
        keywords = []
        for kw in ["pressing", "contre-pressing", "bloc bas", "bloc median", "low-block", "transition", "possession", "lateral", "ailier"]:
            if kw in query_lower:
                keywords.append(kw)
                
        # Extraction simplifiée d'équipes clés
        teams = []
        for team in ["psg", "paris", "om", "marseille", "real", "madrid", "barca", "barcelone"]:
            if team in query_lower:
                teams.append(team)

        if teams and keywords:
            variations.append(f"{' '.join(teams)} { ' '.join(keywords) }")
        elif keywords:
            variations.append(f"{keywords[0]} tactique")
            
        variations.append(f"{query} tactique football")
        
        # Dédupliquer tout en gardant l'ordre
        seen = set()
        dedup_vars = []
        for v in variations:
            if v.lower() not in seen:
                seen.add(v.lower())
                dedup_vars.append(v)
                
        return {
            "variations": dedup_vars[:3],
            "periode_cible": periode,
            "intervalle_cible": intervalle
        }

