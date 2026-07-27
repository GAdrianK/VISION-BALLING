# 📋 T-09 : Persistence Locale & Actions Rapides

## Objectif

Enrichir le frontend du Football IQ Assistant avec :
1. La sauvegarde et restauration de session via `localStorage`
2. Des boutons d'action fonctionnels sur chaque réponse : **Copier**, **Simplifier**, **Approfondir**
3. La connexion du bouton **Export PDF** à `/api/export-pdf`

---

## Périmètre exact

### Inclus
- `localStorage` : sauvegarde après chaque échange, restauration au rechargement, nettoyage à "Nouvelle session"
- Bouton **Copier** : copie le texte brut de la réponse + feedback "Copié !" 2 secondes
- Bouton **Simplifier** : POST `/api/chat` avec préfixe "Simplifie cette réponse..."
- Bouton **Approfondir** : POST `/api/chat` avec préfixe "Approfondis cette réponse..."
- Bouton **Export PDF** : POST `/api/export-pdf` avec le texte de la réponse

### Exclu
- Pas d'historique multi-sessions
- Pas de login
- Pas de base de données
- Pas de modification du backend

---

## Fichiers concernés

| Fichier | Action |
|---|---|
| `frontend/app.js` | Principaux changements : localStorage, actions boutons |
| `frontend/styles.css` | Micro-styles pour feedback "Copié !" et état actif des boutons |

---

## Plan d'implémentation

### 1. localStorage helpers
- `saveSession()` : `localStorage.setItem('fiq_session', JSON.stringify(currentSession))`
- `loadSession()` : lire et valider la session sauvegardée au démarrage
- `clearSession()` : `localStorage.removeItem('fiq_session')` appelé dans `resetSession()`

### 2. Restauration au démarrage
- Si une session valide existe dans `localStorage`, restaurer les messages et le mode
- Re-rendre tous les messages dans le DOM via `createMessageElement`
- Réactiver la bonne carte de mode dans la sidebar

### 3. Sauvegarde après chaque échange
- Appeler `saveSession()` après chaque `currentSession.messages.push(...)`

### 4. Bouton Copier
- Lire `content` depuis le paramètre de `createMessageElement`
- `navigator.clipboard.writeText(content)`
- Changer le texte du bouton en "✅ Copié !" pendant 2 secondes

### 5. Boutons Simplifier / Approfondir
- Créer `handleQuickAction(prompt)` qui appelle `handleSendMessage` avec un message préfabriqué
- Le message est construit avec le contenu brut de la réponse précédente

### 6. Bouton Export PDF
- POST `/api/export-pdf` avec `{ content: responseText, mode: currentSession.mode }`
- Télécharger le blob PDF retourné via `URL.createObjectURL`

---

## Critères de validation

- [ ] Poser une question → recharger la page → la conversation revient
- [ ] Cliquer "Nouvelle session" → conversation disparaît + localStorage vidé
- [ ] Cliquer "Copier" → texte copié dans le presse-papier + feedback visuel
- [ ] Cliquer "Simplifier" → nouvelle réponse simplifiée dans le chat
- [ ] Cliquer "Approfondir" → nouvelle réponse détaillée dans le chat
- [ ] Cliquer "Export PDF" → téléchargement du PDF ou message clair
- [ ] Les tests backend passent toujours (`pytest` 18/18)
