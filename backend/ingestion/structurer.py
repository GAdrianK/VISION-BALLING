import re
import uuid
from typing import List, Dict, Any
from backend.ingestion.schemas import ProcessedChunk, ChunkMetadata

# Dictionnaires et listes de détection déterministe pour le football
TEAMS_DB = [
    "Paris Saint-Germain", "PSG", "Olympique de Marseille", "OM", "Olympique Lyonnais", "OL",
    "Real Madrid", "Barcelona", "Barça", "Atletico Madrid", "Manchester City", "Man City",
    "Liverpool", "Arsenal", "Chelsea", "Manchester United", "Bayern Munich", "Borussia Dortmund",
    "Juventus", "AC Milan", "Inter Milan", "Ajax", "Pays-Bas", "Italie", "Allemagne", "France", "Espagne"
]

TACTICAL_TAGS_MAP = {
    "pressing": ["pressing", "contre-pressing", "gegenpress", "harcèlement", "pressing haut", "pression"],
    "low-block": ["bloc bas", "low-block", "low block", "défense basse", "compacite", "repli"],
    "mid-block": ["bloc médian", "mid-block", "bloc moyen", "coulissement"],
    "offense": ["attaque", "offensive", "possession", "construction", "centres", "finition", "déséquilibrer", "animation", "passes"],
    "defense": ["défense", "défensif", "coulissement", "zone", "rest defense", "marquage", "hors-jeu"],
    "transition": ["transition", "contre-attaque", "repli", "perte", "récupération", "contre-attaquer"],
    "formation": ["4-3-3", "4-4-2", "3-5-2", "3-4-3", "4-2-3-1", "3-2-4-1", "5-4-1", "4-1-4-1"],
    "player-role": ["faux 9", "faux-9", "sentinelle", "piston", "gardien-libéro", "sweeper keeper", "ailier inversé", "latéral inversé", "wingback"]
}

def extract_teams(text: str) -> List[str]:
    """
    Extrait de manière déterministe les équipes mentionnées dans le texte.
    """
    found_teams = []
    for team in TEAMS_DB:
        # Recherche insensible à la casse avec délimiteur de mots
        pattern = r"\b" + re.escape(team) + r"\b"
        if re.search(pattern, text, re.IGNORECASE):
            # Éviter les doublons comme PSG et Paris Saint-Germain si les deux sont là (facultatif, on garde les deux pour l'instant)
            found_teams.append(team)
    return found_teams

def extract_tactical_tags(text: str) -> List[str]:
    """
    Extrait les concepts tactiques basés sur des mots-clés prédéfinis.
    """
    tags = []
    text_lower = text.lower()
    for tag, keywords in TACTICAL_TAGS_MAP.items():
        for kw in keywords:
            if kw in text_lower:
                tags.append(tag)
                break  # Passer au tag suivant dès qu'un mot-clé matche
    return tags

def determine_chunk_type(text: str, h1: str, h2: str) -> str:
    """
    Détermine le type de chunk (exercice, match, tactique, historique, general).
    """
    combined_context = f"{h1} {h2} {text}".lower()
    
    if any(kw in combined_context for kw in ["exercice", "entrainement", "entraînement", "consignes", "dimensions", "règles de jeu"]):
        return "exercice"
    elif any(kw in combined_context for kw in ["match", "rencontre", "score", "buts", "minutes", "mi-temps"]):
        return "match"
    elif any(kw in combined_context for kw in ["historique", "sacchi", "cruyff", "années", "siecle", "histoire", "ajax 1970"]):
        return "historique"
    elif any(kw in combined_context for kw in ["tactique", "formation", "principe", "rôle", "role", "système"]):
        return "tactique"
    
    return "general"

class MarkdownHeaderSplitter:
    """
    Découpeur de document Markdown intelligent basé sur la hiérarchie des titres.
    """
    def __init__(self, max_words_per_chunk: int = 350):
        self.max_words_per_chunk = max_words_per_chunk

    def split_document(self, content: str, source_filename: str) -> List[ProcessedChunk]:
        chunks = []
        lines = content.split("\n")
        
        current_h1 = source_filename.replace(".md", "").replace("_", " ").title()
        current_h2 = ""
        current_h3 = ""
        
        current_block = []
        current_word_count = 0
        
        def save_chunk(text_lines: List[str]):
            text = "\n".join(text_lines).strip()
            if not text:
                return
                
            # Construire l'en-tête de contexte hiérarchique
            context_header = f"[{current_h1}"
            if current_h2:
                context_header += f" > {current_h2}"
            if current_h3:
                context_header += f" > {current_h3}"
            context_header += "]\n"
            
            full_text = context_header + text
            
            # Extraction des métadonnées
            teams = extract_teams(full_text)
            tags = extract_tactical_tags(full_text)
            chunk_type = determine_chunk_type(text, current_h1, current_h2)
            
            # Extraction de la période et de l'intervalle de temps
            periode = "global"
            intervalle = "all"
            
            # 1. Recherche via les commentaires HTML d'annotation temporelle
            time_match = re.search(r"<!--\s*@time:\s*periode=(\w+),\s*intervalle=([\w+-]+)\s*-->", full_text)
            if time_match:
                periode = time_match.group(1)
                intervalle = time_match.group(2)
            elif source_filename.startswith("match_"):
                # 2. Heuristique textuelle si pas de commentaire (uniquement pour les rapports de match)
                min_match = re.search(r"\b(\d{1,3})(?:e|ème)?\s*(?:minute|min|')", full_text, re.IGNORECASE)
                if min_match:
                    minute = int(min_match.group(1))
                    if minute <= 45:
                        periode = "1MT"
                        if minute <= 15:
                            intervalle = "0-15"
                        elif minute <= 30:
                            intervalle = "15-30"
                        else:
                            intervalle = "30-45"
                    else:
                        periode = "2MT"
                        if minute <= 60:
                            intervalle = "45-60"
                        elif minute <= 75:
                            intervalle = "60-75"
                        elif minute <= 90:
                            intervalle = "75-90"
                        else:
                            intervalle = "90+"

            # Génération d'un UUID unique pour le chunk
            chunk_id = str(uuid.uuid4())
            
            metadata = ChunkMetadata(
                id=chunk_id,
                source=source_filename,
                equipes=teams,
                tags_tactiques=tags,
                type_chunk=chunk_type,
                periode=periode,
                intervalle_temps=intervalle
            )
            
            chunks.append(ProcessedChunk(
                text=full_text,
                metadata=metadata
            ))

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if current_block:
                    current_block.append(line)
                continue
                
            # Détection de titre H1
            if stripped.startswith("# "):
                if current_block:
                    save_chunk(current_block)
                    current_block = []
                    current_word_count = 0
                current_h1 = stripped[2:].strip()
                current_h2 = ""
                current_h3 = ""
                
            # Détection de titre H2
            elif stripped.startswith("## "):
                if current_block:
                    save_chunk(current_block)
                    current_block = []
                    current_word_count = 0
                current_h2 = stripped[3:].strip()
                current_h3 = ""
                
            # Détection de titre H3
            elif stripped.startswith("### "):
                if current_block:
                    save_chunk(current_block)
                    current_block = []
                    current_word_count = 0
                current_h3 = stripped[4:].strip()
                
            else:
                current_block.append(line)
                current_word_count += len(stripped.split())
                
                # Si la taille dépasse, on découpe pour garder des chunks digestes
                if current_word_count >= self.max_words_per_chunk:
                    save_chunk(current_block)
                    current_block = []
                    current_word_count = 0
                    
        # Enregistrer le reliquat final
        if current_block:
            save_chunk(current_block)
            
        return chunks
