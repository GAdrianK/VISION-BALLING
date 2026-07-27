# 📝 Audit de Qualité des Prompts & Plan d'Amélioration (Prompt Quality Pass)

Ce document analyse les faiblesses des prompts système actuels (Coach, Analyste, Fan) et propose des solutions concrètes pour éliminer les hallucinations, forcer l'usage exclusif du RAG, et améliorer la structure des réponses.

---

## 🔍 1. Problèmes Observés & Causes Probables

### Problème A : Hallucination de structure obligatoire (Le Conflit Structure vs RAG)
* **Symptôme :** Lorsqu'on demande *"Explique-moi ce qu'est un faux 9"*, le modèle en mode Coach invente un exercice d'entraînement de toutes pièces (par exemple un jeu en 4vs4), alors que le document RAG `roles_modernes.md` ne contient qu'une définition théorique du poste.
* **Cause probable :** La consigne de structure est rigide : `"Structure ta réponse avec des sections claires : ... 'Exercice Recommandé sur le Terrain'"`. Pour satisfaire cette consigne obligatoire, le LLM passe outre l'interdiction d'improviser et génère un exercice à partir de ses propres poids d'entraînement génériques.

### Problème B : Invention d'entités (Le Syndrome du Supporter)
* **Symptôme :** En mode Fan, la réponse cite de faux joueurs ou fait référence à des clubs réels ("Notre numéro 6", "Messi") absents de la base de connaissances locale.
* **Cause probable :** La structure forcée `"Le Joueur Clé"` et le ton libre du supporter incitent le modèle à extrapoler pour incarner le rôle, contournant ainsi le filtre du RAG.

### Problème C : Manque de directives négatives explicites (Faux Positifs)
* **Symptôme :** Le système répond à des questions tactiques génériques du football mondial non documentées dans la base de connaissances (ex. *"Comment joue l'Italie de 2006 ?"*).
* **Cause probable :** Bien que les prompts indiquent de se baser sur le contexte, ils ne spécifient pas ce qui constitue une "source non vérifiée". Les règles négatives de rejet ne sont pas assez agressives (par exemple, interdire l'usage de données antérieures à l'entraînement du modèle sur des sujets non indexés).

---

## 💡 2. Améliorations Proposées & Directives de Refactoring

Pour corriger ces dérives, nous devons restructurer les prompts selon 4 principes clés :

1. **Règles de Structure Conditionnelles :**
   * Au lieu de forcer une section (ex. "Exercice"), spécifier au LLM : *"N'ajoute la section 'Exercice' que si un exercice spécifique est décrit dans le contexte fourni. Si aucun exercice n'est mentionné, écris à la place : 'Aucun exercice disponible pour ce concept dans notre base de données'."*
2. **Isolation Hermétique du RAG (Directives de "Boîte Noire") :**
   * Ajouter une clause explicite de "Zéro Connaissance Externe" : *"Tu agis comme si tu avais perdu la mémoire de toutes les tactiques de football non décrites dans les extraits fournis. Tout concept tactique absent des sources doit être considéré comme inexistant."*
3. **Citations Strictes et Ancrage :**
   * Obliger le LLM à lister à la fin de chaque paragraphe le nom de la source d'où provient l'information (ex: `(Réf: roles_modernes.md)`).
4. **Standardisation du Message de Rejet :**
   * Unifier les réponses lorsque le contexte est vide ou incomplet pour éviter les variations créatives.

---

## 📈 3. Exemples de Restructuration des Prompts (Avant / Après)

### 📋 Profil : Coach Tactique

#### Prompt Actuel (Extrait)
```text
1. Structure ta réponse avec des sections claires : "Analyse du Coach", "Consignes Individuelles/Collectives" et "Exercice Recommandé sur le Terrain".
3. Base-toi STRICTEMENT sur le contexte fourni.
```

#### Prompt Proposé (Refactorisé)
```text
RÈGLES DE STRUCTURE STRICTES ET CONDITIONNELLES :
1. "Analyse du Coach" : Explique la notion de manière simplifiée en te basant STRICTEMENT sur le contexte.
2. "Consignes du Terrain" : Donne les consignes de jeu issues des sources.
3. "Exercice Recommandé" : Si et SEULEMENT si un exercice d'entraînement est documenté dans le contexte, décris-le. Sinon, écris texto : "[Aucun exercice spécifique n'est référencé dans notre base de données tactique pour ce sujet. Nous restons sur les principes de jeu généraux.]"

CLAUSE DE NON-INVENTION CRITIQUE :
- Tu as interdiction formelle d'inventer des schémas d'exercices, des effectifs (ex: 4 vs 4) ou des règles si le contexte ne les décrit pas.
- Si le contexte RAG est vide ou insuffisant pour répondre précisément à la question tactique, tu dois répondre : "En tant que coach, nos tablettes tactiques actuelles ne contiennent pas assez de données sur ce point précis pour planifier nos séances."
- Chaque fait ou consigne tactique énoncé doit être suivi de sa source exacte (ex. [source: bloc_bas.md]).
```

---

### 🔍 Profil : Analyste Technique

#### Prompt Actuel (Extrait)
```text
1. Structure ta réponse de manière scientifique : "Observations Structurelles", "Schéma de Transition / Animation" et "Forces/Faiblesses du Système".
3. Base-toi STRICTEMENT sur le contexte fourni.
```

#### Prompt Proposé (Refactorisé)
```text
RÈGLES DE STRUCTURE ET DE RIGUEUR ANALYTIQUE :
1. "Observations Structurelles" : Analyse géométrique basée uniquement sur le RAG.
2. "Forces/Faiblesses du Système" : Analyse des avantages et inconvénients décrits dans les sources. Si le document source ne mentionne pas explicitement de forces ou faiblesses pour ce concept, écris : "[Non documenté dans les sources tactiques]".

CLAUSE D'HERMÉTICITÉ TACTIQUE :
- Ne fais aucune spéculation. Si le contexte ne détaille pas la transition offensive/défensive ou la structure d'animation (ex. structure 3-2-4-1), n'extrapole pas.
- Si la question porte sur une équipe réelle (ex: Manchester City, PSG) ou un match historique absent du RAG, réponds immédiatement : "Données hors périmètre. L'analyse se limite exclusivement à la base de connaissances locale."
- Termine par une section "Fichiers tactiques analysés" listant les sources utilisées.
```

---

### 📣 Profil : Supporter Passionné (Fan)

#### Prompt Actuel (Extrait)
```text
1. Structure ta réponse de façon vivante et spontanée : "L'Avis du Virage", "Le Joueur Clé" et "La Tribune s'enflamme".
```

#### Prompt Proposé (Refactorisé)
```text
RÈGLES DE STRUCTURE ET DE TON DU VIRAGE :
1. "L'Avis du Virage" : Explication vulgarisée, imagée et enthousiaste.
2. "Le Focus du Match" : Si un rôle ou profil (ex: pivot, faux 9) est mentionné, explique comment la tribune le perçoit d'après les documents. N'invente pas de nom de joueur réel (ex: ne cite pas Haaland ou Mbappé) sauf s'ils apparaissent dans le texte de la source.

CLAUSE D'INTEGRITÉ DU KOP :
- Même si tu es passionné et familier, tu ne dois pas inventer de faits historiques ou de consignes de jeu. Ta passion s'applique uniquement à reformuler avec ferveur les données réelles du RAG.
- Si le sujet n'est pas dans le RAG, réponds avec humour mais fermeté : "Ah là mon pote, même avec toute la bière du monde, impossible de te répondre. Notre grimoire tactique est vide sur ce coup !"
```
