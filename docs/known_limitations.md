# ⚠️ Limites Connues — Football IQ Assistant MVP V1

Ce document recense honnêtement les limites actuelles du système, pour une présentation transparente.

---

## 1. 📚 Base de connaissances limitée

**Statut actuel :** 24 documents tactiques, 268 chunks indexés.

**Impact :**
- Les sujets non couverts retournent "Je n'ai pas assez d'informations".
- La qualité de la réponse est directement proportionnelle à la richesse du document source.
- Certains sous-thèmes tactiques spécialisés (ex: set-pieces, pressing différentiel, hors-jeu actif) ne sont pas encore couverts.

**Contournement :** Ajouter un fichier `.md` dans `football-rag-system/data_football/knowledge_base/` et relancer le backend.

---

## 2. 🎥 Pas d'analyse vidéo réelle

**Statut actuel :** Les documents `analyse_video_*.md` décrivent des principes d'observation, mais le système ne traite pas de vraies vidéos.

**Impact :** Impossible d'analyser un match ou une action vidéo concrète.

**Feuille de route :** Module d'intégration vidéo prévu en V2.

---

## 3. 🔐 Pas d'authentification

**Statut actuel :** L'application est ouverte sans login.

**Impact :**
- Usage personnel uniquement.
- Pas de profil utilisateur ni de personnalisation persistante.
- Pas de contrôle d'accès pour un déploiement public.

---

## 4. 🧠 Pas de mémoire long-terme

**Statut actuel :** Le `localStorage` conserve la session en cours par onglet/navigateur uniquement.

**Impact :**
- Changer de navigateur ou vider le cache = perte de l'historique.
- Pas de continuité entre sessions distinctes (ex: "comme on en avait parlé la semaine dernière").
- Historique limité à la session courante (pas de multi-conversations).

**Feuille de route :** Base de données légère (SQLite ou IndexedDB) prévue en V2.

---

## 5. 📝 Qualité RAG dépendante des documents

**Statut actuel :** Le RAG TF-IDF est purement lexical en mode offline.

**Impact :**
- La pertinence dépend du vocabulaire partagé entre la question et le document.
- Les synonymes ou reformulations éloignées peuvent mal matcher.
- En mode offline (sans clé OpenAI), les réponses sont des extractions directes — pas une synthèse fluide.

**Contournement :** Fournir une clé `OPENAI_API_KEY` valide dans `.env` pour activer GPT-4o-mini.

---

## 6. 🌐 Pas de déploiement cloud configuré

**Statut actuel :** Fonctionne uniquement en local (`http://127.0.0.1:8000`).

**Impact :**
- Le frontend ouvert en `file://` ne peut interroger qu'un backend local.
- Un déploiement distant nécessite la configuration CORS et un serveur de fichiers statiques.

**Feuille de route :** Configuration Render/Railway prévue en T-10 étendu.

---

## 7. 📱 Responsive mais non optimisé mobile

**Statut actuel :** L'interface s'adapte aux écrans mobiles mais n'est pas optimisée pour les interactions tactiles avancées.

**Impact :**
- Les boutons d'action (Copier, Simplifier, Approfondir) sont petits sur mobile.
- L'expérience clavier virtuel peut décaler le layout.

---

## Résumé

| Limite | Sévérité | Feuille de route |
|---|---|---|
| Base de connaissances limitée | 🟡 Modérée | Ajouter des documents en continu |
| Pas de vidéo réelle | 🟢 Faible | V2 |
| Pas d'auth | 🟡 Modérée | V2 |
| Pas de mémoire long-terme | 🟡 Modérée | V2 |
| Qualité RAG offline | 🔴 Haute | Clé OpenAI recommandée |
| Pas de déploiement cloud | 🟡 Modérée | T-10 étendu |
| Mobile non optimisé | 🟢 Faible | V1.5 |
