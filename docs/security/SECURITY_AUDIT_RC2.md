# Audit de Sécurité Initial — VISION-BALLING v0.9.0-rc2
*Document généré en Phase 0 du Sprint de Durcissement Sécurité & Déploiement*
*Date : 3 Octobre 2026*

---

## 1. Principes Directeurs
Conformément à la directive d'intégrité du système, VISION-BALLING adopte une politique stricte de **FAIL CLOSED** :
- Tout accès non authentifié ou non autorisé à des données réelles (`REAL_UPLOAD`) est strictement refusé (`401`/`403`/`404`).
- Aucun basculement silencieux vers des données de démonstration (`PRECOMPUTED_DEMO`) n'est toléré en cas d'erreur ou d'absence d'évidences.
- L'intégrité cryptographique des modèles (SHA-256) est contrôlée au démarrage.
- Les interfaces de diagnostic interne, la génération dynamique de SQL et la documentation interactive sont désactivées en production (`APP_ENV=production`).

---

## 2. Inventaire Exhaustif des Points d'Entrée & Statut de Sécurité

| Méthode | Chemin / Route | Finalité | Public ? | Auth Requise ? | Entrée Utilisateur | Accès FS ? | Accès GPU ? | Accès DB ? | Accès LLM ? | Sortie Sensible ? | Rate Limited ? | Statut de Sécurité Initial | Action de Durcissement RC2 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/analyze` | Scouting legacy Qwen LLM -> SQL text execution | OUI | NON | OUI (texte libre) | OUI (SQLite) | NON | OUI (SQLite) | OUI (OpenRouter) | OUI (schéma DB) | NON | **CRITIQUE (Hostile)** | **DÉSACTIVER en production** (`404` / `403` si non activé explicitement) |
| `GET` | `/api/health` | Healthcheck système | OUI | NON | NON | NON | NON | NON | NON | OUI (version/moteur) | NON | MOYEN | **Épurer la réponse** (`{"status": "healthy"}`) sans fuite de nom de moteur/DB |
| `POST` | `/api/chat` | Chat RAG tactique | OUI | NON | OUI (texte libre) | OUI (KB local) | NON | OUI (Qdrant/SQLite) | OUI (OpenAI/Gemini) | NON | NON | ÉLEVÉ | **Rate limiter** + filtrage prompt injection |
| `POST` | `/api/export-pdf` | Export PDF d'exercices | OUI | NON | OUI (JSON payload) | OUI (temporaire) | NON | NON | NON | NON | NON | MOYEN | **Rate limiter** + validation stricte du schéma payload |
| `GET` | `/api/video-analysis/diagnostics/backend` | Diagnostic runtime CV/FFmpeg | OUI | NON | NON | OUI (chemins locaux) | NON | NON | NON | OUI (chemins absolus) | NON | **ÉLEVÉ (Fuite info)** | **DÉSACTIVER en production** (`404` / admin only) |
| `POST` | `/api/video-analysis` | Upload et lancement d'analyse vidéo | OUI | NON | OUI (fichier binaire) | OUI (stockage) | OUI (Inférence CUDA) | NON | NON | NON | NON | **CRITIQUE (DDoS GPU / FS)** | **Désactiver public par défaut** (`PUBLIC_UPLOAD_ENABLED=false`), token d'accès, validation sandbox, rate limits |
| `GET` | `/api/video-analysis/{analysis_id}` | Consultation du statut d'un job | OUI | NON | OUI (`analysis_id`) | OUI (job.json) | NON | NON | NON | OUI (métadonnées) | NON | **ÉLEVÉ (IDOR)** | **Bearer token obligatoire** pour `REAL_UPLOAD`, public uniquement si DEMO |
| `GET` | `/api/video-analysis/{analysis_id}/detections` | Récupération des détections brutes | OUI | NON | OUI (`analysis_id`) | OUI (result.json) | NON | NON | NON | OUI (données match) | NON | **ÉLEVÉ (IDOR)** | **Bearer token obligatoire** pour `REAL_UPLOAD` |
| `GET` | `/api/video-analysis/{analysis_id}/artifacts` | Liste des artefacts générés | OUI | NON | OUI (`analysis_id`) | OUI (job.json) | NON | NON | NON | OUI (URLs internes) | NON | **ÉLEVÉ (IDOR)** | **Bearer token obligatoire** pour `REAL_UPLOAD` |
| `GET` | `/api/video-analysis/{analysis_id}/artifacts/{name}` | Téléchargement vidéo annotée / json / image | OUI | NON | OUI (`analysis_id`, `name`) | OUI (lecture directe) | NON | NON | NON | OUI (vidéo privée) | NON | **CRITIQUE (IDOR / Fuite vidéo)** | **Bearer token obligatoire** pour `REAL_UPLOAD`, validation nom d'artefact |
| `POST` | `/api/video-analysis/{analysis_id}/query` | Question/Réponse RAG ancré sur vidéo | OUI | NON | OUI (`query`, `analysis_id`) | OUI (évidences) | NON | OUI (Qdrant) | OUI (OpenAI/OpenRouter) | OUI (données vidéo) | NON | **ÉLEVÉ (IDOR / Coût LLM)** | **Bearer token obligatoire** pour `REAL_UPLOAD` + Rate limit |
| `GET` | `/api/video-analysis/{analysis_id}/timeline` | Chronologie des événements tactiques | OUI | NON | OUI (`analysis_id`) | OUI (évidences) | NON | NON | NON | OUI (données match) | NON | **ÉLEVÉ (IDOR / Fallback bug)** | **Bearer token obligatoire** + **Zéro fallback DEMO** |
| `GET` | `/api/video-analysis/{analysis_id}/events` | Index complet des évidences tactiques | OUI | NON | OUI (`analysis_id`) | OUI (évidences) | NON | NON | NON | OUI (données match) | NON | **ÉLEVÉ (IDOR / Fallback bug)** | **Bearer token obligatoire** + **Zéro fallback DEMO** |
| `GET` | `/api/video-analysis/{analysis_id}/summary` | Résumé agrégé par équipe | OUI | NON | OUI (`analysis_id`) | OUI (évidences) | NON | NON | NON | OUI (données match) | NON | **ÉLEVÉ (IDOR / Fallback bug)** | **Bearer token obligatoire** + **Zéro fallback DEMO** |
| `GET/POST`| `/api/video-analysis/{analysis_id}/report` | Rapport tactique Markdown ancré | OUI | NON | OUI (`analysis_id`) | OUI (évidences) | NON | NON | NON | OUI (rapport match) | NON | **ÉLEVÉ (IDOR / Fallback bug)** | **Bearer token obligatoire** + **Zéro fallback DEMO** |
| `GET` | `/docs`, `/redoc`, `/openapi.json` | Documentation interactive Swagger/ReDoc | OUI | NON | NON | NON | NON | NON | NON | OUI (schéma API complet) | NON | MOYEN | **DÉSACTIVER en production** (`APP_ENV=production`) |

---

## 3. Synthèse des Vulnérabilités Majeures & Plan d'Atténuation Immédiat

1. **Exécution de code / Injection SQL arbitraire (`/api/analyze`)** :
   - Risque : L'utilisateur envoie un prompt hostile qui amène le LLM à émettre une commande SQLite arbitraire exécutée par `cursor.execute(sql_query)`.
   - Action : Désactiver immédiatement cette route en mode production. En mode dev, imposer un parseur AST interdisant toute instruction autre que `SELECT` sur liste blanche stricte de tables/colonnes.

2. **Absence d'Autorisation & IDOR sur `REAL_UPLOAD`** :
   - Risque : N'importe quel utilisateur connaissant ou devinant un `analysis_id` peut télécharger les vidéos, détections, rapports et poser des questions sur les vidéos privées d'un tiers.
   - Action : Implémenter un modèle de jeton de capacité cryptographique (`analysis_access_token`) généré lors de la création d'une analyse réelle et hashé côté serveur (`SHA-256`). Requis dans le header `Authorization: Bearer <token>`.

3. **Fallback Silencieux Démo (`_resolve_evidence_dir`)** :
   - Risque : Une analyse réelle sans données probantes complètes bascule automatiquement vers `docs/experiments/exp25_outputs` (données de test SNMOT).
   - Action : Suppression stricte du fallback. Échec `404` / `409` immédiat si les artefacts réels sont introuvables.

4. **Abus de Ressources & Déni de Service GPU** :
   - Risque : Ingestion illimitée de vidéos lourdes sur le GPU local/distant, saturant la VRAM et le disque.
   - Action : Paramètre `PUBLIC_UPLOAD_ENABLED=false` par défaut en production, limitation de débit (`slowapi`), taille max et durée max strictes, streaming direct sur disque sans buffer RAM complet.

5. **XSS via Rendu Markdown non aseptisé (`marked.parse`)** :
   - Risque : Injection de scripts via des données de match forgées ou du contenu de rapport rendu avec `dangerouslySetInnerHTML`.
   - Action : Intégration de DOMPurify pour assainir tout HTML généré et interdire les schémas `javascript:` et balises `<script>`.
