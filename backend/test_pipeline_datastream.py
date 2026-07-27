import os
import sys
import json
from pathlib import Path

# Configurer le sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.append(str(backend_dir))
sys.path.append(str(backend_dir.parent))

from app.core.config import settings
from ingestion.data_parsers.match_parser import MatchDataParser
from run_etl import run_etl_pipeline

def test_pipeline():
    print("==================================================")
    print("      TEST PIPELINE DATASTREAM : DEBUT            ")
    print("==================================================")
    
    # 1. Définition des chemins
    json_path = backend_dir / "data" / "raw_json" / "psg_om_stats.json"
    raw_dir = settings.get_raw_data_dir()
    
    print(f"JSON Source : {json_path}")
    print(f"Dossier Raw cible : {raw_dir}")
    
    # 2. Initialisation et exécution du parser
    parser = MatchDataParser()
    generated_md_path = parser.parse_and_save(str(json_path), raw_dir)
    
    # Vérification que le fichier MD existe
    if not os.path.exists(generated_md_path):
        print(f"[ERREUR] Le fichier Markdown n'a pas été généré à : {generated_md_path}")
        sys.exit(1)
        
    print(f"[SUCCÈS] Rapport Markdown généré.")
    
    # 3. Exécution du pipeline ETL
    print("\nLancement du pipeline ETL pour ingérer le nouveau match...")
    run_etl_pipeline()
    
    # 4. Validation des Chunks dans chunks.jsonl
    chunks_file = Path(settings.get_processed_data_dir()) / "chunks.jsonl"
    if not chunks_file.exists():
        print(f"[ERREUR] Le fichier chunks.jsonl est introuvable à : {chunks_file}")
        sys.exit(1)
        
    print(f"\nValidation du fichier de sortie : {chunks_file}")
    
    match_chunks = []
    with open(chunks_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            chunk_data = json.loads(line)
            if chunk_data.get("metadata", {}).get("source") == "match_2026_psg_om_01.md":
                match_chunks.append(chunk_data)
                
    print(f"Chunks trouvés pour match_2026_psg_om_01.md : {len(match_chunks)}")
    
    if not match_chunks:
        print("[ERREUR] Aucun chunk n'a été créé pour le match PSG vs OM.")
        sys.exit(1)
        
    # Validation du premier chunk
    first_chunk = match_chunks[0]
    print("\n--- Analyse du premier chunk généré ---")
    print(f"Texte : {first_chunk['text'][:150]}...")
    print(f"Source : {first_chunk['metadata']['source']}")
    print(f"Équipes détectées : {first_chunk['metadata']['equipes']}")
    print(f"Tags tactiques : {first_chunk['metadata']['tags_tactiques']}")
    print(f"Type de chunk : {first_chunk['metadata']['type_chunk']}")
    print(f"Période : {first_chunk['metadata']['periode']}")
    print(f"Intervalle : {first_chunk['metadata']['intervalle_temps']}")
    print("---------------------------------------")
    
    # Assertions de validation générales
    assert "PSG" in first_chunk['metadata']['equipes'], "PSG devrait être détecté dans les équipes."
    assert "OM" in first_chunk['metadata']['equipes'], "OM devrait être détecté dans les équipes."
    assert first_chunk['metadata']['type_chunk'] == "match", "Le type de chunk devrait être 'match'."
    
    # Validation de la chronologie et des intervalles de temps
    print("\n--- Validation Chronologique des Chunks ---")
    
    validation_checks = {
        "12": {"expected_periode": "1MT", "expected_intervalle": "0-15", "found": False},
        "34": {"expected_periode": "1MT", "expected_intervalle": "30-45", "found": False},
        "55": {"expected_periode": "2MT", "expected_intervalle": "45-60", "found": False},
        "72": {"expected_periode": "2MT", "expected_intervalle": "60-75", "found": False}
    }
    
    for chunk in match_chunks:
        text = chunk["text"]
        meta = chunk["metadata"]
        periode = meta.get("periode")
        intervalle = meta.get("intervalle_temps")
        
        print(f"Chunk ID: {meta['id'][:8]} | Période: {periode:<10} | Intervalle: {intervalle:<10} | Type: {meta['type_chunk']}")
        
        for key, expected in validation_checks.items():
            # Chercher le chiffre de la minute entouré de délimiteurs de mots ou de texte pour éviter les collisions partielles
            if f" {key} " in text or f" {key}e" in text or f" {key}è" in text or f"({key})" in text:
                expected["found"] = True
                assert periode == expected["expected_periode"], f"Attendu {expected['expected_periode']} pour {key}, obtenu {periode}"
                assert intervalle == expected["expected_intervalle"], f"Attendu {expected['expected_intervalle']} pour {key}, obtenu {intervalle}"
                print(f"  [OK] Validation chronologique réussie pour l'événement minute {key}")
                
    # S'assurer que tous les événements clés ont été trouvés et vérifiés
    for key, expected in validation_checks.items():
        assert expected["found"], f"L'événement de la minute '{key}' n'a pas été trouvé dans les chunks générés."
        
    print("\n==================================================")
    print("      TEST PIPELINE DATASTREAM : SUCCÈS           ")
    print("==================================================")

if __name__ == "__main__":
    test_pipeline()
