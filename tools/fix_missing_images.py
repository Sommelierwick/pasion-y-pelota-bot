import requests
from requests.auth import HTTPBasicAuth
from PIL import Image
import io
import os
import sys
from typing import Optional

sys.path.append("/Users/cristianbruno/Downloads/PAGINA WEB FUTBOL")
import config
from tools.images import get_football_image

auth = HTTPBasicAuth(config.WP_USER, config.WP_PASSWORD)
url_base = config.WP_URL.rstrip('/')

def download_and_optimize(image_url: str) -> Optional[bytes]:
    """Descarga una imagen de una URL y la optimiza usando PIL para bajarle el peso."""
    try:
        headers = {
            "User-Agent": "PasionYPelotaBot/1.0 (contact: elrojobruno@gmail.com) Python-requests/2.31.0"
        }
        r = requests.get(image_url, headers=headers, timeout=15)
        if r.status_code == 200:
            img = Image.open(io.BytesIO(r.content))
            print(f"Original image size: {img.size}, format: {img.format}")
            
            # Convert to RGB if needed (e.g. PNG with alpha)
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                img = img.convert('RGB')
                
            # Resize
            max_w = 1024
            w, h = img.size
            if w > max_w:
                ratio = max_w / w
                new_size = (max_w, int(h * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                print(f"Resized image to: {img.size}")
                
            # Compress and save to bytes
            out_io = io.BytesIO()
            img.save(out_io, format="JPEG", quality=75, optimize=True)
            optimized_data = out_io.getvalue()
            print(f"Compressed weight: {len(optimized_data)/1024:.2f} KB (originally {len(r.content)/1024:.2f} KB)")
            return optimized_data
    except Exception as e:
        print(f"Error optimizing image from {image_url}: {e}")
    return None

def upload_and_set_featured(post_id: int, image_url: str, filename: str):
    print(f"\n--- Procesando Post ID {post_id} ---")
    img_data = download_and_optimize(image_url)
    if not img_data:
        print("No se pudo obtener/optimizar la imagen.")
        return False
        
    # Subir a la biblioteca de medios
    media_url = f"{url_base}/wp-json/wp/v2/media"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "image/jpeg"
    }
    
    resp = requests.post(media_url, data=img_data, headers=headers, auth=auth)
    if resp.status_code in [200, 201]:
        media_id = resp.json().get("id")
        print(f"✅ Imagen subida. ID del media: {media_id}")
        
        # Asignar al post
        post_url = f"{url_base}/wp-json/wp/v2/posts/{post_id}"
        post_resp = requests.post(post_url, json={"featured_media": media_id}, auth=auth)
        if post_resp.status_code == 200:
            print(f"✅ Imagen destacada asignada con éxito al post ID {post_id}!")
            return True
        else:
            print(f"❌ Error al asignar imagen ({post_resp.status_code}): {post_resp.text}")
    else:
        print(f"❌ Error al subir imagen ({resp.status_code}): {resp.text}")
    return False

# 1. Post ID 8: Ferran Torres brilla con Barcelona
print("Buscando imagen de Ferran Torres...")
img_ferran = get_football_image("Ferran Torres", "FC Barcelona")
print(f"Resultado Ferran Torres: {img_ferran}")
if img_ferran:
    upload_and_set_featured(8, img_ferran["url"], "ferran_torres.jpg")

# 2. Post ID 6: El Celta de Vigo
print("\nBuscando imagen de Celta de Vigo...")
img_celta = get_football_image("Celta de Vigo", "Celta de Vigo")
print(f"Resultado Celta de Vigo: {img_celta}")
if img_celta:
    upload_and_set_featured(6, img_celta["url"], "celta_de_vigo.jpg")

print("\nProceso de asignación de fotos finalizado.")
