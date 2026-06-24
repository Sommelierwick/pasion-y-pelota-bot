import requests
from bs4 import BeautifulSoup
import logging
import urllib.parse
import json
from datetime import datetime
import pytz

# Configuración de logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def convert_to_argentina_time(start_time_str: str) -> str:
    if not start_time_str:
        return start_time_str
    start_time_str = str(start_time_str).strip()
    # Promiedos publica por defecto en GMT-3 (Hora Argentina)
    # Solo agregamos el sufijo para cumplir con la regla 11 si no lo tiene
    if "(Hora Argentina)" not in start_time_str:
        return f"{start_time_str} (Hora Argentina)"
    return start_time_str


LEAGUE_URLS = {
    "argentina": "https://www.promiedos.com.ar/league/liga-profesional/hc",
    "futbol-argentino": "https://www.promiedos.com.ar/league/liga-profesional/hc",
    "lpf_argentina": "https://www.promiedos.com.ar/league/liga-profesional/hc",
    "copa libertadores": "https://www.promiedos.com.ar/league/libertadores/bac",
    "libertadores": "https://www.promiedos.com.ar/league/libertadores/bac",
    "inglaterra": "https://www.promiedos.com.ar/league/premier-league/h",
    "premier": "https://www.promiedos.com.ar/league/premier-league/h",
    "premier league": "https://www.promiedos.com.ar/league/premier-league/h",
    "espana": "https://www.promiedos.com.ar/league/laliga/bb",
    "laliga": "https://www.promiedos.com.ar/league/laliga/bb",
    "la liga": "https://www.promiedos.com.ar/league/laliga/bb",
    "italia": "https://www.promiedos.com.ar/league/serie-a/bh",
    "serie a": "https://www.promiedos.com.ar/league/serie-a/bh",
    "francia": "https://www.promiedos.com.ar/league/ligue-1/df",
    "ligue 1": "https://www.promiedos.com.ar/league/ligue-1/df",
    "mexico": "https://www.promiedos.com.ar/league/liga-mx/beb",
    "liga mx": "https://www.promiedos.com.ar/league/liga-mx/beb",
    "mls": "https://www.promiedos.com.ar/league/mls/bae",
    "brasil": "https://www.promiedos.com.ar/league/brasileirao-serie-a/bbd",
    "brasileirao": "https://www.promiedos.com.ar/league/brasileirao-serie-a/bbd",
    "mundial": "https://www.promiedos.com.ar/league/fifa-world-cup/fjda",
    "mundial 2026": "https://www.promiedos.com.ar/league/fifa-world-cup/fjda",
    "mundial_2026": "https://www.promiedos.com.ar/league/fifa-world-cup/fjda",
    "champions": "https://www.promiedos.com.ar/league/uefa-champions-league/fhc",
    "champions league": "https://www.promiedos.com.ar/league/uefa-champions-league/fhc",
    "messi_seleccion": "https://www.promiedos.com.ar/league/fifa-world-cup/fjda"
}

def parse_next_data_to_text(html_content: str, league_key: str = "") -> str:
    """
    Parsea el script __NEXT_DATA__ de Next.js en Promiedos y genera
    una representación en texto legible de partidos y tablas.
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        next_data_script = soup.find("script", id="__NEXT_DATA__")
        if not next_data_script:
            return ""
        
        data = json.loads(next_data_script.string or "{}")
        page_props = data.get("props", {}).get("pageProps", {})
        body_data = page_props.get("data", {})
        
        output = []
        
        # 1. Buscar ligas y partidos (home page)
        leagues = body_data.get("leagues", [])
        if not leagues:
            leagues = page_props.get("menuData", {}).get("leagues", [])
            
        if leagues:
            for league in leagues:
                league_name = league.get("name", "Liga")
                if league_key and league_key.lower() != "all":
                    if league_key.lower() in ["mundial", "mundial 2026", "mundial_2026", "messi_seleccion"]:
                        if not any(x in league_name.lower() for x in ["mundial", "world cup", "fifa"]):
                            continue
                
                output.append(f"\n[Liga: {league_name}]")
                games = league.get("games", [])
                for g in games:
                    teams = g.get("teams", [])
                    scores = g.get("scores", [])
                    status = g.get("status", {})
                    
                    home = teams[0].get("name") if len(teams) > 0 else "Local"
                    away = teams[1].get("name") if len(teams) > 1 else "Visita"
                    home_goals = scores[0] if len(scores) > 0 else "-"
                    away_goals = scores[1] if len(scores) > 1 else "-"
                    
                    status_name = status.get("name", "Prog.")
                    start_time = convert_to_argentina_time(g.get("start_time", ""))
                    display_time = g.get("game_time_to_display", "")
                    display_status = g.get("game_time_status_to_display", "")
                    
                    output.append(f"  - [{status_name}] {home} {home_goals} - {away_goals} {away} | Inicio: {start_time} | Tiempo: {display_time} ({display_status})")
        
        # 2. Posiciones de grupos (Zonas)
        tables_groups = body_data.get("tables_groups", [])
        for tg in tables_groups:
            group_name = tg.get("name", "Grupos")
            output.append(f"\n[Zonas/Posiciones: {group_name}]")
            tables = tg.get("tables", [])
            for t in tables:
                table_name = t.get("name", "Grupo")
                output.append(f"  {table_name}:")
                table_data = t.get("table", {})
                rows = table_data.get("rows", [])
                cols = table_data.get("columns", [])
                col_headers = [c.get("title", "") for c in cols]
                output.append("    Pos | Equipo | " + " | ".join(col_headers))
                for r in rows:
                    num = r.get("num", 1)
                    team_name = r.get("entity", {}).get("object", {}).get("name", "Equipo")
                    vals = r.get("values", [])
                    val_map = {v.get("key"): v.get("value") for v in vals}
                    row_vals = [val_map.get(c.get("key"), "-") for c in cols]
                    output.append(f"    {num} | {team_name} | " + " | ".join(row_vals))
                    
        # 3. Partidos de la fecha activa
        games_data = body_data.get("games", {})
        filters = games_data.get("filters", [])
        for f in filters:
            filter_name = f.get("name")
            games = f.get("games", [])
            if games:
                output.append(f"\n[Fixture - {filter_name}]")
                for g in games:
                    teams = g.get("teams", [])
                    scores = g.get("scores", [])
                    status = g.get("status", {})
                    home = teams[0].get("name") if len(teams) > 0 else "Local"
                    away = teams[1].get("name") if len(teams) > 1 else "Visita"
                    home_goals = scores[0] if len(scores) > 0 else "-"
                    away_goals = scores[1] if len(scores) > 1 else "-"
                    status_name = status.get("name", "Prog.")
                    start_time = convert_to_argentina_time(g.get("start_time", ""))
                    output.append(f"  - [{status_name}] {home} {home_goals} - {away_goals} {away} | Inicio: {start_time}")
                    
        # 4. Cruces de llaves (brackets)
        brackets = body_data.get("brackets", {})
        stages = brackets.get("stages", [])
        if stages:
            output.append("\n[Llaves Eliminatorias]")
            for s in stages:
                stage_name = s.get("name", "Etapa")
                output.append(f"  Fase: {stage_name}")
                groups = s.get("groups", [])
                for idx, grp in enumerate(groups):
                    participants = grp.get("participants", [])
                    p_names = []
                    for p in participants:
                        name = p.get("entity", {}).get("object", {}).get("name", "Por definir")
                        p_names.append(name)
                    p_str = " vs ".join(p_names) if p_names else "Por definir"
                    score = grp.get("score", "")
                    output.append(f"    Cruce {idx+1}: {p_str} | Resultado: {score}")
                    
        return "\n".join(output)
    except Exception as e:
        logging.error(f"Error al procesar Next.js JSON en Promiedos: {e}")
        return ""

def fetch_promiedos_page(league_key: str) -> str:
    """
    Intenta descargar el HTML de la página de Promiedos correspondiente a la liga.
    Si retorna 404 o falla, recurre a la portada principal de Promiedos como fallback.
    Soporta la nueva estructura de JSON Next.js.
    """
    url = LEAGUE_URLS.get(league_key.lower())
    if not url:
        logging.warning(f"No se encontró una URL de Promiedos registrada para la liga: {league_key}. Usando portada como fallback.")
        url = "https://www.promiedos.com.ar/"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3"
    }
    
    logging.info(f"Intentando descargar datos deportivos directamente de Promiedos ({url})...")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200 and url != "https://www.promiedos.com.ar/":
            logging.warning(f"URL {url} retornó {response.status_code}. Intentando portada de Promiedos como fallback...")
            url = "https://www.promiedos.com.ar/"
            response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            # Intentar parsear estructura JSON Next.js
            parsed_text = parse_next_data_to_text(response.text, league_key)
            if parsed_text.strip():
                logging.info(f"Extracción exitosa vía JSON Next.js para '{league_key}' (usando {url}).")
                return parsed_text
                
            # Fallback a tabla legacy
            soup = BeautifulSoup(response.text, "html.parser")
            for s in soup(["script", "style", "iframe", "ins", "nav", "footer"]):
                s.decompose()
                
            body_text = ""
            tables = soup.find_all("table")
            for i, table in enumerate(tables):
                body_text += f"\n[Tabla Deportiva {i+1} encontrada en Promiedos]:\n"
                rows = table.find_all("tr")
                for row in rows:
                    cols = [col.get_text().strip() for col in row.find_all(["td", "th"])]
                    body_text += " | ".join(cols) + "\n"
            
            if body_text.strip():
                logging.info(f"Extracción legacy exitosa para '{league_key}' (usando {url}).")
                return body_text
            
            return soup.get_text(separator="\n", strip=True)
        else:
            logging.error(f"Error {response.status_code} al descargar de Promiedos (incluso portada).")
    except Exception as e:
        logging.error(f"Excepción al descargar de Promiedos para {league_key}: {e}")
        
    return ""

def fetch_mundial_complete_data() -> dict:
    """
    Descarga la página del Mundial de Promiedos y retorna un diccionario
    con todos los grupos, fixture y brackets parseados.
    """
    url = "https://www.promiedos.com.ar/league/fifa-world-cup/fjda"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    logging.info(f"Descargando datos estructurados completos del Mundial desde {url}...")
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            next_data_script = soup.find("script", id="__NEXT_DATA__")
            if not next_data_script:
                logging.error("No se encontró el script __NEXT_DATA__ en la página del Mundial.")
                return {}
            
            try:
                data = json.loads(next_data_script.string or "{}")
                page_props = data.get("props", {}).get("pageProps", {})
                body_data = page_props.get("data", {})
            except Exception as e:
                logging.error(f"Error parseando __NEXT_DATA__: {e}")
                return {}
            
            # 1. Parsear tables_groups (Posiciones de los grupos)
            groups = []
            tables_groups = body_data.get("tables_groups", [])
            for tg in tables_groups:
                tables = tg.get("tables", [])
                for t in tables:
                    group_name = t.get("name", "Grupo")
                    table_data = t.get("table", {})
                    rows = table_data.get("rows", [])
                    cols = table_data.get("columns", [])
                    
                    team_list = []
                    for r in rows:
                        team_name = r.get("entity", {}).get("object", {}).get("name", "Equipo")
                        team_colors = r.get("entity", {}).get("object", {}).get("colors", {})
                        vals = r.get("values", [])
                        val_map = {v.get("key"): v.get("value") for v in vals}
                        
                        team_list.append({
                            "pos": r.get("num", 1),
                            "id": r.get("entity", {}).get("object", {}).get("id", ""),
                            "name": team_name,
                            "colors": team_colors,
                            "pts": val_map.get("Points", "0"),
                            "pj": val_map.get("GamePlayed", "0"),
                            "goals": val_map.get("Goals", "0:0"),
                            "ratio": val_map.get("Ratio", "0"),
                            "pg": val_map.get("GamesWon", "0"),
                            "pe": val_map.get("GamesEven", "0"),
                            "pp": val_map.get("GamesLost", "0"),
                            "dest_color": r.get("destination_color", "#fff")
                        })
                    
                    groups.append({
                        "name": group_name,
                        "teams": team_list
                    })
            
            # 2. Parsear games (Partidos de TODAS las fechas de grupos)
            games_list = []
            games_data = body_data.get("games", {})
            filters = games_data.get("filters", [])
            for f in filters:
                filter_name = f.get("name", "Fase de Grupos")
                for g in f.get("games", []):
                    teams = g.get("teams", [])
                    scores = g.get("scores", [])
                    status = g.get("status", {})
                    
                    home = teams[0].get("name") if len(teams) > 0 else "Local"
                    away = teams[1].get("name") if len(teams) > 1 else "Visita"
                    home_goals = scores[0] if len(scores) > 0 else "-"
                    away_goals = scores[1] if len(scores) > 1 else "-"
                    
                    games_list.append({
                        "id": g.get("id"),
                        "stage": filter_name,
                        "home": home,
                        "away": away,
                        "home_goals": home_goals,
                        "away_goals": away_goals,
                        "status": status.get("name", "Prog."),
                        "status_symbol": status.get("symbol_name", "Prog."),
                        "start_time": convert_to_argentina_time(g.get("start_time")),
                        "display_time": g.get("game_time_to_display") or "",
                        "display_status": g.get("game_time_status_to_display") or ""
                    })
            
            # 3. Parsear brackets (Fase eliminatoria)
            brackets_stages = []
            brackets = body_data.get("brackets", {})
            stages = brackets.get("stages", [])
            for s in stages:
                stage_name = s.get("name", "Etapa")
                groups_list = []
                for grp in s.get("groups", []):
                    participants = grp.get("participants", [])
                    part_list = []
                    for p in participants:
                        part_list.append({
                            "name": p.get("entity", {}).get("object", {}).get("name", "Por definir"),
                            "colors": p.get("entity", {}).get("object", {}).get("colors", {})
                        })
                    
                    cruce_games = []
                    for cg in grp.get("games", []):
                        cg_scores = cg.get("scores", [])
                        cruce_games.append({
                            "start_time": convert_to_argentina_time(cg.get("start_time")),
                            "status": cg.get("status", {}).get("name", "Prog."),
                            "scores": cg_scores
                        })
                        
                    groups_list.append({
                        "participants": part_list,
                        "score": grp.get("score", ""),
                        "winner": grp.get("winner", -1),
                        "games": cruce_games
                    })
                
                brackets_stages.append({
                    "name": stage_name,
                    "matches": groups_list
                })
                
            # Adaptador de formato para retrocompatibilidad con WordPress (PHP)
            raw_players_stats = body_data.get("players_statistics", [])
            players_stats_formatted = []
            if isinstance(raw_players_stats, dict):
                for t in raw_players_stats.get("tables", []):
                    players_stats_formatted.append({
                        "name": t.get("name"),
                        "table": {
                            "rows": t.get("rows", [])
                        }
                    })
            else:
                players_stats_formatted = raw_players_stats

            # --- HOTFIX: INYECTAR PARTIDOS DEL 24 DE JUNIO ---
            # La API original de Promiedos omite estos partidos, provocando que la web salte al 28 de junio.
            hotfix_games = [
                {"id": "hf1", "stage": "Fase de Grupos", "home": "Suiza", "away": "Canadá", "home_goals": "-", "away_goals": "-", "status": "Prog.", "status_symbol": "Prog.", "start_time": "24-06-2026 16:00 (Hora Argentina)", "display_time": "", "display_status": ""},
                {"id": "hf2", "stage": "Fase de Grupos", "home": "Bosnia Herzegovina", "away": "Qatar", "home_goals": "-", "away_goals": "-", "status": "Prog.", "status_symbol": "Prog.", "start_time": "24-06-2026 16:00 (Hora Argentina)", "display_time": "", "display_status": ""},
                {"id": "hf3", "stage": "Fase de Grupos", "home": "Escocia", "away": "Brasil", "home_goals": "-", "away_goals": "-", "status": "Prog.", "status_symbol": "Prog.", "start_time": "24-06-2026 19:00 (Hora Argentina)", "display_time": "", "display_status": ""},
                {"id": "hf4", "stage": "Fase de Grupos", "home": "Marruecos", "away": "Haití", "home_goals": "-", "away_goals": "-", "status": "Prog.", "status_symbol": "Prog.", "start_time": "24-06-2026 19:00 (Hora Argentina)", "display_time": "", "display_status": ""},
                {"id": "hf5", "stage": "Fase de Grupos", "home": "Sudáfrica", "away": "Corea del Sur", "home_goals": "-", "away_goals": "-", "status": "Prog.", "status_symbol": "Prog.", "start_time": "24-06-2026 22:00 (Hora Argentina)", "display_time": "", "display_status": ""},
                {"id": "hf6", "stage": "Fase de Grupos", "home": "República Checa", "away": "México", "home_goals": "-", "away_goals": "-", "status": "Prog.", "status_symbol": "Prog.", "start_time": "24-06-2026 22:00 (Hora Argentina)", "display_time": "", "display_status": ""}
            ]
            games_list.extend(hotfix_games)

            return {
                "groups": groups,
                "games": games_list,
                "brackets": { "stages": brackets_stages },
                "players_statistics": players_stats_formatted,
                "last_updated": "Fase de Grupos"
            }
        else:
            logging.error(f"Error HTTP {response.status_code} al descargar datos del Mundial.")
    except Exception as e:
        logging.error(f"Excepción al descargar datos estructurados del Mundial: {e}")
    return {}

def search_backup_stats(query: str) -> str:
    """
    Función de búsqueda web de respaldo. 
    REGLA ESTRICTA: Solo se permiten consultas de F1/Fórmula 1. 
    Para fútbol, está terminantemente prohibido usar esta función.
    """
    q_lower = query.lower()
    is_f1 = any(x in q_lower for x in ["f1", "formula 1", "gp", "grand prix", "colapinto", "mercedes", "alpine", "verstappen", "hamilton"])
    
    if not is_f1:
        logging.info("Búsqueda web de respaldo ignorada para fútbol (regla estricta: solo Promiedos).")
        return "Búsqueda web desactivada para fútbol por directiva editorial. Todo dato futbolístico debe extraerse de Promiedos."
        
    encoded_query = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    logging.info(f"Realizando búsqueda de respaldo de F1 para: '{query}'")
    import time
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                results = soup.find_all("div", class_="result")
                snippets = []
                
                for r in results[:8]:
                    title = r.find("a", class_="result__snippet")
                    link = r.find("a", class_="result__url")
                    if title and link:
                        snippets.append(f"Fuente: {link.get('href')} | Info: {title.get_text().strip()}")
                
                return "\n\n".join(snippets)
            elif response.status_code == 403 or response.status_code == 429:
                logging.warning(f"DuckDuckGo rate limit. Retrying in 2 seconds (attempt {attempt+1})")
                time.sleep(2)
        except Exception as e:
            logging.error(f"Error en búsqueda de respaldo para '{query}': {e}")
            time.sleep(2)
            
    return "No se pudo obtener información de F1 de respaldo."

def search_web_for_verification(query: str) -> str:
    """
    Realiza una búsqueda web rápida en DuckDuckGo HTML para verificación de hechos (fact-checking).
    No tiene restricciones de liga o F1, ya que es para auditoría editorial.
    """
    encoded_query = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    logging.info(f"Fact-Checking: buscando en la web para veracidad: '{query}'")
    import time
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                results = soup.find_all("div", class_="result")
                snippets = []
                
                for r in results[:6]:
                    title = r.find("a", class_="result__snippet")
                    link = r.find("a", class_="result__url")
                    if title and link:
                        snippets.append(f"Fuente: {link.get('href')} | Info: {title.get_text().strip()}")
                
                if snippets:
                    return "\n\n".join(snippets)
                return "No se encontraron resultados de búsqueda para corroborar la noticia."
            elif response.status_code == 403 or response.status_code == 429:
                logging.warning(f"DuckDuckGo rate limit. Retrying in 2 seconds (attempt {attempt+1})")
                time.sleep(2)
        except Exception as e:
            logging.error(f"Error al realizar búsqueda de fact-check para '{query}': {e}")
            time.sleep(2)
        
    return "Error al buscar fuentes de verificación en la web."

if __name__ == "__main__":
    print("Probando descarga directa de Promiedos (Mundial)...")
    data = fetch_promiedos_page("mundial")
    print(f"Largo de los datos: {len(data)}")
    print(data[:500])

