from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

ALLOWED_ROLES = [
    "Entraîneur",
    "Analyste vidéo",
    "Analyste performance",
    "Staff",
    "Direction sportive",
    "Autre",
]

ALLOWED_VIDEO_TYPES = [
    "Match complet",
    "Première mi-temps",
    "Deuxième mi-temps",
    "Extrait",
    "Autre",
]

ALLOWED_OBJECTIVES = [
    "Analyse globale",
    "Organisation défensive",
    "Bloc / compacité",
    "Pressing",
    "Possession",
    "Transitions",
    "Séquences clés",
    "Autre",
]

ALLOWED_STATUSES = [
    "NEW",
    "CONTACTED",
    "VIDEO_RECEIVED",
    "PROCESSING",
    "DELIVERED",
    "FEEDBACK_RECEIVED",
    "DECLINED",
]

FORBIDDEN_SCHEMES = {"javascript", "data", "file", "ftp", "vbscript", "about", "blob"}


def sanitize_text(value: str) -> str:
    """Strips whitespace and removes null bytes or control characters."""
    if not value:
        return ""
    # Strip null bytes and control chars except space
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", value)
    return cleaned.strip()


EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+$")


class BetaAnalysisRequestCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    club: str = Field(..., min_length=2, max_length=150)
    role: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=254)
    phone: Optional[str] = Field(default=None, max_length=50)
    team_category: str = Field(..., min_length=2, max_length=100)
    competition_level: str = Field(..., min_length=2, max_length=100)
    opponent: Optional[str] = Field(default=None, max_length=150)
    video_type: str = Field(..., min_length=2, max_length=100)
    video_url: str = Field(..., min_length=8, max_length=2048)
    analysis_objectives: List[str] = Field(..., min_length=1, max_length=15)
    message: Optional[str] = Field(default=None, max_length=2000)
    video_authorization_confirmed: bool = Field(...)
    temporary_storage_consent: bool = Field(...)
    honeypot: Optional[str] = Field(default="", max_length=100)

    @field_validator("name", "club", "team_category", "competition_level")
    @classmethod
    def validate_text_fields(cls, v: str) -> str:
        cleaned = sanitize_text(v)
        if len(cleaned) < 2:
            raise ValueError("Ce champ doit contenir au moins 2 caractères.")
        return cleaned

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        cleaned = sanitize_text(v).lower()
        if not EMAIL_REGEX.match(cleaned):
            raise ValueError("Format d'adresse email invalide.")
        return cleaned

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        cleaned = sanitize_text(v)
        if cleaned not in ALLOWED_ROLES:
            raise ValueError(f"Rôle non valide. Valeurs autorisées: {', '.join(ALLOWED_ROLES)}")
        return cleaned

    @field_validator("video_type")
    @classmethod
    def validate_video_type(cls, v: str) -> str:
        cleaned = sanitize_text(v)
        if cleaned not in ALLOWED_VIDEO_TYPES:
            raise ValueError(f"Type de vidéo non valide. Valeurs autorisées: {', '.join(ALLOWED_VIDEO_TYPES)}")
        return cleaned

    @field_validator("analysis_objectives")
    @classmethod
    def validate_objectives(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("Au moins un objectif d'analyse doit être sélectionné.")
        cleaned_list = []
        for obj in v:
            cleaned_obj = sanitize_text(obj)
            if cleaned_obj not in ALLOWED_OBJECTIVES:
                raise ValueError(f"Objectif '{cleaned_obj}' non reconnu.")
            if cleaned_obj not in cleaned_list:
                cleaned_list.append(cleaned_obj)
        return cleaned_list

    @field_validator("phone", "opponent", "message")
    @classmethod
    def validate_optional_text(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = sanitize_text(v)
        return cleaned if cleaned else None

    @field_validator("video_url")
    @classmethod
    def validate_video_url(cls, v: str) -> str:
        cleaned = sanitize_text(v)
        if not cleaned:
            raise ValueError("L'URL de la vidéo est requise.")
        
        parsed = urlparse(cleaned)
        scheme = (parsed.scheme or "").lower()

        if scheme in FORBIDDEN_SCHEMES:
            raise ValueError("Schéma d'URL non autorisé.")
        
        if scheme not in ("https", "http"):
            raise ValueError("L'URL doit commencer par https://")

        # Allow http only for localhost / 127.0.0.1 in testing
        if scheme == "http":
            hostname = (parsed.hostname or "").lower()
            if hostname not in ("localhost", "127.0.0.1", "testserver"):
                raise ValueError("Seules les URL sécurisées https:// sont acceptées.")

        if not parsed.netloc:
            raise ValueError("L'URL de la vidéo est invalide.")

        return cleaned

    @field_validator("video_authorization_confirmed")
    @classmethod
    def validate_video_authorization(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "Vous devez confirmer disposer des droits et autorisations nécessaires pour "
                "transmettre cette vidéo à VISION-BALLING et demander son analyse, "
                "notamment lorsque des sportifs identifiables ou mineurs y apparaissent."
            )
        return v

    @field_validator("temporary_storage_consent")
    @classmethod
    def validate_storage_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Vous devez accepter la conservation temporaire pour analyse.")
        return v


class BetaAnalysisRequestResponse(BaseModel):
    id: str
    created_at: str
    status: str
    message: str
