"""
api_football_client.py
=======================
Client officiel pour l'API API-Sports (v3.football.api-sports.io).
Récupère les vrais matchs du PSG pour la saison 2025-2026, leurs statistiques
et leurs événements, puis les convertit au format JSON interne du pipeline ETL.
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

import requests

backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from app.core.config import settings

logger = logging.getLogger(__name__)

# Constantes
PSG_TEAM_ID = 85
# NOTE: Le plan gratuit API-Sports donne accès aux saisons 2022-2024 uniquement.
# La saison 2025-2026 nécessite un abonnement payant.
SEASON = 2024
BASE_URL = "https://v3.football.api-sports.io"


class APIFootballClient:
    """
    Client pour v3.football.api-sports.io.

    Méthodes principales :
    - fetch_psg_season_fixtures()  : récupère les matchs de la saison PSG
    - fetch_match_stats(fixture_id): statistiques d'équipe pour un match
    - fetch_match_events(fixture_id): événements (buts, cartons, remplacements)
    - build_match_json(fixture, stats, events): construit le JSON interne
    - save_all_finished_matches(output_dir, limit): pipeline complet
    """

    def __init__(self):
        self.api_key = settings.APISPORTS_KEY
        if not self.api_key:
            raise ValueError(
                "La clé APISPORTS_KEY est manquante dans le fichier .env. "
                "Ajoutez APISPORTS_KEY=<votre_clé> dans backend/.env"
            )
        self.session = requests.Session()
        self.session.headers.update({
            "x-apisports-key": self.api_key,
            "Accept": "application/json",
        })

    def _get(self, endpoint: str, params: dict) -> dict:
        """Appel GET authentifié avec gestion d'erreur."""
        url = f"{BASE_URL}/{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            # L'API retourne toujours {"errors": [], "response": [...]}
            errors = data.get("errors", {})
            if errors:
                raise RuntimeError(f"Erreur API-Sports : {errors}")
            return data
        except requests.RequestException as e:
            logger.error(f"[APIFootball] Erreur réseau sur {url} : {e}")
            raise

    def fetch_psg_season_fixtures(self) -> list[dict]:
        """
        Récupère tous les matchs joués par le PSG (team=85) en saison 2025.

        Returns:
            Liste des fixtures (matchs) au format API-Sports.
        """
        print(f"[API-Sports] Récupération des matchs du PSG (team={PSG_TEAM_ID}, season={SEASON})...")
        data = self._get("fixtures", {"team": PSG_TEAM_ID, "season": SEASON})
        fixtures = data.get("response", [])
        print(f"[API-Sports] {len(fixtures)} matchs trouvés au total.")
        return fixtures

    def fetch_match_stats(self, fixture_id: int) -> list[dict]:
        """
        Récupère les statistiques d'équipe pour un match donné.

        Args:
            fixture_id: ID du match dans l'API.

        Returns:
            Liste de dicts [{team: {...}, statistics: [...]}, ...]
        """
        data = self._get("fixtures/statistics", {"fixture": fixture_id})
        return data.get("response", [])

    def fetch_match_events(self, fixture_id: int) -> list[dict]:
        """
        Récupère les événements clés (buts, cartons, remplacements) pour un match.

        Args:
            fixture_id: ID du match dans l'API.

        Returns:
            Liste d'événements [{time: {elapsed}, type, detail, player, ...}, ...]
        """
        data = self._get("fixtures/events", {"fixture": fixture_id})
        return data.get("response", [])

    @staticmethod
    def _extract_stat(stats_list: list[dict], stat_name: str, default=0):
        """Extrait une valeur de statistique par son nom."""
        for s in stats_list:
            if s.get("type") == stat_name:
                val = s.get("value")
                if val is None:
                    return default
                # Nettoyer les valeurs de type "55%" -> 55.0
                if isinstance(val, str) and val.endswith("%"):
                    try:
                        return float(val.replace("%", "").strip())
                    except ValueError:
                        return default
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return default
        return default

    def build_match_json(
        self,
        fixture: dict,
        stats: list[dict],
        events: list[dict],
    ) -> dict:
        """
        Construit le JSON interne du pipeline ETL à partir des données API-Sports.

        Le format produit est compatible avec MatchDataParser._generate_via_template().
        """
        fix = fixture["fixture"]
        teams = fixture["teams"]
        goals = fixture["goals"]
        league = fixture["league"]

        home_name = teams["home"]["name"]
        away_name = teams["away"]["name"]
        score_home = goals["home"] or 0
        score_away = goals["away"] or 0
        match_date = fix["date"][:10]  # Format YYYY-MM-DD
        fixture_id = fix["id"]

        # Construire un ID match déterministe
        date_slug = match_date.replace("-", "_")
        home_slug = home_name.lower().replace(" ", "_")[:12]
        away_slug = away_name.lower().replace(" ", "_")[:12]
        match_id = f"{date_slug}_{home_slug}_{away_slug}_01"

        # --- Statistiques par équipe ---
        team_stats = {}
        for team_block in stats:
            t_name = team_block["team"]["name"]
            s = team_block.get("statistics", [])

            possession_raw = self._extract_stat(s, "Ball Possession", "50%")
            if isinstance(possession_raw, str) and "%" in possession_raw:
                possession = float(possession_raw.replace("%", "").strip())
            else:
                possession = float(possession_raw)

            team_stats[t_name] = {
                "possession_pct": possession,
                "passes_completed": int(self._extract_stat(s, "Passes accurate", 0)),
                "passes_progressive": int(self._extract_stat(s, "Total passes", 0)),
                "shots": int(self._extract_stat(s, "Total Shots", 0)),
                "shots_on_target": int(self._extract_stat(s, "Shots on Goal", 0)),
                "xg": round(self._extract_stat(s, "expected_goals", 0.0), 2),
                "ppda": 0.0,        # Non fourni par l'API, conservé à 0 pour transparence
                "bloc_style": "N/A" # Non fourni par l'API
            }

        # Si pas de stats disponibles, créer des entrées vides mais honnêtes
        for team_name in [home_name, away_name]:
            if team_name not in team_stats:
                team_stats[team_name] = {
                    "possession_pct": 0.0,
                    "passes_completed": 0,
                    "passes_progressive": 0,
                    "shots": 0,
                    "shots_on_target": 0,
                    "xg": 0.0,
                    "ppda": 0.0,
                    "bloc_style": "N/A"
                }

        # --- Événements clés ---
        key_events = []
        for ev in events:
            minute = ev.get("time", {}).get("elapsed", 0)
            extra = ev.get("time", {}).get("extra") or 0
            total_minute = minute + extra

            ev_type = ev.get("type", "")
            ev_detail = ev.get("detail", "")
            player_name = ev.get("player", {}).get("name", "Joueur inconnu")
            team_name = ev.get("team", {}).get("name", "")

            # Construire une description textuelle factuelle
            if ev_type == "Goal":
                description = (
                    f"But de {player_name} ({team_name}). {ev_detail}. "
                    f"Score : {score_home}-{score_away} en faveur de {home_name if score_home > score_away else away_name}."
                )
            elif ev_type == "subst":
                assist_name = ev.get("assist", {}).get("name", "")
                description = f"Remplacement ({team_name}) : {player_name} sort, {assist_name} entre."
            elif ev_type == "Card":
                description = f"Carton {ev_detail.lower()} pour {player_name} ({team_name})."
            elif ev_type == "Var":
                description = f"VAR ({team_name}) : {ev_detail} impliquant {player_name}."
            else:
                description = f"Événement ({ev_type}) : {ev_detail} — {player_name} ({team_name})."

            key_events.append({
                "minute": total_minute,
                "team": team_name,
                "type": ev_type.lower(),
                "description": description
            })

        return {
            "match_id": match_id,
            "api_fixture_id": fixture_id,
            "meta": {
                "competition": league["name"],
                "saison": f"{SEASON}-{SEASON + 1}",
                "date": match_date,
                "home_team": home_name,
                "away_team": away_name,
                "score_home": score_home,
                "score_away": score_away,
            },
            "team_stats": team_stats,
            "key_events": key_events,
        }

    def save_all_finished_matches(
        self,
        output_dir: str,
        limit: int = 10,
    ) -> list[str]:
        """
        Télécharge les matchs terminés du PSG, les formate et les enregistre en JSON.

        Args:
            output_dir: Répertoire de sortie pour les fichiers JSON.
            limit: Nombre maximum de matchs à traiter (pour contrôler le quota API).

        Returns:
            Liste des chemins des fichiers JSON créés.
        """
        os.makedirs(output_dir, exist_ok=True)
        fixtures = self.fetch_psg_season_fixtures()

        # Filtrer les matchs terminés
        finished = [
            f for f in fixtures
            if f.get("fixture", {}).get("status", {}).get("short") == "FT"
        ]
        print(f"[API-Sports] {len(finished)} matchs terminés (FT) trouvés.")

        if not finished:
            print("[API-Sports] Aucun match terminé disponible pour cette saison.")
            return []

        # Limiter le nombre de matchs à traiter
        to_process = finished[:limit]
        print(f"[API-Sports] Traitement de {len(to_process)} matchs (limite={limit}).")

        saved_paths = []
        for i, fixture in enumerate(to_process, 1):
            fixture_id = fixture["fixture"]["id"]
            home = fixture["teams"]["home"]["name"]
            away = fixture["teams"]["away"]["name"]
            score_h = fixture["goals"]["home"]
            score_a = fixture["goals"]["away"]
            date = fixture["fixture"]["date"][:10]
            competition = fixture["league"]["name"]

            print(f"\n  [{i}/{len(to_process)}] {competition} | {date} | {home} {score_h}-{score_a} {away}")

            try:
                # Respecter le quota : 1 requête / seconde (plan gratuit = 100 req/jour)
                time.sleep(1.2)
                stats = self.fetch_match_stats(fixture_id)
                time.sleep(1.2)
                events = self.fetch_match_events(fixture_id)

                match_json = self.build_match_json(fixture, stats, events)

                # Sauvegarder
                output_path = os.path.join(output_dir, f"match_{match_json['match_id']}.json")
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(match_json, f, ensure_ascii=False, indent=2)
                print(f"    [✓] Sauvegardé : {os.path.basename(output_path)}")
                saved_paths.append(output_path)

            except Exception as e:
                print(f"    [ERROR] Impossible de traiter le match {fixture_id} : {e}")
                logger.error(f"Échec traitement fixture {fixture_id} : {e}", exc_info=True)

        print(f"\n[API-Sports] {len(saved_paths)}/{len(to_process)} fichiers JSON sauvegardés dans {output_dir}")
        return saved_paths


if __name__ == "__main__":
    import sys
    client = APIFootballClient()
    raw_json_dir = os.path.join(backend_dir, "data", "raw_json")
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    client.save_all_finished_matches(raw_json_dir, limit=limit)
