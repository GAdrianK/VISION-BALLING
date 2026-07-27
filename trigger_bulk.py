import requests
import json

# L'URL de ton endpoint FastAPI tout neuf
API_URL = "http://127.0.0.1:8000/api/bulk-scrape"

# Liste de matchs à injecter en masse (Moteur Hybride V2)
matchs_a_ingerer = [
    {"match_id": "2024_08_16_le_havre_psg", "url": "https://fbref.com/en/matches/12345678/Le-Havre-Paris-Saint-Germain-Match-Report"},
    {"match_id": "2024_08_23_psg_montpellier", "url": "https://fbref.com/en/matches/23456789/Paris-Saint-Germain-Montpellier-Match-Report"},
    {"match_id": "2024_09_01_lille_psg", "url": "https://fbref.com/en/matches/34567890/Lille-Paris-Saint-Germain-Match-Report"},
    {"match_id": "2024_09_14_psg_brest", "url": "https://fbref.com/en/matches/45678901/Paris-Saint-Germain-Brest-Match-Report"},
    {"match_id": "2024_09_17_psg_atalanta", "url": "https://fbref.com/en/matches/56789012/Paris-Saint-Germain-Atalanta-Match-Report"},
    {"match_id": "2024_10_01_barcelone_psg", "url": "https://fbref.com/en/matches/67890123/Barcelona-Paris-Saint-Germain-Match-Report"},
    {"match_id": "2024_10_27_marseille_psg", "url": "https://fbref.com/en/matches/78901234/Marseille-Paris-Saint-Germain-Match-Report"},
    {"match_id": "2024_11_04_psg_bayern", "url": "https://fbref.com/en/matches/89012345/Paris-Saint-Germain-Bayern-Munich-Match-Report"},
    {"match_id": "2025_01_22_psg_mancity", "url": "https://fbref.com/en/matches/90123456/Paris-Saint-Germain-Manchester-City-Match-Report"},
    {"match_id": "2025_01_29_stuttgart_psg", "url": "https://fbref.com/en/matches/01234567/Stuttgart-Paris-Saint-Germain-Match-Report"},
    {"match_id": "2025_02_17_monaco_psg", "url": "https://fbref.com/en/matches/a1234567/Monaco-Paris-Saint-Germain-Match-Report"},
    {"match_id": "2025_03_11_psg_chelsea", "url": "https://fbref.com/en/matches/b1234567/Paris-Saint-Germain-Chelsea-Match-Report"}
]

print(f"🚀 Envoi de {len(matchs_a_ingerer)} matchs à l'orchestrateur asynchrone...")

try:
    response = requests.post(
        API_URL, 
        json={"matches": matchs_a_ingerer},
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        print("✅ Réponse de l'API : Ingestion acceptée et lancée en tâche de fond !")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    else:
        print(f"❌ Échec de la requête. Code : {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"🚨 Erreur de connexion au serveur FastAPI : {str(e)}")
