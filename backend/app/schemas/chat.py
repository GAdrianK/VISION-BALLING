from enum import Enum
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class ChatMode(str, Enum):
    COACH = "coach"
    ANALYST = "analyst"
    FAN = "fan"

class MessageHistory(BaseModel):
    role: str = Field(..., description="Le rôle de l'auteur : 'user' ou 'assistant' ou 'system'")
    content: str = Field(..., description="Le contenu textuel du message")

class ChatRequest(BaseModel):
    message: str = Field(..., description="Le message / la question posée par l'utilisateur")
    mode: ChatMode = Field(default=ChatMode.COACH, description="Le profil d'assistance tactique souhaité")
    history: Optional[List[MessageHistory]] = Field(default=None, description="L'historique des échanges conversationnels")

class SourceReference(BaseModel):
    text: str = Field(..., description="L'extrait sémantique récupéré")
    source: str = Field(..., description="Le nom du fichier d'origine")
    score: float = Field(..., description="Le score de pertinence cosinus")

class ChatResponse(BaseModel):
    answer: str = Field(..., description="La réponse textuelle générée")
    mode: ChatMode = Field(..., description="Le mode d'assistance utilisé")
    sources: List[SourceReference] = Field(..., description="Les sources RAG injectées pour formuler la réponse")
