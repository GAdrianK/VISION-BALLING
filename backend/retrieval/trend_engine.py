"""
trend_engine.py
================
Moteur de Tendances Multi-Match (Multi-Match Synthesizer).

Contrairement au moteur hybride qui analyse un seul match en profondeur,
ce moteur répond à des questions macro, comparatives ou évolutives sur
plusieurs matchs de la saison (ex : "Compare le pressing contre l'Inter
et contre Man City" ou "Évolution du rôle de Vitinha cette saison").

Logique :
  1. Extraction des termes-cibles (adversaires, compétitions, joueurs)
     depuis la requête utilisateur.
  2. Filtrage des chunks Qdrant par source (match_id contenant le terme).
  3. Regroupement des chunks par match, contexte rendu étanche match par match.
  4. Envoi du pack structuré à GPT-4o pour synthèse comparative.
"""

import os
import re
import sys
import json
import logging
from pathlib import Path
from typing import Optional
from collections import defaultdict
from sqlalchemy import func, or_

from openai import OpenAI

backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from app.core.config import settings
from database.vector_store import VectorStoreManager
from database.parent_store import ParentStoreManager
from database.indexer import generate_deterministic_vector
from app.services.embedding_provider import OpenAIEmbeddingProvider
from app.database.sql_store import SessionLocal
from app.models.player_stats import PlayerMatchStats

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
# Correspondance de noms courts vers fragments de noms de fichiers (slugifiés)
# Les noms de fichiers générés sont du type : match_2025_05_31_paris_saint__inter_01.md
TEAM_ALIASES: dict[str, list[str]] = {
    "inter":          ["inter"],
    "man city":       ["manchester_city", "man_city", "manchester"],
    "manchester":     ["manchester_city", "man_city", "manchester"],
    "city":           ["manchester_city", "man_city", "manchester"],
    "arsenal":        ["arsenal"],
    "liverpool":      ["liverpool"],
    "brest":          ["brestois", "brest"],
    "aston villa":    ["aston_villa", "aston"],
    "stuttgart":      ["vfb_stuttgart", "stuttgart"],
    "salzburg":       ["salzburg"],
    "marseille":      ["marseille"],
    "monaco":         ["monaco"],
    "girona":         ["girona"],
    "atletico":       ["atletico"],
    "psv":            ["psv"],
    "bayern":         ["bayern"],
    "vitinha":        [],   # joueur → recherche dans le contenu
    "dembele":        [],
    "barcola":        [],
    "donnarumma":     [],
    "hakimi":         [],
    "ruiz":           [],
}

COMPETITION_KEYWORDS: dict[str, str] = {
    "ucl":    "champions",
    "ldc":    "champions",
    "ligue des champions": "champions",
    "champions league":    "champions",
    "ligue 1": "ligue_1",
    "l1":      "ligue_1",
    "coupe":   "coupe",
}


class TrendAnalysisEngine:
    """
    Moteur de synthèse multi-match pour analyses macro et comparatives.
    """

    def __init__(self):
        self.vector_store = VectorStoreManager()
        self.parent_store = ParentStoreManager()
        self.db_session_factory = SessionLocal

        # Charger tous les chunks depuis chunks.jsonl pour filtrage BM25 / métadonnées
        chunks_file = Path(settings.get_processed_data_dir()) / "chunks.jsonl"
        self.chunks: list[dict] = []
        if chunks_file.exists():
            with open(chunks_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        self.chunks.append(json.loads(line))
            logger.info(f"[TrendEngine] {len(self.chunks)} chunks chargés.")
        else:
            logger.warning("[TrendEngine] chunks.jsonl introuvable.")

        # OpenRouter
        openrouter_key = settings.openrouter_key
        self.openrouter_key = openrouter_key
        self.use_openrouter = openrouter_key and not openrouter_key.startswith("mock-") and len(openrouter_key.strip()) > 0

        # Gemini
        gemini_key = settings.gemini_key
        self.gemini_key = gemini_key
        self.use_gemini = gemini_key and not gemini_key.startswith("mock-") and len(gemini_key.strip()) > 0

        # OpenAI
        api_key = settings.OPENAI_API_KEY
        self.use_openai = api_key and not api_key.startswith("mock-") and len(api_key.strip()) > 0

        if self.use_gemini:
            from app.services.embedding_provider import GeminiEmbeddingProvider
            self.emb_provider = GeminiEmbeddingProvider(api_key=gemini_key)
        elif self.use_openai:
            self.emb_provider = OpenAIEmbeddingProvider(api_key=api_key)
        else:
            self.emb_provider = None

        self.openai_client = OpenAI(api_key=api_key) if self.use_openai else None

        # Client OpenRouter
        if self.use_openrouter:
            self.openrouter_client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.openrouter_key
            )
        else:
            self.openrouter_client = None

    # ------------------------------------------------------------------
    # Extraction des cibles depuis la requête
    # ------------------------------------------------------------------
    def _extract_targets(self, query: str) -> dict:
        """
        Extrait les adversaires, joueurs et compétitions mentionnés dans la requête.

        Returns:
            {
              "opponent_slugs": ["inter", "manchester_city"],
              "competition_kw": "champions",      # ou None
              "player_names":   ["vitinha"],
              "raw_query": query
            }
        """
        q_lower = query.lower()
        opponent_slugs: list[str] = []
        player_names: list[str] = []
        competition_kw: Optional[str] = None

        for alias, slugs in TEAM_ALIASES.items():
            if alias in q_lower:
                if slugs:          # équipe
                    opponent_slugs.extend(slugs)
                else:              # joueur
                    player_names.append(alias)

        for kw, mapped in COMPETITION_KEYWORDS.items():
            if kw in q_lower:
                competition_kw = mapped
                break

        return {
            "opponent_slugs": list(set(opponent_slugs)),
            "competition_kw": competition_kw,
            "player_names": player_names,
            "raw_query": query,
        }

    # ------------------------------------------------------------------
    # Filtrage des chunks par cibles
    # ------------------------------------------------------------------
    def _filter_chunks_by_targets(self, targets: dict) -> dict[str, list[dict]]:
        """
        Filtre les chunks selon les adversaires / compétitions / joueurs extraits.
        Utilise une recherche sémantique Qdrant avec un top_k de 150 chunks pour couvrir
        l'intégralité de la saison, puis regroupe par match.
        """
        grouped: dict[str, list[dict]] = defaultdict(list)
        opponent_slugs = targets["opponent_slugs"]
        competition_kw = targets["competition_kw"]
        player_names   = targets["player_names"]
        raw_query      = targets["raw_query"]

        # 1. Recherche sémantique Qdrant (top_k=150)
        retrieved_chunks = []
        try:
            logger.info(f"[TrendEngine] Exécution de la recherche Qdrant pour la requête : {raw_query!r} (top_k=150)")
            if self.emb_provider:
                query_vector = self.emb_provider.get_embedding(raw_query)
            else:
                query_vector = generate_deterministic_vector(raw_query)

            semantic_results = self.vector_store.search_semantic(
                query_vector=query_vector,
                top_k=150,
                filter_dict={"metadata.type_chunk": "match"}
            )
            for hit in semantic_results:
                retrieved_chunks.append({
                    "text": hit.payload["text"],
                    "metadata": hit.payload["metadata"]
                })
            logger.info(f"[TrendEngine] {len(retrieved_chunks)} chunks récupérés de Qdrant.")
        except Exception as e:
            logger.error(f"[TrendEngine] Erreur recherche Qdrant : {e}. Repli sur les chunks de match en mémoire.")
            retrieved_chunks = []

        # Si Qdrant n'a rien retourné (ex: erreur), on utilise l'in-memory corpus
        if not retrieved_chunks:
            retrieved_chunks = [c for c in self.chunks if c["metadata"].get("type_chunk") == "match"]

        # 2. Filtrage post-récupération par cibles
        for chunk in retrieved_chunks:
            source = chunk["metadata"].get("source", "").lower()
            text   = chunk.get("text", "").lower()

            if opponent_slugs:
                if not any(slug in source for slug in opponent_slugs):
                    continue
            if competition_kw:
                if competition_kw not in source and competition_kw not in text:
                    continue
            if player_names:
                if not any(p in text for p in player_names):
                    continue

            grouped[chunk["metadata"]["source"]].append(chunk)

        # 3. Sécurité : si le filtrage a été trop restrictif et qu'on n'a rien,
        # on fait un filtrage global sur l'intégralité du corpus en mémoire pour ne rater aucun match cible
        if not grouped and (opponent_slugs or player_names or competition_kw):
            logger.info("[TrendEngine] Filtrage sur le top Qdrant vide → repli sur le filtrage global en mémoire.")
            match_chunks = [c for c in self.chunks if c["metadata"].get("type_chunk") == "match"]
            for chunk in match_chunks:
                source = chunk["metadata"].get("source", "").lower()
                text   = chunk.get("text", "").lower()

                if opponent_slugs:
                    if not any(slug in source for slug in opponent_slugs):
                        continue
                if competition_kw:
                    if competition_kw not in source and competition_kw not in text:
                        continue
                if player_names:
                    if not any(p in text for p in player_names):
                        continue

                grouped[chunk["metadata"]["source"]].append(chunk)

        # 4. Si toujours vide (ex: requête générique sans filtre), on prend tout le top sémantique Qdrant
        if not grouped:
            logger.info("[TrendEngine] Aucun filtre strict ou aucun résultat → utilisation du top 150 sémantique Qdrant.")
            for chunk in retrieved_chunks[:150]:
                grouped[chunk["metadata"]["source"]].append(chunk)

        return dict(grouped)

    # ------------------------------------------------------------------
    # Construction du contexte structuré par match
    # ------------------------------------------------------------------
    def _build_structured_context(self, grouped: dict[str, list[dict]]) -> str:
        """
        Construit un bloc de contexte étanche par match, trié chronologiquement.

        Format :
          ══════════════════════════════
          MATCH : PSG vs Inter (2025-05-31) — Champions League
          ══════════════════════════════
          [chunk text 1]
          [chunk text 2]
          ...
        """
        if not grouped:
            return "Aucune donnée de match trouvée pour cette requête."

        parts: list[str] = []
        for source, chunks in sorted(grouped.items()):
            # Extraire un titre lisible depuis le premier chunk
            first_text = chunks[0].get("text", "")
            # Cherche le pattern "[Match: XXX vs YYY (score)]"
            match_title_m = re.search(r"\[Match: ([^\]]+)\]", first_text)
            match_title = match_title_m.group(1) if match_title_m else source

            # Trier les chunks par minute si possible
            def get_minute(c):
                m = re.search(r"(\d{1,3})ème minute", c.get("text", ""))
                return int(m.group(1)) if m else 999

            chunks_sorted = sorted(chunks, key=get_minute)

            header = (
                f"\n{'═' * 60}\n"
                f"MATCH : {match_title}\n"
                f"{'═' * 60}"
            )
            body = "\n\n".join(c["text"] for c in chunks_sorted)
            parts.append(f"{header}\n{body}")

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Génération LLM de la synthèse comparative
    # ------------------------------------------------------------------
    def _normalize_name(self, name: str) -> str:
        import unicodedata
        name = unicodedata.normalize('NFD', name)
        return "".join(c for c in name if unicodedata.category(c) != 'Mn').lower()

    def _get_sql_stats(self, player_names: list[str]) -> str:
        """
        Fait une requête d'agrégation (SUM, AVG) sur la table player_match_stats
        pour extraire les statistiques cumulées de la saison des joueurs concernés.
        """
        session = self.db_session_factory()
        try:
            # Récupérer toutes les lignes pour pouvoir filtrer de façon accent-insensitive en Python
            all_stats = session.query(PlayerMatchStats).all()
            if not all_stats:
                return "Aucune donnée statistique (SQL) disponible."

            # Organiser par joueur
            player_groups = defaultdict(list)
            for row in all_stats:
                player_groups[row.player_name].append(row)

            # Si on a des filtres, on filtre de manière insensible aux accents
            normalized_filters = [self._normalize_name(p) for p in player_names] if player_names else []

            sql_results = []
            for name, rows in player_groups.items():
                norm_name = self._normalize_name(name)
                # Vérifier si le joueur correspond à l'un des filtres
                if normalized_filters:
                    matches_filter = False
                    for f in normalized_filters:
                        if f in norm_name:
                            matches_filter = True
                            break
                    if not matches_filter:
                        continue

                # Faire les agrégations
                matches = len(rows)
                total_minutes = sum(r.minutes_played for r in rows)
                total_goals = sum(r.goals for r in rows)
                total_xg = sum(r.expected_goals for r in rows if r.expected_goals is not None)
                total_xa = sum(r.expected_assists for r in rows if r.expected_assists is not None)
                total_key_passes = sum(r.key_passes for r in rows if r.key_passes is not None)
                total_progressive_dribbles = sum(r.progressive_dribbles for r in rows if r.progressive_dribbles is not None)
                total_defensive_pressures = sum(r.defensive_pressures for r in rows if r.defensive_pressures is not None)

                sql_results.append({
                    "player_name": name,
                    "matches": matches,
                    "total_minutes": total_minutes,
                    "total_goals": total_goals,
                    "total_xg": total_xg,
                    "total_xa": total_xa,
                    "total_key_passes": total_key_passes,
                    "total_progressive_dribbles": total_progressive_dribbles,
                    "total_defensive_pressures": total_defensive_pressures,
                })

            if not sql_results:
                return "Aucune donnée statistique (SQL) disponible."

            sql_markdown = (
                "| Joueur | Matchs | Minutes | Buts | xG cumulé | xA cumulé | Passes Clés | Dribbles Prog. | Pressions Déf. |\n"
                "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n"
            )
            for r in sql_results:
                total_xg = r["total_xg"]
                total_xa = r["total_xa"]
                sql_markdown += f"| {r['player_name']} | {r['matches']} | {r['total_minutes']} | {r['total_goals']} | {total_xg:.2f} | {total_xa:.2f} | {r['total_key_passes']} | {r['total_progressive_dribbles']} | {r['total_defensive_pressures']} |\n"
            
            return sql_markdown
        except Exception as e:
            logger.error(f"[TrendEngine] Erreur SQL : {e}")
            return f"Erreur lors de la récupération des stats SQL : {e}"
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Génération LLM de la synthèse comparative
    # ------------------------------------------------------------------
    def _generate_synthesis(
        self,
        query: str,
        structured_context: str,
        sql_context: str,
        competitions: Optional[list[str]] = None,
    ) -> str:
        """
        Envoie le contexte multi-match structuré et les données SQL à Gemini pour synthèse.
        """
        comp_hint = ""
        if competitions:
            comp_hint = f"\nL'utilisateur s'intéresse particulièrement aux compétitions : {', '.join(competitions)}."

        system_prompt = f"""Tu es un ingénieur tactique d'élite travaillant pour un département analytique de football professionnel.
Tu reçois deux sources de données distinctes sur le Paris Saint-Germain :
1. Données Statistiques Réelles (SQL) : Statistiques cumulées froides de la saison issues de notre base de données relationnelle.
2. Contextes Isolés (Qdrant) : Comptes-rendus textuels et notes tactiques match par match.

Ta mission : produire une **synthèse comparative, analytique et évolutive** en répondant à la question posée.

Règles impératives de fusion hybride :
1. Utilise IMPÉRATIVEMENT les chiffres du SQL comme vérité absolue et incontestable pour tous les calculs statistiques et volumes de performances.
2. Utilise le contexte textuel de Qdrant pour expliquer le style de jeu, l'animation sur le terrain, le pressing et l'explication tactique.
3. Ne pas inventer de chiffres ni de faits qui ne figurent pas dans les données ci-dessous.
4. Organise ta réponse avec des sections Markdown claires (##, ###, tableaux).
5. Commence par présenter un tableau ou récapitulatif des données de performance réelles.
6. Réponds en français.{comp_hint}
7. Évaluation tactique globale des joueurs : Analyse l'apport collectif au-delà de la simple finition. Prends en compte l'impact global, la création d'occasions (passes clés, expected assists - xA, dribbles progressifs) et le pressing défensif (pressions défensives).

Données Statistiques Réelles (SQL) :
{sql_context}

Contextes Isolés (Qdrant) :
{structured_context}
"""

        if self.use_openrouter and self.openrouter_client:
            try:
                response = self.openrouter_client.chat.completions.create(
                    model="qwen/qwen-2.5-72b-instruct:free",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query},
                    ],
                    temperature=0.2,
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"[TrendEngine] Erreur OpenRouter Qwen : {e}")
                # En cas d'erreur de la version gratuite d'OpenRouter, on essaie la version payante standard
                try:
                    response = self.openrouter_client.chat.completions.create(
                        model="qwen/qwen-2.5-72b-instruct",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": query},
                        ],
                        temperature=0.2,
                    )
                    return response.choices[0].message.content
                except Exception as e2:
                    logger.error(f"[TrendEngine] Erreur OpenRouter Qwen (payant) : {e2}")
                    if not self.use_gemini and not self.use_openai:
                        raise e2

        if self.use_gemini and not self.use_openrouter:
            try:
                from google import genai
                from google.genai import types
                
                client = genai.Client(api_key=self.gemini_key)
                response = client.models.generate_content(
                    model="gemini-flash-latest",
                    contents=query,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.2,
                    )
                )
                return response.text
            except Exception as e:
                logger.error(f"[TrendEngine] Erreur Gemini : {e}")
                raise e

        if self.use_openai and self.openai_client and not self.use_gemini and not self.use_openrouter:
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query},
                    ],
                    temperature=0.2,
                    max_tokens=2000,
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"[TrendEngine] Erreur GPT-4o : {e}")
                return self._mock_synthesis(query, structured_context, sql_context)
        else:
            return self._mock_synthesis(query, structured_context, sql_context)

    def _mock_synthesis(self, query: str, context: str, sql_context: str) -> str:
        """Synthèse de démonstration quand OpenAI/Gemini ne sont pas disponibles."""
        match_count = context.count("MATCH :")
        return (
            f"## Synthèse Comparative Multi-Match (Mode Local)\n\n"
            f"**Requête :** {query}\n\n"
            f"**Matchs analysés (Qdrant) :** {match_count} match(s) isolé(s) dans la base de données.\n\n"
            f"### Données SQL Réelles\n"
            f"{sql_context}\n\n"
            f"### Contexte Qdrant récupéré\n"
            f"```\n{context[:800]}...\n```\n\n"
            f"> ℹ️ Synthèse indisponible en mode local (clé mock). "
            f"Configurez une clé API Google Gemini ou OpenAI dans `.env` pour la génération complète."
        )

    # ------------------------------------------------------------------
    # Point d'entrée principal
    # ------------------------------------------------------------------
    def analyze(
        self,
        query: str,
        competitions: Optional[list[str]] = None,
    ) -> dict:
        """
        Lance l'analyse de tendances hybride (SQL + Qdrant).
        """
        logger.info(f"[TrendEngine] Requête : {query!r}")

        # 1. Extraire les cibles
        targets = self._extract_targets(query)
        logger.info(f"[TrendEngine] Cibles extraites : {targets}")

        # 2. Filtrer et grouper les chunks (Qdrant)
        grouped = self._filter_chunks_by_targets(targets)
        total_chunks = sum(len(v) for v in grouped.values())
        logger.info(f"[TrendEngine] {len(grouped)} matchs isolés, {total_chunks} chunks.")

        # 3. Récupérer les stats cumulées (SQL)
        sql_context = self._get_sql_stats(targets["player_names"])

        # 4. Construire le contexte structuré
        structured_context = self._build_structured_context(grouped)

        # 5. Générer la synthèse
        synthesis = self._generate_synthesis(query, structured_context, sql_context, competitions)

        return {
            "synthesis": synthesis,
            "matches_analyzed": list(grouped.keys()),
            "chunks_used": total_chunks,
            "context_preview": structured_context[:500] + "..." if len(structured_context) > 500 else structured_context,
        }
