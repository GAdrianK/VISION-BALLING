# 🎬 Script de Démo — Football IQ Assistant MVP (5 minutes)

Ce script décrit un scénario de démonstration complet du MVP, étape par étape.

---

## ⏱️ Durée : 5 minutes

---

## 🔧 Préparation (avant la démo)

1. Démarrer le backend :
   ```bash
   cd backend
   venv/bin/python -m uvicorn app.main:app --reload --port 8000
   ```
2. Ouvrir `frontend/index.html` dans le navigateur.
3. Vérifier que le badge est **vert** avec "268 chunks actifs".

---

## 🟢 Étape 1 — Présentation de l'interface (30 sec)

**À montrer :**
- Le bandeau supérieur avec le statut RAG en temps réel
- Les 3 cartes de mode : Coach / Analyste / Fan
- La barre latérale avec "Nouvelle session"

**Message à dire :**
> "Football IQ Assistant est un assistant tactique football. Il répond uniquement à partir d'une base de connaissances structurée — pas d'invention, pas d'hallucination."

---

## 🎓 Étape 2 — Mode Coach (1 min 30)

**Action :** Cliquer sur la carte **Coach**.

**Question 1 :**
```
Comment défendre en bloc bas face à une équipe qui joue long ?
```
**À montrer :**
- Les sources RAG affichées sous la réponse (ex: `bloc_bas.md`)
- La structure Coach : Analyse + Consignes + Exercice recommandé

**Question 2 :**
```
Prépare une séance de pressing haut pour une équipe U17
```
**À montrer :**
- La réponse structurée avec les blocs d'exercices
- Le bouton **Approfondir** → cliquer → nouvelle réponse plus détaillée apparaît

---

## 🔍 Étape 3 — Mode Analyste (1 min)

**Action :** Cliquer sur la carte **Analyste** → le chat se vide automatiquement.

**Question :**
```
Quels sont les avantages et faiblesses du 3-5-2 ?
```
**À montrer :**
- Le ton analytique et structuré de la réponse
- Les sources (`formation_352.md`)
- Le bouton **Simplifier** → cliquer → version plus accessible

---

## 📣 Étape 4 — Mode Fan (45 sec)

**Action :** Cliquer sur la carte **Fan** → chat vidé.

**Question :**
```
C'est quoi un faux 9 en vrai ?
```
**À montrer :**
- Le ton vulgarisé et accessible sans jargon technique excessif
- Les sources (`roles_modernes.md`)

**Test salutation :**
```
salut
```
**À montrer :**
- La réponse de bienvenue immédiate **sans appel RAG** (pas de sources affichées)

---

## 📄 Étape 5 — Export PDF (30 sec)

**Action :** Sur la réponse précédente, cliquer sur **Exporter PDF**.

**À montrer :**
- Le bouton passe à "⏳ Génération..."
- Puis "✅ Téléchargé"
- Le fichier `fiche_tactique_XXXXXX.pdf` apparaît dans les téléchargements

---

## 📋 Étape 6 — Copier & Persistence (30 sec)

**Copier :**
- Cliquer sur **Copier** sur n'importe quelle réponse
- Montrer le feedback vert "✅ Copié !"

**Persistence :**
- Recharger la page (F5)
- Montrer que la conversation revient automatiquement depuis le `localStorage`

---

## 🔄 Étape 7 — Nouvelle session (15 sec)

**Action :** Cliquer sur **Nouvelle session** dans la barre latérale.

**À montrer :**
- Chat vidé instantanément
- Mode conservé
- `localStorage` effacé → rechargement = session vide

---

## ✅ Conclusion (15 sec)

> "Ce MVP fonctionne entièrement en local, sans clé OpenAI requise. La base de connaissances contient 24 documents tactiques et 268 chunks indexés. Une clé OpenAI peut être ajoutée pour des réponses encore plus riches."

---

## 💡 Questions fréquentes en démo

| Question | Réponse |
|---|---|
| "Ça marche sans internet ?" | Oui — le RAG TF-IDF est 100% local |
| "Quelle est la qualité des réponses ?" | Dépend de la qualité des documents RAG et de la présence d'une clé OpenAI |
| "On peut ajouter d'autres documents ?" | Oui — ajouter un `.md` dans `knowledge_base/` et relancer le backend |
| "C'est déployable en ligne ?" | Oui — FastAPI + fichiers statiques, CORS à configurer |
