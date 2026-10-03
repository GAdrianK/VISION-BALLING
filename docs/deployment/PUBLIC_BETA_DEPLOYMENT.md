# VISION-BALLING — Guide de Déploiement Public BETA (France)

Ce document décrit l'architecture de déploiement de l'application publique VISION-BALLING (v0.9.0-rc2) en France, garantissant la conformité RGPD / LCEN, l'étanchéité des calculs GPU et la protection fail-closed.

---

## 1. Architecture de Déploiement

```
                                    INTERNET
                                       │
                         HTTPS (TLS 1.3 / Port 443)
                                       │
                ┌──────────────────────┴──────────────────────┐
                ▼                                             ▼
        [FRONTEND PUBLIC]                             [API PUBLIQUE]
        Vite Single Page App                     FastAPI (Gunicorn/Uvicorn)
     https://app.[DOMAINE].fr                      https://api.[DOMAINE].fr
    (CDN / Serveur Statique Nginx)                 (Conteneur Docker durci)
                │                                             │
                │                                             ▼
                │                                    [STOCKAGE PERSISTANT]
                │                                    PostgreSQL Managé (Cloud)
                │                                    ou Volume SQLite monté
                │                                             │
                └──────────────────────┬──────────────────────┘
                                       │
                      ====================================
                       AIR GAP / ACCÈS INTERNE RESTREINT
                      ====================================
                                       │
                                       ▼
                             [STATION DE CALCUL GPU]
                           Local RTX / Station de recherche
                           (Hors exposition Internet publique)
                           PUBLIC_UPLOAD_ENABLED=false
```

---

## 2. Nom de Domaine & Enregistrements DNS

### Configuration requise
- Domaine racine : `[DOMAINE].fr` ou `vision-balling.fr`
- Frontend : `app.[DOMAINE].fr` (ou `[DOMAINE].fr`)
- API Backend : `api.[DOMAINE].fr`

### Enregistrements DNS recommandés
| Type | Nom d'hôte | Valeur cible | TTL |
| :--- | :--- | :--- | :--- |
| `A` / `CNAME` | `app` | IP / CNAME de l'hébergeur frontend | 3600 |
| `A` / `CNAME` | `api` | IP / CNAME du serveur API backend | 3600 |
| `CAA` | `@` | `0 issue "letsencrypt.org"` | 86400 |

---

## 3. Déploiement Frontend (Vite Static)

### Construction des artefacts de production
```bash
cd frontend
export VITE_API_URL="https://api.[DOMAINE].fr"
npm ci
npm run lint
npm run build
```
Les fichiers statiques produits se trouvent dans `frontend/dist/`.

### Configuration Nginx (exemple)
```nginx
server {
    listen 443 ssl http2;
    server_name app.[DOMAINE].fr;

    ssl_certificate /etc/letsencrypt/live/app.[DOMAINE].fr/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.[DOMAINE].fr/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    root /var/www/vision-balling-frontend/dist;
    index index.html;

    # En-têtes de sécurité
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Content-Security-Policy "default-src 'self'; connect-src 'self' https://api.[DOMAINE].fr; font-src 'self' https://fonts.gstatic.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src 'self' data:; frame-ancestors 'none';" always;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

---

## 4. Déploiement API Backend

### Conteneurisation & Démarrage
L'API publique traite uniquement l'ingestion des candidatures BETA (`/api/beta-requests`), les séquences de démonstration et les requêtes RAG ancrées.

Commande d'exécution de production :
```bash
uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --workers 4 --proxy-headers --forwarded-allow-ips="*"
```

---

## 5. Base de Données Persistante

Le service de candidatures BETA utilise l'abstraction SQLAlchemy supportant à la fois un volume persistant SQLite et une base managée PostgreSQL.

### Option A : PostgreSQL Managé (Recommandé en Cloud)
```env
BETA_DATABASE_URL=postgresql://user:password@db-host:5432/vision_balling_prod
```

### Option B : Volume SQLite Monté (Serveur Unique / Docker)
```env
BETA_DATABASE_URL=sqlite:////mnt/persistent-data/beta_requests.db
```

La création des tables (`beta_analysis_requests`) et des index d'horodatage et de statut est idempotente et automatisée au démarrage du service.

---

## 6. Variables d'Environnement de Production

### Fichier `.env` Backend
```ini
APP_ENV=production
PUBLIC_UPLOAD_ENABLED=false
ALLOWED_ORIGINS=https://app.[DOMAINE].fr
REQUIRE_ANALYSIS_TOKEN=true
ENABLE_DOCS=false

# Base de données persistante des candidatures BETA
BETA_DATABASE_URL=postgresql://...

# Politiques de rétention (en jours)
BETA_REQUEST_RETENTION_DAYS=180
VIDEO_RETENTION_DAYS=14
ANALYSIS_RESULT_RETENTION_DAYS=30

# Clés de services LLM / RAG (stockage sécurisé)
OPENROUTER_API_KEY=sk-or-v1-...
```

> **Règle absolue** : `PUBLIC_UPLOAD_ENABLED` doit être strictement positionné à `false`. Tout démarrage avec `APP_ENV=production` et `PUBLIC_UPLOAD_ENABLED=true` déclenche une exception bloquante fail-closed.

---

## 7. Rétention des Données & Purge Automatisée

Planifier une tâche cron quotidienne pour purger les dossiers de candidature expirés au-delà de la durée légale définie :
```cron
0 3 * * * /opt/venv/bin/python /opt/vision-balling/scripts/cleanup_expired_beta_data.py >> /var/log/beta_cleanup.log 2>&1
```

---

## 8. Tests de Fumée (Smoke Tests)

Après déploiement, exécuter la séquence suivante depuis une machine externe :

1. **Vérification de l'API Racine & En-têtes** :
   ```bash
   curl -I https://api.[DOMAINE].fr/api/beta-requests
   ```
   Attendu : `405 Method Not Allowed` ou `422 Unprocessable Entity` avec en-têtes `X-Content-Type-Options: nosniff` et `Strict-Transport-Security`.

2. **Test de soumission valide (Smoke test intake)** :
   ```bash
   curl -X POST https://api.[DOMAINE].fr/api/beta-requests \
     -H "Content-Type: application/json" \
     -H "Origin: https://app.[DOMAINE].fr" \
     -d '{
       "name": "Smoke Test Coach",
       "club": "RC Smoke Test",
       "role": "Entraîneur",
       "email": "smoke@club.fr",
       "team_category": "Séniors",
       "competition_level": "Régional",
       "video_type": "Extrait",
       "video_url": "https://swisstransfer.com/d/smoke-test",
       "analysis_objectives": ["Analyse globale"],
       "video_authorization_confirmed": true,
       "temporary_storage_consent": true
     }'
   ```
   Attendu : `HTTP 201 Created` avec JSON `{"id": "beta_...", "status": "NEW", ...}`.

3. **Vérification du rejet d'upload direct public** :
   ```bash
   curl -X POST https://api.[DOMAINE].fr/api/video-analysis
   ```
   Attendu : `HTTP 403 Forbidden` (`Direct video upload is disabled in this environment`).

---

## 9. Procédure de Rollback

En cas d'anomalie critique lors du déploiement :
1. **Frontend** : Repositionner le symlink Nginx `/var/www/vision-balling-frontend/dist` vers la release précédente `dist-previous/`. Recharger Nginx (`systemctl reload nginx`).
2. **Backend** : Repositionner l'image de conteneur Docker sur le tag précédent (ex. `v0.9.0-rc1` ou commit parent).
3. **Données** : La table `beta_analysis_requests` est additive et rétrocompatible ; aucun rollback de schéma SQL n'est nécessaire.
