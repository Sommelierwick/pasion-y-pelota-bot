import os
import json
import logging
from typing import Dict, Any, List
import copy

logger = logging.getLogger(__name__)

HISTORICAL_STATS_FILE = "historical_stats.json"

def detect_statistical_anomalies(current_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Compara las estadísticas actuales (current_data) con el snapshot guardado.
    Retorna una lista de anomalías (si las hay) para activar el Agente Estadístico.
    """
    anomalies = []
    
    if not os.path.exists(HISTORICAL_STATS_FILE):
        logger.info("No hay historial estadístico previo. Creando el primer snapshot.")
        _save_snapshot(current_data)
        return anomalies
        
    try:
        with open(HISTORICAL_STATS_FILE, "r", encoding="utf-8") as f:
            historical_data = json.load(f)
    except Exception as e:
        logger.error(f"Error leyendo el historial estadístico: {e}")
        return anomalies
        
    # Analizar Grupos (Cambios de Posición, Diferencias de Gol, etc.)
    hist_groups = _index_teams_by_group(historical_data.get("groups", []))
    curr_groups = _index_teams_by_group(current_data.get("groups", []))
    
    for group_name, teams in curr_groups.items():
        for team in teams.values():
            team_name = team.get("name")
            hist_team = hist_groups.get(group_name, {}).get(team_name)
            
            if hist_team:
                # Gatillo 1: Cambio radical de posición (Ej. cae del puesto 1 o 2 al puesto 3 o 4)
                hist_pos = int(hist_team.get("pos", 0))
                curr_pos = int(team.get("pos", 0))
                
                # Ejemplo de anomalía: el equipo cayó de zona de clasificación (1-2) a eliminación (3-4)
                if hist_pos <= 2 and curr_pos > 2:
                    anomalies.append({
                        "type": "Caída en Tabla",
                        "team": team_name,
                        "group": group_name,
                        "description": f"El equipo ha caído de la posición {hist_pos} a la {curr_pos}, quedando temporalmente fuera de la clasificación.",
                        "data": team
                    })
                # O viceversa: entró sorpresivamente a zona de clasificación
                elif hist_pos > 2 and curr_pos <= 2:
                    anomalies.append({
                        "type": "Ascenso en Tabla",
                        "team": team_name,
                        "group": group_name,
                        "description": f"El equipo ha subido de la posición {hist_pos} a la {curr_pos}, ingresando a la zona de clasificación.",
                        "data": team
                    })
                
                # Gatillo 2: Diferencia de gol anómala (goleada)
                # Extraer goles a favor y en contra de "goals" (ej. "3:1")
                def parse_goals(goal_str):
                    parts = str(goal_str).split(":")
                    if len(parts) == 2:
                        try:
                            return int(parts[0]), int(parts[1])
                        except:
                            return 0, 0
                    return 0, 0
                
                hist_gf, hist_gc = parse_goals(hist_team.get("goals", "0:0"))
                curr_gf, curr_gc = parse_goals(team.get("goals", "0:0"))
                
                new_gf = curr_gf - hist_gf
                new_gc = curr_gc - hist_gc
                
                # Si en un partido metió 4 o más goles, o recibió 4 o más goles
                if new_gf >= 4:
                    anomalies.append({
                        "type": "Goleada Histórica a Favor",
                        "team": team_name,
                        "group": group_name,
                        "description": f"El equipo ha anotado una cifra asombrosa de {new_gf} goles desde la última medición.",
                        "data": team
                    })
                if new_gc >= 4:
                    anomalies.append({
                        "type": "Goleada Histórica en Contra",
                        "team": team_name,
                        "group": group_name,
                        "description": f"El equipo ha recibido una cantidad crítica de {new_gc} goles desde la última medición.",
                        "data": team
                    })
                    
    # Analizar Eliminatorias (Si un grande queda fuera)
    # Por ahora el Mundial 2026 no ha llegado ahí, pero dejamos la puerta abierta.
    # ...

    # Guardar nuevo snapshot si hubo cambios en los datos evaluados
    _save_snapshot(current_data)
    
    return anomalies

def _index_teams_by_group(groups: list) -> dict:
    """Retorna un dict: {'Grupo A': {'Argentina': {...team_data...}}}"""
    index = {}
    for g in groups:
        g_name = g.get("name")
        index[g_name] = {}
        for team in g.get("teams", []):
            index[g_name][team.get("name")] = team
    return index

def _save_snapshot(data: Dict[str, Any]):
    try:
        with open(HISTORICAL_STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error guardando el historial estadístico: {e}")
