# 🚀 Sprint 02 — Déploiement & Feedback Testeurs

**Durée estimée :** 2 à 3 semaines  
**Objectif principal :** Rendre le MVP accessible à 3–5 testeurs externes (coachs, utilisateurs football) et collecter du feedback réel pour améliorer le système.

---

## 📈 Avancement Sprint 02

| Indicateur | Valeur |
| :--- | :--- |
| **Progression Globale** | ![66%](https://geps.dev/progress/66) **66%** (4 / 6 tâches) |
| **Statut** | 🔵 En cours |
| **Prochaine tâche** | T-15 : Formulaire de feedback testeurs |

---

## 🎯 Tâches du Sprint

| ID | Tâche | Statut | Priorité | Estimé |
| :--- | :--- | :---: | :---: | :---: |
| **T-11** | Déploiement Backend Cloud (Render / Railway) | `DONE` | 🔴 Critique | 4h |
| **T-12** | Configuration OpenAI en production | `DONE` | 🔴 Critique | 1h |
| **T-13** | Sécurisation des variables d'environnement | `DONE` | 🔴 Critique | 2h |
| **T-14** | Hébergement Frontend (GitHub Pages / Netlify) | `DONE` | 🔴 Critique | 2h |
| **T-15** | Formulaire de feedback testeurs | `TODO` | 🟡 Haute | 3h |
| **T-16** | Amélioration knowledge base post-feedback | `TODO` | 🟢 Normale | 4h |

---

## 📋 Détail des Tâches

---

### T-11 — Déploiement Backend Cloud

**Objectif :** Rendre l'API FastAPI accessible publiquement via une URL HTTPS stable.

**Plateforme recommandée :** [Render.com](https://render.com) (tier gratuit, support Python natif, déploiement Git automatique)

**Fichiers concernés :**
- `backend/requirements.txt` — vérifier toutes les dépendances
- `Procfile` ou `render.yaml` ← **à créer**
- `backend/app/main.py` — vérifier la config CORS
- `.gitignore` — s'assurer que `.env` est exclu

**Plan d'implémentation :**
1. Créer un compte Render et connecter le repo Git
2. Créer le service `Web Service` → Python → `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Configurer les variables d'environnement dans le dashboard Render
4. Ajouter les origines autorisées CORS (domaine frontend)
5. Tester `GET /api/health` sur l'URL publique

**Temps estimé :** 4h

**Critères de validation :**
- `curl https://[app].onrender.com/api/health` → `{"status":"healthy"}`
- L'index RAG est chargé au démarrage (268 chunks)
- Aucune donnée sensible dans les logs publics

**Risques :**
- ⚠️ Render tier gratuit : timeout après 15 min d'inactivité → cold start de ~30 sec
- ⚠️ Mémoire limitée (512 Mo) : surveiller la consommation du RAG TF-IDF
- ⚠️ La `knowledge_base/` doit être dans le repo Git (pas de volume externe)

---

### T-12 — Configuration OpenAI en Production

**Objectif :** Activer GPT-4o-mini en production pour des réponses de bien meilleure qualité qu'en mode TF-IDF local.

**Fichiers concernés :**
- Variables d'environnement Render (dashboard, pas de fichier)
- `backend/app/core/config.py` — déjà configuré, rien à changer

**Plan d'implémentation :**
1. Ajouter `OPENAI_API_KEY=sk-proj-xxx` dans les variables d'environnement Render
2. Vérifier que la clé active bien le mode `online` au démarrage (log : "OpenAI Embeddings")
3. Tester une question via `POST /api/chat` et comparer la qualité avec le mode offline

**Temps estimé :** 1h

**Critères de validation :**
- Log au démarrage : `Indexation réussie de X chunks via OpenAI.`
- Une question sur le faux 9 produit une réponse fluide et complète (pas une extraction brute)
- Coût OpenAI estimé acceptable pour 3–5 testeurs (~quelques cents par session)

**Risques :**
- ⚠️ Coût API OpenAI si usage intensif → mettre une limite de dépenses dans le dashboard OpenAI
- ⚠️ Ne jamais exposer la clé dans le code source

---

### T-13 — Sécurisation des Variables d'Environnement

**Objectif :** S'assurer qu'aucune donnée sensible n'est exposée dans le code ou les logs.

**Fichiers concernés :**
- `.gitignore` ← vérifier que `backend/.env` est bien ignoré
- `backend/.env.example` ← déjà créé, à maintenir à jour
- `backend/app/main.py` ← vérifier les headers CORS et les logs

**Plan d'implémentation :**
1. Audit `.gitignore` — vérifier `*.env`, `.env`, `venv/`
2. Vérifier que `git log` ne contient aucune clé API dans l'historique
3. Configurer CORS strictement : autoriser uniquement le domaine frontend déployé (pas `*`)
4. Ajouter un rate limiting basique (`slowapi` ou équivalent) pour éviter l'abus

**Temps estimé :** 2h

**Critères de validation :**
- `git grep -r "sk-proj"` → aucun résultat
- Les headers CORS en production n'autorisent pas `*`
- Le `.env` n'apparaît pas dans `git status`

**Risques :**
- ⚠️ Rate limiting trop strict → bloquer les testeurs légitimes
- ⚠️ CORS trop restrictif → frontend incapable d'interroger l'API

---

### T-14 — Hébergement Frontend Statique

**Objectif :** Héberger `frontend/` en HTTPS pour que les testeurs puissent accéder à l'app via un lien simple.

**Plateforme recommandée :** [Netlify](https://netlify.com) ou [GitHub Pages](https://pages.github.com) (gratuit, drag & drop ou déploiement Git)

**Fichiers concernés :**
- `frontend/app.js` ← mettre à jour `API_BASE_URL` pour pointer vers l'URL Render en production
- `frontend/index.html` ← vérifier les meta tags SEO

**Plan d'implémentation :**
1. Mettre à jour `API_BASE_URL` dans `app.js` :
   ```js
   const API_BASE_URL = window.location.hostname === 'localhost' || window.location.protocol === 'file:'
       ? 'http://127.0.0.1:8000'
       : 'https://[app].onrender.com';
   ```
2. Déposer `frontend/` sur Netlify (drag & drop du dossier)
3. Configurer un domaine personnalisé si disponible
4. Tester le chat complet via l'URL publique Netlify

**Temps estimé :** 2h

**Critères de validation :**
- L'URL publique Netlify charge l'app correctement en HTTPS
- Le badge de statut passe au vert (connexion backend Render OK)
- Envoyer une question et recevoir une réponse depuis un autre appareil

**Risques :**
- ⚠️ CORS bloqué si le domaine Netlify n'est pas autorisé côté Render
- ⚠️ Cold start Render de 30 sec → expérience dégradée au premier accès testeur

---

### T-15 — Formulaire de Feedback Testeurs

**Objectif :** Collecter du feedback structuré des 3–5 testeurs pour guider les améliorations.

**Approche recommandée :** Google Form intégré via lien (zéro code backend, simple et rapide)

**Fichiers concernés :**
- `frontend/index.html` ← ajouter un bouton/lien "Donner mon avis" discret
- `docs/feedback_guide.md` ← **à créer** : guide envoyé aux testeurs

**Plan d'implémentation :**
1. Créer un Google Form avec les questions suivantes :
   - Ton profil (coach, joueur, fan, autre)
   - As-tu trouvé les réponses pertinentes ? (1–5)
   - Quel mode as-tu le plus utilisé ?
   - Une réponse t'a-t-elle surpris (positivement ou négativement) ?
   - Quel sujet manque le plus à la base de connaissances ?
   - Commentaire libre
2. Ajouter un lien vers le formulaire dans le footer du frontend
3. Créer `docs/feedback_guide.md` — instructions pour les testeurs
4. Partager l'URL frontend + guide aux testeurs

**Temps estimé :** 3h

**Critères de validation :**
- Le formulaire est accessible depuis l'app
- Au moins 3 réponses reçues dans les 2 premières semaines
- Les réponses permettent d'identifier 3+ sujets à améliorer

**Risques :**
- ⚠️ Faible taux de réponse → relancer les testeurs manuellement
- ⚠️ Feedback trop générique → formulaire trop court

---

### T-16 — Amélioration Knowledge Base Post-Feedback

**Objectif :** Enrichir la `knowledge_base/` sur les sujets identifiés comme manquants par les testeurs.

**Fichiers concernés :**
- `knowledge_base/*.md` ← nouveaux documents à ajouter
- `backend/app/core/config.py` ← aucune modification nécessaire
- Backend : relancer pour réindexer automatiquement

**Plan d'implémentation :**
1. Analyser les réponses du formulaire Google Form
2. Identifier les 3–5 sujets les plus demandés
3. Rédiger les nouveaux documents `.md` selon le template existant
4. Ajouter les fichiers dans `knowledge_base/`
5. Redémarrer le backend (Render redéploie automatiquement sur push Git)
6. Valider avec les questions des testeurs

**Temps estimé :** 4h (variable selon les retours)

**Critères de validation :**
- Les nouveaux sujets reçoivent une réponse pertinente
- Le nombre de chunks augmente dans le badge de statut
- Au moins un testeur confirme l'amélioration

**Risques :**
- ⚠️ Sujets trop vagues ou trop spécifiques → mauvaise couverture RAG
- ⚠️ Trop de nouveaux documents → dégradation de la précision TF-IDF

---

## 🗓️ Séquençage Recommandé

```
Semaine 1
├── T-13 : Sécurisation .env et CORS        (2h)
├── T-11 : Déploiement backend Render        (4h)
└── T-14 : Hébergement frontend Netlify      (2h)

Semaine 2
├── T-12 : Configuration OpenAI production   (1h)
└── T-15 : Formulaire feedback + envoi       (3h)

Semaine 3 (après retours)
└── T-16 : Amélioration knowledge base       (4h)
```

---

## 🎯 Définition du Succès Sprint 02

- [ ] URL publique fonctionnelle partageable en un lien
- [ ] 3 testeurs minimum ont utilisé l'app
- [ ] 3 réponses formulaire reçues
- [ ] Les réponses en mode OpenAI sont qualitativement meilleures qu'en mode TF-IDF
- [ ] Aucune clé API exposée dans le code

---

## ⚠️ Ce qui est hors périmètre Sprint 02

- Authentification / login utilisateur
- Base de données utilisateurs
- Analyse vidéo réelle
- Refonte frontend
- Système de paiement
- Multi-langues

---

## 🔗 Ressources

- [Render.com — Python Web Service](https://render.com/docs/deploy-fastapi)
- [Netlify — Deploy a folder](https://docs.netlify.com/site-deploys/create-deploys/)
- [OpenAI — API Keys](https://platform.openai.com/api-keys)
- [OpenAI — Usage limits](https://platform.openai.com/settings/organization/limits)
