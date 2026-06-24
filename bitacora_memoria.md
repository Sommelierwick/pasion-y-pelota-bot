# Bitácora de Memoria: Proyecto Pasión y Pelota (Bot Mundial 2026)
*Última actualización: 22 de Junio de 2026*

Este documento sirve como registro oficial y verificado (sin alucinaciones) de todas las modificaciones, reglas y arquitecturas establecidas en las sesiones de trabajo. Debe ser consultado por cualquier agente antes de realizar modificaciones estructurales.

## 1. Arquitectura del Proyecto
- **Orquestador Principal:** `main_standalone.py`. Se encarga de correr el pipeline.
- **Módulos de Apoyo:** 
  - `tools/editor_jefe.py`: Maneja lógicas de post-procesamiento, sanitización de datos y actualización de widgets/semáforo.
  - `tools/images.py`: Genera y optimiza las imágenes IA.
  - `tools/wordpress.py`: Se conecta vía API REST para publicar y actualizar entradas, tags, categorías y portadas en WordPress.
- **Automatización en la Nube (100% Free):** El bot corre de manera autónoma sin necesidad de la Mac encendida gracias a **GitHub Actions**. El archivo `.github/workflows/publish_news.yml` se ejecuta vía cron cada 30 minutos, instalando dependencias y corriendo `main_standalone.py --mode publish`.

## 2. Reglas Editoriales y de Negocio (Estrictas)
1. **Fuente de Datos:** La fuente oficial de la verdad para horarios y estadísticas es `https://www.promiedos.com.ar/league/fifa-world-cup/fjda`.
2. **Huso Horario:** Todos los horarios publicados en los artículos o en el frontend deben estar estrictamente en UTC-3 (Hora de Argentina).
3. **Jerarquía de Noticias:** Argentina, Francia, España y Portugal tienen máxima prioridad en la cobertura.
4. **Sedes Neutrales:** El Mundial 2026 se juega en Estados Unidos, México y Canadá. Salvo los anfitriones, ninguna selección juega de local en su estadio habitual (ej. Argentina no juega en el Monumental, juega en estadios como el MetLife de Norteamérica).
5. **Generación de Notas (Previas, Durante y Post):** El flujo debe asegurar previas completas de los partidos, reportes de medio tiempo ("durante") y cierres definitivos ("post").

## 3. Modificaciones Implementadas Recientemente (Historial)

### A. Corrección de Horarios
- Se detectó un error donde el bot publicaba horas incorrectas y desfasadas. Se forzó el chequeo y respeto de la zona horaria UTC-3.

### B. Gestión y Política Estricta de Imágenes
El manejo visual del sitio se rige por un esquema híbrido (Imágenes de Archivo + Generación IA) altamente regulado:
1. **Conferencias de Prensa de Entrenadores (Prioridad 1 - Máxima Absoluta):**
   - Como primera opción SIEMPRE se debe priorizar el uso de fotos de las conferencias de prensa de los entrenadores o directores técnicos, ya que suelen tener derechos libres.
   - **Condición estricta:** Deben corresponder obligatoriamente al Mundial FIFA 2026 y ser específicamente del equipo o del partido que se está tratando en la nota.
2. **Derechos de Autor y Wikimedia Commons (Prioridad 2):** 
   - No se usa el nombre del país a secas para evitar fotos fuera de contexto (paisajes o políticos). Se usa siempre la fórmula: `{equipo} national football team` o `Selección de fútbol de {equipo}`.
   - Obligación absoluta de incrustar la **Atribución CC** exacta al pie de la foto: `Foto: [Autor] / Licencia [Licencia]`. No sirve poner "Fuente: Google".
3. **Generación IA con Pollinations (Flux-Realism) (Prioridad 3 - Último Recurso):**
   - Cuando no hay fotos de conferencias ni libres disponibles, se utiliza IA, pero bajo un estricto prompt "Director de Arte" generado por Gemini.
   - **Regla inquebrantable:** El prompt debe exigir *"Award-winning Getty Images sports photography"*. Están terminantemente prohibidas las ilustraciones, anime, renders 3D o textos incrustados. La imagen debe tener contexto absoluto con el texto de la nota.
4. **Mantenimiento Retroactivo:**
   - Se estableció la directiva de delegar en **Subagentes (mínimo 4 simultáneos)** la tarea de recorrer notas antiguas, buscar fotos IA de mala calidad (cartoons) y reemplazarlas en segundo plano.

### C. Sanitización de Estadísticas (Países vs Jugadores)
- Había un bug crítico donde el sistema listaba el nombre de un país (ej. "Argentina") en las tablas estadísticas de jugadores (ej. "Pases Correctos").
- Se corrigió modificando `tools/editor_jefe.py`, agregando lógica de sanitización y prompeo estricto para que la IA entienda que si no encuentra 10 jugadores, devuelva menos, pero jamás invente con el nombre del país.

### D. Adaptación a Fase Eliminatoria (Muerte Súbita)
- Se actualizaron los cerebros `DOCUMENTALISTA_WORLD_CUP_SYSTEM` y `REDACTOR_WORLD_CUP_SYSTEM` en `main_standalone.py`.
- El sistema ahora entiende que a partir de Octavos de Final **no hay tablas de puntos**, sino clasificaciones a Cuartos de final, posibilidad de alargue y definición por penales. El redactor SEO ahora inserta "brackets" (llaves) en lugar de tablas de clasificación en esta fase.

## 4. Uso de Subagentes
- Se incorporó la metodología de trabajar con 4 a 5 subagentes simultáneos para tareas masivas (como regenerar todas las imágenes defectuosas del pasado o auditar notas), ahorrando tiempo de ejecución del hilo principal.

## 5. Infraestructura y Servicios (Servidores y Claves)
El ecosistema completo se apoya en los siguientes servidores y APIs. Por motivos de seguridad y buenas prácticas, las contraseñas exactas están parcialmente enmascaradas en este documento de texto, pero se leen en texto plano desde el archivo oculto `.env` (en Mac) y desde **GitHub Secrets** (en la nube).

### Servidores Activos:
1. **GitHub Actions (Orquestador Cloud):** Servidor Ubuntu efímero provisto por GitHub que levanta el entorno, corre el bot y se apaga cada 30 minutos de forma 100% gratuita.
2. **WordPress (Frontend/CMS):** `https://pasionypelota.com` - Es el servidor final donde publicamos la información periodística mediante su REST API.
3. **Pollinations.ai:** Servidor en la nube libre y gratuito utilizado para procesar imágenes con Flux-Realism.
4. **DuckDuckGo (Scraping):** Se utiliza indirectamente a través del código para hacer consultas web rápidas sin API Key.

### API Keys y Credenciales (Mapeo):
- **WordPress User (`WP_USER`):** `cristianbruno@circulorojomkt.com`
- **WordPress App Password (`WP_PASSWORD`):** `W8OnfO****************QueK`
- **Google Gemini (`GEMINI_API_KEYS`):** Arreglo de 3 claves rotativas para evitar Rate Limits (429). Empiezan con `AQ.Ab8RN6LLr...`, `AQ.Ab8RN6Jzy...`, y `AQ.Ab8RN6JVF...`
- **Groq API (`GROQ_API_KEY`):** `gsk_wAyl****************************************9xOe`
- **OpenAI API (`OPENAI_API_KEY`):** `sk-proj-8xpn************************************************************************BXMA`

*Nota Técnica:* Si alguna clave caduca, no se debe modificar este archivo. Se debe modificar el `.env` local y los *Secrets* en el repositorio de GitHub para que la nube lo tome.

---
*Fin de la bitácora. Consultar este archivo periódicamente.*

### ORDEN SUPREMA: TyC Sports
**REGLA:** A partir del 22 de junio de 2026, **está permitido usar fotos de TyC Sports** siempre que respeten el contexto de la noticia y **SE DEBE CITAR LA FUENTE** ("Foto: TyC Sports / [Contexto]").
**Implementación:** Se agregó `search_tycsports_images` en `tools/images.py` como **Prioridad 2**, buscando el término del equipo/jugador en el buscador oficial de TyC Sports y obteniendo la versión en alta resolución (862x485).

### Órdenes Supremas Actualizadas (2026-06-22)
1. **NO PUEDEN REPETIRSE FOTOS**: Se ha implementado un archivo `used_images.json` para llevar el control global de todas las imágenes usadas en los artículos. Ningún artículo puede volver a usar la misma imagen.
2. **TABLA DE GOLEADORES EXACTA DE PROMIEDOS**: Queda ESTRICTAMENTE PROHIBIDO que el modelo de IA invente goleadores. Las estadísticas de Goleadores, Asistencias y Pases deben extraerse *única y exclusivamente* del campo `players_statistics` del JSON interno de Promiedos, sin alteraciones.
3. **AUDITORÍA DE FOTOS**: Es obligatorio usar agentes para auditar las fotos de los artículos publicados y asegurarse de que cumplan con el contexto.

* **[REGLA INCORPORADA - JUNIO 2026]**: ORDEN SUPREMA: SOLO FOTOS DEL MUNDIAL FIFA 2026. Todas las imágenes deben coincidir estrictamente con el contexto de la noticia y pertenecer a la cita mundialista actual (2026), evitando fotos viejas de mundiales pasados (2022 o 2018).

6. **DIRECTRIZ SUPREMA EDITORIAL (Agregado el 24/06/2026):** Actualidad estricta (solo noticias de HOY). Equilibrio matemático y narrativo de potencias (Argentina, Francia, Inglaterra, Brasil, España, etc.). Des-messificación de Argentina (obligación de destacar táctica de Scaloni, Dibu Martínez, Lautaro, De Paul) y destaque de estrellas globales (Mbappé, Kane, Vinícius, Lamine Yamal).

7. **SISTEMA DE AUTODOCUMENTACIÓN:** Cada vez que se dicte una 'ORDEN SUPREMA', el agente debe registrar invariablemente los cambios estructurales en este archivo () para asegurar la trazabilidad del código y las normativas.

7. **SISTEMA DE AUTODOCUMENTACIÓN:** Cada vez que se dicte una ORDEN SUPREMA, el agente debe registrar invariablemente los cambios estructurales en este archivo bitacora_memoria.md para asegurar la trazabilidad del código y las normativas.

8. **ORDEN SUPREMA (24/06/2026) - PORTADA Y PARTIDOS:** Se corrigió un error crítico donde los partidos de las fases eliminatorias (Octavos, Cuartos, Semi y Final) no aparecían en las marquesinas. Se inyectó lógica para parsear los brackets y asegurar que el frontend nunca más quede desactualizado o vacío, incluso en días de descanso del Mundial.
9. **ORDEN SUPREMA (24/06/2026) - REFACTORIZACIÓN DINÁMICA DE MARQUESINAS:** Para evitar que los filtros de seguridad de WordPress (wp_kses_post) eliminen el HTML pre-renderizado por Python y muestren partidos "fantasma" del pasado por fallback, se refactorizó el código fuente del tema (PHP). Ahora, tanto la marquesina de "Próximos Encuentros" como la de "En Vivo" se construyen de forma dinámica y directa sobre la base de datos cruda del Mundial (`ppelota_mundial_data`), garantizando una actualización 100% robusta y en tiempo real sin vulnerabilidades de renderizado.

---

## 6. AUDITORÍA Y CORRECCIONES — 24 de Junio de 2026 (12:08 GMT-3)

**Commit de producción:** `9a105d9` — Branch `main` — Repositorio `Sommelierwick/pasion-y-pelota-bot`
**Archivos modificados:** `main_standalone.py`, `tools/editor_jefe.py`, `tools/images.py`, `tools/cleanup.py`, `.github/workflows/publish_news.yml`

Se realizó una auditoría profunda del sistema durante un día de partido del Mundial 2026 (sin días de descanso). Se encontraron y corrigieron 8 bugs en el siguiente orden de prioridad:

---

### CORRECCIÓN 1 — Modelos Gemini inexistentes
**Archivos:** `main_standalone.py` (L248-255) y `tools/editor_jefe.py` (L104-111)
**Bug:** La lista `models_to_try` contenía nombres de modelos que no existen en la API de Google Gemini: `gemini-3.1-flash-lite`, `gemini-3.1-flash-lite-preview`, `gemini-3-flash-preview`, `gemini-3.5-flash`, `gemini-flash-latest`. Cada uno provocaba un HTTP 404 silencioso, haciendo que el bot desperdiciara tiempo y cuota antes de caer al modelo válido.
**Corrección:** Se reemplazó la lista en ambos archivos por los modelos reales disponibles en junio 2026:
```python
models_to_try = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash-latest"
]
```

---

### CORRECCIÓN 2 — `{horario}` y `{resultado}` nunca se reemplazaban correctamente
**Archivo:** `main_standalone.py` (L1416-1434)
**Bug:** El código intentaba acceder a `g.get("home", {}).get("name", "")` pero en `fetch_mundial_complete_data()` (de `tools/promiedos.py`), los campos `home` y `away` de cada game son **strings directos**, no diccionarios. Además, el resultado se buscaba en `g.get("scores", [])` cuando en realidad los goles están en `home_goals` y `away_goals` como campos directos del dict. Consecuencia: todos los artículos del Mundial publicaban literalmente `{horario}` y `{resultado}` sin reemplazar.
**Corrección:** Se corrigió el acceso con un check de tipo (`isinstance(g.get("home"), str)`) y se reemplazó la lectura de scores por `home_goals`/`away_goals`.

---

### CORRECCIÓN 3 — Motor del Mundial publicaba previas de partidos de otros días
**Archivo:** `main_standalone.py` (L422-439)
**Bug:** El motor `run_worldcup_coverage_engine()` ordenaba los partidos por prioridad (`is_today` primero), pero nunca descartaba activamente los partidos de días anteriores con `continue`. Podía generar previas para partidos que ya habían terminado el día anterior y aún estaban en la API de Promiedos.
**Corrección:** Se agregó un bloque de filtro estricto de fecha justo después de limpiar los goles:
```python
# FILTRO ESTRICTO DE FECHA (Directriz Suprema: solo noticias de HOY)
start_time_str = g.get("start_time", "")
is_today = start_time_str.startswith(today_arg) if start_time_str else False
partido_activo = status not in ["Prog.", "Progr."] and not (home_goals == "-" and away_goals == "-")

if not is_today and not partido_activo:
    logging.info(f"Saltando {home} vs {away}: no es partido de hoy ({today_arg}) y no está activo.")
    continue
```
Esto garantiza que solo se generen artículos de partidos que **ocurren hoy** o que están en progreso activo.

---

### CORRECCIÓN 4 — Regla 9: límite de 30 posts no implementada
**Archivo:** `main_standalone.py` (L1676-1706)
**Bug:** La Regla 9 de la bitácora ("después de cada publish, si el total supera 30 posts, mover el más antiguo a draft") no tenía ninguna implementación en el código. El sitio podía acumular posts indefinidamente.
**Corrección:** Se implementó el bloque completo después de cada publicación exitosa:
```python
# Tras cada publish: GET /wp/v2/posts con per_page=1&order=asc
# Leer X-WP-Total del header
# Si supera 30: PATCH del post más antiguo con status: draft
```
Usa el módulo `requests` ya importado y las credenciales de `config.WP_USER` / `config.WP_PASSWORD`.

---

### CORRECCIÓN 5 — Cleanup usaba papelera (DELETE), no draft
**Archivo:** `tools/cleanup.py` (L177-189)
**Bug:** La función `cleanup_old_posts()` usaba `requests.delete()` para mover posts a la papelera de WordPress (`force: False`). La Regla 9 de la bitácora exige **`draft`** (estado recuperable), no papelera.
**Corrección:** Se reemplazó `requests.delete()` por `requests.patch()` con `json={"status": "draft"}`.

---

### CORRECCIÓN 6 — `used_images.json` no se commiteaba en GitHub Actions
**Archivo:** `.github/workflows/publish_news.yml` (paso "Commit and Push Database Updates")
**Bug:** El workflow solo commiteaba `database.json`. El archivo `used_images.json`, que controla el anti-duplicado de imágenes, se perdía al final de cada ejecución efímera de GitHub Actions. Consecuencia: en cada ciclo nuevo, el bot podía reusar fotos ya publicadas.
**Corrección:** Se modificó el paso de commit para detectar y agregar `used_images.json` si tiene cambios:
```bash
if git status --porcelain | grep -q "used_images.json"; then
    git add used_images.json
    CHANGED="$CHANGED used_images.json"
fi
```

---

### CORRECCIÓN 7 — Jacinto Perplejo mencionaba explícitamente a "Lionel Messi" en su prompt
**Archivo:** `main_standalone.py` (L748)
**Bug:** La regla 3 del prompt de `JACINTO_SYSTEM` decía: *"Cita y menciona a los jugadores clave... como Deniz Undav, **Lionel Messi** o Alexander Isak"*. Esto violaba la Directriz Suprema de Des-Messificación al inducir al LLM a nombrar a Messi explícitamente incluso cuando no era el protagonista.
**Corrección:** Se eliminó la mención de Messi como ejemplo y se reemplazó por instrucciones más generales y más descriptivas de la política editorial:
- Para Argentina: obligación de destacar a Scaloni, Dibu, Lautaro, De Paul, Enzo.
- Para otras potencias: mencionar a Mbappé, Kane/Bellingham, Vinícius.
- Nunca centrar en Messi cuando hay análisis táctico de Argentina.

---

### CORRECCIÓN 8 — `from PIL import Image` faltaba en `tools/images.py`
**Archivo:** `tools/images.py` (imports globales, L18)
**Bug:** La función `strip_watermark()` usaba `Image.open(local_path)` pero `Image` solo se importaba dentro de `verify_image_suitability()` (import local). Si `strip_watermark()` se llamaba directamente desde otro contexto, arrojaba `NameError: name 'Image' is not defined`.
**Corrección:** Se agregó `from PIL import Image` al bloque de imports globales del módulo, junto al resto de las importaciones estándar.

---

### CORRECCIÓN ADICIONAL — Des-Messificación en el prompt del Ojeador
**Archivo:** `main_standalone.py` (L1037)
**Bug:** El clúster `messi_seleccion` estaba definido en el prompt del Ojeador sin ninguna aclaración sobre su cobertura real. El LLM lo interpretaba como un clúster destinado exclusivamente a Messi.
**Corrección:** Se agregó una nota aclaratoria en la línea de instrucción del Ojeador:
```
messi_seleccion (= Selección Argentina en su conjunto — DES-MESSIFICACIÓN:
usar para noticias de Scaloni, Dibu, Lautaro, De Paul, Enzo, no solo Messi)
```

---

### Estado de bugs post-auditoría:
| Bug | Severidad original | Estado |
|---|---|---|
| Modelos Gemini falsos | 🔴 Crítico | ✅ Corregido |
| {horario}/{resultado} nunca reemplazados | 🔴 Crítico | ✅ Corregido |
| Regla 9 no implementada | 🔴 Crítico | ✅ Implementada |
| Cleanup usando DELETE en vez de draft | 🔴 Crítico | ✅ Corregido |
| Motor Mundial sin filtro de fecha | 🟠 Importante | ✅ Corregido |
| Jacinto Perplejo / Messi explícito | 🟠 Importante | ✅ Corregido |
| used_images.json perdido en Actions | 🟠 Importante | ✅ Corregido |
| PIL Image no importado globalmente | 🟠 Importante | ✅ Corregido |
| Clúster messi_seleccion mal etiquetado | 🟡 Menor | ✅ Corregido |

*Última actualización: 24 de Junio de 2026 — 12:14 GMT-3*

---

### 🔥 HOTFIX — 24 de Junio de 2026 (12:24 GMT-3)
**Commit de producción:** `b9c699e`
**Archivo modificado:** `create_and_upload_theme.py`
**Bug:** El sitio entró en "Pantalla Blanca de la Muerte" (Fatal Error de PHP, response size de 2.700 bytes) tras la refactorización de la marquesina dinámica en la "Orden Suprema 9". Se comprobó que el error era que se había cerrado un div de HTML y comenzado lógica PHP (procesando JSON) sin abrir previamente la etiqueta `<?php` en el archivo `header.php`.
**Corrección:** Se inyectó la etiqueta `<?php` faltante en la línea 2072 del generador del tema y se procedió a re-empaquetar y subir el tema automáticamente. El sitio volvió a estar online de inmediato.
