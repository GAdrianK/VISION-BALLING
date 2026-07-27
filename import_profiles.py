import os
import sqlite3
import pandas as pd
from pathlib import Path

def main():
    base_dir = Path(__file__).resolve().parent
    db_path = base_dir / "backend" / "data" / "football_iq.db"
    
    if not db_path.exists():
        print(f"❌ Base de données introuvable : {db_path}")
        return
        
    archive_dir = Path("/home/adriano/Documents/PROJET PERSO/football-rag-system-archive")
    profiles_path = archive_dir / "all_player_profiles.csv"
    stats_path = archive_dir / "all_player_stats.csv"
    
    if not profiles_path.exists() or not stats_path.exists():
        print("❌ Fichiers CSV introuvables dans l'archive.")
        return
        
    print("📖 Chargement des fichiers CSV de l'archive...")
    df_profiles = pd.read_csv(profiles_path)
    df_stats = pd.read_csv(stats_path)
    
    print(f"Loaded {len(df_profiles)} profiles and {len(df_stats)} player statistics.")
    
    # Merge datasets on player_id and league
    df_merged = pd.merge(
        df_profiles[['player_id', 'name', 'position', 'market_value', 'league']], 
        df_stats[['player_id', 'rating']], 
        on='player_id', 
        how='left'
    )
    
    print(f"Merged dataset contains {len(df_merged)} entries.")
    
    # Connect to SQLite
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Create player_profiles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS player_profiles (
            player_id INTEGER PRIMARY KEY,
            player_name TEXT UNIQUE,
            position TEXT,
            market_value REAL,
            rating REAL,
            league TEXT
        )
    """)
    conn.commit()
    
    print("⚡ Insertion des profils dans la table player_profiles...")
    inserted_count = 0
    updated_count = 0
    
    for _, row in df_merged.iterrows():
        player_id = int(row['player_id'])
        player_name = row['name']
        position = row['position']
        
        # Parse market value and rating, handling NaNs
        market_value = float(row['market_value']) if pd.notna(row['market_value']) else None
        rating = float(row['rating']) if pd.notna(row['rating']) else None
        league = row['league']
        
        # Clean player name
        if pd.isna(player_name):
            continue
        player_name = str(player_name).strip()
        
        try:
            cursor.execute("""
                INSERT INTO player_profiles (player_id, player_name, position, market_value, rating, league)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (player_id, player_name, position, market_value, rating, league))
            inserted_count += 1
        except sqlite3.IntegrityError:
            # Player already exists, update profile details
            cursor.execute("""
                UPDATE player_profiles
                SET position=?, market_value=?, rating=?, league=?
                WHERE player_id=? OR player_name=?
            """, (position, market_value, rating, league, player_id, player_name))
            updated_count += 1
            
    conn.commit()
    
    # Double check database row count
    cursor.execute("SELECT COUNT(*) FROM player_profiles")
    db_count = cursor.fetchone()[0]
    conn.close()
    
    print(f"🎉 Importation terminée ! {inserted_count} profils insérés, {updated_count} profils mis à jour.")
    print(f"📊 La table player_profiles contient maintenant {db_count} enregistrements uniques.")

if __name__ == "__main__":
    main()
