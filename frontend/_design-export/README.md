# Handoff de diseño (referencia, no código de producción)

Exportado tal cual desde el proyecto de claude.ai/design
`Centinela: Mapa de alertas normativas` (`ea402877-d0ec-4231-8505-11d13d1914f0`).

> Nota: el proyecto se renombró a "Faro Cuir" después de este handoff. Los archivos de
> esta carpeta son un artefacto histórico y se conservan con el nombre original tal como
> se exportaron; no se renombran ni se editan.

- `Centinela.dc.html` — maqueta única en formato `.dc.html` (runtime propio tipo
  React, ver `support.js`). No se ejecuta ni se importa desde `src/`; es solo
  referencia visual y de interacción para construir los componentes reales.
- `support.js` — runtime que interpreta el `.dc.html` (`dc-runtime`, generado).
- `data/ccaa-paths.json` — geometría SVG de los 17 polígonos de CCAA (`d` por
  comunidad). Esta sí se reutiliza en `src/` tal cual, es solo geometría.
- `data/es-autonomous-regions.topo.json` — TopoJSON fuente de esa geometría.
  No se usa en runtime, se conserva como referencia de procedencia.

**Omitido:** `screenshots/map.png`. Al traerlo desde el MCP de diseño llegó
inline en vez de persistido a disco, y la transcripción manual del base64 no
pasó la validación de integridad (longitud no múltiplo de 4 tras dos intentos
idénticos) — la codificación en sí venía bien del servidor, el fallo estaba en
copiarla a mano. Prefiero omitirlo a arriesgar un binario corrupto en el repo;
no afecta a nada funcional, era solo una captura de referencia.
