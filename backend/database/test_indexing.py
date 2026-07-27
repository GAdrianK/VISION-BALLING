import sys
from pathlib import Path

# Ajout du dossier backend au sys.path pour permettre les imports absolus
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from app.core.config import settings
from database.vector_store import VectorStoreManager
from database.parent_store import ParentStoreManager
from database.indexer import run_indexing, generate_deterministic_vector
from app.services.embedding_provider import OpenAIEmbeddingProvider

def test_parent_child_retrieval(query: str = "bloc bas"):
    print("==================================================")
    print(f"   TEST RECHERCHE PARENT-CHILD SUR: '{query}'")
    print("==================================================")
    
    # 1. Connexion aux gestionnaires
    v_store = VectorStoreManager()
    p_store = ParentStoreManager()
    
    # Détection automatique : si on est en mémoire ou si la collection est vide/inexistante, on indexe d'abord.
    should_index = False
    if settings.QDRANT_URL == ":memory:":
        should_index = True
    else:
        try:
            info = v_store.client.get_collection(v_store.collection_name)
            if info.points_count == 0:
                should_index = True
        except Exception:
            should_index = True
            
    if should_index:
        print("Collection Qdrant vide ou en mémoire. Lancement de l'indexation ETL...")
        run_indexing()
        print("\nIndexation terminée. Reprise de la recherche...\n")
        
    # 2. Vectorisation de la requête de test
    api_key = settings.OPENAI_API_KEY
    use_openai = api_key and not api_key.startswith("mock-") and len(api_key.strip()) > 0
    
    if use_openai:
        print("Génération de l'embedding de la requête via OpenAI...")
        emb_provider = OpenAIEmbeddingProvider(api_key=api_key)
        query_vector = emb_provider.get_embedding(query)
    else:
        print("Génération de l'embedding de la requête via simulation déterministe local...")
        query_vector = generate_deterministic_vector(query)
        
    # 3. Recherche sémantique dans Qdrant pour trouver le chunk Enfant
    print(f"Recherche du meilleur chunk sémantique dans Qdrant (Collection: {v_store.collection_name})...")
    results = v_store.search_semantic(query_vector, top_k=1)
    
    if not results:
        print("[WARNING] Aucun point trouvé dans la collection Qdrant.")
        return
        
    best_match = results[0]
    payload = best_match.payload
    child_text = payload["text"]
    parent_id = payload["parent_id"]
    score = best_match.score
    metadata = payload["metadata"]
    
    print("\n--------------------------------------------------")
    print("           CHUNK ENFANT TROUVÉ (Qdrant)           ")
    print("--------------------------------------------------")
    print(f"ID du Point : {best_match.id}")
    print(f"Score       : {score:.4f}")
    print(f"Source      : {metadata['source']}")
    print(f"Tags        : {metadata['tags_tactiques']}")
    print(f"Type        : {metadata['type_chunk']}")
    print(f"Parent ID   : {parent_id}")
    print(f"Texte Enfant (extrait) :\n{child_text}")
    print("--------------------------------------------------")
    
    # 4. Récupération du document Parent complet depuis SQLite
    print(f"\nRécupération du document parent complet depuis SQLite avec parent_id : {parent_id}...")
    parent_data = p_store.get_parent(parent_id)
    
    if parent_data:
        source_name, parent_content = parent_data
        print("\n--------------------------------------------------")
        print("        DOCUMENT PARENT RÉCUPÉRÉ (SQLite)         ")
        print("--------------------------------------------------")
        print(f"Fichier Source : {source_name}")
        print(f"Taille Totale  : {len(parent_content)} caractères")
        print(f"Texte Parent (200 premiers caractères) :\n{parent_content[:200]}...")
        print("--------------------------------------------------")
    else:
        print(f"\n[ERROR] Aucun document parent trouvé dans SQLite pour l'ID : {parent_id}")

if __name__ == "__main__":
    query_param = "bloc bas"
    if len(sys.argv) > 1:
        query_param = " ".join(sys.argv[1:])
    test_parent_child_retrieval(query_param)
