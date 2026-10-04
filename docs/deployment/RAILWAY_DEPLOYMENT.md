# VISION-BALLING — Guide de Déploiement Backend Railway (CPU + PostgreSQL)

Ce guide fournit la procédure pas-à-pas pour déployer le backend FastAPI et la base de données PostgreSQL de VISION-BALLING sur [Railway](https://railway.app).

---

## 1. Vue d'ensemble de l'architecture Railway

- **Type de déploiement** : Conteneur Linux CPU-only (Python 3.12-slim).
- **GPU Cloud** : **NON DÉPLOYÉ**. L'inférence lourde de vision par ordinateur (détection RF-DETR, tracking ByteTrack, calibration homographique) reste strictement confinée à la station locale privée (GPU NVIDIA RTX 4060).
- **Rôle du backend public** :
  1. Servir le endpoint de santé `/health` et `/api/health`.
  2. Recevoir et sécuriser les candidatures au programme BETA via `POST /api/beta/requests`.
  3. Rejeter toute tentative d'envoi direct de vidéo en production (`POST /api/video-analysis` renvoie immédiatement HTTP 403 Forbidden).
  4. Stocker les dossiers d'inscription dans une base managée PostgreSQL.

---

## 2. Étape 1 : Créer le projet et la base PostgreSQL sur Railway

1. Connectez-vous à la console [Railway Dashboard](https://railway.app/dashboard).
2. Cliquez sur **New Project** > **Provision PostgreSQL**.
3. Railway crée une instance PostgreSQL managée avec sauvegardes automatiques.
4. Dans l'onglet **Variables** du service PostgreSQL, notez que Railway génère automatiquement :
   - `DATABASE_URL` (format `postgresql://...` ou `postgres://...`)
   - Les identifiants `PGUSER`, `PGPASSWORD`, `PGHOST`, `PGPORT`, `PGDATABASE`.

> **Note de compatibilité SQLAlchemy** : Railway fournit parfois une URL commençant par `postgres://`. Le backend VISION-BALLING normalise automatiquement ce préfixe en `postgresql://` via `Settings.effective_database_url`.

---

## 3. Étape 2 : Déployer le service Backend depuis GitHub

1. Dans le même projet Railway, cliquez sur **+ New** > **GitHub Repo**.
2. Sélectionnez le dépôt `VISION-BALLING` et la branche de production (ex. `main` ou votre branche validée).
3. Railway détecte automatiquement le fichier [`Dockerfile`](file:///home/adriano/Documents/PROJET%20PERSO/VISION-BALLING/Dockerfile) ou [`railway.json`](file:///home/adriano/Documents/PROJET%20PERSO/VISION-BALLING/railway.json) à la racine du dépôt.

---

## 4. Étape 3 : Configurer les Variables d'Environnement

Dans l'onglet **Variables** du service Backend, configurez **strictement** les variables suivantes :

| Variable | Valeur recommandée | Explication |
| :--- | :--- | :--- |
| `APP_ENV` | `production` | **Obligatoire**. Active les sécurités fail-closed, interdit SQLite et bloque les chemins locaux. |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Référence automatique Railway vers le service PostgreSQL provisionné. |
| `PUBLIC_UPLOAD_ENABLED` | `false` | **Obligatoire**. Désactive l'analyse vidéo directe sur le cloud public. |
| `CORS_ORIGINS` | `["https://vision-balling.pages.dev","https://app.vision-balling.com"]` | Liste JSON des origines frontend autorisées (Cloudflare Pages et domaine personnalisé). |
| `RATE_LIMIT_ENABLED` | `true` | Active la protection contre les abus sur les candidatures BETA. |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `10` | Plafond de requêtes par IP et par minute. |
| `LOG_LEVEL` | `INFO` | Journalisation sécurisée sans affichage des jetons ou secrets. |
| `PYTHONUNBUFFERED` | `1` | Flux direct des logs stdout/stderr dans la console Railway. |

### Ce qu'il ne faut JAMAIS configurer en production :
- Ne définissez **PAS** de chemin local personnel (ex: `/media/adriano/...` ou `/home/...`).
- Ne définissez **PAS** de clés secrètes d'API tierces non nécessaires.
- Ne laissez **PAS** `DATABASE_URL` vide en production (l'API refuserait de démarrer).
- N'utilisez **PAS** d'URL `sqlite:///` en production (le backend crashe volontairement par sécurité).

---

## 5. Étape 4 : Configuration du Healthcheck et des Ressources

Dans l'onglet **Settings** du service Backend :

1. **Networking** :
   - Cliquez sur **Generate Domain** pour obtenir l'URL publique de staging (ex. `vision-balling-production.up.railway.app`).
   - Si vous disposez d'un domaine personnalisé : ajoutez `api.vision-balling.com` et configurez le CNAME DNS chez votre registrar.
2. **Healthcheck** :
   - Healthcheck Path : `/health`
   - Healthcheck Timeout : `10` secondes.
3. **Deploy** :
   - Restart Policy : `ON_FAILURE` (max retries 5).

---

## 6. Étape 5 : Vérification Post-Déploiement

Une fois le déploiement terminé (statut vert *Active*) :

### 1. Sonde de santé et connectivité PostgreSQL
```bash
curl -i https://<votre-domaine-railway>/health
```
**Résultat attendu** :
```http
HTTP/1.1 200 OK
Content-Type: application/json

{"status":"ok"}
```
> Le endpoint `/health` vérifie en interne l'exécution d'un `SELECT 1` sur l'instance PostgreSQL managée. Si la base est inaccessible, il renvoie un code HTTP 503 Service Unavailable.

### 2. Vérification du verrou de sécurité (Fail-Closed)
```bash
curl -i -X POST https://<votre-domaine-railway>/api/video-analysis
```
**Résultat attendu** :
```http
HTTP/1.1 403 Forbidden
Content-Type: application/json

{"detail":"Public video upload is disabled on this deployment. Please apply via the Beta intake program (/beta)."}
```

### 3. Exécution du smoke test automatisé
Depuis votre machine locale :
```bash
python scripts/smoke_test_public.py \
  --frontend https://vision-balling.pages.dev \
  --api https://<votre-domaine-railway> \
  --test-form
```
