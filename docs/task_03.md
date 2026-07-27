# 📋 Fiche Technique : Tâche T-03 — Setup de l'Environnement Backend & FastAPI (Découpée)

Cette fiche spécifie le plan d'action détaillé pour l'initialisation et la validation de l'environnement backend de Football IQ Assistant.

---

## 🎯 1. Vue d'Ensemble
L'objectif est d'installer l'architecture logicielle du serveur backend en 4 sous-tapes logiques (T-03A à T-03D) pour garantir la robustesse de l'environnement Python et la validation immédiate de l'architecture par des tests.

---

## 🛠️ 2. Découpage en Sous-Tâches

### 📌 Sous-tâche T-03A : Démarrage FastAPI Minimal
* **Objectif :** Créer un environnement virtuel Python propre et lancer un serveur FastAPI de base exposant une route de test minimal.
* **Fichiers concernés :**
  - `[NEW] backend/requirements.txt` : Dépendances de base (`fastapi`, `uvicorn`, `pytest`, `httpx`).
  - `[NEW] backend/app/main.py` : Route de santé `/api/health` minimaliste.
* **Dépendances :** Aucune.
* **Temps estimé :** 30 minutes.
* **Critères de validation :**
  - Le serveur tourne localement via `uvicorn app.main:app --port 8000`.
  - La commande `curl http://localhost:8000/api/health` renvoie un HTTP 200 avec le statut.

---

### 📌 Sous-tâche T-03B : Configuration `.env` & Validation OpenAI
* **Objectif :** Mettre en place la gestion sécurisée des configurations et variables d'environnement via Pydantic Settings. Valider la connexion de test vers l'API OpenAI.
* **Fichiers concernés :**
  - `[NEW] backend/.env.example` : Template des variables.
  - `[NEW] backend/.env` : Fichier local contenant la clé API réelle (non suivi par Git).
  - `[NEW] backend/app/config.py` : Configuration de l'application via Pydantic BaseSettings.
  - `[MODIFY] backend/app/main.py` : Validation de la configuration au démarrage (startup event).
* **Dépendances :** T-03A.
* **Temps estimé :** 30 minutes.
* **Critères de validation :**
  - Le serveur refuse de démarrer si `OPENAI_API_KEY` est manquante ou vide (validation Pydantic).
  - La configuration se charge correctement à partir du fichier `.env`.

---

### 📌 Sous-tâche T-03C : Structure Backend Cible
* **Objectif :** Mettre en place l'arborescence complète des modules de l'application conformément aux bonnes pratiques d'une architecture propre (Clean Architecture).
* **Fichiers concernés :**
  - `[NEW] backend/app/__init__.py`
  - `[NEW] backend/app/api/` : Dossier pour les contrôleurs / routes de l'API.
  - `[NEW] backend/app/services/` : Dossier pour la logique métier (RAG, Chat, PDF).
  - `[NEW] backend/app/core/` : Dossier pour la configuration, les prompts et la sécurité.
  - `[NEW] backend/tests/` : Dossier pour les tests unitaires et d'intégration.
* **Dépendances :** T-03B.
* **Temps estimé :** 30 minutes.
* **Critères de validation :**
  - L'arborescence des dossiers et des fichiers d'initialisation Python (`__init__.py`) est créée et fonctionnelle.
  - Les imports relatifs au sein du module `app` fonctionnent sans erreur.

---

### 📌 Sous-tâche T-03D : Validation de l'Architecture (Tests de base)
* **Objectif :** Écrire et exécuter la suite de tests automatisés validant la santé du serveur, le bon chargement des configurations et la politique CORS (Cross-Origin Resource Sharing).
* **Fichiers concernés :**
  - `[NEW] backend/tests/conftest.py` : Fixtures pytest (client HTTP, configuration de test).
  - `[NEW] backend/tests/test_health.py` : Validation de la route `/api/health`.
  - `[NEW] backend/tests/test_config.py` : Validation de la validation des variables d'environnement.
* **Dépendances :** T-03C.
* **Temps estimé :** 30 minutes.
* **Critères de validation :**
  - L'exécution de `pytest backend/` renvoie un succès à 100% (tous les tests passent).
  - Les en-têtes CORS (Access-Control-Allow-Origin) sont présents dans les réponses du serveur pour autoriser le futur frontend.

---

## 🏁 3. Definition of Done (DoD) pour Task T-03
1. La commande `pytest backend/` s'exécute avec succès.
2. L'application démarre localement sans aucune erreur d'importation ou de configuration.
3. Les modifications sont poussées et committées dans le dépôt Git local sous le répertoire du projet.
