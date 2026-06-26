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
import urllib.parse
from bs4 import BeautifulSoup
from PIL import Image
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



def build_image_query(entity_type: str, entity_name: str) -> str:
    """Construye el string de consulta con sufijos deportivos obligatorios."""
    if not entity_name or entity_name.lower() in ["desconocido", "ninguno", ""]:
        return ""
    if entity_type == "team":
        return f"{entity_name} national football team"
    elif entity_type == "player":
        return f"{entity_name} football"
    return f"{entity_name} football"

def strip_watermark(image_path: str) -> str:
    """Recorta el 10% inferior de la imagen para despojarla de marcas de agua."""
    try:
        if not image_path.startswith("file://"):
            return image_path
            
        local_path = image_path.replace("file://", "", 1)
        if not os.path.exists(local_path):
            return image_path
            
        with Image.open(local_path) as img:
            width, height = img.size
            crop_height = int(height * 0.90)  # Conserva el 90% superior
            cropped_img = img.crop((0, 0, width, crop_height))
            
            # Guardamos con el mismo nombre
            cropped_img.save(local_path, quality=95)
        logger.info(f"Watermark strip (10% inferior) aplicado a {local_path}")
        return image_path
    except Exception as e:
        logger.error(f"Error recortando watermark de {image_path}: {e}")
        return image_path




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


def search_tycsports_images(query: str, exclude_urls: list = None) -> Optional[Dict[str, str]]:
    """
    Busca imágenes en TyC Sports extrayendo de su página principal.
    Respeta la directiva de citar la fuente y el contexto.
    """
    if exclude_urls is None:
        exclude_urls = []
        
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        # TyC Sports /busqueda endpoint gives 404 now, so we scrape the homepage for recent relevant images
        url = "https://www.tycsports.com"
        r = requests.get(url, headers=headers, timeout=10)
        
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            images = soup.find_all("img")
            
            # Divide query into keywords
            keywords = [k.lower() for k in query.split() if len(k) > 2]
            
            for img in images:
                src = img.get("data-src") or img.get("src")
                if not src or src.startswith("data:"):
                    continue
                    
                # Filtros estrictos para excluir banners, scoreboards y fixtures
                forbidden_keywords = ["site_image", "default", "logo", "bombero", "dia-del-padre", "cuadro", "fixture", "resultados", "creatividad", "bloque", "semaforo", "partidos"]
                if any(fw in src.lower() for fw in forbidden_keywords):
                    continue
                    
                alt_text = img.get("alt", "").lower()
                if any(fw in alt_text for fw in forbidden_keywords):
                    continue
                
                # Check if alt text contains any of our query keywords
                if not any(kw in alt_text for kw in keywords) and query.lower() not in src.lower():
                    continue
                    
                                # Exclusividad Mundial 2026 (Regla 6)
                if "2026" not in alt_text and "mundial" not in alt_text and "2026" not in src.lower() and "mundial" not in src.lower():
                    continue
                
                # TyC Sports usually serves thumbnails like _416x234.webp, replace for HD
                hd_url = src.replace("_416x234", "_862x485").replace("_416x416", "_862x485").split("?")[0]
                
                # Check exclusion
                if any(hd_url == ex for ex in exclude_urls):
                    continue
                    
                logger.info(f"Imagen válida encontrada en TyC Sports (Scraping Homepage): {hd_url}")
                return {
                    "url": hd_url,
                    "citation": f"Foto: TyC Sports / {img.get('alt', query)}"
                }
    except Exception as e:
        logger.warning(f"Error buscando en TyC Sports: {e}")
        
    return None


def search_cadena3_images(query: str, exclude_urls: list = None) -> Optional[Dict[str, str]]:
    """
    Busca imágenes en Cadena 3 Deportes (sección 45) extraídas de sus notas de Deportes.
    Respeta la directiva de citar la fuente y el contexto.
    """
    if exclude_urls is None:
        exclude_urls = []
        
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        url = "https://www.cadena3.com/seccion/deportes/45"
        r = requests.get(url, headers=headers, timeout=10)
        
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            pictures = soup.find_all("picture", attrs={"data-src": True})
            
            # Divide query into keywords
            keywords = [k.lower() for k in query.split() if len(k) > 2]
            
            for pic in pictures:
                src = pic.get("data-src")
                if not src or "logo" in src.lower() or "header" in src.lower():
                    continue
                
                # Check surrounding text context (parent, article or card)
                card = pic.find_parent("article") or pic.find_parent("div", class_=lambda x: x and ('card' in x.lower() or 'nota' in x.lower() or 'item' in x.lower()))
                if card:
                    text_content = card.get_text(separator=" ").strip()
                else:
                    text_content = pic.parent.get_text(separator=" ").strip()
                    
                text_content_lower = text_content.lower()
                
                # Check if it contains keywords
                match_count = sum(1 for kw in keywords if kw in text_content_lower)
                if match_count == 0:
                    continue
                
                # Exclusividad Mundial 2026 (Regla 6)
                is_mundial = any(w in text_content_lower or w in src.lower() for w in ["2026", "mundial", "copa del mundo"])
                if not is_mundial:
                    continue
                
                # Clean URL
                hd_url = src.split("?")[0]
                if "?" in src:
                    hd_url = hd_url + "?width=800"
                
                if any(hd_url == ex for ex in exclude_urls):
                    continue
                    
                logger.info(f"Imagen válida encontrada en Cadena 3 Deportes: {hd_url}")
                title_text = text_content.split(".")[0].strip()
                if "Fútbol" in title_text:
                    title_text = title_text.replace("Fútbol Fútbol", "Fútbol").replace("Fútbol", "").strip()
                
                return {
                    "url": hd_url,
                    "citation": f"Foto: Cadena 3 Deportes / {title_text}"
                }
    except Exception as e:
        logger.warning(f"Error buscando en Cadena 3: {e}")
        
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


def verify_image_suitability(image_url_or_path: str, article_title: str, is_scraped: bool = True) -> bool:
    """
    Verifica si una imagen es apta para el artículo de fútbol asociación:
    1. Filtra localmente por palabras clave prohibidas en el nombre de archivo/URL.
    2. Usa el modelo multimodal de Gemini para inspección visual.
    3. Si Gemini falla (429/500/etc.) y es una imagen scrapeada, se rechaza estrictamente (retorna False).
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
        "flag_of", "map_of", "coat_of_arms", "emblem", "shield", "bandera", "mapa", "escudo",
        "canal_autorizado", "canal autorizado", "tycsports_canal_autorizado", "tyc_sports_canal_autorizado",
        "banner", "logo", "watermark", "promo"
    ]
    for kw in reject_keywords:
        if kw in filename_clean:
            logger.warning(f"❌ Imagen RECHAZADA localmente por palabra clave prohibida '{kw}' en el nombre de archivo: {os.path.basename(image_url_or_path)}")
            return False

    api_key = config.get_active_key()
    if not api_key:
        if is_scraped:
            logger.warning("No hay API Key activa para Gemini. Rechazando imagen scrapeada debido a ORDEN SUPREMA.")
            return False
        else:
            logger.warning("No hay API Key activa para Gemini. Aprobando imagen generada por IA por defecto.")
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
        - The image is the 'TyC Sports CANAL AUTORIZADO' promotional banner or placeholder with a giant FIFA World Cup 2026 logo next to the TyC Sports logo. THIS IS STRICTLY PROHIBITED.
        
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
            else:
                logger.warning("Fallo en llamada a la API de verificación de imagen de Gemini (vacío).")
                if is_scraped:
                    logger.warning("Rechazando imagen scrapeada por falta de candidatos.")
                    return False
                return True
        elif r_api.status_code == 429:
            logger.warning("Quota límite excedida (429) en verificación de imagen de Gemini.")
            config.rotate_key()
            if is_scraped:
                logger.warning("Rechazando imagen scrapeada por quota excedida (429) de Gemini.")
                return False
            else:
                logger.warning("Aprobando imagen generada por IA (429 fallback).")
                return True
        else:
            logger.warning(f"Fallo en llamada a la API de verificación de imagen de Gemini ({r_api.status_code}).")
            if is_scraped:
                logger.warning("Rechazando imagen scrapeada por fallo de API.")
                return False
            else:
                logger.warning("Aprobando imagen generada por IA (Fallo API fallback).")
                return True

    except Exception as e:
        logger.error(f"Excepción al verificar idoneidad de imagen con Gemini: {e}.")
        if is_scraped:
            logger.warning("Rechazando imagen scrapeada por excepción en verificación.")
            return False
        else:
            logger.warning("Aprobando imagen generada por IA (Excepción fallback).")
            return True

    return True

def generate_image_prompt_via_llm(title: str, content: str = "") -> str:
    """
    Usa gemini-2.5-flash para generar un prompt detallado en inglés para la generación de imágenes con Imagen/Flux.
    """
    import time
    api_key = config.get_active_key()
    if not api_key:
        logger.warning("No hay API Key activa de Gemini para generar el prompt.")
        return ""
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    prompt_payload = f"""
    You are an award-winning Sports Illustrated and Getty Images professional photographer.
    Read the following article title and content, and output exactly ONE short paragraph (under 60 words) in ENGLISH containing a hyper-realistic, high-end photography prompt for an AI image generator.
    
    STRICT RULES:
    1. START WITH: "A hyper-realistic professional sports photography of..." or "Award-winning Getty Images sports photography shot on Canon EOS R3 of..."
    2. Focus purely on realistic action on the pitch or player emotions. Mention team colors if relevant.
    3. ABSOLUTELY PROHIBITED: No cartoons, no 3D renders, no digital art, no anime, no illustrations, no text/fonts.
    4. ADD THESE ENFORCEMENT TAGS AT THE END: "photo-realism, 8k resolution, raw photo, highly detailed, realistic skin texture, cinematic lighting, depth of field, real life sports photo."
    5. Output ONLY the English prompt. NO quotes, NO introductions, NO markdown.
    
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
        r = requests.post(url, json=payload, headers=headers, timeout=30)
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
        
    fallback = f"Hyper-realistic professional action sports photography of {title}. High quality, stadium lighting, sharp focus, 8k resolution, Getty Images style."
    logger.warning("Fallo en la generación de prompt con LLM. Usando fallback estático.")
    return fallback

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
        f"&model=flux-realism&nologo=true&enhance=true&seed={seed}"
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
    # 1. Intentar Gemini Imagen (MEJOR CALIDAD / FOTOREALISMO)
    api_key = config.get_active_key()
    if api_key:
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
                                "citation": "Foto: Generada por IA (Gemini Imagen) / Licencia Libre"
                            }
                elif r.status_code == 400 and "only available on paid plans" in r.text:
                    logger.warning(f"El modelo {model} requiere cuenta de pago. Saltando...")
                else:
                    logger.warning(f"Error de API con modelo {model} ({r.status_code}): {r.text[:200]}")
            except Exception as e:
                logger.error(f"Excepción al llamar al modelo {model}: {e}")

    # 2. Fallbacks secundarios si falla Gemini
    logger.info("Gemini falló o no está disponible. Pasando a opciones secundarias (Flux/Pollinations)...")
    
    res_pollinations = generate_pollinations_image(prompt)
    if res_pollinations:
        return res_pollinations

    res_hf = generate_huggingface_image(prompt)
    if res_hf:
        return res_hf

    flux_res = generate_flux_image(prompt)
    if flux_res:
        return flux_res


def get_football_image(player_name, team_name=None, exclude_urls: list = None, article_title: str = "", article_content: str = "") -> Dict[str, str]:
    """
    Busca una imagen real del jugador o equipo en Wikimedia.
    prompt_payload = f\"\"\"
    Eres un director de fotografía deportiva trabajando para Getty Images.
    Tu tarea es leer el Título y el Contenido del artículo deportivo que te proveeré, y crear un prompt de 1 solo párrafo, extremadamente descriptivo en INGLÉS para generar una imagen fotorrealista de hiper-alta calidad con una IA generativa.
    
    REGLAS ESTRICTAS PARA EL PROMPT:
    1. DEBE comenzar con términos fotográficos profesionales como: "A hyper-realistic professional sports photography of...", "Award-winning Getty Images sports photography shot on Canon EOS R3...", etc.
    2. DEBE incluir la acción exacta descrita en el artículo, identificando los colores y equipos involucrados, la emoción del momento y el tipo de estadio (si se menciona).
    3. DEBE prohibir absolutamente ilustraciones, dibujos, arte digital o cartoons. Agrega términos como: "photo-realism, 8k resolution, raw photo, highly detailed, realistic skin texture, cinematic lighting, depth of field".
    4. NO uses comillas en tu respuesta, solo devuelve el texto en inglés.
    5. NO menciones que eres una IA o que estás creando un prompt.
    6. MANTÉN el texto final debajo de las 60 palabras.
    \"\"\"
    Si no encuentra una específica, y disponemos de contexto del artículo, genera una imagen hiperrealista por IA (Flux/Imagen).
    Si falla la IA, recurre a los fallbacks genéricos de Wikimedia.
    """
    try:
        teams_to_try = []
        if isinstance(team_name, list):
            teams_to_try = [t for t in team_name if t and isinstance(t, str) and t.lower() not in ["desconocido", "ninguno", ""]]
        elif team_name and isinstance(team_name, str) and team_name.lower() not in ["desconocido", "ninguno", ""]:
            teams_to_try = [team_name]
            
        players_to_try = []
        if isinstance(player_name, list):
            players_to_try = [p for p in player_name if p and isinstance(p, str) and p.lower() not in ["desconocido", "ninguno", ""]]
        elif player_name and isinstance(player_name, str) and player_name.lower() not in ["desconocido", "ninguno", ""]:
            players_to_try = [player_name]

        if exclude_urls is None:
            exclude_urls = []

        # --- 1. PRIORIDAD 1: TYC SPORTS (ORDEN SUPREMA) ---
        logger.info("Prioridad 1: Buscando imágenes en TyC Sports según ORDEN SUPREMA...")
        for team in teams_to_try:
            query = build_image_query("team", team)
            if query:
                res = search_tycsports_images(query, exclude_urls=exclude_urls)
                if res:
                    if article_title and not verify_image_suitability(res["url"], article_title, is_scraped=True):
                        if exclude_urls is None:
                            exclude_urls = []
                        exclude_urls.append(res["url"])
                        continue
                    return res
        
        for player in players_to_try:
            query = build_image_query("player", player)
            if query:
                res = search_tycsports_images(query, exclude_urls=exclude_urls)
                if res:
                    if article_title and not verify_image_suitability(res["url"], article_title, is_scraped=True):
                        if exclude_urls is None:
                            exclude_urls = []
                        exclude_urls.append(res["url"])
                        continue
                    return res

        # --- 1.5. PRIORIDAD 1.5: CADENA 3 DEPORTES (ORDEN SUPREMA) ---
        logger.info("Prioridad 1.5: Buscando imágenes en Cadena 3 Deportes según ORDEN SUPREMA...")
        for team in teams_to_try:
            query = build_image_query("team", team)
            if query:
                res = search_cadena3_images(query, exclude_urls=exclude_urls)
                if res:
                    if article_title and not verify_image_suitability(res["url"], article_title, is_scraped=True):
                        exclude_urls.append(res["url"])
                        continue
                    return res
        
        for player in players_to_try:
            query = build_image_query("player", player)
            if query:
                res = search_cadena3_images(query, exclude_urls=exclude_urls)
                if res:
                    if article_title and not verify_image_suitability(res["url"], article_title, is_scraped=True):
                        exclude_urls.append(res["url"])
                        continue
                    return res

        # --- 2. PRIORIDAD 2: GENERACIÓN CON IA (ÚLTIMO RECURSO LIBRE DE WIKIMEDIA) ---
        logger.info("Prioridad 2: No se encontraron fotos. Recurriendo a IA como último recurso...")
        if article_title or article_content:
            ai_prompt = generate_image_prompt_via_llm(article_title, article_content)
            if ai_prompt:
                res = generate_ai_image(ai_prompt)
                if res:
                    if verify_image_suitability(res["url"], article_title, is_scraped=False):
                        return res
                    else:
                        try:
                            local_path = res["url"].replace("file://", "", 1)
                            if os.path.exists(local_path):
                                os.remove(local_path)
                        except Exception:
                            pass

    except Exception as e:
        logger.error(f"Excepción general en get_football_image: {e}. Recurriendo a fallback de IA genérico.")

    # 3. Fallback absoluto generado por IA (sin usar Wikimedia)
    logger.info("Fallback absoluto: Generando imagen genérica con IA...")
    generic_prompt = "A hyper-realistic professional sports photography of a highly detailed, modern soccer stadium filled with cheering fans during a night match, 8k resolution, photorealistic, Canon EOS R3"
    return generate_ai_image(generic_prompt)

if __name__ == "__main__":
    # Test directo
    logging.basicConfig(level=logging.INFO)
    print(get_football_image("Kylian Mbappe"))
    print(get_football_image("", "Fenerbahce"))
