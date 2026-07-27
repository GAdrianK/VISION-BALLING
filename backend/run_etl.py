import os
import json
import sys
from pathlib import Path

# Ajout du dossier backend et de son parent au sys.path pour permettre les imports absolus
backend_dir = Path(__file__).resolve().parent
sys.path.append(str(backend_dir))
sys.path.append(str(backend_dir.parent))


from app.core.config import settings
from ingestion.cleaner import clean_text
from ingestion.structurer import MarkdownHeaderSplitter

def run_etl_pipeline():
    raw_dir = Path(settings.get_raw_data_dir())
    processed_dir = Path(settings.get_processed_data_dir())
    
    # S'assurer que les dossiers existent
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = processed_dir / "chunks.jsonl"
    
    print("==================================================")
    print("      FOOTBALL IQ - PIPELINE ETL D'INGESTION       ")
    print("==================================================")
    print(f"Dossier source (brut) : {raw_dir}")
    print(f"Dossier cible (JSONL) : {output_file}")
    
    # Récupérer les fichiers bruts (.md, .txt, .html)
    raw_files = []
    for ext in ["*.md", "*.txt", "*.html"]:
        raw_files.extend(raw_dir.glob(ext))
        
    if not raw_files:
        print("\nAucun fichier brut trouvé dans le dossier raw.")
        print(f"Veuillez déposer des fichiers tactiques ou de rapports de matchs dans : {raw_dir}")
        return
        
    print(f"\nFichiers trouvés ({len(raw_files)}) : {[f.name for f in raw_files]}")
    print("Traitement en cours...")
    
    splitter = MarkdownHeaderSplitter()
    processed_chunks_count = 0
    all_chunks = []
    
    for file_path in raw_files:
        print(f"\nProcessing: {file_path.name}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            # 1. Nettoyage
            cleaned = clean_text(content)
            
            # 2. Découpage et extraction métadonnées
            chunks = splitter.split_document(cleaned, file_path.name)
            all_chunks.extend(chunks)
            print(f"  -> {len(chunks)} chunks créés et validés.")
            
        except Exception as e:
            print(f"  [ERROR] Échec du traitement de {file_path.name} : {e}")
            
    if not all_chunks:
        print("\nAucun chunk n'a été produit. Fin du traitement.")
        return
        
    # 3. Export au format JSONL
    print(f"\nÉcriture de {len(all_chunks)} chunks dans {output_file}...")
    try:
        with open(output_file, "w", encoding="utf-8") as f_out:
            for chunk in all_chunks:
                # model_dump() est le standard Pydantic v2
                line = json.dumps(chunk.model_dump(), ensure_ascii=False)
                f_out.write(line + "\n")
        print("==================================================")
        print("          PIPELINE ETL EXÉCUTÉ AVEC SUCCÈS        ")
        print("==================================================")
    except Exception as e:
        print(f"[ERROR] Échec de l'écriture du fichier JSONL : {e}")

if __name__ == "__main__":
    run_etl_pipeline()
