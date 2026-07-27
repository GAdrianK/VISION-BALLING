import math
import re
from typing import List, Dict, Union
from openai import OpenAI

class EmbeddingProvider:
    """
    Interface de base pour les fournisseurs d'embeddings.
    """
    def get_embedding(self, text: str) -> List[float]:
        raise NotImplementedError

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        return [self.get_embedding(t) for t in texts]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    Fournisseur d'embeddings utilisant l'API OpenAI.
    """
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def get_embedding(self, text: str) -> List[float]:
        # Nettoyer les sauts de ligne pour de meilleures performances
        clean_text = text.replace("\n", " ")
        response = self.client.embeddings.create(
            input=[clean_text],
            model=self.model
        )
        return response.data[0].embedding

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        clean_texts = [t.replace("\n", " ") for t in texts]
        response = self.client.embeddings.create(
            input=clean_texts,
            model=self.model
        )
        return [item.embedding for item in response.data]

class GeminiEmbeddingProvider(EmbeddingProvider):
    """
    Fournisseur d'embeddings utilisant l'API Google Gemini.
    """
    def __init__(self, api_key: str, model: str = "gemini-embedding-2"):
        from google import genai
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def get_embedding(self, text: str) -> List[float]:
        from google.genai import types
        clean_text = text.replace("\n", " ")
        try:
            response = self.client.models.embed_content(
                model=self.model,
                contents=clean_text,
                config=types.EmbedContentConfig(output_dimensionality=1536)
            )
            return response.embeddings[0].values
        except Exception as e:
            # Fallback to local tf-idf or error raise
            print(f"[ERROR] Gemini embedding failed: {e}")
            raise e


class TFIDFEmbeddingProvider(EmbeddingProvider):
    """
    Fournisseur d'embeddings local léger basé sur TF-IDF en Python pur.
    Sert de fallback sans clé API OpenAI ou pour les tests unitaires locaux hors-ligne.
    """
    def __init__(self):
        self.vocabulary: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.is_fitted = False

    def _tokenize(self, text: str) -> List[str]:
        # Lowercase et suppression de la ponctuation de base
        text_clean = re.sub(r'[^\w\s-]', ' ', text.lower())
        # Découper par mot
        tokens = []
        for token in text_clean.split():
            if len(token) > 1:
                tokens.append(token)
                # Si le token contient des tirets et ressemble à une formation (ex: 4-3-3)
                if '-' in token and re.match(r'^\d+(-\d+)+$', token):
                    normalized = token.replace('-', '')
                    tokens.append(normalized)
                # Si le token est composé uniquement de chiffres et ressemble à une formation sans tiret (ex: 433, 442, 4231, 352)
                elif token.isdigit() and len(token) in [3, 4]:
                    with_hyphens = "-".join(list(token))
                    tokens.append(with_hyphens)
        return tokens

    def fit(self, documents: List[str]):
        if not documents:
            return
        
        # 1. Construire le vocabulaire
        vocab_set = set()
        tokenized_docs = []
        for doc in documents:
            tokens = self._tokenize(doc)
            tokenized_docs.append(tokens)
            vocab_set.update(tokens)
            
        self.vocabulary = {word: idx for idx, word in enumerate(sorted(vocab_set))}
        vocab_size = len(self.vocabulary)
        num_docs = len(documents)

        # 2. Calculer le document frequency (DF) pour chaque terme du vocabulaire
        df = {word: 0 for word in self.vocabulary}
        for tokens in tokenized_docs:
            unique_tokens = set(tokens)
            for token in unique_tokens:
                if token in df:
                    df[token] += 1

        # 3. Calculer l'IDF avec lissage standard
        self.idf = {}
        for word, count in df.items():
            self.idf[word] = math.log(1 + (num_docs / (1 + count))) + 1.0

        self.is_fitted = True

    def get_embedding(self, text: str) -> List[float]:
        """
        Génère un vecteur TF-IDF pour un texte donné.
        """
        if not self.is_fitted:
            # Si non fitted, retourne un vecteur vide
            return []
            
        vector = [0.0] * len(self.vocabulary)
        tokens = self._tokenize(text)
        if not tokens:
            return vector
            
        # Calcul des fréquences de termes (TF)
        tf = {}
        for token in tokens:
            if token in self.vocabulary:
                tf[token] = tf.get(token, 0) + 1

        # Construction du vecteur TF-IDF
        for token, count in tf.items():
            idx = self.vocabulary[token]
            # TF normalisé par la taille du texte * IDF
            vector[idx] = (count / len(tokens)) * self.idf[token]
            
        # Normalisation L2 du vecteur pour simplifier le calcul du cosinus ensuite
        norm = math.sqrt(sum(val ** 2 for val in vector))
        if norm > 0:
            vector = [val / norm for val in vector]
            
        return vector

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not self.is_fitted:
            # Fit à la volée si nécessaire
            self.fit(texts)
        return [self.get_embedding(t) for t in texts]


def get_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Calcule la similarité cosinus entre deux vecteurs.
    Si les vecteurs ont été normalisés L2, c'est simplement le produit scalaire.
    """
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
        
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a ** 2 for a in vec_a))
    norm_b = math.sqrt(sum(b ** 2 for b in vec_b))
    
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
        
    return dot_product / (norm_a * norm_b)
