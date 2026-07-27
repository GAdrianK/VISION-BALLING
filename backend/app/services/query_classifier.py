import re
from typing import Dict, Any

class QueryClassifier:
    """
    Classifie les requêtes de l'utilisateur pour déterminer le type
    (salutation, hors-sujet, question tactique) et extraire les intentions sémantiques.
    """
    def __init__(self):
        # Mots-clés pour les salutations
        self.greeting_patterns = [
            r"\b(salut|bonjour|bonsoir|hello|hey|yo|coucou|hi)\b",
            r"\bca\s+va\b",
            r"\bcomment\s+ca\s+va\b",
            r"\bcomment\s+allez-vous\b",
            r"\bcomment\s+vas-tu\b"
        ]
        
        # Mots-clés hors-sujet (cuisine, météo, actualités, politique, etc.)
        self.out_of_scope_patterns = [
            r"\bpizza\b",
            r"\brecette\b",
            r"\bcuisine\b",
            r"\bmeteo\b",
            r"\bmétéo\b",
            r"\bpolitique\b",
            r"\bcinema\b",
            r"\bcinéma\b",
            r"\bfilm\b",
            r"\bmusique\b",
            r"\bchanson\b",
            r"\bprésident\b",
            r"\bpresident\b",
            r"\bmacron\b",
            r"\bgouvernement\b",
            r"\bclimat\b"
        ]

        # Dictionnaires d'intentions
        self.intent_keywords = {
            "defend": [
                "défend", "defend", "couliss", "compac", "fermer l'axe", "défens", "defens",
                "marquage", "recul-frein", "garer le bus", "fermer les espaces", "repli", "reconstitution"
            ],
            "attack": [
                "attaqu", "attack", "déséquilibr", "desequilibr", "percer", "contourn", "marqu",
                "offens", "centr", "dédoubl", "dedoubl", "amplitude", "surcharge", "overload",
                "underlap", "overlap", "creer des espaces", "créer des espaces"
            ],
            "roles": [
                "faux 9", "pivot", "double pivot", "box-to-box", "gardien-libero", "gardien-libéro",
                "sweeper keeper", "inverted fullback", "latéral inversé", "relayeur", "mezzala",
                "raumdeuter", "inside forward", "piston"
            ],
            "formations": [
                "4-3-3", "3-5-2", "4-4-2", "3-4-3", "3-2-4-1", "4-2-3-1",
                "433", "352", "442", "343", "3241", "4231",
                "système", "systeme", "formation"
            ]
        }

        # Dictionnaires de phases
        self.phase_keywords = {
            "offensive": ["attaqu", "offens", "possession", "construction", "finition"],
            "defensive": ["défend", "défens", "defens", "repli", "recule", "coulisse", "marquage"],
            "transition": ["transition", "contre-press", "gegenpress", "récupér", "perte", "contre-attaq", "recupér"]
        }

    def classify(self, message: str) -> Dict[str, Any]:
        """
        Analyse le message et renvoie sa classification complète.
        """
        msg_lower = message.lower().strip()
        
        # 1. Vérification des Salutations
        is_greeting = False
        for pattern in self.greeting_patterns:
            if re.search(pattern, msg_lower):
                is_greeting = True
                break
                
        if is_greeting:
            return {
                "type": "greeting",
                "intent": "general",
                "phase": "general"
            }
            
        # 2. Vérification des Hors-Sujets
        is_out_of_scope = False
        for pattern in self.out_of_scope_patterns:
            if re.search(pattern, msg_lower):
                is_out_of_scope = True
                break
                
        if is_out_of_scope:
            return {
                "type": "out_of_scope",
                "intent": "general",
                "phase": "general"
            }
            
        # 3. Extraction des Intentions Tactiques
        detected_intent = "general"
        for intent, keywords in self.intent_keywords.items():
            for kw in keywords:
                if kw in msg_lower:
                    # Permet de prioriser les intentions spécifiques (attack/defend)
                    if detected_intent == "general" or detected_intent in ["roles", "formations"]:
                        detected_intent = intent
                    break
                    
        # 4. Extraction de la Phase de Jeu
        detected_phase = "general"
        for phase, keywords in self.phase_keywords.items():
            for kw in keywords:
                if kw in msg_lower:
                    detected_phase = phase
                    break
                    
        return {
            "type": "tactical_question",
            "intent": detected_intent,
            "phase": detected_phase,
            "entities": self.extract_tactical_entities(message)
        }

    def extract_tactical_entities(self, text: str) -> Dict[str, Any]:
        """
        Extrait les entités tactiques clés de la requête (formation, problem, phase, goal).
        """
        msg_lower = text.lower().strip()
        
        # 1. Extraction de la formation
        formation = None
        formations_patterns_hyphens = [
            r"4-3-3", r"3-5-2", r"4-4-2", r"3-4-3", r"3-2-4-1", r"4-2-3-1", r"5-4-1", r"4-1-4-1"
        ]
        for pattern in formations_patterns_hyphens:
            if re.search(r"\b" + pattern + r"\b", msg_lower):
                formation = pattern
                break
        
        if not formation:
            formations_no_hyphens = {
                "433": "4-3-3",
                "352": "3-5-2",
                "442": "4-4-2",
                "343": "3-4-3",
                "3241": "3-2-4-1",
                "4231": "4-2-3-1",
                "541": "5-4-1",
                "4141": "4-1-4-1"
            }
            for raw, normalized in formations_no_hyphens.items():
                if re.search(r"\b" + raw + r"\b", msg_lower):
                    formation = normalized
                    break

        # 2. Extraction du problème
        problem = None
        problem_keywords = {
            "pertes de balle": ["perdre", "perte", "perd", "déchet", "dechet"],
            "manque d'occasions": ["occasion", "creer", "créer"],
            "difficulté à défendre": ["defend", "défend", "buts", "encaiss", "transperce", "subit", "dédoubl", "dedoubl"],
            "manque d'intensité": ["intensité", "intensite", "physique", "fatigue", "epuis", "épuis"],
            "erreurs": ["erreur", "faute", "bavure"],
            "isolement": ["isol"]
        }
        for category, keywords in problem_keywords.items():
            if any(kw in msg_lower for kw in keywords):
                problem = category
                break

        # 3. Extraction de la phase de jeu
        phase = None
        phase_keywords = {
            "relance": ["relance", "construction", "sortie de balle", "sortie de press", "ressortir", "build-up", "build up", "relancent", "sortie_balle"],
            "pressing": ["pressing", "contre-press", "gegenpress", "chasser", "harcel", "presser haut"],
            "transition": ["transition", "contre-attaq", "contre", "repli", "contre-defens", "rest defense", "défense préventive"],
            "bloc bas": ["bloc bas", "bloc-bas", "defendre bas", "défendre bas", "entre les lignes", "interlignes"],
            "attaque placée": ["attaque placee", "attaque placée", "possession", "circul"],
            "finition": ["finition", "marquer", "tirer", "centre", "devant le but", "surface"]
        }
        for category, keywords in phase_keywords.items():
            if any(kw in msg_lower for kw in keywords):
                phase = category
                break

        # 4. Extraction du but/goal
        goal = None
        goal_keywords = {
            "améliorer": ["ameliorer", "améliorer", "optimiser", "perfectionner", "developper", "développer"],
            "corriger": ["corriger", "eviter", "éviter", "resoudre", "résoudre", "que faire", "comment faire", "remédier", "remedier", "n’arrive pas", "arrive pas"],
            "préparer": ["preparer", "préparer", "entrainer", "entraîner", "seance", "séance", "exercice"],
            "comprendre": ["comprendre", "expliquer", "c'est quoi", "qu'est-ce que", "analyse", "difference", "différence"],
            "défendre": ["defendre", "défendre", "bloquer", "intercepter", "empecher", "empêcher", "coulisser"],
            "attaquer": ["attaquer", "percer", "passer", "trouver le", "marquer"]
        }
        for category, keywords in goal_keywords.items():
            if any(kw in msg_lower for kw in keywords):
                goal = category
                break

        return {
            "formation": formation,
            "problem": problem,
            "phase": phase,
            "goal": goal
        }

