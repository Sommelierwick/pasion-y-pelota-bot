import os
import requests
import json
import logging
from requests.auth import HTTPBasicAuth
from tools.promiedos import fetch_promiedos_page, fetch_mundial_complete_data
import config

logger = logging.getLogger(__name__)

import pydantic
from typing import List, Optional
try:
    from google.antigravity import Agent, LocalAgentConfig
    HAS_ANTIGRAVITY = True
except ImportError:
    HAS_ANTIGRAVITY = False
import asyncio
from concurrent.futures import ThreadPoolExecutor

class ApprovedData(pydantic.BaseModel):
    approved: bool = pydantic.Field(description="Verdadero si la noticia es aprobada")
    rejection_reason: str = pydantic.Field(description="Razón detallada de la desaprobación si aplica")
    corrected_category: str = pydantic.Field(description="Categoría corregida de WordPress")

class WidgetData(pydantic.BaseModel):
    live_scores: str = pydantic.Field(description="HTML string de los marcadores en vivo")
    upcoming_matches: str = pydantic.Field(description="HTML string de los partidos programados")
    semaforo: str = pydantic.Field(description="HTML string del semáforo deportivo")

class SemaforoData(pydantic.BaseModel):
    semaforo: str = pydantic.Field(description="HTML string del semáforo deportivo lateral con exactamente 3 bloques de <a>...</a> con clase semaforo-link")

class PlayerStatScorer(pydantic.BaseModel):
    name: str = pydantic.Field(description="Nombre y apellido del jugador (ej. Deniz Undav o Lionel Messi).")
    team: str = pydantic.Field(description="Nombre de la selección (ej. Alemania o Argentina). Debe coincidir con los nombres del fixture.")
    goals: int = pydantic.Field(description="Cantidad de goles anotados.")

class PlayerStatAssist(pydantic.BaseModel):
    name: str = pydantic.Field(description="Nombre y apellido del jugador.")
    team: str = pydantic.Field(description="Nombre de la selección.")
    assists: int = pydantic.Field(description="Cantidad de asistencias.")

class PlayerStatPassing(pydantic.BaseModel):
    name: str = pydantic.Field(description="Nombre y apellido del jugador.")
    team: str = pydantic.Field(description="Nombre de la selección.")
    passes: int = pydantic.Field(description="Cantidad de pases correctos completados.")
    accuracy: str = pydantic.Field(description="Efectividad en pases (ej. '93%').")

class PlayerStatsSchema(pydantic.BaseModel):
    scorers: List[PlayerStatScorer] = pydantic.Field(description="Top 10 goleadores.")
    assists: List[PlayerStatAssist] = pydantic.Field(description="Top 10 asistidores.")
    passing: List[PlayerStatPassing] = pydantic.Field(description="Top 10 pasadores eficientes.")

def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)

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

def call_gemini_json(prompt: str, system_instruction: str, schema) -> dict:
    """Intenta llamar a Gemini para obtener JSON estructurado usando solicitudes HTTP directas,
    probando con varios modelos y rotando claves en caso de rate limit."""
    import time
    logger.info("⏳ Aplicando Delay Inteligente de 15 segundos para evitar Rate Limits (429)...")
    time.sleep(15)
    
    if not config.GEMINI_API_KEYS:
        logger.warning("No hay claves de Gemini configuradas.")
        return {}
        
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
                logger.error("No se pudo obtener una clave activa de Gemini.")
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
            
            if schema:
                raw_schema = schema.model_json_schema()
                gemini_schema = clean_schema_for_gemini(raw_schema)
                payload["generationConfig"] = {
                    "responseMimeType": "application/json",
                    "responseSchema": gemini_schema
                }
                
            try:
                logger.info(f"Intentando Gemini HTTP ({model_name}) (Key Index: {config.ACTIVE_KEY_INDEX % num_keys})...")
                response = requests.post(url, json=payload, headers=headers, timeout=45)
                
                if response.status_code == 200:
                    result = response.json()
                    try:
                        content = result["candidates"][0]["content"]["parts"][0]["text"]
                        return json.loads(content)
                    except (KeyError, IndexError, json.JSONDecodeError) as parse_err:
                        logger.error(f"Error parseando respuesta de Gemini HTTP: {parse_err}")
                        config.rotate_key()
                elif response.status_code == 429:
                    logger.warning(f"Gemini Rate Limit (429) detectado para {model_name}. Rotando clave y esperando 15s...")
                    config.rotate_key()
                    time.sleep(15)
                else:
                    logger.error(f"Error de Gemini HTTP ({response.status_code}) para {model_name}: {response.text}")
                    config.rotate_key()
            except Exception as e:
                logger.error(f"Excepción en Gemini HTTP call ({model_name}): {e}")
                config.rotate_key()
    return {}

def call_openai_json(prompt: str, system_instruction: str, model: str = "gpt-4o-mini") -> dict:
    """Función auxiliar para llamar a la API de OpenAI y obtener una respuesta JSON estructurada."""
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        logger.error("No se encontró la variable OPENAI_API_KEY en el entorno.")
        return {}
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openai_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }
    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Intentando OpenAI en EditorJefe ({model})...")
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                return json.loads(content)
            elif response.status_code == 429:
                logger.warning(f"OpenAI Rate Limit (429) detectado ({model}). Reintentando en 15 segundos... (Intento {attempt + 1}/{max_retries})")
                time.sleep(15)
                continue
            else:
                logger.error(f"Error de API de OpenAI: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Excepción al llamar a OpenAI: {e}")
    return {}

def call_groq_json(prompt: str, system_instruction: str, model: str = "llama-3.3-70b-versatile") -> dict:
    """Función auxiliar para llamar a la API de Groq y obtener una respuesta JSON estructurada."""
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        logger.error("No se encontró la variable GROQ_API_KEY en el entorno.")
        return {}
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {groq_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }
    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                return json.loads(content)
            elif response.status_code == 429:
                logger.warning(f"Groq Rate Limit (429) detectado en EditorJefe ({model}): {response.text}. Reintentando en 15 segundos... (Intento {attempt + 1}/{max_retries})")
                time.sleep(15)
                continue
            else:
                logger.error(f"Error de API de Groq: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Excepción al llamar a Groq: {e}")
    return {}

class EditorJefe:
    def __init__(self):
        self.wp_url = config.WP_URL.rstrip('/')
        self.auth = HTTPBasicAuth(config.WP_USER, config.WP_PASSWORD)

    def review_news(self, news_headline: str, news_details: str, seo_cluster: str, source_url: str, fact_check_results: str = "") -> dict:
        """
        Revisa la noticia candidata seleccionada por el Ojeador para validar que cumple el plan.
        """
        system_instruction = """
Eres "El Editor Jefe", periodista deportivo y fact-checker de fútbol y F1 para un portal deportivo panamericano.
Tu rol es asegurar que CUALQUIER noticia cumpla estrictamente con el plan y sea verídica.

Reglas Editoriales Estrictas:
1. LIGAS PERMITIDAS: Solo MLS, Brasileirão, Liga Profesional Argentina, Liga MX, Premier League, LaLiga, Serie A, Champions League, Copa Libertadores y Copa Mundial 2026.
   - CUALQUIER otra liga (ej: Liga Turca, Superliga turca, Griega, Escocesa, Saudí, etc.) está TERMINANTEMENTE PROHIBIDA. Si la noticia trata de un traspaso a/desde un club de estas ligas prohibidas (como Fenerbahçe, Galatasaray, Al-Nassr, etc.), debes desaprobarla.
2. ENTIDADES PROHIBIDAS: Miguel Almirón está completamente prohibido en cualquier contexto en el Mundial 2026 o en la tapa. Si se le menciona o si la noticia lo involucra, debes desaprobar.
3. EXCEPCIÓN MESSI/ARGENTINA: Se permite cualquier noticia sobre Messi o Selección Argentina. Sin embargo, NUNCA deben categorizarse bajo "MLS" ni bajo "Fútbol Argentino" (para evitar mezclar la temática de la liga local); si provienen de Inter Miami, MLS o Selección Argentina, debes corregir la categoría a "Mundial 2026".
4. FÓRMULA 1 (F1): Solo se habla de Franco Colapinto, Alpine y Mercedes F1, Hamilton y Verstappen.
5. REGLA DE ORO DE FÚTBOL ARGENTINO: Si la noticia corresponde a "Fútbol Argentino" (clúster "lpf_argentina" o categoría "Fútbol Argentino"), DEBES desaprobarla si el tema NO es estrictamente el mercado de pases (fichajes, rumores, renovaciones, salidas, llegadas) o clubes inhibidos por la FIFA (sanciones, deudas e inhibiciones oficiales de la FIFA para incorporar). No se permite ningún otro tema general de la liga local (crónicas de partidos, resultados, polémicas locales, etc.).
6. FAKE NEWS / FACT-CHECK: Compara la noticia candidata con los resultados de búsqueda web (Fact-Checking) provistos. Si la noticia no se encuentra reportada por medios confiables y certificados (ej: Marca, Olé, ESPN, etc.), o si figura como desmentida o como un rumor falso de cuentas no verificadas, debes desaprobarla devolviendo "approved": false. Todo debe ser confirmado, ya que son noticias serias.
7. PRIORIDAD DE SELECCIONES EN EL MUNDIAL: Durante el mundial, se le debe dar prioridad a las selecciones nacionales en este orden estricto: Argentina, Brasil, España, Francia, Inglaterra, Uruguay, México. Las noticias sobre otras selecciones nacionales solo deben ser aprobadas si son de extrema relevancia o si lograron ganarle a alguna de las potencias mencionadas anteriormente (Argentina, Brasil, España, Francia, Inglaterra, Uruguay, México).
8. JERARQUÍA DEL FÚTBOL ARGENTINO: Toda noticia del fútbol argentino debe respetar y ser coherente con la jerarquía institucional de los 6 clubes grandes (1 y 2. Boca y River [Clásico], 3. Independiente [Clásico con Racing], 4. Racing Club [Clásico con Independiente], 5. San Lorenzo [Clásico con Huracán], 6. Huracán [Clásico con San Lorenzo, y acechando su puesto de 5º grande por economía/resultados de los últimos 20 años]).

Devuelve un JSON con exactamente estos campos:
{
  "approved": bool,
  "rejection_reason": "razón detallada si es desaprobada (en español)",
  "corrected_category": "categoría WP corregida (Mundial 2026 | F1 | MLS | Brasileirão | Fútbol Argentino | Liga MX | Champions League | Copa Libertadores | Premier League | LaLiga | Serie A | otra)"
}
"""
        prompt = f"""
Noticia a evaluar:
Titular: {news_headline}
Detalles: {news_details}
Clúster SEO: {seo_cluster}
Fuente original: {source_url}

Resultados de búsqueda para verificación de hechos (Fact-Checking):
{fact_check_results}
        """
        res = call_gemini_json(prompt, system_instruction, ApprovedData)
        if not res:
            logger.info("Falló Gemini en review_news, usando Groq como respaldo...")
            res = call_groq_json(prompt, system_instruction, model="llama-3.3-70b-versatile")
        # Reglas Editoriales Estrictas:
        # 1. LIGAS PERMITIDAS: Solo MLS, Brasileirão, Liga Profesional Argentina, Liga MX, Premier League, LaLiga, Serie A, Champions League, Copa Libertadores y Copa Mundial 2026.
        # 2. ENTIDADES PROHIBIDAS: Miguel Almirón está completamente prohibido en cualquier contexto en el Mundial 2026 o en la tapa.
        # 3. EXCEPCIÓN MESSI/ARGENTINA: Se permite cualquier noticia sobre Messi o Selección Argentina. NUNCA deben categorizarse bajo "MLS" o "Fútbol Argentino".
        
        # Forzar aprobación y re-categorización para Messi/Argentina
        lower_headline = news_headline.lower()
        lower_details = str(news_details).lower()
        if "messi" in lower_headline or "messi" in lower_details or "argentina" in lower_headline or "argentina" in lower_details:
            res["approved"] = True
            if res.get("corrected_category") in ["MLS", "Fútbol Argentino"] or seo_cluster in ["mls", "lpf_argentina"]:
                res["corrected_category"] = "Mundial 2026"
        return res

    def calculate_projected_brackets(self, mundial_data: dict) -> list:
        groups = mundial_data.get("groups", [])
        if not groups:
            return []
            
        # 1. Obtener ganadores y segundos de grupo
        qualifiers = {}
        for g in groups:
            g_name = g.get("name", "Grupo")
            g_letter = g_name.replace("Grupo ", "").strip()
            if g_letter not in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']:
                continue
            teams = g.get("teams", [])
            
            t1 = teams[0] if len(teams) >= 1 else {"name": f"1º {g_letter}", "colors": {}}
            t2 = teams[1] if len(teams) >= 2 else {"name": f"2º {g_letter}", "colors": {}}
            t3 = teams[2] if len(teams) >= 3 else {"name": f"3º {g_letter}", "colors": {}}
            
            qualifiers[g_letter] = {
                "winner": {
                    "name": t1.get("name", f"1º {g_letter}"),
                    "colors": t1.get("colors", {})
                },
                "runner_up": {
                    "name": t2.get("name", f"2º {g_letter}"),
                    "colors": t2.get("colors", {})
                },
                "third": {
                    "name": t3.get("name", f"3º {g_letter}"),
                    "colors": t3.get("colors", {}),
                    "pts": int(t3.get("pts", 0)) if str(t3.get("pts", "")).isdigit() else 0,
                    "ratio": int(t3.get("ratio", 0)) if str(t3.get("ratio", "")).replace("-","").isdigit() else 0,
                    "goals": t3.get("goals", "0:0")
                }
            }
            
        # 2. Obtener y rankear a los mejores terceros
        third_teams = []
        for g_letter, q in qualifiers.items():
            t3 = q["third"]
            goals_str = t3["goals"]
            gf = 0
            if ":" in goals_str:
                parts = goals_str.split(":")
                gf = int(parts[0]) if parts[0].isdigit() else 0
            
            third_teams.append({
                "group": g_letter,
                "name": t3["name"],
                "pts": t3["pts"],
                "dg": t3["ratio"],
                "gf": gf,
                "colors": t3["colors"]
            })
            
        # Ordenar terceros por pts, dg (diferencia gol), gf (goles favor)
        third_teams.sort(key=lambda x: (x["pts"], x["dg"], x["gf"]), reverse=True)
        top_8_thirds = third_teams[:8]
        
        # 3. Resolver emparejamiento usando backtracking solver
        allowed = {
            'E': ['A', 'B', 'C', 'D', 'F'],
            'I': ['C', 'D', 'F', 'G', 'H'],
            'A': ['C', 'E', 'F', 'H', 'I'],
            'L': ['E', 'H', 'I', 'J', 'K'],
            'D': ['B', 'E', 'F', 'I', 'J'],
            'G': ['A', 'E', 'H', 'I', 'J'],
            'B': ['E', 'F', 'G', 'I', 'J'],
            'K': ['D', 'E', 'I', 'J', 'L']
        }
        
        matching = {}
        used_thirds = set()
        winners_list = ['E', 'I', 'A', 'L', 'D', 'G', 'B', 'K']
        
        def backtrack(winner_idx):
            if winner_idx == len(winners_list):
                return True
            w_letter = winners_list[winner_idx]
            for t in top_8_thirds:
                t_letter = t["group"]
                if t_letter not in used_thirds:
                    if t_letter in allowed[w_letter] and t_letter != w_letter:
                        matching[w_letter] = (t["name"], t["colors"], f"3º {t_letter}")
                        used_thirds.add(t_letter)
                        if backtrack(winner_idx + 1):
                            return True
                        used_thirds.remove(t_letter)
                        del matching[w_letter]
            return False
            
        if not backtrack(0):
            # Fallback simple
            logger.warning("No se pudo hallar matching perfecto de FIFA. Aplicando fallback de descarte.")
            for w_letter in winners_list:
                for t in top_8_thirds:
                    t_letter = t["group"]
                    if t_letter not in used_thirds and t_letter != w_letter:
                        matching[w_letter] = (t["name"], t["colors"], f"3º {t_letter}")
                        used_thirds.add(t_letter)
                        break
                        
        # 4. Estructurar los 16 partidos de la ronda de 32 (Dieciseisavos)
        projected = []
        
        match_configs = [
            {"num": 73, "home": qualifiers['A']['runner_up']['name'], "home_label": "2º A", "home_colors": qualifiers['A']['runner_up']['colors'], "away": qualifiers['B']['runner_up']['name'], "away_label": "2º B", "away_colors": qualifiers['B']['runner_up']['colors'], "date": "28 de Junio", "venue": "Los Angeles Stadium"},
            {"num": 74, "home": qualifiers['E']['winner']['name'], "home_label": "1º E", "home_colors": qualifiers['E']['winner']['colors'], "away": matching.get('E', ('Por definir', {}, '3º A/B/C/D/F'))[0], "away_label": matching.get('E', ('Por definir', {}, '3º A/B/C/D/F'))[2], "away_colors": matching.get('E', ('Por definir', {}, '3º A/B/C/D/F'))[1], "date": "29 de Junio", "venue": "Boston Stadium"},
            {"num": 75, "home": qualifiers['F']['winner']['name'], "home_label": "1º F", "home_colors": qualifiers['F']['winner']['colors'], "away": qualifiers['C']['runner_up']['name'], "away_label": "2º C", "away_colors": qualifiers['C']['runner_up']['colors'], "date": "29 de Junio", "venue": "Estadio Monterrey"},
            {"num": 76, "home": qualifiers['C']['winner']['name'], "home_label": "1º C", "home_colors": qualifiers['C']['winner']['colors'], "away": qualifiers['F']['runner_up']['name'], "away_label": "2º F", "away_colors": qualifiers['F']['runner_up']['colors'], "date": "29 de Junio", "venue": "Houston Stadium"},
            {"num": 77, "home": qualifiers['I']['winner']['name'], "home_label": "1º I", "home_colors": qualifiers['I']['winner']['colors'], "away": matching.get('I', ('Por definir', {}, '3º C/D/F/G/H'))[0], "away_label": matching.get('I', ('Por definir', {}, '3º C/D/F/G/H'))[2], "away_colors": matching.get('I', ('Por definir', {}, '3º C/D/F/G/H'))[1], "date": "30 de Junio", "venue": "New York/New Jersey Stadium"},
            {"num": 78, "home": qualifiers['E']['runner_up']['name'], "home_label": "2º E", "home_colors": qualifiers['E']['runner_up']['colors'], "away": qualifiers['I']['runner_up']['name'], "away_label": "2º I", "away_colors": qualifiers['I']['runner_up']['colors'], "date": "30 de Junio", "venue": "Dallas Stadium"},
            {"num": 79, "home": qualifiers['A']['winner']['name'], "home_label": "1º A", "home_colors": qualifiers['A']['winner']['colors'], "away": matching.get('A', ('Por definir', {}, '3º C/E/F/H/I'))[0], "away_label": matching.get('A', ('Por definir', {}, '3º C/E/F/H/I'))[2], "away_colors": matching.get('A', ('Por definir', {}, '3º C/E/F/H/I'))[1], "date": "30 de Junio", "venue": "Estadio Azteca, CDMX"},
            {"num": 80, "home": qualifiers['L']['winner']['name'], "home_label": "1º L", "home_colors": qualifiers['L']['winner']['colors'], "away": matching.get('L', ('Por definir', {}, '3º E/H/I/J/K'))[0], "away_label": matching.get('L', ('Por definir', {}, '3º E/H/I/J/K'))[2], "away_colors": matching.get('L', ('Por definir', {}, '3º E/H/I/J/K'))[1], "date": "1 de Julio", "venue": "Atlanta Stadium"},
            {"num": 81, "home": qualifiers['D']['winner']['name'], "home_label": "1º D", "home_colors": qualifiers['D']['winner']['colors'], "away": matching.get('D', ('Por definir', {}, '3º B/E/F/I/J'))[0], "away_label": matching.get('D', ('Por definir', {}, '3º B/E/F/I/J'))[2], "away_colors": matching.get('D', ('Por definir', {}, '3º B/E/F/I/J'))[1], "date": "1 de Julio", "venue": "San Francisco Bay Area Stadium"},
            {"num": 82, "home": qualifiers['G']['winner']['name'], "home_label": "1º G", "home_colors": qualifiers['G']['winner']['colors'], "away": matching.get('G', ('Por definir', {}, '3º A/E/H/I/J'))[0], "away_label": matching.get('G', ('Por definir', {}, '3º A/E/H/I/J'))[2], "away_colors": matching.get('G', ('Por definir', {}, '3º A/E/H/I/J'))[1], "date": "1 de Julio", "venue": "Seattle Stadium"},
            {"num": 83, "home": qualifiers['K']['runner_up']['name'], "home_label": "2º K", "home_colors": qualifiers['K']['runner_up']['colors'], "away": qualifiers['L']['runner_up']['name'], "away_label": "2º L", "away_colors": qualifiers['L']['runner_up']['colors'], "date": "2 de Julio", "venue": "Toronto Stadium"},
            {"num": 84, "home": qualifiers['H']['winner']['name'], "home_label": "1º H", "home_colors": qualifiers['H']['winner']['colors'], "away": qualifiers['J']['runner_up']['name'], "away_label": "2º J", "away_colors": qualifiers['J']['runner_up']['colors'], "date": "2 de Julio", "venue": "Los Angeles Stadium"},
            {"num": 85, "home": qualifiers['B']['winner']['name'], "home_label": "1º B", "home_colors": qualifiers['B']['winner']['colors'], "away": matching.get('B', ('Por definir', {}, '3º E/F/G/I/J'))[0], "away_label": matching.get('B', ('Por definir', {}, '3º E/F/G/I/J'))[2], "away_colors": matching.get('B', ('Por definir', {}, '3º E/F/G/I/J'))[1], "date": "2 de Julio", "venue": "BC Place, Vancouver"},
            {"num": 86, "home": qualifiers['J']['winner']['name'], "home_label": "1º J", "home_colors": qualifiers['J']['winner']['colors'], "away": qualifiers['H']['runner_up']['name'], "away_label": "2º H", "away_colors": qualifiers['H']['runner_up']['colors'], "date": "3 de Julio", "venue": "Miami Stadium"},
            {"num": 87, "home": qualifiers['K']['winner']['name'], "home_label": "1º K", "home_colors": qualifiers['K']['winner']['colors'], "away": matching.get('K', ('Por definir', {}, '3º D/E/I/J/L'))[0], "away_label": matching.get('K', ('Por definir', {}, '3º D/E/I/J/L'))[2], "away_colors": matching.get('K', ('Por definir', {}, '3º D/E/I/J/L'))[1], "date": "3 de Julio", "venue": "Kansas City Stadium"},
            {"num": 88, "home": qualifiers['D']['runner_up']['name'], "home_label": "2º D", "home_colors": qualifiers['D']['runner_up']['colors'], "away": qualifiers['G']['runner_up']['name'], "away_label": "2º G", "away_colors": qualifiers['G']['runner_up']['colors'], "date": "3 de Julio", "venue": "Dallas Stadium"},
        ]
        
        projected = []
        for c in match_configs:
            projected.append({
                "match_num": c["num"],
                "home": c["home"],
                "home_label": c["home_label"],
                "home_colors": c["home_colors"],
                "away": c["away"],
                "away_label": c["away_label"],
                "away_colors": c["away_colors"],
                "date": c["date"],
                "venue": c["venue"]
            })
        return projected

    def calculate_player_stats(self, mundial_data: dict) -> dict:
        logger.info("El Editor Jefe está extrayendo estadísticas del Mundial 2026 directamente del JSON (cero alucinación)...")
        
        # 1. Obtener coincidencia de colores y nombres de selecciones
        team_colors = {}
        team_names = {}
        for g in mundial_data.get("groups", []):
            for t in g.get("teams", []):
                team_id = t.get("id")
                team_names[team_id] = t.get("name")
                team_colors[team_id] = t.get("colors", {})

        res = {"scorers": [], "assists": [], "passing": []}
        
        stats = mundial_data.get("players_statistics", [])
        # Compatibilidad: stats puede ser lista (del adaptador) o dict con clave "tables"
        if isinstance(stats, dict):
            tables = stats.get("tables", [])
        elif isinstance(stats, list):
            tables = stats
        else:
            tables = []
        
        for t in tables:
            name = t.get("name", "")
            for r in t.get("rows", [])[:10]:
                player_name = r.get("entity", {}).get("object", {}).get("name", "Desconocido")
                team_id = r.get("entity", {}).get("object", {}).get("team_id", "")
                team_name = team_names.get(team_id, "Desconocido")
                colors = team_colors.get(team_id, {"color": "#333", "text_color": "#fff"})
                
                vals = r.get("values", [])
                if not vals:
                    continue
                    
                val = vals[0].get("value", "0")
                
                if name == "Goles":
                    res["scorers"].append({"name": player_name, "team": team_name, "goals": val, "colors": colors})
                elif name == "Asistencias":
                    res["assists"].append({"name": player_name, "team": team_name, "assists": val, "colors": colors})
                elif name == "Barridas ganadas":
                    res["passing"].append({"name": player_name, "team": team_name, "passes": val, "accuracy": "-", "colors": colors})
        
        return res

    def update_widgets_and_banners(self) -> bool:
        """
        Lee datos reales del Mundial en Promiedos y actualiza dinámicamente las marquesinas, el Semáforo y el fixture.
        """
        logger.info("El Editor Jefe está recopilando datos reales de la Copa del Mundo 2026 desde Promiedos...")
        
        from tools.statistical_monitor import detect_statistical_anomalies
        from tools.wordpress import WordPressPublisher
        
        # Obtener datos estructurados para la página de Fixture y Marquesinas
        mundial_data = fetch_mundial_complete_data()
        games = mundial_data.get("games", [])
        
        # ORDEN SUPREMA: Inyectar partidos de fase eliminatoria (brackets) para que NUNCA deje de aparecer la data
        for stage in mundial_data.get("brackets", {}).get("stages", []):
            stage_name = stage.get("name", "Fase")
            for match in stage.get("matches", []):
                participants = match.get("participants", [])
                home = participants[0].get("name", "Por definir") if len(participants) > 0 else "Por definir"
                away = participants[1].get("name", "Por definir") if len(participants) > 1 else "Por definir"
                
                for g in match.get("games", []):
                    # Solo agregar si tiene fecha programada
                    if g.get("start_time"):
                        games.append({
                            "id": "bracket_game",
                            "stage": stage_name,
                            "home": home,
                            "away": away,
                            "home_goals": "-",
                            "away_goals": "-",
                            "status": g.get("status", "Prog."),
                            "status_symbol": "Prog.",
                            "start_time": g.get("start_time", ""),
                            "display_time": "",
                            "display_status": ""
                        })

        # ─── GENERACIÓN DETERMINÍSTICA DE MARQUESINAS EN PYTHON ─────────────────
        from datetime import datetime
        import pytz
        tz = pytz.timezone('America/Argentina/Buenos_Aires')
        now = datetime.now(tz)
        
        live_games = []
        upcoming_games = []
        
        for g in games:
            start_time_str = g.get("start_time", "")
            game_time = None
            if start_time_str:
                try:
                    clean_time_str = start_time_str.replace(" (Hora Argentina)", "").strip()
                    dt = datetime.strptime(clean_time_str, "%d-%m-%Y %H:%M")
                    game_time = tz.localize(dt)
                except Exception as e:
                    logger.warning(f"Error parsing start_time {start_time_str}: {e}")
            
            status_name = g.get("status", "")
            status_sym = g.get("status_symbol", "")
            
            is_live_or_finished = False
            if status_sym == "Fin" or status_name == "Finalizado":
                is_live_or_finished = True
            elif game_time and game_time <= now:
                is_live_or_finished = True
                
            if is_live_or_finished:
                live_games.append((game_time, g))
            else:
                upcoming_games.append((game_time, g))
                
        # Ordenar partidos
        live_games.sort(key=lambda x: x[0] if x[0] else datetime.min.replace(tzinfo=tz), reverse=True)
        upcoming_games.sort(key=lambda x: x[0] if x[0] else datetime.max.replace(tzinfo=tz))
        
        months_abbr = {
            1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
            7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"
        }
        
        # Generar HTML para Marquesina de Marcadores (live_scores)
        live_items = []
        for gt, g in live_games:
            home = g.get("home", "Local")
            away = g.get("away", "Visita")
            home_goals = g.get("home_goals", "-")
            away_goals = g.get("away_goals", "-")
            status_name = g.get("status", "")
            status_sym = g.get("status_symbol", "")
            display_status = g.get("display_status") or g.get("game_time_status_to_display") or ""
            
            if status_sym == "Fin" or status_name == "Finalizado":
                status_display = "Final"
            elif display_status:
                status_display = display_status
            else:
                status_display = "En Vivo"
                
            item_html = f'<div class="score-item"><span class="league-tag">MUNDIAL 2026</span> <strong>{home}</strong> {home_goals} - {away_goals} <strong>{away}</strong> <span class="match-status">{status_display}</span></div>'
            live_items.append(item_html)
            
        # Generar HTML para Marquesina de Próximos Partidos (upcoming_matches)
        upcoming_items = []
        for gt, g in upcoming_games:
            home = g.get("home", "Local")
            away = g.get("away", "Visita")
            start_time_str = g.get("start_time", "")
            
            if gt:
                date_time_display = f"{gt.day} {months_abbr[gt.month]} {gt.hour:02d}:{gt.minute:02d}"
            else:
                date_time_display = start_time_str
                
            item_html = f'<div class="score-item"><span class="league-tag">PRÓXIMO ENCUENTRO</span> <strong>{home}</strong> vs. <strong>{away}</strong> <span class="match-status">{date_time_display} (Hora Arg)</span></div>'
            upcoming_items.append(item_html)
            
        # Duplicar items para loop continuo (mínimo 8 items)
        if live_items:
            while len(live_items) < 8:
                live_items.extend(list(live_items))
            live_scores_html = "\n".join(live_items[:12])
        else:
            live_scores_html = ""
            
        if upcoming_items:
            while len(upcoming_items) < 8:
                upcoming_items.extend(list(upcoming_items))
            upcoming_matches_html = "\n".join(upcoming_items[:12])
        else:
            upcoming_matches_html = ""

        # ─── GENERACIÓN DEL SEMÁFORO DEPORTIVO (CON LLM O FALLBACK) ─────────────
        # Obtener artículos recientes desde la REST API de WordPress para el Semáforo Deportivo
        posts_data = []
        posts_list_str = ""
        try:
            posts_url = f"{self.wp_url}/wp-json/wp/v2/posts"
            logger.info("Consultando artículos publicados en WordPress para el Semáforo...")
            resp_posts = requests.get(posts_url, params={"per_page": 15, "_fields": "id,title,link,categories,excerpt"}, auth=self.auth, timeout=15)
            if resp_posts.status_code == 200:
                posts_data = resp_posts.json()
                
                # Obtener categorías para mapear nombres
                cats_url = f"{self.wp_url}/wp-json/wp/v2/categories"
                resp_cats = requests.get(cats_url, params={"per_page": 100, "_fields": "id,name"}, auth=self.auth, timeout=15)
                cat_map = {}
                if resp_cats.status_code == 200:
                    for c in resp_cats.json():
                        cat_map[c["id"]] = c["name"]
                
                posts_formatted = []
                import re
                for p in posts_data:
                    p_id = p.get("id")
                    title = p.get("title", {}).get("rendered", "")
                    link = p.get("link", "")
                    cat_ids = p.get("categories", [])
                    cat_name = cat_map.get(cat_ids[0], "Deportes") if cat_ids else "Deportes"
                    excerpt = p.get("excerpt", {}).get("rendered", "")
                    excerpt_clean = re.sub('<[^<]+?>', '', excerpt).strip()[:100]
                    posts_formatted.append(f"- ID: {p_id} | Título: '{title}' | Categoría: '{cat_name}' | Link: {link} | Resumen: {excerpt_clean}")
                
                posts_list_str = "\n".join(posts_formatted)
                logger.info(f"Se encontraron {len(posts_formatted)} artículos para alimentar el Semáforo.")
            else:
                logger.error(f"Error al obtener artículos para el Semáforo (HTTP {resp_posts.status_code})")
        except Exception as e:
            logger.error(f"Excepción al obtener artículos para el Semáforo: {e}")
        
        current_time_str = now.strftime('%H:%M (Hora Arg)')
        months_es = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
            7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }
        current_date_str = f"{now.day} de {months_es[now.month]} de {now.year}"

        system_instruction = """
Eres "El Editor Jefe", periodista experto en deportes. Debes armar el HTML del Semáforo Deportivo lateral para la web usando la lista de artículos recientemente publicados.
La fecha actual es {SIMULATION_DATE}, {SIMULATION_TIME}.

Debes generar el HTML del Semáforo Deportivo lateral.
- Debe contener exactamente tres bloques wrapped en enlaces (tag <a>) apuntando a los artículos reales correspondientes a los 3 semáforos, con clase "semaforo-link":
  <a href="{link_real}" class="semaforo-link">
    <div class="semaforo-item {color}">
      <span class="semaforo-dot">{emoji}</span>
      <div class="semaforo-content">
        <strong>{categoria_del_post}:</strong> {texto_breve_del_semaforo}
      </div>
    </div>
  </a>
- Colores a generar:
  - verde: Para un artículo de éxito, victoria, Lionel Messi, Selección Argentina o gran expectativa.
  - amarillo: Para un artículo neutral, rumores de fichajes/mercado de pases o F1.
  - rojo: Para un artículo de deudas/crisis económica de clubes, lesiones graves o inhibiciones de la FIFA.
- Selecciona exactamente 3 artículos reales de la "LISTA DE ARTÍCULOS PUBLICADOS EN EL PORTAL" para mapear cada uno a un color.
- El texto explicativo de cada ítem del semáforo debe ser muy corto, llamativo y adaptado a lo que dice el artículo seleccionado (máximo 15-20 palabras).
- NUNCA uses Miguel Almirón en ningún contexto.
- Si por alguna razón no hay suficientes artículos en la lista, puedes usar enlaces simulados a '/#', pero prioriza siempre la lista de artículos reales.
""".replace("{SIMULATION_DATE}", current_date_str).replace("{SIMULATION_TIME}", current_time_str)

        prompt = f"""
LISTA DE ARTÍCULOS PUBLICADOS EN EL PORTAL (Usa los links de esta lista para el semáforo):
{posts_list_str}
"""
        
        res_llm = None
        if posts_list_str.strip():
            res_llm = call_gemini_json(prompt, system_instruction, SemaforoData)
            if not res_llm or "semaforo" not in res_llm:
                logger.info("Falló Gemini en semáforo, usando Groq como respaldo...")
                res_llm = call_groq_json(prompt, system_instruction, model="llama-3.3-70b-versatile")
            if not res_llm or "semaforo" not in res_llm:
                logger.info("Falló Groq en semáforo, usando OpenAI como respaldo final...")
                res_llm = call_openai_json(prompt, system_instruction, model="gpt-4o-mini")

        # Fallback local determinístico de Semáforo si fallan las APIs
        if not res_llm or "semaforo" not in res_llm:
            logger.warning("Fallo general en APIs al generar semáforo. Recurriendo a fallback determinístico local.")
            colors = ["verde", "amarillo", "rojo"]
            emojis = ["🟢", "🟡", "🔴"]
            fallback_items = []
            for idx, p in enumerate(posts_data[:3]):
                title = p.get("title", {}).get("rendered", "")
                link = p.get("link", "")
                fallback_items.append(f"""<a href="{link}" class="semaforo-link">
  <div class="semaforo-item {colors[idx]}">
    <span class="semaforo-dot">{emojis[idx]}</span>
    <div class="semaforo-content">
      <strong>Fútbol:</strong> {title}
    </div>
  </div>
</a>""")
            while len(fallback_items) < 3:
                idx = len(fallback_items)
                fallback_items.append(f"""<a href="/#" class="semaforo-link">
  <div class="semaforo-item {colors[idx]}">
    <span class="semaforo-dot">{emojis[idx]}</span>
    <div class="semaforo-content">
      <strong>Mundial:</strong> Copa del Mundo de la FIFA 2026 en vivo.
    </div>
  </div>
</a>""")
            semaforo_html = "\n".join(fallback_items)
        else:
            semaforo_html = res_llm["semaforo"]

        # Sanitizar saltos de línea y contrabarras en el Semáforo
        if isinstance(semaforo_html, str):
            semaforo_html = semaforo_html.replace('\\\\n', '\n').replace('\\n', '\n').replace('\\t', '')
            semaforo_html = semaforo_html.replace('\\"', '"').replace('\\/', '/')

        # Construir la estructura final de datos
        res = {
            "live_scores": live_scores_html,
            "upcoming_matches": upcoming_matches_html,
            "semaforo": semaforo_html,
            "mundial_data": mundial_data
        }
        
        # Calcular los cruces proyectados de dieciseisavos (Ronda de 32)
        projected_brackets = []
        try:
            projected_brackets = self.calculate_projected_brackets(mundial_data)
            logger.info("Cruces proyectados del Mundial calculados con éxito.")
        except Exception as pe:
            logger.error(f"Error al calcular los cruces proyectados: {pe}")
        res["projected_brackets"] = projected_brackets

        # Calcular estadísticas de los jugadores del mundial
        player_stats = {}
        try:
            player_stats = self.calculate_player_stats(mundial_data)
            logger.info("Estadísticas de jugadores del Mundial calculadas con éxito.")
        except Exception as se:
            logger.error(f"Error al calcular las estadísticas de jugadores: {se}")
        res["player_stats"] = player_stats

        # Subir los datos generados a WordPress
        update_url = f"{self.wp_url}/wp-json/ppelota/v1/update-data"
        try:
            logger.info("Enviando actualización de marquesinas, semáforo y fixture del Mundial a la API de WordPress...")
            resp = requests.post(update_url, json=res, auth=self.auth, timeout=20)
            if resp.status_code == 200:
                logger.info("✅ Marquesinas, Semáforo y Fixture actualizados dinámicamente en WordPress.")
            else:
                logger.error(f"Error al actualizar marquesinas ({resp.status_code}): {resp.text}")
        except Exception as e:
            logger.error(f"Excepción al actualizar marquesinas vía REST API: {e}")
            
        # ─── MONITOREO ESTADÍSTICO PARA ALARMAS ─────────────
        try:
            logger.info("Iniciando monitor estadístico para detectar anomalías...")
            anomalies = detect_statistical_anomalies(mundial_data)
            if anomalies:
                logger.info(f"¡Se detectaron {len(anomalies)} anomalías estadísticas! Invocando al Agente Estadístico...")
                wp_pub = WordPressPublisher()
                category_id = wp_pub.get_or_create_category("Estadísticas")
                
                for anomaly in anomalies:
                    logger.info(f"Alerta: {anomaly['type']} - {anomaly['team']}")
                    
                    sys_prompt = "Eres un Agente Estadístico experto. Analiza el siguiente cambio brusco en los datos de un equipo del Mundial 2026. Escribe un reporte analítico de 3-4 párrafos. Escribe en formato HTML para WordPress sin Markdown ni etiquetas de código."
                    
                    user_prompt = f"El equipo {anomaly['team']} ({anomaly['group']}) ha tenido la siguiente anomalía: {anomaly['type']}.\nDetalles: {anomaly['description']}\nEscribe un artículo corto explicando lo que significa esto para su futuro en el torneo. El título debe ser impactante e ir en la primera línea precedido por 'TITULO:'."
                    
                    # Llamamos a Groq directamente para el reporte
                    try:
                        from main_standalone import call_groq
                        content = call_groq(user_prompt, sys_prompt)
                        if content:
                            title = f"ALERTA ESTADÍSTICA: {anomaly['team']} y un cambio radical"
                            body = content
                            if "TITULO:" in content:
                                parts = content.split("\n", 1)
                                title = parts[0].replace("TITULO:", "").replace("TÍTULO:", "").strip()
                                body = parts[1].strip() if len(parts) > 1 else body
                                
                            wp_pub.publish_post(
                                title=title,
                                content=body,
                                league_category="Estadísticas",
                                tags=[anomaly['team'], "Estadísticas", anomaly['type']],
                                featured_image_id=None,
                                status="publish"
                            )
                            logger.info(f"✅ Artículo estadístico publicado: {title}")
                    except Exception as ge:
                        logger.error(f"Error al generar artículo estadístico con la IA: {ge}")
            else:
                logger.info("No se detectaron anomalías estadísticas en este ciclo.")
        except Exception as se:
            logger.error(f"Error en el monitoreo estadístico: {se}")
            
        return True
