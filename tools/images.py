"""
tools/images.py — Búsqueda de imágenes reales de fútbol con licencias y atribución (Wikimedia Commons)
y generación de imágenes premium mediante IA (Flux en la nube o Gemini Imagen) como fallback de calidad.
Incluye un Inspector Editorial Multimodal de Imágenes que revisa la idoneidad antes de subirlas.
"""

import requests
import re
import logging
import random
import os
import uuid
import base64
import time
import json
from bs4 import BeautifulSoup
from typing import Optional, Dict
import config

logger = logging.getLogger(__name__)

# Palabras clave para excluir imágenes de fútbol americano, rugby y otros deportes no deseados
EXCLUDED_SPORTS_KEYWORDS = [
    "american football", "nfl", "gridiron", "quarterback", "touchdown", 
    "super bowl", "superbowl", "helmet", "ncaa football", "college football", 
    "cfl", "canadian football", "rugby", "football card", "vintage football",
    "american football player", "pro bowl"
]

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
    Devuelve un diccionario con {'url': ..., 'citation': ...} o None si no hay resultados o están excluidos.
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
            categories = extmetadata.get("Categories", {}).get("value", "")
            image_desc_html = extmetadata.get("ImageDescription", {}).get("value", "")

            # Limpiar HTML
            artist = clean_html_text(artist_html) or "Colaborador de Wikimedia"
            credit = clean_html_text(credit_html) or "Wikimedia Commons"
            image_desc = clean_html_text(image_desc_html)

            # --- FILTRO ANTI-FÚTBOL AMERICANO / RUGBY ---
            check_text = (title + " " + url + " " + categories + " " + image_desc).lower()
            if any(kw in check_text for kw in EXCLUDED_SPORTS_KEYWORDS):
                logger.info(f"Filtro anti-fútbol americano activado. Saltando imagen: {title}")
                continue

            # Acortar créditos muy largos o con URLs feas
            if "https://" in credit and len(credit) > 60:
                credit = "Wikimedia Commons"

            citation = f"Foto: {artist} ({credit}) / Licencia {license_name}"
            
            logger.info(f"Imagen válida de fútbol encontrada: {url} | Citación: {citation}")
            return {
                "url": url,
                "citation": citation
            }

    except Exception as e:
        logger.error(f"Excepción al buscar imagen en Wikimedia Commons: {e}")

    return None

def verify_image_suitability_text_fallback(filename: str, article_title: str) -> bool:
    """
    Usa Groq (Llama 3.3 70B) como fallback para evaluar si la imagen es apta basándose únicamente
    en el nombre del archivo y el título del artículo (cuando Gemini está bajo límite de cuota).
    """
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        logger.warning("No hay GROQ_API_KEY configurada para la verificación de imagen de respaldo. Aprobando por defecto.")
        return True

    system_prompt = "Eres un Inspector de Contenido Editorial para un portal de fútbol premium."
    prompt = f"""
    Evalúa si la siguiente imagen es adecuada para un artículo de fútbol asociación (soccer) en nuestro portal.
    
    Título del artículo: "{article_title}"
    Nombre de archivo de la imagen: "{filename}"
    
    Criterios de rechazo:
    - La imagen representa fútbol americano, NFL, rugby, béisbol u otros deportes ajenos al fútbol asociación.
    - La imagen es de fútbol playa (beach soccer) o futsal (a menos que el título del artículo hable explícitamente de fútbol playa o futsal).
    - La imagen representa políticos, presidentes, mandatarios o banderas nacionales.
    - La imagen representa ciudades, castillos, catedrales, paisajes o edificios turísticos fuera del contexto de un partido de fútbol.
    
    Responde únicamente con un objeto JSON con esta estructura:
    {{
        "is_suitable": true o false,
        "reason": "Explicación breve de por qué se aprueba o rechaza"
    }}
    """
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {groq_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }
    
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            result = resp.json()
            content = result["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            is_suitable = parsed.get("is_suitable", True)
            reason = parsed.get("reason", "")
            if not is_suitable:
                logger.warning(f"❌ Imagen RECHAZADA por Groq (Fallback de Texto) para '{article_title}'. Razón: {reason}")
                return False
            else:
                logger.info(f"✅ Imagen aprobada por Groq (Fallback de Texto): {reason}")
                return True
    except Exception as e:
        logger.error(f"Error en fallback de verificación de texto con Groq: {e}")
    return True


def verify_image_suitability(image_url_or_path: str, article_title: str) -> bool:
    """
    Verifica si una imagen es apta para el artículo de fútbol asociación:
    1. Filtra localmente por palabras clave prohibidas en el nombre de archivo/URL.
    2. Usa el modelo multimodal de Gemini para inspección visual.
    3. Si Gemini falla (429/500), recurre a Groq para análisis de texto basado en el nombre del archivo.
    """
    if not article_title:
        return True

    # 1. Filtro local basado en palabras clave en la URL/nombre del archivo (Case-Insensitive)
    filename_clean = os.path.basename(image_url_or_path).lower().replace("%20", " ").replace("_", " ").replace("-", " ")
    reject_keywords = [
        "american_football", "american-football", "american football", "gridiron", "quarterback", "touchdown", 
        "superbowl", "helmet", "rugby", "baseball", "cricket", "basketball", "volleyball",
        "tennis", "golf", "athletics", "swimming", "boxing",
        "beach_soccer", "beach-soccer", "beachsoccer", "beach soccer", "sand_soccer", "sand soccer", "futsal", "indoor_soccer",
        "futbol_playa", "futbol-playa", "playa_futbol", "playa-futbol", "playa futbol", "futbol playa",
        "biden", "putin", "trump", "obama", "xi_jinping", "macron", "merkel", "politician", 
        "president", "minister", "senate", "parliament", "congress", "government",
        "politico", "presidente", "ministro", "parlamento", "congreso", "gobierno",
        "cathedral", "castle", "church", "palace", "monument", "cityscape", "landscape", 
        "skyline", "temple", "museum", "ruins", "bridge", "street_view",
        "catedral", "castillo", "iglesia", "palacio", "monumento", "templo", "museo", "ruinas", "puente",
        "flag_of", "map_of", "coat_of_arms", "emblem", "shield", "bandera", "mapa", "escudo"
    ]
    for kw in reject_keywords:
        if kw in filename_clean:
            logger.warning(f"❌ Imagen RECHAZADA localmente por palabra clave prohibida '{kw}' en el nombre de archivo: {os.path.basename(image_url_or_path)}")
            return False

    api_key = config.get_active_key()
    if not api_key:
        logger.warning("No hay API Key activa para Gemini. Aprobando por regla Regex (Fallback).")
        return True

    try:
        # Obtener los bytes de la imagen
        is_local = not image_url_or_path.startswith(("http://", "https://"))
        if is_local:
            local_path = image_url_or_path
            if local_path.startswith("file://"):
                local_path = local_path.replace("file://", "", 1)
            if not os.path.exists(local_path):
                logger.warning(f"No se encontró el archivo local para verificar: {local_path}")
                return False
            with open(local_path, "rb") as f:
                img_content = f.read()
        else:
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(image_url_or_path, headers=headers, timeout=15)
            if r.status_code != 200:
                logger.warning(f"No se pudo descargar la imagen para verificar: {image_url_or_path} (HTTP {r.status_code})")
                return False
            img_content = r.content

        # Redimensionar/optimizar la imagen usando PIL
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(img_content))
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.thumbnail((384, 384))
        out_io = io.BytesIO()
        img.save(out_io, format="JPEG", quality=75)
        optimized_bytes = out_io.getvalue()
        b64_data = base64.b64encode(optimized_bytes).decode("utf-8")

        # Llamar a la API Multimodal de Gemini
        import time
        logger.info("⏳ Aplicando Delay Inteligente de 15 segundos para evitar Rate Limits (429) en validación visual...")
        time.sleep(15)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        
        prompt = f"""
        You are the Editorial Image Inspector for a premium soccer website 'Pasión y Pelota'.
        Analyze this image and the article title: "{article_title}".
        Verify if the image depicts a soccer match, soccer player, soccer stadium, or generic soccer elements (like a soccer ball/pitch) that fit the article.
        
        CRITICAL REJECTION CRITERIA (Return false if):
        - The image depicts American football (NFL/college, gridiron, quarterbacks, oval ball, helmets).
        - The image depicts rugby.
        - The image depicts a politician (e.g. Vladimir Putin, Joe Biden).
        - The image is a map, flag, document, or abstract logo/emblem (unless it's directly relevant, but generally reject flags/emblems as cover images).
        - The image is a landscape, city photo, or unrelated building.
        - The image is completely out of context for a soccer news portal.
        
        Return a JSON object with this exact structure:
        {{
            "is_suitable": true or false,
            "reason": "Brief explanation of why it is suitable or rejected."
        }}
        """

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inlineData": {
                                "mimeType": "image/jpeg",
                                "data": b64_data
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT",
                    "properties": {
                        "is_suitable": {"type": "BOOLEAN"},
                        "reason": {"type": "STRING"}
                    },
                    "required": ["is_suitable", "reason"]
                }
            }
        }

        r_api = requests.post(url, json=payload, headers=headers, timeout=20)
        if r_api.status_code == 200:
            result = r_api.json()
            candidates = result.get("candidates", [])
            if candidates:
                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                eval_data = json.loads(text)
                is_suitable = eval_data.get("is_suitable", True)
                reason = eval_data.get("reason", "")
                if not is_suitable:
                    logger.warning(f"❌ Imagen rechazada por el inspector multimodal para '{article_title}'. Razón: {reason}")
                    return False
                else:
                    logger.info(f"✅ Imagen aprobada por el inspector multimodal: {reason}")
                    return True
        elif r_api.status_code == 429:
            logger.warning("Quota límite excedida (429) en verificación de imagen de Gemini. Aprobando por regla Regex (Fallback).")
            config.rotate_key()
            return True
        else:
            logger.warning(f"Fallo en llamada a la API de verificación de imagen de Gemini ({r_api.status_code}). Aprobando por regla Regex (Fallback).")
            return True

    except Exception as e:
        logger.error(f"Excepción al verificar idoneidad de imagen con Gemini: {e}. Aprobando por regla Regex (Fallback).")
        return True

    return True

def generate_image_prompt_via_llm(title: str, content: str = "") -> str:
    """
    Usa gemini-2.5-flash para generar un prompt detallado en inglés para la generación de imágenes con Imagen/Flux.
    """
    import time
    logger.info("⏳ Aplicando Delay Inteligente de 15 segundos para evitar Rate Limits (429)...")
    time.sleep(15)

    api_key = config.get_active_key()
    if not api_key:
        logger.warning("No hay API Key activa de Gemini para generar el prompt.")
        return ""
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    prompt_payload = f"""
    Based on the following soccer article title and content, write a highly detailed descriptive prompt in English for an AI image generator (like Flux).
    The image must be a highly realistic, professional action sports photograph of a soccer match or soccer player, matching the style of a real live broadcast or sports magazine photo (like Getty Images).
    
    Guidelines:
    1. Describe the scene: action on the pitch, players contesting for the ball, or a key player exhibiting genuine emotion (e.g. celebration, disappointment).
    2. Specify the setting: lush green grass field, massive stadium background, bright stadium lights, professional sports camera style, 16:9 aspect ratio.
    3. Include jersey descriptions matching the teams if mentioned.
    4. Utilize professional photographic terminology: specify lens (e.g., '85mm lens', 'f/1.8'), camera parameters ('motion blur', 'hyper-realistic', 'film grain'), and dynamic stadium lighting.
    5. Ensure a dramatic, emotional, or epic composition that guarantees high visual engagement and viral appeal on social media.
    6. Explicitly forbid and avoid any text/typography (except numbers on jerseys or legibly rendered scoreboards if relevant to the context), cartoons, drawings, 3D renders, or digital art style.
    7. Output ONLY the image generation prompt as a single paragraph (maximum 120 words). No introduction, no markdown, no quotes.
    
    Article Title: {title}
    Article Content: {content[:800]}
    """
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt_payload}]
        }]
    }
    
    try:
        logger.info("Generando prompt de imagen premium usando Gemini 2.5 Flash...")
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        if r.status_code == 200:
            result = r.json()
            candidates = result.get("candidates", [])
            if candidates:
                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                # Limpiar comillas y formato markdown
                text = text.replace('"', '').replace('`', '').strip()
                logger.info(f"Prompt generado con éxito: '{text}'")
                return text
        logger.warning(f"No se pudo generar el prompt con LLM ({r.status_code}): {r.text}")
    except Exception as e:
        logger.error(f"Excepción al generar prompt con LLM: {e}")
        
    return ""

def optimize_image_for_web(filepath: str, max_size_kb: int = 150) -> bool:
    """
    Optimiza una imagen local para la web:
    - La redimensiona a un tamaño máximo de 1024x576 (o mantiene relación 16:9).
    - La guarda en formato JPEG comprimido.
    - Reduce la calidad progresivamente si excede max_size_kb hasta quedar por debajo.
    """
    try:
        from PIL import Image
        if not os.path.exists(filepath):
            return False
            
        img = Image.open(filepath)
        if img.mode != "RGB":
            img = img.convert("RGB")
            
        # Redimensionar si es más grande de lo necesario para web
        max_width = 1024
        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_height = int(float(img.height) * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
        quality = 85
        temp_path = filepath + ".tmp"
        
        while quality >= 30:
            img.save(temp_path, format="JPEG", quality=quality, optimize=True)
            size_kb = os.path.getsize(temp_path) / 1024
            if size_kb <= max_size_kb:
                break
            quality -= 5
            
        if os.path.exists(temp_path):
            os.replace(temp_path, filepath)
            logger.info(f"✅ Imagen optimizada para la web: {os.path.getsize(filepath)/1024:.1f} KB (Calidad: {quality})")
            return True
    except Exception as e:
        logger.error(f"Error al optimizar imagen para la web: {e}")
    return False

def generate_pollinations_image(prompt: str) -> Optional[Dict[str, str]]:
    """
    Genera una imagen usando la API gratuita e ilimitada de Pollinations.ai (modelo Flux).
    """
    import urllib.parse
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    temp_dir = os.path.join(project_root, "temp_images")
    os.makedirs(temp_dir, exist_ok=True)
    local_path = os.path.join(temp_dir, f"pollinations_img_{uuid.uuid4().hex[:8]}.jpg")
    
    encoded_prompt = urllib.parse.quote(prompt)
    seed = int(time.time())
    url = (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        f"?width=1024&height=576"
        f"&model=flux&nologo=true&enhance=true&seed={seed}"
    )
    
    try:
        logger.info("Llamando a Pollinations.ai (Flux) en la nube de forma gratuita...")
        r = requests.get(url, timeout=45)
        if r.status_code == 200:
            with open(local_path, "wb") as f:
                f.write(r.content)
            optimize_image_for_web(local_path)
            logger.info(f"✅ Imagen generada con éxito por Pollinations.ai en: {local_path}")
            return {
                "url": local_path,
                "citation": "Foto: Generada por IA (Flux Pollinations) / Licencia Libre (Ilustración IA)"
            }
        logger.warning(f"Error llamando a Pollinations.ai ({r.status_code}): {r.text[:200]}")
    except Exception as e:
        logger.error(f"Excepción llamando a Pollinations.ai: {e}")
        
    return None

def generate_huggingface_image(prompt: str) -> Optional[Dict[str, str]]:
    """
    Genera una imagen usando Hugging Face Inference API (modelo FLUX.1-schnell) con un token gratuito.
    """
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        logger.warning("No hay HF_TOKEN configurado en el archivo .env para el fallback de HuggingFace.")
        return None
        
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    temp_dir = os.path.join(project_root, "temp_images")
    os.makedirs(temp_dir, exist_ok=True)
    local_path = os.path.join(temp_dir, f"hf_img_{uuid.uuid4().hex[:8]}.jpg")
    
    url = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": prompt,
        "parameters": {
            "width": 1024,
            "height": 576
        }
    }
    
    try:
        logger.info("Llamando a Hugging Face Inference API (Flux.1-schnell) de respaldo...")
        r = requests.post(url, json=payload, headers=headers, timeout=45)
        if r.status_code == 200:
            with open(local_path, "wb") as f:
                f.write(r.content)
            optimize_image_for_web(local_path)
            logger.info(f"✅ Imagen generada con éxito por Hugging Face en: {local_path}")
            return {
                "url": local_path,
                "citation": "Foto: Generada por IA (Flux HuggingFace) / Licencia Libre (Ilustración IA)"
            }
        logger.warning(f"Error llamando a Hugging Face ({r.status_code}): {r.text[:200]}")
    except Exception as e:
        logger.error(f"Excepción llamando a Hugging Face: {e}")
        
    return None

def generate_flux_image(prompt: str) -> Optional[Dict[str, str]]:
    """
    Intenta generar una imagen usando la API de Flux en la nube (Fal.ai o Replicate) si las llaves están configuradas.
    """
    fal_key = os.getenv("FAL_KEY")
    replicate_token = os.getenv("REPLICATE_API_TOKEN")
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    temp_dir = os.path.join(project_root, "temp_images")
    os.makedirs(temp_dir, exist_ok=True)
    local_path = os.path.join(temp_dir, f"flux_img_{uuid.uuid4().hex[:8]}.jpg")

    # 1. Intentar Fal.ai (Flux Schnell)
    if fal_key:
        logger.info("Llamando a Fal.ai en la nube para generar imagen con Flux.1...")
        url = "https://queue.fal.run/fal-ai/flux/schnell"
        headers = {
            "Authorization": f"Key {fal_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "prompt": prompt,
            "image_size": "landscape_16_9",
            "sync_mode": True
        }
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=30)
            if r.status_code == 200:
                data = r.json()
                images = data.get("images", [])
                if images:
                    img_url = images[0].get("url")
                    if img_url:
                        # Descargar la imagen
                        img_r = requests.get(img_url, timeout=15)
                        if img_r.status_code == 200:
                            with open(local_path, "wb") as f:
                                f.write(img_r.content)
                            optimize_image_for_web(local_path)
                            logger.info(f"✅ Imagen generada con éxito por Flux (Fal.ai) en: {local_path}")
                            return {
                                "url": local_path,
                                "citation": "Foto: Generada por IA (Flux.1 Fal.ai) / Licencia Libre (Ilustración IA)"
                            }
            logger.warning(f"Error llamando a Fal.ai ({r.status_code}): {r.text}")
        except Exception as e:
            logger.error(f"Excepción llamando a Fal.ai: {e}")

    # 2. Intentar Replicate (Flux Schnell)
    if replicate_token:
        logger.info("Llamando a Replicate en la nube para generar imagen con Flux.1...")
        url = "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions"
        headers = {
            "Authorization": f"Token {replicate_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "input": {
                "prompt": prompt,
                "aspect_ratio": "16:9"
            }
        }
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=20)
            if r.status_code in [200, 201]:
                prediction = r.json()
                poll_url = prediction.get("urls", {}).get("get")
                
                if poll_url:
                    # Polling
                    for _ in range(15):  # Máximo 15 segundos
                        time.sleep(1)
                        poll_r = requests.get(poll_url, headers=headers, timeout=10)
                        if poll_r.status_code == 200:
                            p_data = poll_r.json()
                            status = p_data.get("status")
                            if status == "succeeded":
                                output = p_data.get("output", [])
                                if output:
                                    img_url = output[0]
                                    img_r = requests.get(img_url, timeout=15)
                                    if img_r.status_code == 200:
                                        with open(local_path, "wb") as f:
                                            f.write(img_r.content)
                                        optimize_image_for_web(local_path)
                                        logger.info(f"✅ Imagen generada con éxito por Flux (Replicate) en: {local_path}")
                                        return {
                                            "url": local_path,
                                            "citation": "Foto: Generada por IA (Flux.1 Replicate) / Licencia Libre (Ilustración IA)"
                                        }
                                break
                            elif status in ["failed", "canceled"]:
                                logger.warning(f"La predicción de Replicate falló o fue cancelada. Estado: {status}")
                                break
            else:
                logger.warning(f"Error iniciando predicción en Replicate ({r.status_code}): {r.text}")
        except Exception as e:
            logger.error(f"Excepción llamando a Replicate: {e}")

    return None

def generate_ai_image(prompt: str) -> Optional[Dict[str, str]]:
    """
    Genera una imagen usando Flux en la nube (comenzando por opciones gratuitas como Pollinations
    o Hugging Face, luego Fal.ai/Replicate de pago y finalmente Gemini Imagen).
    Almacena los resultados optimizados en la carpeta local 'temp_images'.
    """
    # 1. Intentar Pollinations.ai (Flux gratis sin límites ni keys)
    res_pollinations = generate_pollinations_image(prompt)
    if res_pollinations:
        return res_pollinations

    # 2. Intentar Hugging Face Inference API (Flux.1-schnell gratis de respaldo)
    res_hf = generate_huggingface_image(prompt)
    if res_hf:
        return res_hf

    # 3. Intentar Flux en la nube (si FAL_KEY o REPLICATE_API_TOKEN están configuradas)
    flux_res = generate_flux_image(prompt)
    if flux_res:
        return flux_res
        
    # 4. Si fallan, recurrir a Gemini Imagen
    api_key = config.get_active_key()
    if not api_key:
        logger.warning("No hay API Key configurada para Gemini Imagen.")
        return None

    models_to_try = [
        "imagen-4.0-generate-001",
        "imagen-4.0-fast-generate-001",
        "imagen-3.0-generate-002"
    ]
    
    headers = {"Content-Type": "application/json"}
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "16:9"
        }
    }
    
    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:predict?key={api_key}"
        try:
            logger.info(f"Intentando generar imagen mediante Gemini {model}...")
            r = requests.post(url, json=payload, headers=headers, timeout=45)
            if r.status_code == 200:
                data = r.json()
                predictions = data.get("predictions", [])
                if predictions:
                    b64_data = predictions[0].get("bytesBase64Encoded")
                    if b64_data:
                        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                        temp_dir = os.path.join(project_root, "temp_images")
                        os.makedirs(temp_dir, exist_ok=True)
                        
                        filename = f"ai_img_{uuid.uuid4().hex[:8]}.jpg"
                        local_path = os.path.join(temp_dir, filename)
                        
                        img_bytes = base64.b64decode(b64_data)
                        with open(local_path, "wb") as f:
                            f.write(img_bytes)
                        optimize_image_for_web(local_path)
                        logger.info(f"✅ Imagen generada con éxito por Gemini Imagen ({model}) en {local_path}")
                        return {
                            "url": local_path,
                            "citation": "Foto: Generada por IA (Gemini Imagen) / Licencia Libre (Ilustración IA)"
                        }
            elif r.status_code == 400 and "only available on paid plans" in r.text:
                logger.warning(f"El modelo {model} requiere una cuenta de pago (Free Tier activo).")
            else:
                logger.warning(f"Error de API con modelo {model} ({r.status_code}): {r.text[:200]}")
        except Exception as e:
            logger.error(f"Excepción al llamar al modelo {model}: {e}")
            
    return None

def get_football_image(player_name, team_name=None, exclude_urls: list = None, article_title: str = "", article_content: str = "") -> Dict[str, str]:
    """
    Busca una imagen real del jugador o equipo en Wikimedia Commons (con filtro anti-fútbol-americano).
    Si no encuentra una específica, y disponemos de contexto del artículo, genera una imagen hiperrealista por IA (Flux/Imagen).
    Si falla la IA, recurre a los fallbacks genéricos de Wikimedia.
    """
    try:
        # 1. Intentar buscar con el nombre del jugador en Wikimedia Commons
        if isinstance(player_name, list):
            for name in player_name:
                if name and isinstance(name, str) and name.lower() not in ["desconocido", "ninguno", ""]:
                    # Intentamos con sufijo deportivo primero para evitar coincidencias homónimas extrañas
                    # El filtro anti-fútbol-americano en search_wikimedia_commons asegura que no se traiga NFL
                    for q in [f"{name} soccer", f"{name} association football", f"{name} football", name]:
                        res = search_wikimedia_commons(q, exclude_urls=exclude_urls)
                        if res:
                            # Verificar idoneidad multimodal si hay título
                            if article_title:
                                if verify_image_suitability(res["url"], article_title):
                                    return res
                                else:
                                    if not exclude_urls:
                                        exclude_urls = []
                                    exclude_urls.append(res["url"])
                                    continue
                            return res
            player_name = player_name[0] if player_name else ""

        if player_name and isinstance(player_name, str) and player_name.lower() not in ["desconocido", "ninguno", ""]:
            for q in [f"{player_name} soccer", f"{player_name} association football", f"{player_name} football", player_name]:
                res = search_wikimedia_commons(q, exclude_urls=exclude_urls)
                if res:
                    # Verificar idoneidad multimodal si hay título
                    if article_title:
                        if verify_image_suitability(res["url"], article_title):
                            return res
                        else:
                            if not exclude_urls:
                                exclude_urls = []
                            exclude_urls.append(res["url"])
                            continue
                    return res

        # 2. Intentar buscar con el nombre del equipo con sufijos deportivos específicos
        teams_to_try = []
        if isinstance(team_name, list):
            teams_to_try = [t for t in team_name if t and isinstance(t, str) and t.lower() not in ["desconocido", "ninguno", ""]]
        elif team_name and isinstance(team_name, str) and team_name.lower() not in ["desconocido", "ninguno", ""]:
            teams_to_try = [team_name]

        for t in teams_to_try:
            queries_to_try = [
                f"{t} national football team",
                f"Selección de fútbol de {t}",
                f"{t} football club",
                f"{t} soccer",
                f"{t} stadium",
                f"{t} football"
            ]
            for q in queries_to_try:
                res = search_wikimedia_commons(q, exclude_urls=exclude_urls)
                if res:
                    # Verificar idoneidad multimodal si hay título
                    if article_title:
                        if verify_image_suitability(res["url"], article_title):
                            return res
                        else:
                            if not exclude_urls:
                                exclude_urls = []
                            exclude_urls.append(res["url"])
                            continue
                    return res

        # --- FALLBACK A IA (IMAGEN DE ALTA CALIDAD ESPECÍFICA) ---
        if article_title:
            logger.info(f"No se encontró imagen real específica para '{player_name}' / '{team_name}'. Iniciando fallback de generación con IA...")
            ai_prompt = generate_image_prompt_via_llm(article_title, article_content)
            if ai_prompt:
                res = generate_ai_image(ai_prompt)
                if res:
                    # Also verify AI generated images just in case
                    if verify_image_suitability(res["url"], article_title):
                        return res
                    else:
                        # If AI generated something invalid, delete the temporary file
                        try:
                            local_path = res["url"].replace("file://", "", 1)
                            if os.path.exists(local_path):
                                os.remove(local_path)
                        except Exception:
                            pass

        # 3. Fallback genérico de alta calidad de Wikimedia (si la IA falló o no había título)
        generic_terms = ["association football match", "soccer stadium", "soccer match action", "futbol"]
        random.shuffle(generic_terms)
        for term in generic_terms:
            res = search_wikimedia_commons(term, exclude_urls=exclude_urls)
            if res:
                return res

    except Exception as e:
        logger.error(f"Excepción general en get_football_image: {e}. Recurriendo a fallback absoluto.")

    # 4. Fallback absoluto cableado (imagen libre conocida de Wikimedia)
    return {
        "url": "https://upload.wikimedia.org/wikipedia/commons/c/cf/Football_in_Scunthorpe.jpg",
        "citation": "Foto: Scunthorpe (Wikimedia Commons) / Licencia CC BY-SA 2.0"
    }

if __name__ == "__main__":
    # Test directo
    logging.basicConfig(level=logging.INFO)
    print(get_football_image("Kylian Mbappe"))
    print(get_football_image("", "Fenerbahce"))
