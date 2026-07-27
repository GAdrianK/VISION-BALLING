# 🗺️ Roadmap Produit & Technique — Football IQ Assistant
**Auteur :** CTO / Vision Stratégique & Exécution

Ce document définit la stratégie de développement par phases du projet **Football IQ Assistant**. Il est conçu pour orienter le travail d'un développeur seul (étudiant) assisté par des IA de code, afin de maximiser l'efficacité budgétaire et les chances d'adoption par les coachs de football.

---

## 🚀 1. Analyse Détaillée par Phase

```mermaid
gantt
    title Programme de Déploiement Football IQ Assistant
    dateFormat  YYYY-MM-DD
    section MVP V1
    Phase 1 : Assistant MVP       :active, p1, 2026-06-08, 60d
    section Expert V2
    Phase 2 : Expert Platform     : p2, after p1, 90d
    section Match V3
    Phase 3 : Match Intelligence : p3, after p2, 90d
    section Video V4
    Phase 4 : Video Intelligence : p4, after p3, 120d
    section SaaS V5
    Phase 5 : Commercial SaaS     : p5, after p4, 90d
```

---

### ⏱️ Résumé des Phases de Développement

| Phase | Objectif Business | Objectif Technique | Fonctionnalités Clés | Dépendances | Risques Majeurs | Complexité | Temps Estimé | Valeur Utilisateur | Critères de Validation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | Valider la valeur d'usage auprès de 50 coachs bêta-testeurs. | RAG local sans base vectorielle lourde, latence < 3s. | Chat 3 modes (Coach, Analyste, Fan), export PDF, prompts système étanches. | Clé API LLM (OpenAI/Anthropic). | Hallucinations tactiques, ton mal ajusté de l'IA. | **Faible** (3/10) | 2 mois | **Élevée** (gain de temps immédiat). | 10 séances générées et validées par un coach pro. |
| **Phase 2** | Engager les coachs en personnalisant l'IA avec les données de leur effectif. | Base SQL (Postgres), gestion d'états d'effectifs, ingestion PDF/txt. | Profils joueurs (force/faiblesse), téléverseur de notes tactiques privées. | Base de données relationnelle. | Ingestion de fichiers mal formatés. | **Moyenne** (5/10) | 3 mois | **Très Élevée** (conseils sur-mesure). | Téléversement réussi de 3 PDF tactiques + réponse IA basée dessus. |
| **Phase 3** | Apporter de la crédibilité analytique via l'analyse de données de match. | Parseur de fichiers d'événements de jeu (JSON/XML) et rendu SVG terrain. | Shot maps, réseaux de passes, rapports d'adversaires automatisés. | Jeux de données de match (JSON de type StatsBomb Open Data). | Complexité des coordonnées spatiales du terrain. | **Moyenne+** (6.5/10) | 3 mois | **Élevée** (visualisation de données). | Rendu correct d'un terrain avec 100 passes tracées en SVG. |
| **Phase 4** | Entrer dans le cœur du métier d'analyste vidéo moderne. | Synchronisation vidéo/données, modèle YOLO local (détection joueurs). | Lecteur vidéo indexé sur les événements, clips d'actions auto (ex: corners). | Serveur de stockage vidéo, GPU pour inférence YOLO. | Coût de calcul GPU, latence de traitement vidéo. | **Élevée** (8.5/10) | 4 mois | **Critique** (le standard de l'industrie). | Clic sur une action -> la vidéo saute à la bonne seconde du match. |
| **Phase 5** | Monétiser l'outil et sécuriser les données des clubs pros. | Multi-tenancy (isolation de données), Stripe, authentification sécurisée. | Abonnements Stripe, comptes d'équipe (partage staff), logs de sécurité. | Stripe API, Auth0/Clerk. | Faible taux de conversion, sécurité des données tactiques privées. | **Moyenne** (5/10) | 3 mois | **Moyenne** (commodités). | Paiement Stripe validé en mode Test + création de compte d'équipe. |

---

### 🔍 Focus Stratégique par Phase

#### PHASE 1 : Football Assistant MVP
*   **Pourquoi elle existe :** Valider l'hypothèse de valeur : *« Les coachs amateurs et créateurs de contenu sont-ils prêts à utiliser une IA pour rédiger leurs séances et leurs posts s'ils n'ont pas besoin d'écrire de prompts compliqués ? »*
*   **Minimum à construire (Strict) :**
    *   Un frontend en chat simple avec un sélecteur de rôle visible (Coach / Analyste / Fan).
    *   Un moteur RAG simple en Python lisant des fichiers Markdown locaux contenant les concepts de jeu (pressing, transition, etc.).
    *   La génération de réponses formatées strictement selon le mode choisi (par exemple : Exercices terrain structurés pour le Coach, ou Script court pour X/TikTok pour le Fan).
    *   Un bouton "Exporter en PDF" pour le coach et "Copier" pour le créateur de contenu.
*   **Ce qu'il faut absolument éviter :**
    *   Créer des comptes utilisateurs, des mots de passe ou des profils d'équipes.
    *   Mettre en place une base de données vectorielle complexe (ex: Pinecone/weaviate). Un simple script python qui extrait les termes clés ou fait un cosinus de similarité avec des embeddings locaux stockés dans un fichier JSON suffit pour 50 fichiers.
    *   Tenter d'analyser des vidéos ou de dessiner des schémas animés.
*   **Technologies adaptées :**
    *   *Backend :* Python FastAPI.
    *   *Frontend :* HTML / Vanilla JS ou Next.js ultra-léger (sans base de données).
    *   *IA / RAG :* API OpenAI (GPT-4o) ou Anthropic (Claude 3.5 Sonnet). Utilisation de `chromadb` local ou d'une simple recherche par similarité cosinus avec `sentence-transformers` en local.
*   **Métriques de succès :**
    *   Nombre de séances d'entraînement exportées en PDF par les utilisateurs bêta (> 100/mois).
    *   Taux de rétention hebdomadaire (WAU / Bêta-testeurs > 30%).

#### PHASE 2 : Football Expert Platform
*   **Pourquoi elle existe :** Résoudre le problème du manque de contexte. L'IA générale ne connaît pas l'effectif du coach (ex: « Mon défenseur droit est lent, comment organiser mon pressing ? »). Cette phase permet d'associer la théorie footballistique aux données réelles de l'utilisateur.
*   **Minimum à construire (Strict) :**
    *   Un écran "Mon Effectif" : Liste simple des joueurs avec leur poste, pied fort, et 3 caractéristiques (Vitesse, Technique, Endurance).
    *   Un téléverseur de fichiers PDF/Textes dans le chat pour ajouter des notes d'observation privées.
    *   Le RAG doit interroger en priorité le contexte de l'équipe avant la base générale.
*   **Ce qu'il faut absolument éviter :**
    *   Développer des statistiques de performance complexes (GPS, charges d'entraînement).
    *   Vouloir gérer des catégories d'âge multiples de façon complexe (U15, U17, Seniors). Rester sur une seule équipe par compte.
*   **Technologies adaptées :**
    *   *Base de données :* PostgreSQL.
    *   *RAG persistant :* PostgreSQL avec l'extension `pgvector` (simple, robuste, standard).
*   **Métriques de succès :**
    *   Pourcentage de questions posées par le coach faisant référence à un joueur de son effectif (> 40%).

#### PHASE 3 : Match Intelligence Layer
*   **Pourquoi elle existe :** Rendre l'outil indispensable pour la préparation de match. Les coachs passent des heures à décortiquer les données de l'adversaire ou de leur propre match. Automatiser la transformation de données brutes en rapports tactiques est une fonctionnalité à forte valeur ajoutée.
*   **Minimum à construire (Strict) :**
    *   Un parseur de données d'événements de match au format JSON (passes, tirs, ballons récupérés).
    *   Génération automatique de graphiques statiques SVG : Carte de tirs (Shot Map) et réseau de passes (Passing Network).
    *   Génération de rapport écrit automatique : Points forts et points faibles identifiés dans la donnée.
*   **Ce qu'il faut absolument éviter :**
    *   Essayer de collecter la donnée soi-même. On utilise des imports de fichiers générés par des plateformes existantes (Wyscout, Hudl) ou des jeux de données libres (StatsBomb).
    *   Créer des animations vidéo ou des schémas interactifs en drag & drop.
*   **Technologies adaptées :**
    *   *Visualisation :* Python `mplsoccer` (bibliothèque de référence pour tracer sur un terrain de foot) exécutée en tâche de fond pour générer des images ou des SVG à intégrer au chat.
*   **Métriques de succès :**
    *   Temps de génération d'un rapport de match inférieur à 10 secondes.

#### PHASE 4 : Video Intelligence
*   **Pourquoi elle existe :** La vidéo est le média roi du football moderne. Un analyste n'utilise pas uniquement du texte ou des stats, il montre des clips vidéo aux joueurs. Synchroniser les statistiques de match avec la vidéo permet de diviser par 10 le temps de montage vidéo.
*   **Minimum à construire (Strict) :**
    *   Un lecteur vidéo HTML5 simple.
    *   La synchronisation temporelle : charger un fichier vidéo de match et son fichier d'événements JSON associé. En cliquant sur une ligne d'événement (ex: "Tir à la 42ème minute"), la vidéo saute directement à la 42ème minute.
    *   Un bouton de découpe automatique (clipping) pour exporter la séquence sélectionnée (de T-5 secondes à T+5 secondes) en format MP4.
*   **Ce qu'il faut absolument éviter :**
    *   Essayer de faire tourner des modèles de Computer Vision lourds sur le navigateur de l'utilisateur. Tout traitement IA lourd (YOLO, tracking) doit être fait de manière asynchrone côté serveur.
    *   Vouloir faire du tracking 3D temps réel. Se limiter à la détection de cadres fixes avec YOLO pour poser des cercles sous les joueurs.
*   **Technologies adaptées :**
    *   *Lecteur :* `video.js` avec des marqueurs personnalisés.
    *   *Découpe vidéo :* `FFmpeg` exécuté côté backend (ultra-rapide pour découper sans ré-encoder).
    *   *Computer Vision :* `Ultralytics YOLOv8` en Python pour la détection de joueurs et du ballon sur des images clés.
*   **Métriques de succès :**
    *   Taux de clics sur la timeline vidéo (> 80% des sessions d'analyse).

#### PHASE 5 : Commercial SaaS Platform
*   **Pourquoi elle existe :** Transformer le projet technique en entreprise viable, capable de facturer les clubs et de protéger les données sensibles.
*   **Minimum à construire (Strict) :**
    *   Système d'abonnements avec 3 formules (Gratuit, Coach Individuel, Club/Staff).
    *   Gestion d'équipe : Un administrateur (Coach principal) peut inviter des collaborateurs (Adjoints, Préparateur physique) à consulter le même effectif et les mêmes rapports.
    *   Chiffrement des données sensibles au repos.
*   **Ce qu'il faut absolument éviter :**
    *   Créer son propre système de facturation.
    *   Viser des marchés hors football (rester ultra-spécialisé pour garder l'avantage concurrentiel).
*   **Technologies adaptées :**
    *   *Authentification :* Clerk ou Auth0 (gère le multi-tenant et la sécurité nativement).
    *   *Paiement :* Stripe Billing + Stripe Checkout.
*   **Métriques de succès :**
    *   Taux de conversion Bêta vers Payant (> 5%).
    *   MRR (Revenu Mensuel Récurrent) en croissance de 15% par mois.

---

## 📅 2. Planification Temporelle

### 🗺️ Roadmap Trimestrielle (Vue Macro)

```
   Trimestre 1 (Q1)                 Trimestre 2 (Q2)                 Trimestre 3 (Q3)                 Trimestre 4 (Q4)
┌──────────────────────────────┐ ┌──────────────────────────────┐ ┌──────────────────────────────┐ ┌──────────────────────────────┐
│  Phase 1 : RAG & Prompt      │ │  Phase 2 : Profils Équipe    │ │  Phase 3 : Parseur Données   │ │  Phase 4 : Sync Vidéo        │
│  - Assistant conversationnel │ │  - Gestion de l'effectif     │ │  - Graphiques de tirs/passes │ │  - Clips auto par événement  │
│  - Prompts stricts par Mode  │ │  - Ingestion de fichiers     │ │  - Rapports d'adversaires    │ │  - Inférence YOLO basique    │
│  - Exports PDF & Réseaux     │ │  - Base de données Postgres  │ │  - Visualisation terrain     │ │  - Début Phase 5 (Stripe)    │
└──────────────────────────────┘ └──────────────────────────────┘ └──────────────────────────────┘ └──────────────────────────────┘
```

---

### 📅 Roadmap Mensuelle (Focus Exécution : Phase 1 & 2)

*   **Mois 1 : Cœur Logique & Prompts (Phase 1)**
    *   *Semaine 1-2 :* Établir le backend FastAPI et connecter les API OpenAI/Anthropic. Rédiger les prompts système (`coach_prompt.txt`, `analyst_prompt.txt`, `fan_prompt.txt`) et les tester manuellement pour valider le ton.
    *   *Semaine 3-4 :* Déployer le RAG local. Mettre en place la lecture de la base documentaire tactique (`pressing.md`, `formations.md`) via une recherche de similarité sémantique simple.
*   **Mois 2 : Interface Utilisateur & Exports (Phase 1)**
    *   *Semaine 1-2 :* Développer le frontend de chat. Intégrer le sélecteur de mode et adapter le style visuel de l'interface en fonction du mode actif.
    *   *Semaine 3-4 :* Implémenter les générateurs d'exports. Créer les boutons de téléchargement de fiches d'entraînement PDF et le bouton de copie rapide des scripts de posts pour les réseaux sociaux. Lancement de la bêta fermée auprès de 20 coachs.
*   **Mois 3 : Base de Données & Effectif (Phase 2)**
    *   *Semaine 1-2 :* Configurer PostgreSQL et concevoir le schéma de base de données (Tables: `users`, `players`, `teams`).
    *   *Semaine 3-4 :* Créer l'interface "Mon Effectif" sur le frontend pour permettre la saisie et l'édition des fiches de joueurs.
*   **Mois 4 : Ingestion de Contexte Privé (Phase 2)**
    *   *Semaine 1-2 :* Développer le système de téléversement de documents (PDF, TXT) pour le coach. Configurer l'extraction de texte côté backend.
    *   *Semaine 3-4 :* Connecter le RAG à cette base de documents utilisateur dynamique (`pgvector`). L'IA doit désormais répondre en croisant la question, l'effectif saisi, les notes téléversées et la théorie générale du football.
*   **Mois 5 : Consolidation & Feedback (Phase 2)**
    *   *Semaine 1-4 :* Phase de test intensive avec 100 utilisateurs. Optimisation des temps de réponse (mise en cache des requêtes RAG récurrentes) et correction des bugs d'interface.

---

## 📋 3. Backlog Priorisé (Prêt pour l'Exécution)

Le tableau suivant représente le backlog initial de développement à fournir à l'IA de code pour démarrer le projet.

| ID Task | Titre de la Tâche | Description Technique | Phase | Priorité | Complexité |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TSK-101** | Init Projet Backend & FastAPI | Configurer le projet Python, installer FastAPI, uvicorn, et structurer les dossiers du backend. | Phase 1 | **Bloquant (P0)** | 1/5 |
| **TSK-102** | Intégration API LLM & Prompts | Créer le connecteur API OpenAI/Anthropic. Charger dynamiquement les fichiers prompts de `/prompts/` selon le mode sélectionné. | Phase 1 | **Bloquant (P0)** | 2/5 |
| **TSK-103** | Moteur RAG Local Init | Implémenter une classe `RAGEngine` qui lit les fichiers Markdown du dossier `data/knowledge_base/`, génère des embeddings locaux et retourne les passages pertinents. | Phase 1 | **Bloquant (P0)** | 3/5 |
| **TSK-104** | UI Chat de Base | Créer l'interface de messagerie en ligne avec affichage des messages utilisateur et IA sous forme de bulles. | Phase 1 | **Bloquant (P0)** | 2/5 |
| **TSK-105** | Sélecteur de Mode Interactif | Ajouter le bouton de sélection triple (Coach, Analyste, Fan). Modifier l'envoi de la requête API pour y joindre le mode actif. | Phase 1 | **Majeur (P1)** | 2/5 |
| **TSK-106** | Export PDF Fiche Séance | Écrire le service de génération de PDF côté backend à partir des réponses structurées du mode Coach. | Phase 1 | **Majeur (P1)** | 3/5 |
| **TSK-107** | Copy-to-Clipboard Réseaux | Ajouter le bouton "Copier le post" sur les réponses en mode Fan pour récupérer directement la version formatée pour X/TikTok. | Phase 1 | **Mineur (P2)** | 1/5 |
| **TSK-108** | Schéma Base de Données SQL | Modéliser et exécuter les migrations Postgres pour stocker les utilisateurs et l'effectif des joueurs. | Phase 2 | **Majeur (P1)** | 2/5 |
| **TSK-109** | UI Gestion de l'Effectif | Développer l'écran permettant au coach d'ajouter, modifier et supprimer des joueurs de son équipe. | Phase 2 | **Majeur (P1)** | 3/5 |
| **TSK-110** | Upload de Fichiers & pgvector | Mettre en place l'API d'upload de fichiers et stocker leurs embeddings dans la table Postgres vectorielle pour enrichir le RAG. | Phase 2 | **Majeur (P1)** | 4/5 |

---

## 🎯 4. Définition des Niveaux de MVP (Minimum Viable Product)

Pour réussir le lancement sans s'épuiser dans des développements inutiles, voici la délimitation stricte entre le MVP Absolu et le MVP Recommandé.

### 🔴 Le MVP Absolu (À construire en 3 semaines maximum pour tester l'idée)
*   **Objectif :** Valider uniquement l'utilité du chat spécialisé par rapport à un ChatGPT classique.
*   **Fonctionnalités :**
    1.  Une interface de chat unique (sans authentification, ouverte).
    2.  Trois boutons en haut : "Mode Coach", "Mode Analyste", "Mode Fan".
    3.  Le prompt système change en arrière-plan selon le bouton cliqué.
    4.  Le modèle de réponse respecte les règles (ex: générer un exercice d'entraînement si Mode Coach).
    5.  Pas de RAG (base de connaissances vide, on fait confiance aux connaissances générales du LLM).
    6.  Bouton "Copier la réponse".

### 🟢 Le MVP Recommandé (La base pour un lancement public crédible)
*   **Objectif :** Offrir une vraie valeur ajoutée introuvable sur un LLM classique grâce à des connaissances exclusives et des documents de club.
*   **Fonctionnalités :**
    1.  Toutes les fonctions du MVP Absolu.
    2.  **RAG local fonctionnel** avec 15-20 fiches de tactique footballistique pointue (pressing de zone, transition offensive, gestion du bloc bas) écrites par des professionnels.
    3.  Affichage clair des **sources documentaires** utilisées pour générer la réponse (ex: *"Source : pressing.md - Section 3 : Pressing haut"*).
    4.  Bouton d'**exportation PDF propre** avec le logo de l'application pour que le coach puisse imprimer sa séance et l'amener sur le terrain.
    5.  Bouton de formatage automatique des scripts vidéo (TikTok/Reels) pour les créateurs.

### 💎 Fonctionnalités Premium Futures (Pour la Phase 5 - Monétisation)
*   **Générateur de schémas tactiques animés :** Transformer une consigne textuelle de l'IA en un petit clip de tableau noir animé en 2D (ex: des ronds bleus qui se déplacent pour montrer le pressing).
*   **Rapports de scouting automatique :** Importation de 5 fichiers de match d'un joueur adverse pour obtenir sa fiche de caractéristiques et sa heatmap.
*   **Partage parents/joueurs :** Une application mobile simplifiée pour que les joueurs reçoivent directement les consignes tactiques et les vidéos préparées par le coach sur leur téléphone.

---

## 🧠 5. Avis Honnête & Recommandations du CTO

> [!IMPORTANT]
> **Scénario : Budget limité à un étudiant seul aidé par des IA de code (Cursor/Claude).**
> Voici l'analyse stratégique et la séquence optimale d'exécution pour maximiser les chances de succès commercial.

### ⚠️ Les Pièges Mortels du Projet (À éviter absolument)

1.  **Vouloir faire de la Computer Vision au début :**
    L'analyse automatique de vidéo (détecter les joueurs, tracer les lignes de passe) est un gouffre technique. Cela demande des compétences en IA lourdes, des serveurs GPU coûteux et des mois de R&D. **Si l'étudiant commence par là, le projet mourra avant d'avoir un seul utilisateur.**
2.  **Créer une usine à gaz SaaS trop tôt :**
    Passer 1 mois à coder le système d'abonnement Stripe, la gestion des rôles utilisateur et l'authentification sécurisée est une perte de temps. Si personne ne veut de l'assistant de chat de base, le système de paiement ne servira à rien.
3.  **Négliger la qualité du contenu footballistique :**
    Les coachs de football repèrent immédiatement les réponses génériques sans valeur (ex: *"faites des passes et courez"*). La valeur du RAG dépend à 100% de la qualité des fichiers documentaires de départ. Si vos fichiers Markdown tactiques sont médiocres, l'IA sera médiocre.

### 🛠️ La Séquence Optimale d'Exécution en Solo

Pour réussir avec un seul développeur assisté par IA, il faut appliquer la méthode **"Value First, Tech Second"** :

```
Étape 1 : Prompts & Contenu (15 jours) ──> Étape 2 : MVP Recommandé Sans DB (20 jours) ──> Étape 3 : Test Terrain (15 jours) ──> Étape 4 : Ingestion Données Équipe (30 jours)
```

1.  **Étape 1 : Le Contenu et les Prompts (15 jours)**
    *   L'étudiant ne code rien au début. Il utilise ChatGPT/Claude pour rédiger 15 fichiers Markdown de très haute qualité sur des principes tactiques précis (ex: le *Gegenpressing*, la défense de zone sur corner, le rôle du numéro 6 hybride).
    *   Il crée les 3 fichiers de prompts système et teste les réponses dans l'interface de test d'OpenAI pour s'assurer que le ton est ultra-professionnel.
2.  **Étape 2 : Le MVP Recommandé sans base de données (20 jours)**
    *   Il utilise une IA de code (Cursor) pour générer l'architecture FastAPI + une interface web minimaliste mais très esthétique (Dark Mode type dashboard).
    *   Il intègre un RAG ultra-simple : lecture des fichiers Markdown locaux en mémoire au démarrage de l'API, recherche par similarité cosinus basique. Pas de base de données à administrer.
    *   Il déploie cette version sur un serveur à 5$/mois (Render ou Railway).
3.  **Étape 3 : Le Test Terrain (15 jours)**
    *   Il donne l'URL à 20-30 coachs amateurs (trouvés sur Twitter/X ou dans des clubs locaux) et observe leur comportement.
    *   *La question clé à poser :* « Est-ce que tu as imprimé un PDF pour ton entraînement cette semaine ? » Si la réponse est oui, vous avez un produit.
4.  **Étape 4 : L'ajout du Contexte Équipe (30 jours)**
    *   Seulement après validation de l'étape 3, l'étudiant ajoute PostgreSQL pour permettre aux coachs de sauvegarder leur effectif. C'est à ce moment que l'outil devient un compagnon quotidien et que la rétention utilisateur augmente.

En suivant cette séquence, l'étudiant produit de la valeur utilisable dès le premier mois, sans s'épuiser sur de la plomberie technique complexe.
