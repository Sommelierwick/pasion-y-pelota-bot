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
from tools.promiedos import fetch_promiedos_page, search_backup_stats, search_web_for_verification
from tools.wordpress import WordPressPublisher
from tools.cleanup import cleanup_old_posts
from tools.images import get_football_image

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

class Article(pydantic.BaseModel):
    title: str = pydantic.Field(description="Título H1: clickbait honesto con jugador/equipo + dato estadístico o contexto.")
    content_html: str = pydantic.Field(description="Cuerpo en HTML limpio, 500-700 palabras, con H2, párrafos cortos, tabla HTML de estadísticas.")
    tags: List[str] = pydantic.Field(description="4-7 etiquetas: jugador, equipos, liga, tipo de noticia, competición.")
    league_category: str = pydantic.Field(description="Categoría WP: 'LaLiga'|'Premier League'|'Brasileirão'|'Fútbol Argentino'|'MLS'|'Liga MX'|'Champions League'|'Copa Libertadores'|'Mundial 2026'|otra")
    meta_description: str = pydantic.Field(default="", description="Meta descripción SEO de 140-155 caracteres con keyword principal.")

# =============================================================================
# 2. Base de Datos Local de Control de Duplicados
# =============================================================================

def load_database():
    if not os.path.exists(config.DATABASE_FILE):
        return {"published_urls": [], "published_titles": []}
    try:
        with open(config.DATABASE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error al cargar base de datos: {e}")
        return {"published_urls": [], "published_titles": []}

def save_database(db):
    try:
        with open(config.DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Error al guardar base de datos: {e}")

# =============================================================================
# 3. Motor de IA: API de Groq
# =============================================================================

def call_groq(prompt: str, system_instruction: str, response_schema=None, model="llama-3.1-8b-instant") -> Optional[dict]:
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
    """Llama a la API de Gemini mediante solicitudes HTTP directas rotando claves en caso de error 429."""
    if not config.GEMINI_API_KEYS:
        logging.warning("No hay claves de Gemini configuradas. Saltando a Groq.")
        return None
        
    num_keys = len(config.GEMINI_API_KEYS)
    import time
    for attempt in range(num_keys * 2):
        api_key = config.get_active_key()
        if not api_key:
            logging.error("No se pudo obtener una clave activa de Gemini.")
            config.rotate_key()
            continue
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
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
            logging.info(f"Intentando Gemini HTTP (Key Index: {config.ACTIVE_KEY_INDEX % num_keys})...")
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
                    return None
            elif response.status_code == 429:
                logging.warning(f"Gemini Rate Limit (429) detectado. Rotando clave...")
                config.rotate_key()
                time.sleep(2)
            else:
                logging.error(f"Error de Gemini HTTP ({response.status_code}): {response.text}")
                config.rotate_key()
        except Exception as e:
            logging.error(f"Excepción al llamar a Gemini HTTP: {e}")
            config.rotate_key()
            
    return None

def call_ai_json(prompt: str, system_instruction: str, response_schema=None) -> Optional[dict]:
    """Motor híbrido principal: Intenta Gemini primero (con rotación). Si falla, recurre a Groq."""
    res = call_gemini_http(prompt, system_instruction, response_schema)
    if res:
        logging.info("Respuesta obtenida con éxito usando Gemini.")
        return res
        
    logging.warning("Fallo en todas las claves de Gemini. Recurriendo a Groq como respaldo...")
    return call_groq(prompt, system_instruction, response_schema)

# =============================================================================
# 4. Flujo Principal del Pipeline
# =============================================================================

def run_pipeline():
    logging.info("=" * 70)
    logging.info("INICIANDO PIPELINE DE REDACCIÓN VIRTUAL — PASIÓN Y PELOTA")
    logging.info("=" * 70)

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

    # --- PASO 1: Obtener noticias recientes de todas las fuentes ---
    logging.info("Paso 1: Monitoreando fuentes de noticias...")
    raw_news = monitor_all_sources()
    if raw_news is None:
        raw_news = []

    # ─── AGREGAR CANDIDATO DE RESUMEN DIARIO DEL MUNDIAL ──────────────────────
    try:
        from tools.promiedos import fetch_mundial_complete_data
        import time
        mundial_data = fetch_mundial_complete_data()
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

    if not new_candidates:
        logging.info("Todas las noticias ya fueron procesadas. Fin del proceso.")
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

    OJEADOR_SYSTEM = """
Eres 'El Ojeador', editor jefe de un portal deportivo panamericano con estrategia SEO avanzada.

Tu misión es seleccionar UNA sola noticia para publicar. Debes cumplir ESTRICTAMENTE con estas reglas:

⚠️ REGLA DE LAS LIGAS DE CLUBES Y FÚTBOL ARGENTINO:
- Para cualquier noticia de ligas o copas de clubes (MLS, Liga Profesional Argentina, Liga MX, Premier League, LaLiga, Serie A, Champions League, Libertadores, etc. - EXCEPTUANDO el Brasileirão que tiene cobertura total de partidos), ÚNICAMENTE se permite hablar de:
  1. MERCADO DE PASES (fichajes, rumores de traspaso, renovaciones, salidas, llegadas de jugadores o técnicos).
  2. CLUBES INHIBIDOS POR LA FIFA (sanciones, deudas e inhibiciones oficiales de la FIFA que les impidan incorporar jugadores).
- REGLA DE ORO DE FÚTBOL ARGENTINO: En la categoría y temática de "Fútbol Argentino" (lpf_argentina), TODAS las notas sin excepción deben ser sobre el mercado de pases (fichajes, rumores de pases, salidas, llegadas) o sobre clubes inhibidos por la FIFA (sanciones, deudas e inhibiciones oficiales de la FIFA). No se permite ninguna otra temática (como partidos del torneo local, rendimiento deportivo, crónicas de la liga local, etc.).
- Ignora CUALQUIER otra noticia de ligas de clubes (resultados de partidos regulares, crónicas de partidos, tablas de posiciones locales, polémicas locales, etc.) que no esté ligada a un fichaje, traspaso o inhibición de la FIFA.

🌟 EXCEPCIONES ABSOLUTAS (SE PERMITE CUALQUIER NOTICIA GENERAL/DEPORTIVA/DE CRÓNICAS DE PARTIDOS):
1. LIONEL MESSI: Se acepta cualquier noticia sobre él (goles, partidos, récords en Inter Miami, lesiones, rendimiento, etc.).
2. SELECCIÓN ARGENTINA: Se permite cobertura total de su desempeño, partidos, resultados, previas, tácticas, convocatorias y noticias en general.
3. COPA MUNDIAL 2026: Se permite cobertura total de partidos, resultados, fixtures, grupos, clasificaciones y selecciones nacionales. Durante el mundial, se le debe dar prioridad a las selecciones en este orden estricto: Argentina, Brasil, España, Francia, Inglaterra, Uruguay, México. Las noticias sobre otras selecciones nacionales solo son de interés y se permite seleccionarlas si son muy importantes debido a que le ganaron o empataron un partido a alguna de las potencias mencionadas anteriormente (Argentina, Brasil, España, Francia, Inglaterra, Uruguay, México). Si existe un candidato de "Resumen del Mundial 2026" de la jornada, se le debe dar la máxima prioridad de publicación para resumir la fecha completa.
4. FÓRMULA 1 (F1): Se permite cobertura completa de carreras, resultados, clasificaciones y rumores de escuderías. Se debe hablar prioritariamente sobre Franco Colapinto, Alpine, Mercedes F1, Hamilton, Verstappen, etc.
5. BRASILEIRÃO (FÚTBOL DE BRASIL): Dado que el torneo está en juego, se permite cobertura total de partidos, resultados, crónicas de encuentros, tablas de posiciones y noticias de los clubes brasileños (Flamengo, Palmeiras, São Paulo, etc.), no limitándose únicamente a mercado de pases.

⚠️ DIRECTIVA DE REESCRITURA:
- Toda noticia seleccionada que provenga de los portales scrapeados debe ser reescrita por completo (cambiando drásticamente el vocabulario y estructura de las oraciones) e incorporando más datos estadísticos profundos y curiosidades históricas para superar la calidad del artículo original y evitar cualquier tipo de plagio o copia directa.

🏆 JERARQUÍA DE PRIORIDAD DE SELECCIÓN (Selecciona la más importante de esta lista):
1. Resumen diario de la jornada de la Copa Mundial 2026 (si está disponible) / Lionel Messi / Selección Argentina / Fórmula 1 (F1) (Mercedes, Alpine, Colapinto) (Máxima prioridad absoluta de la portada).
2. Brasileirão (crónicas de partidos, resultados y noticias de clubes brasileños).
3. Mercado de pases de la MLS (Inter Miami CF, LAFC, etc.).
4. Mercado de pases de la Liga Profesional Argentina (Boca, River, Racing) y clubes inhibidos por FIFA.
5. Mercado de pases de la Liga MX o Europa (Premier League, LaLiga, etc.).

Asigna el campo 'seo_cluster' con el identificador del clúster correspondiente: messi_seleccion, mundial_2026, f1, mls, brasileirao, lpf_argentina, liga_mx, champions, libertadores, premier, laliga, serie_a.
Asigna 'priority_score' del 1 (altísima) al 10 (baja).
"""

    import time
    time.sleep(3)
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
    logging.info("Aguardando 6 segundos para enfriar TPM antes de llamar al Editor Jefe...")
    time.sleep(6)
    
    headline = selected_news.get("headline", "")
    details_str = ", ".join(selected_news.get("details", []))
    player = selected_news.get("player", "")
    teams = selected_news.get("teams_involved", [])
    
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
    logging.info("Aguardando 12 segundos para enfriar TPM antes de llamar al Documentalista...")
    time.sleep(12)
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

5. TABLA MARKDOWN clara con columnas: Temporada | Goles | Asistencias | Partidos | xG

Si no hay datos exactos disponibles, usa estimaciones razonables basadas en el contexto
de la noticia y el clúster. NO inventes cifras extremas.
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
    logging.info("Aguardando 12 segundos para enfriar TPM antes de llamar al Redactor SEO...")
    time.sleep(12)
    logging.info("Agente 3 — El Redactor SEO: Redactando artículo con estrategia panamericana...")

    lsi_to_integrate = enriched_data.get("lsi_keywords", [])
    seo_cluster_name = enriched_data.get("seo_cluster", "global")

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

REGLAS ESTRICTAS DE REDACCIÓN Y REESCRITURA:

1. ESTRATEGIA GEO Y SEMÁNTICA (CO-CITACIÓN EN PIE DE NOTA):
   - Está COMPLETAMENTE PROHIBIDO mencionar en el cuerpo del artículo (en los párrafos o títulos) la fuente, medio o diario de donde proviene la noticia original, así como a sus autores o periodistas. No uses frases como "Según Diario Olé...", "De acuerdo a lo reportado por Marca...", ni nada similar. Presenta la información redactada de forma 100% autónoma como análisis propio del portal.
   - MANDATORIO: Al final de cada nota, DEBES añadir EXACTAMENTE la siguiente sección de co-citaciones en HTML (incluyendo las URLs crudas en texto plano):
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

5. TÍTULO H1: Clickbait honesto. Debe incluir:
   - Nombre del jugador, piloto o equipo protagonista.
   - Un dato estadístico o hecho concreto (goles, xG, valor de mercado, puntos en campeonato F1, posición de carrera).
   - Pregunta retórica O consecuencia impactante.
   Ejemplo: "Franco Colapinto sorprende a Williams: ¿Tiene el ritmo para ganar su primer punto F1?"

6. ESTRUCTURA HTML OBLIGATORIA:
   <h2>Contexto táctico y estadístico</h2>  → datos xG, forma reciente, clasificación, o tiempos/posiciones de F1.
   <h2>Impacto en la clasificación/campeonato</h2> → consecuencias reales en la tabla o el campeonato de escuderías.
   <h2>¿Qué viene ahora?</h2> → proyección del próximo partido o gran premio de F1.

7. TABLA HTML DE ESTADÍSTICAS (OBLIGATORIA):
   - Si el artículo es el "Resumen del Mundial 2026" de la jornada, la tabla HTML debe mostrar todos los partidos del día (Columnas: Local | Resultado | Visitante | Estado).
   - Para Fútbol en general: Columnas relevantes: Temporada, Competición, Goles, Asistencias, Partidos, xG.
   - Para Fórmula 1 (F1): Columnas relevantes: Gran Premio / Escudería, Posición Final, Puntos Obtenidos, Vueltas Rápidas, etc.
   - Usar <table>, <thead> y <tbody>. Estilos inline mínimos y limpios.

8. EVITAR ABSOLUTAMENTE:
   - Biografías estáticas ("Nacido en...")
   - "En este artículo veremos..."
   - "En conclusión..."
   - Párrafos de más de 4 líneas
   - Información de relleno.

9. CAMPOS DEL JSON:
   - content_html: HTML limpio SIN <html>, <head>, <body>, <article>
   - league_category: Mundial 2026 | F1 | MLS | Brasileirão | Fútbol Argentino | Liga MX |
     Champions League | Copa Libertadores | Premier League | LaLiga | Serie A | otra
   - tags: 4-7 tags (jugador/piloto, escudería/equipos, liga/GP, tipo de noticia).
   - meta_description: 140-155 caracteres, con la palabra clave principal al inicio.
   - 500-700 palabras totales.

10. CONTEXTO HISTÓRICO Y JERARQUÍA DEL FÚTBOL ARGENTINO (MANDATORIO):
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

13. REGLA LEGAL DE "CONDICIONAL PERIODÍSTICO" (MANDATORIO PARA TODOS LOS REDACTORES):
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

    logging.info(f"✅ Artículo redactado: '{final_article.get('title')}'")

    # --- PROCESO DE MONETIZACIÓN: Afiliados ---
    content_html = final_article.get("content_html", "")
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
    img_data = get_football_image(player_name_str, team_name, exclude_urls=exclude_urls)
    image_url = img_data.get("url")
    citation = img_data.get("citation", "")
    
    logging.info(f"Subiendo imagen de portada real desde Wikimedia: {image_url}")
    featured_image_id = publisher.upload_featured_image(
        image_url=image_url,
        filename=f"{player_name_clean}_portada.jpg"
    )

    # Determinar el redactor según la categoría/clúster original
    league_cat_orig = final_article.get("league_category", "Noticias")
    lower_title = final_article.get("title", "").lower()
    lower_content = content_html.lower()
    
    # Si la noticia trata de Huracán, firma Juan Carlos Perrusta; si trata de San Lorenzo, Carlos Four
    if "huracan" in lower_title or "huracán" in lower_title or "huracan" in lower_content or "huracán" in lower_content or any("huracan" in str(t).lower() or "huracán" in str(t).lower() for t in teams):
        writer = "Juan Carlos Perrusta"
    elif "san lorenzo" in lower_title or "san lorenzo" in lower_content or any("san lorenzo" in str(t).lower() for t in teams):
        writer = "Carlos Four"
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
    # 1. Messi -> Mundial 2026 y MLS
    if "messi" in lower_title or "messi" in lower_content or "inter miami" in lower_title or "inter miami" in lower_content:
        if "Mundial 2026" not in categories_list:
            categories_list.append("Mundial 2026")
        if "MLS" not in categories_list:
            categories_list.append("MLS")

    # 2. Selección Argentina o jugadores argentinos en el Mundial -> Mundial 2026 y Fútbol Argentino
    if "argentina" in lower_title or "argentina" in lower_content:
        if "Mundial 2026" in categories_list and "Fútbol Argentino" not in categories_list:
            categories_list.append("Fútbol Argentino")

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

    wp_post = publisher.publish_post(
        title=final_article.get("title"),
        content=content_html,
        league_category=categories_list,
        tags=final_article.get("tags", []),
        status="publish",
        featured_image_id=featured_image_id,
        seo_desc=final_article.get("meta_description"),
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
        if image_url:
            if "published_image_urls" not in db:
                db["published_image_urls"] = []
            db["published_image_urls"].append(image_url)
        save_database(db)
        logging.info("Base de datos anti-duplicados actualizada.")
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
