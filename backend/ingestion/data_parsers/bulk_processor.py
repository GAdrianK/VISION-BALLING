import os
import json
import re
import sys
from pathlib import Path
from typing import List, Dict
from pydantic import BaseModel, Field

# Add backend directory to sys.path for settings and absolute imports
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(backend_dir))

from openai import OpenAI
from app.core.config import settings

# =====================================================================
# Pydantic Schemas matching the standard raw JSON schema
# =====================================================================
class TeamStats(BaseModel):
    possession_pct: int = Field(..., description="Percentage of possession (e.g. 58)")
    passes_completed: int = Field(..., description="Number of completed passes")
    passes_progressive: int = Field(..., description="Number of progressive passes")
    shots: int = Field(..., description="Number of shots")
    shots_on_target: int = Field(..., description="Number of shots on target")
    xg: float = Field(..., description="Expected Goals (xG)")
    ppda: float = Field(..., description="PPDA metric (Passes Allowed per Defensive Action)")
    bloc_style: str = Field(..., description="Style of defensive block (e.g. high-block, low-block, medium-block)")

class MatchMeta(BaseModel):
    competition: str = Field(..., description="Competition name (e.g. Ligue 1)")
    saison: str = Field(..., description="Season (e.g. 2025-2026)")
    date: str = Field(..., description="Date of the match (YYYY-MM-DD)")
    home_team: str = Field(..., description="Home team name")
    away_team: str = Field(..., description="Away team name")
    score_home: int = Field(..., description="Score of the home team")
    score_away: int = Field(..., description="Score of the away team")

class KeyEvent(BaseModel):
    minute: int = Field(..., description="Minute of the event (1-90)")
    team: str = Field(..., description="Team associated with the event")
    type: str = Field(..., description="Type of event: goal, tactical_change, big_chance, etc.")
    description: str = Field(..., description="Detailed tactical description of the event")

class MatchData(BaseModel):
    match_id: str = Field(..., description="Unique match ID (e.g. 2026_psg_lens_01)")
    meta: MatchMeta
    team_stats: Dict[str, TeamStats] = Field(..., description="Keyed by team name (home_team and away_team keys)")
    key_events: List[KeyEvent]

# =====================================================================
# Fallback local regex parser
# =====================================================================
def local_regex_parse(text: str, filename: str) -> dict:
    meta = {
        "competition": "Ligue 1",
        "saison": "2025-2026",
        "date": "2026-06-09",
        "home_team": "PSG",
        "away_team": "OM",
        "score_home": 0,
        "score_away": 0
    }
    team_stats = {}
    key_events = []

    lines = [line.strip() for line in text.split("\n")]
    for line in lines:
        if not line:
            continue
        if line.startswith("Match:"):
            match = re.search(r"Match:\s*([A-Za-z0-9\s]+)\s+vs\s+([A-Za-z0-9\s]+)", line)
            if match:
                meta["home_team"] = match.group(1).strip()
                meta["away_team"] = match.group(2).strip()
        elif line.startswith("Score:"):
            match = re.search(r"Score:\s*(\d+)-(\d+)", line)
            if match:
                meta["score_home"] = int(match.group(1))
                meta["score_away"] = int(match.group(2))
        elif line.startswith("Date:"):
            match = re.search(r"Date:\s*([\d-]+)", line)
            if match:
                meta["date"] = match.group(1).strip()
        elif line.startswith("Competition:"):
            meta["competition"] = line.replace("Competition:", "").strip()
        elif line.startswith("Saison:"):
            meta["saison"] = line.replace("Saison:", "").strip()
        elif ":" in line and ("Possession" in line or "Passes" in line):
            parts = line.split(":", 1)
            team_name = parts[0].strip()
            stats_str = parts[1].strip()
            
            pos_m = re.search(r"Possession\s*(\d+)%", stats_str)
            pas_m = re.search(r"Passes\s*(\d+)", stats_str)
            prog_m = re.search(r"Passes progressives\s*(\d+)", stats_str)
            tirs_m = re.search(r"Tirs\s*(\d+)", stats_str)
            cadr_m = re.search(r"Tirs cadrés\s*(\d+)", stats_str)
            xg_m = re.search(r"xG\s*([\d.]+)", stats_str)
            ppda_m = re.search(r"PPDA\s*([\d.]+)", stats_str)
            bloc_m = re.search(r"Bloc style\s*(\S+)", stats_str)
            
            team_stats[team_name] = {
                "possession_pct": int(pos_m.group(1)) if pos_m else 50,
                "passes_completed": int(pas_m.group(1)) if pas_m else 400,
                "passes_progressive": int(prog_m.group(1)) if prog_m else 30,
                "shots": int(tirs_m.group(1)) if tirs_m else 10,
                "shots_on_target": int(cadr_m.group(1)) if cadr_m else 4,
                "xg": float(xg_m.group(1)) if xg_m else 1.0,
                "ppda": float(ppda_m.group(1)) if ppda_m else 10.0,
                "bloc_style": bloc_m.group(1).strip() if bloc_m else "medium-block"
            }
        elif line.startswith("-") and "minute" in line:
            match = re.search(r"-\s*(\d+)(?:ème|e)?\s*minute:\s*\((\w+)\)\s*(.*)", line)
            if match:
                minute = int(match.group(1))
                team = match.group(2).strip()
                rest = match.group(3).strip()
                
                ev_type = "tactical_change"
                if "But" in rest or "but" in rest:
                    ev_type = "goal"
                elif "Transition" in rest or "transition" in rest or "contre-attaque" in rest:
                    ev_type = "big_chance"
                
                key_events.append({
                    "minute": minute,
                    "team": team,
                    "type": ev_type,
                    "description": rest
                })

    home_slug = meta["home_team"].lower().replace(" ", "_")
    away_slug = meta["away_team"].lower().replace(" ", "_")
    date_slug = meta["date"].replace("-", "_")
    match_id = f"{date_slug}_{home_slug}_{away_slug}_01"

    for t in [meta["home_team"], meta["away_team"]]:
        if t not in team_stats:
            team_stats[t] = {
                "possession_pct": 50,
                "passes_completed": 400,
                "passes_progressive": 30,
                "shots": 10,
                "shots_on_target": 4,
                "xg": 1.0,
                "ppda": 10.0,
                "bloc_style": "medium-block"
            }

    return {
        "match_id": match_id,
        "meta": meta,
        "team_stats": team_stats,
        "key_events": key_events
    }

# =====================================================================
# Main processor class
# =====================================================================
class MatchBulkProcessor:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.use_llm = self.api_key and not self.api_key.startswith("mock-") and len(self.api_key.strip()) > 0

    def process_file(self, text_path: str) -> dict:
        with open(text_path, 'r', encoding='utf-8') as f:
            text_content = f.read()

        filename = os.path.basename(text_path)
        
        if self.use_llm:
            try:
                print(f"-> Extraction LLM (GPT-4o-mini) pour {filename}...")
                client = OpenAI(api_key=self.api_key)
                
                prompt = f"""
                Tu es un ingénieur de données et un analyste tactique de football.
                Analyse le compte-rendu textuel ci-dessous et extrais ses données de match sous forme structurée en respectant scrupuleusement le format.
                
                Texte du match :
                {text_content}
                
                Règles importantes pour l'extraction :
                - Le match_id doit être unique au format: YYYY_MM_DD_home_away_01 (en minuscules).
                - Les team_stats doivent être renseignées pour les deux équipes mentionnées. Si des métriques (comme passes progressives, xG, PPDA, passes complétées) manquent, estime-les de manière réaliste par rapport au score et à la possession.
                - Les key_events doivent capturer les minutes exactes, les équipes associées, les types d'événements (goal, tactical_change, big_chance, card, etc.) et les descriptions tactiques correspondantes.
                """
                
                response = client.beta.chat.completions.parse(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    response_format=MatchData,
                    temperature=0.1
                )
                
                # parsed holds the validated Pydantic model
                return response.choices[0].message.parsed.model_dump()
            except Exception as e:
                print(f"[WARNING] Échec de l'appel LLM pour {filename} ({e}). Utilisation du fallback déterministe.")
                return local_regex_parse(text_content, filename)
        else:
            print(f"-> Mode offline : utilisation du parseur déterministe local pour {filename}...")
            return local_regex_parse(text_content, filename)

    def process_directory(self, source_dir: str, output_dir: str) -> List[str]:
        os.makedirs(output_dir, exist_ok=True)
        src_path = Path(source_dir)
        
        txt_files = list(src_path.glob("*.txt"))
        if not txt_files:
            print(f"Aucun fichier texte trouvé dans {source_dir}")
            return []

        print(f"Début du Batch Processing dans {source_dir} ({len(txt_files)} fichiers à traiter)...")
        generated_files = []
        
        for file in txt_files:
            try:
                match_dict = self.process_file(str(file))
                
                # Write to raw_json
                out_filename = f"{match_dict['match_id']}.json"
                out_path = os.path.join(output_dir, out_filename)
                
                with open(out_path, 'w', encoding='utf-8') as f_out:
                    json.dump(match_dict, f_out, indent=2, ensure_ascii=False)
                
                print(f"  [OK] Fichier JSON sauvegardé : {out_filename}")
                generated_files.append(out_path)
            except Exception as ex:
                print(f"  [ERROR] Échec de la conversion de {file.name} : {ex}")
                
        return generated_files

if __name__ == "__main__":
    # Test execution
    if len(sys.argv) > 2:
        src = sys.argv[1]
        out = sys.argv[2]
        processor = MatchBulkProcessor()
        processor.process_directory(src, out)
    else:
        print("Usage: python bulk_processor.py <source_dir> <output_dir>")
