import requests
import logging
import io
import os
from typing import List, Optional
from requests.auth import HTTPBasicAuth
import config
from tools.images import strip_watermark, get_used_images, mark_image_used

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
                img_content = img_response.content
            else:
                local_path = image_url
                if local_path.startswith("file://"):
                    local_path = local_path.replace("file://", "", 1)
                
                if not os.path.exists(local_path):
                    logging.error(f"No se encontró el archivo de imagen local: {local_path}")
                    return None
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

    def publish_post(self, title: str, content: str, league_category = "Noticias", tags: List[str] = None, status: str = "publish", featured_image_id: Optional[int] = None, seo_desc: Optional[str] = None, writer: Optional[str] = None, date: Optional[str] = None) -> Optional[dict]:
        """
        Publica una entrada en WordPress.
        
        Args:
            title: Título de la entrada.
            content: Contenido HTML del artículo.
            league_category: Nombre de la categoría (o lista de nombres de categorías).
            tags: Lista de nombres de etiquetas (jugadores, equipos).
            status: 'publish' para publicar de inmediato, 'draft' para guardarlo como borrador.
            featured_image_id: ID del attachment de imagen destacada (opcional).
            seo_desc: Meta descripción para SEO/GEO invisible (opcional).
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
        
        if date:
            post_payload["date"] = date
        
        if seo_desc:
            post_payload["meta"]["ppelota_seo_desc"] = seo_desc
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
                
                # Ejecutar purga de notas excedentes según la ORDEN SUPREMA (máximo 30)
                self.enforce_limit(30)
                
                return published_post
            else:
                logging.error(f"Error al publicar entrada en WordPress ({response.status_code}): {response.text}")
                return None
        except Exception as e:
            logging.error(f"Excepción al publicar entrada en WordPress: {e}")
            return None

    def enforce_limit(self, limit: int = 30):
        """Mantiene un límite estricto de posts en el portal, eliminando los más antiguos."""
        url = f"{self.url}/posts?per_page=100&orderby=date&order=desc"
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
            logging.warning(f"ORDEN SUPREMA LÍMITE: Eliminando {len(posts_to_delete)} notas para mantener exactamente {limit} en portada.")
            
            for post in posts_to_delete:
                post_id = post["id"]
                update_url = f"{self.url}/posts/{post_id}"
                try:
                    update_payload = {"status": "draft"}
                    r = requests.post(update_url, json=update_payload, headers=self._get_headers(), auth=self.auth, timeout=15)
                    if r.status_code in [200, 201]:
                        logging.info(f"Nota ID {post_id} movida a borrador exitosamente.")
                    else:
                        logging.error(f"Error moviendo a borrador la nota ID {post_id}: HTTP {r.status_code}")
                except Exception as e:
                    logging.error(f"Excepción al mover nota a borrador: {e}")

                    
        except Exception as e:
            logging.error(f"Excepción general en enforce_limit: {e}")

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
