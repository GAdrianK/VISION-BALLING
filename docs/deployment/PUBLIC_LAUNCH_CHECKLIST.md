# VISION-BALLING — Checklist de Lancement Public (Mise en Production)

> **AVERTISSEMENT STRICT** : Aucun déploiement public en production ne doit être validé tant que des espaces réservés (*placeholders*) subsistent dans les pages légales (`/legal`, `/privacy`, `/beta-terms`). L'opérateur doit renseigner l'ensemble de ses informations réelles avant publication.

---

## 1. Identité Juridique & Mentions Légales
- [ ] Nom légal de l'éditeur ou raison sociale renseigné (remplace `[LEGAL_NAME]`)
- [ ] Nom commercial renseigné (remplace `[BUSINESS_NAME]`)
- [ ] Statut juridique et forme sociale complétés (remplace `[LEGAL_STATUS]`)
- [ ] Adresse professionnelle réelle renseignée (remplace `[PROFESSIONAL_ADDRESS]`)
- [ ] Courriel de contact officiel configuré et actif (remplace `[EMAIL]`)
- [ ] Numéro de téléphone de contact renseigné (remplace `[PHONE]`)
- [ ] Numéros SIREN / SIRET / RNE / RCS renseignés selon le statut (remplacent `[SIREN]`, `[SIRET]`, `[RNE]`, `[RCS_IF_APPLICABLE]`)
- [ ] Numéro de TVA intracommunautaire renseigné si assujetti (remplace `[VAT_NUMBER_IF_APPLICABLE]`)
- [ ] Nom du Directeur de la publication complété (remplace `[NAME]`)
- [ ] Coordonnées complètes de l'hébergeur renseignées (remplacent `[HOST_NAME]`, `[HOST_LEGAL_ENTITY]`, `[HOST_ADDRESS]`, `[HOST_PHONE]`, `[HOST_URL]`)

---

## 2. Conformité RGPD & Politique de Confidentialité
- [ ] Politique de confidentialité relue et validée avec les coordonnées du DPO / contact RGPD
- [ ] Durées de rétention sélectionnées et configurées via les variables d'environnement :
  - `BETA_REQUEST_RETENTION_DAYS` (ex. 180 jours)
  - `VIDEO_RETENTION_DAYS` (ex. 14 jours)
  - `ANALYSIS_RESULT_RETENTION_DAYS` (ex. 30 jours)
- [ ] Tâche planifiée (cron) de purge automatisée configurée (`scripts/cleanup_expired_beta_data.py`)
- [ ] Case d'autorisation des droits vidéo active et obligatoire dans le formulaire
- [ ] Politique formelle de non-réutilisation sans accord (pas de réutilisation marketing, pas d'entraînement de modèle non consenti)
- [ ] Absence confirmée de cookies ou pixels publicitaires (pas de Google Analytics, Meta Pixel, etc.)

---

## 3. Sécurité & Configuration d'Infrastructure
- [ ] HTTPS (TLS 1.3 / Certificat Let's Encrypt ou autorité reconnue) actif sur le domaine et les sous-domaines
- [ ] En-têtes de sécurité HTTP stricts vérifiés (`HSTS`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `CSP`)
- [ ] CORS restreint en production : `ALLOWED_ORIGINS=https://app.[DOMAINE].fr` (interdiction stricte du joker `*`)
- [ ] Ingestion publique GPU désactivée : `PUBLIC_UPLOAD_ENABLED=false` dans la configuration de production
- [ ] `APP_ENV=production` activé (documentation Swagger `/docs` désactivée)
- [ ] Station de calcul GPU isolée en local (aucun port d'inférence exposé sur l'Internet public)

---

## 4. Persistance des Données & Fonctionnalité Pilote
- [ ] Stockage persistant configuré (PostgreSQL managé ou volume Docker persistant SQLite via `BETA_DATABASE_URL`)
- [ ] Table `beta_analysis_requests` créée avec succès
- [ ] Masquage des paramètres de requête d'URL validé dans les journaux système (`url.split("?")[0]`)
- [ ] Formulaire de candidature `/beta` testé de bout en bout (soumission, état de succès `DEMANDE REÇUE.`, identifiant `beta_xxxx`)
- [ ] Script d'administration CLI fonctionnel :
  ```bash
  python scripts/list_beta_requests.py
  python scripts/update_beta_request.py <id> PROCESSING
  ```

---

## 5. Validation Qualité & Ergonomie
- [ ] Tests unitaires et d'intégration validés à 100% :
  ```bash
  pytest backend/tests -q
  ```
- [ ] Audit de sécurité automatisé 100% vert :
  ```bash
  python scripts/security_release_gate.py
  ```
- [ ] Linting et build frontend de production réussis :
  ```bash
  cd frontend && npm run lint && npm run build
  ```
- [ ] Test d'affichage responsive validé sur mobile (390px), tablette (768px) et grand écran (1440px)
- [ ] Tous les liens de pied de page testés sans erreur 404 (`/legal`, `/privacy`, `/cookies`, `/beta-terms`, `/licenses`)
