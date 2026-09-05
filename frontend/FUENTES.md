# Tipografías alojadas aquí

Las tres las servía Google (`fonts.googleapis.com` + `fonts.gstatic.com`) y se trajeron al
repositorio el **2026-09-05** (ADR 0033). El motivo no es de rendimiento: cargarlas desde Google
hace que **el navegador de cada visitante mande su IP a Google en cada carga**, y la sección 6.4
dice que el sistema no registra IPs de quien consulta la web. Servirlas desde el mismo origen es
lo único que hace cierta esa frase de punta a punta, y de paso deja la CSP en `default-src 'self'`
sin nombrar a terceros.

| familia | ficheros | qué es |
|---|---|---|
| Libre Franklin | `libre-franklin-400-700-*` | **variable**: un fichero cubre de 400 a 700 |
| Source Serif 4 | `source-serif-4-400-700-*` | **variable**, con el eje óptico de Google |
| IBM Plex Mono | `ibm-plex-mono-400-*`, `-500-*` | estática: Google no la sirve variable |

**Solo `latin` y `latin-ext`.** El resto de alfabetos que sirve Google —cirílico, griego,
vietnamita— son megas que ningún boletín oficial español va a usar. `latin-ext` se queda porque
el DOGC publica en catalán.

**327 KB en total.** Con las instancias estáticas eran 706 KB, y una página que usara negrita y
semibold de serif se bajaba 238 KB en vez de 119.

## Licencia

Las tres son **SIL Open Font License 1.1**, que permite redistribuirlas siempre que la licencia
viaje con ellas. Por eso están aquí los tres `OFL-*.txt`, descargados de `google/fonts`. No se
renombran los ficheros de fuente por capricho: la OFL prohíbe distribuirlas bajo el nombre
reservado modificadas, y aquí no se modifica nada — son los mismos woff2 que servía Google.

## Cómo se reproduce

`docs/adr/0033-*.md` explica el porqué. Los ficheros salieron de pedirle a Google el CSS con un
agente de navegador moderno (para que devuelva `woff2` y las variables), quedarse con los bloques
`latin` y `latin-ext`, y descargar sus URL. Las reglas `@font-face` resultantes están en
`src/index.css`.
