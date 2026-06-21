import os
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# ─── Credenciales de API ─────────────────────────────────────────────────────
_keys_raw = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
GEMINI_API_KEYS = [k.strip() for k in _keys_raw.split(",") if k.strip()]
ACTIVE_KEY_INDEX = 0

def get_active_key():
    if not GEMINI_API_KEYS:
        return None
    return GEMINI_API_KEYS[ACTIVE_KEY_INDEX % len(GEMINI_API_KEYS)]

def rotate_key():
    global ACTIVE_KEY_INDEX
    ACTIVE_KEY_INDEX += 1
    import logging
    logging.info(f"Rotando API Key de Gemini (Index: {ACTIVE_KEY_INDEX % len(GEMINI_API_KEYS)})")

# ─── Credenciales de WordPress ───────────────────────────────────────────────
WP_URL      = os.getenv("WP_URL", "https://pasionypelota.com")
WP_USER     = os.getenv("WP_USER", "elrojobruno@gmail.com")
WP_PASSWORD = os.getenv("WP_PASSWORD")

# ─── Canales RSS por clúster semántico ──────────────────────────────────────
# Prioridad SEO: Messi/Selección >= Mundial 2026 > MLS > Brasileirão > LPF Argentina > Liga MX
# > Champions > Libertadores > Premier > LaLiga > Serie A
RSS_FEEDS = {
    # EXCEPCIONES CORE (Siempre vigentes, máxima prioridad de cobertura)
    "messi_seleccion": [
        "https://news.google.com/rss/search?q=Lionel+Messi&hl=es-419&gl=AR&ceid=AR:es-419",
        "https://news.google.com/rss/search?q=Seleccion+Argentina+de+futbol&hl=es-419&gl=AR&ceid=AR:es-419",
    ],

    # FÓRMULA 1 (Tráfico global masivo y alta fidelidad)
    "f1": [
        "https://lat.motorsport.com/rss/f1/news/",
        "https://e00-marca.uecdn.es/rss/motor/formula1.xml",
    ],

    # CLÚSTER 1 — MLS (Alto RPM: tráfico USA)
    "mls_usa": [
        "https://www.mlssoccer.com/rss/news",
        "https://www.espn.com/espn/rss/soccer/news",          # incluye MLS
    ],
    # CLÚSTER 2 — Brasileirão (Volumen masivo Sudamérica)
    "brasil": [
        "https://ge.globo.com/rss/ge.xml",
        "https://www.espn.com.br/espn/rss/futebol",
    ],

    # CLÚSTER 3 — Liga Profesional Argentina (Alta retención/fandom)
    "argentina": [
        "https://www.ole.com.ar/rss/futbol-primera-division/",
        "https://www.ole.com.ar/rss/futbol/",
        "https://www.infobae.com/arc/outboundfeeds/rss/category/deportes/",
        "https://www.youtube.com/feeds/videos.xml?channel_id=UC-ty00L1Av_avCNT_xw5vNQ",
    ],

    # CLÚSTER 4 — Liga MX (Tráfico cruzado USA/México)
    "mexico": [
        "https://www.record.com.mx/rss",
        "https://www.mediotiempo.com/rss",
    ],

    # MACRO-EVENTO — Copa Mundial 2026 (Tráfico global masivo)
    "mundial_2026": [
        "https://www.fifa.com/rss-feeds/news/",
        "https://www.espn.com/espn/rss/soccer/news",
    ],

    # CHAMPIONS LEAGUE / LIBERTADORES
    "copas_continentales": [
        "https://www.uefa.com/rssfeed/championsleague/newsfeeds/news/",
        "https://www.conmebol.com/feed/",
    ],

    # LaLiga / España (fuerte tracción LATAM)
    "espana": [
        "https://e00-marca.uecdn.es/rss/futbol.xml",
        "https://e00-marca.uecdn.es/rss/futbol/primera-division.xml",
        "https://www.mundodeportivo.com/rss/futbol",
    ],

    # Premier League (alta monetización RPM)
    "premier": [
        "https://www.bbc.com/sport/football/rss.xml",
        "https://www.skysports.com/rss/12040",
    ],

    # Global
    "global": [
        "https://www.espn.com.ar/espn/rss/futbol",
        "https://www.goal.com/feeds/news",
    ],
}

# ─── Periodistas a monitorear en X ──────────────────────────────────────────
JOURNALISTS_TO_MONITOR = [
    # Fichajes globales
    {"name": "Fabrizio Romano",     "handle": "FabrizioRomano",  "region": "global"},
    {"name": "David Ornstein",      "handle": "David_Ornstein",  "region": "premier"},
    {"name": "Gianluca Di Marzio",  "handle": "DiMarzio",        "region": "italia"},
    {"name": "Matteo Moretto",      "handle": "MatteMoretto",    "region": "espana"},
    # Argentina / Sudamérica
    {"name": "Gastón Edul",         "handle": "gastonedul",      "region": "argentina"},
    {"name": "Germán García Grova", "handle": "GerGarciaGrova",  "region": "argentina"},
    {"name": "César Luis Merlo",    "handle": "CLMerlo",         "region": "sudamerica"},
    {"name": "Brian Pécora",        "handle": "BrianEPecora",    "region": "argentina"},
    # Brasil
    {"name": "Jorge Nicola",        "handle": "jorgenicola",     "region": "brasil"},
    # México / MLS
    {"name": "Tom Bogert",          "handle": "tombogert",       "region": "mls"},
    {"name": "Transfermarkt MX",    "handle": "TMmercados",      "region": "mexico"},
]

# ─── ESTRATEGIA DE NODOS SEMÁNTICOS ─────────────────────────────────────────
# Usada por los agentes para priorizar, redactar y optimizar artículos.

SEO_CLUSTERS = {
    # ── EXCEPCIÓN MÁXIMA CORE: LIONEL MESSI Y SELECCIÓN ARGENTINA ───────────
    "messi_seleccion": {
        "priority": 1,
        "label": "Lionel Messi y Selección Argentina",
        "category_wp": "Fútbol Argentino",
        "lsi_keywords": [
            "goles de Messi hoy",
            "partido de la seleccion argentina en vivo",
            "desempeño de Messi Inter Miami",
            "formacion seleccion argentina",
            "proximo partido de Argentina",
        ],
        "core_entities": ["Lionel Messi", "Argentina", "Scaloni", "Inter Miami CF"],
        "monetization": "VERY_HIGH",
    },

    "f1": {
        "priority": 2,
        "label": "Fórmula 1",
        "category_wp": "F1",
        "lsi_keywords": [
            "posiciones formula 1 2026",
            "proxima carrera de f1 hoy en vivo",
            "campeonato de pilotos f1",
            "horarios f1 proximo gran premio",
            "resultados formula 1",
        ],
        "core_entities": ["Franco Colapinto", "Lewis Hamilton", "Max Verstappen", "Ferrari", "Red Bull Racing", "Mercedes F1"],
        "monetization": "HIGH",
    },

    # ── NIVEL 0: MACRO-EVENTO (Mayor prioridad absoluta) ────────────────────
    "mundial_2026": {
        "priority": 1,
        "label": "Copa Mundial FIFA 2026",
        "category_wp": "Mundial 2026",
        "lsi_keywords": [
            "fase de grupos Mundial 2026 en vivo",
            "simulador de cruces octavos de final",
            "probabilidad de clasificación Mundial 2026",
            "sedes Mundial 2026 USA México Canadá",
            "tabla de posiciones Mundial 2026",
            "fixture completo Copa del Mundo 2026",
        ],
        "core_entities": ["Argentina", "Brasil", "Francia", "España", "Uruguay",
                          "Inter Miami", "LAFC", "Estadio Azteca"],
        "monetization": "VERY_HIGH",  # RPM máximo por tráfico USA
    },

    # ── NIVEL 1A: MLS (Alto RPM) ─────────────────────────────────────────────
    "mls": {
        "priority": 2,
        "label": "Major League Soccer",
        "category_wp": "MLS",
        "lsi_keywords": [
            "franquicias MLS 2026",
            "límite salarial MLS jugadores designados",
            "impacto comercial sedes Mundial 2026",
            "Inter Miami CF tráfico Florida",
            "tabla de posiciones MLS Conferencia Este",
            "playoffs MLS 2026",
            "expansion teams MLS",
        ],
        "core_entities": ["Inter Miami CF", "LAFC", "Atlanta United",
                          "Lionel Messi", "Lorenzo Insigne"],
        "monetization": "VERY_HIGH",  # Tráfico USA = RPM alto
    },

    # ── NIVEL 1B: BRASILEIRÃO (Volumen masivo) ───────────────────────────────
    "brasileirao": {
        "priority": 3,
        "label": "Brasileirão Série A",
        "category_wp": "Brasileirão",
        "lsi_keywords": [
            "mercado de pases Brasileirão",
            "clasificación Copas Libertadores Brasil",
            "xG promesas exportables Brasileirão",
            "tabla posiciones Brasileirão 2026",
            "goleadores Série A Brasil",
            "VAR Brasileirão controversias",
        ],
        "core_entities": ["CR Flamengo", "SE Palmeiras", "São Paulo FC",
                          "Atlético Mineiro", "Corinthians"],
        "monetization": "HIGH",
    },

    # ── NIVEL 1C: LIGA PROFESIONAL ARGENTINA ─────────────────────────────────
    "lpf_argentina": {
        "priority": 4,
        "label": "Liga Profesional de Fútbol Argentina",
        "category_wp": "Fútbol Argentino",
        "lsi_keywords": [
            "mercado de pases fútbol argentino 2026",
            "clubes inhibidos por la FIFA",
            "fichajes liga profesional argentina",
            "inhibición de la FIFA para incorporar",
            "rumores de pases Boca River San Lorenzo Independiente",
            "nuevos refuerzos fútbol argentino",
            "sanciones FIFA clubes argentinos",
        ],
        "core_entities": ["River Plate", "Boca Juniors", "Racing Club",
                          "Club Atlético Huracán", "San Lorenzo", "Independiente"],
        "monetization": "HIGH",  # Alta retención, usuarios recurrentes
    },

    # ── NIVEL 1D: LIGA MX ────────────────────────────────────────────────────
    "liga_mx": {
        "priority": 5,
        "label": "Liga MX",
        "category_wp": "Liga MX",
        "lsi_keywords": [
            "tabla Liga MX Clausura 2026",
            "Liguilla Liga MX resultados",
            "Clásico Nacional América vs Chivas",
            "Clásico Regio Rayados vs Tigres",
            "transferencias Liga MX",
            "Leagues Cup 2026 Liga MX vs MLS",
        ],
        "core_entities": ["Club América", "CF Monterrey", "Chivas de Guadalajara",
                          "Club Tigres UANL", "Cruz Azul"],
        "monetization": "HIGH",  # Tráfico cruzado USA/México
    },

    # ── NIVEL 2A: UEFA CHAMPIONS LEAGUE ──────────────────────────────────────
    "champions": {
        "priority": 6,
        "label": "UEFA Champions League",
        "category_wp": "Champions League",
        "lsi_keywords": [
            "tabla general Champions en vivo formato suizo",
            "clasificación octavos de final Champions",
            "sorteo fase eliminatoria Champions 2026",
            "goleadores Champions League",
            "posiciones fase de liga Champions",
            "coeficientes UEFA ranking clubes",
        ],
        "core_entities": ["Real Madrid", "Manchester City", "Bayern München",
                          "FC Barcelona", "PSG", "Arsenal"],
        "monetization": "HIGH",
    },

    # ── NIVEL 2B: COPA LIBERTADORES ──────────────────────────────────────────
    "libertadores": {
        "priority": 7,
        "label": "Copa Libertadores",
        "category_wp": "Copa Libertadores",
        "lsi_keywords": [
            "cuadro de cruces Libertadores 2026",
            "historial de enfrentamientos CONMEBOL",
            "ventaja de localía altura clima Libertadores",
            "grupos Copa Libertadores tabla",
            "mejores equipos Libertadores histórico",
            "final Copa Libertadores 2026",
        ],
        "core_entities": ["Flamengo", "River Plate", "Boca Juniors",
                          "Palmeiras", "Estudiantes", "Nacional"],
        "monetization": "MEDIUM_HIGH",
    },

    # ── NIVEL 3: PREMIER LEAGUE ──────────────────────────────────────────────
    "premier": {
        "priority": 8,
        "label": "Premier League",
        "category_wp": "Premier League",
        "lsi_keywords": [
            "tabla Premier League 2026",
            "estadísticas xG Premier League",
            "clasificación Champions Premier League",
            "fichajes Premier League enero 2026",
            "goleadores Premier League temporada",
        ],
        "core_entities": ["Manchester City", "Arsenal", "Liverpool",
                          "Chelsea", "Manchester United", "Tottenham"],
        "monetization": "VERY_HIGH",  # Mayor RPM histórico
    },

    # ── NIVEL 3: LaLiga ──────────────────────────────────────────────────────
    "laliga": {
        "priority": 9,
        "label": "LaLiga EA Sports",
        "category_wp": "LaLiga",
        "lsi_keywords": [
            "tabla LaLiga 2026",
            "derbi madrileño Real Madrid Atlético",
            "El Clásico Barcelona Real Madrid",
            "goleadores LaLiga temporada actual",
            "fichajes LaLiga enero 2026",
        ],
        "core_entities": ["Real Madrid", "FC Barcelona", "Atlético de Madrid",
                          "Athletic Club", "Real Sociedad", "Sevilla FC"],
        "monetization": "HIGH",
    },
}

# ─── ENTIDADES JUGADOR FRANQUICIA ────────────────────────────────────────────
# Tier 1: Volumen masivo de búsqueda
PLAYER_ENTITIES_TIER1 = {
    "Kylian Mbappé": {
        "club": "Real Madrid", "selección": "Francia",
        "lsi": ["mapa de calor Mbappé Mundial 2026", "goles Mbappé Real Madrid 2026",
                "Mbappé lesión regreso", "Mbappé mejor jugador"],
    },
    "Vinícius Júnior": {
        "club": "Real Madrid", "selección": "Brasil",
        "lsi": ["Vinicius Jr goles 2026", "Balón de Oro Vinicius",
                "Vinicius estadísticas Champions", "Vinicius Brasil Mundial"],
    },
    "Erling Haaland": {
        "club": "Manchester City", "selección": "Noruega",
        "lsi": ["xG Haaland vs Big Six", "goles Haaland Premier League",
                "Haaland récord goleador", "Haaland Champions League"],
    },
    "Jude Bellingham": {
        "club": "Real Madrid", "selección": "Inglaterra",
        "lsi": ["Bellingham goles Real Madrid", "Bellingham Mundial 2026 Inglaterra",
                "Bellingham estadísticas 2026"],
    },
    "Lamine Yamal": {
        "club": "FC Barcelona", "selección": "España",
        "lsi": ["Lamine Yamal edad récord", "Yamal estadísticas LaLiga",
                "Yamal España Mundial 2026", "mejor joven del mundo 2026"],
    },
}

# Tier 2: Tráfico táctico/especializado
PLAYER_ENTITIES_TIER2 = {
    "Florian Wirtz":  {"club": "Bayern München",  "selección": "Alemania"},
    "Jamal Musiala":  {"club": "Bayern München",  "selección": "Alemania"},
    "Phil Foden":     {"club": "Manchester City", "selección": "Inglaterra"},
    "Pedri":          {"club": "FC Barcelona",    "selección": "España"},
    "Raphinha":       {"club": "FC Barcelona",    "selección": "Brasil"},
    "Cole Palmer":    {"club": "Chelsea",         "selección": "Inglaterra"},
}

# ─── DIRECTIVA DE REDACCIÓN SEO ──────────────────────────────────────────────
EDITORIAL_DIRECTIVE = """
DIRECTIVA DE REDACCIÓN PANAMERICANA Y REGLAS DE CONTENIDO:

1. REGLA ESTRICTA DE LIGAS DE CLUBES Y FÚTBOL ARGENTINO:
   - Para cualquier liga o copa de clubes (MLS, Brasileirão, Liga Profesional Argentina, Liga MX, Premier League, LaLiga, Serie A, Champions League, Libertadores, etc.), la cobertura debe centrarse ÚNICAMENTE en el MERCADO DE PASES (fichajes, rumores de traspaso, renovaciones, salidas, llegadas de jugadores o técnicos) o en CLUBES INHIBIDOS POR LA FIFA.
   - REGLA DE ORO DE FÚTBOL ARGENTINO: En la categoría y temática de "Fútbol Argentino" (lpf_argentina), TODAS las notas sin excepción deben ser sobre el mercado de pases (fichajes, rumores de pases, salidas, llegadas) o sobre clubes inhibidos por la FIFA (sanciones, deudas e inhibiciones oficiales). No se permite ninguna otra temática (como partidos del torneo local, rendimiento deportivo, crónicas de la liga local, etc.).
   - Queda estrictamente prohibido publicar crónicas de partidos regulares de liga, resultados de partidos, análisis tácticos locales, o fixtures y tablas que no estén directamente ligados a un traspaso.

2. EXCEPCIONES CORE ABSOLUTAS:
   - LIONEL MESSI: Se permite cualquier noticia sobre él de manera incondicional (goles, récords, partidos jugados, lesiones, rendimiento o futuro).
   - SELECCIÓN ARGENTINA: Se permite la cobertura total de su desempeño, resultados de partidos, previas, tácticas, convocatorias y noticias en general.
   - COPA MUNDIAL 2026: Cobertura total autorizada (partidos, resultados, clasificaciones, sedes, fixtures, simulaciones, etc.).
   - FÓRMULA 1 (F1): Cobertura completa de carreras, resultados, clasificación de pilotos y constructores, rumores de escuderías, con prioridad en la estrella emergente Franco Colapinto, Hamilton, Verstappen y escuderías históricas como Ferrari y Red Bull.

3. PRIORIDAD DE COBERTURA (mayor a menor):
   Lionel Messi / Selección Argentina / Copa Mundial 2026 → Fórmula 1 (F1) → MLS → Brasileirão → LPF Argentina → Liga MX → Champions League → Libertadores → Premier League → LaLiga

4. INTEGRACIÓN DE DATOS ESTADÍSTICOS OBLIGATORIOS:
   - Incluir siempre: xG (Expected Goals), estadísticas recientes, posición en tabla o valor de mercado (según corresponda).
   - Para noticias de mercado de pases, destacar las estadísticas actuales del jugador en su club actual y su valor Transfermarkt.
   - EVITAR: biografías estáticas. PREFERIR: análisis de rendimiento y mercado de pases actual.

5. LSI KEYWORDS: Incluir al menos 2-3 términos LSI del clúster correspondiente de forma natural en el texto.

6. ESTRUCTURA DE ARTÍCULO:
   - Párrafo 1: Lead con entidad principal + dato estadístico clave.
   - H2 #1: Contexto táctico/estadístico (o detalles del rumor/fichaje).
   - H2 #2: Impacto en el equipo o en el mercado de pases.
   - H2 #3: Proyección futura.
   - Cierre: Llamado a la acción implícito.

7. TABLAS DE DATOS: Incluir siempre una tabla HTML con estadísticas (goles, asistencias, partidos, valor) para aumentar el tiempo de retención.

8. AUDIENCIA PANAMERICANA: Español neutro de alta calidad.
"""

# ─── Afiliados por equipo/liga ───────────────────────────────────────────────
AFFILIATE_LINKS = {
    "real madrid":    '<div class="affiliate-box"><strong>👕 Camiseta Real Madrid</strong><br><a href="TU_ENLACE_AMAZON" target="_blank" rel="nofollow noopener">Ver oferta en Amazon →</a></div>',
    "barcelona":      '<div class="affiliate-box"><strong>👕 Camiseta FC Barcelona</strong><br><a href="TU_ENLACE_AMAZON" target="_blank" rel="nofollow noopener">Ver oferta en Amazon →</a></div>',
    "boca juniors":   '<div class="affiliate-box"><strong>👕 Camiseta Boca Juniors</strong><br><a href="TU_ENLACE_AMAZON" target="_blank" rel="nofollow noopener">Ver oferta en Amazon →</a></div>',
    "river plate":    '<div class="affiliate-box"><strong>👕 Camiseta River Plate</strong><br><a href="TU_ENLACE_AMAZON" target="_blank" rel="nofollow noopener">Ver oferta en Amazon →</a></div>',
    "manchester city":'<div class="affiliate-box"><strong>👕 Camiseta Man City</strong><br><a href="TU_ENLACE_AMAZON" target="_blank" rel="nofollow noopener">Ver oferta en Amazon →</a></div>',
    "inter miami":    '<div class="affiliate-box"><strong>👕 Camiseta Inter Miami</strong><br><a href="TU_ENLACE_AMAZON" target="_blank" rel="nofollow noopener">Ver oferta en Amazon →</a></div>',
    "flamengo":       '<div class="affiliate-box"><strong>👕 Camiseta Flamengo</strong><br><a href="TU_ENLACE_AMAZON" target="_blank" rel="nofollow noopener">Ver oferta en Amazon →</a></div>',
    "club america":   '<div class="affiliate-box"><strong>👕 Camiseta Club América</strong><br><a href="TU_ENLACE_AMAZON" target="_blank" rel="nofollow noopener">Ver oferta en Amazon →</a></div>',
    "generico":       '<div class="affiliate-box"><strong>⚽ Las mejores camisetas de fútbol</strong><br><a href="TU_ENLACE_AMAZON_GENERICO" target="_blank" rel="nofollow noopener">Ver todas las ofertas en Amazon →</a></div>',
}

# ─── Base de datos local ─────────────────────────────────────────────────────
DATABASE_FILE = os.path.join(os.path.dirname(__file__), "database.json")
