import sys
import logging
import requests
from requests.auth import HTTPBasicAuth
from collections import defaultdict
import re

sys.path.append("/Users/cristianbruno/Downloads/PAGINA WEB FUTBOL")
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Topics and keywords to group posts
TOPICS = {
    "boca_arruabarrena": ["arruabarrena", "zeballos", "boca"],
    "river_coudet": ["coudet", "river", "núñez", "nunez"],
    "racing_vojvoda": ["vojvoda", "racing", "milito", "saja"],
    "independiente_inhibiciones": ["independiente", "quinteros", "inhibiciones"],
    "san_lorenzo_muniain": ["muniain", "san lorenzo", "boedo", "ciclón", "ciclon"],
    "real_madrid_mourinho": ["mourinho", "real madrid", "bernabéu", "bernabeu"],
    "barca_flick": ["flick", "barça", "barcelona", "culé", "cule"],
    "atletico_simeone": ["simeone", "atlético", "atletico", "colchonero"],
    "city_rodri": ["rodri", "etihad", "maresca", "city"],
    "liverpool_iraola": ["iraola", "anfield", "liverpool", "luis díaz", "luis diaz"],
    "arsenal_arteta": ["arteta", "arsenal", "odegaard", "gunner"],
    "flamengo_jardim": ["jardim", "flamengo", "mengão", "mengao"],
    "palmeiras_ferreira": ["abel ferreira", "palmeiras", "verdão", "verdao", "estêvão", "estevao"],
    "america_almada": ["almada", "américa", "america", "águilas", "aguilas"],
    "cruz_azul_huiqui": ["huiqui", "cruz azul", "la noria", "cemento"],
    "inter_miami_hoyos": ["hoyos", "inter miami", "garzas", "mls"],
    "nacional_rueda": ["rueda", "atlético nacional", "atletico nacional", "verdolaga"],
    "junior_arias": ["arias", "junior", "tiburón", "tiburon", "barranquilla"],
    "messi_jordania": ["messi", "jordania", "scaloni", "banquillo", "cargas"],
    "daniel_zabala_huracan": ["zabala", "huracán", "huracan", "globo"],
    "belgica_iran": ["bélgica", "belgica", "irán", "iran", "grupo g"],
}

def get_post_topic(title, content):
    title_lower = title.lower()
    content_lower = content.lower()
    
    # Check match based on keywords
    for topic, keywords in TOPICS.items():
        # Require at least 2 keywords to match or 1 if it's unique enough
        match_count = sum(1 for kw in keywords if kw in title_lower or kw in content_lower)
        if match_count >= 2:
            return topic
        elif topic in ["racing_vojvoda", "san_lorenzo_muniain", "boca_arruabarrena", "real_madrid_mourinho", "palmeiras_ferreira"] and keywords[0] in title_lower:
            return topic
            
    return None

def deduplicate(dry_run=True):
    auth = HTTPBasicAuth(config.WP_USER, config.WP_PASSWORD)
    
    logger.info("Obteniendo todos los posts publicados...")
    r = requests.get(f"{config.WP_URL.rstrip('/')}/wp-json/wp/v2/posts?per_page=100&status=publish", auth=auth, timeout=30)
    if r.status_code != 200:
        logger.error(f"Error al obtener posts: {r.status_code}")
        return
        
    posts = r.json()
    logger.info(f"Se obtuvieron {len(posts)} posts publicados.")
    
    social_by_topic = defaultdict(list)
    main_by_topic = defaultdict(list)
    
    unclassified_social = []
    unclassified_main = []
    
    for p in posts:
        p_id = p["id"]
        title = p["title"]["rendered"]
        content = p["content"]["rendered"]
        is_social = 303 in p.get("categories", [])
        
        topic = get_post_topic(title, content)
        if topic:
            if is_social:
                social_by_topic[topic].append(p)
            else:
                main_by_topic[topic].append(p)
        else:
            if is_social:
                unclassified_social.append(p)
            else:
                unclassified_main.append(p)
                
    def process_group(group_name, posts_list, label):
        if len(posts_list) <= 1:
            return 0
            
        posts_sorted = sorted(posts_list, key=lambda x: x["id"], reverse=True)
        keep_post = posts_sorted[0]
        duplicate_posts = posts_sorted[1:]
        
        logger.info(f"[{label}] Tema '{group_name}': Manteniendo ID {keep_post['id']} ('{keep_post['title']['rendered'][:40]}')")
        
        drafted_count = 0
        for dup in duplicate_posts:
            dup_id = dup["id"]
            dup_title = dup["title"]["rendered"]
            logger.info(f"  -> 🚨 Duplicado detectado: ID {dup_id} ('{dup_title[:40]}')")
            
            if not dry_run:
                patch_url = f"{config.WP_URL.rstrip('/')}/wp-json/wp/v2/posts/{dup_id}"
                resp = requests.patch(patch_url, json={"status": "draft"}, auth=auth, timeout=15)
                if resp.status_code == 200:
                    logger.info(f"     ✅ ID {dup_id} movido a borrador exitosamente.")
                    drafted_count += 1
                else:
                    logger.error(f"     ❌ Fallo al mover ID {dup_id} a borrador: HTTP {resp.status_code}")
            else:
                logger.info(f"     [Simulación] Se movería a borrador.")
                drafted_count += 1
                
        return drafted_count

    total_drafted = 0
    
    logger.info("=== PROCESANDO CLONES SOCIALES (303) ===")
    for topic, group in social_by_topic.items():
        total_drafted += process_group(topic, group, "SOCIAL")
        
    logger.info("=== PROCESANDO NOTAS PRINCIPALES ===")
    for topic, group in main_by_topic.items():
        total_drafted += process_group(topic, group, "MAIN")
        
    logger.info(f"Deduplicación finalizada. Total posts {'simulados para borrar' if dry_run else 'movidos a borrador'}: {total_drafted}")

if __name__ == "__main__":
    dry = True
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        dry = False
    deduplicate(dry_run=dry)
