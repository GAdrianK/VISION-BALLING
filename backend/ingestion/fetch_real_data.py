import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

def fetch_real_data():
    print("==================================================")
    print("      CONSTITUTION DE LA SAISON COMPLÈTE PSG      ")
    print("==================================================")
    
    raw_dir = os.path.join(backend_dir, "data", "psg_season_raw")
    os.makedirs(raw_dir, exist_ok=True)
    
    # List actual txt files in the directory
    real_files = [f for f in os.listdir(raw_dir) if f.endswith(".txt")]
    
    print(f"Dossier source de masse : {raw_dir}")
    print(f"Fichiers réels trouvés : {len(real_files)}")
    for f in real_files:
        print(f"  [+] {f}")
        
    if len(real_files) == 0:
        print("\n[INFO] Aucun résumé réel de match trouvé dans psg_season_raw.")
        print("Veuillez déposer vos résumés textuels réels (fichiers .txt) dans ce dossier.")
        print("Le pipeline les traitera lors du prochain lancement de run_psg_campaign.py.")
        
    print("==================================================")
    return len(real_files)

if __name__ == "__main__":
    fetch_real_data()
