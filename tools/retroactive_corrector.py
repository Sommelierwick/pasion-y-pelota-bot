"""
tools/retroactive_corrector.py — Agente Corrector Retroactivo de Pasión y Pelota

Actúa sobre artículos YA PUBLICADOS en WordPress:
1. CORRECTOR DE IMAGEN: Si la imagen destacada del post está fuera de contexto (mapa, político,
   paisaje, etc.) o falta, genera una nueva con Flux/Pollinations y la reemplaza.
2. CORRECTOR EDITORIAL: Pasa el texto del artículo por el Corrector Editorial (mismas reglas
   que el pipeline nuevo) y si hay cambios, actualiza el post en WordPress.

Parámetros:
    max_posts (int): Cuántos posts recientes revisar. Default 20.
    dry_run (bool): Si True, solo reporta sin hacer cambios en WordPress.
"""

import requests
import logging
import json
import re
import os
import io
import base64
import time
import uuid
import sys
from bs4 import BeautifulSoup
from requests.auth import HTTPBasicAuth
from typing import Optional
from PIL import Image

import config
from tools.images import generate_ai_image, verify_image_suitability
from tools.wordpress import WordPressPublisher

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Corrector Editorial (mismo prompt que main_standalone)
# ─────────────────────────────────────────────
CORRECTOR_EDITORIAL_SYSTEM = """
Eres el 'Corrector Editorial Experto en Fútbol e Imágenes'. Tu misión es auditar, corregir y pulir el contenido redactado por el periodista antes de que sea publicado. Garantizas el máximo rigor fáctico, conceptual y estructural de Pasión y Pelota.

REGLAS DE AUDITORÍA Y EDICIÓN OBLIGATORIAS:
1. SEDES DEL MUNDIAL 2026: El Mundial de la FIFA 2026 se juega de forma neutral en Estados Unidos, México y Canadá. Ninguna selección (por ejemplo, Uruguay, Brasil, Argentina, Alemania, etc.) juega de local en su propio país. Si el artículo menciona erróneamente estadios locales históricos (como el Estadio Centenario para Uruguay, el Maracaná para Brasil, el Monumental para Argentina) o que jugaron en su país original, corrígelo inmediatamente para situarlo en las sedes oficiales norteamericanas de la FIFA 2026 (por ejemplo: Estadio Miami / Hard Rock Stadium en Florida, MetLife Stadium, Estadio Azteca, etc.).
2. FÚTBOL ASOCIACIÓN (SOCCER) VS FÚTBOL AMERICANO: Asegúrate de que no haya ninguna confusión terminológica con el fútbol americano (como yardas, touchdowns, quarterbacks, cascos de fútbol americano, etc.). Todo debe hacer referencia exclusiva al fútbol asociación (soccer).
3. CO-CITACIONES OCULTAS: La sección final de co-citaciones a medios deportivos panamericanos (Marca, AS, Olé, etc.) DEBE estar obligatoriamente envuelta en un contenedor HTML invisible (<div style="display: none !important;" aria-hidden="true"> ... </div>). Si el redactor omitió la envoltura oculta o dejó los links visibles, reescríbela y enciérrala dentro de este div oculto.
4. COHERENCIA ESTADÍSTICA: Verifica que las tablas de estadísticas estén completas, tengan coherencia numérica y no contengan disculpas ni comentarios sobre la falta de datos de la IA.
5. Devolver el JSON estructurado con el mismo esquema de entrada. No agregues preámbulos, saludos ni explicaciones.
"""


def _call_gemini_corrector(title: str, content_html: str) -> Optional[dict]:
    """
    Intenta corregir el artículo vía Gemini probando con varios modelos y rotando claves en caso de rate limit.
    """
    if not config.GEMINI_API_KEYS:
        return None
        
    models_to_try = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.0-flash-lite", "gemini-flash-latest"]
    num_keys = len(config.GEMINI_API_KEYS)
    prompt = f"""Por favor revisa, audita y corrige el siguiente artículo.
Título: {title}
Contenido HTML:
{content_html}

Devuelve un JSON con exactamente esta estructura:
{{
    "title": "Título corregido",
    "content_html": "Contenido HTML corregido"
}}
No agregues preámbulos ni explicaciones fuera del JSON."""

    import time
    for model_name in models_to_try:
        for attempt in range(num_keys):
            api_key = config.get_active_key()
            if not api_key:
                config.rotate_key()
                continue
                
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "system_instruction": {"parts": [{"text": CORRECTOR_EDITORIAL_SYSTEM}]},
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.2
                }
            }
            
            try:
                logger.info(f"Intentando Gemini HTTP en corrector ({model_name}) (Key Index: {config.ACTIVE_KEY_INDEX % num_keys})...")
                resp = requests.post(url, headers=headers, json=payload, timeout=60)
                if resp.status_code == 200:
                    raw = resp.json()
                    text = raw.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    result = json.loads(text)
                    if "title" in result and "content_html" in result:
                        return result
                elif resp.status_code == 429:
                    logger.warning(f"Gemini Rate Limit (429) en corrector para {model_name}. Rotando clave...")
                    config.rotate_key()
                    time.sleep(1)
                else:
                    logger.error(f"Error de Gemini ({resp.status_code}) en corrector para {model_name}: {resp.text}")
                    config.rotate_key()
            except Exception as e:
                logger.error(f"Excepción en Gemini corrector ({model_name}): {e}")
                config.rotate_key()
                
    return None


def _call_groq_corrector(title: str, content_html: str) -> Optional[dict]:
    """
    Intenta corregir el artículo vía Groq como respaldo si Gemini falla.
    """
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        logger.error("No hay GROQ_API_KEY configurada para el respaldo en corrector.")
        return None

    prompt = f"""Por favor revisa, audita y corrige el siguiente artículo.
Título: {title}
Contenido HTML:
{content_html}

Devuelve un JSON con exactamente esta estructura:
{{
    "title": "Título corregido",
    "content_html": "Contenido HTML corregido"
}}
Responde ÚNICAMENTE con un objeto JSON válido con exactamente estos campos: 'title' y 'content_html'. Sin introducción, sin bloques markdown, solo el JSON puro."""

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {groq_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": CORRECTOR_EDITORIAL_SYSTEM},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"}
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Intentando Groq en corrector (Intento {attempt+1}/{max_retries})...")
            resp = requests.post(url, json=payload, headers=headers, timeout=60)
            if resp.status_code == 200:
                result = resp.json()
                content = result["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                if "title" in parsed and "content_html" in parsed:
                    return parsed
            elif resp.status_code == 429:
                logger.warning(f"Groq Rate Limit (429) en corrector. Reintentando en 15 segundos...")
                time.sleep(15)
            else:
                logger.error(f"Error de Groq ({resp.status_code}) en corrector: {resp.text}")
        except Exception as e:
            logger.error(f"Excepción en Groq corrector: {e}")
    return None

def _call_openai_corrector(title: str, content_html: str) -> Optional[dict]:
    """
    Intenta corregir el artículo vía OpenAI como respaldo final.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        logger.error("No hay OPENAI_API_KEY configurada para el respaldo final en corrector.")
        return None

    prompt = f"""Por favor revisa, audita y corrige el siguiente artículo.
Título: {title}
Contenido HTML:
{content_html}

Devuelve un JSON con exactamente esta estructura:
{{
    "title": "Título corregido",
    "content_html": "Contenido HTML corregido"
}}
Responde ÚNICAMENTE con un objeto JSON válido con exactamente estos campos: 'title' y 'content_html'. Sin introducción, sin bloques markdown, solo el JSON puro."""

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openai_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": CORRECTOR_EDITORIAL_SYSTEM},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"}
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Intentando OpenAI en corrector (Intento {attempt+1}/{max_retries})...")
            resp = requests.post(url, json=payload, headers=headers, timeout=60)
            if resp.status_code == 200:
                result = resp.json()
                content = result["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                if "title" in parsed and "content_html" in parsed:
                    return parsed
            elif resp.status_code == 429:
                logger.warning(f"OpenAI Rate Limit (429) en corrector. Reintentando en 15 segundos...")
                time.sleep(15)
            else:
                logger.error(f"Error de OpenAI ({resp.status_code}) en corrector: {resp.text}")
        except Exception as e:
            logger.error(f"Excepción en OpenAI corrector: {e}")
    return None


def call_corrector_editorial(title: str, content_html: str) -> Optional[dict]:
    """
    Llama al Corrector Editorial. Intenta Gemini primero (con rotación de keys).
    Si falla, recurre a Groq como respaldo. Si falla, recurre a OpenAI como respaldo final.
    """
    res = _call_gemini_corrector(title, content_html)
    if res:
        logger.info("Corrección editorial exitosa con Gemini.")
        return res
    logger.warning("Fallo en todas las claves de Gemini en corrector retroactivo. Recurriendo a Groq...")
    res = _call_groq_corrector(title, content_html)
    if res:
        logger.info("Corrección editorial exitosa con Groq.")
        return res
    logger.warning("Fallo en Groq en corrector retroactivo. Recurriendo a OpenAI...")
    return _call_openai_corrector(title, content_html)


def get_featured_image_url(post: dict, wp_base_url: str, auth: HTTPBasicAuth) -> Optional[str]:
    """
    Dado un post de la API de WP, devuelve la URL de su imagen destacada, o None si no tiene.
    """
    media_id = post.get("featured_media", 0)
    if not media_id:
        return None
    try:
        r = requests.get(
            f"{wp_base_url}/wp-json/wp/v2/media/{media_id}",
            auth=auth,
            timeout=15
        )
        if r.status_code == 200:
            return r.json().get("source_url")
    except Exception as e:
        logger.error(f"Error al obtener imagen de media ID {media_id}: {e}")
    return None


def run_retroactive_correction(max_posts: int = 20, dry_run: bool = False):
    """
    Agente principal: revisa los últimos `max_posts` posts publicados y:
    1. Corrige imágenes fuera de contexto o faltantes (reemplaza con IA Flux/Pollinations).
    2. Corrige el contenido editorial (sedes, errores factuales, co-citas ocultas).
    """
    logger.info("=" * 70)
    logger.info("AGENTE CORRECTOR RETROACTIVO — INICIANDO")
    logger.info(f"Modo: {'DRY RUN (sin cambios reales)' if dry_run else 'PRODUCCIÓN (aplicando cambios)'}")
    logger.info("=" * 70)

    wp_base = config.WP_URL.rstrip("/").strip()
    auth = HTTPBasicAuth(config.WP_USER, config.WP_PASSWORD)
    publisher = WordPressPublisher()

    # 1. Obtener los últimos posts publicados
    try:
        resp = requests.get(
            f"{wp_base}/wp-json/wp/v2/posts",
            params={"per_page": max_posts, "status": "publish", "orderby": "date", "order": "desc"},
            auth=auth,
            timeout=30
        )
        if resp.status_code != 200:
            logger.error(f"No se pudieron obtener los posts de WordPress: {resp.status_code}")
            return
        posts = resp.json()
    except Exception as e:
        logger.error(f"Excepción al obtener posts de WordPress: {e}")
        return

    logger.info(f"Posts obtenidos: {len(posts)}")

    image_fixed = 0
    image_ok = 0
    image_missing_fixed = 0
    text_fixed = 0
    text_ok = 0
    errors = 0

    for post in posts:
        post_id = post.get("id")
        title_raw = post.get("title", {}).get("rendered", "")
        # Limpiar HTML del título
        title = BeautifulSoup(title_raw, "html.parser").get_text()
        content_html = post.get("content", {}).get("rendered", "")
        post_link = post.get("link", "")

        logger.info(f"\n{'─'*60}")
        logger.info(f"[Post ID {post_id}] {title}")
        logger.info(f"Link: {post_link}")

        # ─── PASO 1: CORRECCIÓN DE IMAGEN ────────────────────────────────────
        featured_url = get_featured_image_url(post, wp_base, auth)

        needs_new_image = False
        rejection_reason = ""

        if not featured_url:
            logger.warning(f"  [IMAGEN] ❌ Post sin imagen destacada.")
            needs_new_image = True
            rejection_reason = "Sin imagen destacada"
        else:
            logger.info(f"  [IMAGEN] Verificando: {featured_url[:80]}...")
            is_ok = verify_image_suitability(featured_url, title)
            if is_ok:
                logger.info(f"  [IMAGEN] ✅ Imagen aprobada por el inspector.")
                image_ok += 1
            else:
                logger.warning(f"  [IMAGEN] ❌ Imagen RECHAZADA por el inspector.")
                needs_new_image = True
                rejection_reason = "Imagen fuera de contexto"

        if needs_new_image:
            logger.info(f"  [IMAGEN] Generando nueva imagen con IA Flux/Pollinations para: '{title}'")
            ai_prompt = (
                f"Photorealistic sports press photo for a soccer news article titled: '{title}'. "
                f"Show soccer players in action, stadium crowd, ball, or professional training. "
                f"FIFA World Cup 2026 style. No text, no watermarks. Cinematic lighting."
            )
            new_img = generate_ai_image(ai_prompt)

            if new_img:
                img_local_path = new_img.get("url")  # ruta local del archivo
                citation = new_img.get("citation", "Foto: Generada por IA (Flux) / Licencia Libre (Ilustración IA)")

                if not dry_run:
                    # Subir la imagen nueva a WordPress y asignarla al post
                    media_id = publisher.upload_featured_image(
                        image_url=img_local_path,
                        filename=f"retro_fix_{post_id}_{uuid.uuid4().hex[:6]}.jpg"
                    )
                    if media_id:
                        # Actualizar la imagen y agregar citación al pie del contenido
                        # Eliminar citación vieja si existe
                        content_updated = re.sub(
                            r'<p style="font-size: 11px;[^"]*">[^<]*Foto:[^<]*</p>',
                            '',
                            content_html
                        )
                        content_updated += f'\n\n<p style="font-size: 11px; color: #777; text-align: right; margin-top: 20px; font-style: italic;">{citation}</p>'

                        success = publisher.update_post(post_id, {
                            "featured_media": media_id,
                            "content": content_updated
                        })
                        if success:
                            logger.info(f"  [IMAGEN] ✅ Imagen nueva subida y asignada. Motivo anterior: {rejection_reason}")
                            image_fixed += 1
                            image_missing_fixed += (1 if not featured_url else 0)
                        else:
                            logger.error(f"  [IMAGEN] ❌ Error al asignar la nueva imagen al post.")
                            errors += 1
                    else:
                        logger.error(f"  [IMAGEN] ❌ Error al subir la imagen nueva a WordPress.")
                        errors += 1
                else:
                    logger.info(f"  [IMAGEN] [DRY RUN] Imagen nueva generada pero no subida.")
                    image_fixed += 1
            else:
                logger.error(f"  [IMAGEN] ❌ No se pudo generar imagen con IA para este post.")
                errors += 1

        # ─── PASO 2: CORRECCIÓN EDITORIAL DEL TEXTO ──────────────────────────
        logger.info(f"  [TEXTO] Auditando contenido editorial...")
        corrected = call_corrector_editorial(title, content_html)

        if corrected:
            new_title = corrected.get("title", title).strip()
            new_content = corrected.get("content_html", content_html).strip()

            title_changed = new_title != title
            content_changed = new_content != content_html

            if title_changed or content_changed:
                logger.info(f"  [TEXTO] ✏️  Correcciones detectadas:")
                if title_changed:
                    logger.info(f"    Título cambiado: '{title}' → '{new_title}'")
                if content_changed:
                    logger.info(f"    Contenido editorial corregido.")

                if not dry_run:
                    patch = {}
                    if title_changed:
                        patch["title"] = new_title
                    if content_changed:
                        patch["content"] = new_content
                    success = publisher.update_post(post_id, patch)
                    if success:
                        logger.info(f"  [TEXTO] ✅ Post actualizado en WordPress.")
                        text_fixed += 1
                    else:
                        logger.error(f"  [TEXTO] ❌ Error al actualizar el post en WordPress.")
                        errors += 1
                else:
                    logger.info(f"  [TEXTO] [DRY RUN] Correcciones detectadas pero no aplicadas.")
                    text_fixed += 1
            else:
                logger.info(f"  [TEXTO] ✅ Contenido aprobado sin cambios necesarios.")
                text_ok += 1
        else:
            logger.warning(f"  [TEXTO] ⚠️  No se pudo obtener respuesta del corrector editorial (se omite este post).")

        # Pausa entre posts para no saturar las APIs
        time.sleep(2)

    # ─── RESUMEN FINAL ───────────────────────────────────────────────────────
    logger.info("\n" + "=" * 70)
    logger.info("RESUMEN DEL AGENTE CORRECTOR RETROACTIVO")
    logger.info("=" * 70)
    logger.info(f"  Posts revisados:              {len(posts)}")
    logger.info(f"  Imágenes correctas (OK):      {image_ok}")
    logger.info(f"  Imágenes corregidas:          {image_fixed}")
    logger.info(f"  Texto sin cambios (OK):       {text_ok}")
    logger.info(f"  Texto corregido:              {text_fixed}")
    logger.info(f"  Errores:                      {errors}")
    logger.info("=" * 70)


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description="Agente Corrector Retroactivo de Pasión y Pelota")
    parser.add_argument("--max-posts", type=int, default=20, help="Cuántos posts recientes revisar (default: 20)")
    parser.add_argument("--dry-run", action="store_true", help="Solo reportar cambios sin aplicarlos en WordPress")
    args = parser.parse_args()
    run_retroactive_correction(max_posts=args.max_posts, dry_run=args.dry_run)
