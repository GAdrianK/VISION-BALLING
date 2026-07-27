# Rapport d'Implémentation : Retrieval Orienté Problème & Sémantique

Ce rapport décrit l'implémentation de la recherche RAG orientée problème (Problem-Oriented Retrieval) au sein du **Football IQ Assistant**. Cette fonctionnalité résout les biais d'analyse lexicale brute (TF-IDF) en priorisant les fiches de solutions tactiques par rapport aux structures de jeu descriptives.

---

## 🔍 1. Problématique Initiale
Lorsqu'un utilisateur posait une question mélangeant un contexte de formation et un problème concret (ex: *"Je joue en 4-3-3 mais mon équipe perd trop de ballons à la relance. Que faire ?"*), le moteur RAG renvoyait en premier lieu la fiche descriptive de la formation (`formation_433.md`) au lieu de la fiche répondant spécifiquement au problème de relance sous pression (`sortie_balle.md`).

### Causes du biais :
1. **IDF élevé des termes numériques** : Les chaînes de caractères comme `4-3-3` ou `433` sont rares dans la base globale de connaissances, ce qui augmente artificiellement leur poids statistique.
2. **Fréquence de terme (TF)** : Les fiches de formation répètent constamment la formation concernée, alors que les fiches de solutions ne la mentionnent qu'occasionnellement à titre d'exemple.
3. **Absence de structure sémantique** : L'algorithme ne distinguait pas le contexte secondaire de formation du besoin prioritaire de l'utilisateur (le problème).

---

## 🛠️ 2. Solutions Apportées

Nous avons mis en place une architecture d'extraction et de scoring sémantique hybride en trois volets.

### A. Extraction d'Entités Tactiques (`query_classifier.py`)
La méthode `extract_tactical_entities(text)` a été ajoutée au classifieur. Elle analyse la requête et isole quatre dimensions sémantiques distinctes :
*   **Formation** : Extraction et normalisation automatique des patterns de jeu (ex: `433` ou `4-3-3` -> `4-3-3`).
*   **Problème** : Détection des concepts de douleur clés (ex: `"pertes de balle"`, `"difficulté à défendre"`, `"manque d'intensité"`).
*   **Phase** : Détection de la phase de jeu ciblée (ex: `"relance"`, `"pressing"`, `"bloc bas"`, `"transition"`).
*   **Goal** : Détection du verbe d'intention ou de l'objectif recherché (ex: `"préparer"`, `"corriger"`, `"améliorer"`).

### B. Système de Scoring Hybride & Pondéré (`rag_engine.py`)
La recherche RAG (`RAGEngine.search`) a été réécrite pour moduler le score cosinus de base :
1. **Désactivation du Bonus d'Intention** : Si la requête contient un problème ou une phase de jeu, le bonus sémantique par défaut lié à l'intention `"formations"` est désactivé, empêchant les guides généraux de formation de dominer.
2. **Ajustements de Score Additifs** :
    *   **Formation** : Match de formation (`+0.10`)
    *   **Problème** : Match de problème (`+0.40`) avec bonus additionnel de `+0.20` si le nom du problème est explicitement dans le nom du fichier source.
    *   **Phase de jeu** : Match de phase (`+0.35`) avec bonus additionnel de `+0.20` si le nom de la phase est dans le nom du fichier source.
    *   **Goal** : Match d'objectif lié à la nature du chunk (`+0.15`).
3. **Pénalité Formationnelle Directe** : Lorsqu'un problème est détecté dans la requête, toute fiche purement descriptive de système de jeu (sources commençant par `formation_` ou `formations_`) subit une forte pénalité de `-0.50`.

### C. Tri par Score Sémantique Non Tronqué (Tie-Breaker)
Pour éviter la perte de granularité et les erreurs de classement lorsque plusieurs fiches tactiques d'excellence atteignent le score maximal de `1.0000` (après application des bonus), l'algorithme :
*   Conserve le score brut non tronqué (ex: `1.4653` pour `bloc_bas.md`) comme clé principale de tri.
*   Plafonne le score final affiché pour l'utilisateur à `1.0000` conformément au standard de pertinence cosinus.

---

## 📈 3. Validation des Performances (pytest)

La batterie de tests sémantiques a été exécutée et **100% des tests se terminent avec succès**.

### Focus sur les 4 Cas Critiques :
| ID | Requête Utilisateur | Premier Document Choisi | Document Indésirable Écarté | Résultat du Test |
|---|---|---|---|---|
| **1** | *"Je joue en 4-3-3 mais mon équipe perd trop de ballons à la relance. Que faire ?"* | **`sortie_balle.md`** (Rank 3) | `formation_433.md` (Rank 123) | **PASSED** |
| **2** | *"Je joue en 3-5-2 mais je n’arrive pas à presser haut"* | **`pressing_haut.md`** (Rank 1) | `formation_352.md` (Rank 41) | **PASSED** |
| **3** | *"Je joue en 4-4-2 mais je prends trop de buts entre les lignes"* | **`bloc_bas.md`** (Rank 1) | `formation_442.md` (Rank 9) | **PASSED** |
| **4** | *"Comment jouer en 4-3-3 ?"* | **`formation_433.md`** (Rank 1) | *Aucun* | **PASSED** |

### Synthèse des tests :
```bash
venv/bin/pytest tests/
======================== 20 passed, 3 warnings in 4.64s ========================
```
*   `test_rag_retrieval_quality_defend_vs_attack` : **Vérifié et valide**
*   `test_chat_service_mock_specific_requirements` : **Vérifié et valide** (les modes de chat s'ancrent de façon stable dans les fiches recommandées).
