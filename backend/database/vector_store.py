import os
import logging
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams
from app.core.config import settings

logger = logging.getLogger(__name__)

class VectorStoreManager:
    """
    Gestionnaire pour le Vector Store Qdrant.
    Gère la connexion, la création de la collection et l'indexation du payload.
    """
    _client_instance = None

    def __init__(self):
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        
        # Singleton pattern pour éviter les verrous d'accès concurrents sur Qdrant local
        if VectorStoreManager._client_instance is None:
            url = settings.QDRANT_URL
            if url == ":memory:":
                # Utilise un stockage local persistant sous backend/data/qdrant_local
                qdrant_path = os.path.abspath(os.path.join(settings.get_processed_data_dir(), "..", "qdrant_local"))
                logger.info(f"Initialisation de Qdrant local persistant sur : {qdrant_path}")
                VectorStoreManager._client_instance = QdrantClient(path=qdrant_path)
            else:
                logger.info(f"Connexion au serveur Qdrant sur : {url}")
                VectorStoreManager._client_instance = QdrantClient(url=url)
                
        self.client = VectorStoreManager._client_instance


    def init_collection(self, force_recreate: bool = False):
        """
        Initialise la collection dans Qdrant avec les paramètres et index appropriés.
        """
        # Vérifier si la collection existe déjà
        collections_response = self.client.get_collections()
        exists = any(c.name == self.collection_name for c in collections_response.collections)

        if exists and force_recreate:
            logger.info(f"Suppression de la collection existante : {self.collection_name}")
            self.client.delete_collection(self.collection_name)
            exists = False

        if not exists:
            logger.info(f"Création de la collection : {self.collection_name} (dim=1536, metric=Cosine)")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
            )
            
            # Création des index de payload pour optimiser le filtrage sémantique
            self._create_payload_indexes()
        else:
            logger.info(f"La collection {self.collection_name} existe déjà.")

    def _create_payload_indexes(self):
        """
        Crée des index sur les champs clés des métadonnées pour accélérer le filtrage.
        """
        fields_to_index = [
            ("metadata.equipes", models.PayloadSchemaType.KEYWORD),
            ("metadata.tags_tactiques", models.PayloadSchemaType.KEYWORD),
            ("metadata.type_chunk", models.PayloadSchemaType.KEYWORD),
            ("metadata.source", models.PayloadSchemaType.KEYWORD),
            ("metadata.periode", models.PayloadSchemaType.KEYWORD),
            ("metadata.intervalle_temps", models.PayloadSchemaType.KEYWORD)
        ]

        for field_name, schema_type in fields_to_index:
            try:
                logger.info(f"Création de l'index de payload pour : {field_name}")
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=schema_type
                )
            except Exception as e:
                logger.error(f"Erreur lors de la création de l'index pour {field_name} : {e}")

    def upsert_points(self, points: list):
        """
        Insère ou met à jour des points vectoriels dans Qdrant.
        Chaque point doit être un objet models.PointStruct.
        """
        if not points:
            return
            
        logger.info(f"Insertion de {len(points)} points dans {self.collection_name}...")
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )

    def search_semantic(self, query_vector: list, top_k: int = 3, filter_dict: dict = None) -> list:
        """
        Recherche sémantique avec filtrage de métadonnées optionnel.
        """
        qdrant_filter = None
        if filter_dict:
            must_conditions = []
            for key, val in filter_dict.items():
                if isinstance(val, list):
                    # Filtrage MatchAny pour les listes (ex: tag dans une liste)
                    must_conditions.append(
                        models.FieldCondition(
                            key=key,
                            match=models.MatchAny(any=val)
                        )
                    )
                else:
                    must_conditions.append(
                        models.FieldCondition(
                            key=key,
                            match=models.MatchValue(value=val)
                        )
                    )
            qdrant_filter = models.Filter(must=must_conditions)

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            query_filter=qdrant_filter
        )
        return response.points

