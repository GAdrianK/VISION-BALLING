# 🏛️ Architecture de la Base de Connaissances Tactique — Football IQ

Ce document définit la stratégie d'organisation, la taxonomie de dossiers, la politique de métadonnées et la modélisation RAG pour étendre notre base de connaissances afin de couvrir plus de 80% des questions utilisateurs.

---

## 🔍 1. Analyse Structurée des 300 Questions Utilisateurs

L'analyse des 300 questions (Coach, Analyste, Fan) révèle 12 grappes thématiques (clusters) de connaissances nécessaires. Chaque cluster exige des documents spécifiques et des métadonnées adaptées pour optimiser la pertinence de la recherche (RAG).

### Cartographie des Clusters et Besoins RAG

| Cluster | Connaissances Clés Requises | Métadonnées Clés | Type de Fiches Recommandé |
| :--- | :--- | :--- | :--- |
| **Pressing & Bloc Haut** | Lignes de passe, déclencheurs (triggers), rest defense, PPDA, press-traps. | `phase: defensive`, `intensity: high` | Concept & Fiche Pratique |
| **Bloc Bas & Défense** | Coulissement, compacité, couverture mutuelle, gestion des centres, zone vs indiv. | `phase: defensive`, `intensity: low` | Concept & Consignes Terrain |
| **Transitions** | Règle des 6s, contre-attaque rapide, tactical foul, rest defense, réorganisation. | `phase: transition` | Fiche Pratique & Schémas |
| **Animation Offensive** | Half-spaces, passes de 3e homme, fixation, supériorité numérique, circuits de passes. | `phase: offensive` | Concept & Exercices |
| **Systèmes & Formations** | Modèles géométriques (3-5-2, 4-3-3, WM), hybridation (défendre en 4, attaquer en 3). | `topic: formations` | Fiches Formations Dédiées |
| **Rôles des Joueurs** | Mezzala, inverted fullback, regista, raumeuter, faux 9, target man, sentinelle. | `topic: player_roles` | Profils de Poste |
| **Séances d'Entraînement** | Progressions pédagogiques, rondos, jeux réduits, minutage, U15 vs Seniors. | `topic: training` | Fiches Exercices (PDF-ready) |
| **Analyse Adverse** | Profils de vitesse, points faibles gardien, détection vidéo de schémas. | `topic: analysis` | Grilles méthodologiques |
| **Physique & Performance** | HIR (High Intensity Running), RSA, GPS, fatigue tactique, charge métabolique. | `topic: performance` | Fiches Concepts Scientifiques |
| **Histoire de la Tactique** | Catenaccio, Total Football, Sacchi, Guardiola, Diniz (Relationnisme), WM. | `topic: history` | Fiches de Synthèse Historique |
| **Règles & VAR** | Hors-jeu de position, main dans la surface, 5 changements (impact tactique). | `topic: rules` | Fiches explicatives simplifiées |
| **Analyse en Direct** | Réorganisation à 10, réaction face à un press-trap, changement de gardien. | `topic: live` | Fiches tactiques de contingence |

---

## 📂 2. Taxonomie et Architecture des Dossiers

La racine de la base de connaissances `knowledge_base/` est organisée en 12 sous-dossiers thématiques stricts :

```
knowledge_base/
├── coaching/              # Méthodologie, causeries, psychologie, management
├── tactics/               # Principes collectifs (pressing, bloc bas, transitions)
├── formations/            # Fiches de systèmes de jeu (4-3-3, 3-5-2, etc.)
├── player_roles/          # Profils détaillés par poste moderne (mezzala, regista...)
├── training_sessions/     # Exercices prêts à l'emploi (rondos, jeux réduits)
├── match_preparation/     # Analyse adverse, plans de contingence, météo
├── opponent_analysis/     # Grilles d'évaluation, déchiffrage vidéo, détection de patterns
├── football_history/      # Évolutions historiques (Catenaccio, Total Football...)
├── competitions/          # Spécificités tactiques des ligues (PL vs Liga, UCL)
├── player_profiles/       # Études de cas (Busquets, Müller, Pirlo...)
├── modern_analysis/       # Métriques avancées (xG, xT, PPDA, Pitch Control)
└── glossary/              # Lexique complet des termes tactiques
```

---

## 🏷️ 3. Spécifications des Métadonnées & Nomenclature

Pour maximiser la pertinence du RAG hybride, chaque fichier Markdown doit intégrer un bloc YAML front-matter avec des métadonnées standardisées.

### Schéma de Métadonnées
```yaml
---
id: [code-unique-document] # ex: TAC-PRE-001
title: "Titre précis du document"
category: "tactics | formations | player_roles | coaching | etc."
phase: "offensive | defensive | transition | multi"
intent: "attack | defend | transition | analysis | education"
tags: ["pressing", "bloc-bas", "half-spaces", "rondo"]
difficulty: "beginner | intermediate | advanced"
---
```

### Règle de Nomenclature des Fichiers
Chaque fichier doit être nommé selon le format :  
`[categorie]_[phase_ou_concept]_[sujet_tactique].md`  
*Exemples :*
- `tactics_defensive_pressing_haut.md`
- `formations_multi_352_animation.md`
- `player_roles_offensive_mezzala.md`

---

## 📚 4. Identification des Meilleures Sources de Données

Pour rédiger des fiches de haute qualité et précises sur le plan professionnel, les sources suivantes doivent être utilisées pour l'extraction de contenu :

1. **FIFA Training Centre** : La référence absolue pour les exercices officiels de la FIFA et les tendances de développement des jeunes.
2. **UEFA Coach Education & Technica Reports** : Rapports de tournois majeurs (UCL, Euro) décortiquant l'évolution tactique des blocs et des transitions.
3. **The Coaches' Voice (CV Academy)** : Analyses approfondies rédigées par des coachs professionnels, explications de systèmes et plans de jeu réels.
4. **StatsBomb, Opta & Wyscout Blogs** : Pour la partie métriques avancées (xG, xT, PPDA, rest defense en données).
5. **Livres et Ouvrages de Référence** :
   - *Inverting the Pyramid* (Jonathan Wilson) — pour la partie histoire.
   - *Juego de Posición* (Pep Guardiola's tactical diaries).
   - *La défense de zone* (Arrigo Sacchi).
