# VISION-BALLING : Fiche Système & Carte du Projet (Project Card)

**Identifiant du Système :** VISION-BALLING Multimodal Match Intelligence System  
**Version :** `v0.9.0-rc1` (Release Candidate 1)  
**Date d'émission :** Octobre 2026  
**Type :** Système hybride de Vision par Ordinateur, Géométrie Tactique et RAG Multimodal Ancré  
**Licence Globale :** Apache-2.0 (avec isolation subprocess de composants tiers GPL-2.0)  

---

## 1. Description du Système

VISION-BALLING traite des enregistrements vidéo de matchs de football pour générer des représentations métriques géométriques au sol (105 m $\times$ 68 m), quantifier les dynamiques collectives (hauteur de bloc, compacité d'équipe, pression continue sur le porteur, transitions et contre-pressing) et produire des rapports d'analyse vérifiables où chaque affirmation est formellement liée à une fiche de preuve horodatée.

---

## 2. Utilisations Visées & Hors-Périmètre (Intended & Out-of-Scope Use)

### Utilisations visées
- **Assistance aux analystes vidéo et tacticiens de clubs de football** pour accélérer le séquençage post-match.
- **Audit quantitatif de style de jeu** : mesure objective des blocs défensifs, intensité de pressing et compacité.
- **Vérification d'affirmations journalistiques ou de scouting** appuyée par des fiches d'événements géoréférencées.

### Utilisations hors-périmètre et non autorisées
- **Arbitrage automatique en direct (VAR)** : le système n'est ni certifié FIFA, ni infaillible au millimètre près.
- **Décisions contractuelles ou de carrière automatisées** sur des joueurs sans supervision humaine.
- **Traitement de caméras mobiles non calibrées** (ex. caméras de smartphone en tribune, caméras drones instables).
- **Attribution d'étiquettes de formation nominales (4-3-3, etc.)** : formellement exclue en raison de la troncation de champ des caméras TV.

---

## 3. Données & Protocole d'Évaluation

- **Détection des Objets** : Dataset H250 (5 834 images annotées). Partitions : Train (2 842), Dev (300), Test/Holdout (2 692).
- **Tracking & Tactique** : 12 séquences SoccerNet Tracking 2023 (SNMOT-060 à SNMOT-071), partitionnées en DEV (060-062), VALIDATION (063-068), HOLDOUT (069-071).
- **Évaluation RAG** : 76 scénarios standardisés couvrant la précision des faits, la contextualisation temporelle, l'explication causale et l'abstention motivée.

---

## 4. Métriques de Performance Clés

| Domaine | Métrique Principale | Score Validé |
| :--- | :--- | :--- |
| **Détection Joueurs & Ballon** | mAP50 / mAP50-95 (RF-DETR @ 960px) | **0.865 / 0.618** |
| **Association Multi-Objets** | IDF1 (BoT-SORT + PRTReID) | **75.8 %** |
| **Coût Inférence ReID** | Réduction d'appels par gating conditionnel | **-68 %** |
| **Classification d'Équipe** | Exactitude non supervisée CIE-Lab | **96.2 %** |
| **Calibration Terrain** | Erreur de reprojection / IoU terrain | **3.2 px / 88.5 %** |
| **Contrôle & Possession** | F1 Identification du porteur (V2 vs V1) | **+21 %** |
| **Pression Défensive** | Monotonie physique et absence de seuil discret | **100 %** |
| **Grounding RAG Match** | Supported Claim Rate / Match Hallucination | **100 % / 0 %** |
| **Débit Pipeline Plein** | Throughput effectif (Quality / Low Latency) | **11.4 FPS / 24.2 FPS** |

---

## 5. Limites et Facteurs d'Incertitude

1. **Troncation du Champ de Vision (FOV)** : La caméra de retransmission télévisuelle standard ne montre pas l'ensemble des 22 acteurs simultanément. Les métriques globales portent uniquement sur les joueurs visibles.
2. **Planarité du Ballon ($Z = 0$)** : Les trajectoires de balle aériennes présentent une distorsion de projection 2D due à la parallaxe.
3. **Temps Réel Strict Non Garanti** : Le pipeline complet ne garantit pas 25 FPS constants sans infrastructure dédiée.
4. **Licence PnLCalib (GPL-2.0)** : Exige une isolation subprocess stricte ou l'utilisation de TVCalib (MIT) pour un déploiement commercial permissif.

---

## 6. Considérations Éthiques & Épistémologiques

- **Discipline "Zéro Hallucination"** : Le LLM ne peut émettre aucune affirmation sur le déroulement du match sans citer une preuve observée (`[REF-TIMESTAMP-ID]`). En l'absence de preuve, il pratique l'abstention explicite.
- **Transparence des Sources** : Toute métrique affichée est directement traçable jusqu'aux coordonnées métriques calculées sur les images vidéo sources.
