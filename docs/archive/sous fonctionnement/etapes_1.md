# 📋 Football IQ Assistant — Étape 1 : Cadrage & Définition Produit

---

## 🎯 1. Vision & Objectif Global

> **Objectif :** Fournir un outil complet d'analyse et de préparation de match pour les coachs, analystes, et fans/créateurs de contenu.
>
> **Promesse utilisateur :** *"Pose une question football, obtiens une réponse tactique claire, structurée et exploitable."*

### 💡 Exemples de requêtes :
* 🛡️ **Tactique bloc bas :** *"Comment battre une équipe en 4-4-2 bloc bas ?"*
* 🏃 **Entraînement :** *"Crée une séance pour travailler la sortie de balle."*
* 📐 **Rôle tactique :** *"Explique le rôle du numéro 6 dans un 3-2-5."*
* 📊 **Analyse comparative :** *"Compare Rodri et Busquets dans la première relance."*
* ⚔️ **Plan de match :** *"Prépare un plan de match contre une équipe qui presse haut."*

---

## ⚙️ 2. Les 3 Modes Utilisateurs

Chaque mode répond à un besoin spécifique avec un comportement de l'IA adapté.

| Mode | But Principal | Fonctions Clés |
| :--- | :--- | :--- |
| **📋 Coach** | Produire des éléments directement utilisables sur le terrain | ⏱️ Créer une séance d'entraînement<br>📝 Préparer un match<br>🔍 Analyser un problème tactique<br>🗣️ Donner des consignes simples aux joueurs<br>📊 Générer un rapport coach |
| **📊 Analyste** | Fournir une analyse tactique et technique approfondie | 🧠 Analyse tactique globale<br>⚖️ Comparaison de joueurs<br>📐 Analyse de systèmes<br>🕵️ Scouting détaillé<br>📖 Explication de concepts avancés |
| **📱 Fan & Créateur** | Vulgarisation et **création de contenu réseaux sociaux** | 💡 Expliquer simplement un concept<br>🧵 **Générer des threads (X/Twitter)**<br>🎬 **Créer des scripts de posts (TikTok, Instagram)**<br>🥊 Comparer pour alimenter des débats<br>💬 Répondre aux débats football populaires |

---

## ✍️ 3. Formats de Sorties Obligatoires

L'IA ne doit **jamais** répondre sous forme de texte brut désorganisé. Chaque mode possède une structure de réponse fixe pour maximiser la clarté.

### 📋 Format Coach
1. **Résumé rapide** (Ce qu'il faut retenir)
2. **Analyse** (L'explication tactique)
3. **Conseils terrain** (Consignes claires pour les joueurs)
4. **Exercice recommandé** (Description de l'exercice terrain)
5. **Points d’attention** (Les clés de réussite)

### 📊 Format Analyste
1. **Contexte** (Pourquoi on en parle)
2. **Principes tactiques** (Les fondements du jeu)
3. **Mécanismes clés** (Comment ça s'articule en phase offensive/défensive)
4. **Limites** (Les failles du système/profil)
5. **Exemples** (Équipes ou joueurs réels)

### 📱 Format Fan & Créateur
1. **Réponse simple** (La vulgarisation)
2. **Exemple connu** (Pour que tout le monde comprenne)
3. **Pourquoi c’est important** (L'impact sur le jeu)
4. **Version réseaux sociaux** (Format court et accrocheur optimisé pour X, Instagram, TikTok)

---

## 🚀 4. Définition du MVP (Périmètre V1)

Pour garantir un développement rapide et percutant, le périmètre est strictement délimité.

### ✅ Inclus dans le MVP :
* **Interface propre & moderne** (Dark mode, design fluide).
* **Sélecteur de mode** (Coach, Analyste, Fan/Créateur) réactif.
* **RAG Football** (Base documentaire tactique).
* **Réponses structurées** (respectant les formats ci-dessus).
* **Sources visibles** sous chaque réponse.
* **Boutons d'action rapide** (Générer post, Exporter PDF, Simplifier, Approfondir).
* **Export de rapport** au format PDF.

### ❌ Exclus du MVP (Évolutions Futures) :
* 📹 Analyse vidéo automatique (upload de matchs).
* 🏃 Tracking de joueurs et détection de ballon.
* 🗺️ Heatmap automatique.
* 🧠 Modèle entraîné *from scratch*.

---

## 📄 5. Document de Définition Produit (`docs/product_definition.md`)

*Ce bloc de texte définit la fiche produit officielle à intégrer dans le dossier `docs/`.*

```markdown
# Football IQ Assistant

## Vision
Créer une interface IA spécialisée football pour aider les coachs, les analystes, ainsi que les passionnés et créateurs de contenu à décrypter le jeu et à produire des supports clairs et professionnels.

## Problème
Les coachs amateurs et les passionnés n’ont pas accès facilement à une analyse football claire, exploitable, structurée et contextualisée. Les créateurs de contenu manquent d'outils pour transformer rapidement des concepts tactiques en posts engageants.

## Solution
Une application RAG football complète avec plusieurs modes adaptés (Coach, Analyste, Fan) et des outils de génération de contenu en un clic.

## Cibles
- **Cible principale :** Le coach amateur / semi-professionnel souhaitant professionnaliser ses séances.
- **Cible secondaire :** Les passionnés de tactique et les **créateurs de contenu football** sur les réseaux sociaux (X, Instagram, TikTok, YouTube).

## Fonctionnalités V1
- Chat football spécialisé.
- 3 modes de réponse adaptés (Coach, Analyste, Fan/Créateur).
- Réponses structurées avec sources documentaires visibles.
- Génération automatique de rapports d'analyse.
- Création de fiches de séances d'entraînement.
- Comparaison tactique de joueurs et de systèmes.
- Outils de conversion rapide en posts pour les réseaux sociaux.

## Fonctionnalités futures
- Upload vidéo & Détection d'événements.
- Découpage automatique de clips vidéo.
- Génération automatisée de heatmaps tactiques.
```
