**MEMO TÉCNICO CONFIDENCIAL — USO INTERNO**
**PARA:** Sistema Antigravity / Agentes autónomos de Pasión y Pelota
**DE:** Dirección Técnica del Portal
**ASUNTO:** Actualización obligatoria de protocolo — Reglas 1 a 10 (versión con gancho en código, no solo en prompt)
**PRIORIDAD:** Crítica — aplicar antes del próximo ciclo de publicación

Las 10 reglas vigentes no se están cumpliendo porque están escritas como texto de prompt, no como lógica determinística en el código que efectivamente se ejecuta. Esta directiva las traduce a implementación concreta. A partir de ahora, ninguna regla se considera "cumplida" si no tiene un gate, contador o función específica que la haga cumplir — el modelo de lenguaje no decide si una regla se respeta, el código se lo impone.

**1 — Construcción de queries de imagen.**
Toda búsqueda de imagen pasa obligatoriamente por una única función `build_image_query(entity_type, entity_name)` que concatena sufijo deportivo (`{equipo} national football team`, `{jugador} football`). Prohibido cualquier llamada de búsqueda que no pase por esa función. Auditar el código y eliminar fallbacks que arman queries por fuera.

**2 — Fuentes de imagen permitidas (taxativo).**
Únicamente: (a) Unsplash vía API con licencia confirmada, (b) embeds oficiales de Instagram/X de cuentas verificadas de selecciones, FIFA o clubes, (c) generación propia vía Flux/Pollinations. Ninguna otra fuente persiste un archivo de imagen en el servidor del portal.

**3 — [REEMPLAZADA] Fuentes con copyright reservado (TyC Sports, Diario Marca).**
Queda HABILITADO extraer y rehostear imágenes de estas fuentes, con  cita de atribución. Una leyenda de crédito constituye licencia de uso. 

**4 — Anti-duplicado de imágenes.**
El check contra `used_images.json` debe estar en el único punto de persistencia final, inmediatamente antes de `upload_to_media_library`. Toda imagen, sea cual sea su origen, pasa por ese gate antes de subirse. Prohibido replicar el check por fuente separada.

**5 — Estadísticas exactas, cero alucinación.**
Separación total entre redacción (LLM) e inyección numérica (template). El modelo jamás escribe una cifra propia: los placeholders (`{goles}`, `{asistencias}`, `{resultado}`) se completan después, por código, directo desde el JSON crudo de Promiedos. El LLM redacta alrededor de números ya fijos, nunca los genera.

**6 — Exclusividad Mundial 2026.**
No depender del juicio visual de Gemini Vision sobre uniformes para distinguir años de Mundial — no es confiable. Filtrar por metadata de la fuente: si el feed/API no etiqueta competición y fecha 2026, se descarta automáticamente sin pasar a verificación visual.

**7 — [REEMPLAZADA] Diario Marca.**
Misma razón que el punto 3. Reemplazo idéntico
**8 — Directiva de detectar y aceptar visualmente banners de marca ajena.  Corresponde una regla que busque despojar a un embed de su marca.**

**9 — Límite estricto de 30 notas.**
Después de cada publish exitoso: `GET /wp/v2/posts?per_page=1&orderby=date&order=asc` para identificar el post más antiguo. Si el total supera 30, mover ese post a estado `draft` (no `DELETE` irreversible).

**10 — Eliminación total de Wikimedia/Wikipedia.**
Eliminar el import y la función `wikimedia_search()` del módulo de búsqueda de imágenes. La prohibición se garantiza sacando la función del código, no pidiéndole al modelo que "decida" no usarla.

**Cierre:** queda todo automatizado, si en alguna de las reglas no sefalta algun codigo para la correcta funcion del agente debe incorporarse con la misma logica q las reglas q lo tienen.

**11 — HORA OFICIAL DEL PORTAL (GMT-3)**
El ecosistema completo (servidores, scrapers, API, y agentes) opera bajo la zona horaria oficial del portal: GMT-3 (America/Argentina/Buenos_Aires). Todas las fechas y horas procesadas desde cualquier fuente deben ser convertidas a esta zona horaria antes de almacenarse o publicarse. Asimismo, los agentes deben redactar todo horario haciendo referencia explícita a la hora argentina si aplica, sin convertir a otros husos horarios a menos que se especifique.
