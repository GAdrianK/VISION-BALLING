import re

# Dictionnaire de normalisation pour le jargon de football
JARGON_NORMALIZATION = {
    r"\barrière[ -]latéral\b": "latéral",
    r"\barrière[ -]gauche\b": "latéral gauche",
    r"\barrière[ -]droit\b": "latéral droit",
    r"\btrequartista\b": "meneur de jeu",
    r"\bregista\b": "milieu reculé",
    r"\bhalf[ -]spaces?\b": "demi-espace",
    r"\bhalf[ -]espace\b": "demi-espace",
    r"\bdemi[ -]espaces?\b": "demi-espace",
    r"\blow[ -]block\b": "bloc bas",
    r"\blowblock\b": "bloc bas",
    r"\bcounter[ -]pressing\b": "contre-pressing",
    r"\bcounterpressing\b": "contre-pressing",
    r"\bgegenpress\b": "contre-pressing",
    r"\bgegenpressing\b": "contre-pressing",
    r"\bailier[ -]inverse\b": "ailier inversé",
    r"\blateral[ -]inverse\b": "latéral inversé",
    r"\blatéral[ -]inverse\b": "latéral inversé",
}

# Lignes publicitaires ou boilerplate typiques des sites de sport à supprimer
AD_PATTERNS = [
    r"^publicité\b",
    r"^partager sur\b",
    r"^lire aussi\b",
    r"^cliquez ici pour\b",
    r"^abonnez-vous\b",
    r"^suivez-nous sur\b",
    r"^inscrivez-vous à\b",
    r"^retrouvez l'article original sur\b"
]

def clean_html(text: str) -> str:
    """
    Supprime les balises HTML, les blocs de script et de style.
    """
    # Enlever les balises de scripts et styles avec leur contenu
    text = re.sub(r"<(script|style|iframe)[^>]*>([\s\S]*?)<\/\1>", "", text, flags=re.IGNORECASE)
    # Enlever toutes les autres balises HTML
    text = re.sub(r"<[^>]*>", "", text)
    return text

def clean_ads_and_boilerplate(text: str) -> str:
    """
    Supprime les lignes publicitaires ou promotionnelles courantes.
    """
    lines = text.split("\n")
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        # Ignorer les lignes vides
        if not stripped:
            cleaned_lines.append(line)
            continue
            
        # Vérifier si la ligne correspond à un pattern de publicité
        is_ad = False
        for pattern in AD_PATTERNS:
            if re.search(pattern, stripped, re.IGNORECASE):
                is_ad = True
                break
                
        if not is_ad:
            cleaned_lines.append(line)
            
    return "\n".join(cleaned_lines)

def normalize_jargon(text: str) -> str:
    """
    Normalise le jargon footballistique vers une terminologie uniforme.
    """
    for pattern, replacement in JARGON_NORMALIZATION.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

def clean_text(text: str) -> str:
    """
    Pipeline complet de nettoyage pour un texte brut.
    """
    # 1. Nettoyer le HTML
    text = clean_html(text)
    # 2. Supprimer les publicités et les lignes de boilerplate
    text = clean_ads_and_boilerplate(text)
    # 3. Normaliser le jargon
    text = normalize_jargon(text)
    # 4. Nettoyer les espaces multiples et sauts de ligne excessifs
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()
