import os
import json
import logging
import time
import requests
from tools.promiedos import fetch_mundial_complete_data
from tools.editor_jefe import EditorJefe
from tools.wordpress import WordPressPublisher
from tools.images import generate_ai_image
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CACHE_FILE = ".cache/stats_history.json"

AGENTE_ESTADISTICO_PROMPT = """
Eres el 'Periodista Analista de Datos' de Pasión y Pelota. 
Has detectado un cambio radical en las estadísticas del Mundial 2026.
Tu tarea es redactar un artículo breve, impactante y muy analítico sobre este cambio estadístico.

REGLAS:
1. El artículo debe centrarse exclusivamente en la estadística que ha cambiado (goles, recuperaciones, posiciones).
2. Usa un tono periodístico, analítico y serio.
3. El título debe ser atractivo pero directo.
4. Incluye la estadística numérica dura. No inventes números que no te hayan proporcionado.
5. Usa formato HTML para el contenido (párrafos <p>, negritas <strong>).

Devuelve EXACTAMENTE un JSON con este formato:
{
    "title": "Título del artículo",
    "content_html": "Contenido HTML del artículo"
}
No agregues preámbulos ni código markdown, solo el JSON puro.
"""

def call_gemini_writer(prompt: str) -> dict:
    models = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-1.5-flash-latest"]
    for model in models:
        for _ in range(len(config.GEMINI_API_KEYS)):
            api_key = config.get_active_key()
            if not api_key:
                config.rotate_key()
                continue
                
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            payload = {
                "system_instruction": {"parts": [{"text": AGENTE_ESTADISTICO_PROMPT}]},
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.5
                }
            }
            try:
                resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
                if resp.status_code == 200:
                    data = resp.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return json.loads(text)
                elif resp.status_code == 429:
                    config.rotate_key()
            except Exception as e:
                logger.error(f"Error LLM: {e}")
                
    return {}

def load_previous_state():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            try:
                return json.load(f)
            except:
                pass
    return {"scorers": {}, "assists": {}, "passing": {}}

def save_current_state(state):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def dictify_stats(stats_list):
    res = {}
    for s in stats_list:
        try:
            val = s.get("goals") or s.get("assists") or s.get("passes") or "0"
            res[s["name"]] = int(val)
        except:
            pass
    return res

def analyze_changes(current_stats, previous_state, player_to_team, covered_teams_today_lower):
    radical_changes = []
    
    current_scorers = dictify_stats(current_stats.get("scorers", []))
    prev_scorers = previous_state.get("scorers", {})
    
    for player, goals in current_scorers.items():
        prev_goals = prev_scorers.get(player, 0)
        diff = goals - prev_goals
        if diff >= 2:
            team = player_to_team.get(player, "")
            if team and team.lower() in covered_teams_today_lower:
                logger.info(f"Omitiendo cambio radical de goleador {player} ({team}) porque ya fue cubierto hoy.")
                continue
            radical_changes.append(f"El jugador {player} ({team}) ha tenido una actuación consagratoria anotando {diff} goles recientes, sumando un total de {goals} goles en el torneo y escalando bruscamente en la tabla de goleadores.")
            
    current_assists = dictify_stats(current_stats.get("assists", []))
    prev_assists = previous_state.get("assists", {})
    
    for player, assists in current_assists.items():
        prev_assists_val = prev_assists.get(player, 0)
        diff = assists - prev_assists_val
        if diff >= 2:
            team = player_to_team.get(player, "")
            if team and team.lower() in covered_teams_today_lower:
                logger.info(f"Omitiendo cambio radical de asistidor {player} ({team}) porque ya fue cubierto hoy.")
                continue
            radical_changes.append(f"El jugador {player} ({team}) demostró una visión de juego letal sumando {diff} asistencias nuevas, acumulando {assists} asistencias totales y posicionándose como el máximo asistidor sorpresivo.")
            
    return radical_changes

def load_database():
    import pytz
    from datetime import datetime
    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    today_str = datetime.now(tz).strftime('%Y-%m-%d')
    default_db = {
        "published_urls": [],
        "published_titles": [],
        "covered_teams_today": {"date": today_str, "teams": []}
    }
    if not os.path.exists(config.DATABASE_FILE):
        return default_db
    try:
        with open(config.DATABASE_FILE, 'r', encoding='utf-8') as f:
            db = json.load(f)
            for k, v in default_db.items():
                if k not in db:
                    db[k] = v
            if not isinstance(db.get("covered_teams_today"), dict):
                db["covered_teams_today"] = default_db["covered_teams_today"]
            else:
                if "date" not in db["covered_teams_today"]:
                    db["covered_teams_today"]["date"] = ""
                if "teams" not in db["covered_teams_today"]:
                    db["covered_teams_today"]["teams"] = []
            
            # Resetear si es un día nuevo en America/Argentina/Buenos_Aires
            if db["covered_teams_today"].get("date") != today_str:
                db["covered_teams_today"] = {"date": today_str, "teams": []}
                
            return db
    except Exception as e:
        logger.error(f"Error al cargar base de datos: {e}")
        return default_db

def save_database(db):
    try:
        with open(config.DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error al guardar base de datos: {e}")

def main():
    logger.info("Despertando al Agente Estadístico...")
    
    mundial_data = fetch_mundial_complete_data()
    if not mundial_data:
        logger.error("No se pudieron descargar los datos del mundial.")
        return
        
    editor = EditorJefe()
    current_stats = editor.calculate_player_stats(mundial_data)
    
    # Cargar base de datos de control de duplicados
    db = load_database()
    covered_teams_today_list = db.get("covered_teams_today", {}).get("teams", [])
    covered_teams_today_lower = [t.lower() for t in covered_teams_today_list]
    
    # Mapear jugadores a sus equipos/selecciones
    player_to_team = {}
    for item in current_stats.get("scorers", []) + current_stats.get("assists", []) + current_stats.get("passing", []):
        name = item.get("name")
        team = item.get("team")
        if name and team:
            player_to_team[name] = team
            
    previous_state = load_previous_state()
    radical_changes = analyze_changes(current_stats, previous_state, player_to_team, covered_teams_today_lower)
    
    # Preparamos el nuevo estado a guardar
    new_state = {
        "scorers": dictify_stats(current_stats.get("scorers", [])),
        "assists": dictify_stats(current_stats.get("assists", [])),
        "passing": dictify_stats(current_stats.get("passing", []))
    }
    
    if radical_changes:
        logger.info(f"Se detectaron {len(radical_changes)} cambios radicales. Generando artículo...")
        prompt = "Redacta el artículo analítico basado estrictamente en estos cambios radicales confirmados por Promiedos:\n" + "\n".join(radical_changes)
        
        article = call_gemini_writer(prompt)
        if article and "title" in article and "content_html" in article:
            logger.info("Generando imagen para la nota...")
            image_prompt = "Dramatic sports data visualization, neon data streams ascending in a graph, modern soccer analytics, ultra realistic, epic lighting, unbranded"
            new_img = generate_ai_image(image_prompt)
            image_id = None
            if new_img and "url" in new_img:
                wp = WordPressPublisher()
                image_id = wp.upload_featured_image(image_url=new_img["url"], filename="stats_update.jpg")
                
            if "wp" not in locals():
                wp = WordPressPublisher()
            logger.info("Publicando en WordPress...")
            wp_post = wp.publish_post(
                title=article["title"],
                content=article["content_html"],
                league_category="Estadístico",
                featured_image_id=image_id,
                seo_desc="Análisis estadístico de impacto en el Mundial 2026."
            )
            if wp_post:
                # Registrar los equipos involucrados en covered_teams_today
                import pytz
                from datetime import datetime
                tz_arg = pytz.timezone('America/Argentina/Buenos_Aires')
                today_arg = datetime.now(tz_arg).strftime("%Y-%m-%d")
                
                teams_to_register = []
                for change in radical_changes:
                    for player, team in player_to_team.items():
                        if player in change and team not in teams_to_register:
                            teams_to_register.append(team)
                            
                for t in teams_to_register:
                    if t not in db["covered_teams_today"]["teams"]:
                        db["covered_teams_today"]["teams"].append(t)
                        
                save_database(db)
                logger.info("Base de datos de duplicados de equipos actualizada por el agente estadístico.")
        else:
            logger.error("Error al generar el artículo con Gemini.")
    else:
        logger.info("No se detectaron cambios radicales estadísticos o todos involucran equipos ya cubiertos hoy. Volviendo a dormir silenciosamente.")
        
    save_current_state(new_state)
    logger.info("Estado estadístico actualizado y guardado.")

if __name__ == "__main__":
    main()
