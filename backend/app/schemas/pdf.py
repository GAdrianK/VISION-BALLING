from typing import List, Optional
from pydantic import BaseModel, Field

class PDFBlock(BaseModel):
    title: str = Field(..., description="Le titre de l'exercice ou de l'étape tactique (ex: Échauffement)")
    content: str = Field(..., description="Le contenu détaillé ou les consignes tactiques associées")

class PDFExportRequest(BaseModel):
    title: str = Field(..., description="Le titre principal de la fiche d'entraînement (ex: Travailler le pressing haut)")
    coach: Optional[str] = Field(default="Coach Football IQ Assistant", description="Le nom de l'entraîneur responsable de la séance")
    date: Optional[str] = Field(default=None, description="La date de la séance (optionnelle, sera générée automatiquement si vide)")
    blocks: List[PDFBlock] = Field(..., description="La liste des blocs ou exercices constituant la séance")
