import requests
import logging
import io
import os
import json
from typing import List, Optional
from requests.auth import HTTPBasicAuth
import config
from tools.images import strip_watermark

# Configuración de logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class WordPressPublisher:
    def __init__(self):
        self.url = config.WP_URL.rstrip('/') + "/wp-json/wp/v2"
        self.user = config.WP_USER
        self.password = config.WP_PASSWORD
        
        # Validar credenciales
        if not self.user or not self.password:
            logging.warning("Advertencia: Las credenciales de WordPress no están configuradas correctamente en config.py / .env")
        
        self.auth = HTTPBasicAuth(self.user, self.password)

    def _get_headers(self):
        return {
            "Content-Type": "application/json"
        }

    def upload_featured_image(self, image_url: str, filename: str = "portada.jpg") -> Optional[int]:
        """Descarga una imagen desde una URL o lee un archivo local, y la sube a la Media Library de WordPress.
        Devuelve el ID del media attachment, o None si falla."""
        if not image_url:
            logging.warning("No se proporcionó URL o ruta de imagen para subir como destacada.")
            return None
        
        image_url = image_url.strip()
        
        # --- REGLA 4: Anti-duplicado en el gate final ---
        import json
        import os
        USED_IMAGES_FILE = "used_images.json"
        
        try:
            used = set()
            if os.path.exists(USED_IMAGES_FILE):
                with open(USED_IMAGES_FILE, "r", encoding="utf-8") as f:
                    used = set(json.load(f))
            if image_url in used:
                logging.warning(f"❌ Anti-duplicado: La imagen {image_url} ya fue usada. Rechazando subida para evitar duplicados.")
                return None
        except Exception as e:
            logging.warning(f"Error al leer {USED_IMAGES_FILE}: {e}")
        # ------------------------------------------------
        
        try:
            # Check if it is a local file path
            is_local = False
            if image_url.startswith("file://") or image_url.startswith("/") or image_url.startswith("C:\\"):
                is_local = True
            elif not image_url.startswith(("http://", "https://")):
                is_local = True
                
            if not is_local:
                headers_get = {
                    "User-Agent": "PasionYPelotaBot/1.0 (contact: elrojobruno@gmail.com) Python-requests/2.31.0"
                }
                img_response = requests.get(image_url, headers=headers_get, timeout=15)
                if img_response.status_code != 200:
                    logging.error(f"No se pudo descargar la imagen de portada: {image_url} (HTTP {img_response.status_code})")
                    return None
                
                # Guardar temporalmente para strip_watermark
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
                    tmp_file.write(img_response.content)
                    local_path = tmp_file.name
                
                strip_watermark(local_path)
                
                with open(local_path, "rb") as f:
                    img_content = f.read()
                os.remove(local_path)
            else:
                local_path = image_url
                if local_path.startswith("file://"):
                    local_path = local_path.replace("file://", "", 1)
                
                if not os.path.exists(local_path):
                    logging.error(f"No se encontró el archivo de imagen local: {local_path}")
                    return None
                    
                strip_watermark(local_path)
                with open(local_path, "rb") as f:
                    img_content = f.read()

            import mimetypes
            content_type, _ = mimetypes.guess_type(filename)
            if not content_type:
                content_type = "image/jpeg"
                
            media_url = f"{self.url}/media"
            headers = {
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": content_type
            }
            upload_response = requests.post(
                media_url,
                data=img_content,
                headers=headers,
                auth=self.auth
            )
            if upload_response.status_code in [200, 201]:
                media_id = upload_response.json().get("id")
                logging.info(f"Imagen de portada subida con éxito (ID: {media_id})")
                
                # --- Guardar en used_images.json ---
                try:
                    used.add(image_url)
                    with open(USED_IMAGES_FILE, "w", encoding="utf-8") as f:
                        json.dump(list(used), f, indent=2)
                except Exception as e:
                    logging.warning(f"No se pudo guardar la imagen usada: {e}")
                # -----------------------------------
                
                if is_local:
                    try:
                        os.remove(local_path)
                        logging.info(f"Archivo de imagen local temporal eliminado: {local_path}")
                    except Exception as e:
                        logging.warning(f"No se pudo eliminar el archivo local temporal {local_path}: {e}")
                return media_id
            else:
                logging.error(f"Error al subir imagen ({upload_response.status_code}): {upload_response.text[:200]}")
        except Exception as e:
            logging.error(f"Excepción al subir imagen de portada: {e}")
        return None

    def get_or_create_category(self, category_name: str) -> int:
        """Busca una categoría por nombre. Si no existe, la crea y devuelve su ID."""
        if not category_name:
            return 1  # Categoría por defecto (Sin categoría / Uncategorized)
        
        category_name = category_name.strip()
        search_url = f"{self.url}/categories"
        
        try:
            # Buscar categoría existente
            response = requests.get(search_url, params={"search": category_name}, auth=self.auth)
            if response.status_code == 200:
                categories = response.json()
                for cat in categories:
                    if cat["name"].lower() == category_name.lower():
                        logging.info(f"Categoría encontrada: '{category_name}' (ID: {cat['id']})")
                        return cat["id"]
            
            # Si no se encontró, crearla
            logging.info(f"Creando nueva categoría: '{category_name}'")
            create_payload = {"name": category_name}
            create_response = requests.post(search_url, json=create_payload, headers=self._get_headers(), auth=self.auth)
            if create_response.status_code == 201:
                new_cat = create_response.json()
                logging.info(f"Categoría '{category_name}' creada con éxito (ID: {new_cat['id']})")
                return new_cat["id"]
            else:
                logging.error(f"Error al crear categoría '{category_name}': {create_response.text}")
        except Exception as e:
            logging.error(f"Excepción al buscar/crear categoría '{category_name}': {e}")
        
        return 1  # ID de categoría por defecto ante fallas

    def get_or_create_tags(self, tag_names) -> List[int]:
        """Recibe una lista de nombres de etiquetas, busca sus IDs o las crea si no existen."""
        tag_ids = []
        if not tag_names:
            return tag_ids
        
        if isinstance(tag_names, str):
            tag_names = [t.strip() for t in tag_names.split(",") if t.strip()]
        
        search_url = f"{self.url}/tags"
        
        for name in tag_names:
            name = name.strip()
            if not name:
                continue
            
            try:
                # Buscar etiqueta existente
                response = requests.get(search_url, params={"search": name}, auth=self.auth)
                tag_id = None
                if response.status_code == 200:
                    tags = response.json()
                    for t in tags:
                        if t["name"].lower() == name.lower():
                            tag_id = t["id"]
                            logging.info(f"Etiqueta encontrada: '{name}' (ID: {tag_id})")
                            break
                
                # Si no existe, crearla
                if not tag_id:
                    logging.info(f"Creando nueva etiqueta: '{name}'")
                    create_payload = {"name": name}
                    create_response = requests.post(search_url, json=create_payload, headers=self._get_headers(), auth=self.auth)
                    if create_response.status_code == 201:
                        new_tag = create_response.json()
                        tag_id = new_tag["id"]
                        logging.info(f"Etiqueta '{name}' creada con éxito (ID: {tag_id})")
                    else:
                        logging.error(f"Error al crear etiqueta '{name}': {create_response.text}")
                
                if tag_id:
                    tag_ids.append(tag_id)
            except Exception as e:
                logging.error(f"Excepción al buscar/crear etiqueta '{name}': {e}")
                
        return tag_ids

    def publish_post(self, title: str, content: str, league_category = "Noticias", tags: List[str] = None, status: str = "publish", featured_image_id: Optional[int] = None, seo_desc: Optional[str] = None, seo_focuskw: Optional[str] = None, writer: Optional[str] = None, date: Optional[str] = None) -> Optional[dict]:
        """
        Publica una entrada en WordPress.
        
        Args:
            title: Título de la entrada.
            content: Contenido HTML del artículo.
            league_category: Nombre de la categoría (o lista de nombres de categorías).
            tags: Lista de nombres de etiquetas (jugadores, equipos).
            status: 'publish' para publicar de inmediato, 'draft' para guardarlo como borrador.
            featured_image_id: ID del attachment de imagen destacada (opcional).
            seo_desc: Meta descripción para SEO (Yoast) (opcional).
            seo_focuskw: Palabra clave principal para SEO (Yoast) (opcional).
            writer: Nombre del autor/periodista para atribución JSON-LD (opcional).
            date: Fecha exacta de publicación en formato ISO (opcional).
        """
        if tags is None:
            tags = []
            
        logging.info(f"Iniciando publicación de artículo: '{title}'")
        
        # 1. Obtener o crear las categorías
        category_ids = []
        if isinstance(league_category, list):
            for cat_name in league_category:
                if cat_name:
                    category_ids.append(self.get_or_create_category(cat_name))
        elif isinstance(league_category, str):
            category_ids.append(self.get_or_create_category(league_category))
        else:
            category_ids.append(self.get_or_create_category("Noticias"))
        
        # 2. Obtener o crear los IDs de las etiquetas
        tag_ids = self.get_or_create_tags(tags)
        
        # 3. Preparar payload de la entrada
        post_payload = {
            "title": title,
            "content": content,
            "status": status,
            "categories": category_ids,
            "tags": tag_ids,
            "meta": {}
        }
        
        import pytz
        from datetime import datetime, timedelta
        tz = pytz.timezone('America/Argentina/Buenos_Aires')
        
        if not date:
            dt = datetime.now(tz)
        else:
            try:
                from dateutil import parser
                dt = parser.parse(date)
                if dt.tzinfo is not None:
                    dt = dt.astimezone(tz)
                else:
                    # Si es naive, asumimos que viene en el huso de Buenos Aires
                    dt = tz.localize(dt)
            except Exception as e:
                logging.warning(f"No se pudo parsear/convertir la fecha {date}: {e}")
                dt = datetime.now(tz)
        
        # Corrección del desfase sistemático de +3 horas de la REST API de WordPress:
        # Le restamos 3 horas al objeto datetime local de Buenos Aires
        dt_shifted = dt - timedelta(hours=3)
        date = dt_shifted.strftime('%Y-%m-%dT%H:%M:%S')
            
        if date:
            post_payload["date"] = date
        
        if seo_desc:
            post_payload["meta"]["_yoast_wpseo_metadesc"] = seo_desc
        if seo_focuskw:
            post_payload["meta"]["_yoast_wpseo_focuskw"] = seo_focuskw
        if writer:
            post_payload["meta"]["ppelota_writer"] = writer
            
        # Agregar imagen destacada si se proporcionó
        if featured_image_id:
            post_payload["featured_media"] = featured_image_id
            logging.info(f"Imagen destacada asignada (ID: {featured_image_id})")
        
        # 4. Enviar petición HTTP POST para crear la entrada
        posts_url = f"{self.url}/posts"
        try:
            response = requests.post(posts_url, json=post_payload, headers=self._get_headers(), auth=self.auth)
            if response.status_code in [200, 201]:
                published_post = response.json()
                post_link = published_post.get("link", "")
                logging.info(f"¡Artículo publicado con éxito! Link: {post_link}")
                
                # Ejecutar purga de notas excedentes según la ORDEN SUPREMA (máximo 50)
                self.enforce_limit(50)
                
                # --- ORDEN SUPREMA: TODO LO QUE SE SUBE SE PUBLICA EN REDES ---
                # Si el estado es publicado y no es ya una nota de la categoría Social Share,
                # generamos el clon social automático.
                is_social_share = False
                if isinstance(league_category, str):
                    is_social_share = (league_category.strip().lower() in ["social share", "social-share", "303"])
                elif isinstance(league_category, list):
                    is_social_share = any(str(c).strip().lower() in ["social share", "social-share", "303"] for c in league_category)
                
                if status == "publish" and not is_social_share:
                    try:
                        logging.info("Generando clon social automático para publicar en redes...")
                        social_title = self.generate_social_title(title, content)
                        if social_title:
                            logging.info(f"Clon social generado: '{social_title}'. Publicando en 'Social Share'...")
                            self.publish_post(
                                title=social_title,
                                content=content,
                                league_category="Social Share",
                                tags=[],
                                status="publish",
                                featured_image_id=featured_image_id,
                                seo_desc=seo_desc,
                                seo_focuskw=seo_focuskw,
                                writer=writer,
                                date=date
                            )
                    except Exception as e_social:
                        logging.error(f"Error al generar/publicar clon social: {e_social}")
                
                return published_post
            else:
                logging.error(f"Error al publicar entrada en WordPress ({response.status_code}): {response.text}")
                return None
        except Exception as e:
            logging.error(f"Excepción al publicar entrada en WordPress: {e}")
            return None

    def enforce_limit(self, limit: int = 50):
        """Mantiene un límite estricto de posts en el portal, archivando los más antiguos en la categoría Social Share (303)."""
        url = f"{self.url}/posts?per_page=100&orderby=id&order=desc&categories_exclude=303"
        try:
            response = requests.get(url, headers=self._get_headers(), auth=self.auth, timeout=15)
            if response.status_code != 200:
                logging.error(f"Fallo al obtener la lista de posts para la purga: HTTP {response.status_code}")
                return
            
            posts = response.json()
            total_posts = len(posts)
            
            if total_posts <= limit:
                return

            posts_to_delete = posts[limit:]
            logging.warning(f"ORDEN SUPREMA LÍMITE: Archivando {len(posts_to_delete)} notas para mantener exactamente {limit} en portada.")
            
            for post in posts_to_delete:
                post_id = post["id"]
                update_url = f"{self.url}/posts/{post_id}"
                try:
                    # En lugar de mover a borrador (draft) lo cual rompe las Twitter Cards con 404,
                    # lo movemos a la categoría Social Share (303) manteniéndolo público.
                    # Esto lo oculta del portal y loops, pero mantiene activa su URL y tarjeta en X.
                    update_payload = {"categories": [303]}
                    r = requests.post(update_url, json=update_payload, headers=self._get_headers(), auth=self.auth, timeout=15)
                    if r.status_code in [200, 201]:
                        logging.info(f"Nota ID {post_id} archivada en la categoría Social Share (303) exitosamente.")
                    else:
                        logging.error(f"Error archivando la nota ID {post_id}: HTTP {r.status_code}")
                except Exception as e:
                    logging.error(f"Excepción al archivar nota: {e}")

                    
        except Exception as e:
            logging.error(f"Excepción general en enforce_limit: {e}")

    def generate_social_title(self, original_title: str, content_snippet: str) -> Optional[str]:
        """Genera un título optimizado para redes sociales a partir del original y el resumen."""
        models = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-1.5-flash-latest"]
        
        TEAM_HANDLES = {
            "Argentina": "@Argentina",
            "Francia": "@EquipeDeFrance",
            "España": "@SEFutbol",
            "Brasil": "@CBF_Futebol",
            "Inglaterra": "@England",
            "Portugal": "@selecaoportugal",
            "Uruguay": "@Uruguay",
            "Ecuador": "@LaTri",
            "Alemania": "@DFB_Team",
            "Turquía": "@MilliTakimlar",
            "Estados Unidos": "@USMNT",
            "Curazao": "@CuracaoFutbol",
            "Costa de Marfil": "@FIFCI_tweet",
            "Túnez": "@FTF_OFFICIELLE",
            "Países Bajos": "@OnsOranje",
            "Japón": "@jfa_samuraiblue",
            "Suecia": "@svenskfotboll",
            "Paraguay": "@Albirroja",
            "Australia": "@Socceroos",
            "Sudáfrica": "@BafanaBafana",
            "Corea del Sur": "@theKFA"
        }
        
        from bs4 import BeautifulSoup
        try:
            content_clean = BeautifulSoup(content_snippet, "html.parser").get_text()
        except:
            content_clean = content_snippet
            
        prompt = f"""
        Eres el redactor de redes sociales para Pasión y Pelota.
        Tu tarea es transformar el siguiente título de artículo y su resumen en un tweet viral y llamativo que funcione como el título del post.
        
        TÍTULO ORIGINAL: {original_title}
        RESUMEN DEL CONTENIDO: {content_clean[:500]}
        
        REGLAS DEL TÍTULO DE REDES SOCIALES:
        1. Comienza con un emoji llamativo (como 🏆, 💥, ⚔️, ⚽, 😱, 😮, 🚨).
        2. Redacta un gancho viral, irónico, inteligente o emocionante de máximo 200 caracteres en total.
        3. Incluye obligatoriamente los handles/menciones de Twitter correspondientes a las selecciones involucradas si se encuentran en esta lista: {json.dumps(TEAM_HANDLES, ensure_ascii=False)}.
        4. Termina el título con los hashtags de Twitter adecuados (ejemplo: #Mundial2026 y hashtags de los países/equipos involucrados).
        5. Todo el título (incluyendo emojis, menciones y hashtags) debe ser una única línea de texto plano.
        
        Devuelve un JSON con exactamente este formato:
        {{
            "social_title": "El título en formato de tweet"
        }}
        """
        
        for model in models:
            for _ in range(len(config.GEMINI_API_KEYS)):
                api_key = config.get_active_key()
                if not api_key:
                    config.rotate_key()
                    continue
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                payload = {
                    "system_instruction": {"parts": [{"text": "Eres un experto en redes sociales y SEO deportivo."}]},
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "responseMimeType": "application/json",
                        "temperature": 0.6
                    }
                }
                try:
                    resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
                    if resp.status_code == 200:
                        data = resp.json()
                        text = data["candidates"][0]["content"]["parts"][0]["text"]
                        res = json.loads(text)
                        return res.get("social_title")
                    elif resp.status_code == 429:
                        config.rotate_key()
                except Exception as e:
                    logging.error(f"Error calling LLM in generate_social_title: {e}")
        return None

    def update_post(self, post_id: int, post_payload: dict) -> bool:
        """Actualiza una entrada existente en WordPress."""
        url = f"{self.url}/posts/{post_id}"
        try:
            response = requests.post(url, json=post_payload, headers=self._get_headers(), auth=self.auth)
            if response.status_code in [200, 201]:
                logging.info(f"Artículo ID {post_id} actualizado con éxito.")
                return True
            else:
                logging.error(f"Error al actualizar entrada ID {post_id} ({response.status_code}): {response.text}")
                return False
        except Exception as e:
            logging.error(f"Excepción al actualizar entrada ID {post_id} en WordPress: {e}")
            return False

# Instancia para pruebas directas si se ejecuta este archivo
if __name__ == "__main__":
    import sys
    print("Probando conector de WordPress...")
    publisher = WordPressPublisher()
    # Descomentar para realizar una prueba real si el usuario lo solicita:
    # publisher.publish_post("Prueba de Automatización", "<p>Hola Mundo. Este es un borrador automático.</p>", "Pruebas", ["Test"], "draft")
