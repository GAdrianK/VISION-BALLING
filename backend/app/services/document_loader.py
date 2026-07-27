import os
import re
from pathlib import Path
from typing import List, Dict, Any

class MarkdownChunker:
    """
    Découpeur de document Markdown intelligent.
    Découpe par section de titres (H2/H3) et par paragraphes,
    en préservant le contexte hiérarchique.
    """
    def __init__(self, target_chunk_words: int = 300, min_chunk_words: int = 50):
        self.target_chunk_words = target_chunk_words
        self.min_chunk_words = min_chunk_words

    def chunk_document(self, content: str, source_name: str) -> List[Dict[str, Any]]:
        chunks = []
        lines = content.split("\n")
        
        current_title = source_name.replace(".md", "").replace("_", " ").title()
        current_section = ""
        current_subsection = ""
        
        current_block = []
        current_word_count = 0
        
        def save_chunk(text_lines: List[str], doc_title: str, sec: str, subsec: str):
            text = "\n".join(text_lines).strip()
            if not text:
                return
            
            # Déduction des métadonnées tactiques à partir du nom du fichier
            src_lower = source_name.lower()
            intent = "general"
            phase = "general"
            topic = "general"
            
            # Détection du sujet (Topic)
            if "bloc_bas" in src_lower:
                topic = "bloc_bas"
            elif "pressing" in src_lower:
                topic = "pressing"
            elif "sortie_balle" in src_lower or "relance" in src_lower:
                topic = "relance"
            elif "roles" in src_lower or "role" in src_lower:
                topic = "roles"
            elif "formation" in src_lower:
                topic = "formations"
            elif "transition" in src_lower:
                topic = "transitions"
            elif "phase_offensive" in src_lower:
                topic = "offensif"
            elif "analyse_video" in src_lower:
                topic = "video"
                
            # Détection de l'intention et de la phase
            if "defend" in src_lower or "repli" in src_lower or "cpa_defensifs" in src_lower or ("bloc_bas" in src_lower and "desequilibrer" not in src_lower):
                intent = "defend"
                phase = "defensive"
            elif "attack" in src_lower or "desequilibrer" in src_lower or "jeu_couloirs" in src_lower or "centres_surface" in src_lower or "fixation_axiale" in src_lower or "sortie_balle" in src_lower or "relance" in src_lower or "jeu_direct" in src_lower:
                intent = "attack"
                phase = "offensive"
            elif "transition" in src_lower or "pressing" in src_lower:
                intent = "transition"
                phase = "transition"
            elif "roles" in src_lower:
                intent = "roles"
            elif "formation" in src_lower:
                intent = "formations"
            
            # Construire un en-tête contextuel pour le RAG
            context_prefix = f"[{doc_title}"
            if sec:
                context_prefix += f" > {sec}"
            if subsec:
                context_prefix += f" > {subsec}"
            context_prefix += "]\n"
            
            chunks.append({
                "text": context_prefix + text,
                "source": source_name,
                "metadata": {
                    "document_title": doc_title,
                    "section": sec,
                    "subsection": subsec,
                    "word_count": len(text.split()),
                    "intent": intent,
                    "phase": phase,
                    "topic": topic
                }
            })

        for line in lines:
            stripped = line.strip()
            # Détection de titre H1
            if stripped.startswith("# "):
                if current_block:
                    save_chunk(current_block, current_title, current_section, current_subsection)
                    current_block = []
                    current_word_count = 0
                current_title = stripped[2:].strip()
            # Détection de titre H2
            elif stripped.startswith("## "):
                if current_block:
                    save_chunk(current_block, current_title, current_section, current_subsection)
                    current_block = []
                    current_word_count = 0
                current_section = stripped[3:].strip()
                current_subsection = ""
            # Détection de titre H3
            elif stripped.startswith("### "):
                if current_block:
                    save_chunk(current_block, current_title, current_section, current_subsection)
                    current_block = []
                    current_word_count = 0
                current_subsection = stripped[4:].strip()
            else:
                if stripped:
                    current_block.append(line)
                    current_word_count += len(stripped.split())
                    
                    # Si le bloc en cours dépasse la taille cible, on le sauvegarde
                    if current_word_count >= self.target_chunk_words:
                        save_chunk(current_block, current_title, current_section, current_subsection)
                        current_block = []
                        current_word_count = 0

        # Enregistrer le dernier bloc résiduel
        if current_block and current_word_count >= self.min_chunk_words:
            save_chunk(current_block, current_title, current_section, current_subsection)
        elif current_block and chunks:
            # Si le dernier bloc est trop court, on l'ajoute au précédent pour ne pas perdre l'information
            last_chunk = chunks[-1]
            last_chunk["text"] += "\n" + "\n".join(current_block)
            last_chunk["metadata"]["word_count"] += current_word_count

        return chunks

class DocumentLoader:
    """
    Chargeur de documents Markdown de la base de connaissances.
    """
    def __init__(self, knowledge_base_dir: str):
        self.kb_dir = Path(knowledge_base_dir)
        self.chunker = MarkdownChunker()

    def load_all_documents(self) -> List[Dict[str, Any]]:
        all_chunks = []
        if not self.kb_dir.exists():
            print(f"Avertissement : Le dossier {self.kb_dir} n'existe pas.")
            return all_chunks

        for path in self.kb_dir.rglob("*.md"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Retirer d'éventuels front-matters YAML en haut du fichier
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        content = parts[2]
                
                chunks = self.chunker.chunk_document(content, path.name)
                all_chunks.extend(chunks)
            except Exception as e:
                print(f"Erreur lors du chargement de {path.name} : {e}")
        
        return all_chunks
