import io
import requests
import pandas as pd
from sqlalchemy.orm import Session
from app.models.player_stats import PlayerMatchStats

class FootballScraperEngine:
    def __init__(self):
        # Un User-Agent complet et des en-têtes réalistes sont obligatoires
        # pour éviter d'être bloqué par le rate-limiting/anti-bot de FBref (Code 403)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0"
        }

    def fetch_and_save_match_stats(self, url: str, match_id: str, db: Session):
        """
        Scrape les tableaux HTML d'une page de statistiques (URL ou fichier local) et les insère en base de données.
        """
        try:
            # 1. Récupération du contenu HTML (URL ou fichier local)
            if url.startswith("http://") or url.startswith("https://"):
                response = requests.get(url, headers=self.headers)
                if response.status_code != 200:
                    raise Exception(f"Impossible d'accéder à la page : Code {response.status_code}")
                html_content = response.text
            else:
                # Lecture d'un fichier local (utile pour bypass Cloudflare lors des tests)
                clean_path = url.replace("file://", "")
                with open(clean_path, "r", encoding="utf-8") as f:
                    html_content = f.read()

            # 2. Utilisation de Pandas pour extraire TOUS les tableaux d'un coup
            all_tables = pd.read_html(io.StringIO(html_content))
            
            # Le premier tableau d'un rapport de match FBref contient généralement 
            # les statistiques globales de l'équipe à domicile ou à l'extérieur
            summary_table = all_tables[0]
            
            # 3. Boucle de parsing (analyse ligne par ligne) des joueurs
            for index, row in summary_table.iterrows():
                # On ignore les lignes de sous-totaux ou les lignes vides
                # Remarque : FBref utilise des MultiIndex ou des index de colonnes simples.
                # Pour s'assurer de récupérer la colonne 'Player', on gère différents formats de colonnes.
                player_col = None
                for col in summary_table.columns:
                    col_name = col[-1] if isinstance(col, tuple) else col
                    if col_name == 'Player':
                        player_col = col
                        break
                
                if player_col is None:
                    continue
                
                player_name = row[player_col]
                if pd.isna(player_name) or player_name in ['Player', 'Squad Totals']:
                    continue
                
                # Helper pour récupérer une valeur de colonne indépendamment du fait qu'elle soit MultiIndex ou non
                def get_val(col_name, default=0):
                    target_col = None
                    for col in summary_table.columns:
                        curr_name = col[-1] if isinstance(col, tuple) else col
                        if curr_name == col_name:
                            target_col = col
                            break
                    if target_col is None:
                        return default
                    val = row[target_col]
                    return val if not pd.isna(val) else default

                # Nettoyage et conversion des données avec des valeurs par défaut à 0
                stats_data = PlayerMatchStats(
                    match_id=match_id,
                    player_name=player_name,
                    minutes_played=int(get_val('Min', 0)),
                    goals=int(get_val('Gls', 0)),
                    expected_goals=float(get_val('xG', 0.0)),
                    expected_assists=float(get_val('xA', 0.0)),
                    key_passes=int(get_val('KP', 0)),
                    progressive_dribbles=int(get_val('Prog', 0)),
                    defensive_pressures=int(get_val('Press', 0))
                )
                
                # 4. Sauvegarde dans la base SQLite via SQLAlchemy
                # On vérifie si la stat existe déjà pour éviter les doublons
                exists = db.query(PlayerMatchStats).filter_by(match_id=match_id, player_name=player_name).first()
                if not exists:
                    db.add(stats_data)
            
            db.commit()
            return f"Succès : Match {match_id} ingéré avec succès."
            
        except Exception as e:
            db.rollback()
            return f"Erreur lors de l'extraction : {str(e)}"
