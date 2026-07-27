from pydantic import BaseModel, Field
from typing import List, Optional

class OrganisationOffensive(BaseModel):
    creation: str = Field(..., description="Création d'occasions et dynamique d'attaque")
    espaces: str = Field(..., description="Exploitation des espaces (ex: demi-espaces / half-spaces)")
    largeur: str = Field(..., description="Occupation de la largeur du terrain (ailiers, pistons)")
    profondeur: str = Field(..., description="Attaque de la profondeur et courses dans le dos")

class OrganisationDefensive(BaseModel):
    bloc: str = Field(..., description="Hauteur et comportement du bloc défensif (bas, médian, haut)")
    compacite: str = Field(..., description="Compacité horizontale et verticale")
    duels: str = Field(..., description="Gestion des duels individuels, intensité physique")
    couverture: str = Field(..., description="Couvertures mutuelles, compensations et glissements")

class Transitions(BaseModel):
    offensive: str = Field(..., description="Transition offensive (projection, contre-attaque, jeu direct)")
    defensive: str = Field(..., description="Transition défensive (repli défensif, contre-pressing / gegenpressing)")

class Pressing(BaseModel):
    intensite: str = Field(..., description="Intensité du pressing, déclencheurs (triggers) de pression")
    zones: str = Field(..., description="Zones préférentielles de pressing (haut, médian, bas)")

class Construction(BaseModel):
    relance: str = Field(..., description="Sortie de balle depuis le gardien/défenseurs centraux")
    progression: str = Field(..., description="Progression du ballon à travers les lignes adverses")

class Couloirs(BaseModel):
    ailes: str = Field(..., description="Rôle et animation des ailiers/latéraux dans les couloirs")
    centres: str = Field(..., description="Fréquence, qualité et types de centres (tendus, en retrait)")

class Milieu(BaseModel):
    domination: str = Field(..., description="Contrôle physique ou technique du milieu de terrain")
    creation: str = Field(..., description="Création et orientation du jeu depuis l'axe central")

class Occasions(BaseModel):
    qualite: str = Field(..., description="Qualité des tirs créés et volume de xG")
    volume: str = Field(..., description="Volume et fréquence globale des tirs tentés")

class JoueurCle(BaseModel):
    nom: str = Field(..., description="Nom complet du joueur clé")
    impact: str = Field(..., description="Contribution tactique majeure dans le match")
    erreurs: Optional[str] = Field(None, description="Erreurs commises ou zones de vigilance identifiées")

class Recommandations(BaseModel):
    axes_travail: List[str] = Field(..., description="Axes de travail prioritaires pour l'équipe")
    exercice_entrainement: str = Field(..., description="Description détaillée d'un exercice terrain adapté pour corriger les faiblesses")

class TacticalReportSchema(BaseModel):
    titre: str = Field(..., description="Titre professionnel du rapport tactique")
    match_ou_sujet: str = Field(..., description="Sujet ou match analysé (ex: Paris Saint-Germain vs Olympique de Marseille)")
    organisation_offensive: OrganisationOffensive
    organisation_defensive: OrganisationDefensive
    transitions: Transitions
    pressing: Pressing
    construction: Construction
    couloirs: Couloirs
    milieu: Milieu
    occasions: Occasions
    joueurs_cles: List[JoueurCle]
    recommandations: Recommandations
