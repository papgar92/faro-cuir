# Auditoría de fuentes

Las **61 fuentes** normativas que vigila Faro Cuir, en tres niveles de administración:

| Nivel | Cuántas | Qué se publica ahí |
|---|---|---|
| Estatal | 1 (BOE) | Leyes, reales decretos, órdenes ministeriales |
| Autonómico | 17 | Leyes autonómicas, decretos, órdenes, instrucciones |
| **Provincial (BOP)** | **43** | **Ordenanzas y reglamentos municipales, bases y convocatorias de subvenciones, acuerdos de pleno** |

Este documento es un entregable clave (CLAUDE.md sección 4): antes de escribir un solo módulo
de ingesta, hay que saber qué formato expone cada fuente, si hace falta OCR, bajo qué licencia
se puede reutilizar el contenido, y cuánto cuesta integrarla.

## Por qué hay una capa provincial (ADR 0014)

El nivel local se vigila **a través del BOP, no municipio a municipio**. La razón es que una
ordenanza municipal **no entra en vigor si no se publica íntegra en el BOP** de su provincia
(Ley 5/2002, de 4 de abril, reguladora de los Boletines Oficiales de las Provincias,
`BOE-A-2002-6467`). El municipio no es una fuente: es un emisor que publica en la fuente
provincial. Eso convierte vigilar 8.131 municipios en vigilar 43 boletines.

Es además la capa que más encaja con el objetivo del proyecto (CLAUDE.md sección 1): una ley
autonómica que recorta derechos sale en la prensa; unas bases de subvención modificadas para
dejar fuera a una asociación LGTBI+ no salen en ninguna parte.

**Las 7 provincias sin BOP no son un hueco.** 50 provincias − 43 BOP = 7, y son exactamente
las CCAA uniprovinciales (Asturias, Cantabria, Illes Balears, Madrid, Murcia, Navarra, La
Rioja), donde el boletín autonómico hace ese papel y ya está en la tabla de arriba. Ceuta y
Melilla tampoco tienen BOP: publican en sus propios boletines de ciudad, y si entran en
alcance es una decisión aparte todavía abierta.

**Regla de oro 8 de CLAUDE.md: nunca inventar fuentes, plazos ni artículos legales.** Por
eso solo está rellena la fila del BOE, que se verificó directamente contra su API. El resto
de filas quedan marcadas `TODO(verificar)` a propósito — se completan en una sesión dedicada
a la auditoría, contrastando cada dato contra la fuente oficial, no por deducción ni por lo
que "suene plausible".

En la tabla provincial, **el nombre y la URL sí están verificados** (directorio oficial del
Punto de Acceso General, consultado el 2026-08-08) y el resto de columnas no. Es una
distinción deliberada: saber *dónde está* una fuente es barato y ya está hecho; saber *cómo
se integra* exige entrar en cada una. Ninguna fila mezcla lo comprobado con lo supuesto.

**Registrada ≠ vigilada.** El guardarraíl de CLAUDE.md sección 8 sigue en pie y con 61
fuentes importa más que antes: la primera iteración integra **como máximo 5**. Las demás se
registran con `activa=false`, que es información y no relleno — «sabemos que existe y no la
estamos mirando» es un hueco de cobertura declarado; una fuente ausente de la tabla es un
hueco invisible.

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
| **DOGC** (Diari Oficial de la Generalitat de Catalunya) | Catalunya | sumario `https://analisi.transparenciacatalunya.cat/resource/n6hn-rmy7.json` · texto `https://portaljuridic.gencat.cat/eli/...` | **API (JSON) + XML Akoma Ntoso** — verificado el 2026-08-16 descargando ambos | No | CC BY 4.0 (declarada por la fuente) | **Baja-media** — cinco particularidades, ver nota; el XML falta en 172 de 264 normas y no publica a quién afecta cada norma | **INTEGRADA** (ADR 0019), segunda fuente del proyecto; cobertura real 92 de 264 |
| TODO(verificar) | Comunitat Valenciana | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | Extremadura | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | Galicia | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | Comunidad de Madrid | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | Región de Murcia | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | Comunidad Foral de Navarra | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | País Vasco / Euskadi | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| TODO(verificar) | La Rioja | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |

### El DOGC, integrado: lo que hubo que aprender (ADR 0019 y 0020)

Es la única fuente de cinco candidatas que superó la verificación —BOJA, BOCM, BOPB y el BOP de
Cáceres quedaron descartadas o pendientes, con el motivo en el ADR—, y aun así trajo tres cosas
que ninguna documentación anunciaba —y dos más, aparecidas al medir dos días después, que pesan
más que las tres juntas:

1. **El articulado no está donde el estándar dice.** Publica Akoma Ntoso, pero mete el texto
   entero **dentro de un atributo XML**, escapado como HTML. Un derivador escrito leyendo el
   estándar habría archivado normas vacías **sin que fallara nada**.
2. **Solo negocia TLS 1.2 con `AES256-SHA`** en el host del texto íntegro. OpenSSL 3 lo rechaza;
   `curl` no, porque en Windows usa el TLS del sistema. Se aceptó un perfil heredado **para ese
   host y solo para él**, sin tocar la verificación del certificado.
3. **La versión oficial es la catalana**; se ingiere la castellana porque es la que el vocabulario
   del prefiltro sabe leer. Queda escrito porque las citas de las alertas saldrán de una
   traducción.

**Lo que esta fuente NO cubre:** son disposiciones generales (leyes, decretos legislativos,
decretos ley, decretos y órdenes: 31.094 desde 1977, de ellas 20.889 órdenes). **Las resoluciones
e instrucciones no están**, y son un vector de retroceso real.

**Cuarta particularidad, medida el 2026-08-18 y la más grave: el XML no existe para dos de cada
tres disposiciones, y la fuente no lo dice.** El conjunto de datos abiertos publica un
`url_es_format_xml` para **todas** las filas; el Portal Jurídic responde a 172 de esas 264 URL con
**HTTP 200 y su página de error** (12 KB de cromo del portal, sin una línea de articulado).
Comprobado sobre `DOGC-24291044` (ORDEN ESP/214/2024): la URL catalana devuelve la misma página de
error, el HTML es un contenedor de JavaScript sin articulado, y **solo el PDF trae el texto** (883
KB, PDF nativo, no escaneado).

Consecuencias que hay que decir enteras:

- **La cobertura real de esta fuente hoy es de 92 de 264 normas (35 %).** Cualquier cifra de
  recall medida sobre el DOGC es una cifra sobre ese 35 %, y se publica diciéndolo.
- Las otras 172 están archivadas con su huella —el archivo conserva lo que la fuente sirvió, 6.5—
  y marcadas **`ilegible`** en el prefiltro (ADR 0020), que es lo que hace que se vean en vez de
  confundirse con las que esperan descarga.
- El único camino de recuperación conocido es el **PDF**, con extracción de texto (permitida por
  6.1; el OCR sigue fuera de alcance por la sección 8, y aquí no hace falta porque el PDF es
  nativo). No está implementado.
- `xml_safe` rechaza esas respuestas por su `<!DOCTYPE html>` y **es lo único que impidió que 172
  páginas de error entraran en el pipeline como si fueran normas**. Es el mismo modo de fallo que
  la particularidad 1, y la segunda vez que esta fuente lo produce.

**Quinta particularidad, y es la que más cambia el diseño: el DOGC no dice a quién afecta una
norma.** Su Akoma Ntoso trae un bloque `<references>`, pero no es el equivalente del `<analisis>`
del BOE: los `activeRef` apuntan al **propio documento** con `showAs="Modificado"`/`"Derogado"`
—son anotaciones de ciclo de vida— y los `passiveRef` son normas *posteriores*, que el día de la
publicación no existen. Comprobado el 2026-08-19 en cuatro documentos, uno titulado literalmente
«de modificación del Decreto 358/2004»: la norma afectada aparece **solo en el texto**.

| | BOE | DOGC |
|---|---|---|
| cuerpos legibles | 2.968 | 92 |
| con referencias que el eje 2 puede leer | 211 (7,1 %) | **0** |

Consecuencia: el eje referencial del prefiltro —el que cubre el agujero estructural del
diccionario (7.3)— **no existía en esta fuente**. El ADR 0022 lo reconstruye leyendo las citas
del texto («Ley 11/2014, de 10 de octubre») con las cautelas que exigió la medición: solo forma
larga, porque la corta produjo 4 falsos positivos de 4. Hay que contar con lo mismo en cualquier
fuente nueva que no sea el BOE: **la estructura de referencias es una particularidad del BOE, no
un estándar**, y darla por hecha deja el eje 2 apagado en silencio.

**Y el dato que justifica toda esta capa**, medido sobre 1.193 normas del BOE: de órganos
autonómicos llegan al BOE **31 ítems**, todos anuncios y correcciones. Las leyes autonómicas sí se
republican; los decretos y órdenes, no. Sin boletines autonómicos, esa normativa es invisible.

## Tabla provincial — los 43 BOP

Nombre y URL **verificados** contra el directorio oficial del Punto de Acceso General
(`administracion.gob.es/pag_Home/espanaAdmon/boletinesYLegislacion/BO_Diputaciones.html`),
consultado el **2026-08-08**. Las columnas de integración están sin verificar y se marcan como
tal: para rellenarlas hay que entrar en cada boletín, y eso es una sesión aparte.

Los tres del País Vasco no se llaman «BOP» sino **Boletín Oficial del Territorio Histórico**
(BOTHA en Álava, BOB en Bizkaia, BOG en Gipuzkoa), por el régimen foral. Cumplen la misma
función a efectos de este proyecto: es donde publican sus ayuntamientos.

| Provincia | CCAA | URL base | Formato | ¿OCR? | Licencia | Dificultad | Prioridad |
|---|---|---|---|---|---|---|---|
| Almería | Andalucía | `https://www.dipalme.org/Servicios/cmsdipro/index.nsf/bop_view.xsp` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Cádiz | Andalucía | `https://www.bopcadiz.es` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Córdoba | Andalucía | `https://bop.dipucordoba.es` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Granada | Andalucía | `https://bop.dipgra.es/publica/consulta-de-bops/` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Huelva | Andalucía | `https://sede.diphuelva.es/servicios/bop` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Jaén | Andalucía | `https://bop.dipujaen.es` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Málaga | Andalucía | `https://www.bopmalaga.es` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Sevilla | Andalucía | `https://www.dipusevilla.es/bop/` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Huesca | Aragón | `https://bop.dphuesca.es/index.php/mod.menus/mem.detalle` | TODO(verificar) — hay indicios de XML/CSV, **confirmar** | TODO(verificar) | TODO(verificar) | TODO(verificar) | Candidata: hay señales de formato estructurado |
| Teruel | Aragón | `https://236ws.dpteruel.es/DPT/bopt.nsf` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Zaragoza | Aragón | `https://bop.dpz.es/BOPZ/` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Las Palmas | Canarias | `https://www.boplaspalmas.net/nbop2/index.php` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Santa Cruz de Tenerife | Canarias | `https://www.bopsantacruzdetenerife.es/bopsc2/index.php` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Albacete | Castilla-La Mancha | `https://bop.dipualba.es` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Ciudad Real | Castilla-La Mancha | `https://bop.dipucr.es` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Cuenca | Castilla-La Mancha | `https://www.dipucuenca.es/boletin-oficial-de-la-provincia` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Guadalajara | Castilla-La Mancha | `https://boletin.dguadalajara.es/boletin/` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Toledo | Castilla-La Mancha | `https://bop.diputoledo.es/webEbop/ebopCalendar.jsp` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Ávila | Castilla y León | `https://www.diputacionavila.es/boletin-oficial/` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Burgos | Castilla y León | `https://bopbur.diputaciondeburgos.es/search` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| León | Castilla y León | `https://bop.dipuleon.es/publica/consulta-de-bops/` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Palencia | Castilla y León | `https://www.diputaciondepalencia.es/servicios/boletin-oficial-provincia` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Salamanca | Castilla y León | `https://sede.diputaciondesalamanca.gob.es/BOP/` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Segovia | Castilla y León | `https://www.dipsegovia.es/bop` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Soria | Castilla y León | `https://bop.dipsoria.es` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Valladolid | Castilla y León | `https://bop.sede.diputaciondevalladolid.es/` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Zamora | Castilla y León | `https://www.diputaciondezamora.es/opencms/servicios/BOP/bop/index.html` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Barcelona | Catalunya | `https://bop.diba.cat` | TODO(verificar) — publica XML, pero **solo el día de publicación**; confirmar antes de diseñar la ingesta | TODO(verificar) | TODO(verificar) | TODO(verificar) | Candidata: formato estructurado documentado en datos.gob.es |
| Girona | Catalunya | `https://www.ddgi.cat/bop/` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Lleida | Catalunya | `https://ebop.diputaciolleida.cat/bop/` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Tarragona | Catalunya | `https://www.diputaciodetarragona.cat/ebop/` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Alicante | C. Valenciana | `https://sede.diputacionalicante.es/consultas-bop/` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Castellón | C. Valenciana | `https://bop.dipcas.es/PortalBOP/boletin.do` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Valencia | C. Valenciana | `https://bop.dival.es/bop/drvisapi.dll` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Badajoz | Extremadura | `https://www.dip-badajoz.es/bop/` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Cáceres | Extremadura | `https://bop.dip-caceres.es/bop/index.html` | TODO(verificar) — portal de datos abiertos con JSON/XML/CSV, **confirmar cobertura** | TODO(verificar) | TODO(verificar) | TODO(verificar) | Candidata: portal `opendata.dip-caceres.es` |
| A Coruña | Galicia | `https://bop.dacoruna.gal/bopportal/` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Lugo | Galicia | `https://www.deputacionlugo.gal/boletin-oficial-da-provincia-de-lugo` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Ourense | Galicia | `https://bop.depourense.es/portal/` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Pontevedra | Galicia | `https://boppo.depo.gal/` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Álava (BOTHA) | País Vasco | `https://www.araba.eus/botha/Inicio/SGBO5001.aspx` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Bizkaia (BOB) | País Vasco | `https://www.bizkaia.eus/es/bob` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |
| Gipuzkoa (BOG) | País Vasco | `https://egoitza.gipuzkoa.eus/es/bog` | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) | TODO(verificar) |

### Comprobación de que la lista está completa

No basta con contar 43 filas: hay que comprobar que las 43 son **las que deben ser**. El
reparto por CCAA cuadra con la división provincial de España, y esa suma es una verificación
independiente del recuento del directorio:

| CCAA | Provincias con BOP |
|---|---|
| Andalucía | 8 |
| Castilla y León | 9 |
| Castilla-La Mancha | 5 |
| Catalunya | 4 |
| Galicia | 4 |
| Aragón | 3 |
| C. Valenciana | 3 |
| País Vasco | 3 |
| Canarias | 2 |
| Extremadura | 2 |
| **Total** | **43** |

Las 7 CCAA uniprovinciales no aparecen aquí porque no tienen BOP, y ese es justamente el
resultado esperado: **43 + 7 = 50 provincias**. Si algún día esta tabla deja de sumar 43 o el
reparto por CCAA deja de cuadrar con la división provincial, la lista se ha roto.

### Lo que esta tabla NO dice

- **No dice que se pueda integrar ninguno de los 43.** Es previsible que varios publiquen solo
  PDF escaneado; el OCR está fuera de alcance (CLAUDE.md sección 8) y esos se quedarán como
  hoja de ruta. Con 43 fuentes, hacer «una excepción solo para este» es una excepción que se
  repite 43 veces.
- **No dice bajo qué licencia se puede reutilizar nada.** Ninguna licencia está verificada.
- **Las tres «candidatas» no están confirmadas**, solo tienen indicios de formato
  estructurado. La de Barcelona lleva además una advertencia que puede invalidarla como
  primera opción: hay indicios de que el XML **solo está disponible el día de publicación**,
  lo que impediría reingerir histórico y chocaría con la idempotencia por `sha256` en la que
  se apoya el worker. Confirmarlo es lo primero que hay que mirar de ese BOP.

## Siguiente paso

Sesión dedicada de auditoría: para cada fuente, entrar en la web oficial del boletín,
confirmar si hay API/RSS o solo HTML/PDF, si el PDF lleva capa de texto o es escaneado, y
localizar la página de condiciones de reutilización (normalmente bajo "aviso legal" o
"reutilización de la información"). No completar una fila sin haber visitado la fuente.

**Con 61 fuentes, auditarlas todas ya no cabe y no es el objetivo.** El orden que rinde:

1. **Un solo BOP, de punta a punta**, elegido entre las tres candidatas por formato
   estructurado (Huesca, Cáceres, Barcelona — empezando por descartar la advertencia del XML
   de Barcelona). Un BOP integrado y midiendo demuestra la capa local entera; cuarenta y dos
   filas de tabla rellenadas no demuestran ninguna.
2. **Repetir la medición del ADR 0011 sobre ese BOP** con `scripts/medir_fase2.py`, que existe
   justo para esto. El riesgo no es la descarga —el ADR 0011 midió que es barata— sino la cola
   del LLM, a 133,9 s por extracción. Multiplicar fuentes multiplica esa cola, y **hay que
   tener el número antes de activar la segunda fuente**, no después.
3. Solo entonces, decidir si el resto se integra con un ingestor genérico o uno por familia de
   plataforma. Hoy no hay dato para decidir eso, y decidirlo sin dato sería inventar.
