# 📐 Cadre de Génération des Documents Tactiques — Football IQ

Ce document définit les normes, la structure technique, les métadonnées et la charte éditoriale pour la génération automatique et cohérente des fiches tactiques de notre base de connaissances (RAG).

---

## 🎯 1. Principes de Conception RAG & Qualité

Pour assurer une recherche RAG optimale (hybride et lexicale) et des réponses de haute qualité de la part du LLM, chaque document doit obéir à trois règles d'or :

1. **Compacité et densité informative** : Les documents doivent faire entre **400 et 800 mots**. Les formulations doivent être directes, éliminant tout bavardage inutile pour économiser la fenêtre de contexte du LLM.
2. **Richesse lexicale (Mots-clés RAG)** : Chaque fiche doit inclure un lexique de synonymes et de termes associés (français/anglais) pour combler le fossé lexical lors d'une recherche TF-IDF ou vectorielle.
3. **Double niveau de lecture** : Fournir à la fois des explications claires et simplifiées pour les supporters (concept général) et des exercices ou détails précis pour les coachs et analystes.

---

## 🏷️ 2. Structure Technique : YAML Front-Matter

Chaque document **doit obligatoirement** commencer par le bloc de métadonnées YAML suivant :

```yaml
---
title: "Titre exact de la fiche tactique (ex: Le Pressing Haut et ses Déclencheurs)"
topic: "tactics | formations | player_roles | coaching | match_preparation | opponent_analysis | football_history | modern_analysis"
intent: "attack | defend | transition | analysis | education"
phase: "offensive | defensive | transition | multi"
level: "beginner | intermediate | advanced"
audience: "coach | analyst | fan | all"
keywords: ["mot-cle1", "mot-cle2", "synonyme-en-anglais", "concept-proche"]
---
```

### Directives de remplissage des métadonnées :
- **`topic`** : Doit correspondre à l'un des 12 dossiers de l'architecture.
- **`intent`** : Utiliser `defend` pour les concepts défensifs et `attack` pour les concepts offensifs. Cela est utilisé par le `QueryClassifier` du backend pour appliquer le scoring hybride RAG.
- **`phase`** : Indiquer la phase de jeu principale.
- **`level`** : Niveau de complexité tactique.
- **`keywords`** : Liste de 5 à 10 mots clés en minuscules, séparés par des virgules.

---

## 📝 3. Sections Obligatoires du Document

Le corps du fichier Markdown doit obligatoirement suivre le plan suivant, structuré par des titres de niveau 1 (`#`) et niveau 2 (`##`).

### `# Définition`
Description synthétique du concept en 2-3 phrases maximum. Vulgarisation claire accessible au grand public (Fan).

### `# Objectifs`
Liste à puces des 3 à 5 buts tactiques principaux recherchés par ce concept ou ce rôle (ex: réduire le temps de décision adverse, forcer le jeu long).

### `# Principes clés`
Explication détaillée des 3 fondements mécaniques ou géométriques du concept.
- Utiliser des sous-titres de niveau 2 (`##`) pour chaque principe.
- Expliquer précisément le "comment" et le "pourquoi".

### `# Erreurs fréquentes`
Description de 3 erreurs tactiques classiques commises par les équipes ou les joueurs lors de la mise en pratique.

### `# Corrections terrain`
Pour chaque erreur listée ci-dessus, donner la correction directe ou la consigne que le coach doit crier depuis le bord du terrain.

### `# Exemple concret`
Une étude de cas historique ou moderne illustrant parfaitement le concept (ex: le Liverpool de Klopp 2019 pour le contre-pressing, ou le Busquets du FC Barcelone de Guardiola).

### `# Exercice d'entraînement`
Un exercice terrain prêt à l'emploi pour les coachs, formaté ainsi :
- **Nom de l'exercice** (ex: Rondo de transition 4v4+3)
- **Dimensions & Matériel** (ex: carré de 15x15m, 4 coupelles)
- **Consignes & Règles de jeu** (ex: 2 touches maximum, transition à la perte)
- **Variantes** (pour simplifier ou complexifier l'exercice)

### `# Points de vigilance`
Liste des 3 risques tactiques ou physiques inhérents à l'application de ce concept (ex: fatigue rapide des milieux de terrain sur un gegenpress soutenu).

### `# Questions fréquentes`
Une section FAQ contenant 2 à 3 questions typiques qu'un joueur ou un supporter pourrait poser, avec leurs réponses claires et concrètes.

### `# Mots-clés RAG`
Une liste de termes techniques, synonymes et traductions anglaises pour faciliter la recherche sémantique et lexicale dans l'index du RAG. Format brut séparé par des virgules.

---

## 🎨 4. Directives de Rédaction et Style

- **Ton** : Expert, pédagogique et axé sur l'action terrain. Éviter le jargon creux.
- **Formatage** : Utiliser le gras (`**texte**`) pour faire ressortir les termes tactiques clés.
- **Listes** : Utiliser des listes à puces claires pour faciliter le découpage en chunks par le chargeur du RAG.
- **Schémas textuels** : Pour les formations ou exercices, utiliser des diagrammes textuels simples (ex: `4v4+3`) plutôt que des images pour rester lisible par le RAG.
