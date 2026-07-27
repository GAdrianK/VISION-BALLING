"""
run_psg_campaign.py
====================
Orchestrateur principal du pipeline d'ingestion de données de match du PSG.

Flux d'exécution :
  1. Purge de l'index existant (Qdrant + SQLite + chunks JSONL)
  2. Appel API-Sports pour télécharger les vrais matchs terminés du PSG 2025-2026
  3. Conversion de chaque JSON en prose tactique Markdown (via MatchDataParser)
  4. ETL : découpage en chunks temporels qualifiés
  5. Indexation vectorielle incrémentale (Qdrant + SQLite parent-child)
"""

import os
import sys
from pathlib import Path

# Add backend directory to sys.path for absolute imports
backend_dir = Path(__file__).resolve().parent
sys.path.append(str(backend_dir))

from app.core.config import settings
from database.clear_fake_data import clear_all_data
from ingestion.api_football_client import APIFootballClient
from ingestion.data_parsers.match_parser import MatchDataParser
from run_etl import run_etl_pipeline
from database.indexer import run_indexing

# Nombre maximum de matchs à traiter lors de ce run (contrôle du quota API)
MATCH_FETCH_LIMIT = 10


def run_campaign():
    print("==================================================")
    print("      FOOTBALL IQ - PSG REAL DATA CAMPAIGN        ")
    print("==================================================")

    # --- ÉTAPE 0 : Purge de l'index existant ---
    print("\n--- [ÉTAPE 0] Purge de l'index (Qdrant + SQLite + Chunks) ---")
    clear_all_data(confirm=True)  # confirm=True pour exécution non-interactive

    # --- Configuration des répertoires ---
    raw_json_dir = os.path.join(backend_dir, "data", "raw_json")
    raw_md_dir = settings.get_raw_data_dir()

    print(f"\nDossier JSON intermédiaire : {raw_json_dir}")
    print(f"Dossier Markdown final ETL : {raw_md_dir}\n")

    os.makedirs(raw_json_dir, exist_ok=True)
    os.makedirs(raw_md_dir, exist_ok=True)

    # --- ÉTAPE 1 : Téléchargement des vrais matchs via API-Sports ---
    print(f"\n--- [ÉTAPE 1] Téléchargement des matchs PSG via API-Sports (limite={MATCH_FETCH_LIMIT}) ---")
    try:
        client = APIFootballClient()
        generated_jsons = client.save_all_finished_matches(raw_json_dir, limit=MATCH_FETCH_LIMIT)
    except ValueError as e:
        print(f"\n[ERREUR CRITIQUE] {e}")
        print("Vérifiez que APISPORTS_KEY est défini dans backend/.env")
        return
    except Exception as e:
        print(f"\n[ERREUR] Échec de la connexion à API-Sports : {e}")
        print("Vérifiez votre connexion internet et votre clé API.")
        return

    if not generated_jsons:
        print("\n[INFO] Aucun match terminé disponible depuis l'API.")
        print("Les documents tactiques de la knowledge base seront quand même ré-indexés.")

    # Afficher le récapitulatif des matchs téléchargés
    if generated_jsons:
        print(f"\n{'='*50}")
        print(f"  {len(generated_jsons)} VRAIS MATCHS TÉLÉCHARGÉS DEPUIS API-SPORTS")
        print(f"{'='*50}")
        import json
        for path in generated_jsons:
            with open(path) as f:
                d = json.load(f)
            meta = d["meta"]
            print(
                f"  ✓ {meta['competition']:30s} | {meta['date']} | "
                f"{meta['home_team']} {meta['score_home']}-{meta['score_away']} {meta['away_team']}"
            )
        print(f"{'='*50}\n")

    # --- ÉTAPE 2 : Conversion JSON → Prose Markdown ---
    print("\n--- [ÉTAPE 2] Conversion JSON vers Prose Tactique (Markdown) ---")
    match_parser = MatchDataParser()
    generated_markdowns = []

    for json_path in generated_jsons:
        filename = os.path.basename(json_path)
        try:
            md_path = match_parser.parse_and_save(json_path, raw_md_dir)
            generated_markdowns.append(md_path)
            print(f"  [OK] {os.path.basename(md_path)}")
        except Exception as e:
            print(f"  [ERROR] Conversion échouée pour {filename} : {e}")

    print(f"\n-> {len(generated_markdowns)} fichiers Markdown insérés dans le dossier ETL.")

    # --- ÉTAPE 3 : ETL de chunking temporel ---
    print("\n--- [ÉTAPE 3] Lancement de l'ETL de Chunking ---")
    run_etl_pipeline()

    # --- ÉTAPE 4 : Indexation vectorielle ---
    print("\n--- [ÉTAPE 4] Lancement de l'Indexation & Vectorisation ---")
    run_indexing()

    # --- Bilan final ---
    print("\n==================================================")
    print("     CAMPAGNE D'INGESTION TERMINÉE AVEC SUCCÈS    ")
    print("==================================================")
    print(f"  Vrais matchs ingérés  : {len(generated_markdowns)}")
    print(f"  Source               : API-Sports (v3.football.api-sports.io)")
    print(f"  Équipe               : PSG (ID={85}, Saison=2025-2026)")
    print("Les données sont prêtes à être interrogées.")
    print("==================================================")


if __name__ == "__main__":
    run_campaign()
