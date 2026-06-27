import sys
import requests
import logging

sys.path.append("/Users/cristianbruno/Downloads/PAGINA WEB FUTBOL")
import config
from requests.auth import HTTPBasicAuth

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    auth = HTTPBasicAuth(config.WP_USER, config.WP_PASSWORD)
    placeholders = ['{goles}', '{asistencias}', '{tactical_rating}', '{expected_goals}', '{partidos}', '{horario}', '{resultado}']
    
    # Fetch posts (status = publish, draft, private, etc.)
    logger.info("Fetching posts to clean placeholders...")
    r = requests.get(f"{config.WP_URL.rstrip('/')}/wp-json/wp/v2/posts?per_page=100&status=any", auth=auth, timeout=30)
    if r.status_code != 200:
        logger.error(f"Failed to fetch posts: {r.status_code}")
        return
        
    posts = r.json()
    logger.info(f"Retrieved {len(posts)} posts. Starting scan...")
    
    updated_count = 0
    for p in posts:
        pid = p.get("id")
        title_obj = p.get("title", {})
        title_raw = title_obj.get("raw") or title_obj.get("rendered") or ""
        content_raw = p.get("content", {}).get("raw") or p.get("content", {}).get("rendered") or ""
        
        has_ph = False
        new_title = title_raw
        new_content = content_raw
        
        for ph in placeholders:
            if ph in new_title:
                new_title = new_title.replace(ph, "-")
                has_ph = True
            if ph in new_content:
                new_content = new_content.replace(ph, "-")
                has_ph = True
                
        if has_ph:
            logger.info(f"Cleaning placeholders in post {pid} '{title_raw[:40]}'...")
            payload = {}
            if title_raw != new_title:
                payload["title"] = new_title
            if content_raw != new_content:
                payload["content"] = new_content
                
            update_res = requests.post(
                f"{config.WP_URL.rstrip('/')}/wp-json/wp/v2/posts/{pid}",
                auth=auth,
                json=payload,
                timeout=30
            )
            if update_res.status_code == 200:
                logger.info(f"Successfully cleaned post {pid}.")
                updated_count += 1
            else:
                logger.error(f"Failed to update post {pid}: {update_res.status_code} - {update_res.text[:200]}")
                
    logger.info(f"Scan finished. Cleaned {updated_count} posts.")

if __name__ == "__main__":
    main()
