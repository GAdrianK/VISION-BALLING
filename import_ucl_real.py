import os
import sqlite3
import pandas as pd
from pathlib import Path

# Set soccerdata directory
os.environ["SOCCERDATA_DIR"] = "/home/adriano/Documents/PROJET PERSO/IA FOOT/backend/data/soccerdata"

import soccerdata as sd

def import_real_ucl():
    db_path = Path("/home/adriano/Documents/PROJET PERSO/IA FOOT/backend/data/football_iq.db")
    print(f"⏳ Connexion à la base de données : {db_path}...")
    if not db_path.exists():
        print(f"❌ Erreur : La base de données n'existe pas dans {db_path}")
        return
        
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    print("⏳ Téléchargement des statistiques réelles LDC 24-25 et 25-26 depuis FBref...")
    try:
        fbref = sd.FBref(leagues="UEFA-Champions League", seasons=["2024-25", "2025-26"])
        df = fbref.read_player_season_stats(stat_type="standard")
        print(f"✅ Données récupérées avec succès. Dimensions : {df.shape}")
    except Exception as e:
        print(f"❌ Erreur lors du téléchargement FBref via soccerdata : {str(e)}")
        conn.close()
        return

    # Reset index to easily access columns
    df_flat = df.reset_index()

    # Nettoyage des anciennes lignes de LDC simulées
    print("🧹 Nettoyage des anciennes statistiques LDC simulées dans la base de données...")
    cursor.execute("""
        DELETE FROM player_match_stats 
        WHERE match_id IN ('season_2024_2025_cl', 'season_2025_2026_cl')
    """)
    conn.commit()
    print("✅ Anciennes lignes supprimées.")

    print("⚽ Début de l'injection des données réelles...")
    rows_inserted = 0
    errors = 0

    for _, row in df_flat.iterrows():
        # Get raw fields
        try:
            player_name = row[('player', '')]
            team_name = row[('team', '')]
            season_code = row[('season', '')]
            
            # Map season to match_id
            if season_code == "2425":
                match_id = "season_2024_2025_cl"
            elif season_code == "2526":
                match_id = "season_2025_2026_cl"
            else:
                continue

            # Read playing stats (with NaN protection)
            minutes = row[('Playing Time', 'Min')]
            minutes = int(minutes) if pd.notna(minutes) else 0
            
            goals = row[('Performance', 'Gls')]
            goals = int(goals) if pd.notna(goals) else 0

            assists = row[('Performance', 'Ast')]
            assists = int(assists) if pd.notna(assists) else 0

            # Since we want ONLY real stats, advanced metrics are set to 0.0/0
            # as tournament player overview tables do not contain them.
            xg = 0.0
            xa = 0.0
            key_passes = 0
            dribbles = 0
            pressures = 0

            # Insert into database
            cursor.execute("""
                INSERT INTO player_match_stats 
                (match_id, player_name, minutes_played, goals, expected_goals, expected_assists, key_passes, progressive_dribbles, defensive_pressures, competition, team_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (match_id, player_name, minutes, goals, xg, xa, key_passes, dribbles, pressures, 'Champions League', team_name))
            rows_inserted += 1

        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"⚠️ Erreur sur une ligne : {str(e)}")

    conn.commit()
    print(f"\n🎉 Opération terminée !")
    print(f"✅ {rows_inserted} profils de joueurs réels importés avec succès.")
    if errors > 0:
        print(f"⚠️ Nombre total de lignes en erreur : {errors}")

    # Print summary of injected rows per match_id
    cursor.execute("""
        SELECT match_id, count(*), sum(goals) 
        FROM player_match_stats 
        WHERE match_id IN ('season_2024_2025_cl', 'season_2025_2026_cl')
        GROUP BY match_id
    """)
    print("\nRécapitulatif LDC dans la base de données :")
    for row in cursor.fetchall():
        print(f"- {row[0]} : {row[1]} joueurs, {row[2]} buts au total.")

    conn.close()

if __name__ == "__main__":
    import_real_ucl()
