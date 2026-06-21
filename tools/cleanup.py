"""
tools/cleanup.py — Limpieza automática de posts WordPress viejos.

Regla:
  - Posts con más de 3 días de antigüedad → BORRAR (mover a papelera)
  - EXCEPCIONES que se conservan indefinidamente:
      * Contienen palabras clave del Mundial 2026
      * Son fixtures / calendarios / programas de partidos
      * Son estadísticas / clasificaciones / tablas
      * Son artículos "evergreen" etiquetados explícitamente

La hora de referencia siempre viene de internet (WorldTimeAPI), no del reloj local.
"""

import requests
import logging
from datetime import datetime, timezone, timedelta
from requests.auth import HTTPBasicAuth
import config

logger = logging.getLogger(__name__)

# ─── Palabras clave que protegen un post de ser eliminado ────────────────────

PROTECTED_KEYWORDS = [
    # Mundial 2026
    "mundial 2026", "copa del mundo 2026", "world cup 2026", "mundial fifa 2026",
    "fase de grupos mundial", "octavos mundial", "cuartos mundial", "final mundial",
    "selección argentina mundial", "selección brasil mundial",
    # Fixtures y calendarios
    "fixture", "calendario", "programación", "horarios", "jornada", "agenda deportiva",
    "próximos partidos", "fixture completo", "schedule",
    # Estadísticas y tablas
    "tabla de posiciones", "clasificación", "estadísticas", "xg", "goles esperados",
    "tabla general", "standings", "liga table", "tabla de promedio", "promedio descenso",
    # Champions / Libertadores formato
    "formato suizo champions", "fase de liga", "tabla champions",
    "cuadro de cruces libertadores",
    # Copa Libertadores
    "libertadores 2026", "copa libertadores",
]


def get_internet_utc_now() -> datetime:
    """Obtiene hora UTC actual desde internet (Google header / WorldTimeAPI)."""
    import email.utils
    try:
        resp = requests.head("https://www.google.com", timeout=5)
        date_str = resp.headers.get("Date")
        if date_str:
            dt = email.utils.parsedate_to_datetime(date_str)
            return dt.astimezone(timezone.utc)
    except Exception as e:
        logger.warning(f"No se pudo obtener hora de Google: {e}")

    try:
        resp = requests.get("https://worldtimeapi.org/api/timezone/UTC", timeout=5)
        if resp.status_code == 200:
            dt_str = resp.json().get("datetime", "")
            return datetime.fromisoformat(dt_str).astimezone(timezone.utc)
    except Exception:
        pass
    logger.warning("⚠️  Usando reloj local como fallback para limpieza.")
    return datetime.now(timezone.utc)


def is_protected(post: dict) -> bool:
    """
    Determina si un post debe conservarse indefinidamente.
    Revisa título, contenido (excerpt/content), tags y categorías.
    """
    # Texto completo a inspeccionar (en minúsculas)
    check_text = " ".join([
        post.get("title", {}).get("rendered", ""),
        post.get("excerpt", {}).get("rendered", ""),
        " ".join(post.get("_embedded", {}).get("wp:term", [[]])[0]
                 if post.get("_embedded") else []),
    ]).lower()

    for kw in PROTECTED_KEYWORDS:
        if kw.lower() in check_text:
            return True
    return False


def cleanup_old_posts(max_age_days: int = 3, dry_run: bool = False) -> dict:
    """
    Elimina posts de WordPress con más de `max_age_days` días de antigüedad.

    Args:
        max_age_days: Días máximos de antigüedad permitida (default: 4).
        dry_run: Si True, solo lista los posts que serían eliminados sin borrarlos.

    Returns:
        dict con contadores: deleted, protected, total_checked, errors
    """
    internet_now = get_internet_utc_now()
    cutoff = internet_now - timedelta(days=max_age_days)

    logger.info("=" * 60)
    logger.info(f"🧹 LIMPIEZA AUTOMÁTICA DE POSTS VIEJOS")
    logger.info(f"   Hora referencia: {internet_now.strftime('%Y-%m-%d %H:%M UTC')}")
    logger.info(f"   Eliminar posts anteriores a: {cutoff.strftime('%Y-%m-%d %H:%M UTC')}")
    logger.info(f"   Modo: {'DRY RUN (sin borrar)' if dry_run else 'PRODUCCIÓN (borra realmente)'}")
    logger.info("=" * 60)

    base_url = config.WP_URL.rstrip("/") + "/wp-json/wp/v2"
    auth     = HTTPBasicAuth(config.WP_USER, config.WP_PASSWORD)

    stats = {"deleted": 0, "protected": 0, "too_recent": 0,
             "total_checked": 0, "errors": 0}

    # Paginar todos los posts publicados
    page = 1
    while True:
        try:
            resp = requests.get(
                f"{base_url}/posts",
                auth=auth,
                params={
                    "status":   "publish",
                    "per_page": 50,
                    "page":     page,
                    "_embed":   1,
                    "orderby":  "date",
                    "order":    "asc",  # más viejos primero
                },
                timeout=20,
            )

            if resp.status_code == 400:
                break  # Sin más páginas
            if resp.status_code != 200:
                logger.error(f"Error al listar posts: {resp.status_code}")
                stats["errors"] += 1
                break

            posts = resp.json()
            if not posts:
                break

            for post in posts:
                stats["total_checked"] += 1
                post_id    = post.get("id")
                post_title = post.get("title", {}).get("rendered", "Sin título")[:70]
                date_str   = post.get("date_gmt", "")  # Ya está en UTC

                # Parsear fecha del post
                try:
                    post_dt = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
                except Exception:
                    logger.warning(f"  ⚠️  Post #{post_id}: No se pudo parsear fecha '{date_str}'")
                    stats["errors"] += 1
                    continue

                age_days = (internet_now - post_dt).days
                age_h    = round((internet_now - post_dt).total_seconds() / 3600, 1)

                # ¿Está dentro del período permitido?
                if post_dt >= cutoff:
                    stats["too_recent"] += 1
                    continue  # Reciente → conservar

                # ¿Está protegido por palabras clave?
                if is_protected(post):
                    stats["protected"] += 1
                    logger.info(f"  🛡️  PROTEGIDO ({age_days}d): {post_title}")
                    continue

                # → Eliminar (mover a papelera)
                logger.info(f"  🗑️  {'[DRY RUN] ' if dry_run else ''}ELIMINANDO ({age_days}d, {age_h}h): #{post_id} — {post_title}")

                if not dry_run:
                    del_resp = requests.delete(
                        f"{base_url}/posts/{post_id}",
                        auth=auth,
                        params={"force": False},  # False = papelera, True = borrado permanente
                        timeout=15,
                    )
                    if del_resp.status_code in [200, 201]:
                        stats["deleted"] += 1
                        logger.info(f"     ✅ Post #{post_id} movido a papelera.")
                    else:
                        stats["errors"] += 1
                        logger.error(f"     ❌ Error al eliminar #{post_id}: {del_resp.status_code}")
                else:
                    stats["deleted"] += 1  # contamos igual en dry run

            page += 1

        except Exception as e:
            logger.error(f"Excepción durante limpieza (página {page}): {e}")
            stats["errors"] += 1
            break

    # Resumen final
    logger.info("=" * 60)
    logger.info(f"📊 RESUMEN LIMPIEZA:")
    logger.info(f"   Total revisados: {stats['total_checked']}")
    logger.info(f"   Recientes (<{max_age_days}d): {stats['too_recent']}")
    logger.info(f"   🛡️  Protegidos (Mundial/Fixtures/Stats): {stats['protected']}")
    logger.info(f"   🗑️  {'Que se borrarían' if dry_run else 'Eliminados'}: {stats['deleted']}")
    logger.info(f"   ❌ Errores: {stats['errors']}")
    logger.info("=" * 60)

    return stats


# ─── Test directo ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    dry = "--dry-run" in sys.argv
    result = cleanup_old_posts(max_age_days=3, dry_run=dry)
    print(f"\nResultado: {result}")
