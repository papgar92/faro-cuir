# Auditoría de fuentes

Las 18 fuentes normativas que vigila Faro Cuir: el BOE (Estado) y los 17 boletines/diarios
oficiales de las comunidades autónomas. Este documento es un entregable clave (CLAUDE.md
sección 4): antes de escribir un solo módulo de ingesta, hay que saber qué formato expone
cada fuente, si hace falta OCR, bajo qué licencia se puede reutilizar el contenido, y cuánto
cuesta integrarla.

**Regla de oro 8 de CLAUDE.md: nunca inventar fuentes, plazos ni artículos legales.** Por
eso solo está rellena la fila del BOE, que se verificó directamente contra su API. El resto
de filas quedan marcadas `TODO(verificar)` a propósito — se completan en una sesión dedicada
a la auditoría, contrastando cada dato contra la fuente oficial, no por deducción ni por lo
que "suene plausible".

Recordatorio de CLAUDE.md sección 8: la primera iteración cubre como máximo 5 fuentes:
con eso se demuestra el sistema; el resto queda documentado como hoja de ruta.

## Columnas

- **Fuente** — nombre oficial del boletín/diario.
- **CCAA** — comunidad autónoma (o "Estado" para el BOE).
- **URL base** — endpoint o URL raíz para la ingesta.
- **Formato disponible** — API / RSS / HTML / PDF (el mejor disponible, no necesariamente
  el único).
- **¿Requiere OCR?** — si el formato es PDF escaneado sin capa de texto. OCR está fuera de
  alcance de este proyecto (CLAUDE.md sección 8); una fuente que lo requiera se documenta
  como hoja de ruta, no se integra.
- **Licencia de reutilización** — bajo qué términos se puede reutilizar el contenido.
- **Dificultad de integración** — baja/media/alta, estimada a partir del formato y la
  autenticación requerida.
- **Prioridad** — candidata a una de las primeras 5 fuentes o no.

## Tabla

| Fuente | CCAA | URL base | Formato disponible | ¿Requiere OCR? | Licencia de reutilización | Dificultad | Prioridad |
|---|---|---|---|---|---|---|---|
| BOE (Boletín Oficial del Estado) | Estado | `https://boe.es/datosabiertos/api/boe/sumario/{fecha}` | API (XML/JSON) | No | TODO(verificar) | Baja — API REST abierta, sin autenticación, formato estructurado | Alta — fuente base nacional, integración más barata de las 18, candidata natural a estar entre las primeras 5 |
| TODO(verificar) | Andalucía | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | Aragón | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | Principado de Asturias | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | Illes Balears | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | Canarias | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | Cantabria | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | Castilla-La Mancha | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | Castilla y León | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | Catalunya | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | Comunitat Valenciana | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | Extremadura | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | Galicia | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | Comunidad de Madrid | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | Región de Murcia | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | Comunidad Foral de Navarra | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | País Vasco / Euskadi | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | La Rioja | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |

## Siguiente paso

Sesión dedicada de auditoría: para cada CCAA, entrar en la web oficial del boletín,
confirmar si hay API/RSS o solo HTML/PDF, si el PDF lleva capa de texto o es escaneado, y
localizar la página de condiciones de reutilización (normalmente bajo "aviso legal" o
"reutilización de la información"). No completar una fila sin haber visitado la fuente.
