import os
import requests
from pathlib import Path

# Configuration des chemins et de l'API
TARGET_DIR = Path("/home/adriano/Documents/PROJET PERSO/IA FOOT/backend/data/html_matches")
API_URL = "http://127.0.0.1:8000/api/bulk-scrape"

if not TARGET_DIR.exists():
    print(f"🚨 Erreur : Le dossier {TARGET_DIR} n'existe pas. Crée-le et places-y tes fichiers HTML.")
    exit()

# Scan du dossier pour récupérer tous les fichiers HTML
html_files = list(TARGET_DIR.glob("*.html"))
print(f"🔍 {len(html_files)} fichiers HTML détectés dans {TARGET_DIR}")

matchs_a_ingerer = []

for file_path in html_files:
    # On crée un match_id propre basé sur le nom du fichier (ex: "psg_lyon.html" -> "psg_lyon")
    match_id = file_path.stem.lower().replace("-", "_").replace(" ", "_")
    
    # On récupère le chemin absolu du fichier pour que le backend le trouve sans ambiguïté
    absolute_path = str(file_path.resolve())
    
    matchs_a_ingerer.append({
        "match_id": match_id,
        "url": absolute_path  # L'engine sait détecter si c'est un fichier local ou une URL !
    })

if not matchs_a_ingerer:
    print("⚠️ Aucun fichier HTML trouvé. Fin du script.")
    exit()

# Envoi de la charge utile (payload) au format attendu par FastAPI
payload = {"matches": matchs_a_ingerer}

print(f"🚀 Envoi groupé de {len(matchs_a_ingerer)} matchs locaux à l'API...")

try:
    response = requests.post(API_URL, json=payload)
    if response.status_code == 200:
        print("✅ Réponse de l'API : Ingestion locale lancée avec succès en tâche de fond !")
        print(response.json())
    else:
        print(f"❌ Échec de la requête : Code {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"🚨 Impossible de joindre le serveur FastAPI : {str(e)}")
