# CTO Roadmap Review - Football IQ Assistant

## Position CTO

Le projet ne doit pas etre pilote par la question "que peut faire l'IA ?", mais par la question "qu'est-ce qu'un coach utilisera chaque semaine parce que cela lui fait gagner du temps avant l'entrainement ou le match ?".

La reponse la plus probable n'est pas la video au depart. La valeur hebdomadaire la plus rapide est :

1. preparer une seance d'entrainement exploitable en 10 minutes ;
2. adapter cette seance a l'effectif reel du coach ;
3. preparer le prochain match avec un plan simple ;
4. reutiliser et ameliorer les plans precedents semaine apres semaine.

Le produit doit donc commencer comme un outil de preparation coach, pas comme un chatbot generaliste, pas comme une plateforme analyste complete, et pas comme un outil de computer vision.

## 1. Analyse critique de la roadmap actuelle

La roadmap actuelle est bien structuree sur le papier : elle separe les modes, le RAG, les prompts, les templates, les exports, l'effectif, les donnees de match, la video et le SaaS. Elle montre aussi une bonne conscience des risques techniques : eviter Pinecone/Weaviate au debut, eviter la computer vision, repousser Stripe et l'auth complexe.

Le probleme principal est l'ordre des priorites. La roadmap donne encore trop d'espace a des elements qui ne prouvent pas la retention coach : mode Fan, posts reseaux sociaux, "effet wow", video fictive, JSON de match, architecture SaaS, visualisations de donnees. Ces sujets peuvent etre utiles plus tard, mais ils ne repondent pas directement a l'objectif central : faire revenir un coach chaque semaine.

Le risque CTO est de construire un assistant impressionnant mais interchangeable avec ChatGPT. Pour eviter cela, il faut concentrer la V1 sur des workflows repetes : "je prepare ma seance", "je note ce qui a marche", "je prepare le match suivant", "je garde mon historique de semaines".

## 2. Ce qui est bon

- La vision "Football Intelligence" est meilleure qu'un simple chatbot football.
- Les modes Coach / Analyste / Fan clarifient les intentions utilisateur.
- Les reponses structurees sont une bonne decision produit : un coach n'a pas besoin d'un long texte, il a besoin d'un plan utilisable.
- Le RAG football local est adapte a un budget faible.
- Les sources visibles peuvent augmenter la confiance.
- L'export PDF est pertinent si le PDF devient une fiche terrain imprimable.
- La prudence sur la video et le SaaS est saine.
- L'idee d'ajouter le contexte de l'equipe est probablement le vrai levier de retention.

## 3. Ce qui est premature

- Le mode Fan dans le MVP coach. Il dilue le produit et attire des usages qui ne prouvent pas l'adoption par les coachs.
- Les posts X/TikTok/Reels. Utile pour acquisition, pas pour retention coach.
- L'effet wow UI. L'interface doit etre claire et rapide, pas spectaculaire.
- Le RAG trop ambitieux. 20 fiches excellentes valent mieux que 100 fiches moyennes.
- Les donnees de match et visualisations terrain avant d'avoir des coachs qui utilisent deja les seances.
- Les mock JSON video. Preparer une architecture future est acceptable, mais interroger des donnees fictives n'apporte pas de valeur utilisateur.
- Stripe, multi-tenancy, roles staff, securite avancee avant validation.
- Computer vision, tracking, YOLO, clipping automatique : beaucoup trop cher et trop risque pour un developpeur seul.

## 4. Ce qui manque

- Un workflow hebdomadaire explicite pour le coach.
- Une notion de saison, semaine, objectif d'entrainement, prochain match.
- Un profil d'equipe minimal : age/categorie, niveau, systeme prefere, contraintes, effectif simplifie.
- Une boucle de feedback : "cette seance a-t-elle ete utile ?", "qu'est-ce qui a marche ?", "que changer la semaine prochaine ?".
- Des templates vraiment terrain : duree, materiel, nombre de joueurs, espace, consignes, variantes, criteres de reussite.
- Une bibliotheque personnelle de seances sauvegardees.
- Des exemples pre-remplis pour reduire la page blanche.
- Une strategie d'acquisition terrain : clubs locaux, educateurs, groupes WhatsApp, LinkedIn, X, districts, academies.
- Des metriques simples : seances generees, seances exportees, coachs actifs hebdomadaires, retours notes, reutilisation semaine suivante.

## 5. Analyse des phases

### Phase 1 - Football Assistant MVP

| Angle | Analyse |
| --- | --- |
| Objectif | Valider que des coachs utilisent l'outil pour preparer une seance reelle chaque semaine. |
| Valeur utilisateur | Gain de temps immediat : transformer un objectif d'entrainement en fiche terrain claire. |
| Complexite | Faible a moyenne. Le danger n'est pas technique, il est qualitatif : les sorties doivent etre bonnes. |
| Dependances | API LLM, prompts Coach solides, 15-25 fiches football de qualite, UI chat simple, export/copie. |
| Risques | Reponses generiques, seances trop theoriques, absence de contexte equipe, produit percu comme ChatGPT avec un skin. |
| Fonctionnalites minimum | Mode Coach uniquement, generation de seance, plan de match simple, sources, copier/export PDF, exemples de prompts, collecte feedback. |
| Fonctionnalites a repousser | Mode Fan, mode Analyste avance, historique complexe, auth complete, base vectorielle lourde, video, donnees match. |
| Temps estime | 3 a 5 semaines pour une beta utilisable. |

Verdict CTO : Phase 1 doit etre plus stricte. Elle ne doit pas etre "chat 3 modes", elle doit etre "assistant de preparation coach".

### Phase 2 - Football Expert Platform

| Angle | Analyse |
| --- | --- |
| Objectif | Rendre les reponses personnalisees a l'equipe du coach pour creer de la retention. |
| Valeur utilisateur | Tres forte : "adapte ma seance a mes U15, mon effectif, mes problemes actuels". |
| Complexite | Moyenne si le perimetre reste simple. |
| Dependances | Auth minimale, stockage equipe, sauvegarde seances, profil joueurs simplifie, historique. |
| Risques | Trop de formulaires, ingestion PDF fragile, donnees trop longues a saisir, complexite DB prematuree. |
| Fonctionnalites minimum | Une equipe par utilisateur, categorie/niveau/systeme, 12-25 joueurs avec poste et 3 tags, objectifs de la semaine, seances sauvegardees, feedback apres seance. |
| Fonctionnalites a repousser | Multi-equipes, staff complet, permissions, upload PDF complexe, pgvector obligatoire, statistiques avancees. |
| Temps estime | 4 a 6 semaines apres Phase 1. |

Verdict CTO : C'est probablement la phase la plus importante pour revenir chaque semaine. Elle doit passer avant Match Intelligence.

### Phase 3 - Match Intelligence

| Angle | Analyse |
| --- | --- |
| Objectif | Aider le coach a preparer le prochain match et a tirer des enseignements du dernier match. |
| Valeur utilisateur | Elevee si l'entree de donnees est simple. Faible si le coach doit importer des formats complexes. |
| Complexite | Moyenne a elevee selon la source de donnees. |
| Dependances | Produit coach deja utilise, historique d'equipe, modele de rapport de match, event data disponible ou saisie manuelle simplifiee. |
| Risques | Peu de coachs amateurs ont des donnees Wyscout/Hudl/StatsBomb ; les visualisations peuvent devenir un demo technique sans usage reel. |
| Fonctionnalites minimum | Rapport de match manuel guide : score, systeme adverse, problemes observes, moments cles, plan semaine suivante. Option CSV/JSON seulement si donnees disponibles. |
| Fonctionnalites a repousser | Shot maps automatiques, passing networks, imports Wyscout/Hudl generiques, visualisations interactives, analyse adversaire automatisee avancee. |
| Temps estime | 4 a 8 semaines selon le niveau de donnees vise. |

Verdict CTO : commencer par un "match review assistant" manuel avant les donnees evenementielles.

### Phase 4 - Football Copilot

| Angle | Analyse |
| --- | --- |
| Objectif | Passer d'un generateur ponctuel a un copilote de saison : planifier, suivre, recommander. |
| Valeur utilisateur | Tres forte si l'outil devient le rituel du lundi/dimanche soir du coach. |
| Complexite | Moyenne. Beaucoup de valeur peut etre creee avec peu de technologie. |
| Dependances | Comptes utilisateurs, historique, equipe, seances sauvegardees, feedback, objectifs. |
| Risques | Trop automatiser sans confiance, recommandations vagues, notifications inutiles. |
| Fonctionnalites minimum | Tableau "cette semaine", objectifs, prochaine seance, dernier feedback, plan de progression sur 4 semaines, rappels email simples. |
| Fonctionnalites a repousser | Mobile app, calendriers complexes, staff, IA proactive multi-agent, integrations club. |
| Temps estime | 6 a 10 semaines apres validation des phases 1 et 2. |

Verdict CTO : cette phase devrait etre plus haute dans la strategie que la video. C'est elle qui peut creer l'habitude hebdomadaire.

### Phase 5 - Video Intelligence

| Angle | Analyse |
| --- | --- |
| Objectif | Reduire le temps d'analyse video et relier actions de match, clips et recommandations. |
| Valeur utilisateur | Potentiellement tres forte, mais seulement pour les coachs qui filment deja et acceptent un workflow plus lourd. |
| Complexite | Elevee a tres elevee. Cout infra, stockage, formats video, UX, droits, temps de traitement. |
| Dependances | Base utilisateurs active, cas d'usage prouve, stockage, FFmpeg, event tagging, event data ou tagging manuel. |
| Risques | Gouffre technique, cout GPU, upload lent, qualite detection mediocre, distraction totale avant product-market fit. |
| Fonctionnalites minimum | Pas de computer vision au debut : lecteur video + tags manuels + jump-to-time + clips courts via FFmpeg. |
| Fonctionnalites a repousser | YOLO, tracking joueurs/ballon, detection automatique d'evenements, heatmaps video, 3D, temps reel. |
| Temps estime | 3 a 6 mois pour une version utile sans computer vision ; 6 a 12 mois+ pour de la CV fiable. |

Verdict CTO : attendre. La video ne doit commencer que quand 100+ coachs actifs prouvent que le produit texte/terrain est utilise.

## 6. Roadmap recommandee

### Roadmap produit

1. **MVP Coach Terrain** : generation de seances et plans de match exploitables.
2. **Coach Workspace** : equipe, contraintes, sauvegarde, feedback, reutilisation.
3. **Weekly Coaching Loop** : rituel hebdomadaire, objectifs, progression, rappels.
4. **Match Review Simple** : analyse de match manuelle guidee, recommandations pour la semaine.
5. **Expert Layer** : analyste, scouting, data imports seulement pour les coachs avances.
6. **Video Light** : tags manuels, timeline, clips.
7. **Video Intelligence** : detection automatique uniquement si usage et budget le justifient.

### Roadmap technique

1. Frontend simple + backend API + LLM.
2. Prompts Coach et templates stricts.
3. RAG local avec fichiers Markdown selectionnes.
4. Stockage leger : SQLite ou Postgres selon deploy choisi.
5. Auth minimale quand sauvegarde necessaire.
6. Export PDF robuste.
7. Analytics produit basiques.
8. Plus tard : pgvector, imports, video, paiements.

## 7. Backlog priorise

### P0 - Construire la valeur coach

| Priorite | Tache | Raison |
| --- | --- | --- |
| P0 | Prompt Coach terrain strict | La qualite des reponses fait ou tue le produit. |
| P0 | Template seance complet | Le coach doit pouvoir utiliser la sortie directement. |
| P0 | 20 fiches knowledge base haute qualite | Differenciation vs ChatGPT generaliste. |
| P0 | UI simple avec exemples pre-remplis | Reduit la page blanche. |
| P0 | Copier + export PDF propre | Passage du chat au terrain. |
| P0 | Feedback apres generation | Mesure la qualite et ameliore le produit. |
| P0 | Analytics WAU / exports / retours | Sans mesure, impossible de piloter. |

### P1 - Creer la retention

| Priorite | Tache | Raison |
| --- | --- | --- |
| P1 | Auth minimale | Necessaire pour sauvegarder. |
| P1 | Profil equipe simple | Personnalisation hebdomadaire. |
| P1 | Bibliotheque de seances | Reutilisation et historique. |
| P1 | Feedback post-seance | Boucle d'apprentissage. |
| P1 | Plan sur 4 semaines | Rend l'outil recurrent. |
| P1 | Email recap hebdomadaire | Ramene le coach dans le produit. |

### P2 - Elargir apres validation

| Priorite | Tache | Raison |
| --- | --- | --- |
| P2 | Mode Analyste | Utile quand la base coach est active. |
| P2 | Match review manuel | Forte valeur sans dependance data. |
| P2 | Upload documents simple | Peut enrichir le contexte, mais fragile. |
| P2 | Imports CSV/JSON | Pour utilisateurs avances seulement. |
| P2 | Paiement Stripe | Apres preuve de demande. |

### P3 - Attendre

| Priorite | Tache | Raison |
| --- | --- | --- |
| P3 | Mode Fan | Pas central pour 100 coachs WAU. |
| P3 | Reseaux sociaux | Acquisition possible, retention faible. |
| P3 | Visualisations avancees | Demo utile, pas priorite. |
| P3 | Video intelligence | Trop complexe avant traction. |
| P3 | Multi-tenancy staff | Trop tot. |

## 8. Plan sur 12 mois

### Mois 1 - MVP Coach Terrain

- Construire uniquement le mode Coach.
- Rediger les prompts et 20 fiches football.
- Generer seances, plans de match, exercices, variantes.
- Ajouter copier, PDF, sources, feedback.
- Tester avec 10 coachs connus.

### Mois 2 - Beta terrain

- Corriger les sorties selon les retours.
- Ajouter exemples de demandes par objectif : pressing, bloc bas, transition, finition, relance.
- Lancer a 30-50 coachs.
- Mesurer : seances generees, PDF exports, retours positifs, retour semaine suivante.

### Mois 3 - Personnalisation equipe

- Auth minimale.
- Profil equipe : categorie, niveau, systeme, contraintes, nombre de joueurs.
- Fiches joueurs simplifiees.
- Adapter les seances au contexte reel.

### Mois 4 - Retention hebdomadaire

- Bibliotheque de seances.
- Feedback post-seance.
- Plan de progression sur 4 semaines.
- Email recap hebdomadaire.
- Objectif : 30 coachs actifs hebdomadaires.

### Mois 5 - Amelioration qualite

- Enrichir la knowledge base selon les questions reelles.
- Ajouter tests de qualite sur les templates.
- Ajouter scoring interne des reponses.
- Interviewer 15 coachs actifs.

### Mois 6 - Match Review Simple

- Formulaire guide apres match.
- Rapport : problemes, causes probables, priorites semaine suivante.
- Lier match review aux prochaines seances.
- Objectif : 50 coachs actifs hebdomadaires.

### Mois 7 - Coach Copilot V1

- Tableau "cette semaine".
- Objectifs, seance prevue, dernier feedback, prochain match.
- Recommandations basees sur l'historique.

### Mois 8 - Distribution et preuve marche

- Programme ambassadeurs coachs.
- Templates publics partageables.
- Landing simple orientee coachs.
- Collecter temoignages et cas reels.
- Objectif : 75 coachs actifs hebdomadaires.

### Mois 9 - Monetisation legere

- Offre payante simple si usage recurrent prouve.
- Stripe Checkout seulement, pas de SaaS complexe.
- Plan gratuit limite + plan coach individuel.

### Mois 10 - Expert Layer

- Mode Analyste limite aux coachs avances.
- Rapports adversaire manuels.
- Import CSV/JSON en option, pas au coeur du produit.

### Mois 11 - Video Light Discovery

- Prototyper lecteur video + tags manuels avec 3-5 coachs tres motives.
- Pas de computer vision.
- Valider si le workflow video est vraiment demande.

### Mois 12 - Consolidation

- Doubler ce qui marche.
- Supprimer les fonctions peu utilisees.
- Stabiliser cout LLM, qualite, onboarding.
- Objectif : 100 coachs actifs hebdomadaires.

## 9. MVP absolu

Objectif : savoir en moins d'un mois si un coach prefere utiliser Football IQ Assistant plutot que ChatGPT pour preparer sa semaine.

Fonctionnalites :

- Une page web.
- Mode Coach uniquement.
- 8 a 12 exemples de demandes.
- Generation de fiche seance.
- Generation de plan de match simple.
- Template strict : objectif, duree, materiel, organisation, consignes, variantes, criteres de reussite.
- Copier la reponse.
- Export PDF basique.
- Feedback "utile / pas utile" + commentaire.
- Analytics basiques.

Ce MVP peut etre teste sans compte utilisateur, sans vraie base de donnees et sans video.

## 10. MVP recommande

Objectif : avoir une beta credible capable de creer une habitude hebdomadaire.

Fonctionnalites :

- Tout le MVP absolu.
- RAG local avec 20 fiches football solides.
- Sources visibles.
- Auth minimale.
- Profil equipe simple.
- Sauvegarde des seances.
- Feedback post-seance.
- Plan de progression sur 4 semaines.
- Email recap hebdomadaire.
- Dashboard minimal "ma semaine".

Ce MVP est le meilleur compromis valeur / complexite pour atteindre 100 coachs actifs hebdomadaires.

## 11. Fonctionnalites qui doivent attendre

- Mode Fan.
- Threads X/TikTok/Reels.
- Mode Analyste avance.
- Comparaison de joueurs avancee.
- Scouting complet.
- Import PDF complexe.
- pgvector si le RAG local suffit.
- Shot maps et passing networks.
- Wyscout/Hudl imports.
- Video upload.
- Clipping automatique.
- YOLO / tracking / detection ballon.
- Multi-staff, multi-club, permissions avancees.
- Stripe avant preuve de retention.
- Application mobile.

## 12. Sequence exacte pour obtenir 100 coachs actifs hebdomadaires avant fin 2026

Si l'objectif est 100 coachs actifs hebdomadaires avant le 31 decembre 2026, je suivrais cette sequence exacte :

### Semaine 1

- Supprimer le mode Fan du perimetre actif.
- Mettre le mode Analyste en arriere-plan.
- Ecrire le prompt Coach comme le coeur du produit.
- Definir 5 sorties obligatoires : seance, plan de match, correction de probleme tactique, cycle de 4 semaines, consignes joueurs.

### Semaines 2-3

- Construire le MVP Coach terrain.
- Ajouter 20 fiches RAG maximum, mais excellentes.
- Ajouter copier, PDF, sources et feedback.
- Pas d'auth, pas de DB, pas de video.

### Semaine 4

- Donner l'outil a 10 coachs.
- Les observer produire une vraie seance.
- Leur demander : "Est-ce que tu utiliserais cette fiche cette semaine sur le terrain ?"
- Corriger les templates jusqu'a obtenir des sorties directement exploitables.

### Mois 2

- Ouvrir a 30-50 coachs.
- Construire uniquement ce que les coachs demandent plusieurs fois.
- Ajouter exemples pre-remplis et onboarding ultra court.
- Mesurer les exports PDF et les retours semaine suivante.

### Mois 3

- Ajouter comptes utilisateurs et profil equipe simple.
- Ajouter sauvegarde des seances.
- Ajouter personnalisation par categorie, niveau, nombre de joueurs, contraintes terrain.

### Mois 4

- Ajouter feedback post-seance.
- Ajouter "preparer ma prochaine seance a partir de la precedente".
- Ajouter plan de 4 semaines.
- Lancer un email recap chaque debut de semaine.

### Mois 5-6

- Ajouter match review manuel.
- Relier le match review a la prochaine semaine d'entrainement.
- Ne pas faire de visualisations avancees.
- Objectif : 50 coachs actifs hebdomadaires.

### Mois 7-9

- Creer le Coach Copilot : tableau de semaine, objectifs, historique, recommandations.
- Ajouter une boucle de relance simple.
- Lancer acquisition terrain : clubs locaux, educateurs, groupes coachs, contenus LinkedIn/X avec exemples de fiches.
- Objectif : 75 coachs actifs hebdomadaires.

### Mois 10-12

- Monetiser legerement si la retention est la.
- Ajouter mode Analyste limite pour les coachs avances.
- Tester video light avec tags manuels seulement si des coachs actifs le demandent explicitement.
- Supprimer ou cacher les fonctions non utilisees.
- Objectif : 100 coachs actifs hebdomadaires.

## Reponse honnete

Pour atteindre 100 coachs actifs hebdomadaires, je ne construirais pas d'abord une plateforme complete. Je construirais un assistant de preparation de semaine pour coachs.

La fonctionnalite qui fera revenir un coach chaque semaine n'est pas "poser une question football". C'est :

> "Aide-moi a preparer ma semaine d'entrainement en fonction de mon dernier match, de mon effectif et de mon prochain objectif."

Tout ce qui ne sert pas cette boucle doit etre repousse. Le mode Fan doit attendre. La video doit attendre. Les donnees de match avancees doivent attendre. La priorite est de devenir l'outil que le coach ouvre chaque dimanche soir ou lundi matin pour transformer ses problemes de match en seance concrete.
