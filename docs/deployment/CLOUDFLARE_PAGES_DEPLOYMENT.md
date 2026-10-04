# VISION-BALLING — Guide de Déploiement Frontend Cloudflare Pages

Ce guide fournit la procédure détaillée pour déployer le frontend client (React + Vite SPA) de VISION-BALLING sur [Cloudflare Pages](https://pages.cloudflare.com).

---

## 1. Vue d'ensemble de l'architecture Frontend

- **Type de projet** : Application monopage (SPA) statique construite avec Vite et React.
- **Réseau de distribution** : CDN mondial Cloudflare (Anycast) avec points de présence (PoP) en France et dans l'Union Européenne.
- **Protection & Sécurité** :
  - Routage SPA garanti via [`frontend/public/_redirects`](file:///home/adriano/Documents/PROJET%20PERSO/VISION-BALLING/frontend/public/_redirects) (règle `/* /index.html 200`).
  - Blocage strict à la compilation si `VITE_API_URL` est omis ou pointe vers `localhost` en production ([`frontend/vite.config.js`](file:///home/adriano/Documents/PROJET%20PERSO/VISION-BALLING/frontend/vite.config.js)).
  - Isolation totale : aucun calcul d'inférence ni modèle lourd n'est embarqué dans le bundle statique.

---

## 2. Étape 1 : Prérequis

1. Un compte [Cloudflare](https://dash.cloudflare.com).
2. L'accès en lecture au dépôt GitHub contenant le projet VISION-BALLING.
3. L'URL publique de l'API backend Railway (ex. `https://vision-balling-production.up.railway.app` ou `https://api.vision-balling.com`).

---

## 3. Étape 2 : Création du projet Cloudflare Pages

1. Rendez-vous sur le [Tableau de bord Cloudflare](https://dash.cloudflare.com/).
2. Dans le menu latéral gauche, cliquez sur **Workers & Pages**.
3. Cliquez sur **Create application** > onglet **Pages** > **Connect to Git**.
4. Sélectionnez votre compte GitHub et choisissez le dépôt `VISION-BALLING`.
5. Cliquez sur **Begin setup**.

---

## 4. Étape 3 : Paramètres de Build (Construction)

Renseignez les champs de configuration exactement comme suit :

| Paramètre | Valeur | Note |
| :--- | :--- | :--- |
| **Project name** | `vision-balling` | Utilisé pour le sous-domaine par défaut `vision-balling.pages.dev`. |
| **Production branch** | `main` (ou branche validée) | Branche déclenchant les déploiements de production. |
| **Framework preset** | `Vite` | Préconfiguration recommandée. |
| **Root directory** | `frontend` | **Crucial** : le code React se trouve dans le sous-dossier `frontend/`. |
| **Build command** | `npm run build` | Exécute la compilation Vite durcie. |
| **Build output directory** | `dist` | Dossier relatif à `frontend` où sont générés les fichiers compilés. |

---

## 5. Étape 4 : Variables d'Environnement

Dans la section **Environment variables (production)** de la même page (ou dans *Settings* > *Environment variables*) :

| Nom de variable | Valeur | Description |
| :--- | :--- | :--- |
| `VITE_API_URL` | `https://api.vision-balling.com` *(ou URL Railway)* | **Obligatoire**. URL absolue HTTPS de l'API backend. |
| `NODE_VERSION` | `20` | Version Node.js LTS recommandée pour la compilation. |

> **Garantie de sécurité** : Si vous oubliez de renseigner `VITE_API_URL` ou si sa valeur commence par `http://localhost` ou `http://127.0.0.1`, le script `vite.config.js` fera échouer immédiatement la compilation avec un message d'erreur explicite, empêchant tout déploiement corrompu.

Cliquez sur **Save and Deploy**.

---

## 6. Étape 5 : Routage SPA & Gestion des URL profondes

Cloudflare Pages prend automatiquement en charge le fichier `_redirects` placé dans le dossier `public/` lors du build.

Le fichier [`frontend/public/_redirects`](file:///home/adriano/Documents/PROJET%20PERSO/VISION-BALLING/frontend/public/_redirects) contient :
```
/*    /index.html   200
```

Ce mécanisme garantit que les utilisateurs ou les liens partagés vers des sous-pages :
- `/beta` (formulaire de candidature)
- `/legal` (mentions légales)
- `/privacy` (politique de confidentialité RGPD)
- `/cookies` (information traceurs)
- `/beta-terms` (conditions d'utilisation)

sont servis immédiatement avec un code HTTP 200 et pris en charge par le routeur React, sans générer d'erreur 404 Not Found au niveau de Cloudflare.

---

## 7. Étape 6 : Domaine Personnalisé (Optionnel)

1. Dans les paramètres de votre projet Pages, allez dans l'onglet **Custom domains**.
2. Cliquez sur **Set up a custom domain**.
3. Saisissez votre domaine (ex. `app.vision-balling.com` ou `vision-balling.fr`).
4. Si votre zone DNS est gérée chez Cloudflare, la configuration des enregistrements CNAME est automatique avec provisionnement d'un certificat SSL/TLS gratuit.

---

## 8. Étape 7 : Vérification & Test de Déploiement

Une fois le déploiement Cloudflare Pages terminé :

1. Ouvrez l'URL `https://vision-balling.pages.dev` dans un navigateur.
2. Naviguez directement sur `https://vision-balling.pages.dev/beta` et rechargez la page (F5) : vérifiez que la page se recharge correctement sans 404.
3. Ouvrez la console développeur (F12) > onglet **Réseau** : soumettez une interaction et vérifiez que toutes les requêtes ciblent bien votre URL d'API Railway et qu'aucune requête ne tente d'appeler `localhost`.
4. Lancez le script de contrôle qualité :
   ```bash
   python scripts/smoke_test_public.py \
     --frontend https://vision-balling.pages.dev \
     --api https://<votre-domaine-railway>
   ```
