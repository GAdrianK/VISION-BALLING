import os
import json
from pathlib import Path
from openai import OpenAI
from app.core.config import settings

def get_temporal_metadata(minute: int) -> tuple[str, str]:
    if minute <= 45:
        periode = "1MT"
        if minute <= 15:
            intervalle = "0-15"
        elif minute <= 30:
            intervalle = "15-30"
        else:
            intervalle = "30-45"
    else:
        periode = "2MT"
        if minute <= 60:
            intervalle = "45-60"
        elif minute <= 75:
            intervalle = "60-75"
        elif minute <= 90:
            intervalle = "75-90"
        else:
            intervalle = "90+"
    return periode, intervalle

class MatchDataParser:
    def __init__(self):
        self.gemini_key = settings.gemini_key
        self.openai_key = settings.OPENAI_API_KEY
        self.openrouter_key = settings.openrouter_key
        self.use_gemini = self.gemini_key and not self.gemini_key.startswith("mock-") and len(self.gemini_key.strip()) > 0
        self.use_openai = self.openai_key and not self.openai_key.startswith("mock-") and len(self.openai_key.strip()) > 0
        self.use_openrouter = self.openrouter_key and not self.openrouter_key.startswith("mock-") and len(self.openrouter_key.strip()) > 0
        self.use_llm = self.use_gemini or self.use_openai or self.use_openrouter

    def load_json(self, json_path: str) -> dict:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def generate_markdown(self, match_data: dict) -> str:
        if self.use_llm:
            try:
                return self._generate_via_llm(match_data)
            except Exception as e:
                # Fallback to local template if LLM fails
                print(f"Erreur d'appel LLM, repli sur le générateur de template : {e}")
                return self._generate_via_template(match_data)
        else:
            return self._generate_via_template(match_data)

    def _generate_via_llm(self, match_data: dict) -> str:
        prompt = f"""
        Tu es un analyste tactique de football professionnel et un expert en data scouting.
        Traduis le rapport de données JSON ci-dessous en un document Markdown hautement rédigé, fluide et analytique (prose tactique en français).
        
        JSON du match :
        {json.dumps(match_data, indent=2, ensure_ascii=False)}
        
        Règles de formatage impératives :
        1. Le document doit démarrer par un YAML Front Matter délimité par --- contenant :
           title, competition, season, date, et teams (liste des deux équipes).
         2. Le titre principal doit être : # Match: <Home> vs <Away> (<ScoreHome> - <ScoreAway>)
        3. Le document doit utiliser ces sous-sections de niveau H2 pour l'analyse des statistiques d'équipe :
           - ## Construction & Sortie
           - ## Organisation Offensive
           - ## Organisation Défensive
           - ## Transitions
        4. Crée une section de niveau H2 : ## Analyse Chronologique des Événements
        5. Dans cette section, crée une sous-section H3 pour CHAQUE événement clé du match :
           ### Événement : <Minute>ème minute
           Rédige l'analyse de cet événement dans le paragraphe correspondant, et ajoute obligatoirement à la fin du paragraphe son tag temporel HTML exact :
           - Événement 12' : <!-- @time: periode=1MT, intervalle=0-15 -->
           - Événement 34' : <!-- @time: periode=1MT, intervalle=30-45 -->
           - Événement 55' : <!-- @time: periode=2MT, intervalle=45-60 -->
           - Événement 72' : <!-- @time: periode=2MT, intervalle=60-75 -->
        6. Intègre toutes les statistiques globales (possession, passes, tirs, xG, PPDA, style de bloc) dans les sections H2 correspondantes.
        7. N'invente pas de faits non inclus dans le JSON. Reste purement focalisé sur la prose footballistique analytique et technique.
        """
        if self.use_openrouter:
            try:
                client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=self.openrouter_key
                )
                try:
                    response = client.chat.completions.create(
                        model="qwen/qwen-2.5-72b-instruct:free",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.2
                    )
                    return response.choices[0].message.content
                except Exception as e:
                    print(f"[WARNING] Erreur OpenRouter Qwen gratuit dans match_parser : {e}. Tentative avec la version payante.")
                    response = client.chat.completions.create(
                        model="qwen/qwen-2.5-72b-instruct",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.2
                    )
                    return response.choices[0].message.content
            except Exception as e2:
                print(f"Erreur OpenRouter dans _generate_via_llm: {e2}")
                if not self.use_gemini and not self.use_openai:
                    raise e2

        if self.use_gemini and not self.use_openrouter:
            try:
                from google import genai
                client = genai.Client(api_key=self.gemini_key)
                response = client.models.generate_content(
                    model="gemini-flash-latest",
                    contents=prompt
                )
                return response.text
            except Exception as e:
                print(f"Erreur Gemini dans _generate_via_llm: {e}")
                if not self.use_openai:
                    raise e
        
        if self.use_openai and not self.use_gemini and not self.use_openrouter:
            client = OpenAI(api_key=self.openai_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            return response.choices[0].message.content

        raise RuntimeError("Aucune clé d'API LLM configurée pour _generate_via_llm.")

    def _generate_via_template(self, match_data: dict) -> str:
        meta = match_data["meta"]
        stats = match_data["team_stats"]
        events = match_data["key_events"]
        
        home = meta["home_team"]
        away = meta["away_team"]
        
        # Génération des paragraphes pour chaque section
        const_text = (
            f"Le {home} a privilégié une phase de relance structurée et posée, totalisant {stats[home]['passes_completed']} passes complétées "
            f"avec une volonté verticale marquée par {stats[home]['passes_progressive']} passes progressives. "
            f"De son côté, l'{away} s'est montré plus en retrait dans sa phase de relance avec {stats[away]['passes_completed']} passes complétées "
            f"et seulement {stats[away]['passes_progressive']} passes progressives.\n"
        )

        off_text = (
            f"L'organisation offensive du {home} s'est montrée particulièrement dangereuse avec {stats[home]['shots']} tirs au total "
            f"dont {stats[home]['shots_on_target']} cadrés, générant un total d'Expected Goals (xG) de {stats[home]['xg']:.2f}. "
            f"L'{away} a tenté de répliquer par des contres, totalisant {stats[away]['shots']} tirs dont {stats[away]['shots_on_target']} cadrés "
            f"pour un total de {stats[away]['xg']:.2f} xG.\n"
        )

        def_text = (
            f"Sur le plan défensif, le {home} a évolué avec un style de {stats[home]['bloc_style']}, maintenant un pressing "
            f"intense comme en témoigne son PPDA de {stats[home]['ppda']:.1f}. En réponse, l'{away} a structuré son organisation "
            f"défensive autour d'un {stats[away]['bloc_style']} compact, acceptant de subir le jeu tout en appliquant un "
            f"pressing moins étouffant (PPDA de {stats[away]['ppda']:.1f}).\n"
        )

        trans_text = (
            f"Les transitions de balle ont vu le {home} imposer son style de contre-pressing haut, tandis que l'{away} "
            f"a tenté d'exploiter la profondeur dès la récupération pour prendre à revers la rest defense parisienne."
        )

        # Génération des sous-sections H3 pour chaque événement chronologique
        chronology_text = ""
        for ev in events:
            p, i = get_temporal_metadata(ev["minute"])
            chronology_text += f"\n### Événement : {ev['minute']}ème minute\n"
            chronology_text += f"{ev['description']} <!-- @time: periode={p}, intervalle={i} -->\n"

        markdown = f"""---
title: "Analyse Tactique du Match : {home} vs {away} ({meta['score_home']}-{meta['score_away']})"
competition: "{meta['competition']}"
season: "{meta['saison']}"
date: "{meta['date']}"
teams: ["{home}", "{away}"]
---

# Match: {home} vs {away} ({meta['score_home']} - {meta['score_away']})

Ce document présente l'analyse tactique et statistique de la confrontation opposant le {home} et l'{away} dans le cadre de la compétition {meta['competition']}.

## Construction & Sortie
{const_text}
## Organisation Offensive
{off_text}
## Organisation Défensive
{def_text}
## Transitions
{trans_text}

## Analyse Chronologique des Événements
{chronology_text}
"""
        return markdown

    def parse_and_save(self, json_path: str, output_dir: str) -> str:
        match_data = self.load_json(json_path)
        markdown_content = self.generate_markdown(match_data)
        
        match_id = match_data["match_id"]
        output_filename = f"match_{match_id}.md"
        output_path = os.path.join(output_dir, output_filename)
        
        os.makedirs(output_dir, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
            
        print(f"Rapport Markdown généré avec succès dans : {output_path}")
        return output_path
