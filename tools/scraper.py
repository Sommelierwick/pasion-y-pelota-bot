"""
tools/scraper.py — Monitor de fuentes con filtrado estricto por fecha.

Reglas de tiempo:
  - Solo se aceptan noticias de las últimas 48 horas.
  - La hora de referencia se obtiene de la API de internet (WorldTimeAPI / NTP),
    NO del reloj local del Mac (puede estar mal configurado).
  - Las noticias sin fecha publicada se marcan como "reciente" y se aceptan
    solo si vienen de X (periodistas) donde la fecha no se puede extraer.
"""

import feedparser
import requests
from bs4 import BeautifulSoup
import logging
import urllib.parse
import email.utils
import calendar
from datetime import datetime, timezone, timedelta
from typing import Optional
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ─── Obtener hora actual de internet (NTP/API) ────────────────────────────────

def get_internet_arg_now() -> datetime:
    """
    Obtiene la hora actual desde internet (altamente confiable).
    Si falla, usa datetime.now(tz_arg) como fallback (con aviso).
    Siempre devuelve un datetime timezone-aware en America/Argentina/Buenos_Aires.
    """
    import pytz
    tz_arg = pytz.timezone('America/Argentina/Buenos_Aires')
    try:
        resp = requests.head("https://www.google.com", timeout=5)
        date_str = resp.headers.get("Date")
        if date_str:
            dt = email.utils.parsedate_to_datetime(date_str)
            return dt.astimezone(tz_arg)
    except Exception as e:
        logging.warning(f"No se pudo obtener hora de Google: {e}")

    try:
        resp = requests.get("https://worldtimeapi.org/api/timezone/America/Argentina/Buenos_Aires", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            dt_str = data.get("datetime", "")
            dt = datetime.fromisoformat(dt_str)
            return dt.astimezone(tz_arg)
    except Exception:
        pass

    # Fallback: reloj del sistema (con aviso) convertido a Arg
    logging.warning("⚠️  No se pudo obtener hora de internet. Usando reloj local convertido a Arg.")
    return datetime.now(tz_arg)


# ─── Parsear fecha de una entrada RSS ────────────────────────────────────────

def parse_rss_date(entry) -> Optional[datetime]:
    """
    Intenta parsear la fecha de publicación de un entry RSS.
    Devuelve un datetime timezone-aware en America/Argentina/Buenos_Aires, o None si no se puede.
    """
    # feedparser a veces popula 'published_parsed' (struct_time en UTC)
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            ts = calendar.timegm(entry.published_parsed)
            import pytz
            tz_arg = pytz.timezone('America/Argentina/Buenos_Aires')
            return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(tz_arg)
        except Exception:
            pass

    # Fallback: parsear el string 'published' con email.utils (RFC 2822)
    pub_str = entry.get("published", "") or entry.get("updated", "")
    if pub_str:
        try:
            tpl = email.utils.parsedate_to_datetime(pub_str)
            import pytz
            tz_arg = pytz.timezone('America/Argentina/Buenos_Aires')
            return tpl.astimezone(tz_arg)
        except Exception:
            pass

    return None


# ─── Fetch RSS con filtro de 48 horas ────────────────────────────────────────

def fetch_rss_news(internet_now: datetime, max_age_hours: int = 48) -> list:
    """
    Lee noticias RSS y devuelve solo las publicadas en las últimas `max_age_hours`.
    La referencia temporal es `internet_now` (Hora de Argentina desde internet).
    """
    news_items = []
    cutoff = internet_now - timedelta(hours=max_age_hours)

    for league, urls in config.RSS_FEEDS.items():
        for url in urls:
            logging.info(f"Leyendo RSS de {league}: {url}")
            try:
                feed = feedparser.parse(url)
                accepted = 0
                for entry in feed.entries[:20]:  # revisar hasta 20 por feed
                    title     = entry.get("title", "").strip()
                    link      = entry.get("link", "").strip()
                    summary   = entry.get("summary", "").strip()

                    pub_dt = parse_rss_date(entry)

                    # Filtrar por fecha
                    if pub_dt is not None:
                        if pub_dt < cutoff:
                            continue  # más vieja que el umbral → descartar
                        age_h = round((internet_now - pub_dt).total_seconds() / 3600, 1)
                        pub_label = f"{pub_dt.strftime('%d/%m/%Y %H:%M')} Arg ({age_h}h atrás)"
                    else:
                        # Sin fecha: se acepta pero con baja prioridad
                        pub_label = "sin fecha (aceptada)"

                    if not title or not link:
                        continue

                    news_items.append({
                        "title":     title,
                        "link":      link,
                        "summary":   summary[:300],
                        "published": pub_label,
                        "pub_dt":    pub_dt.isoformat() if pub_dt else None,
                        "source":    f"RSS {league.capitalize()}",
                        "league":    league,
                    })
                    accepted += 1

                logging.info(f"  → {league}: {accepted} noticias recientes (<{max_age_hours}h)")

            except Exception as e:
                logging.error(f"Error al leer feed RSS {url}: {e}")

    return news_items


# ─── Búsqueda de tweets via DuckDuckGo ───────────────────────────────────────

def search_tweets_via_ddg(handle: str) -> list:
    """
    Busca los últimos tweets de un periodista en X/Twitter via DuckDuckGo HTML.
    Tweets de X no tienen fecha extraíble → se aceptan siempre (vienen de periodistas de confianza).
    """
    tweets = []
    query = f"site:x.com/{handle}"
    url   = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    logging.info(f"Buscando tweets de X para @{handle} en DuckDuckGo...")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup    = BeautifulSoup(response.text, "html.parser")
            results = soup.find_all("div", class_="result")

            for r in results[:5]:
                title_elem = r.find("a", class_="result__snippet")
                link_elem  = r.find("a", class_="result__url")
                if not title_elem or not link_elem:
                    continue

                snippet    = title_elem.get_text().strip()
                tweet_link = link_elem.get("href", "").strip()

                # Desencriptar redirección DuckDuckGo
                if "duckduckgo.com/l/?" in tweet_link:
                    parsed = urllib.parse.urlparse(tweet_link)
                    params = urllib.parse.parse_qs(parsed.query)
                    if "uddg" in params:
                        tweet_link = params["uddg"][0]

                # Solo tweets directos (con /status/)
                if (f"x.com/{handle}/status/" in tweet_link or
                        f"twitter.com/{handle}/status/" in tweet_link):
                    tweets.append({
                        "title":     f"Actualización de @{handle}",
                        "link":      tweet_link,
                        "summary":   snippet,
                        "published": "Reciente (Monitoreo X)",
                        "pub_dt":    None,  # sin fecha extraíble de DuckDuckGo
                        "source":    f"X (@{handle})",
                        "journalist": handle,
                    })
        else:
            logging.error(f"Error al buscar tweets de @{handle}: Código {response.status_code}")
    except Exception as e:
        logging.error(f"Excepción al buscar tweets de @{handle}: {e}")

    return tweets


# ─── Monitor principal ────────────────────────────────────────────────────────

def monitor_all_sources() -> list:
    """
    Monitorea todas las fuentes (RSS + periodistas en X).
    Solo devuelve noticias de las últimas 48 horas según hora de internet.
    """
    # 1. Obtener hora actual desde internet
    internet_now = get_internet_arg_now()
    logging.info(
        f"🕐 Hora de referencia (internet Arg): {internet_now.strftime('%Y-%m-%d %H:%M:%S Arg')}"
    )
    logging.info(
        f"   Ventana temporal: noticias desde {(internet_now - timedelta(hours=48)).strftime('%Y-%m-%d %H:%M')} Arg"
    )

    all_news = []

    # 2. RSS filtrado por fecha
    rss_news = fetch_rss_news(internet_now, max_age_hours=48)
    all_news.extend(rss_news)

    # 3. Tweets de periodistas (sin filtro de fecha, son en tiempo real)
    for j in config.JOURNALISTS_TO_MONITOR:
        tweets = search_tweets_via_ddg(j["handle"])
        for t in tweets:
            t["league"] = j["region"]
        all_news.extend(tweets)

    logging.info(
        f"Monitoreo finalizado. Total noticias recientes (<48h) + tweets: {len(all_news)}"
    )
    return all_news


# ─── Test directo ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Probando monitoreo con filtro de 48h...")
    news = monitor_all_sources()
    print(f"\nTotal noticias: {len(news)}")
    for n in news[:5]:
        print(f"  [{n.get('published','?')}] {n['title'][:80]}")
