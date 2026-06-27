import sys
import logging
import re
import requests
import asyncio
from typing import Tuple, Optional

sys.path.append("/Users/cristianbruno/Downloads/PAGINA WEB FUTBOL")
import config

logger = logging.getLogger(__name__)

def translate_to_english(html_content: str) -> str:
    """Traduce el contenido HTML de español a inglés usando el motor híbrido de IA,
    preservando la estructura de etiquetas HTML intacta."""
    from main_standalone import call_ai_json
    
    prompt = (
        "Translate the following article from Spanish to English. You MUST preserve all HTML tags "
        "and layout exactly as they are. Translate ONLY the user-facing text inside the HTML tags. "
        "Do not alter class names, tag structures, or properties:\n\n"
        f"{html_content}"
    )
    sys_prompt = (
        "You are an expert bilingual sports translator. You translate football news from Spanish to English "
        "precisely, preserving all HTML code structures and tags."
    )
    
    try:
        res = call_ai_json(prompt, sys_prompt)
        if res and "text" in res:
            return res["text"]
    except Exception as e:
        logger.error(f"Error al traducir artículo a inglés: {e}")
        
    return ""

def clean_html_for_speech(html: str) -> str:
    """Limpia el HTML para obtener texto plano optimizado para TTS,
    remplazando etiquetas de bloques por saltos de línea para generar pausas naturales."""
    # 1. Remplazar etiquetas de bloque con saltos de línea para pausas
    text = re.sub(r'</?(?:p|h1|h2|h3|h4|ul|ol|li|div|br)[^>]*>', '\n', html)
    # 2. Eliminar todas las etiquetas HTML restantes
    text = re.sub(r'<[^>]+>', '', text)
    # 3. Limpiar espacios y saltos de línea redundantes
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    # 4. Decodificar entidades HTML básicas
    text = text.replace("&nbsp;", " ").replace("&#8216;", "'").replace("&#8217;", "'").replace("&amp;", "&")
    return text.strip()

def generate_tts_edge(text: str, voice: str) -> Optional[bytes]:
    """Genera audio MP3 usando la API gratuita de Microsoft Edge TTS (streaming a memoria)."""
    import edge_tts
    
    # Calibración específica para lograr el estilo de relato deportivo argentino (rápido y grave)
    rate = "+10%" if voice == "es-AR-TomasNeural" else "+0%"
    pitch = "-2Hz" if voice == "es-AR-TomasNeural" else "+0Hz"
    
    async def amain():
        try:
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            audio_data = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data.extend(chunk["data"])
            return bytes(audio_data)
        except Exception as e:
            logger.error(f"Error en Edge TTS streaming ({voice}): {e}")
            return None
            
    try:
        return asyncio.run(amain())
    except Exception as e:
        logger.error(f"Excepción al ejecutar asyncio para Edge TTS ({voice}): {e}")
        return None

def generate_tts_google(text: str, lang: str, api_key: str) -> Optional[bytes]:
    """Genera audio MP3 usando la API de Google Cloud Text-to-Speech con API Key (requiere que esté habilitada en la consola)."""
    import base64
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}"
    
    # Voces de Google (Studio: altísima fidelidad y realismo natural)
    voice_name = "es-US-Studio-B" if lang == "es" else "en-GB-Studio-B"
    language_code = "es-US" if lang == "es" else "en-GB"
    
    payload = {
        'input': {'text': text[:4500]},
        'voice': {
            'languageCode': language_code,
            'name': voice_name
        },
        'audioConfig': {
            'audioEncoding': 'MP3',
            'speakingRate': 1.04,
            'pitch': -2.0
        }
    }
    
    try:
        logger.info(f"Intentando generar audio con Google Cloud TTS ({lang}, voz: {voice_name})...")
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            audio_content_b64 = response.json().get("audioContent", "")
            if audio_content_b64:
                logger.info(f"Audio generado con Google Cloud TTS con éxito ({lang}).")
                return base64.b64decode(audio_content_b64)
        else:
            logger.warning(f"Google Cloud TTS falló (HTTP {response.status_code}): {response.text}")
    except Exception as e:
        logger.warning(f"Excepción en Google Cloud TTS: {e}")
    return None

def rewrite_for_sports_narrator(title: str, text: str) -> str:
    """Reescribe la nota periodística al estilo de un relato o análisis deportivo de fútbol argentino
    (tipo Mariano Closs) para que al leerse con la voz es-AR suene natural, apasionado y profesional."""
    from main_standalone import call_ai_json
    
    prompt = (
        f"Reescribe la siguiente nota periodística titulada '{title}' para ser leída por un comentarista o relator deportivo argentino "
        "con el estilo, la pasión, el ritmo y los modismos característicos de Mariano Closs y el periodismo de fútbol rioplatense. "
        "Usa expresiones futbolísticas argentinas ('señoras y señores', 'el esférico', 'remate', 'pelota', 'córner', 'táctico', etc.) "
        "y dale un ritmo apasionado y experto. "
        "IMPORTANTE: Todos los datos numéricos, estadísticas, nombres de jugadores e información táctica deben permanecer 100% EXACTOS. "
        "No inventes información. "
        "Devuelve únicamente el texto plano reescrito para ser leído, sin indicaciones de escena, sin negritas, sin formato markdown:\n\n"
        f"{text}"
    )
    sys_prompt = (
        "Sos un redactor deportivo experto en transmisiones de fútbol argentino. Tu especialidad es adaptar "
        "artículos de noticias a guiones hablados al estilo de Mariano Closs, llenos de ritmo, pasión y jerga futbolística argentina."
    )
    
    try:
        res = call_ai_json(prompt, sys_prompt)
        if res and "text" in res:
            logger.info("Texto adaptado al estilo Mariano Closs con éxito.")
            return res["text"]
    except Exception as e:
        logger.error(f"Error al reescribir nota al estilo Closs: {e}")
        
    return text

def generate_tts_gemini(text: str, voice_name: str, sample_rate: int) -> Optional[bytes]:
    """Genera audio nativo usando el modelo gemini-3.1-flash-tts-preview de la API de Gemini
    y lo formatea como un archivo WAV reproducible con la tasa de muestreo (sample_rate) deseada."""
    import base64
    import wave
    import io
    
    api_key = config.GEMINI_API_KEYS[0]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-tts-preview:generateContent?key={api_key}"
    
    payload = {
        "contents": [{
            "parts": [{"text": text}]
        }],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": voice_name
                    }
                }
            }
        }
    }
    
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        if response.status_code == 200:
            data = response.json()
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            for part in parts:
                if "inlineData" in part and "audio" in part["inlineData"].get("mimeType", ""):
                    raw_pcm = base64.b64decode(part["inlineData"]["data"])
                    
                    # Convertir los bytes crudos PCM a formato WAV estándar
                    wav_io = io.BytesIO()
                    with wave.open(wav_io, "wb") as w:
                        w.setnchannels(1)       # Mono
                        w.setsampwidth(2)       # 16-bit
                        w.setframerate(sample_rate) # Tasa de muestreo (ej: 21000 para tono grave)
                        w.writeframes(raw_pcm)
                    
                    return wav_io.getvalue()
            logger.error("No se encontraron datos de audio en la respuesta de Gemini.")
        else:
            logger.error(f"Error en la API de Gemini TTS: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Excepción al llamar a Gemini TTS: {e}")
        
    return None

def generate_tts(text: str, lang: str = "es", voice: str = "onyx", model: str = "tts-1") -> Optional[bytes]:
    """Genera audio. Para español, usa Gemini TTS (Puck a 21000 Hz para tono grave y enérgico).
    Para inglés, usa la opción gratuita de Edge TTS para ahorrar costos."""
    audio_bytes = None
    
    if lang == "es":
        # Opción 1: Gemini TTS con la voz Puck ralentizada/bajado de tono a 21KHz
        logger.info("Generando audio en español usando Gemini TTS (Puck Grave 21KHz)...")
        audio_bytes = generate_tts_gemini(text, voice_name="Puck", sample_rate=21000)
        
        # Fallback a Edge TTS si Gemini falla
        if not audio_bytes:
            edge_voice = "es-AR-TomasNeural"
            logger.warning(f"Fallback a Edge TTS ({edge_voice}) por fallo en Gemini TTS.")
            audio_bytes = generate_tts_edge(text, edge_voice)
    else:
        # Para inglés, usar directamente la opción gratuita (Edge TTS) para ahorrar costos
        edge_voice = "en-GB-RyanNeural"
        logger.info(f"Generando audio en inglés usando la opción gratuita Edge TTS ({edge_voice})...")
        audio_bytes = generate_tts_edge(text, edge_voice)
            
    return audio_bytes

def upload_audio_to_wp(wp_publisher, file_bytes: bytes, filename: str) -> Optional[str]:
    """Sube un archivo de audio a la biblioteca multimedia de WordPress y retorna su URL."""
    media_url = f"{wp_publisher.url}/media"
    content_type = "audio/wav" if filename.endswith(".wav") else "audio/mpeg"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": content_type
    }
    try:
        response = requests.post(media_url, data=file_bytes, headers=headers, auth=wp_publisher.auth, timeout=45)
        if response.status_code in [200, 201]:
            media_data = response.json()
            source_url = media_data.get("source_url")
            logger.info(f"Audio subido con éxito a WordPress: {filename} -> {source_url}")
            return source_url
        else:
            logger.error(f"Error subiendo audio a WordPress ({filename}): HTTP {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Excepción al subir audio {filename} a WordPress: {e}")
        
    return None

def generate_and_upload_audios(wp_publisher, title_es: str, content_es_html: str) -> Tuple[Optional[str], Optional[str]]:
    """Traduce la nota, genera los audios en ambos idiomas y los sube a WordPress.
    Retorna una tupla (url_audio_es, url_audio_en)."""
    if not config.ENABLE_AUDIO_NARRATION:
        logger.info("Audio narración desactivada en la configuración.")
        return None, None
        
    logger.info("Iniciando flujo de generación de audio para el post...")
    
    # 1. Traducir contenido al inglés
    logger.info("Traduciendo nota a inglés...")
    content_en_html = translate_to_english(content_es_html)
    if not content_en_html:
        logger.warning("La traducción falló. Se usará el contenido en español como base para evitar fallas críticas.")
        content_en_html = content_es_html
        
    # 2. Limpiar textos para lectura por voz
    text_es_clean = clean_html_for_speech(content_es_html)
    text_en_clean = clean_html_for_speech(content_en_html)
    
    # Reescribir al estilo periodístico y de relato deportivo argentino (tipo Mariano Closs)
    text_es = rewrite_for_sports_narrator(title_es, text_es_clean)
    text_en = text_en_clean
    
    # Agregar introducción de estilo comentarista deportivo
    intro_es = f"¡Señoras y señores! Bienvenidos a Pasión y Pelota. Les presentamos el informe táctico para la jornada de hoy: {title_es}.\n\n"
    intro_en = f"Listening to Pasión y Pelota. Today's report: {title_es}.\n\n"
    
    text_es = intro_es + text_es
    text_en = intro_en + text_en
    
    # 3. Generar audios (con fallback automático a Edge TTS)
    audio_es_bytes = generate_tts(text_es, lang="es", voice=config.TTS_VOICE, model=config.TTS_MODEL)
    audio_en_bytes = generate_tts(text_en, lang="en", voice=config.TTS_VOICE, model=config.TTS_MODEL)
    
    if not audio_es_bytes or not audio_en_bytes:
        logger.error("No se pudieron generar los audios en ambos idiomas. Abortando inyección de audio.")
        return None, None
        
    # Crear nombres únicos de archivo
    import time
    timestamp = int(time.time())
    clean_title = re.sub(r'[^a-zA-Z0-9]', '_', title_es)[:30].strip('_').lower()
    
    filename_es = f"audio_es_{clean_title}_{timestamp}.wav"
    filename_en = f"audio_en_{clean_title}_{timestamp}.mp3"
    
    # 4. Subir a WordPress
    logger.info("Subiendo audios a la biblioteca de WordPress...")
    url_es = upload_audio_to_wp(wp_publisher, audio_es_bytes, filename_es)
    url_en = upload_audio_to_wp(wp_publisher, audio_en_bytes, filename_en)
    
    return url_es, url_en
