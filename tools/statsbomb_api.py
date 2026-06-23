import os
import json
import logging
from typing import Dict, Any

try:
    from statsbombpy import sb
except ImportError:
    sb = None

logger = logging.getLogger(__name__)

CACHE_FILE = "cache/statsbomb_wc2022.json"

def build_cache():
    """Descarga y calcula métricas avanzadas para todos los jugadores del Mundial 2022."""
    if not sb:
        logger.error("statsbombpy no está instalado.")
        return {}
        
    logger.info("Construyendo caché de StatsBomb para el Mundial 2022...")
    os.makedirs("cache", exist_ok=True)
    
    try:
        # 43 = FIFA World Cup, 106 = 2022
        matches = sb.matches(competition_id=43, season_id=106)
        match_ids = matches["match_id"].tolist()
    except Exception as e:
        logger.error(f"Error fetching matches: {e}")
        return {}

    player_stats = {}
    
    # Process only a subset or all matches? All 64 matches might take 1-2 minutes to download
    # but we only do it once. Let's do it!
    for mid in match_ids:
        try:
            events = sb.events(match_id=mid)
            
            # Filter shots
            if 'shot_statsbomb_xg' in events.columns and 'player' in events.columns:
                shots = events[events['type'] == 'Shot'].dropna(subset=['player'])
                for _, row in shots.iterrows():
                    player = row['player']
                    xg = row.get('shot_statsbomb_xg', 0.0)
                    if player not in player_stats:
                        player_stats[player] = {'xg': 0.0, 'shots': 0, 'key_passes': 0}
                    
                    player_stats[player]['xg'] += xg if not type(xg) is str else float(xg)
                    player_stats[player]['shots'] += 1
                    
            # Filter passes (Key passes)
            if 'pass_shot_assist' in events.columns and 'player' in events.columns:
                key_passes = events[(events['type'] == 'Pass') & (events['pass_shot_assist'] == True)].dropna(subset=['player'])
                for _, row in key_passes.iterrows():
                    player = row['player']
                    if player not in player_stats:
                        player_stats[player] = {'xg': 0.0, 'shots': 0, 'key_passes': 0}
                    player_stats[player]['key_passes'] += 1
                    
        except Exception as e:
            logger.warning(f"Error procesando match {mid}: {e}")
            continue

    # Round xG to 2 decimals
    for p in player_stats:
        player_stats[p]['xg'] = round(player_stats[p]['xg'], 2)

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(player_stats, f, ensure_ascii=False, indent=2)
        
    logger.info(f"Caché construida con {len(player_stats)} jugadores.")
    return player_stats

def get_player_historical_stats(player_name: str) -> Dict[str, Any]:
    """Retorna las estadísticas históricas de StatsBomb para un jugador (Mundial 2022)."""
    if not os.path.exists(CACHE_FILE):
        stats = build_cache()
    else:
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                stats = json.load(f)
        except Exception:
            stats = build_cache()
            
    if not stats:
        return {}
        
    import unicodedata
    def normalize_name(s: str) -> str:
        return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii').lower()

    p_normalized = normalize_name(player_name)
    for name, data in stats.items():
        if p_normalized in normalize_name(name):
            return {
                "name": name,
                "xg": data.get("xg", 0.0),
                "shots": data.get("shots", 0),
                "key_passes": data.get("key_passes", 0)
            }
            
    return {}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(get_player_historical_stats("Messi"))
    print(get_player_historical_stats("Mbappe"))
