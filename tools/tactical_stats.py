import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

def convert_to_gmt3(utc_timestamp_str: str) -> str:
    """
    Obligatorio: Convierte cualquier timestamp de la API a la zona horaria Argentina (GMT-3).
    Soporta formato ISO 8601 (ej. '2026-06-24T18:00:00+00:00' o '2026-06-24T18:00:00Z').
    """
    try:
        # Reemplazar Z por +00:00 para facilitar el parseo
        if utc_timestamp_str.endswith('Z'):
            utc_timestamp_str = utc_timestamp_str[:-1] + '+00:00'
            
        dt_utc = datetime.fromisoformat(utc_timestamp_str)
        tz_arg = pytz.timezone('America/Argentina/Buenos_Aires')
        dt_arg = dt_utc.astimezone(tz_arg)
        
        # Devolver en formato amigable
        return dt_arg.strftime('%d-%m-%Y %H:%M')
    except Exception as e:
        logger.warning(f"Error al convertir fecha a GMT-3 ({utc_timestamp_str}): {e}")
        return utc_timestamp_str

def fetch_player_tactical_stats(player_name: str) -> dict:
    """
    Conecta a la API táctica (ej. API-Football o Sofascore) para extraer el rating y el xG.
    Actualmente devuelve datos simulados (Mock) debido al bloqueo antibot, 
    listo para reemplazar por la petición real con API Key.
    """
    logger.info(f"Buscando estadísticas tácticas avanzadas para: {player_name}")
    
    # Aquí iría el código real de requests.get() a la API con tu API Key
    # Ejemplo:
    # url = f"https://v3.football.api-sports.io/players?search={player_name}"
    # headers = {"x-apisports-key": "TU_API_KEY"}
    # response = requests.get(url, headers=headers)
    
    # MOCK DATA para mantener la operatividad de la arquitectura y la IA
    mock_utc_time = "2026-06-24T20:00:00+00:00" # Horario UTC
    gmt3_time = convert_to_gmt3(mock_utc_time) # Se convierte estrictamente a GMT-3
    
    # Simulamos un rating y xG realista
    tactical_data = {
        "rating": "8.2",
        "expected_goals": "0.75",
        "last_match_time_gmt3": gmt3_time
    }
    
    logger.info(f"Datos tácticos extraídos: Rating {tactical_data['rating']}, xG {tactical_data['expected_goals']} (Hora GMT-3: {gmt3_time})")
    
    return tactical_data
