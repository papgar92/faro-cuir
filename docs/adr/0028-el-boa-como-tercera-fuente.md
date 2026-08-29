# ADR 0028 — El BOA como tercera fuente, y el precio de no poder pedir un documento por su nombre

- **Fecha:** 2026-08-29
- **Estado:** aceptado
- **Sustituye a:** nada. Continúa el ADR 0019 (el DOGC como segunda fuente).

## Contexto

El proyecto vigilaba dos fuentes: el BOE y el DOGC. El mapa de la portada pintaba **2 de 19
territorios** y los otros 17 salían con trama, que es como el frontend dice «aquí no está
mirando nadie». El humano pidió que el mapa se fuera rellenando.

Hay además un hueco de cobertura escrito en el ADR 0019 y que no se había cerrado: el conjunto
de datos del DOGC son **disposiciones generales** —leyes, decretos legislativos, decretos ley,
decretos y órdenes—. **Sus resoluciones e instrucciones no están**, y la sección 1 de CLAUDE.md
dice que el retroceso silencioso vive justo en el rango bajo. O sea que la segunda fuente
cubría la mitad alta del problema.

La sección 8 limita la primera iteración a cinco fuentes integradas. Con dos, quedaba sitio.

## Cómo se eligió: descargando, no leyendo documentación

Mismo método que el ADR 0019, y otra vez dio resultados que ninguna documentación anunciaba. Se
sondearon nueve portales autonómicos pidiéndoles un día concreto:

| Fuente | Qué se pudo obtener | Veredicto |
|---|---|---|
| **BOA** (Aragón) | Sumario **y texto íntegro** en XML, en la misma petición, filtrable por fecha exacta | **Integrable ya** |
| BON (Navarra) | Sumario HTML de 113 KB, sin interfaz de datos localizada | Pendiente |
| BOC (Canarias) | Índice HTML | Pendiente |
| DOE (Extremadura) | Índice HTML | Pendiente |
| BORM (Murcia) | PDF del boletín | Pendiente: PDF, y la 6.1 lo permite pero es la vía cara |
| BOPV (Euskadi) | Sumario HTML direccionado por **número de boletín**, no por fecha | Pendiente: hay que resolver la fecha → número |
| BOCYL (Castilla y León) | El RSS por fecha devuelve 500 | Descartada por ahora |
| DOGV (Comunitat Valenciana) | 404 en la ruta de sumario probada | Descartada por ahora |
| BOJA (Andalucía) | Ya evaluada en el ADR 0019: el HTML **declara que suprime contenido** | Descartada: choca con 7.1 |

El BOA gana sin discusión, y por una pieza que no está documentada en ninguna parte: BRSCGI —el
buscador documental del Gobierno de Aragón— acepta **`OUTPUTMODE=XML` sobre una sección de datos
abiertos** (`SEC=OPENDATABOAXML`). Ese endpoint devuelve, para una fecha exacta y en una sola
respuesta, metadatos de sumario **y el texto íntegro** de cada disposición.

`OUTPUTMODE` solo por su cuenta no basta y esto es fácil de leer mal: `SEC=OPENDATASUMARIO` con
`OUTPUTMODE=JSON` sigue devolviendo el HTML del diario. **La sección elige la plantilla; el
`OUTPUTMODE` sin la sección correcta se ignora en silencio.**

### Lo que el BOA trae y el DOGC no

Día verificado (2024-01-10), 38 disposiciones:

| sección | items |
|---|---|
| I. Disposiciones Generales | 1 |
| II. Autoridades y Personal | 10 |
| III. Otras Disposiciones y Acuerdos | 16 |
| V. Anuncios | 11 |

y por rango, **15 de 38 son resoluciones**. Esta fuente cubre el hueco que el ADR 0019 dejó
abierto, y esa es la razón principal para elegirla; sumar una comunidad al mapa es la segunda.

## Decisión

**Se integra el Boletín Oficial de Aragón como tercera fuente y segunda autonómica.**

### 1. El cuerpo se direcciona por posición, y por eso se verifica

**Este es el precio de la fuente y lo que gobierna todo el módulo.** BRSCGI **no expone el
número de control como campo consultable**: probados `DOCN`, `DOCN-C`, `NDOC`, `CLAVE`,
`TEXT`, `@DOCN` y la forma entrecomillada, los siete devuelven cero registros. La URI ELI que
publica la fuente (`/eli/es-ar/o/2023/12/28/eei1987/dof/spa/html`) **solo sirve HTML** —`/xml`
da 404— y además solo existe para algunos rangos, no para resoluciones ni anuncios.

Así que la única forma de pedir una disposición suelta es **su posición ordinal dentro del día**:
`DOCS=n-n&PUBL=YYYYMMDD`. Eso es una dirección frágil por naturaleza — depende de que la fuente
ordene igual el mismo conjunto dos veces.

**No se confía en ella: se comprueba.** El registro trae su propio `<docn>`, así que
`boa.parsear_cuerpo` exige que el que vuelve sea el que se pidió, y si no cuadra levanta y **no
se archiva nada**. La norma se queda sin `documento_texto_id` y vuelve sola a la cola de la fase
2, que es la vía de fallo normal del proyecto.

La alternativa —archivar lo que llegue— pondría el texto de una norma bajo el identificador de
otra. Eso no rompe nada visiblemente y hace que el archivo **afirme en falso qué decía cada
cual**, que es exactamente la corrupción silenciosa que la sección 6.5 existe para impedir. Es
el mismo modo de fallo que motivó el estado `ilegible` (ADR 0020) y el `num_predict` sin fijar
del 2026-08-28: algo que no se puede hacer, repitiéndose sin que nadie lo cuente.

La comprobación se ejecuta en la fase 2 (`services/texto_integro.py`), que es donde se archiva.
Entra por un registro de validadores indexado por prefijo del identificador, y **una fuente
entra ahí solo si su forma de direccionar el cuerpo puede devolver otro documento**: el BOE y el
DOGC piden una URL que nombra la disposición, así que no pueden equivocarse de norma y no
necesitan validador.

### 2. Se descarga el cuerpo aparte aunque el sumario ya lo traiga

El sumario del día trae el texto de las 38 disposiciones. Sería tentador partirlo y ahorrarse 38
peticiones. **No se hace**, porque el `sha256` del ADR 0005 y la sección 6.5 tienen que
calcularse sobre **los bytes que envió el servidor**: un cuerpo recortado por nosotros del XML
del día tendría una huella de lo que entendimos nosotros, no de lo que se publicó. Es el mismo
motivo por el que `descargar_sumario` devuelve bytes crudos sin tocar.

El coste medido es despreciable: **376 KB y ~38 peticiones por día**, frente a los 4,3 MB del
BOE (ADR 0011).

### 3. `formato='api'`, y la licencia no se deduce

`api` como el BOE y el DOGC, y significa lo mismo: hay una interfaz de datos, no una página que
raspar. La licencia se anota como **CC BY 4.0** porque el catálogo de datos abiertos de Aragón la
declara así en el conjunto «Boletín Oficial de Aragón», comprobado contra
`opendata.aragon.es/api/action/package_search` el 2026-08-29. No se dedujo (regla de oro 8).

### 4. `VERSION_TEXTO_PLANO` **no** sube

`pipeline/texto.texto_plano` gana una rama para la estructura del BOA (`documento > registro >
texto`). Sin ella caería al árbol completo y el texto se llenaría de metadatos del registro
—título, emisor, sección—, que para el prefiltro léxico son falsos positivos del mismo tipo que
el bloque `<analisis>` del BOE.

Pero **la versión no sube**, y es deliberado: gobierna las colas de reproceso del prefiltro y del
clasificador (`!=` en `services/prefiltro.py` y `services/clasificacion.py`), así que subirla
reprocesaría las ~75.000 normas ya archivadas del BOE y del DOGC, cuya derivación esta rama no
toca porque solo dispara sobre una estructura que ningún documento suyo tiene. **Se sube cuando
cambia cómo se deriva algo ya archivado, no cuando se aprende a leer una forma nueva.**

## Alternativas consideradas

- **Empezar por Madrid (BOCM)**, donde ocurrió la reforma del caso insignia. Sigue descartada
  por lo mismo que en el ADR 0019: su XML por disposición devuelve 500 y el resto es HTML y PDF.
  Es la candidata con más valor simbólico y la que peor formato tiene; integrarla antes que el
  BOA habría costado varias veces más para cubrir peor.
- **Partir el XML del día en cuerpos.** Descartada en la decisión 2: rompe la garantía de 6.5.
- **Raspar el HTML del diario** (`VERDOC`), que también trae el texto íntegro (146 KB, 62
  artículos en el documento comprobado). Innecesario habiendo XML, y HTML es más frágil.
- **Esperar a resolver las 17 a la vez.** Contra la sección 8 y contra lo aprendido con el DOGC:
  cada fuente tiene sus rarezas y solo aparecen integrándola.

## Consecuencias

- **El mapa deja de pintar dos territorios y pinta tres.** No es cosmética: 17 de 19 con trama
  era una afirmación honesta de que ahí no mira nadie, y ahora es una menos.
- **El sistema ve resoluciones autonómicas por primera vez.** El hueco del ADR 0019 queda
  cubierto para una comunidad, no para las diecisiete.
- **La cobertura de esta fuente es completa desde el primer día, y eso la distingue del DOGC.**
  En la ingesta real del 2024-01-10: 38 items, 38 cuerpos descargados, **0 fallidas y 0
  `ilegible`**. El DOGC iba con 172 de 264 ilegibles (65 %). No hay aquí el problema de los
  cuerpos que la fuente promete y no sirve.
- **El eje referencial (7.3) depende de las citas del texto, no de metadatos.** El registro del
  BOA no dice a qué norma afecta: no hay equivalente del `<analisis>` del BOE. Vale lo mismo que
  se dijo del DOGC en el ADR 0022, y conviene repetirlo porque es el error fácil: **la estructura
  de referencias es una particularidad del BOE, no un estándar**, y darla por hecha deja el eje 2
  apagado en silencio.
- **El despacho de fuentes del worker deja de ser un `if`.** Hasta aquí era
  `if fuente != "boe"` con el código de comunidad escrito a mano en la consulta. Con dos colaba;
  con tres deja de colar y la cuarta se habría añadido por copia. Ahora es una tabla `FUENTES`
  con las tres cosas que distinguen una fuente: tipo, comunidad e ingestor.
- **Una entrada más en la allowlist de `url_guard`** (`boa.aragon.es`), y una sola: aquí el
  sumario y el cuerpo salen del mismo host, sin la gimnasia de dos dominios que necesitó el DOGC.
- **Quedan dos huecos de fuente por integrar dentro del límite de cinco de la sección 8**, y las
  candidatas con su estado están en la tabla de arriba y en `docs/fuentes.md`.
