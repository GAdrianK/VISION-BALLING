import os
import sys
import json
import uuid
import random
from pathlib import Path
from typing import List

# Ajout du dossier backend au sys.path pour permettre les imports absolus
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from qdrant_client.http.models import PointStruct
from app.core.config import settings
from app.services.embedding_provider import OpenAIEmbeddingProvider, GeminiEmbeddingProvider
from database.vector_store import VectorStoreManager
from database.parent_store import ParentStoreManager

def generate_deterministic_vector(text: str, dimension: int = 1536) -> List[float]:
    """
    Génère un vecteur normalisé déterministe basé sur le hash du texte.
    Utile pour tester le pipeline hors-ligne sans clé API OpenAI réelle.
    """
    # Calculer un seed stable à partir du texte
    # hash() n'est pas stable entre les sessions Python, on utilise donc une fonction stable
    import hashlib
    hash_bytes = hashlib.md5(text.encode('utf-8')).digest()
    seed = int.from_bytes(hash_bytes, byteorder='big')
    
    rng = random.Random(seed)
    vector = [rng.gauss(0, 1) for _ in range(dimension)]
    norm = sum(x*x for x in vector) ** 0.5
    if norm > 0:
        vector = [x / norm for x in vector]
    else:
        vector = [0.0] * dimension
    return vector

def run_indexing():
    processed_dir = Path(settings.get_processed_data_dir())
    raw_dir = Path(settings.get_raw_data_dir())
    chunks_file = processed_dir / "chunks.jsonl"
    
    if not chunks_file.exists():
        print(f"[ERROR] Le fichier {chunks_file} n'existe pas. Veuillez d'abord exécuter run_etl.py.")
        return

    print("==================================================")
    print("      FOOTBALL IQ - SCRIPT D'INDEXATION ETL        ")
    print("==================================================")

    # Initialisation des gestionnaires de stockage
    vector_store = VectorStoreManager()
    parent_store = ParentStoreManager()

    # Ne pas forcer la récréation pour préserver les indexations précédentes
    vector_store.init_collection(force_recreate=False)

    # Lecture des chunks
    chunks = []
    with open(chunks_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))

    print(f"\nChargement de {len(chunks)} chunks enfants depuis chunks.jsonl...")

    # Déterminer si on utilise l'API Gemini, OpenAI ou le mode simulation
    gemini_key = settings.gemini_key
    use_gemini = gemini_key and not gemini_key.startswith("mock-") and len(gemini_key.strip()) > 0

    api_key = settings.OPENAI_API_KEY
    use_openai = api_key and not api_key.startswith("mock-") and len(api_key.strip()) > 0
    
    if use_gemini:
        print("Mode : Gemini Embeddings (En ligne)")
        emb_provider = GeminiEmbeddingProvider(api_key=gemini_key)
    elif use_openai:
        print("Mode : OpenAI Embeddings (En ligne)")
        emb_provider = OpenAIEmbeddingProvider(api_key=api_key)
    else:
        print("Mode : Simulation déterministe (Hors-ligne / Clé mockée)")
        emb_provider = None

    processed_parents = {}
    points_to_upsert = []

    for idx, chunk in enumerate(chunks):
        text = chunk["text"]
        metadata = chunk["metadata"]
        source_name = metadata["source"]
        chunk_id = metadata["id"]

        # 1. Gestion du document parent (SQLite) avec logique d'Upsert
        # Génération d'un parent_id unique et déterministe basé sur le nom du fichier source
        parent_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, source_name))
        
        if parent_uuid not in processed_parents:
            parent_file_path = raw_dir / source_name
            if parent_file_path.exists():
                try:
                    with open(parent_file_path, "r", encoding="utf-8") as f_parent:
                        parent_content = f_parent.read()
                    
                    # Si le parent est déjà indexé, on fait un Upsert en nettoyant d'abord Qdrant
                    if parent_store.exists(parent_uuid):
                        print(f"[UPSERT] Le document {source_name} est déjà indexé. Nettoyage des anciens points dans Qdrant...")
                        from qdrant_client.http import models as qdrant_models
                        try:
                            vector_store.client.delete(
                                collection_name=vector_store.collection_name,
                                points_selector=qdrant_models.FilterSelector(
                                    filter=qdrant_models.Filter(
                                        must=[
                                            qdrant_models.FieldCondition(
                                                key="parent_id",
                                                match=qdrant_models.MatchValue(value=parent_uuid)
                                            )
                                        ]
                                    )
                                )
                            )
                        except Exception as delete_error:
                            print(f"[WARNING] Erreur lors de la suppression de points : {delete_error}")

                    # Sauvegarder dans SQLite (INSERT OR REPLACE)
                    parent_store.save_parent(
                        parent_id=parent_uuid,
                        source_name=source_name,
                        content=parent_content
                    )
                    processed_parents[parent_uuid] = source_name
                except Exception as e:
                    print(f"[ERROR] Impossible de lire le fichier parent {source_name} : {e}")
            else:
                print(f"[WARNING] Le fichier parent brut {source_name} est introuvable dans {raw_dir}.")

        # 2. Génération de l'embedding du chunk enfant
        try:
            if use_openai and emb_provider:
                vector = emb_provider.get_embedding(text)
            else:
                vector = generate_deterministic_vector(text)
        except Exception as e:
            print(f"[ERROR] Échec de la vectorisation pour le chunk {idx} : {e}")
            # Fallback en mode déterministe local en cas d'erreur de clé ou réseau
            vector = generate_deterministic_vector(text)

        # 3. Création du PointStruct pour Qdrant
        payload = {
            "text": text,
            "parent_id": parent_uuid,
            "metadata": metadata
        }
        
        points_to_upsert.append(
            PointStruct(
                id=chunk_id,
                vector=vector,
                payload=payload
            )
        )

    # Upsert dans Qdrant
    if points_to_upsert:
        vector_store.upsert_points(points_to_upsert)
        
    # Fermeture explicite du client pour libérer le verrou
    try:
        vector_store.client.close()
    except Exception:
        pass

    print("==================================================")
    print("          INDEXATION PIPELINE TERMINÉE            ")
    print("==================================================")
    print(f"-> {len(processed_parents)} documents parents stockés dans SQLite.")
    print(f"-> {len(points_to_upsert)} chunks enfants vectorisés et stockés dans Qdrant.")
    print("==================================================")

if __name__ == "__main__":
    run_indexing()
