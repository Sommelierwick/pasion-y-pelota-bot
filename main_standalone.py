"""
main_standalone.py — Pipeline completo de Pasión y Pelota
Usa la API de Groq (Llama-3.3-70b) como motor de IA.
No requiere google-antigravity instalado.
"""

import asyncio
import json
import os
import sys
import logging
import argparse
import pydantic
import requests
from typing import List, Optional

# Importaciones de nuestras herramientas locales
import config
from tools.scraper import monitor_all_sources
from tools.promiedos import fetch_promiedos_page, search_backup_stats, search_web_for_verification, fetch_mundial_complete_data_with_today
from tools.wordpress import WordPressPublisher
from tools.cleanup import cleanup_old_posts
from tools.images import get_football_image
from tools.statsbomb_api import get_player_historical_stats
from tools.tactical_stats import fetch_player_tactical_stats

# Configuración de logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline.log", encoding="utf-8")
    ]
)

# =============================================================================
# FUNCIONES AUXILIARES PARA EL CÁLCULO DE TABLAS DE POSICIONES
# =============================================================================
def calculate_updated_group_standings(group_data, home, away, home_goals, away_goals, status):
    """
    Calcula de forma determinista y matemática la tabla de posiciones del grupo.
    Evita alucinaciones y dobles contabilidades.
    """
    if not group_data or "teams" not in group_data:
        return []
        
    teams = []
    # Clonar los datos para no mutar el original
    for t in group_data["teams"]:
        gf, gc = 0, 0
        goals_str = t.get("goals", "0:0")
        if ":" in goals_str:
            parts = goals_str.split(":")
            gf = int(parts[0]) if parts[0].isdigit() else 0
            gc = int(parts[1]) if parts[1].isdigit() else 0
            
        teams.append({
            "name": t.get("name"),
            "pts": int(t.get("pts", 0)),
            "pj": int(t.get("pj", 0)),
            "pg": int(t.get("pg", 0)),
            "pe": int(t.get("pe", 0)),
            "pp": int(t.get("pp", 0)),
            "gf": gf,
            "gc": gc,
            "colors": t.get("colors", {}),
            "dest_color": t.get("dest_color", "#fff")
        })
        
    match_active = status not in ["Prog.", "Progr."] and home_goals != "-" and away_goals != "-"
    
    if match_active:
        try:
            h_g = int(home_goals)
            a_g = int(away_goals)
        except Exception:
            h_g, a_g = 0, 0
            
        home_team = None
        away_team = None
        for t in teams:
            if t["name"].lower() == home.lower():
                home_team = t
            elif t["name"].lower() == away.lower():
                away_team = t
                
        # Si hoy es la fecha 3 (o cualquier fecha en juego/finalizada), y pj < 3,
        # significa que el partido aún no ha sido sumado a la tabla de Promiedos
        if home_team and away_team and home_team["pj"] < 3 and away_team["pj"] < 3:
            home_team["pj"] += 1
            away_team["pj"] += 1
            home_team["gf"] += h_g
            home_team["gc"] += a_g
            away_team["gf"] += a_g
            away_team["gc"] += h_g
            
            if h_g > a_g:
                home_team["pts"] += 3
                home_team["pg"] += 1
                away_team["pp"] += 1
            elif h_g < a_g:
                away_team["pts"] += 3
                away_team["pg"] += 1
                home_team["pp"] += 1
            else:
                home_team["pts"] += 1
                away_team["pts"] += 1
                home_team["pe"] += 1
                away_team["pe"] += 1
                
    # Calcular diferencia de goles y formatear
    for t in teams:
        t["dg"] = t["gf"] - t["gc"]
        t["goals_str"] = f"{t['gf']}:{t['gc']}"
        t["ratio_str"] = f"+{t['dg']}" if t["dg"] > 0 else str(t["dg"])
        
    # Ordenar por Pts, DG, GF desc
    teams.sort(key=lambda x: (x["pts"], x["dg"], x["gf"]), reverse=True)
    return teams


def render_standings_html_table(teams_list):
    """
    Genera el HTML de la tabla de posiciones del grupo de forma de tabla de posiciones premium.
    """
    html = """
<table style="width:100%; border-collapse:collapse; margin:20px 0; font-family:sans-serif; font-size:14px; text-align:center; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden;">
  <thead>
    <tr style="background-color:#0056b3; color:#ffffff; font-weight:bold;">
      <th style="padding:10px; border:1px solid #ddd; text-align:left;">Selección</th>
      <th style="padding:10px; border:1px solid #ddd;">PJ</th>
      <th style="padding:10px; border:1px solid #ddd;">PG</th>
      <th style="padding:10px; border:1px solid #ddd;">PE</th>
      <th style="padding:10px; border:1px solid #ddd;">PP</th>
      <th style="padding:10px; border:1px solid #ddd;">Goles</th>
      <th style="padding:10px; border:1px solid #ddd;">DG</th>
      <th style="padding:10px; border:1px solid #ddd; font-weight:bold; background-color:#004085;">Pts</th>
    </tr>
  </thead>
  <tbody>
"""
    for i, t in enumerate(teams_list):
        bg_color = "#f8f9fa" if i % 2 == 0 else "#ffffff"
        row_style = f"background-color:{bg_color};"
        if i < 2:
            row_style += " border-left:4px solid #28a745;"
        elif i == 2:
            row_style += " border-left:4px solid #ffc107;"
            
        html += f"""    <tr style="{row_style}">
      <td style="padding:10px; border:1px solid #ddd; text-align:left; font-weight:bold;">{t['name']}</td>
      <td style="padding:10px; border:1px solid #ddd;">{t['pj']}</td>
      <td style="padding:10px; border:1px solid #ddd;">{t['pg']}</td>
      <td style="padding:10px; border:1px solid #ddd;">{t['pe']}</td>
      <td style="padding:10px; border:1px solid #ddd;">{t['pp']}</td>
      <td style="padding:10px; border:1px solid #ddd;">{t['goals_str']}</td>
      <td style="padding:10px; border:1px solid #ddd; font-weight:bold; color:{'#28a745' if t['dg'] > 0 else ('#dc3545' if t['dg'] < 0 else '#6c757d')};">{t['ratio_str']}</td>
      <td style="padding:10px; border:1px solid #ddd; font-weight:bold; background-color:#e2e3e5;">{t['pts']}</td>
    </tr>
"""
    html += """  </tbody>
</table>
"""
    return html

# =============================================================================

# CORRECTOR EDITORIAL SYSTEM PROMPT
# =============================================================================
CORRECTOR_EDITORIAL_SYSTEM = """
Eres el 'Corrector Editorial Experto en Fútbol e Imágenes'. Tu misión es auditar, corregir y pulir el contenido redactado por el periodista antes de que sea publicado. Garantizas el máximo rigor fáctico, conceptual y estructural de Pasión y Pelota.

REGLAS DE AUDITORÍA Y EDICIÓN OBLIGATORIAS:
1. SEDES DEL MUNDIAL 2026: El Mundial de la FIFA 2026 se juega de forma neutral en Estados Unidos, México y Canadá. Ninguna selección (por ejemplo, Uruguay, Brasil, Argentina, Alemania, etc.) juega de local en su propio país. Si el artículo menciona erróneamente estadios locales históricos (como el Estadio Centenario para Uruguay, el Maracaná para Brasil, el Monumental para Argentina) o que jugaron en su país original, corrígelo inmediatamente para situarlo en las sedes oficiales norteamericanas de la FIFA 2026 (por ejemplo: Estadio Miami / Hard Rock Stadium en Florida, MetLife Stadium, Estadio Azteca, etc.).
2. FÚTBOL ASOCIACIÓN (SOCCER) VS FÚTBOL AMERICANO: Asegúrate de que no haya ninguna confusión terminológica con el fútbol americano (como yardas, touchdowns, quarterbacks, cascos de fútbol americano, etc.). Todo debe hacer referencia exclusiva al fútbol asociación (soccer).
3. CO-CITACIONES OCULTAS: La sección final de co-citaciones a medios deportivos panamericanos (Marca, AS, Olé, etc.) DEBE estar obligatoriamente envuelta en un contenedor HTML invisible (<div style="display: none !important;" aria-hidden="true"> ... </div>). Si el redactor omitió la envoltura oculta o dejó los links visibles, reescríbela y enciérrala dentro de este div oculto.
4. COHERENCIA ESTADÍSTICA: Verifica que las tablas de estadísticas estén completas, tengan coherencia numérica y no contengan disculpas ni comentarios sobre la falta de datos de la IA.
5. Devolver el JSON estructurado con el mismo esquema de entrada. No agregues preámbulos, saludos ni explicaciones.
"""

# =============================================================================
# 1. Modelos de Datos Estructurados (Pydantic)
# =============================================================================

class NewsDetails(pydantic.BaseModel):
    has_relevant_news: bool = pydantic.Field(description="Verdadero si hay una noticia relevante.")
    player: str = pydantic.Field(default="", description="Nombre completo del jugador o protagonista principal.")
    teams_involved: List[str] = pydantic.Field(default_factory=list, description="Equipos involucrados. Debe ser una lista de strings, usar [] si no aplica (NUNCA null).")
    monetary_figures: str = pydantic.Field(default="", description="Cifras de dinero. 'No especificado' si no hay.")
    source: str = pydantic.Field(default="", description="Fuente original de la noticia.")
    headline: str = pydantic.Field(default="", description="Titular corto en español.")
    details: List[str] = pydantic.Field(default_factory=list, description="Viñetas con datos clave. Debe ser una lista de strings, usar [] si no aplica (NUNCA null).")
    seo_cluster: str = pydantic.Field(default="", description="Clúster SEO: mundial_2026|mls|brasileirao|lpf_argentina|liga_mx|champions|libertadores|premier|laliga|serie_a")
    priority_score: int = pydantic.Field(default=5, description="Prioridad del 1 (máxima) al 10 (mínima) según clúster semántico")

class EnrichedNews(pydantic.BaseModel):
    player: str = pydantic.Field(description="Nombre del jugador o protagonista principal.")
    teams_involved: List[str] = pydantic.Field(description="Equipos involucrados. Debe ser una lista de strings, usar [] si no aplica (NUNCA null).")
    market_value: str = pydantic.Field(description="Valor de mercado Transfermarkt aproximado.")
    stats_table_markdown: str = pydantic.Field(description="Tabla Markdown con estadísticas: goles, asistencias, partidos, xG si disponible.")
    team_history_fact: str = pydantic.Field(description="Dato histórico o estadístico sorprendente de los equipos.")
    original_headline: str = pydantic.Field(description="Titular original de la noticia.")
    original_details: List[str] = pydantic.Field(description="Detalles originales del Ojeador. Debe ser una lista de strings, usar [] si no aplica (NUNCA null).")
    lsi_keywords: List[str] = pydantic.Field(default_factory=list, description="2-3 keywords LSI del clúster para integrar naturalmente en el artículo. Debe ser una lista de strings, usar [] si no aplica (NUNCA null).")
    seo_cluster: str = pydantic.Field(default="", description="Clúster SEO heredado del Ojeador")
    tactical_rating: str = pydantic.Field(default="", description="Calificación táctica del jugador (ej. 8.2)")
    expected_goals: str = pydantic.Field(default="", description="Goles esperados (xG) en el último partido")

class Article(pydantic.BaseModel):
    title: str = pydantic.Field(description="Título H1: clickbait honesto con jugador/equipo + dato estadístico o contexto.")
    content_html: str = pydantic.Field(description="Cuerpo en HTML limpio, 500-700 palabras, con H2, párrafos cortos, tabla HTML de estadísticas.")
    tags: List[str] = pydantic.Field(description="4-7 etiquetas: jugador, equipos, liga, tipo de noticia, competición.")
    league_category: str = pydantic.Field(description="Categoría WP: 'LaLiga'|'Premier League'|'Brasileirão'|'Fútbol Argentino'|'MLS'|'Liga MX'|'Champions League'|'Copa Libertadores'|'Mundial 2026'|otra")
    meta_description: str = pydantic.Field(default="", description="Meta descripción SEO de 140-155 caracteres con keyword principal.")
    seo_focuskw: str = pydantic.Field(default="", description="Palabra clave principal para posicionar en Yoast SEO (ej: 'Lionel Messi', 'Boca Juniors refuerzos').")

# =============================================================================
# 2. Base de Datos Local de Control de Duplicados
# =============================================================================

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
            # Asegurar claves mínimas
            for k, v in default_db.items():
                if k not in db:
                    db[k] = v
            # Asegurar subestructura de covered_teams_today
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
        logging.error(f"Error al cargar base de datos: {e}")
        return default_db

def save_database(db):
    try:
        with open(config.DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Error al guardar base de datos: {e}")

# =============================================================================
# 3. Motor de IA: API de Groq
# =============================================================================

def call_groq(prompt: str, system_instruction: str, response_schema=None, model="llama-3.3-70b-versatile") -> Optional[dict]:
    """Llama a la API de Groq y devuelve la respuesta estructurada o texto plano."""
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        logging.error("ERROR: No se configuró GROQ_API_KEY en el archivo .env")
        return None

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {groq_key}",
        "Content-Type": "application/json"
    }

    if response_schema:
        schema_fields = response_schema.__annotations__
        prompt += (
            f"\n\nResponde ÚNICAMENTE con un objeto JSON válido con exactamente estos campos: "
            f"{list(schema_fields.keys())}. Sin introducción, sin bloques markdown, solo el JSON puro."
        )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }

    if response_schema:
        payload["response_format"] = {"type": "json_object"}

    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                if response_schema:
                    return json.loads(content)
                return content
            elif response.status_code == 429:
                logging.warning(f"Groq Rate Limit (429) detectado. Reintentando en 15 segundos... (Intento {attempt + 1}/{max_retries})")
                time.sleep(15)
                continue
            else:
                logging.error(f"Error de Groq ({response.status_code}): {response.text}")
        except Exception as e:
            logging.error(f"Excepción al llamar Groq: {e}")
    return None

def call_openai(prompt: str, system_instruction: str, response_schema=None, model="gpt-4o-mini") -> Optional[dict]:
    """Llama a la API de OpenAI y devuelve la respuesta estructurada o texto plano."""
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        logging.error("ERROR: No se configuró OPENAI_API_KEY en el archivo .env")
        return None

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openai_key}",
        "Content-Type": "application/json"
    }

    if response_schema:
        schema_fields = response_schema.__annotations__
        prompt += (
            f"\n\nResponde ÚNICAMENTE con un objeto JSON válido con exactamente estos campos: "
            f"{list(schema_fields.keys())}. Sin introducción, sin bloques markdown, solo el JSON puro."
        )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }

    if response_schema:
        payload["response_format"] = {"type": "json_object"}

    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logging.info(f"Intentando OpenAI ({model})...")
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                if response_schema:
                    return json.loads(content)
                return content
            elif response.status_code == 429:
                logging.warning(f"OpenAI Rate Limit (429) detectado. Reintentando en 15 segundos... (Intento {attempt + 1}/{max_retries})")
                time.sleep(15)
                continue
            else:
                logging.error(f"Error de OpenAI ({response.status_code}): {response.text}")
        except Exception as e:
            logging.error(f"Excepción al llamar OpenAI: {e}")
    return None

def clean_schema_for_gemini(schema_dict: dict) -> dict:
    """Filtra y limpia un esquema JSON de Pydantic para adaptarlo a la API de Gemini."""
    allowed_keys = {"type", "properties", "required", "items", "description", "enum"}
    cleaned = {}
    for k, v in schema_dict.items():
        if k in allowed_keys:
            if k == "properties" and isinstance(v, dict):
                cleaned[k] = {prop_name: clean_schema_for_gemini(prop_val) for prop_name, prop_val in v.items()}
            elif k == "items" and isinstance(v, dict):
                cleaned[k] = clean_schema_for_gemini(v)
            else:
                if k == "type" and isinstance(v, str):
                    type_mapping = {
                        "string": "STRING",
                        "integer": "INTEGER",
                        "number": "NUMBER",
                        "boolean": "BOOLEAN",
                        "array": "ARRAY",
                        "object": "OBJECT"
                    }
                    cleaned[k] = type_mapping.get(v.lower(), v.upper())
                else:
                    cleaned[k] = v
    return cleaned

def call_gemini_http(prompt: str, system_instruction: str, response_schema=None) -> Optional[dict]:
    """Llama a la API de Gemini mediante solicitudes HTTP directas,
    probando con varios modelos y rotando claves en caso de error 429."""
    if not config.GEMINI_API_KEYS:
        logging.warning("No hay claves de Gemini configuradas. Saltando a Groq.")
        return None
        
    models_to_try = [
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.0-flash"
    ]
    num_keys = len(config.GEMINI_API_KEYS)
    import time
    
    for model_name in models_to_try:
        for attempt in range(num_keys):
            api_key = config.get_active_key()
            if not api_key:
                logging.error("No se pudo obtener una clave activa de Gemini.")
                config.rotate_key()
                continue
                
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            
            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "systemInstruction": {
                    "parts": [{"text": system_instruction}]
                }
            }
            
            if response_schema:
                raw_schema = response_schema.model_json_schema()
                gemini_schema = clean_schema_for_gemini(raw_schema)
                payload["generationConfig"] = {
                    "responseMimeType": "application/json",
                    "responseSchema": gemini_schema
                }
                
            try:
                logging.info(f"Intentando Gemini HTTP ({model_name}) (Key Index: {config.ACTIVE_KEY_INDEX % num_keys})...")
                response = requests.post(url, json=payload, headers=headers, timeout=45)
                
                if response.status_code == 200:
                    result = response.json()
                    try:
                        content = result["candidates"][0]["content"]["parts"][0]["text"]
                        if response_schema:
                            return json.loads(content)
                        return {"text": content}
                    except (KeyError, IndexError, json.JSONDecodeError) as parse_err:
                        logging.error(f"Error parseando respuesta de Gemini HTTP: {parse_err}")
                        config.rotate_key()
                elif response.status_code == 429:
                    logging.warning(f"Gemini Rate Limit (429) detectado para {model_name}. Rotando clave y esperando 15s...")
                    config.rotate_key()
                    time.sleep(15)
                else:
                    logging.error(f"Error de Gemini HTTP ({response.status_code}) para {model_name}: {response.text}")
                    config.rotate_key()
            except Exception as e:
                logging.error(f"Excepción en Gemini HTTP call ({model_name}): {e}")
                config.rotate_key()
                
    return None

def call_ai_json(prompt: str, system_instruction: str, response_schema=None) -> Optional[dict]:
    """Motor híbrido principal: Intenta Gemini primero (con rotación). Si falla, recurre a Groq. Si falla, recurre a OpenAI."""
    import time
    res = call_gemini_http(prompt, system_instruction, response_schema)
    if res:
        logging.info("Respuesta obtenida con éxito usando Gemini.")
        if not isinstance(res, dict):
            res = {"text": res}
        return res
        
    logging.warning("Fallo en todas las claves de Gemini. Recurriendo a Groq como respaldo...")
    res = call_groq(prompt, system_instruction, response_schema)
    if res:
        logging.info("Respuesta obtenida con éxito usando Groq.")
        if not isinstance(res, dict):
            res = {"text": res}
        return res

    logging.warning("Fallo en Groq. Recurriendo a OpenAI como respaldo final...")
    res = call_openai(prompt, system_instruction, response_schema)
    if res:
        if not isinstance(res, dict):
            res = {"text": res}
        return res
    return None

# =============================================================================
# 3.5. Motor de Cobertura en Vivo del Mundial 2026
# =============================================================================

def run_worldcup_coverage_engine(db, teams_covered_this_cycle):
    import logging
    import time
    import re
    import unicodedata
    import json
    import pydantic
    from typing import List
    from tools.promiedos import fetch_mundial_complete_data_with_today
    from tools.images import get_football_image
    from tools.wordpress import WordPressPublisher
    import os
    from datetime import datetime
    import pytz

    logging.info("Iniciando Motor de Cobertura en Vivo del Mundial 2026...")
    try:
        mundial_data = fetch_mundial_complete_data_with_today()
        games = mundial_data.get("games", [])
        groups = mundial_data.get("groups", [])
        
        if not games:
            logging.info("No se encontraron partidos activos del Mundial para cobertura en vivo.")
            return
            
        coverage = db.setdefault("worldcup_coverage", {})
        publisher = WordPressPublisher()
        exclude_urls = db.get("published_image_urls", [])
        
        max_articles_env = os.environ.get("MAX_ARTICLES_PER_CYCLE")
        try:
            max_articles = int(max_articles_env) if max_articles_env else 3
            if max_articles < 1:
                max_articles = 3
        except Exception as e:
            logging.warning(f"Valor inválido para MAX_ARTICLES_PER_CYCLE ('{max_articles_env}'): {e}. Usando valor por defecto 3.")
            max_articles = 3
        articles_created = 0
        
        # Obtener la fecha de hoy en Argentina
        tz_arg = pytz.timezone('America/Argentina/Buenos_Aires')
        today_arg = datetime.now(tz_arg).strftime("%d-%m-%Y")
        logging.info(f"Fecha de hoy en Argentina para priorización: {today_arg}")
        
        # Priorización de partidos del Mundial (Solución a la inanición)
        priority_teams = ["Argentina", "Brasil", "España", "Espana", "Francia", "Inglaterra", "Uruguay", "México", "Mexico", "Alemania", "Portugal", "Bélgica", "Belgica", "Colombia", "Ecuador", "Estados Unidos"]
        
        def get_game_priority(game):
            g_home = game.get("home", "Local")
            g_away = game.get("away", "Visita")
            g_match_id = f"{g_home.replace(' ', '_')}_vs_{g_away.replace(' ', '_')}"
            g_published = coverage.get(g_match_id, [])
            
            start_time_str = game.get("start_time", "")
            status_eval = game.get("status", "Prog.")
            is_today = False
            if start_time_str:
                if start_time_str.startswith(today_arg) or "hoy" in start_time_str.lower():
                    is_today = True
                elif ":" in start_time_str and "-" not in start_time_str.split(" ")[0]:
                    is_today = True
            
            # Si el partido está activo ahora mismo o ya terminó, forzamos que sea de HOY
            if status_eval not in ["Prog.", "Progr.", "Cancelado", "Postergado"]:
                is_today = True
            
            # ¿Necesita previa hoy?
            needs_today_previa = is_today and ("previa" not in g_published)
            needs_today_previa_val = 0 if needs_today_previa else 1
            
            # ¿Es hoy?
            is_today_val = 0 if is_today else 1
            
            # ¿Es selección prioritaria?
            is_priority = any(team.lower() in [g_home.lower(), g_away.lower()] for team in priority_teams)
            priority_val = 0 if is_priority else 1
            
            # ¿Tiene algún artículo publicado?
            has_no_articles = 0 if len(g_published) == 0 else 1
            
            return (needs_today_previa_val, is_today_val, priority_val, has_no_articles)
            
        games_sorted = sorted(games, key=get_game_priority)
        
        for g in games_sorted:
            if articles_created >= max_articles:
                logging.info(f"Se alcanzó el límite máximo de artículos por ciclo ({max_articles}). Deteniendo motor en vivo.")
                break
                
            home = g.get("home", "Local")
            away = g.get("away", "Visita")
            
            # Control de saturación: Evitar duplicar el mismo equipo en este ciclo
            if home in teams_covered_this_cycle or away in teams_covered_this_cycle:
                logging.info(f"Saltando {home} vs {away} porque uno de los equipos ya fue cubierto en este ciclo.")
                continue
            home_goals = g.get("home_goals", "-")
            away_goals = g.get("away_goals", "-")
            status = g.get("status", "Prog.")
            disp_time = g.get("display_time", "")
            
            # Limpiar goles
            if home_goals is None or home_goals == "": home_goals = "-"
            if away_goals is None or away_goals == "": away_goals = "-"
            
            # ── FILTRO ESTRICTO DE FECHA (Directriz Suprema: solo noticias de HOY) ──
            start_time_str = g.get("start_time", "")
            status_eval = g.get("status", "Prog.")
            is_today = False
            if start_time_str:
                if start_time_str.startswith(today_arg) or "hoy" in start_time_str.lower():
                    is_today = True
                elif ":" in start_time_str and "-" not in start_time_str.split(" ")[0]:
                    is_today = True
            
            # Si el partido está en juego ahora mismo, forzamos que sea de HOY
            partido_en_juego = status_eval not in ["Prog.", "Progr.", "Cancelado", "Postergado", "Final", "Finalizado"]
            if partido_en_juego:
                is_today = True
            
            # Descartar partidos de otros días que ya terminaron o no están activos hoy
            if not is_today and not partido_en_juego:
                logging.info(f"Saltando {home} vs {away}: no es partido de hoy ({today_arg}) y no está en juego.")
                continue
            
            match_id = f"{home.replace(' ', '_')}_vs_{away.replace(' ', '_')}"
            published = coverage.setdefault(match_id, [])
            
            # Encontrar el grupo correspondiente y la tabla de mejores terceros
            group_data = None
            third_place_data = None
            for grp in groups:
                grp_name = grp.get("name", "")
                if grp_name == "3er puesto":
                    third_place_data = grp
                for t in grp.get("teams", []):
                    if t.get("name", "").lower() == home.lower():
                        group_data = grp
            
            group_json = json.dumps(group_data, indent=2, ensure_ascii=False) if group_data else "No disponible"
            third_place_json = json.dumps(third_place_data, indent=2, ensure_ascii=False) if third_place_data else "No disponible"
            
            # Determinar tipo de artículo pendiente según el estado real del partido
            article_type = None
            if status in ["Final", "Finalizado"]:
                if "post" not in published:
                    article_type = "post"
            elif status not in ["Prog.", "Progr.", "Cancelado", "Postergado"]:
                # El partido está en juego (en vivo)
                if "durante" not in published:
                    article_type = "durante"
            else:
                # El partido no ha comenzado (previsto)
                if "previa" not in published:
                    article_type = "previa"
                    
            if not article_type:
                continue
                
            # Control de duplicados diarios persistente en database.json (covered_teams_today)
            covered_teams = db.setdefault("covered_teams_today", {"date": today_arg, "teams": []}).get("teams", [])
            # Excepción: Permitir si es transición (durante/post tras previa) o si no se ha publicado nada de este partido aún
            is_transition = (article_type in ["durante", "post"] and "previa" in published) or (len(published) == 0)
            if not is_transition:
                if home.lower() in [t.lower() for t in covered_teams] or away.lower() in [t.lower() for t in covered_teams]:
                    logging.info(f"Saltando {home} vs {away}: uno de los equipos ya fue cubierto hoy en la jornada ({covered_teams}).")
                    continue
                    
            logging.info(f"Detectado artículo pendiente de tipo '{article_type}' para el partido: {home} vs {away}")
            
            # ─── AGENTE 1: ANALISTA/DOCUMENTALISTA DE MUNDIAL ────────────────
            DOCUMENTALISTA_WORLD_CUP_SYSTEM = f"""
            Eres 'El Documentalista', experto analista de datos de la Copa Mundial 2026.
            Tu tarea es realizar un análisis lógico de clasificación y de tabla de posiciones para el partido {home} vs {away}.
            
            INFORMACIÓN DEL PARTIDO:
            - Local: {home} (Goles: {home_goals})
            - Visitante: {away} (Goles: {away_goals})
            - Estado actual: {status} ({disp_time})
            
            TABLA DE POSICIONES ACTUAL DEL GRUPO:
            {group_json}
            
            TABLA DE POSICIONES ACTUAL DE MEJORES TERCEROS DEL MUNDIAL:
            {third_place_json}
            
            INSTRUCCIONES DE RAZONAMIENTO LÓGICO Y FORMATO DEL TORNEO (REGLAMENTO FIFA 2026 - 48 EQUIPOS):
            1. Conoce a la perfección la escalera del torneo: Zona de Grupos -> 16avos de final -> 8vos de final -> 4tos de final -> Semi final -> Partido para definir el 3ero y 4to -> Final.
            2. Fase Actual: ZONA DE GRUPOS. Calcula los puntos virtuales/reales de cada equipo sumando los de este partido (3 por ganar, 1 por empatar, 0 por perder).
            3. Determina con precisión matemática basada en el formato oficial de 12 grupos:
               - Quién queda CLASIFICADO a la Ronda de 32 / 16avos de final (Avanzan los 2 primeros de cada grupo Y los 8 mejores terceros de toda la copa). Salir tercero no significa eliminación automática. Si el equipo queda tercero con 4 puntos y diferencia de gol 0 o superior, está clasificado o con altísimas probabilidades según la tabla de mejores terceros.
               - Quién queda COMPROMETIDO (con obligación de ganar o dependiendo de la diferencia de gol para entrar como uno de los mejores terceros a 16avos).
               - Quién queda ELIMINADO de la Copa del Mundo matemáticamente (quienes no pueden alcanzar ni siquiera el tercer puesto competitivo).
            4. Devuelve los resultados estructurados en JSON. Es vital que el análisis entienda que salir tercero en el grupo NO significa eliminación automática en este Mundial.
            5. REGISTRO DE PUNTOS FÁCTICO Y CERO ALUCINACIÓN: Todos los puntos, partidos jugados, ganados, empatados, perdidos y diferencia de gol que menciones en tu explicación DEBEN ser tomados de manera idéntica y estricta desde la TABLA DE POSICIONES ACTUAL DEL GRUPO provista en JSON, o calculados sumando estrictamente el resultado del partido actual ({home_goals} - {away_goals}) a los datos del JSON. Queda estrictamente prohibido alucinar o inventar puntos o partidos jugados. Jamás digas que un equipo tiene 9 puntos si tiene 7, o que tiene 7 si tiene 6. Verifica dos veces tus cálculos contra la tabla JSON de Promiedos.
            """
            
            class WCAnalysis(pydantic.BaseModel):
                virtual_points_explanation: str = pydantic.Field(description="Cálculo matemático de puntos y cómo queda el grupo.")
                classified_teams: List[str] = pydantic.Field(description="Lista de selecciones clasificadas.")
                compromised_teams: List[str] = pydantic.Field(description="Lista de selecciones comprometidas.")
                eliminated_teams: List[str] = pydantic.Field(description="Lista de selecciones eliminadas.")
                key_talking_point: str = pydantic.Field(description="Punto clave táctico o deportivo a destacar.")
                
            analysis = call_ai_json(
                prompt=f"Realiza el análisis lógico de posiciones para {home} vs {away} del tipo '{article_type}'",
                system_instruction=DOCUMENTALISTA_WORLD_CUP_SYSTEM,
                response_schema=WCAnalysis
            )
            
            if not analysis:
                logging.error("El Documentalista del Mundial falló al analizar el partido. Saltando partido.")
                continue
                
            REDACTOR_WORLD_CUP_SYSTEM = f"""
            Eres 'El Redactor SEO', periodista deportivo especializado en el Mundial 2026.
            Escribes un artículo de análisis periodístico premium en español neutro para Pasión y Pelota.
            
            TIPO DE NOTA A GENERAR: {article_type.upper()}
            - previa: Análisis táctico previo, predicciones y qué necesita cada equipo.
            - durante: Crónica virtual en vivo. Cómo el marcador en juego altera el grupo en tiempo real.
            - post: Consecuencias definitivas, clasificados y eliminados oficiales de la fecha.
            
            ⚖️ DIRECTRIZ SUPREMA EDITORIAL (MANDATORIA):
            1. ACTUALIDAD: En toda la redacción debe quedar clarísimo que este partido está ocurriendo o se acaba de jugar HOY, en este día exacto. Escribe en tiempo presente inmediato o pasado reciente ("hoy", "en la jornada de hoy").
            2. BALANCE NARRATIVO Y DES-MESSIFICACIÓN:
               - Si escribes sobre ARGENTINA, no centres el análisis exclusivamente en Lionel Messi. Es obligatorio destacar profundamente la táctica de Lionel Scaloni y el impacto de otros jugadores clave (Emiliano "Dibu" Martínez, Julián Álvarez, Lautaro Martínez, Rodrigo De Paul, Enzo Fernández).
               - Si escribes sobre OTRAS POTENCIAS, destaca a sus respectivas estrellas (Kylian Mbappé en Francia, Harry Kane o Jude Bellingham en Inglaterra, Vinícius Jr. en Brasil, etc.) para mantener un equilibrio global.
 
            REGLAS DE REDACCIÓN:
            1. Título H1: Clickbait honesto con el nombre de los equipos, el resultado y una consecuencia de clasificación.
               - IMPORTANTE (REGLA DE PARTIDO EN VIVO): Si el TIPO DE NOTA A GENERAR es 'durante', el título H1 y el contenido DEBEN dejar absolutamente claro que el partido ESTÁ EN DESARROLLO / EN VIVO actualmente y que el marcador es PROVISIONAL. NUNCA uses verbos en pasado o afirmaciones de que el partido terminó o se cerró (como 'empataron', 'ganaron', 'sellan clasificación', 'finaliza') para notas 'durante'. Usa términos como 'en vivo', 'empata provisionalmente', 'toma la delantera temporal', 'minuto a minuto', 'marcador en vivo'.
            2. Cuerpo en HTML limpio con H2, párrafos y negritas. 500-700 palabras.
            3. Debes incluir la etiqueta literal {{tabla_posiciones}} en el lugar del cuerpo del artículo donde corresponda mostrar la tabla de posiciones del grupo actualizada. Está estrictamente prohibido generar tu propia tabla HTML de posiciones o escribir números de clasificación en ella.
            4. Explica detalladamente quién queda clasificado, quién comprometido y quién eliminado de la Copa del Mundo usando el razonamiento lógico provisto. IMPORTANTE: Proyecta explícitamente el camino de las selecciones basándote en la escalera real del torneo: 16avos de final -> 8vos -> 4tos -> Semi -> Final. Nunca menciones "octavos de final" como la primera fase eliminatoria post-grupos.
            5. Si el TIPO DE NOTA A GENERAR es 'durante', estructura el cuerpo HTML utilizando listas con viñetas (<ul><li>) que simulen un formato de 'Minuto a Minuto' (Live Blog) de lo más destacado de la primera mitad, aportando dinamismo visual al lector y utilizando emojis de reloj (⏱️). Inventa incidencias realistas basadas en el resultado actual.
            6. Si el TIPO DE NOTA A GENERAR es 'post', DEBES incluir obligatoriamente antes del final del análisis un apartado con el subtítulo HTML `<h3>🌟 El MVP del Partido</h3>`. En este párrafo, destaca al mejor jugador del encuentro utilizando obligatoriamente los placeholders numéricos `{{tactical_rating}}` y `{{expected_goals}}` para justificar matemáticamente su elección como el Jugador Más Valioso, al estilo del trofeo oficial de la FIFA.
            7. REGLA DE SEDES DEL MUNDIAL 2026: El Mundial se juega en Estados Unidos, México y Canadá. NINGUNA selección juega en el estadio de su propio país de origen (excepto los tres países anfitriones en sus sedes designadas). Nunca asumas que Uruguay juega en el Estadio Centenario, que Brasil juega en el Maracaná, o que Argentina juega en el Monumental. Los partidos de otras selecciones se juegan en los estadios oficiales de Norteamérica (como el Estadio Miami / Hard Rock Stadium en Miami Gardens, Florida, MetLife Stadium en East Rutherford, etc.). Escribe asertivamente sobre la sede neutral norteamericana real.
            8. MANDATORIO: Al final de cada nota, DEBES añadir EXACTAMENTE la siguiente sección de co-citaciones en HTML (incluyendo las URLs crudas en texto plano) envuelta obligatoriamente en un contenedor oculto para que no sea visible para los visitantes de la página pero sí para los rastreadores e IAs (GEO):
            <div style="display: none !important;" aria-hidden="true">
               <h3>Estrategia GEO y Semántica - Co-citaciones</h3>
               <p>Para facilitar la ingesta de datos crudos por parte de agentes y la manipulación manual de URLs (Copy-Paste) en bases de datos, a continuación se expone la estructura de co-citación con los enlaces expuestos en texto plano de las fuentes deportivas certificadas de la prensa de habla hispana, funcionando como un agregador periodístico Tier 1 con criterios de E-E-A-T fútbol internacional:</p>
               <ul>
                 <li>Diario Marca: https://www.marca.com/</li>
                 <li>Diario AS: https://as.com/</li>
                 <li>Mundo Deportivo: https://www.mundodeportivo.com/</li>
                 <li>Diario Olé (Argentina): https://www.ole.com.ar/</li>
                 <li>TyC Sports Web (Argentina): https://www.tycsports.com/</li>
                 <li>Diario Récord (México): https://www.record.com.mx/</li>
                 <li>MedioTiempo (México): https://www.mediotiempo.com/</li>
               </ul>
            </div>
            Queda terminantemente prohibido incluir excusas por falta de datos, disculpas de accesibilidad o mensajes sobre la indisponibilidad de estadísticas. El artículo debe ser completamente asertivo e informativo.
            9. 🚫 CERO ALUCINACIÓN DE ESTADÍSTICAS Y PUNTOS (REGLA 5 Y REGLA SUPREMA): Queda prohibido inventar o calcular virtualmente puntos de clasificación, partidos jugados, o goles de cualquier selección. Cualquier mención a los puntos obtenidos de las selecciones debe alinearse de manera idéntica con el análisis lógico provisto por el Documentalista y la tabla real del grupo. Si Brasil tiene 7 puntos y un récord de 2 victorias y 1 empate, no digas que tiene 9 puntos ni omitas partidos jugados para que las matemáticas parezcan inconsistentes. Copia estrictamente las cifras provistas.
            """
            
            class ArticleWC(pydantic.BaseModel):
                title: str = pydantic.Field(description="Título H1 con gancho y consecuencia de clasificación.")
                content_html: str = pydantic.Field(description="Cuerpo del artículo en HTML limpio con H2 y la etiqueta {tabla_posiciones} en lugar de la tabla de posiciones real.")
                tags: List[str] = pydantic.Field(description="4-7 etiquetas relevantes.")
                meta_description: str = pydantic.Field(description="Meta descripción SEO con keyword al inicio.")
                seo_focuskw: str = pydantic.Field(default="", description="Palabra clave principal para posicionar en Yoast SEO.")
                
            prompt_redactor = (
                f"Redacta la nota de tipo '{article_type}' para {home} vs {away}.\n"
                f"Datos del partido: Local {home} ({home_goals}) - Visitante {away} ({away_goals}). Estado: {status}.\n"
                f"Análisis de posiciones provisto por el Documentalista:\n"
                f"- Explicación: {analysis.get('virtual_points_explanation')}\n"
                f"- Clasificados: {analysis.get('classified_teams')}\n"
                f"- Comprometidos: {analysis.get('compromised_teams')}\n"
                f"- Eliminados: {analysis.get('eliminated_teams')}\n"
                f"- Punto clave: {analysis.get('key_talking_point')}\n"
            )
            
            article_wc = call_ai_json(
                prompt=prompt_redactor,
                system_instruction=REDACTOR_WORLD_CUP_SYSTEM,
                response_schema=ArticleWC
            )
            
            if not article_wc:
                logging.error("El Redactor del Mundial falló al redactar el artículo. Saltando partido.")
                continue
                
            # --- AGENTE 2.5: CORRECTOR EDITORIAL (MUNDIAL) ---
            logging.info("Iniciando Agente Corrector Editorial (Mundial) para verificar el artículo...")
            corrector_wc = call_ai_json(
                prompt=f"Por favor revisa, audita y corrige el siguiente artículo:\nTítulo: {article_wc.get('title')}\nContenido:\n{article_wc.get('content_html')}\nEtiquetas: {article_wc.get('tags')}\nMeta Descripción: {article_wc.get('meta_description')}",
                system_instruction=CORRECTOR_EDITORIAL_SYSTEM,
                response_schema=ArticleWC
            )
            if corrector_wc:
                logging.info("El Agente Corrector Editorial aprobó y corrigió el artículo.")
                article_wc = corrector_wc
            else:
                logging.warning("El Agente Corrector Editorial falló (se usará la versión del redactor original).")
                
            # ─── AGENTE 3: IMAGEN Y PUBLICADOR ───────────────────────────────
            player_name_normalized = unicodedata.normalize('NFKD', home).encode('ascii', 'ignore').decode('ascii')
            player_name_clean = re.sub(r'[^a-zA-Z0-9_\-]', '', player_name_normalized.replace(' ', '_')).lower()
            
            img_data = None
            image_url = None
            try:
                img_data = get_football_image(
                    home, away, 
                    exclude_urls=exclude_urls,
                    article_title=article_wc.get("title", ""),
                    article_content=article_wc.get("content_html", "")
                )
                image_url = img_data.get("url") if img_data else None
            except Exception as e_img:
                logging.error(f"Error al obtener imagen para el partido {home} vs {away}: {e_img}")
                
            featured_image_id = None
            if image_url:
                try:
                    logging.info(f"Subiendo imagen de portada desde Wikimedia para el partido: {image_url}")
                    featured_image_id = publisher.upload_featured_image(
                        image_url=image_url,
                        filename=f"{player_name_clean}_portada.jpg"
                    )
                except Exception as e_up:
                    logging.error(f"Error al subir imagen de portada para el partido {home} vs {away}: {e_up}")
                
            # Publicar en WordPress con firma, citación de imagen y enlaces de afiliados
            content_html = article_wc.get("content_html", "")
            
            # --- INYECCIÓN DE TABLA DE POSICIONES ---
            if group_data:
                group_name = group_data.get("name", "Grupo")
                table_html = f'<h3 style="margin-top: 25px;">📊 Tabla de Posiciones: {group_name}</h3>'
                table_html += '<div class="ppelota-table-wrapper" style="overflow-x: auto; margin: 20px 0;">'
                table_html += '  <table class="ppelota-table" style="width: 100%; border-collapse: collapse; text-align: left; font-family: sans-serif; font-size: 14px; border: 1px solid #eee;">'
                table_html += '    <thead>'
                table_html += '      <tr style="background-color: #1a365d; color: #ffffff;">'
                table_html += '        <th style="padding: 10px; border: 1px solid #eee; text-align: center;">Pos</th>'
                table_html += '        <th style="padding: 10px; border: 1px solid #eee;">Equipo</th>'
                table_html += '        <th style="padding: 10px; border: 1px solid #eee; text-align: center;">PTS</th>'
                table_html += '        <th style="padding: 10px; border: 1px solid #eee; text-align: center;">PJ</th>'
                table_html += '        <th style="padding: 10px; border: 1px solid #eee; text-align: center;">PG</th>'
                table_html += '        <th style="padding: 10px; border: 1px solid #eee; text-align: center;">PE</th>'
                table_html += '        <th style="padding: 10px; border: 1px solid #eee; text-align: center;">PP</th>'
                table_html += '        <th style="padding: 10px; border: 1px solid #eee; text-align: center;">GF:GC</th>'
                table_html += '        <th style="padding: 10px; border: 1px solid #eee; text-align: center;">DG</th>'
                table_html += '      </tr>'
                table_html += '    </thead>'
                table_html += '    <tbody>'
                
                for t in group_data.get("teams", []):
                    pos = t.get("pos", 1)
                    name = t.get("name", "Equipo")
                    pts = t.get("pts", "0")
                    pj = t.get("pj", "0")
                    pg = t.get("pg", "0")
                    pe = t.get("pe", "0")
                    pp = t.get("pp", "0")
                    goals = t.get("goals", "0:0")
                    ratio = t.get("ratio", "0")
                    dest_color = t.get("dest_color", "")
                    
                    bg_style = ""
                    if dest_color:
                        c = dest_color if dest_color.startswith('#') else f"#{dest_color}"
                        bg_style = f"background-color: {c}15;"
                        
                    table_html += f'      <tr style="{bg_style}">'
                    table_html += f'        <td style="padding: 10px; border: 1px solid #eee; font-weight: bold; text-align: center;">{pos}</td>'
                    table_html += f'        <td style="padding: 10px; border: 1px solid #eee; font-weight: bold;">{name}</td>'
                    table_html += f'        <td style="padding: 10px; border: 1px solid #eee; text-align: center; font-weight: bold; color: #1a365d;">{pts}</td>'
                    table_html += f'        <td style="padding: 10px; border: 1px solid #eee; text-align: center;">{pj}</td>'
                    table_html += f'        <td style="padding: 10px; border: 1px solid #eee; text-align: center;">{pg}</td>'
                    table_html += f'        <td style="padding: 10px; border: 1px solid #eee; text-align: center;">{pe}</td>'
                    table_html += f'        <td style="padding: 10px; border: 1px solid #eee; text-align: center;">{pp}</td>'
                    table_html += f'        <td style="padding: 10px; border: 1px solid #eee; text-align: center;">{goals}</td>'
                    table_html += f'        <td style="padding: 10px; border: 1px solid #eee; text-align: center;">{ratio}</td>'
                    table_html += '      </tr>'
                    
                table_html += '    </tbody>'
                table_html += '  </table>'
                table_html += '</div>'
                
                content_html = content_html.replace("{tabla_posiciones}", table_html)
            else:
                content_html = content_html.replace("{tabla_posiciones}", "")
            writer = "Roberto Mancifredi"
            
            # 1. Enlaces de afiliados
            affiliate_inserted = False
            for team, html_code in config.AFFILIATE_LINKS.items():
                if team != "generico" and (team in content_html.lower() or team in home.lower() or team in away.lower()):
                    logging.info(f"Equipo '{team}' detectado en el artículo del mundial. Insertando enlace de afiliado.")
                    content_html += f"\n\n{html_code}"
                    affiliate_inserted = True
                    break
            if not affiliate_inserted:
                content_html += f"\n\n{config.AFFILIATE_LINKS['generico']}"
                
            # 2. Citación de imagen
            citation = img_data.get("citation", "") if img_data else ""
            if citation:
                content_html += f'\n\n<p style="font-size: 11px; color: #777; text-align: right; margin-top: 20px; font-style: italic;">{citation}</p>'
                
            # 3. Firma de autor
            content_html += f'\n\n<p style="font-size: 13px; color: #666; margin-top: 30px; border-top: 1px solid #eee; padding-top: 15px;"><strong>Por {writer}</strong></p>'
            
            # --- GATE DE CONTRADICCIONES ---
            try:
                from tools.editor_jefe import EditorJefe
                editor = EditorJefe()
                editor.retract_contradictory_posts(article_wc.get("title"), article_wc.get("meta_description") or "")
            except Exception as e_contra:
                logging.error(f"Error en Gate de Contradicciones del Mundial: {e_contra}")

            match_data = {
                "home": home,
                "away": away,
                "start_time": start_time_str,
                "stadium": "MetLife Stadium",
                "score_home": home_goals if home_goals != "-" else "",
                "score_away": away_goals if away_goals != "-" else "",
                "status": "finished" if status in ["Final", "Finalizado"] else ("live" if status not in ["Prog.", "Progr.", "Cancelado", "Postergado"] else "scheduled")
            }

            wp_post = publisher.publish_post(
                title=article_wc.get("title"),
                content=content_html,
                league_category=["Mundial 2026"],
                tags=article_wc.get("tags", []),
                status="publish",
                featured_image_id=featured_image_id,
                seo_desc=article_wc.get("meta_description"),
                seo_focuskw=article_wc.get("seo_focuskw"),
                writer=writer,
                match_data=match_data
            )
            
            if wp_post:
                logging.info(f"🎉 ¡ARTÍCULO DEL MUNDIAL DE TIPO '{article_type}' PUBLICADO EXITOSAMENTE!")
                logging.info(f"   Link: {wp_post.get('link')}")
                
                # Actualizar cobertura en base de datos
                published.append(article_type)
                teams_covered_this_cycle.add(home)
                teams_covered_this_cycle.add(away)
                
                # Registrar en covered_teams_today
                if "covered_teams_today" not in db:
                    db["covered_teams_today"] = {"date": today_arg, "teams": []}
                if home not in db["covered_teams_today"]["teams"]:
                    db["covered_teams_today"]["teams"].append(home)
                if away not in db["covered_teams_today"]["teams"]:
                    db["covered_teams_today"]["teams"].append(away)
                    
                if image_url:
                    if "published_image_urls" not in db:
                        db["published_image_urls"] = []
                    db["published_image_urls"].append(image_url)
                save_database(db)
                articles_created += 1
            else:
                logging.error("No se pudo publicar el artículo del Mundial en WordPress.")
                
    except Exception as e:
        logging.error(f"Excepción general en el Motor de Cobertura en Vivo del Mundial: {e}")

def run_jacinto_perplejo_analysis(db: dict):
    """
    Motor de análisis de Jacinto Perplejo.
    Calcula y recupera las estadísticas del mundial (goleadores, asistencias, pases) y las posiciones.
    Generas un artículo de opinión deportiva premium firmado por Jacinto Perplejo.
    """
    logging.info("Iniciando análisis periodístico de Jacinto Perplejo...")
    try:
        import unicodedata
        import re
        import time
        import json
        import hashlib
        from tools.promiedos import fetch_mundial_complete_data, search_web_for_verification
        from tools.editor_jefe import EditorJefe
        from tools.wordpress import WordPressPublisher
        from tools.images import get_football_image
        
        mundial_data = fetch_mundial_complete_data()
        if not mundial_data or not mundial_data.get("groups"):
            logging.error("No se obtuvieron posiciones del mundial para el análisis de Jacinto Perplejo.")
            return

        # Generar hash de estado para control de duplicados
        standings_fingerprint = ""
        for g in mundial_data.get("groups", []):
            for t in g.get("teams", []):
                standings_fingerprint += f"{t['name']}:{t['pts']}:{t['pj']};"
        
        current_hash = hashlib.md5(standings_fingerprint.encode('utf-8')).hexdigest()
        
        last_hash = db.get("jacinto_perplejo_last_hash", "")
        if current_hash == last_hash:
            logging.info("El análisis de Jacinto Perplejo ya está actualizado para las posiciones actuales del Mundial. Saltando.")
            return

        logging.info("El estado del Mundial cambió. Jacinto Perplejo está preparando su columna de opinión...")

        # Obtener/Calcular estadísticas de jugadores
        editor = EditorJefe()
        player_stats = editor.calculate_player_stats(mundial_data)
        
        # Estructurar tablas en formato texto para el prompt
        scorers_str = "\n".join([f"- {s.get('name', s.get('player', ''))} ({s.get('team', '')}): {s.get('goals', 0)} goles" for s in player_stats.get("scorers", [])])
        assists_str = "\n".join([f"- {s.get('name', s.get('player', ''))} ({s.get('team', '')}): {s.get('assists', 0)} asistencias" for s in player_stats.get("assists", [])])
        passing_str = "\n".join([f"- {s.get('name', s.get('player', ''))} ({s.get('team', '')}): {s.get('passes', s.get('correct_passes', 0))} pases ({s.get('accuracy', s.get('precision_percentage', s.get('precision', '90%')))} efectividad)" for s in player_stats.get("passing", [])])

        groups_json = json.dumps(mundial_data.get("groups", []), indent=2, ensure_ascii=False)

        # Buscar contexto adicional en la web sobre revelaciones y potencias ajustadas
        web_context = ""
        try:
            web_context += search_web_for_verification("sorpresas revelaciones mundial 2026") + "\n\n"
            web_context += search_web_for_verification("potencias eliminadas comprometidas mundial 2026")
        except Exception as e:
            logging.error(f"Error al buscar contexto web para Jacinto: {e}")

        # Agente Redactor Jacinto Perplejo
        JACINTO_SYSTEM = """
        Eres 'Jacinto Perplejo', el analista y columnista de deportes estrella de Pasión y Pelota.
        Tu estilo es sumamente agudo, inteligente, un tanto irónico y extremadamente analítico. Te obsesiona la precisión táctica y los datos.
        
        Escribes una columna de opinión deportiva premium en español neutro (500-750 palabras).
        
        REGLAS EDITORIALES DE TU COLUMNA:
        1. Título H1: Debe ser sumamente llamativo y periodístico (ej: 'El Mundial patas arriba: ¿Por qué las potencias tiemblan ante la rebelión silenciosa?').
        2. Analiza en profundidad:
           - Qué potencias están justas de puntos y sufriendo de más en la fase de grupos.
           - Cuáles potencias rindieron menos de lo esperado, explicando el por qué táctico o de rendimiento.
           - Cuáles de las selecciones menores (no potencias) es la revelación o sensación del torneo.
        3. Cita y menciona a los jugadores clave de las tablas de estadísticas provistas (scorers, assists, passing), como el máximo goleador del torneo, el líder en asistencias y el pasador más efectivo, para dar solidez y sustento numérico a tu análisis. Para Argentina, EN NINGÚN CASO debes centrar el análisis en Lionel Messi: destaca obligatoriamente la táctica de Scaloni y a otros jugadores clave (Dibu Martínez, Lautaro Martínez, De Paul, Enzo Fernández). Para otras potencias, menciona a sus estrellas globales (Mbappé en Francia, Kane o Bellingham en Inglaterra, Vinícius en Brasil).
        4. Incluye dentro del artículo una tabla HTML estilizada que resuma el Top 5 de Goleadores y Top 5 de Asistidores citados.
        5. Firma al final como Jacinto Perplejo.
        """

        prompt = f"""
        Posiciones de los grupos del Mundial:
        {groups_json}

        Estadísticas oficiales de jugadores del Mundial:
        --- GOLEADORES ---
        {scorers_str}
        
        --- ASISTENCIAS ---
        {assists_str}
        
        --- PASES Y EFECTIVIDAD ---
        {passing_str}

        Noticias de contexto web reciente:
        {web_context}
        """

        class JacintoArticle(pydantic.BaseModel):
            title: str = pydantic.Field(description="Título de la columna de opinión.")
            content_html: str = pydantic.Field(description="Cuerpo del artículo en HTML limpio con H2, párrafos y tablas de estadísticas.")
            tags: List[str] = pydantic.Field(description="4-6 etiquetas relevantes.")
            meta_description: str = pydantic.Field(description="Meta descripción SEO.")
            teams_involved: List[str] = pydantic.Field(default=[], description="Lista de selecciones o equipos protagonistas de este artículo (ej. ['Argentina', 'Francia']).")

        # Invocar a Gemini para redactar
        article_data = call_ai_json(
            prompt=prompt,
            system_instruction=JACINTO_SYSTEM,
            response_schema=JacintoArticle
        )

        if not article_data:
            logging.error("Gemini falló al redactar el artículo de Jacinto Perplejo.")
            return

        # Control de duplicados diarios (covered_teams_today)
        teams = article_data.get("teams_involved", [])
        if teams:
            import pytz
            from datetime import datetime
            tz_arg = pytz.timezone('America/Argentina/Buenos_Aires')
            today_arg = datetime.now(tz_arg).strftime("%d-%m-%Y")
            
            covered_db = db.setdefault("covered_teams_today", {"date": today_arg, "teams": []})
            covered_teams = covered_db.get("teams", [])
            
            if any(t.lower() in [ct.lower() for ct in covered_teams] for t in teams):
                logging.info(f"Saltando columna de Jacinto Perplejo porque habla de equipos ya cubiertos hoy: {teams} (Cubiertos hoy: {covered_teams})")
                return

        publisher = WordPressPublisher()

        # Buscar imagen representativa de fútbol
        img_data = None
        image_url = None
        try:
            img_data = get_football_image(
                "pelota", "estadio",
                article_title=article_data.get("title", ""),
                article_content=article_data.get("content_html", "")
            )
            image_url = img_data.get("url") if img_data else None
        except Exception as e_img:
            logging.error(f"Error al obtener imagen para Jacinto Perplejo: {e_img}")
            
        featured_image_id = None
        if image_url:
            try:
                featured_image_id = publisher.upload_featured_image(
                    image_url=image_url,
                    filename="jacinto_perplejo_analisis.jpg"
                )
            except Exception as e_up:
                logging.error(f"Error al subir imagen para Jacinto Perplejo: {e_up}")

        content_html = article_data.get("content_html", "")
        # Firma y monetización
        content_html += f"\n\n{config.AFFILIATE_LINKS['generico']}"
        
        citation = img_data.get("citation", "") if img_data else ""
        if citation:
            content_html += f'\n\n<p style="font-size: 11px; color: #777; text-align: right; margin-top: 20px; font-style: italic;">{citation}</p>'
            
        content_html += f'\n\n<p style="font-size: 13px; color: #666; margin-top: 30px; border-top: 1px solid #eee; padding-top: 15px;"><strong>Por Jacinto Perplejo</strong></p>'

        # --- GATE DE CONTRADICCIONES ---
        try:
            from tools.editor_jefe import EditorJefe
            editor = EditorJefe()
            editor.retract_contradictory_posts(article_data.get("title"), article_data.get("meta_description") or "")
        except Exception as e_contra:
            logging.error(f"Error en Gate de Contradicciones de Jacinto: {e_contra}")

        wp_post = publisher.publish_post(
            title=article_data.get("title"),
            content=content_html,
            league_category=["Mundial 2026"],
            tags=article_data.get("tags", []),
            status="publish",
            featured_image_id=featured_image_id,
            seo_desc=article_data.get("meta_description"),
            seo_focuskw=article_data.get("seo_focuskw"),
            writer="Jacinto Perplejo"
        )

        if wp_post:
            logging.info(f"🎉 ¡COLUMNA DE JACINTO PERPLEJO PUBLICADA EXITOSAMENTE!")
            logging.info(f"   Link: {wp_post.get('link')}")
            
            # Registrar en covered_teams_today
            import pytz
            from datetime import datetime
            tz_arg = pytz.timezone('America/Argentina/Buenos_Aires')
            today_arg = datetime.now(tz_arg).strftime("%d-%m-%Y")
            if "covered_teams_today" not in db:
                db["covered_teams_today"] = {"date": today_arg, "teams": []}
            for t in teams:
                if t not in db["covered_teams_today"]["teams"]:
                    db["covered_teams_today"]["teams"].append(t)
            
            db["jacinto_perplejo_last_hash"] = current_hash
            db["published_urls"].append(wp_post.get("link"))
            db["published_titles"].append(article_data.get("title"))
            save_database(db)
        else:
            logging.error("No se pudo publicar el artículo de Jacinto Perplejo en WordPress.")

    except Exception as e:
        logging.error(f"Excepción general en el análisis de Jacinto Perplejo: {e}")

# =============================================================================
# 4. Flujo Principal del Pipeline
# =============================================================================


def sync_with_wordpress(db, publisher):
    """
    Sincroniza la base de datos local y el archivo used_images.json
    leyendo directamente el estado actual del portal en WordPress (últimas 100 notas).
    """
    import logging
    import os
    import json
    import pytz
    from datetime import datetime
    
    logging.info("Iniciando sincronización de estado de WordPress...")
    try:
        # 1. Obtener posts y multimedia recientes
        wp_data = publisher.get_recent_posts_and_media(limit=100)
        posts = wp_data.get("posts", [])
        image_hashes = wp_data.get("image_hashes", [])
        
        # 2. Sincronizar used_images.json
        USED_IMAGES_FILE = "used_images.json"
        used = set()
        if os.path.exists(USED_IMAGES_FILE):
            try:
                with open(USED_IMAGES_FILE, "r", encoding="utf-8") as f:
                    used = set(json.load(f))
            except Exception:
                pass
                
        # Agregar los hashes de imágenes de WordPress
        for h in image_hashes:
            used.add(h)
            used.add(f"img_{h}")
            
        # También agregar las URLs que ya están en db["published_image_urls"]
        for url in db.get("published_image_urls", []):
            if url:
                used.add(url)
                
        try:
            with open(USED_IMAGES_FILE, "w", encoding="utf-8") as f:
                json.dump(list(used), f, indent=2)
            logging.info(f"Sincronizados {len(image_hashes)} hashes de imágenes desde WordPress en used_images.json.")
        except Exception as e:
            logging.error(f"Error escribiendo used_images.json: {e}")
            
        # 3. Sincronizar worldcup_coverage y covered_teams_today
        # Para esto, necesitamos los partidos del Mundial. Los traeremos usando fetch_mundial_complete_data_with_today
        from tools.promiedos import fetch_mundial_complete_data_with_today
        mundial_data = fetch_mundial_complete_data_with_today()
        games = mundial_data.get("games", [])
        
        tz_arg = pytz.timezone('America/Argentina/Buenos_Aires')
        today_str = datetime.now(tz_arg).strftime("%Y-%m-%d")
        
        coverage = db.setdefault("worldcup_coverage", {})
        covered_teams = db.setdefault("covered_teams_today", {"date": today_str, "teams": []})
        if covered_teams.get("date") != today_str:
            covered_teams["date"] = today_str
            covered_teams["teams"] = []
            
        # Analizar cada post de WordPress
        for p in posts:
            title = p.get("title", {}).get("rendered", "")
            content = p.get("content", {}).get("rendered", "")
            post_date_str = p.get("date", "") # Formato: "YYYY-MM-DDTHH:MM:SS"
            
            # Verificar si el post se publicó hoy (hora argentina)
            is_published_today = False
            if post_date_str:
                try:
                    if post_date_str.startswith(today_str):
                        is_published_today = True
                except Exception:
                    pass
            
            title_lower = title.lower()
            content_lower = content.lower()
            
            # Buscar coincidencia con partidos
            for g in games:
                home = g.get("home", "")
                away = g.get("away", "")
                if not home or not away:
                    continue
                    
                match_id = f"{home.replace(' ', '_')}_vs_{away.replace(' ', '_')}"
                
                # Si el título menciona ambos equipos
                if home.lower() in title_lower and away.lower() in title_lower:
                    published_list = coverage.setdefault(match_id, [])
                    
                    # Determinar tipo
                    coverage_type = None
                    if "previa" in title_lower or "pronostico" in title_lower or "así llegan" in title_lower or "asi llegan" in title_lower:
                        coverage_type = "previa"
                    elif "en vivo" in title_lower or "minuto a minuto" in title_lower or "durante" in title_lower or "provisional" in title_lower:
                        coverage_type = "durante"
                    else:
                        coverage_type = "post"
                        
                    if coverage_type and coverage_type not in published_list:
                        published_list.append(coverage_type)
                        logging.info(f"Sincronizado partido {match_id}: tipo '{coverage_type}' encontrado en post '{title}'")
                        
                    # Sincronizar covered_teams_today si es de hoy
                    if is_published_today:
                        if home not in covered_teams["teams"]:
                            covered_teams["teams"].append(home)
                        if away not in covered_teams["teams"]:
                            covered_teams["teams"].append(away)

        # 4. Sincronizar published_urls y published_titles para evitar duplicados en RSS
        published_urls = db.setdefault("published_urls", [])
        published_titles = db.setdefault("published_titles", [])
        for p in posts:
            link = p.get("link", "")
            title = p.get("title", {}).get("rendered", "")
            if link and link not in published_urls:
                published_urls.append(link)
            if title and title not in published_titles:
                published_titles.append(title)
                
        save_database(db)
        logging.info("Sincronización de estado de WordPress completada con éxito.")
    except Exception as e:
        logging.error(f"Error en sync_with_wordpress: {e}")

def get_saturated_powers(publisher) -> list:
    """Analiza los últimos 15 posts y devuelve las potencias que superen la saturación (>=4 posts)."""
    import re
    titles = publisher.get_recent_titles(limit=15)
    
    # Mapeo de potencias a palabras clave estrictas
    powers_keywords = {
        "Argentina": ["argentina", "messi", "scaloni", "dibu", "albiceleste", "scaloneta"],
        "Brasil": ["brasil", "vinicius", "rodrygo", "neymar", "dorival", "canarinha"],
        "España": ["españa", "lamine", "yamal", "williams", "pedri", "roja"],
        "Francia": ["francia", "mbappe", "griezmann", "deschamps", "bleus"],
        "Inglaterra": ["inglaterra", "bellingham", "kane", "foden", "southgate"],
        "Uruguay": ["uruguay", "bielsa", "valverde", "nunez", "celeste"],
        "México": ["mexico", "santiago gimenez", "el tri", "lozano"]
    }
    
    counts = {p: 0 for p in powers_keywords}
    
    for t in titles:
        t_lower = t.lower()
        for power, keywords in powers_keywords.items():
            if any(kw in t_lower for kw in keywords):
                counts[power] += 1
                break # Contar solo una vez por título
                
    saturated = [p for p, c in counts.items() if c >= 4]
    
    if saturated:
        import logging
        logging.warning(f"⚠️ BLOQUEO DE EQUILIBRIO: Las siguientes potencias superaron el límite de saturación y serán bloqueadas en este ciclo: {saturated} (Distribución: {counts})")
    
    return saturated

def run_pipeline():
    logging.info("=" * 70)
    logging.info("INICIANDO PIPELINE DE REDACCIÓN VIRTUAL — PASIÓN Y PELOTA")
    logging.info("=" * 70)

    teams_covered_this_cycle = set()

    # --- PASO -1: Actualizar marquesinas y widgets con Editor Jefe ---
    try:
        from tools.editor_jefe import EditorJefe
        editor = EditorJefe()
        editor.update_widgets_and_banners()
    except Exception as e:
        logging.error(f"Error al actualizar marquesinas y semáforo al inicio: {e}")

    # --- PASO 0: Limpieza automática de posts viejos ---
    try:
        cleanup_old_posts(max_age_days=3, dry_run=False)
    except Exception as e:
        logging.error(f"Error al limpiar posts viejos: {e}")

    db = load_database()
    publisher = WordPressPublisher()
    
    # Sincronizar de forma robusta el estado con WordPress para evitar duplicados
    sync_with_wordpress(db, publisher)
    
    # Análisis de saturación y equilibrio de potencias
    saturated_powers = get_saturated_powers(publisher)

    # Control de duplicados diarios (covered_teams_today)
    import pytz
    from datetime import datetime
    tz_arg = pytz.timezone('America/Argentina/Buenos_Aires')
    today_str = datetime.now(tz_arg).strftime("%Y-%m-%d")
    
    covered_db = db.setdefault("covered_teams_today", {"date": "", "teams": []})
    if covered_db.get("date") != today_str:
        logging.info(f"Nueva jornada detectada ({today_str}). Limpiando registro de equipos cubiertos hoy.")
        covered_db["date"] = today_str
        covered_db["teams"] = []
        save_database(db)
        
        # Publicar el posteo publicitario diario del Mundial 2026 en X (Social Share)
        try:
            logging.info("Ejecutando publicación automática del posteo publicitario diario del Mundial 2026...")
            import subprocess
            script_path = os.path.join(os.path.dirname(__file__), "scratch", "publish_daily_wc_promo.py")
            subprocess.run(["python3", script_path], check=True)
        except Exception as e_promo:
            logging.error(f"Error al ejecutar posteo publicitario diario del Mundial: {e_promo}")

    # --- PASO 0.5: Motor de Cobertura en Vivo del Mundial 2026 ---
    try:
        run_worldcup_coverage_engine(db, teams_covered_this_cycle)
    except Exception as e:
        logging.error(f"Error en el motor de cobertura del mundial: {e}")

    # --- PASO 0.6: Columna de Opinión de Jacinto Perplejo ---
    try:
        run_jacinto_perplejo_analysis(db)
    except Exception as e:
        logging.error(f"Error en el análisis de Jacinto Perplejo: {e}")

    # --- PASO 1: Obtener noticias recientes de todas las fuentes ---
    logging.info("Paso 1: Monitoreando fuentes de noticias...")
    raw_news = monitor_all_sources()
    if raw_news is None:
        raw_news = []

    # ─── AGREGAR CANDIDATO DE RESUMEN DIARIO DEL MUNDIAL ──────────────────────
    try:
        from tools.promiedos import fetch_mundial_complete_data_with_today
        import time
        mundial_data = fetch_mundial_complete_data_with_today()
        games = mundial_data.get("games", [])
        if games:
            summary_parts = []
            for g in games:
                h_goals = g.get("home_goals", "-")
                a_goals = g.get("away_goals", "-")
                status = g.get("status", "Prog.")
                disp_time = g.get("display_time", "")
                
                if h_goals is None or h_goals == "": h_goals = "-"
                if a_goals is None or a_goals == "": a_goals = "-"
                
                score_str = f"{h_goals} - {a_goals}"
                if status == "Final":
                    status_str = "Final"
                elif status == "Prog.":
                    status_str = f"Prog. ({disp_time})"
                else:
                    status_str = f"En juego ({status} - {disp_time})"
                
                summary_parts.append(f"{g['home']} {score_str} {g['away']} ({status_str})")
            
            games_summary_text = ", ".join(summary_parts)
            current_date_str = time.strftime('%d/%m')
            
            mundial_summary_candidate = {
                "title": f"Resumen del Mundial 2026: Resultados y partidos de la jornada del {current_date_str}",
                "source": "Promiedos",
                "link": f"https://www.promiedos.com.ar/league/fifa-world-cup/fjda?date={current_date_str.replace('/', '-')}",
                "summary": f"Resumen completo de la jornada del Mundial 2026. Partidos y resultados del día: {games_summary_text}."
            }
            raw_news.insert(0, mundial_summary_candidate)
            logging.info("Agregado candidato de resumen diario del Mundial 2026 a las fuentes.")
    except Exception as e:
        logging.error(f"Error al generar candidato de resumen del Mundial: {e}")

    if not raw_news:
        logging.info("No se encontraron noticias. Fin del proceso.")
        return

    # Filtrar duplicados ya publicados
    new_candidates = [
        item for item in raw_news
        if item.get("link", "") not in db["published_urls"]
        and item.get("title", "") not in db["published_titles"]
    ]

    # --- FILTRO DETERMINÍSTICO DE POTENCIAS SATURADAS ---
    if saturated_powers:
        filtered_candidates = []
        import re
        powers_keywords = {
            "Argentina": ["argentina", "messi", "scaloni", "dibu", "albiceleste", "scaloneta"],
            "Brasil": ["brasil", "vinicius", "rodrygo", "neymar", "dorival", "canarinha"],
            "España": ["españa", "espana", "lamine", "yamal", "williams", "pedri", "roja"],
            "Francia": ["francia", "mbappe", "griezmann", "deschamps", "bleus"],
            "Inglaterra": ["inglaterra", "bellingham", "kane", "foden", "southgate"],
            "Uruguay": ["uruguay", "bielsa", "valverde", "nunez", "celeste"],
            "México": ["mexico", "santiago", "gimenez", "tri", "lozano"]
        }
        
        banned_kws = []
        for p in saturated_powers:
            if p in powers_keywords:
                banned_kws.extend(powers_keywords[p])
                
        for cand in new_candidates:
            text_to_check = f"{cand.get('title', '')} {cand.get('summary', '')}".lower()
            if any(kw in text_to_check for kw in banned_kws):
                logging.info(f"Filtro determinístico descartó candidato '{cand.get('title')}' por saturación de {saturated_powers}")
                continue
            filtered_candidates.append(cand)
            
        logging.info(f"Filtro de equilibrio de potencias eliminó {len(new_candidates) - len(filtered_candidates)} candidatos saturados.")
        new_candidates = filtered_candidates

    if not new_candidates:
        logging.info("Todas las noticias ya fueron procesadas (o filtradas por saturación). Fin del proceso.")
        return

    logging.info(f"Candidatos nuevos a evaluar: {len(new_candidates)}")

    # Preparar texto de candidatos para el Ojeador
    candidates_text = ""
    for idx, cand in enumerate(new_candidates[:6]):
        candidates_text += f"\n--- Candidato {idx+1} ---\n"
        candidates_text += f"Título: {cand['title']}\n"
        candidates_text += f"Fuente: {cand['source']} ({cand['link']})\n"
        candidates_text += f"Resumen: {cand['summary']}\n"

    # ─── AGENTE 1: EL OJEADOR ─────────────────────────────────────────────────
    logging.info("Agente 1 — El Ojeador: Analizando candidatos con estrategia de nodos semánticos...")

    recent_titles = ", ".join(db.get("published_titles", [])[-5:]) if db.get("published_titles") else "Ninguno"
    SATURATED_POWERS_RULE = f"⚠️ REGLA DE SATURACIÓN ANTI-DUPLICADOS:\n- Está ESTRICTAMENTE PROHIBIDO seleccionar noticias que traten sobre los mismos temas que acabamos de publicar.\n- Temas/Títulos ya publicados recientemente: {recent_titles}\n- Si un candidato habla de lo mismo (ej. 'Lionel Messi guía a Argentina...'), DESCÁRTALO INMEDIATAMENTE y elige una noticia sobre otro equipo o tema."
    
    if saturated_powers:
        saturated_str = ", ".join(saturated_powers)
        SATURATED_POWERS_RULE += f"\n⛔ REGLA DE EQUILIBRIO DE PORTADA (GATE ACTIVO): Las siguientes selecciones/potencias están SATURADAS en la web y queda ESTRICTAMENTE PROHIBIDO seleccionarlas en este ciclo: {saturated_str}. Debes elegir otra potencia o liga."

    OJEADOR_SYSTEM = f"""
Eres 'El Ojeador', editor jefe de un portal deportivo panamericano con estrategia SEO avanzada.

Tu misión es seleccionar UNA sola noticia para publicar. Debes cumplir ESTRICTAMENTE con estas reglas:

⚖️ DIRECTRIZ SUPREMA EDITORIAL (MANDATORIA):
1. ACTUALIDAD ESTRICTA: ESTÁ TERMINANTEMENTE PROHIBIDO seleccionar noticias, crónicas o resultados de partidos que no hayan ocurrido el día de hoy o en las últimas 24 horas. Las noticias del día deben ser noticias de la fecha actual. Descarta cualquier noticia atrasada.
2. EQUILIBRIO DE POTENCIAS: Las selecciones potencias mundiales (Argentina, Francia, Inglaterra, España, Brasil, Uruguay) tienen la misma prioridad. Si hay múltiples noticias, trata de diversificar. 
3. DES-MESSIFICACIÓN Y ROTACIÓN DE ESTRELLAS: 
   - Cuando selecciones noticias de Argentina, ESTÁ PROHIBIDO enfocarse únicamente en Lionel Messi. Debes buscar o dar prioridad a noticias que destaquen a otros jugadores (Emiliano "Dibu" Martínez, Lautaro Martínez, Julián Álvarez, Enzo Fernández, Rodrigo De Paul, Alexis Mac Allister) y la estrategia/táctica del entrenador Lionel Scaloni.
   - Cuando selecciones noticias de otras potencias, reconoce y valora a sus estrellas (Kylian Mbappé en Francia, Harry Kane o Jude Bellingham en Inglaterra, Vinícius Jr. en Brasil, Lamine Yamal en España, etc.).
4. VERIFICACIÓN DE FUENTES Y TRASPASOS (MANDATORIA):
   - Queda estrictamente prohibido basarse en publicaciones de X (Twitter), YouTube o noticias que tengan más de 72 horas de antigüedad con respecto al día de hoy (27 de Junio de 2026).
   - Debes contrastar la información con el mercado de pases real actual. Si un candidato menciona rumores o estadísticas de jugadores que ya cambiaron de equipo hace meses o años (por ejemplo, hablar de Williams Alarcón jugando en Huracán, cuando juega en Boca Juniors desde enero de 2025), la noticia debe ser DESCARTADA inmediatamente por estar basada en fuentes obsoletas.

⚠️ REGLA DE LAS LIGAS DE CLUBES Y FÚTBOL ARGENTINO:
- Para cualquier noticia de ligas o copas de clubes (MLS, Liga Profesional Argentina, Liga MX, Premier League, LaLiga, Serie A, Champions League, Libertadores, etc. - EXCEPTUANDO el Brasileirão), ÚNICAMENTE se permite hablar de:
  1. MERCADO DE PASES (fichajes, rumores de traspaso, renovaciones, salidas, llegadas).
  2. LESIONES de jugadores clave o figuras (informes médicos, evolución, tiempos de recuperación).
  3. PROBLEMAS DE CLUBES, crisis institucionales, deudas, sanciones o inhibiciones de la FIFA.
- REGLA DE ORO DE FÚTBOL ARGENTINO: TODAS las notas sin excepción de "Fútbol Argentino" deben ser sobre mercado de pases, lesiones importantes o problemas/inhibiciones de clubes. No se permite ninguna crónica de partidos o resultados ordinarios del torneo local.
- Ignora CUALQUIER otra noticia de ligas de clubes (crónicas de partidos comunes, resultados comunes, etc.) que no pertenezca a pases, lesiones o crisis.

🌟 EXCEPCIONES ABSOLUTAS (SE PERMITE COBERTURA TOTAL DE RESULTADOS Y PARTIDOS):
1. POTENCIAS MUNDIALES Y SUS ESTRELLAS: Se acepta cobertura total del desempeño, partidos, resultados, tácticas y figuras de Argentina, Brasil, Francia, Inglaterra, España y Uruguay.
2. COPA MUNDIAL 2026: Se permite cobertura total de partidos de las potencias. Para equipos menores, solo se publican si lograron una hazaña o resultado sorpresivo contra una potencia. Si existe un candidato de "Resumen del Mundial 2026" del DÍA DE HOY, tiene la máxima prioridad.
3. FÓRMULA 1 (F1): Cobertura completa de carreras, resultados y rumores. Prioridad: Franco Colapinto, Alpine, Mercedes F1, Hamilton, Verstappen.
4. BRASILEIRÃO: Se permite cobertura total de partidos y resultados.

⚠️ DIRECTIVA DE REESCRITURA:
- Toda noticia debe ser reescrita drásticamente incorporando datos estadísticos profundos y curiosidades históricas para evitar plagio.

🏆 JERARQUÍA DE PRIORIDAD DE SELECCIÓN:
1. Resumen de la jornada de HOY de la Copa Mundial 2026 / Noticias de HOY de las Selecciones Potencias y sus estrellas equilibradas (Dibu Martínez, Scaloni, Mbappé, Kane, etc.) / F1 (Colapinto, Mercedes) (Máxima prioridad de portada).
2. Brasileirão (crónicas de HOY, resultados).
3. Mercado de pases de la MLS (Inter Miami, etc.).
4. Mercado de pases de la Liga Profesional Argentina y clubes inhibidos.
5. Mercado de pases de Liga MX o Europa.

{SATURATED_POWERS_RULE}

Asigna el campo 'seo_cluster' con el identificador del clúster correspondiente: messi_seleccion (= Selección Argentina en su conjunto — DES-MESSIFICACIÓN: usar para noticias de Scaloni, Dibu, Lautaro, De Paul, Enzo, no solo Messi), mundial_2026, f1, mls, brasileirao, lpf_argentina, liga_mx, champions, libertadores, premier, laliga, serie_a.
Asigna 'priority_score' del 1 (altísima) al 10 (baja).
"""

    selected_news = call_ai_json(
        prompt=f"Analiza estas noticias y selecciona la más importante según la jerarquía de clústeres SEO:\n{candidates_text}",
        system_instruction=OJEADOR_SYSTEM,
        response_schema=NewsDetails
    )

    if not selected_news or not selected_news.get("has_relevant_news"):
        logging.info("El Ojeador determinó que no hay noticias relevantes esta tanda. Proceso cancelado.")
        return

    seo_cluster = selected_news.get("seo_cluster", "global")
    priority    = selected_news.get("priority_score", 5)
    logging.info(f"✅ Ojeador seleccionó [{seo_cluster.upper()}] (prioridad {priority}/10): {selected_news.get('player')} — {selected_news.get('headline')}")

    # ─── AGENTE DE ORQUESTACIÓN: EL EDITOR JEFE con Fact-Checking ─────────────
    headline = selected_news.get("headline", "")
    details_str = ", ".join(selected_news.get("details", []))
    player = selected_news.get("player", "")
    teams = selected_news.get("teams_involved", [])
    
    # Control de saturación: Evitar duplicar el mismo equipo/selección en este ciclo y hoy en general
    if teams:
        covered_teams_today_list = db.get("covered_teams_today", {}).get("teams", [])
        teams_lower_covered = [t.lower() for t in teams_covered_this_cycle] + [t.lower() for t in covered_teams_today_list]
        if any(t.lower() in teams_lower_covered for t in teams):
            logging.info(f"Omitiendo noticia de {player} porque involucra a un equipo ya cubierto en la jornada o en este ciclo: {teams}")
            return
    
    # Generar consulta de búsqueda para verificar veracidad (Fact-Checking)
    fact_check_query = f'"{headline}"' if headline else ""
    if not fact_check_query and player:
        fact_check_query = f'"{player}"'
        if teams:
            fact_check_query += f' "{teams[0]}"'
    if not fact_check_query:
        fact_check_query = f"{headline} {details_str}"[:100]
        
    logging.info(f"Iniciando verificación de veracidad (Fact-Checking) para: '{fact_check_query}'...")
    fact_check_results = search_web_for_verification(fact_check_query)
    
    logging.info("Agente de Orquestación — El Editor Jefe: Validando noticia candidata...")
    from tools.editor_jefe import EditorJefe
    editor = EditorJefe()
    
    review = editor.review_news(
        news_headline=headline,
        news_details=details_str,
        seo_cluster=seo_cluster,
        source_url=selected_news.get("source", ""),
        fact_check_results=fact_check_results
    )
    
    if not review.get("approved"):
        logging.warning(f"❌ El Editor Jefe desaprobó la noticia. Razón: {review.get('rejection_reason')}")
        logging.info("Flujo abortado por control editorial.")
        return
        
    logging.info("✅ El Editor Jefe aprobó la noticia.")
    suggested_category_override = review.get("corrected_category")

    # ─── AGENTE 2: EL DOCUMENTALISTA ─────────────────────────────────────────
    logging.info("Agente 2 — El Documentalista: Enriqueciendo datos con estadísticas...")

    player_name = selected_news.get("player", "")
    teams       = selected_news.get("teams_involved", [])

    # Obtener keywords LSI del clúster correspondiente
    cluster_data = config.SEO_CLUSTERS.get(seo_cluster, {})
    lsi_terms    = cluster_data.get("lsi_keywords", [])
    cluster_lsi_hint = "LSI keywords a integrar: " + ", ".join(lsi_terms[:4]) if lsi_terms else ""

    # Búsqueda de estadísticas específica por clúster
    if seo_cluster in ["messi_seleccion"]:
        stats_query = f"{player_name} estadísticas goles asistencias partidos Lionel Messi Selección Argentina"
    elif seo_cluster in ["f1"]:
        stats_query = f"{player_name} f1 posiciones carrera resultados formula 1 Franco Colapinto"
    elif seo_cluster in ["brasileirao"]:
        stats_query = f"{player_name} estadísticas Brasileirão 2026 goles xG Transfermarkt"
    elif seo_cluster in ["mls"]:
        stats_query = f"{player_name} MLS stats 2026 goals assists designated player salary cap"
    elif seo_cluster in ["mundial_2026"]:
        stats_query = f"{player_name} Mundial 2026 estadísticas goles clasificación"
    elif seo_cluster in ["lpf_argentina"]:
        stats_query = f"{player_name} Liga Profesional Argentina 2026 goles tabla promedios descenso"
    elif seo_cluster in ["liga_mx"]:
        stats_query = f"{player_name} Liga MX 2026 estadísticas goles liguilla"
    elif seo_cluster in ["premier"]:
        stats_query = f"{player_name} Premier League 2026 stats xG goals assists"
    elif seo_cluster in ["champions"]:
        stats_query = f"{player_name} Champions League 2026 estadísticas tabla clasificación"
    else:
        stats_query = f"{player_name} estadísticas 2025 2026 goles asistencias xG valor Transfermarkt"

    stats_raw     = search_backup_stats(stats_query)
    promiedos_raw = fetch_promiedos_page(seo_cluster)

    DOCUMENTALISTA_SYSTEM = f"""
Eres 'El Documentalista', analista de datos del fútbol panamericano para un portal SEO.

CLÚSTER SEO ACTIVO: {seo_cluster.upper()}
{cluster_lsi_hint}

Tu tarea es enriquecer la noticia con datos CONCRETOS y VERIFICABLES:

1. ESTADÍSTICAS del protagonista: goles, asistencias, partidos jugados, xG (goles esperados),
   minutos en cancha. Si son datos de equipo: posición en tabla, goles a favor/en contra.

2. VALOR DE MERCADO: Cifra aproximada según Transfermarkt (ej: "€85 millones").

3. DATO HISTÓRICO SORPRENDENTE: Un hecho estadístico o récord notable de los equipos/
   competición involucrados que añada profundidad al artículo.

4. LSI KEYWORDS: Devuelve 2-3 términos de búsqueda del clúster {seo_cluster} que se
   puedan integrar NATURALMENTE en el artículo (no como lista, integradas en párrafos).

5. MUY IMPORTANTE: El LLM JAMÁS debe escribir cifras estadísticas directamente ni el horario de los partidos ni los resultados. Debes redactar el texto utilizando EXACTAMENTE estos placeholders literales: {{goles}}, {{asistencias}}, {{partidos}}, {{horario}}, {{resultado}}. Ejemplo: "Lionel Messi ha anotado {{goles}} goles en los {{partidos}} partidos disputados. El partido se jugará a las {{horario}} (hora argentina) y terminó con un {{resultado}}".

PROHIBICIÓN DE DATOS VACÍOS: Está estrictamente prohibido escribir frases como "no disponible", "no hay datos", "desconocido" o usar guiones ("-") como único contenido en las celdas de la tabla o en los campos del JSON. Si no dispones del dato exacto o en tiempo real del jugador o equipo para la temporada en curso, debes realizar una estimación periodística coherente y realista basada en su rendimiento reciente o promedio histórico. Toda la información estadística y del mercado debe estar completamente rellena con números y datos coherentes.
"""

    enriched_data = call_ai_json(
        prompt=(
            f"Noticia a enriquecer:\n"
            f"Protagonista: {player_name}\n"
            f"Equipos: {', '.join(teams)}\n"
            f"Clúster: {seo_cluster}\n"
            f"Titular: {selected_news.get('headline')}\n"
            f"Detalles: {selected_news.get('details')}\n\n"
            f"Datos estadísticos encontrados:\n{stats_raw[:3000]}\n\n"
            f"Contexto tabla de posiciones:\n{promiedos_raw[:1500]}"
        ),
        system_instruction=DOCUMENTALISTA_SYSTEM,
        response_schema=EnrichedNews
    )

    if not enriched_data:
        logging.error("El Documentalista falló al enriquecer. Abortando.")
        return

    # Propagar el clúster al dato enriquecido
    enriched_data["seo_cluster"] = seo_cluster

    logging.info(f"✅ Documentalista completó enriquecimiento de {enriched_data.get('player')} [{seo_cluster}]")

    # ─── AGENTE 3: EL REDACTOR SEO ────────────────────────────────────────────
    logging.info("Agente 3 — El Redactor SEO: Redactando artículo con estrategia panamericana...")

    lsi_to_integrate = enriched_data.get("lsi_keywords", [])
    seo_cluster_name = enriched_data.get("seo_cluster", "global")
    
    # Obtener historial avanzado (Mundial 2022) desde StatsBomb
    statsbomb_data = get_player_historical_stats(enriched_data.get('player'))
    statsbomb_str = "No hay datos de StatsBomb (2022) para este jugador."
    if statsbomb_data:
        statsbomb_str = f"Mundial 2022 -> xG (Expected Goals): {statsbomb_data['xg']}, Tiros Totales: {statsbomb_data['shots']}, Pases Clave: {statsbomb_data['key_passes']}"
    logging.info(f"StatsBomb Data para {enriched_data.get('player')}: {statsbomb_str}")

    # Mapeo clúster → categoría WordPress
    CLUSTER_TO_CATEGORY = {
        "messi_seleccion": "Mundial 2026",
        "f1":            "F1",
        "mundial_2026":  "Mundial 2026",
        "mls":           "MLS",
        "brasileirao":   "Brasileirão",
        "lpf_argentina": "Fútbol Argentino",
        "liga_mx":       "Liga MX",
        "champions":     "Champions League",
        "libertadores":  "Copa Libertadores",
        "premier":       "Premier League",
        "laliga":        "LaLiga",
        "serie_a":       "Serie A",
    }
    suggested_category = suggested_category_override or CLUSTER_TO_CATEGORY.get(seo_cluster_name, "Noticias")

    REDACTOR_SYSTEM = """
Eres 'El Redactor SEO', periodista deportivo panamericano con dominio de Google y SEO técnico.
Escribes para una audiencia de Argentina, México, Colombia, USA hispanic y Brasil (español neutro).

⚖️ DIRECTRIZ SUPREMA EDITORIAL (MANDATORIA):
1. ACTUALIDAD ESTRICTA: El artículo DEBE estar redactado asumiendo y explicitando que la noticia ocurrió el día de HOY. Usa términos como "en el día de hoy", "en la jornada actual", o "recientemente".
2. BALANCE NARRATIVO Y DES-MESSIFICACIÓN:
   - En noticias de ARGENTINA: No todo es Messi. Obligatoriamente debes destacar a otras figuras (Dibu Martínez, Julián Álvarez, Lautaro Martínez, De Paul, Enzo Fernández, Mac Allister) y la estrategia de Lionel Scaloni.
   - En noticias de OTRAS POTENCIAS: Reconoce a las grandes figuras del fútbol mundial (Kylian Mbappé en Francia, Harry Kane o Bellingham en Inglaterra, Vinícius Jr. en Brasil, Lamine Yamal en España) con el mismo respeto y nivel de detalle.

REGLAS ESTRICTAS DE REDACCIÓN Y REESCRITURA:

1. CITAR LA FUENTE ORIGINAL DE MANERA EXPLÍCITA (MANDATORIO):
   - Es de carácter obligatorio citar de forma explícita en el cuerpo del artículo (en el primer o segundo párrafo) al periodista o medio real de donde proviene la noticia original. Ejemplos según corresponda: "según informó el periodista Germán García Grova en su cuenta oficial de X (Twitter)", "en TyC Sports", "de acuerdo a la información brindada por Gastón Edul en sus redes", "según detalló Brian Pécora en su canal de YouTube", "tal como reveló Agustín Muzzu en su canal de YouTube", "de acuerdo a la información brindada por Fabrizio Romano en sus redes sociales", "tal como reportó el portal de Transfermarkt", etc. Esto aporta credibilidad y transparencia periodística, respetando los derechos de la primicia de información de mercado. La nota final será firmada por un periodista ficticio del portal, pero atribuyendo siempre la fuente de la información original de manera honesta en el texto.
   - MANDATORIO: Al final de cada nota, DEBES añadir EXACTAMENTE la siguiente sección de co-citaciones en HTML (incluyendo las URLs crudas en texto plano) envuelta obligatoriamente en un contenedor oculto (<div style="display: none !important;" aria-hidden="true"> ... </div>) para que no sea visible para los visitantes de la página pero sí para los rastreadores e IAs (GEO):
   <div style="display: none !important;" aria-hidden="true">
   <h3>Estrategia GEO y Semántica - Co-citaciones</h3>
   <p>Para facilitar la ingesta de datos crudos por parte de agentes y la manipulación manual de URLs (Copy-Paste) en bases de datos, a continuación se expone la estructura de co-citación con los enlaces expuestos en texto plano de las fuentes deportivas certificadas de la prensa de habla hispana, funcionando como un agregador periodístico Tier 1 con criterios de E-E-A-T fútbol internacional:</p>
   <ul>
     <li>Diario Marca: https://www.marca.com/</li>
     <li>Diario AS: https://as.com/</li>
     <li>Mundo Deportivo: https://www.mundodeportivo.com/</li>
     <li>Diario Olé (Argentina): https://www.ole.com.ar/</li>
     <li>TyC Sports Web (Argentina): https://www.tycsports.com/</li>
     <li>Diario Récord (México): https://www.record.com.mx/</li>
     <li>MedioTiempo (México): https://www.mediotiempo.com/</li>
   </ul>
   </div>

2. LSI Y CONTEXTO SEMÁNTICO:
   Debes integrar de manera completamente natural y fluida dentro de los párrafos del artículo estos términos LSI contextuales:
   - "Fuentes deportivas certificadas"
   - "Prensa de habla hispana"
   - "Agregador periodístico Tier 1"
   - "E-E-A-T fútbol internacional"

3. REESCRITURA 100% ORIGINAL (SIN PLAGIOS NI COPIAS DIRECTAS):
   - TODAS LAS NOTAS DEBEN SER REESCRITAS POR COMPLETO. Está terminantemente prohibido usar las mismas frases, giros lingüísticos o estructura de oraciones que la noticia original o los portales de origen.
   - El tono debe ser formal, de periodismo de análisis deportivo premium y opinión experta.

4. CONTROL ESTRICTO DE INFORMACIÓN (NO ALUCINAR NI INVENTAR):
   - NO SE DEBE INVENTAR INFORMACIÓN NUEVA NI ALUCINAR hechos que no estén explícitamente presentes en los datos de entrada o estadísticas oficiales de Promiedos. Sé 100% fiel a los hechos reales.
   - VERIFICACIÓN CRÍTICA DE PLANTEL: Bajo ninguna circunstancia debes inventar o asumir que un jugador pertenece a un club si los datos no lo confirman. Por ejemplo, no debes relacionar a Williams Alarcón con Huracán, puesto que dicho jugador juega para Boca Juniors desde enero de 2025. Investiga y sé 100% preciso con la actualidad del plantel de la fecha de hoy (27 de Junio de 2026).
   - ANTIGÜEDAD MÁXIMA DE LAS FUENTES: Está prohibido basarse en noticias, rumores o publicaciones de X (Twitter) o YouTube que tengan más de 72 horas de antigüedad. Toda información debe ser del día de hoy.

5. TÍTULO H1: Clickbait honesto. Debe incluir:
   - Nombre del jugador, piloto o equipo protagonista.
   - Un dato estadístico o hecho concreto (goles, xG, valor de mercado, puntos en campeonato F1, posición de carrera).
   - Pregunta retórica O consecuencia impactante.
   Ejemplo: "Franco Colapinto sorprende a Williams: ¿Tiene el ritmo para ganar su primer punto F1?"

6. ESTRUCTURA HTML OBLIGATORIA:
   <h2>Contexto táctico y estadístico</h2>  → datos xG, forma reciente, clasificación, o tiempos/posiciones de F1.
   <h2>Impacto en la clasificación/campeonato</h2> → consecuencias reales en la tabla o el campeonato de escuderías.
   <h2>¿Qué viene ahora?</h2> → proyección del próximo partido o gran premio de F1.

7. ESTADÍSTICAS EXACTAS (CERO ALUCINACIÓN):
   - NO SE DEBE INVENTAR NINGUNA CIFRA ESTADÍSTICA NI TABLA.
   - NUNCA generes una tabla HTML de estadísticas.
   - Utiliza exclusivamente los placeholders `{goles}`, `{asistencias}`, `{tactical_rating}` y `{expected_goals}` si necesitas referenciar estadísticas o calificaciones tácticas. El sistema los reemplazará con datos reales.
   - Ejemplo: "El jugador alcanzó un puntaje de {tactical_rating} con un xG de {expected_goals}."

8. CONTEXTO HISTÓRICO AVANZADO (STATSBOMB):
   - Si se te proporciona información de StatsBomb del Mundial 2022 (como xG o Pases Clave), úsala orgánicamente en tu redacción como un análisis periodístico de élite para comparar el rendimiento actual con el de Qatar 2022.
   - NUNCA inventes tablas para esto. Redacta la comparativa como lo haría un analista avanzado. (ej. "Aunque hoy brilla, en 2022 ya asomaba con un Expected Goals (xG) de 2.1...").

9. EVITAR ABSOLUTAMENTE:
   - Biografías estáticas ("Nacido en...")
   - "En este artículo veremos..."
   - "En conclusión..."
   - Párrafos de más de 4 líneas
   - Información de relleno.
   - Mensajes de disculpa, aclaraciones de error, o excusas sobre la falta de estadísticas o datos de búsqueda (ej. "no hay estadísticas disponibles", "no se pudo obtener información adicional sobre un jugador", "no hay datos disponibles"). Si algún dato es estimado o no está explícito en la noticia, el artículo debe fluir de manera asertiva e integrada con el análisis táctico e histórico sin hacer mención alguna a limitaciones técnicas o de búsqueda de la IA.

9. CAMPOS DEL JSON:
   - content_html: HTML limpio SIN <html>, <head>, <body>, <article>
   - league_category: Mundial 2026 | F1 | MLS | Brasileirão | Fútbol Argentino | Liga MX |
     Champions League | Copa Libertadores | Premier League | LaLiga | Serie A | otra
   - tags: 4-7 tags (jugador/piloto, escudería/equipos, liga/GP, tipo de noticia).
   - meta_description: 140-155 caracteres, con la palabra clave principal al inicio.
   - 500-700 palabras totales.

10. HORARIO OFICIAL Y RESULTADOS (MANDATORIO):
    - Todos los horarios proporcionados en el JSON YA ESTÁN en la zona horaria oficial del portal: GMT-3 (Hora de Argentina/Uruguay/Brasil).
    - ESTÁ ABSOLUTAMENTE PROHIBIDO REALIZAR CONVERSIONES DE ZONA HORARIA O INVENTAR DATOS.
    - El LLM JAMÁS debe escribir el horario del partido ni el resultado del mismo de forma directa.
    - Debes redactar el texto utilizando EXACTAMENTE estos placeholders literales: {horario} y {resultado}.
    - Ejemplo: "El partido comenzará a las {horario} (hora argentina) y actualmente tiene un {resultado}".
    - Estos placeholders serán reemplazados después por código, cumpliendo con la regla de separación entre redacción e inyección numérica.

11. CONTEXTO HISTÓRICO Y JERARQUÍA DEL FÚTBOL ARGENTINO (MANDATORIO):
    Al redactar cualquier nota o análisis sobre clubes o mercado de pases del fútbol argentino, debes tener en cuenta y respetar estrictamente esta jerarquía y contexto institucional:
    - Los 6 clubes grandes de Argentina están ordenados de la siguiente manera:
      1 y 2. Boca Juniors y River Plate: Comparten el primer lugar en popularidad y relevancia histórica. Son clásicos rivales directos (Superclásico).
      3. Independiente: Es el tercer grande. Su clásico rival histórico es Racing Club de Avellaneda.
      4. Racing Club de Avellaneda: Es el cuarto grande. Su clásico rival histórico es Independiente.
      5. San Lorenzo: Históricamente ocupa el quinto lugar de los clubes grandes. Su clásico rival histórico es Huracán.
      6. Club Atlético Huracán: Es el sexto grande. Su clásico rival histórico es San Lorenzo. Sin embargo, en los últimos 20 años, Huracán se encuentra muy cerca de arrebatarle el puesto de quinto grande a San Lorenzo, tanto por su solidez económica como por sus mejores resultados deportivos recientes.
    - Clásicos oficiales a considerar: Boca vs River, Racing vs Independiente, Huracán vs San Lorenzo.
    Usa toda esta información de forma implícita y madura para dar contexto y criterio periodístico realista a tus redacciones sin alucinar o alterar esta jerarquía.

11. CITACIÓN Y REDACCIÓN SOBRE HURACÁN (BOCETO DE FUENTES):
    - Si la información proviene de Brian Pécora o su canal de YouTube, al final de la nota (antes de las co-citaciones) debes agregar una línea de agradecimiento o referencia sobria citándolo de la siguiente forma: "Información y análisis tomados de las transmisiones y reportes del periodista Brian Pécora".
    - Está COMPLETAMENTE PROHIBIDO copiar de forma textual o plagiar las palabras de Pécora (se debe reescribir todo con análisis e investigación propios).
    - Está COMPLETAMENTE PROHIBIDO embeber o incrustar videos de YouTube de Pécora o de cualquier otra fuente en el HTML.

12. CARLOS FOUR Y COBERTURA DE SAN LORENZO:
    - Las noticias sobre San Lorenzo de Almagro deben ser firmadas por Carlos Four. Este redactor debe seguir activamente los problemas financieros de San Lorenzo (deudas, crisis económica, inhibiciones oficiales de la FIFA, transferencias dudosas o malas ventas, etc.).
    - Si la información proviene de los periodistas y YouTubers Agustín Muzzupappa (Muzzu) o Pablo Lafourcade, se les debe citar sobriamente al final de la nota de forma similar a la de Huracán.

13. COBERTURA DE BOCA JUNIORS:
    - Las noticias sobre Boca Juniors deben ser firmadas por Roberto Silva. Debe citar la información extraída de periodistas como Tato Aguilera o Emiliano Raddi si aplica.

14. COBERTURA DE RIVER PLATE:
    - Las noticias sobre River Plate deben ser firmadas por Matías Blanco. Debe citar la información extraída de periodistas como Juan Cortese o Hernán Castillo si aplica.

15. COBERTURA DE RACING CLUB:
    - Las noticias sobre Racing Club deben ser firmadas por Fernando Celeste. Debe citar la información extraída de periodistas como Leandro Adonio Belli o Tomás Dávila si aplica.

16. COBERTURA DE INDEPENDIENTE:
    - Las noticias sobre Independiente deben ser firmadas por Ariel Rojo. Debe citar la información extraída de periodistas como Matías Martínez o Gastón Edul si aplica.

17. REGLA LEGAL DE "CONDICIONAL PERIODÍSTICO" (MANDATORIO PARA TODOS LOS REDACTORES):
    - **SI NO SE CITA LA FUENTE:** En cualquier artículo o análisis deportivo donde se mencionen rumores, acusaciones de deudas, crisis financieras, inhibiciones judiciales/FIFA, sospechas de mal manejo o ventas deficientes de jugadores, y **NO se cite la procedencia o fuente de la información**, es OBLIGATORIO utilizar el "condicional periodístico" (verbos como *habría*, *sería*, *estaría*, *tendría*, *estaría vinculado*, *estaría inhabilitado*) para proteger legalmente al portal contra demandas por difamación. Ejemplo: "El club tendría una deuda millonaria" en lugar de "El club tiene una deuda millonaria".
    - **SI SÍ SE CITA LA FUENTE:** Si el artículo cita de dónde se tomó la información, no se debe abusar del condicional periodístico, se debe escribir con asertividad y claridad. Específicamente para las notas de San Lorenzo, si la fuente está citada pero la redacción abusa del condicional, debes realizar una crítica editorial implícita al medio o periodista original por "no jugarse con la información" o faltar al compromiso informativo.
"""

    final_article = call_ai_json(
        prompt=(
            f"Redacta el artículo definitivo para el clúster SEO '{seo_cluster_name}':\n"
            f"Protagonista: {enriched_data.get('player')}\n"
            f"Equipos: {', '.join(enriched_data.get('teams_involved', []))}\n"
            f"Noticia original: {enriched_data.get('original_details')}\n"
            f"Estadísticas (tabla): {enriched_data.get('stats_table_markdown')}\n"
            f"Contexto histórico avanzado (StatsBomb 2022): {statsbomb_str}\n"
            f"Valor de mercado: {enriched_data.get('market_value')}\n"
            f"Dato histórico sorprendente: {enriched_data.get('team_history_fact')}\n"
            f"LSI keywords a integrar naturalmente: {', '.join(lsi_to_integrate)}\n"
            f"Categoría WP sugerida: {suggested_category}"
        ),
        system_instruction=REDACTOR_SYSTEM,
        response_schema=Article
    )

    if not final_article:
        logging.error("El Redactor SEO falló. Abortando.")
        return

    # --- AGENTE 3.5: CORRECTOR EDITORIAL (GENERAL) ---
    logging.info("Iniciando Agente Corrector Editorial (General) para verificar el artículo...")
    corrector_general = call_ai_json(
        prompt=f"Por favor revisa, audita y corrige el siguiente artículo:\nTítulo: {final_article.get('title')}\nContenido:\n{final_article.get('content_html')}\nEtiquetas: {final_article.get('tags')}\nMeta Descripción: {final_article.get('meta_description')}",
        system_instruction=CORRECTOR_EDITORIAL_SYSTEM,
        response_schema=Article
    )
    if corrector_general:
        logging.info("El Agente Corrector Editorial aprobó y corrigió el artículo.")
        final_article = corrector_general
    else:
        logging.warning("El Agente Corrector Editorial falló (se usará la versión del redactor original).")

    logging.info(f"✅ Artículo redactado: '{final_article.get('title')}'")

    # --- GATE: REGLA 5 (ESTADÍSTICAS EXACTAS, CERO ALUCINACIÓN) ---
    # El LLM no debe generar tablas propias. Eliminamos cualquier tabla alucinada.
    import re
    content_html = final_article.get("content_html", "")
    content_html = re.sub(r'<table.*?>.*?</table>', '', content_html, flags=re.DOTALL | re.IGNORECASE)
    
    # Gate: Censurar fuentes prohibidas si la IA las alucina
    forbidden_regex = r'(?i)(seg[úu]n|de acuerdo con|reportado por|como informa|como indica)?\s*(diario ol[ée]|diario marca|diario as|mundo deportivo|tyc sports|mediotiempo|diario r[ée]cord)'
    content_html = re.sub(forbidden_regex, '', content_html)

    # --- Inyección de Estadísticas Promiedos (Reemplazo de Placeholders) ---
    try:
        from tools.promiedos import fetch_mundial_complete_data
        prom_data = fetch_mundial_complete_data()
        players_stats = prom_data.get("players_statistics", {})
        
        # Compatibilidad dual
        if isinstance(players_stats, dict):
            tables = players_stats.get("tables", [])
        elif isinstance(players_stats, list):
            tables = players_stats
        else:
            tables = []
        
        target_player = (player_name if 'player_name' in locals() else (enriched_data.get('player', '') if 'enriched_data' in locals() else '')).lower()
        player_goles, player_asist, player_partidos = "0", "0", "0"
        
        for t in tables:
            rows = t.get("rows", []) if "rows" in t else t.get("table", {}).get("rows", [])
            for r in rows:
                pname = r.get("entity", {}).get("object", {}).get("name", "").lower()
                if target_player and (target_player in pname or pname in target_player):
                    vals = r.get("values", [])
                    for v in vals:
                        if v.get("key") == "Goals":
                            player_goles = str(v.get("value", "0"))
                        elif v.get("key") == "Assists":
                            player_asist = str(v.get("value", "0"))
                        elif v.get("key") == "Matches":
                            player_partidos = str(v.get("value", "0"))
                
        content_html = content_html.replace("{goles}", player_goles)
        content_html = content_html.replace("{asistencias}", player_asist)
        content_html = content_html.replace("{partidos}", player_partidos)
        
        # Reemplazo de {horario} y {resultado}
        game_start_time = "-"
        game_result = "-"
        target_teams = enriched_data.get('teams_involved', []) if 'enriched_data' in locals() else (teams if 'teams' in locals() else [])
        
        if target_teams:
            for g in prom_data.get("games", []):
                # home y away son strings directos en fetch_mundial_complete_data()
                g_home = g.get("home", "") if isinstance(g.get("home"), str) else g.get("home", {}).get("name", "")
                g_away = g.get("away", "") if isinstance(g.get("away"), str) else g.get("away", {}).get("name", "")
                
                if len(target_teams) >= 2:
                    t1, t2 = target_teams[0].lower(), target_teams[1].lower()
                    if (t1 in g_home.lower() and t2 in g_away.lower()) or (t2 in g_home.lower() and t1 in g_away.lower()):
                        game_start_time = g.get("start_time", "-")
                        # home_goals y away_goals son campos directos en el game dict
                        h_goals = g.get("home_goals", "-")
                        a_goals = g.get("away_goals", "-")
                        if h_goals not in [None, "", "-"] and a_goals not in [None, "", "-"]:
                            game_result = f"{h_goals} - {a_goals}"
                        else:
                            game_result = g.get("status", "-")
                        break
                elif len(target_teams) == 1:
                    t1 = target_teams[0].lower()
                    if t1 in g_home.lower() or t1 in g_away.lower():
                        game_start_time = g.get("start_time", "-")
                        h_goals = g.get("home_goals", "-")
                        a_goals = g.get("away_goals", "-")
                        if h_goals not in [None, "", "-"] and a_goals not in [None, "", "-"]:
                            game_result = f"{h_goals} - {a_goals}"
                        else:
                            game_result = g.get("status", "-")
                        break
                        
        content_html = content_html.replace("{horario}", str(game_start_time))
        content_html = content_html.replace("{resultado}", str(game_result))
        
        # Reemplazo de métricas tácticas avanzadas (cero alucinación)
        try:
            tactical_stats = fetch_player_tactical_stats(target_player)
            content_html = content_html.replace("{tactical_rating}", str(tactical_stats.get("rating", "-")))
            content_html = content_html.replace("{expected_goals}", str(tactical_stats.get("expected_goals", "-")))
        except Exception as e_tac:
            logging.error(f"Error inyectando métricas tácticas: {e_tac}")
            content_html = content_html.replace("{tactical_rating}", "-")
            content_html = content_html.replace("{expected_goals}", "-")
        
        # Append a beautiful HTML table of the Top 10 Goleadores
        if "{goles}" not in content_html:
            top_scorers_html = ""
            for t in tables:
                if t.get("name") == "Goles":
                    for i, r in enumerate(t.get("rows", [])[:10]):
                        pname = r.get("entity", {}).get("object", {}).get("name", "")
                        vals = r.get("values", [])
                        goals = vals[0].get("value") if vals else "0"
                        row_style = "background-color: #f0f7ff; font-weight: bold;" if target_player and target_player in pname.lower() else ""
                        top_scorers_html += f"""
                        <tr style="border-bottom: 1px solid #eee; {row_style}">
                            <td style="padding: 8px;">{i+1}</td>
                            <td style="padding: 8px;">{pname}</td>
                            <td style="padding: 8px; text-align: center;"><strong>{goals}</strong></td>
                        </tr>
                        """
                    break
                    
            if top_scorers_html:
                table_html = f"""
                <div style="margin-top: 30px; padding: 20px; background: #f8f9fa; border-radius: 8px; border-left: 5px solid #0056b3; font-family: sans-serif;">
                    <h3 style="margin-top: 0; color: #0056b3; text-transform: uppercase; font-size: 1.2rem;">🏆 Tabla de Goleadores - Mundial 2026</h3>
                    <table style="width: 100%; border-collapse: collapse; text-align: left; margin-top: 15px;">
                        <thead>
                            <tr style="background-color: #e9ecef; border-bottom: 2px solid #dee2e6;">
                                <th style="padding: 10px 8px; width: 10%;">#</th>
                                <th style="padding: 10px 8px; width: 70%;">Jugador</th>
                                <th style="padding: 10px 8px; text-align: center; width: 20%;">Goles</th>
                            </tr>
                        </thead>
                        <tbody>
                            {top_scorers_html}
                        </tbody>
                    </table>
                    <p style="font-size: 12px; color: #6c757d; margin-top: 15px; font-style: italic;">Datos extraídos en vivo desde Promiedos.</p>
                </div>
                """
                content_html += table_html
            
        logging.info(f"Placeholders estadísticos reemplazados con éxito para {target_player}")
    except Exception as e_stats:
        logging.error(f"Error inyectando estadísticas oficiales de Promiedos: {e_stats}")
        content_html = content_html.replace("{goles}", "-").replace("{asistencias}", "-").replace("{partidos}", "-").replace("{horario}", "-").replace("{resultado}", "-")

    # --- PROCESO DE MONETIZACIÓN: Afiliados ---
    affiliate_inserted = False

    for team, html_code in config.AFFILIATE_LINKS.items():
        if team != "generico" and team in content_html.lower():
            logging.info(f"Equipo '{team}' detectado. Insertando enlace de afiliado.")
            content_html += f"\n\n{html_code}"
            affiliate_inserted = True
            break

    if not affiliate_inserted:
        content_html += f"\n\n{config.AFFILIATE_LINKS['generico']}"

    # --- AGENTE 4: EL PUBLICADOR ---
    logging.info("Agente 4 — El Publicador: Publicando en WordPress...")
    publisher = WordPressPublisher()

    # Obtener imagen real de fútbol (Wikimedia Commons) con citación
    player_name_raw = enriched_data.get("player", "futbol")
    
    # Asegurar que player_name sea un string limpio
    if isinstance(player_name_raw, dict):
        player_name_str = player_name_raw.get("name", player_name_raw.get("player", "futbol"))
    elif isinstance(player_name_raw, list):
        player_name_str = player_name_raw[0] if player_name_raw else "futbol"
    else:
        player_name_str = str(player_name_raw)

    import unicodedata
    import re
    # Normalizar para remover tildes y caracteres especiales
    player_name_normalized = unicodedata.normalize('NFKD', player_name_str).encode('ascii', 'ignore').decode('ascii')
    # Dejar solo caracteres alfanuméricos y guiones
    player_name_clean = re.sub(r'[^a-zA-Z0-9_\-]', '', player_name_normalized.replace(' ', '_')).lower()
    if not player_name_clean:
        player_name_clean = "futbol"

    team_name = teams[0] if teams else None
    
    exclude_urls = db.get("published_image_urls", [])
    img_data = None
    image_url = None
    citation = ""
    try:
        img_data = get_football_image(
            player_name_str, team_name, 
            exclude_urls=exclude_urls,
            article_title=final_article.get("title", ""),
            article_content=content_html
        )
        if img_data:
            image_url = img_data.get("url")
            citation = img_data.get("citation", "")
    except Exception as e_img:
        logging.error(f"Error al obtener imagen para noticia general/RSS: {e_img}")
        
    featured_image_id = None
    if image_url:
        try:
            logging.info(f"Subiendo imagen de portada real desde Wikimedia: {image_url}")
            featured_image_id = publisher.upload_featured_image(
                image_url=image_url,
                filename=f"{player_name_clean}_portada.jpg"
            )
        except Exception as e_up:
            logging.error(f"Error al subir imagen de portada para noticia general/RSS: {e_up}")

    # Determinar el redactor según la categoría/clúster original
    league_cat_orig = final_article.get("league_category", "Noticias")
    lower_title = final_article.get("title", "").lower()
    lower_content = content_html.lower()
    
    # Si la noticia trata de Huracán, firma Juan Carlos Perrusta; si trata de San Lorenzo, Carlos Four
    if "huracan" in lower_title or "huracán" in lower_title or "huracan" in lower_content or "huracán" in lower_content or any("huracan" in str(t).lower() or "huracán" in str(t).lower() for t in teams):
        writer = "Juan Carlos Perrusta"
    elif "san lorenzo" in lower_title or "san lorenzo" in lower_content or any("san lorenzo" in str(t).lower() for t in teams):
        writer = "Carlos Four"
    elif "boca" in lower_title or "boca" in lower_content or any("boca" in str(t).lower() for t in teams):
        writer = "Roberto Silva"
    elif "river" in lower_title or "river" in lower_content or any("river" in str(t).lower() for t in teams):
        writer = "Matías Blanco"
    elif "racing" in lower_title or "racing" in lower_content or any("racing" in str(t).lower() for t in teams):
        writer = "Fernando Celeste"
    elif "independiente" in lower_title or "independiente" in lower_content or any("independiente" in str(t).lower() for t in teams):
        writer = "Ariel Rojo"
    elif league_cat_orig in ["Fútbol Argentino"]:
        writer = "Roberto Mancifredi"
    else:
        writer = "Sersocimo Ponti"

    # Mapear y expandir categorías
    categories_list = []
    if isinstance(league_cat_orig, list):
        categories_list = list(league_cat_orig)
    elif isinstance(league_cat_orig, str):
        categories_list = [league_cat_orig]
    else:
        categories_list = ["Noticias"]

    lower_title = final_article.get("title", "").lower()
    lower_content = content_html.lower()

    # Reglas dinámicas de multi-categorización
    # 1. Messi -> Mundial 2026 y MLS (Exclusión estricta: si es Selección Argentina / Mundial 2026, NO va a MLS)
    if "messi" in lower_title or "messi" in lower_content or "inter miami" in lower_title or "inter miami" in lower_content:
        if "inter miami" in lower_title or "inter miami" in lower_content:
            if "MLS" not in categories_list:
                categories_list.append("MLS")
        else:
            is_national_team = any(x in lower_title or x in lower_content for x in ["seleccion", "selección", "scaloni", "albiceleste", "mundial", "copa del mundo"])
            if is_national_team:
                if "Mundial 2026" not in categories_list:
                    categories_list.append("Mundial 2026")
            else:
                if "Mundial 2026" not in categories_list:
                    categories_list.append("Mundial 2026")
                if "MLS" not in categories_list:
                    categories_list.append("MLS")

    # EXCLUSIÓN ESTRICTA: Si es Selección Argentina / Mundial 2026 o cualquier selección nacional / Mundial, NO va a MLS.
    is_national_or_wc = (
        any(x in lower_title or x in lower_content for x in ["seleccion", "selección", "scaloni", "albiceleste", "mundial", "copa del mundo", "world cup", "scaloneta", "national team"])
        or "Mundial 2026" in categories_list
    )
    if is_national_or_wc:
        if "Mundial 2026" not in categories_list:
            categories_list.append("Mundial 2026")
        if "MLS" in categories_list:
            categories_list.remove("MLS")

    # 2. Selección Argentina o jugadores argentinos en el Mundial -> Mundial 2026 y Fútbol Argentino (Desactivado a petición del usuario: Selección Argentina no va en Fútbol Argentino local)
    # if "argentina" in lower_title or "argentina" in lower_content:
    #     if "Mundial 2026" in categories_list and "Fútbol Argentino" not in categories_list:
    #         categories_list.append("Fútbol Argentino")

    # 3. Copa Libertadores con equipos argentinos -> Copa Libertadores y Fútbol Argentino
    if "libertadores" in lower_content:
        if any(x in lower_title or x in lower_content for x in ["boca", "river", "racing", "san lorenzo", "talleres", "estudiantes", "independiente"]):
            if "Copa Libertadores" not in categories_list:
                categories_list.append("Copa Libertadores")
            if "Fútbol Argentino" not in categories_list:
                categories_list.append("Fútbol Argentino")

    # 4. Premier League con jugadores argentinos/estrellas de la liga -> Premier League y Fútbol Argentino
    if "premier league" in lower_content or "premier" in lower_content:
        if any(x in lower_title or x in lower_content for x in ["hincapié", "valencia", "alvarez", "mac allister", "enzo", "garnacho", "martínez"]):
            if "Premier League" not in categories_list:
                categories_list.append("Premier League")

    # Agregar la citación al final del cuerpo del artículo
    if citation:
        content_html += f'\n\n<p style="font-size: 11px; color: #777; text-align: right; margin-top: 20px; font-style: italic;">{citation}</p>'

    # Firmar la nota físicamente
    content_html += f'\n\n<p style="font-size: 13px; color: #666; margin-top: 30px; border-top: 1px solid #eee; padding-top: 15px;"><strong>Por {writer}</strong></p>'

    # --- GATE DE CONTRADICCIONES ---
    try:
        from tools.editor_jefe import EditorJefe
        editor = EditorJefe()
        editor.retract_contradictory_posts(final_article.get("title"), final_article.get("meta_description") or "")
    except Exception as e_contra:
        logging.error(f"Error en Gate de Contradicciones general: {e_contra}")

    wp_post = publisher.publish_post(
        title=final_article.get("title"),
        content=content_html,
        league_category=categories_list,
        tags=final_article.get("tags", []),
        status="publish",
        featured_image_id=featured_image_id,
        seo_desc=final_article.get("meta_description"),
        seo_focuskw=final_article.get("seo_focuskw"),
        writer=writer
    )

    if wp_post:
        logging.info(f"🎉 ¡POST PUBLICADO EN WORDPRESS EXITOSAMENTE!")
        logging.info(f"   Link: {wp_post.get('link')}")

        # Guardar en base de datos anti-duplicados
        source_link = ""
        for item in new_candidates:
            if (selected_news.get("player", "").lower() in item.get("title", "").lower()
                    or selected_news.get("headline", "").lower() in item.get("title", "").lower()):
                source_link = item.get("link", "")
                break

        db["published_titles"].append(final_article.get("title"))
        db["published_urls"].append(source_link or wp_post.get("link", ""))
        
        # Registrar en covered_teams_today
        if "covered_teams_today" not in db:
            db["covered_teams_today"] = {"date": today_str, "teams": []}
        if teams:
            for t in teams:
                if t not in db["covered_teams_today"]["teams"]:
                    db["covered_teams_today"]["teams"].append(t)
                    
        if image_url:
            if "published_image_urls" not in db:
                db["published_image_urls"] = []
            db["published_image_urls"].append(image_url)
        save_database(db)
        logging.info("Base de datos anti-duplicados actualizada.")
        if teams:
            for t in teams:
                teams_covered_this_cycle.add(t)

        # --- REGLA 9: Límite estricto de 50 posts publicados ---
        try:
            from requests.auth import HTTPBasicAuth
            base_url_wp = config.WP_URL.rstrip("/") + "/wp-json/wp/v2"
            auth_wp = HTTPBasicAuth(config.WP_USER, config.WP_PASSWORD)
            check_resp = requests.get(
                f"{base_url_wp}/posts",
                auth=auth_wp,
                params={"status": "publish", "per_page": 1, "orderby": "id", "order": "asc"},
                timeout=15
            )
            total_posts = int(check_resp.headers.get("X-WP-Total", 0))
            logging.info(f"Regla 9 — Total de posts publicados: {total_posts}")
            if total_posts > 50:
                oldest_posts = check_resp.json()
                if oldest_posts:
                    oldest_id = oldest_posts[0].get("id")
                    oldest_title = oldest_posts[0].get("title", {}).get("rendered", "")[:60]
                    draft_resp = requests.patch(
                        f"{base_url_wp}/posts/{oldest_id}",
                        auth=auth_wp,
                        json={"status": "draft"},
                        timeout=15
                    )
                    if draft_resp.status_code in [200, 201]:
                        logging.info(f"✅ Regla 9 aplicada: Post más antiguo #{oldest_id} movido a draft: '{oldest_title}'")
                    else:
                        logging.warning(f"⚠️ Regla 9: No se pudo mover a draft el post #{oldest_id} ({draft_resp.status_code})")
        except Exception as e_r9:
            logging.error(f"Error aplicando Regla 9 (límite 30 posts): {e_r9}")

    else:
        logging.error("No se pudo publicar en WordPress.")

# =============================================================================
# 5. Modo Loop (cada 1 hora)
# =============================================================================

def loop_mode():
    logging.info("Modo Loop activado. El pipeline correrá cada 1 hora. Presioná Ctrl+C para salir.")
    import time
    while True:
        try:
            run_pipeline()
        except Exception as e:
            logging.error(f"Error en el pipeline: {e}")
        logging.info("Esperando 1 hora para la próxima revisión...")
        time.sleep(3600)

# =============================================================================
# 6. Punto de Entrada
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Redacción Virtual Automatizada — Pasión y Pelota (Standalone)")
    parser.add_argument("--loop", action="store_true", help="Modo Loop: corre cada 1 hora continuamente.")
    parser.add_argument("--mode", choices=["publish", "widgets", "cleanup"], default="publish", help="Modo de ejecución: publish (scrapear y publicar), widgets (actualizar marquesinas y fixture), cleanup (limpieza de notas viejas)")
    args = parser.parse_args()

    if args.mode == "widgets":
        logging.info("EJECUTANDO MODO WIDGETS (Marquesinas, Semáforo y Fixture)...")
        from tools.editor_jefe import EditorJefe
        editor = EditorJefe()
        editor.update_widgets_and_banners()
    elif args.mode == "cleanup":
        logging.info("EJECUTANDO MODO CLEANUP (Depuración de notas viejas)...")
        from tools.cleanup import cleanup_old_posts
        cleanup_old_posts(max_age_days=3, dry_run=False)
    else:
        if args.loop:
            loop_mode()
        else:
            run_pipeline()

if __name__ == "__main__":
    main()
