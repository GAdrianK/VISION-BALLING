import os
import logging
import sqlite3
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

# Résolution robuste du chemin de base du backend
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(dotenv_path=BASE_DIR / ".env")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

from app.core.config import settings

app = FastAPI(
    title="Football IQ - Professional Tactical Engine",
    description="API de scouting européen propulsée par Qwen 2.5 & SQLite",
    docs_url="/docs" if settings.is_docs_enabled else None,
    redoc_url="/redoc" if settings.is_docs_enabled else None,
    openapi_url="/openapi.json" if settings.is_docs_enabled else None,
)

cors_origins = settings.cors_allowed_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True if cors_origins != ["*"] else False,
    allow_methods=["GET", "POST", "OPTIONS", "DELETE", "PUT"] if settings.APP_ENV == "production" else ["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.APP_ENV == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"
    return response


@app.middleware("http")
async def safe_production_logging_middleware(request, call_next):
    import time
    import uuid

    start_time = time.perf_counter()
    request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:10]}"

    response = await call_next(request)

    duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
    # Log only method, clean URL path (no query parameters or tokens), status, and duration
    logging.getLogger("uvicorn.access").info(
        "request_id=%s method=%s path=%s status=%d duration_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    response.headers["X-Request-ID"] = request_id
    return response

from app.services.rag_engine import RAGEngine

# Initialisation globale du moteur RAG
rag_engine = RAGEngine(
    knowledge_base_dir=settings.get_kb_dir(),
    openai_api_key=settings.OPENAI_API_KEY
)
rag_engine.initialize()

from app.api.chat import router as chat_router
from app.api.pdf import router as pdf_router
from app.api.video_analysis import router as video_analysis_router
from app.api.beta import router as beta_router
from app.api.admin_publications import router as admin_publications_router

app.include_router(chat_router)
app.include_router(pdf_router)
app.include_router(video_analysis_router)
app.include_router(beta_router)
app.include_router(admin_publications_router)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY or "mock-key" in OPENROUTER_API_KEY:
    print("⚠️ WARNING: OPENROUTER_API_KEY is not configured or is a mock key! Calls to Qwen LLM will fail with 401.")
else:
    print("🚀 OPENROUTER_API_KEY correctly loaded.")

ai_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY or "mock-key-not-for-network-use"
)

DB_PATH = str(BASE_DIR / "data" / "football_iq.db")

class AnalysisRequest(BaseModel):
    prompt: str
    season: Optional[str] = "season_2025_2026_summary"

def fetch_player_stats_from_db(player_query: str, season: str, use_ldc: bool = False):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        season_prefix = season.replace("_summary", "") + "_%"
        
        if use_ldc:
            cursor.execute("""
                SELECT player_name, 
                       team_name,
                       minutes_played AS minutes, 
                       goals, 
                       expected_goals AS xg, 
                       expected_assists AS xa, 
                       key_passes, 
                       progressive_dribbles AS dribbles_prog, 
                       defensive_pressures AS pressions_def 
                FROM player_match_stats 
                WHERE player_name LIKE ? AND match_id LIKE ? AND competition = 'Champions League'
                LIMIT 5
            """, (f"%{player_query}%", season_prefix))
        else:
            cursor.execute("""
                SELECT player_name, 
                       MAX(team_name) AS team_name,
                       SUM(minutes_played) AS minutes, 
                       SUM(goals) AS goals, 
                       ROUND(SUM(expected_goals), 1) AS xg, 
                       ROUND(SUM(expected_assists), 1) AS xa, 
                       SUM(key_passes) AS key_passes, 
                       SUM(progressive_dribbles) AS dribbles_prog, 
                       SUM(defensive_pressures) AS pressions_def 
                FROM player_match_stats 
                WHERE player_name LIKE ? AND match_id LIKE ?
                GROUP BY player_name
                LIMIT 5
            """, (f"%{player_query}%", season_prefix))
            
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as db_err:
        print(f"⚠️ SQLITE WARNING: {str(db_err)}")
        return []

def fetch_top_players_from_db(season: str, use_ldc: bool = False):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        season_prefix = season.replace("_summary", "") + "_%"
        
        if use_ldc:
            cursor.execute("""
                SELECT player_name, 
                       team_name,
                       minutes_played AS minutes, 
                       expected_goals AS xg, 
                       expected_assists AS xa, 
                       goals, 
                       key_passes, 
                       progressive_dribbles AS dribbles_prog, 
                       defensive_pressures AS pressions_def 
                FROM player_match_stats 
                WHERE match_id LIKE ? AND competition = 'Champions League'
                ORDER BY (goals + key_passes) DESC 
                LIMIT 15
            """, (season_prefix,))
        else:
            cursor.execute("""
                SELECT player_name, 
                       MAX(team_name) AS team_name,
                       SUM(minutes_played) AS minutes, 
                       ROUND(SUM(expected_goals), 1) AS xg, 
                       ROUND(SUM(expected_assists), 1) AS xa, 
                       SUM(goals) AS goals, 
                       SUM(key_passes) AS key_passes, 
                       SUM(progressive_dribbles) AS dribbles_prog, 
                       SUM(defensive_pressures) AS pressions_def 
                FROM player_match_stats 
                WHERE match_id LIKE ?
                GROUP BY player_name
                ORDER BY (SUM(goals) + SUM(key_passes)) DESC 
                LIMIT 15
            """, (season_prefix,))
            
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as db_err:
        print(f"⚠️ SQLITE FALLBACK WARNING: {str(db_err)}")
        return []

@app.post("/api/analyze")
async def analyze_tactical_trends(request: AnalysisRequest):
    if settings.APP_ENV == "production" and not settings.ENABLE_LEGACY_SQL_API:
        raise HTTPException(
            status_code=403,
            detail="Legacy natural-language SQL analysis endpoint is disabled in production.",
        )
    try:
        # Détection du mode Recherche de Similarité (Algorithme ADN)
        prompt_lower = request.prompt.lower()
        sim_keywords = ["clone", "similaire", "ressemble", "profil identique", "sosie", "copie", "semblable"]
        is_similarity_search = any(k in prompt_lower for k in sim_keywords)

        if is_similarity_search:
            print(f"🧬 Similarity search mode activated for query: '{request.prompt}'")
            # Extraction déterministe du nom du joueur cible depuis le prompt
            words = request.prompt.replace("?", "").replace(".", "").replace(",", "").replace("!", "").split()
            stop_words = {"qui", "est", "le", "la", "les", "des", "pour", "dans", "avec", "mais", "plus", "moins", "comme", "sont", "quel", "quelle", "quelles", "quels", "trouve", "trouve-moi", "un", "joueur", "similaire", "clone", "ressemble", "profil", "identique", "sosie", "copie", "semblable", "de", "à", "se", "sa", "ses", "son"}
            candidate_words = [w for w in words if w.lower() not in stop_words and len(w) >= 3]
            
            canonical_target_name = None
            if candidate_words:
                conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
                cursor = conn.cursor()
                
                # Étape 1 : Essayer de trouver un joueur qui correspond à TOUS les mots candidats
                query_parts = []
                params = []
                for w in candidate_words:
                    query_parts.append("player_name LIKE ?")
                    params.append(f"%{w}%")
                
                cursor.execute(
                    f"SELECT DISTINCT player_name FROM player_match_stats WHERE {' AND '.join(query_parts)} LIMIT 1",  # nosec B608
                    params
                )
                row = cursor.fetchone()
                if row:
                    canonical_target_name = row[0]
                else:
                    # Étape 2 : Sinon, essayer les mots un par un par ordre de longueur décroissante
                    for word in sorted(candidate_words, key=len, reverse=True):
                        cursor.execute(
                            "SELECT DISTINCT player_name FROM player_match_stats WHERE player_name LIKE ? LIMIT 1",
                            (f"%{word}%",)
                        )
                        row = cursor.fetchone()
                        if row:
                            canonical_target_name = row[0]
                            break
                conn.close()
            print(f"🧬 Extracted canonical target player name: '{canonical_target_name}'")
            target_profile = None
            top_clones = []

            if canonical_target_name:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                # Récupérer les stats cumulées de TOUS les joueurs pour la saison choisie
                season_pattern = f"{request.season}%"
                cursor.execute("""
                    SELECT 
                        pms.player_name,
                        pms.team_name,
                        pp.position,
                        pp.market_value,
                        pp.rating,
                        SUM(pms.minutes_played) AS total_minutes,
                        SUM(pms.goals) AS total_goals,
                        SUM(pms.expected_goals) AS total_xg,
                        SUM(pms.expected_assists) AS total_xa,
                        SUM(pms.key_passes) AS total_kp,
                        SUM(pms.progressive_dribbles) AS total_dribbles,
                        SUM(pms.defensive_pressures) AS total_pressures
                    FROM player_match_stats pms
                    LEFT JOIN player_profiles pp ON pms.player_name = pp.player_name
                    WHERE pms.match_id LIKE ?
                    GROUP BY pms.player_name, pms.team_name, pp.position, pp.market_value, pp.rating
                """, (season_pattern,))
                
                columns = [d[0] for d in cursor.description]
                all_players = [dict(zip(columns, r)) for r in cursor.fetchall()]
                conn.close()
                
                # Trouver le profil de la cible
                target_profile = next((p for p in all_players if p['player_name'] == canonical_target_name), None)
                if not target_profile:
                    # Recherche globale si absent de la saison courante
                    conn = sqlite3.connect(DB_PATH)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT 
                            pms.player_name,
                            pms.team_name,
                            pp.position,
                            pp.market_value,
                            pp.rating,
                            SUM(pms.minutes_played) AS total_minutes,
                            SUM(pms.goals) AS total_goals,
                            SUM(pms.expected_goals) AS total_xg,
                            SUM(pms.expected_assists) AS total_xa,
                            SUM(pms.key_passes) AS total_kp,
                            SUM(pms.progressive_dribbles) AS total_dribbles,
                            SUM(pms.defensive_pressures) AS total_pressures
                        FROM player_match_stats pms
                        LEFT JOIN player_profiles pp ON pms.player_name = pp.player_name
                        WHERE pms.player_name = ?
                        GROUP BY pms.player_name, pms.team_name, pp.position, pp.market_value, pp.rating
                    """, (canonical_target_name,))
                    row = cursor.fetchone()
                    conn.close()
                    if row:
                        target_profile = dict(row)
                
                if target_profile and target_profile.get('total_minutes', 0) > 0:
                    t_min = target_profile['total_minutes']
                    target_vec = [
                        (target_profile['total_goals'] or 0) / t_min * 90.0,
                        (target_profile['total_xg'] or 0.0) / t_min * 90.0,
                        (target_profile['total_xa'] or 0.0) / t_min * 90.0,
                        (target_profile['total_kp'] or 0) / t_min * 90.0,
                        (target_profile['total_dribbles'] or 0) / t_min * 90.0,
                        (target_profile['total_pressures'] or 0) / t_min * 90.0
                    ]
                    
                    import math
                    clones = []
                    for p in all_players:
                        if p['player_name'] == canonical_target_name:
                            continue
                        if (p['total_minutes'] or 0) < 400:
                            continue
                        
                        p_min = p['total_minutes']
                        p_vec = [
                            (p['total_goals'] or 0) / p_min * 90.0,
                            (p['total_xg'] or 0.0) / p_min * 90.0,
                            (p['total_xa'] or 0.0) / p_min * 90.0,
                            (p['total_kp'] or 0) / p_min * 90.0,
                            (p['total_dribbles'] or 0) / p_min * 90.0,
                            (p['total_pressures'] or 0) / p_min * 90.0
                        ]
                        
                        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(target_vec, p_vec)))
                        similarity = 1.0 / (1.0 + dist) * 100.0
                        
                        clones.append({
                            'player_name': p['player_name'],
                            'team_name': p['team_name'],
                            'position': p['position'],
                            'market_value': p['market_value'],
                            'rating': p['rating'],
                            'minutes': p['total_minutes'],
                            'goals': p['total_goals'],
                            'xg': p['total_xg'],
                            'xa': p['total_xa'],
                            'key_passes': p['total_kp'],
                            'dribbles_prog': p['total_dribbles'],
                            'pressions_def': p['total_pressures'],
                            'vec_90': p_vec,
                            'similarity': similarity
                        })
                    
                    clones.sort(key=lambda x: x['similarity'], reverse=True)
                    top_clones = clones[:5]

            # Construction des prompts pour Qwen (Similarité)
            if canonical_target_name and target_profile and top_clones:
                system_instruction = (
                    "Tu es l'ingénieur tactique en chef et recruteur principal d'un club de football d'élite.\n"
                    "Tu es expert dans l'analyse de l'ADN tactique et la recherche de profils similaires (clones).\n"
                    "Rédige un rapport de scouting prédictif expliquant POURQUOI les clones trouvés partagent le même ADN tactique que le joueur cible.\n"
                    "Base ton analyse exclusivement sur les statistiques réelles fournies.\n"
                    "Formatte tes réponses en Markdown clair, avec un tableau comparatif mettant en valeur le joueur cible, son clone n°1 et les autres clones (incluant le pourcentage de similarité, le club, le poste et la valeur marchande).\n\n"
                    "À la toute fin de ta réponse, après ton rapport textuel, tu dois TOUJOURS ajouter un bloc de données JSON "
                    "structuré sous cette forme exacte, entouré de balises de code markdown (```json ... ```) :\n"
                    "```json\n"
                    "{\n"
                    "  \"chart_type\": \"radar\",\n"
                    "  \"metrics\": [\"goals\", \"xg\", \"xa\", \"key_passes\", \"dribbles_prog\", \"pressions_def\"],\n"
                    "  \"players\": [\n"
                    "    {\"name\": \"" + canonical_target_name + " (Cible)\", \"data\": [" + str(target_profile['total_goals'] or 0) + ", " + str(target_profile['total_xg'] or 0.0) + ", " + str(target_profile['total_xa'] or 0.0) + ", " + str(target_profile['total_kp'] or 0) + ", " + str(target_profile['total_dribbles'] or 0) + ", " + str(target_profile['total_pressures'] or 0) + "]},\n"
                    "    {\"name\": \"" + top_clones[0]['player_name'] + " (Match: " + f"{top_clones[0]['similarity']:.1f}" + "%)\", \"data\": [" + str(top_clones[0]['goals'] or 0) + ", " + str(top_clones[0]['xg'] or 0.0) + ", " + str(top_clones[0]['xa'] or 0.0) + ", " + str(top_clones[0]['key_passes'] or 0) + ", " + str(top_clones[0]['dribbles_prog'] or 0) + ", " + str(top_clones[0]['pressions_def'] or 0) + "]}\n"
                    "  ]\n"
                    "}\n"
                    "```\n"
                    "Utilise les vraies valeurs extraites pour chaque joueur (pas de placeholders, pas de valeurs fictives). "
                    "Les valeurs du JSON doivent être les totaux cumulés absolus (pas par 90 min) pour correspondre au format d'affichage du radar.\n"
                    "Ne mets aucun texte après ce bloc JSON."
                )

                target_val = target_profile.get('market_value')
                target_val_str = f"{target_val/1000000:.1f} M€" if target_val else "N/A"
                
                user_message = (
                    f"🔬 ANALYSE D'ADN TACTIQUE (RECHERCHE DE SIMILARITÉ)\n\n"
                    f"Joueur cible recherché : {canonical_target_name}\n"
                    f"Saison d'analyse : {request.season}\n\n"
                    f"Profil de la cible :\n"
                    f"- Club : {target_profile.get('team_name')}\n"
                    f"- Poste : {target_profile.get('position')}\n"
                    f"- Valeur marchande : {target_val_str}\n"
                    f"- Note moyenne : {target_profile.get('rating') or 'N/A'}/10\n"
                    f"- Minutes jouées : {target_profile['total_minutes']} min\n"
                    f"- Stats absolues : {target_profile['total_goals']} buts, {target_profile['total_xg']} xG, {target_profile['total_xa']} xA, {target_profile['total_kp']} passes clés, {target_profile['total_dribbles']} dribbles, {target_profile['total_pressures']} pressions.\n\n"
                    f"Top 5 des profils similaires (clones tactiques) identifiés :\n"
                )

                for idx, c in enumerate(top_clones):
                    val_str = f"{c['market_value']/1000000:.1f} M€" if c['market_value'] else "N/A"
                    user_message += (
                        f"{idx+1}. {c['player_name']} (Similarité: {c['similarity']:.1f}%)\n"
                        f"   - Club: {c['team_name']} | Poste: {c['position']} | Valeur: {val_str} | Note: {c['rating'] or 'N/A'}/10\n"
                        f"   - Minutes: {c['minutes']} min | Stats: {c['goals']} buts, {c['xg']} xG, {c['xa']} xA, {c['key_passes']} passes clés, {c['dribbles_prog']} dribbles, {c['pressions_def']} pressions.\n"
                    )
            else:
                system_instruction = "Tu es un assistant de football d'élite."
                user_message = f"Le joueur '{candidate_words[0] if candidate_words else 'demandé'}' ou ses statistiques n'ont pas été trouvés dans la base de données pour la saison {request.season}. Explique à l'utilisateur qu'il est impossible de réaliser la recherche de similarité sans ces données."

            response = ai_client.chat.completions.create(
                model="qwen/qwen-2.5-72b-instruct:free",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,
                stream=True
            )
            
            def generate_chunks():
                try:
                    for chunk in response:
                        if chunk.choices and chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content
                except Exception as e:
                    print(f"💥 ERREUR DE STREAMING : {str(e)}")

            return StreamingResponse(generate_chunks(), media_type="text/plain")

        # Code original (Recherche SQL Standard)
        sql_query = None
        sql_rows = []
        use_fallback = False
        fallback_reason = ""

        sql_generation_prompt = (
            "Tu es un traducteur de requêtes tactiques de football en requêtes SQL SQLite très précis.\n"
            "Voici le schéma exact des tables disponibles dans SQLite :\n\n"
            "1. Table 'player_match_stats' (statistiques détaillées de match) :\n"
            "- player_name (VARCHAR) : Nom du joueur\n"
            "- team_name (TEXT) : Nom du club/équipe du joueur (ex: 'Paris S-G', 'PSG', 'Marseille', 'Real Madrid', 'Barcelona', etc. Utilise LIKE '%Paris%' ou LIKE '%PSG%' pour le PSG)\n"
            "- match_id (VARCHAR) : Identifiant de la saison ou du match (ex: 'season_2024_2025_summary', 'season_2024_2025_cl')\n"
            "- minutes_played (INTEGER) : Temps de jeu en minutes\n"
            "- goals (INTEGER) : Buts marqués\n"
            "- expected_goals (FLOAT) : Expected goals (xG)\n"
            "- expected_assists (FLOAT) : Expected assists (xA)\n"
            "- key_passes (INTEGER) : Passes clés\n"
            "- progressive_dribbles (INTEGER) : Dribbles progressifs\n"
            "- defensive_pressures (INTEGER) : Pressions défensives\n"
            "- competition (TEXT) : 'Domestic League' ou 'Champions League'\n\n"
            "2. Table 'player_profiles' (profils et valeurs marchandes) :\n"
            "- player_id (INTEGER) : Identifiant unique du joueur\n"
            "- player_name (TEXT) : Nom du joueur (pour faire la jointure JOIN player_profiles ON player_match_stats.player_name = player_profiles.player_name)\n"
            "- position (TEXT) : Poste principal du joueur : 'F' (Forward/Attaquant), 'M' (Midfielder/Milieu), 'D' (Defender/Défenseur), 'G' (Goalkeeper/Gardien)\n"
            "- market_value (REAL) : Valeur marchande en Euros (ex: 68000000.0 pour 68M€)\n"
            "- rating (REAL) : Note moyenne du joueur sur 10 (ex: 7.21)\n"
            "- league (TEXT) : Championnat domestique du joueur (ex: 'Ligue 1', 'Premier League', 'LaLiga', 'Serie A', 'Bundesliga', 'Eredivisie', 'Liga Portugal', 'Super Lig')\n\n"
            "Consignes de traduction :\n"
            "1. Renvoie UNIQUEMENT la requête SQL correspondante sous forme de bloc de code markdown : ```sql\n[REQUÊTE]\n```\n"
            "2. Ne mets aucun autre texte, explication ou blabla.\n"
            "3. Pour obtenir les statistiques cumulées d'un joueur, utilise des fonctions d'agrégation comme SUM(goals), SUM(minutes_played), SUM(expected_goals), etc., et regroupe par player_name avec GROUP BY player_name.\n"
            "4. Si la question mentionne 'LDC' ou 'Ligue des Champions', ajoute la condition `competition = 'Champions League'`. Si elle mentionne le championnat, ajoute `competition = 'Domestic League'`.\n"
            "5. Assure-sol de filtrer sur match_id en fonction de la saison sélectionnée si mentionné (par exemple match_id LIKE 'season_2024_2025_%' ou match_id LIKE 'season_2025_2026_%').\n"
            "6. Utilise LIKE pour les recherches de noms de joueurs pour être tolérant aux fautes d'orthographe (ex: player_match_stats.player_name LIKE '%Kane%').\n"
            "7. Si la question mentionne un club/équipe (par exemple le PSG), filtre également sur le nom du club avec team_name (ex: team_name LIKE '%Paris%' ou team_name LIKE '%PSG%').\n"
            "8. Fais un JOIN avec player_profiles si la requête mentionne la valeur marchande, la note moyenne du joueur, son poste (F/M/D/G), ou si le filtrage par poste/valeur/championnat est requis.\n\n"
            "Exemples de requêtes générées :\n"
            "- Question: 'Quelle est la valeur marchande de Bradley Barcola ?'\n"
            "  SQL: ```sql\nSELECT player_profiles.player_name, player_profiles.market_value, player_profiles.rating, player_profiles.position FROM player_profiles WHERE player_profiles.player_name LIKE '%Barcola%'\n```\n"
            "- Question: 'Qui est le joueur le plus cher du PSG et quelles sont ses statistiques ?'\n"
            "  SQL: ```sql\nSELECT pms.player_name, pms.team_name, pp.market_value, pp.rating, pp.position, SUM(pms.minutes_played) AS minutes_played, SUM(pms.goals) AS goals, SUM(pms.expected_goals) AS expected_goals, SUM(pms.expected_assists) AS expected_assists, SUM(pms.key_passes) AS key_passes, SUM(pms.progressive_dribbles) AS progressive_dribbles, SUM(pms.defensive_pressures) AS defensive_pressures FROM player_match_stats pms JOIN player_profiles pp ON pms.player_name = pp.player_name WHERE (pms.team_name LIKE '%PSG%' OR pms.team_name LIKE '%Paris%') AND pms.match_id LIKE 'season_2024_2025_%' GROUP BY pms.player_name, pms.team_name, pp.market_value, pp.rating, pp.position ORDER BY pp.market_value DESC LIMIT 1\n```\n"
            "- Question: 'Donne-moi les milieux de terrain de Ligue 1 avec une note supérieure à 7.0 par ordre de valeur marchande décroissante.'\n"
            "  SQL: ```sql\nSELECT player_name, league, position, market_value, rating FROM player_profiles WHERE league = 'Ligue 1' AND position = 'M' AND rating > 7.0 ORDER BY market_value DESC\n```\n"
        )

        user_msg_stage1 = (
            f"Requête tactique de l'utilisateur : {request.prompt}\n"
            f"Saison sélectionnée dans l'UI : {request.season}\n"
        )

        try:
            sql_response = ai_client.chat.completions.create(
                model="qwen/qwen-2.5-72b-instruct:free",
                messages=[
                    {"role": "system", "content": sql_generation_prompt},
                    {"role": "user", "content": user_msg_stage1}
                ],
                temperature=0.0,
                stream=False
            )
            sql_text = sql_response.choices[0].message.content
        except Exception as api_err:
            print(f"⚠️ SQL generation API error: {str(api_err)}")
            sql_text = ""
            use_fallback = True
            fallback_reason = f"LLM API Error: {str(api_err)}"

        # Étape 2 : Extraction et exécution de la requête SQL
        if not use_fallback and sql_text:
            import re
            sql_match = re.search(r'```sql\s*(.*?)\s*```', sql_text, re.DOTALL | re.IGNORECASE)
            if sql_match:
                sql_query = sql_match.group(1).strip()
            else:
                sql_query = sql_text.strip()

            if sql_query:
                clean_query = sql_query.rstrip(";").strip()
                if not re.match(r"^SELECT\s", clean_query, re.IGNORECASE):
                    raise HTTPException(
                        status_code=400,
                        detail="Forbidden query: only SELECT queries are permitted.",
                    )
                dangerous_patterns = [
                    r"\bDROP\b", r"\bDELETE\b", r"\bUPDATE\b", r"\bINSERT\b",
                    r"\bALTER\b", r"\bCREATE\b", r"\bATTACH\b", r"\bDETACH\b",
                    r"\bPRAGMA\b", r"\bVACUUM\b", r"\bTRUNCATE\b", r"--", r"/\*", r";"
                ]
                upper_query = clean_query.upper()
                for pat in dangerous_patterns:
                    if re.search(pat, upper_query):
                        raise HTTPException(
                            status_code=400,
                            detail="Forbidden SQL syntax or keyword detected.",
                        )

                print(f"🔍 Executing validated SQL: {clean_query}")
                try:
                    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute(clean_query)
                    rows = cursor.fetchall()
                    conn.close()

                    # Normalisation des colonnes SQL vers des clés standardisées
                    for row in rows:
                        row_dict = dict(row)
                        mapped_row = {}
                        for k, v in row_dict.items():
                            k_lower = k.lower()
                            if 'player_name' in k_lower or k_lower == 'player' or k_lower == 'nom' or k_lower == 'joueur':
                                mapped_row['player_name'] = v
                            elif 'min' in k_lower:
                                mapped_row['minutes'] = v
                            elif 'xg' in k_lower or 'expected_goals' in k_lower:
                                mapped_row['xg'] = v
                            elif 'xa' in k_lower or 'expected_assists' in k_lower:
                                mapped_row['xa'] = v
                            elif 'dribble' in k_lower or 'carry' in k_lower or 'dribb' in k_lower:
                                mapped_row['dribbles_prog'] = v
                            elif 'press' in k_lower:
                                mapped_row['pressions_def'] = v
                            elif 'goal' in k_lower or k_lower == 'gls' or k_lower == 'but' or k_lower == 'buts':
                                mapped_row['goals'] = v
                            elif 'key' in k_lower or 'kp' in k_lower or 'pass' in k_lower:
                                mapped_row['key_passes'] = v
                            elif 'competition' in k_lower:
                                mapped_row['competition'] = v
                            elif 'team_name' in k_lower or k_lower == 'team' or k_lower == 'squad' or k_lower == 'club' or 'equipe' in k_lower:
                                mapped_row['team_name'] = v
                            elif 'value' in k_lower or 'valeur' in k_lower or 'price' in k_lower or 'tarif' in k_lower:
                                mapped_row['market_value'] = v
                            elif 'rating' in k_lower or 'note' in k_lower:
                                mapped_row['rating'] = v
                            elif 'position' in k_lower or 'poste' in k_lower or k_lower == 'pos':
                                mapped_row['position'] = v
                            else:
                                mapped_row[k] = v

                        # Remplissage par défaut des métriques pour le radar final
                        for req_key in ['player_name', 'minutes', 'goals', 'xg', 'xa', 'key_passes', 'dribbles_prog', 'pressions_def']:
                            if req_key not in mapped_row:
                                if req_key == 'player_name':
                                    mapped_row[req_key] = 'Unknown'
                                elif req_key in ['xg', 'xa']:
                                    mapped_row[req_key] = 0.0
                                else:
                                    mapped_row[req_key] = 0
                        sql_rows.append(mapped_row)

                    if not sql_rows:
                        use_fallback = True
                        fallback_reason = "SQL query returned 0 rows"

                except Exception as db_err:
                    print(f"⚠️ SQLite Execution Error: {str(db_err)}")
                    use_fallback = True
                    fallback_reason = f"SQLite Error: {str(db_err)}"
            else:
                use_fallback = True
                fallback_reason = "SQL query parsing failed"
        else:
            use_fallback = True

        # Fallback de secours si la génération SQL a échoué ou n'a renvoyé aucun résultat
        if use_fallback:
            print(f"🔄 Fallback activé : {fallback_reason}")
            sql_rows = []
            words = request.prompt.replace("?", "").replace(".", "").replace(",", "").replace("!", "").split()
            stop_words = {"qui", "est", "le", "la", "les", "des", "pour", "dans", "avec", "mais", "plus", "moins", "comme", "sont", "quel", "quelle", "quelles", "quels"}
            potential_players = [
                w for w in words 
                if len(w) >= 3 and (w[0].isupper() or (w.lower() not in stop_words and len(w) > 3))
            ]
            
            prompt_lower = request.prompt.lower()
            use_ldc = 'ldc' in prompt_lower or 'ligue des champions' in prompt_lower
            
            for word in potential_players:
                stats = fetch_player_stats_from_db(word, request.season, use_ldc)
                if stats:
                    sql_rows.extend(stats)
            
            if sql_rows:
                sql_rows = list({v['player_name']: v for v in sql_rows}.values())
            
            global_keywords = {'mvp', 'meilleur', 'top', 'classement', 'buteur'}
            has_global_keyword = any(keyword in prompt_lower for keyword in global_keywords)
            
            if not sql_rows or has_global_keyword:
                fallback_stats = fetch_top_players_from_db(request.season, use_ldc)
                if fallback_stats:
                    sql_rows = fallback_stats

        # Étape 3 : Streaming de l'analyse finale avec Qwen
        system_instruction = (
            "Tu es l'ingénieur tactique en chef d'un club de football d'élite mondiale.\n"
            "Tu dois baser tes rapports exclusivement sur les statistiques réelles fournies.\n"
            "Si le jeu de données renvoyé par SQLite est vide ou ne correspond pas au club demandé, tu dois explicitement dire que le joueur ne joue pas ou plus dans ce club pour la saison sélectionnée, sans inventer de fausses statistiques.\n"
            "Formatte tes réponses en Markdown clair, avec des tableaux comparatifs, "
            "des puces lisibles et des directives de coaching exploitables.\n\n"
            "À la toute fin de ta réponse, après l'analyse textuelle, tu dois TOUJOURS ajouter un bloc de données JSON "
            "structuré sous cette forme exacte, entouré de balises de code markdown (```json ... ```) :\n"
            "```json\n"
            "{\n"
            "  \"chart_type\": \"radar\",\n"
            "  \"metrics\": [\"goals\", \"xg\", \"xa\", \"key_passes\", \"dribbles_prog\", \"pressions_def\"],\n"
            "  \"players\": [\n"
            "    {\"name\": \"NomJoueur1\", \"data\": [goals_val, xg_val, xa_val, key_passes_val, dribbles_prog_val, pressions_def_val]},\n"
            "    {\"name\": \"NomJoueur2\", \"data\": [...]}\n"
            "  ]\n"
            "}\n"
            "```\n"
            "Utilise les vraies valeurs extraites du contexte SQL pour chaque joueur (pas de placeholders, pas de valeurs fictives). "
            "Ne mets aucun texte après ce bloc JSON."
        )

        user_message = f"Requête tactique de l'utilisateur : {request.prompt}\n\n"
        if sql_query:
            user_message += f"🤖 Requête SQL générée automatiquement : `{sql_query}`\n\n"

        if sql_rows:
            user_message += "📈 DONNÉES RÉELLES EXTRAITES DE LA BASE SQL :\n"
            for p in sql_rows:
                team_info = f" (Club: {p['team_name']})" if p.get('team_name') else ""
                profile_info = ""
                if p.get('market_value'):
                    profile_info += f", Valeur: {p['market_value']/1000000:.1f} M€"
                if p.get('rating'):
                    profile_info += f", Note: {p['rating']:.2f}/10"
                if p.get('position'):
                    pos_map = {'F': 'Attaquant', 'M': 'Milieu', 'D': 'Défenseur', 'G': 'Gardien'}
                    profile_info += f", Poste: {pos_map.get(p['position'], p['position'])}"
                
                user_message += (
                    f"- {p['player_name']}{team_info}{profile_info} : {p['minutes']} min, {p['goals']} buts, "
                    f"{p['xg']} xG, {p['xa']} xA, {p['key_passes']} passes clés, "
                    f"{p['dribbles_prog']} dribbles progressifs, {p['pressions_def']} pressions.\n"
                )
        else:
            user_message += "⚠️ Remarque : Aucune donnée statistique spécifique trouvée en base pour cette sélection.\n"

        response = ai_client.chat.completions.create(
            model="qwen/qwen-2.5-72b-instruct:free",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_message}
            ],
            temperature=0.3,
            stream=True
        )
        
        def generate_chunks():
            try:
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            except Exception as e:
                print(f"💥 ERREUR DE STREAMING : {str(e)}")

        return StreamingResponse(generate_chunks(), media_type="text/plain")

    except Exception as e:
        print(f"💥 ERREUR CRITIQUE BACKEND : {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health", response_model=dict[str, str])
@app.get("/api/health", response_model=dict[str, str])
def health_check():
    """Minimal health check endpoint.

    Returns strictly: {"status": "ok"}.
    In production mode, internally probes database readiness and returns 503 if unreachable.
    Does not expose filesystem, GPU, dependencies, secrets, or model paths.
    """
    if settings.APP_ENV == "production":
        try:
            from sqlalchemy import text
            from app.services.beta_service import get_beta_service

            svc = get_beta_service()
            with svc.engine.connect() as conn:
                conn.execute(text("SELECT 1;"))
        except Exception as exc:
            logging.getLogger("uvicorn.error").error("Database healthcheck probe failed: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="Service Unavailable: database probe failed",
            ) from exc

    return {"status": "ok"}
