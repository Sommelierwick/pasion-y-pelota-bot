"""
tools/images.py — Búsqueda de imágenes reales de fútbol con licencias y atribución (Wikimedia Commons).
"""

import requests
import re
import logging
import random
from bs4 import BeautifulSoup
from typing import Optional, Dict

logger = logging.getLogger(__name__)

def clean_html_text(html_str: str) -> str:
    """Elimina etiquetas HTML y limpia espacios en blanco."""
    if not html_str:
        return ""
    try:
        soup = BeautifulSoup(html_str, "html.parser")
        text = soup.get_text()
        return re.sub(r'\s+', ' ', text).strip()
    except Exception:
        # Fallback si BeautifulSoup falla
        return re.sub(r'<[^>]*>', '', html_str).strip()

def search_wikimedia_commons(query: str, exclude_urls: list = None) -> Optional[Dict[str, str]]:
    """
    Busca una imagen en Wikimedia Commons para el término dado.
    Devuelve un diccionario con {'url': ..., 'citation': ...} o None si no hay resultados.
    """
    search_url = "https://commons.wikimedia.org/w/api.php"
    headers = {
        "User-Agent": "PasionYPelotaBot/1.0 (contact: elrojobruno@gmail.com) Python-requests/2.31.0"
    }

    # Intentamos primero buscar en el espacio de nombres de archivos (namespace 6)
    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": f"file:{query}",
        "srnamespace": 6,
        "srlimit": 10
    }

    try:
        logger.info(f"Buscando imagen real en Wikimedia Commons para: '{query}'")
        r = requests.get(search_url, params=params, headers=headers, timeout=10)
        if r.status_code != 200:
            logger.error(f"Error en API Wikimedia ({r.status_code})")
            return None
            
        data = r.json()
        search_results = data.get("query", {}).get("search", [])

        # Si no hay resultados específicos, buscamos de forma general en Commons
        if not search_results:
            logger.info("Sin resultados en File:. Intentando búsqueda general...")
            params["srsearch"] = query
            r = requests.get(search_url, params=params, headers=headers, timeout=10)
            if r.status_code == 200:
                search_results = r.json().get("query", {}).get("search", [])

        # Filtrar y buscar la primera imagen válida (jpg, jpeg, png)
        for res in search_results:
            title = res.get("title", "")
            if not title.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue

            pageid = res.get("pageid")
            if not pageid:
                continue

            # Obtener detalles de la imagen (URL directa y metadatos)
            info_params = {
                "action": "query",
                "format": "json",
                "prop": "imageinfo",
                "iiprop": "url|extmetadata",
                "pageids": pageid
            }
            info_r = requests.get(search_url, params=info_params, headers=headers, timeout=10)
            if info_r.status_code != 200:
                continue

            info_data = info_r.json()
            pages = info_data.get("query", {}).get("pages", {})
            page_info = pages.get(str(pageid), {})
            imageinfo_list = page_info.get("imageinfo", [])
            if not imageinfo_list:
                continue

            imageinfo = imageinfo_list[0]
            url = imageinfo.get("url")
            extmetadata = imageinfo.get("extmetadata", {})

            if not url:
                continue

            if exclude_urls and url in exclude_urls:
                logger.info(f"Saltando imagen duplicada ya usada anteriormente: {url}")
                continue

            # Extraer y limpiar metadatos de autoría y crédito
            artist_html = extmetadata.get("Artist", {}).get("value", "")
            license_name = extmetadata.get("LicenseShortName", {}).get("value", "CC")
            credit_html = extmetadata.get("Credit", {}).get("value", "")

            artist = clean_html_text(artist_html) or "Colaborador de Wikimedia"
            credit = clean_html_text(credit_html) or "Wikimedia Commons"

            # Acortar créditos muy largos o con URLs feas
            if "https://" in credit and len(credit) > 60:
                credit = "Wikimedia Commons"

            citation = f"Foto: {artist} ({credit}) / Licencia {license_name}"
            
            logger.info(f"Imagen encontrada: {url} | Citación: {citation}")
            return {
                "url": url,
                "citation": citation
            }

    except Exception as e:
        logger.error(f"Excepción al buscar imagen en Wikimedia Commons: {e}")

    return None

def get_football_image(player_name, team_name=None, exclude_urls: list = None) -> Dict[str, str]:
    """
    Busca una imagen real del jugador. Si falla, busca por el equipo.
    Si ambos fallan, busca una genérica de fútbol/estadio.
    Soporta que player_name o team_name sean listas o strings.
    """
    # 1. Intentar buscar con el nombre del jugador
    if isinstance(player_name, list):
        for name in player_name:
            if name and isinstance(name, str) and name.lower() not in ["desconocido", "ninguno", ""]:
                res = search_wikimedia_commons(name, exclude_urls=exclude_urls)
                if res:
                    return res
        player_name = player_name[0] if player_name else ""

    if player_name and isinstance(player_name, str) and player_name.lower() not in ["desconocido", "ninguno", ""]:
        res = search_wikimedia_commons(player_name, exclude_urls=exclude_urls)
        if res:
            return res

    # 2. Intentar buscar con el nombre del equipo
    if isinstance(team_name, list):
        for t in team_name:
            if t and isinstance(t, str) and t.lower() not in ["desconocido", "ninguno", ""]:
                res = search_wikimedia_commons(t, exclude_urls=exclude_urls)
                if res:
                    return res
        team_name = team_name[0] if team_name else ""

    if team_name and isinstance(team_name, str) and team_name.lower() not in ["desconocido", "ninguno", ""]:
        res = search_wikimedia_commons(team_name, exclude_urls=exclude_urls)
        if res:
            return res

    # 3. Fallback genérico de alta calidad de Wikimedia (iterando para variedad)
    generic_terms = ["association football match", "soccer stadium", "football training", "futbol"]
    random.shuffle(generic_terms)
    for term in generic_terms:
        res = search_wikimedia_commons(term, exclude_urls=exclude_urls)
        if res:
            return res

    # 4. Fallback absoluto cableado (imagen libre conocida de Wikimedia)
    return {
        "url": "https://upload.wikimedia.org/wikipedia/commons/c/cf/Football_in_Scunthorpe.jpg",
        "citation": "Foto: Scunthorpe (Wikimedia Commons) / Licencia CC BY-SA 2.0"
    }

if __name__ == "__main__":
    # Test directo
    print(get_football_image("Kylian Mbappe"))
    print(get_football_image("", "Fenerbahce"))
