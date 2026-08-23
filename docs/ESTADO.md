# Estado actual del proyecto — Faro Cuir

> **Esto era la sección 11 de `CLAUDE.md`.** Se sacó a un fichero propio el 2026-08-09 por un
> motivo medido: `CLAUDE.md` había llegado a 124 KB (~31.000 tokens) y **entra entero en el
> contexto de cada subagente**. Esta sección era el 54 % del fichero y ningún agente la
> necesita — `revisor-seguridad` audita un diff, `auditor-reglas` mira esquemas y CHECKs.
> Cuatro agentes pagaban ~17.000 tokens cada uno por un historial de estado que no leían.
>
> **La numeración se conserva a propósito.** Todo el repositorio (ADRs, ficheros de agentes,
> comentarios del código, backlog) cita "la sección 11", y renumerar habría roto esas
> referencias a cambio de nada. Sigue siendo la sección 11; vive en otro fichero.
>
> **Se sigue actualizando al terminar cada trabajo**, con el mismo criterio de siempre. Y
> conviene no dejarla crecer sin podar: lo que ya está hecho y cerrado se resume, no se
> conserva entero.

---

## 11. Estado actual del proyecto

<!-- Claude Code: actualiza esta sección al terminar CADA trabajo, no solo al cerrar la sesión.
Dos cosas, siempre:
  1. Qué se ha hecho y qué toca. Es lo primero que se lee al retomar.
  2. Cada punto de "Siguiente" lleva su **coste estimado en tokens de contexto**, calculado
     por ti a partir del alcance real (qué hay que leer, cuánto código sale, qué verificación
     hace falta), no de una fórmula. Sirve para decidir si una tarea cabe en la sesión que
     empieza o hay que partirla; si la estimación no es obvia, di en qué se basa.
  3. **Calibra contra lo medido, no contra la intuición.** Las primeras estimaciones de esta
     sección salieron ~3x altas: se estimó el frontend en 40k y el prefiltro en 55k, y
     costaron del orden de 15k y 25k reales. Una tarea normal de este repo -un módulo, sus
     tests, migración si toca y verificación en navegador o curl- ronda los **15-30k**. Si te
     sale más de 50k, sospecha de la estimación antes que del alcance. -->

### ⇨ PLAN A V1 — pedido por el humano el 2026-08-08, fecha objetivo **2026-09-10**

> **El plazo se movió del 22 de agosto al ~10 de septiembre el 2026-08-21**, a petición del
> humano. No es solo más tiempo: **cambia qué cabe**. Con dos días, el histórico grande estaba
> descartado y la fuerza del proyecto tenía que salir del rigor sobre un corpus pequeño. Con
> veinte, un año entero de BOE son ~83 horas de máquina despierta y **sí cabe**.
>
> Lo que eso reordena, y está desarrollado en la última entrada de este fichero: la ingesta pasa
> a ser una tarea de fondo que corre sola durante días, y el trabajo de sesión se va a la
> interfaz del ADR 0025, al gold set y a recuperar las 172 ilegibles del DOGC.
>
> **El cuello de botella medido no es el pipeline, es que la máquina se duerme.** El ritmo real
> son 834 documentos/hora, unos 20 minutos por día de BOE; la noche del 20 al 21 de agosto se
> perdieron 15 horas por suspensión. Con la suspensión desactivada, un año son cuatro días de
> reloj.

Dos semanas. Lo que sigue es el recorte que hace que quepa; si el humano quiere otro, manda él.

**Qué es V1, en una frase:** el pipeline entero funcionando de punta a punta **sobre el BOE**,
con su recall medido, su clasificación auditable, su gate humano y su canal de difusión. No es
"más fuentes": es que lo que hay esté cerrado y demostrable. Coincide con la sección 1 — el
tribunal puntúa el rigor, no el número de features.

**Dentro de V1** (en orden; el coste es el de la lista de "Siguiente", ya recalibrado):

| # | Tarea | ~Coste | Por qué es imprescindible |
|---|---|---|---|
| 1 | 0.b vocabulario + `sospecha` | 15k | Define qué se etiqueta. Va antes del gold set o se etiqueta dos veces. |
| 2 | 0.c worker descarga el día entero | 15k | Implementa el ADR 0011. Sin esto la fase 2 no existe. |
| 3 | Gold set **recortado a 60-80 documentos** | 20k | Ver el aviso de abajo. |
| 4 | Clasificador por diff | 25k | Es la etapa que falta para que el pipeline llegue al final. |
| 5 | Offsets en la extracción | 20k | Regla de oro 9. No es opcional, es una regla no negociable. |
| 6 | Panel de revisión con autenticación | 35k | Regla de oro 4: sin gate humano no se puede emitir **ninguna** alerta. |
| 7 | Migrar Mapa y Alertas a la API | 20k | Es lo que quita el cartel de "datos de ejemplo" de la portada. |
| 8 | Canal pull (RSS/Atom) + ADR 0010 | 15k | Difusión sin lista de suscriptores, y simplifica la EIPD en vez de complicarla. |
| 9 | `docs/eipd.md` | 25k | Único hueco de seguridad sin desarrollar. Se puede cerrar en cuanto exista el 8. |

**Fuera de V1, y son recortes conscientes:**
- **Auditoría de las 17 fuentes autonómicas (~45k).** Es el recorte grande y el que más
  tiempo libera. La sección 8 ya autoriza documentar el resto como hoja de ruta, y frente al
  tribunal compra menos que tener el pipeline entero cerrado sobre el BOE.
- **Provincias y localidades en el mapa.** Ver el estado del backlog más abajo: hace falta
  geometría nueva y, sobre todo, no hay dato provincial que pintar.
- **Difusión** (GitHub público, LinkedIn, asociaciones). Es post-V1 y son acciones del humano,
  no del agente.

**El riesgo real del plazo no es el código, es el etiquetado a mano del gold set.** Por eso
baja de 150-200 documentos a 60-80: es lo que cabe en dos semanas de trabajo humano a ratos.
**Consecuencia que hay que escribir y no maquillar:** con 60-80 documentos el recall se puede
medir, pero con un intervalo de confianza ancho. Se publica el número **con su intervalo y con
el tamaño de la muestra**, nunca el número solo. Ampliar el corpus es lo primero que se hace
después de V1.

---

### ⇨ POR DÓNDE SE EMPIEZA

> **Lo vigente está al final de este fichero, en «CÓMO RETOMAR ESTO — cierre del 2026-08-23».**
> Ahí está qué corre de fondo, qué se hizo lo último y qué toca por valor. Esta sección era la
> guía de arranque de la tarea 0 y se podó el 2026-08-23: ocupaba **55 KB, el 20 % del fichero**,
> y era el diario de S0 y S1 con las tres tareas ya cerradas. Lo que contenía sigue existiendo,
> pero donde se usa: en los ADR, en el código y en los ficheros que lo aplican.

**Lo que se hizo en S0 y S1 (2026-08-04 al 2026-08-09), y dónde vive ahora:**

| trabajo | dónde está hoy |
|---|---|
| Prefiltro léxico, etapa 1 | `pipeline/prefiltro.py`, ADR 0007 |
| Contrato de extracción del LLM y defensas anti-inyección (6.7) | `llm/`, ADR 0008/0009 |
| Extractor cerrado, etapa 2 | `services/extraccion.py` |
| Volumen de la fase 2 medido y umbral fijado en cero | **ADR 0011**, `scripts/medir_fase2.py` |
| Eje referencial y watchlist; auditoría de las 17 CCAA | `config/watchlist.json`, que lleva dentro su propia auditoría, sus tres trampas de verificación y sus limitaciones |
| La capa local entra en alcance vía BOP | **ADR 0014**, `docs/fuentes.md` |
| Frontend con mapa real generado, zoom y manifiesto | `frontend/`, `scripts/generar_mapa.py` |
| Tarea 0.c: el worker descarga el día entero | **ADR 0015** y la entrada «Tarea 0.c cerrada» de abajo |

**Tres avisos de método de aquella época que siguen valiendo, y por eso no se van con el resto:**

- **El gold set es el cuello de botella del proyecto y no se recorta** (7.8). Lo caro no es el
  código, es el tiempo humano de anotación.
- **Cerrar el formato de un caso ANTES de etiquetar en masa.** Etiquetar 200 documentos con el
  formato viejo y repetirlos es el peor uso posible del recurso más caro. Sigue habiendo una
  decisión de formato abierta: los casos-par para los retrocesos por ausencia.
- **Las migraciones se escriben a mano y se revisan siempre.** El autogenerate de alembic ha
  propuesto borrar CHECKs ajenas cinco veces.

### 📚 S1 resumida: del 9 al 16 de agosto — condensado el 2026-08-23

> **88 KB de diario, resumidos a sus hallazgos.** El desarrollo completo de cada trabajo está en
> los mensajes de commit, que en este repositorio son extensos a propósito, y en los ADR que se
> citan. Lo que se conserva aquí es lo que sigue teniendo valor cuando ya no recuerdas la sesión:
> los hallazgos, y sobre todo **los fallos que no habrían dado un rojo**.

#### Lo que se construyó, por orden

| fecha | trabajo | ADR |
|---|---|---|
| 08-09 | Tarea 0.c: el worker descarga el texto íntegro del día entero | 0015 |
| 08-09 | Etapa 4: el catálogo de reglas existe y clasifica la reforma madrileña | 0016 |
| 08-14 | Segunda familia del catálogo: derogación (R-DER-001) | — |
| 08-14 | **El gate humano existe**: panel de revisión autenticado y primera alerta emitida | 0017 |
| 08-14 | API de alertas y canal pull (feed Atom) | 0010 |
| 08-14 | `docs/eipd.md` escrita de verdad y modelo de amenazas al día | — |
| 08-15 | `version_norma` deja de estar vacía: el texto anterior existe | 0018 |
| 08-15 | Tercera familia: modificación (R-MOD-001), y el diff se ve en API y feed | — |
| 08-16 | Auditoría de seguridad del ADR 0018; gold set de 4 a 14 casos | — |

#### Los hallazgos que siguen valiendo

**De diseño:**

- **`R-SUP-001` supone que la watchlist es un catálogo de normas protectoras.** Escrito entonces
  como supuesto explícito «para poder discutirlo». El 2026-08-23 fue justo lo que impidió aplicar
  entera la ampliación de la watchlist. Escribir los supuestos discutibles **paga**.
- **La evidencia va antes que el veredicto en el orden de lectura de la tarjeta**, y el panel no
  publica lo que dijo el modelo. Es la misma defensa contra el anclaje que el informe del jurista.
- **Ni feeds personalizados ni tokens por suscriptor**: una URL única por persona es una lista de
  suscriptores con otro nombre, y encima viaja en la barra de direcciones. Hay un test que lo fija.
- **El diff se filtra distinto según quién mira**: el panel sin filtro —quien mira **es** el gate y
  necesita el material tal cual—, el público solo lo anterior a `alerta.emitida_en`, porque lo que
  se publica es lo que se aprobó.
- **`terminos_perdidos()` es diagnóstico, no criterio**, con su contraejemplo escrito.
- **Un feed vacío responde 200 con cero entradas, no un error.** Un día en el que nada pasa el gate
  es un día normal, no un fallo.

**Fallos encontrados que ningún test habría dado en rojo** (la parte que más vale del tramo):

- **Reclasificar una detección ya emitida** reescribía en silencio lo que ya había leído quien
  recibió la alerta.
- **El consolidado se archivaba bajo la fuente de la norma que lo motivó**, no bajo la suya.
- **El comentario del UNIQUE de `version_norma` prometía una garantía que PostgreSQL no da** con
  columnas NULL.
- **Sin tope de preceptos publicados**: el tamaño de una respuesta pública lo decidía el documento.
- **`tests/gold_set/README.md` enseñaba el formato viejo** (`es_relevante`) después de cambiarlo.

**De método:**

- **Los cuatro subagentes, primera ejecución real (08-09).** El `revisor-seguridad` encontró un
  hallazgo alto propio —la validación de arranque de `llm_base_url`—, el `auditor-reglas` confirmó
  que el clasificador no existía **y lo dijo en vez de inventarlo**, y el `evaluador` corrió el
  prefiltro de verdad sobre el gold set. Dejaron de ser especificación sin probar.
- **Honestidad sobre el sondeo del ADR 0016**: el sondeo con el que se escribió se dejó fuera una
  de las supresiones, y se anotó en vez de taparlo.
- **El `<analisis>` resume y el cuerpo no.** Omite supresiones de *apartados* que el texto sí trae.
  No es una fuente completa, y por eso el catálogo lee el texto archivado.
- **Verificación por HTTP contra la base real, no solo tests**: sin sesión → 401 **y 0 filas en
  `alerta`**, porque el 401 no basta si la fila se escribió igual.

### ✅ La regla de oro 9, volumen de verdad, y la segunda fuente — 2026-08-16/17

Tres trabajos encadenados, y el detonante fue una pregunta del humano: *«¿el BOE publica las
resoluciones de las comunidades?»*.

#### 1. Trazabilidad por offsets (ADR 0013), la última regla de oro que se incumplía

`pipeline/anclaje.py`: cada texto que la extracción afirma haber leído se localiza en el texto
archivado y se guarda con su rango; **lo que no ancla descarta la extracción entera**. Dos
diferencias respecto a como 7.5 estaba escrita, ambas razonadas en el ADR: **los offsets los
calcula el sistema, no se le piden al modelo** —un 3B contando caracteres añade un modo de fallo
y no quita ninguno, porque habría que buscar el texto igualmente— y **no hay una segunda
normalización**: se ancla sobre el mismo texto que usan las reglas, porque dos derivaciones del
mismo documento son dos sistemas de coordenadas y la evidencia deja de poder contrastarse.

Lo que se guarda es el **recorte del archivo**, no la cadena del modelo. La única licencia al
comparar es colapsar espacios; una paráfrasis no ancla. Al actualizar los tests del extractor se
vio el control funcionando: las extracciones falsas de las fixtures **dejaron de persistirse**
porque citaban texto que no estaba en el documento de prueba.

#### 2. Volumen: `--hasta` y `--sin-extraccion`

Con 3 días ingeridos la pantalla se veía vacía. El cuello de botella de un backfill no es la red
(10 s por día) sino el LLM (133,9 s por norma), así que el worker gana un modo de backfill que
salta la extracción; lo que se salta **no se pierde**, porque la cola del extractor es una
consulta y una pasada normal lo recoge. **De 652 normas a 2.968**, un mes de BOE. Siete tests de
la línea de órdenes, que no tenía ninguno.

#### 3. El DOGC, segunda fuente y primera autonómica (ADR 0019)

**La respuesta a la pregunta del humano es no, y está medida**: de órganos autonómicos llegan al
BOE **31 ítems de 1.193**, todos anuncios y correcciones. Las leyes autonómicas sí se republican
—de ahí que la watchlist funcionara—, pero ni un decreto, ni una orden, ni una instrucción. Y de
lo municipal, solo convocatorias y licitaciones. O sea que el sistema estaba ciego exactamente
donde la sección 1 dice que mira.

Se verificaron **cinco fuentes descargando sus endpoints**, no leyendo documentación: el BOP de
Cáceres resultó ser metadatos sin texto ni enlace; el HTML del BOJA **declara por escrito que
suprime contenido** (choca con 7.1); el XML por disposición del BOCM devuelve 500. El DOGC fue el
único que cumplió los cuatro requisitos: sumario JSON por fecha, texto íntegro en XML, sin clave,
diario. **31.094 disposiciones desde 1977, de ellas 20.889 órdenes y 9.061 decretos** — el rango
bajo que motivaba todo esto.

**Tres cosas que costaron el rato y que ninguna documentación anunciaba:**

1. **El DOGC mete todo el articulado dentro de un atributo XML**, escapado como HTML, dentro de
   un Akoma Ntoso por lo demás de manual. `itertext()` devolvía cadena vacía: un derivador
   escrito contra el estándar habría archivado cientos de normas vacías, el prefiltro las habría
   descartado todas y **nada habría fallado visiblemente**. Tiene test con XML real.
2. **`portaldogc.gencat.cat` solo negocia TLS 1.2 con `AES256-SHA`**, que OpenSSL 3 rechaza. El
   síntoma engañaba: `curl` funcionaba y Python no, porque `curl` en Windows usa el TLS del
   sistema. Se aisló probando handshakes uno a uno. `url_guard` gana un **perfil heredado por
   host**: se relaja el cifrado solo ahí, **no** la verificación del certificado, y no para el
   BOE.
3. **Se ingiere la versión castellana**, no la oficial catalana, porque el vocabulario del
   prefiltro es castellano y sobre el catalán quedaría apagado en silencio. Las citas de las
   alertas saldrán de una traducción oficial, y eso está escrito donde toca.

**Verificado de punta a punta**: 4 disposiciones del 19-12-2024 ingeridas, archivadas,
descargadas y prefiltradas (3 sospechas, 1 descartada). La cobertura por CCAA lo refleja sola:
**Catalunya pasa a «autonómico: 1 de 1 vigilada»**. Migración de semilla a mano, 13 CHECK
intactas. **535 tests en verde.**

#### Siguiente, por orden

1. **Terminar el backfill del DOGC** (un año en marcha) y **medir el prefiltro sobre la
   traducción**: es la primera fuente cuyo texto no es castellano original y nadie sabe todavía
   si el eje léxico se comporta igual. Ninguna cifra de esto se publica sin casos del DOGC en el
   gold set.
2. **La capa provincial**: el BOPB (Barcelona) tiene RSS diario e histórico por fecha
   verificados; falta confirmar si sus PDF son nativos o escaneados, porque el OCR está fuera de
   alcance (sección 8).
3. **Los dos hallazgos abiertos de la auditoría** de seguridad: hambre de la cola de versionado y
   reintento eterno de fallos duros.

---

### ⚠️ Primera medición del extractor a escala, y no es buena — 2026-08-18

Se lanzó `--extraer` sobre las 121 normas en cola. **Se detuvo tras 11 normas y ~19 horas**, y lo
que dejó es más valioso que las filas que no escribió:

| dato | valor |
|---|---|
| normas intentadas | 11 |
| respuestas del modelo | 6 |
| **timeouts de Ollama (180 s)** | **4 de 11** |
| **descartadas por no anclar al archivo (regla de oro 9, ADR 0013)** | **3 de 6 respuestas** |
| filas nuevas | **0** |

**Tres hallazgos, en orden de gravedad:**

1. **El commit estaba fuera del bucle.** Cero filas con tres extracciones válidas: 19 horas de
   CPU que se habrían perdido enteras al cerrar la terminal. Arreglado —un commit por norma, como
   ya hacían la fase 2 y el versionado— y el motivo es el mismo: aquí cada iteración cuesta
   133,9 s y perder una hora por una interrupción es inaceptable.
2. **La mitad de lo que el modelo devuelve no ancla.** 3 de 6 respuestas afirmaban un
   `texto_anterior` que no está en el documento archivado. **El control del ADR 0013 funciona y
   por eso duele**: sin él, esas tres citas inventadas estarían hoy en la base de datos
   pareciendo evidencia. Es la primera cifra real de alucinación del sistema y hay que decirla
   entera: **con 6 respuestas no se puede afirmar un porcentaje**, solo que el fenómeno es
   frecuente y no anecdótico.
3. **El 36 % de las llamadas expira.** Cuatro timeouts de 180 s con documentos recortados a 4.000
   caracteres. La causa inmediata es la máquina —Ollama compitiendo con la suite de tests, que
   pasó de 50 s a 20 minutos—, pero el fondo es el que ya avisaba 6.9.7: un modelo de 3B en CPU
   no da para procesar un corpus, solo para demostrar el camino.

**Consecuencia para V1, dicha sin adornos:** el extractor **no es viable a escala en esta
máquina**, y el proyecto no depende de él para clasificar —el catálogo de reglas lee el texto
archivado (ADR 0016)—. Lo honesto es documentarlo como límite medido, no como algo pendiente de
terminar: la etapa existe, está verificada de punta a punta sobre casos concretos, y su coste real
la deja fuera del uso masivo hasta que haya GPU o un modelo distinto. Cualquier cambio de modelo
buscando calidad sigue prohibido sin gold set (sección 8).

---

### ⚠️→✅ 12 normas del DOGC son invisibles para el pipeline — 2026-08-18

> **La cifra estaba corta y el diagnóstico incompleto: son 172, y no son XML con un DOCTYPE
> de más sino páginas de error. Cerrado el 2026-08-19 con el ADR 0020 — ver la entrada
> siguiente. Se conserva porque el razonamiento que llevó a la decisión 2 sigue siendo el
> bueno, y porque enseña lo que costó no medir antes de escribir la cifra.**

Apareció buscando candidatos para el gold set, no buscándolo: al leer los 263 cuerpos catalanes
archivados, **12 fallan con `DtdForbidden`** — el documento declara un DOCTYPE y `xml_safe` lo
rechaza, que es exactamente lo que 6.1 le manda hacer (es la vía de entrada de XXE y de las
bombas de entidades).

**El control está bien; el problema es lo que pasa después.** Esas 12 normas están archivadas con
su huella, pero el prefiltro no puede leerlas, el catálogo de reglas tampoco, y se quedan en
`pendiente` para siempre sin que ninguna cifra del embudo las señale: el resumen del worker las
cuenta como `ilegibles` en la pasada en que ocurre y nadie las vuelve a mirar. **Es el falso
negativo invisible de la sección 1, esta vez causado por un control de seguridad propio.**

Lo que **no** se va a hacer: relajar `xml_safe`. Un DOCTYPE en un documento de una fuente externa
es justo lo que el proyecto decidió no procesar.

Lo que hay que decidir (y aún no está decidido, por eso queda escrito y no implementado):

1. **Reintentar pidiendo otro formato de la misma norma.** El DOGC publica cada disposición
   también en HTML y PDF; si el XML de esas 12 trae DOCTYPE, quizá el otro camino no.
2. **Marcarlas con un estado propio** —`ilegible`— en vez de dejarlas en `pendiente`, para que
   aparezcan en el embudo y en la interfaz como lo que son: normas que el sistema no puede
   vigilar. Hoy se confunden con «esperando su texto íntegro».

La segunda es obligatoria haga lo que haga la primera: **una norma que no se puede analizar tiene
que verse**, o el sistema afirma una cobertura que no tiene.


---

### ✅ El hueco del DOGC, medido y visible: el estado `ilegible` (ADR 0020) — 2026-08-19

El encargo era: drenar la fase 2 para separar lo que faltaba por descargar de lo que de verdad no
se puede leer, y luego darle estado propio. Lo primero cambió lo segundo.

#### 1. La fase 2 estaba drenada, así que el hueco no era de descarga

`--fase2` dejó la cola de descarga en **0** (había **1** norma pendiente en toda la tabla, no
172). Las 172 que seguían en `pendiente` **ya tenían su cuerpo archivado**: lo que fallaba era
leerlo. Sin ese paso previo, el trabajo se habría hecho sobre un diagnóstico falso.

#### 2. No son 12, son 172 — y no son un DOCTYPE de más, son la página de error del portal

| | |
|---|---|
| normas del DOGC ingeridas | 264 |
| cuerpos archivados que **no se pueden parsear** | **172 (65 %)** |
| de esas, contenido real | la **página de error** del Portal Jurídic, 12 KB, **HTTP 200** |
| huellas distintas entre las 172 | 172 — no es un fichero repetido, cada respuesta trae su ruido |
| cobertura real de la segunda fuente | **92 de 264 (35 %)** |

La estimación de 12 salió de una lectura parcial. La cifra buena salió de contar las 264 con el
mismo código que usa el pipeline. **Cualquier medición del DOGC —gold set incluido— es sobre el
35 %, y así hay que publicarla.**

Lo comprobado sobre `DOGC-24291044` (ORDEN ESP/214/2024), pidiendo formato por formato:

- `.../spa/xml` → página de error, HTTP 200. `.../cat/xml` → **la misma página de error**.
- `.../spa/html` → 77 KB de contenedor JavaScript: **cero apariciones** de «Artículo» o «Anexo».
- `.../spa/pdf` → **PDF nativo de 883 KB, con el texto dentro.**

O sea que la opción 1 que quedó escrita ayer —reintentar en otro formato— **no funciona por HTML**
y solo es viable por **PDF**, que es extracción de texto (permitida por 6.1; no hace falta OCR
porque el PDF es nativo). No se ha implementado: es otra etapa y otro ADR.

Y una cosa que el conjunto de datos abiertos no dice y ahora está en `docs/fuentes.md`: **anuncia
un `url_es_format_xml` para las 264**. La fuente promete un formato que sirve en el 35 % de los
casos, y lo niega con un 200.

#### 3. El estado `ilegible`, que es lo que se pedía y era obligatorio pasara lo que pasara

ADR 0020, migración `b8d2e40a71c5` escrita a mano. Lo que lo hace posible es una distinción de
tipos, no un valor nuevo: **`leer_cuerpo` levanta `CuerpoIlegible`** cuando hay cuerpo y no se
puede leer, y reserva `None` para «todavía no hay cuerpo». Antes las dos cosas eran el mismo
`None`, y por eso el prefiltro degradaba a fase 1 y la norma acababa en `pendiente`.

Cuatro decisiones que conviene no volver a discutir sin leer el ADR:

- **`ilegible` gana a cualquier señal del título.** Un `relevante` sacado del título metería la
  norma en la cola del extractor, que lee el cuerpo del almacén: un fallo por pasada, para
  siempre, y una cola que promete trabajo que nadie puede hacer.
- **Se reintenta en cada pasada** (`prefiltro_version_texto` a NULL a propósito). Es lo único que
  recupera la norma sola si su cuerpo pasa a ser legible. Tiene test: el estado sale solo.
- **Se conservan los términos del título**, que son la pista para priorizar la recuperación.
- **No se toca `xml_safe`.** Y hay que decir lo contrario de lo que parece: el control es **lo
  único** que impidió que 172 páginas de error entraran como normas. Sin él, el prefiltro las
  habría descartado por falta de vocabulario y **nada habría fallado visiblemente**. Es el mismo
  modo de fallo que el articulado dentro de un atributo (ADR 0019), y la segunda vez que esta
  fuente lo produce.

#### Verificado, no solo con tests

- **552 tests en verde** (12 nuevos), `ruff` y `mypy` limpios, `tsc -b --noEmit` limpio.
- Migración aplicada contra Postgres real: **14 CHECK**, `estadoprefiltro` sustituida y no
  duplicada, `origenclasificacion` intacta.
- `--reprefiltrar` sobre datos reales: **172 evaluadas → 172 ilegibles, 0 pendientes**. Estado
  final del DOGC: 41 sospecha, 51 descartada, **172 ilegible, 0 pendiente**.
- `GET /api/documentos/3499` devuelve `"prefiltro_estado":"ilegible"`.
- En el navegador (Archivo, DOGC-S-2024-12-31): la insignia **⊘ NO SE PUEDE LEER** en color de
  alerta —no de descarte, no de retroceso— y el contador **«0 de 2 entran en la cola · ⊘ 2 SIN
  PODER LEER»** fuera de la frase del embudo, para que no se lea como una categoría de descarte.
- La fixture del test es la página de error **real**, recortada, no un XML inventado con un
  DOCTYPE: lo que hay que poder reconocer es el caso que se cuela en el archivo.

#### 4. La cobertura pública deja de aparentar lo que no es

Lo encontró el `revisor-seguridad` sobre este mismo diff, y es el hallazgo que más valor tuvo:
la regla que yo acababa de escribir en 7.2 —«cualquier cifra de cobertura va acompañada de
cuántas de sus normas son ilegibles»— **la incumplía `GET /api/cobertura`**, que es literalmente
la única ruta que existe para declarar los huecos del proyecto (ADR 0014). El embudo del worker y
la pantalla de Archivo contaban el hueco; la API pública, no.

`/api/cobertura` gana `normas` e `ilegibles` por comunidad y en el total, siempre las dos juntas
(`ilegibles` a solas no dice si son 172 de 264 o de 20.000), agregadas en SQL como el resto del
endpoint. En el panel de Catalunya se ve así: «Autonómico **1 de 1**» —cierto, la fuente está
activa— y debajo, en ámbar, «**172 de 264 normas** están descargadas y archivadas, pero su texto
llegó en un formato que el sistema no puede leer». Las dos cosas son verdad y hacen falta las
dos. Cuatro tests nuevos lo fijan.

Los otros tres hallazgos de la auditoría fueron BAJA y se resolvieron así: **una línea de
WARNING** por pasada cuando hay ilegibles (no un código de salida distinto de cero: el cron
quedaría en rojo permanente mientras el hueco siga abierto, y un rojo que siempre está rojo no
avisa de nada) y el **`downgrade` de la migración cuenta y anuncia** cuántas filas pierden la
distinción antes de tocarlas. Queda abierto y anotado: `services/cuerpo.py` escribe **una línea
ERROR por norma ilegible y por pasada** —172 idénticas— y esa repetición puede enterrar la única
traza que diría que un control de seguridad saltó de verdad.

#### Lo que este trabajo NO hace, dicho para que no se dé por hecho

- **El color del mapa se sigue calculando con `vigiladas`**, no con la parte legible. Hoy no
  engaña porque el 35 % legible del DOGC sí se analiza, pero una comunidad con fuente activa y
  todo su contenido ilegible se pintaría igual que una vigilada de verdad.
- No recupera ni una de las 172. Para eso hace falta la etapa de PDF.

#### Siguiente, por orden

1. **Gold set con casos del DOGC (~20k).** Sigue siendo lo único que hace evaluable la parte de
   IA, y con el 22 encima. Ahora se puede etiquetar sabiendo cuáles son etiquetables: **solo las
   92 legibles**, y el caso ilegible merece uno o dos casos propios para que el gold set mida
   también que el pipeline los reconoce.
2. **Recuperar las 172 por PDF (~25k, y su ADR).** Extracción de texto de PDF nativo, sin OCR.
   Sube la cobertura del DOGC del 35 % al ~100 % si funciona.
3. **`docs/CLAUDE.md` está en 62 KB, por encima del límite de ~55 KB que él mismo fija.** Ya
   estaba en 60 KB antes de este trabajo. Es coste fijo de cada subagente; toca una poda.


---

### ✅ El gold set mide el DOGC, y lo primero que ha medido es un falso positivo — 2026-08-19

Ocho casos nuevos del DOGC, etiquetados leyendo el texto archivado uno a uno. **El corpus pasa de
14 a 22 casos.** Lo importante no es el número: es que la primera tanda de la segunda fuente ha
encontrado tres cosas que ninguna cifra agregada habría enseñado.

#### 1. El falso positivo, y el cambio de calibración que ha traído (ADR 0021)

`DOGC-24310119` es un **currículo de arte floral** de 105.101 caracteres. Su única coincidencia
con el vocabulario es «plan de igualdad», dentro del módulo de formación y orientación laboral:
*«Fases para la elaboración de un plan de igualdad en la empresa»*. El prefiltro lo mandaba a la
cola del LLM. Es el equivalente en el DOGC de la oposición que cita la Ley 4/2023 en el temario,
que 7.3 ya avisaba para el BOE **desde el 2026-08-07 sin que nadie pudiera aplicarlo**, porque
hacía falta un caso concreto y una medición.

Medido sobre la cola real (`scripts/medir_ruido_lexico.py`, queda en el repo):

| | antes | después |
|---|---|---|
| normas en la cola del extractor | **140** | **40** |
| de ellas, solo por términos de contexto | **100 (71 %)** | **0** |
| longitud mediana de esas 100 | 54.099 caracteres (máx. 2.035.373) | — |
| responsables | «igualdad de trato» (51), «plan de igualdad» (24), «no discriminación» (20), «registro civil» (18) | — |

**La decisión (ADR 0021): sobre el texto íntegro, el eje léxico exige al menos un término
DIRECTO.** Sobre el título no cambia nada —quince palabras, la presencia sí significa algo— y el
umbral de conteo sigue sin decidir ningún descarte. `VERSION_VOCABULARIO` sube a `2026.08.19`
aunque no se haya tocado ni un término, porque la versión cubre el eje entero.

**Lo que se pierde, contado y no adjetivado**: de las 13 detecciones con regla, 3 venían de
normas sin ningún término directo y **las 3 eran R-SUP-002**, la regla que el gate humano
descartó 10 de 10 veces y que por eso ya no se encola (ADR 0017). Las tres alertas publicadas
siguen sobre normas `relevante`, con 22, 31 y 7 términos directos: ninguna se ve afectada. Los 22
casos del gold set siguen coincidiendo con su etiqueta —antes fallaba uno— así que el recall
medido no baja.

Quedan 3 detecciones colgando de normas que ahora son `descartada`. No se retiran solas, por la
misma política de siempre (una detección es rastro de auditoría), y son justo las 3 de R-SUP-002.

#### 2. El eje referencial no existe en el DOGC, y está medido

`DOGC-24261095` deroga artículos del Decreto 134/2022, que es el de estructura del **Departamento
de Igualdad y Feminismos** — donde viven las competencias LGTBI en Catalunya. Es exactamente el
tipo de norma que el eje referencial existe para atrapar. No la atrapa:

| | BOE | DOGC |
|---|---|---|
| cuerpos legibles | 2.968 | 92 |
| **con referencias que el eje puede leer** | **211 (7,1 %)** | **0** |

El DOGC sí trae `<references>` en su Akoma Ntoso, pero **sus `activeRef` apuntan al propio
documento** con `showAs="Modificado"`/`"Derogado"` —son ciclo de vida, no «a quién afecta»— y los
`passiveRef` son normas *posteriores*. Comprobado en cuatro documentos distintos, uno de ellos
titulado literalmente «de modificación del Decreto 358/2004»: la norma afectada **no aparece en
ningún metadato, solo en el texto**.

Consecuencia dicha entera: **en la segunda fuente el sistema vigila con un solo eje**, y es el
léxico, que es justo el que 7.3 describe como incapaz de ver «se modifica el epígrafe 4.3 del
anexo II». Hay un camino y no es caro —la watchlist habla en identificadores del BOE
(`BOE-A-2014-11990`) y el DOGC cita «Ley 11/2014, de 10 de octubre», así que haría falta que cada
entrada de la watchlist llevara sus **formas de cita** y cruzarlas contra el texto— pero es
trabajo con su propio ADR, no un parche.

#### 3. Dos cosas menores que aparecieron al etiquetar

- **`organo_emisor` del DOGC es literalmente «DOGC»**: el conjunto de datos abiertos no publica
  el departamento que emite. Como 7.3 mete el órgano emisor en el texto examinado «porque a veces
  es ahí donde está la señal», en esta fuente esa vía aporta cero. No es arreglable desde el
  conjunto de datos actual.
- **El DOGC empotra fórmulas de lenguaje inclusivo y de desagregación estadística en casi todos
  sus decretos de estructura.** Eso es lo que dispara el eje léxico en `DOGC-24317111` (Política
  Lingüística) o `DOGC-24136006` (régimen lingüístico educativo). Se han etiquetado `sospecha` y
  no `descartada` a conciencia: la cláusula «los datos se desagregarán por sexo e identidad de
  género (mujer/hombre/persona no binaria)» **es un precepto**, y quitarle «persona no binaria»
  sería un retroceso real sin titulares. La línea entre esto y el currículo de arte floral es la
  que separa fórmula-con-precepto de fórmula-sin-ninguno, y está escrita en las notas de los
  casos.

#### Verificado

- **588 tests en verde** (32 nuevos desde ayer), `ruff` y `mypy` limpios.
- Gold set: **22 de 22 casos coinciden con su etiqueta**, y los 8 del DOGC coinciden también con
  lo que tiene la base de datos real tras `--reprefiltrar`.
- `--reprefiltrar` sobre 3.232 normas: 3 relevantes, 37 sospechas, 3.020 descartadas, 172
  ilegibles, **0 que pasen solo por términos de contexto**.

#### Siguiente, por orden

1. **Más casos del gold set, y los que faltan son de un tipo concreto** (~20k). El corpus tiene
   22 de los 60-80 del plan. Y el hueco no es de cantidad: **falta el caso que evalúa el eje
   referencial de verdad** —una norma de título anodino que modifique algo de la watchlist sin
   nombrar al colectivo— porque los tres casos donde hoy dispara los detecta también el léxico.
   Sin él, la aportación única del eje referencial medida sigue siendo cero.
2. **El eje referencial por citas textuales (~25k + ADR).** Es lo que lo haría funcionar en el
   DOGC y en cualquier fuente que no sea el BOE. La watchlist necesita formas de cita; el cruce
   se hace contra el texto, validando formato antes y sin construir ninguna URL con ello (6.10).
3. **Recuperar las 172 ilegibles del DOGC por PDF (~25k + ADR).** Sin esto, cualquier medición de
   esa fuente es sobre el 35 % de su contenido.


---

### ✅ El eje referencial existe fuera del BOE (ADR 0022), y su aportación medida es cero — 2026-08-19

Continuación directa de lo anterior. El gold set había dejado señalado que el eje 2 no funciona en
el DOGC; esto lo arregla, y **el resultado honesto es menos vistoso de lo que parecía**.

#### Lo que se ha construido

`pipeline/citas.py` produce `ReferenciaAnterior` —**el mismo tipo** que el bloque `<analisis>` del
BOE— a partir de las citas dentro del texto: «Se suprime el apartado 2 del artículo 8 de la Ley
2/2016, de 29 de marzo». Se fusionan en `leer_cuerpo`, así que **ninguna etapa se entera**: el
prefiltro, el versionado y las reglas siguen preguntando lo mismo a la misma estructura.

Cuatro reglas, y ninguna es una intuición:

- **Solo forma larga, número y fecha.** La corta produjo **4 coincidencias de 4 falsas** sobre el
  DOGC: «Ley 2/2021» caza la catalana de medidas fiscales en vez de la canaria vigilada, y «Ley
  4/2023» caza dentro de «**Decreto ley** 4/2023». De ahí el `(?<!decreto )` del patrón, que sin
  la medición nadie habría escrito. Cada trampa tiene su test.
- **El verbo se busca 200 caracteres hacia atrás**, que es donde lo pone el texto dispositivo.
- **Sin verbo, `CITA`**, que no dispara nada. Mencionar una ley no es tocarla.
- **La watchlist se pasa por parámetro, no se carga dentro de `leer_cuerpo`.** Lo delató el propio
  diseño: cargarla ahí mete estado global en una función de lectura y deja fuera de juego a los
  tests que la sustituyen.

#### Lo que aporta, medido y sin maquillar

Reevaluado el corpus entero (3.232 normas): el eje referencial dispara en **3 normas, las mismas 3
que ya disparaba con el `<analisis>`**. **Su aportación única es cero**, y presentar ese 3 como
resultado de este trabajo sería apuntarse el de otro.

Lo que sí queda demostrado son dos cosas:

1. **Encuentra la modificación leyendo solo el texto.** Sobre `BOE-A-2024-10767` —la reforma
   madrileña de 2023— saca `BOE-A-2016-6728` con verbo `SUPRIME` sin tocar el metadato. Lo delató
   un test del versionado que se puso rojo al conectarlo: neutralizar el `<analisis>` ya **no
   basta** para neutralizar una referencia, porque ahora hay dos fuentes.
2. **Cero falsos positivos sobre 3.060 cuerpos**, que es lo que hay que exigirle a un módulo que
   busca citas de leyes en texto libre.

Y lo que cubre no ha ocurrido todavía en este corpus: un decreto autonómico que modifique la ley
trans de su comunidad. Hasta hoy eso era **invisible por construcción** en el DOGC.

#### Estado del corpus tras las dos calibraciones del día

| | |
|---|---|
| normas | 3.232 |
| en la cola del extractor | **40** (3 relevantes + 37 sospechas), desde 140 |
| descartadas | 3.020 |
| ilegibles (ADR 0020) | 172 |
| que pasan solo por términos de contexto | **0** |
| ejes | `lexico` 38, `lexico+referencial` 3 |

**607 tests en verde** (19 nuevos), `ruff`, `mypy` y `tsc` limpios.

#### Siguiente, por orden

1. **Más casos del gold set (~20k), y sigue faltando el mismo**: una norma de título anodino que
   modifique algo de la watchlist sin nombrar al colectivo. Ahora hay **dos** caminos por los que
   podría entrar —metadato y cita— y ninguno está evaluado con un caso propio.
2. **Recuperar las 172 ilegibles del DOGC por PDF (~25k + ADR).** Es el único formato con texto.
3. **La poda de `docs/CLAUDE.md` está empezada, no terminada** (~10k para cerrarla). De 63,4 KB a
   **62,2 KB**, con el límite que el propio fichero fija en ~55 KB. Lo hecho han sido tres
   movimientos seguros, sin perder una línea: el script del driver salió a `run_agent.sh` —donde
   la sección 4 decía que estaba, y donde no puede desincronizarse de una segunda copia—, el
   backlog de producto de la sección 12 se movió aquí, y el changelog de 7.5 se comprimió a sus
   reglas dejando el porqué en el ADR 0013.

   Lo que queda son **reescrituras de prosa normativa, no movimientos**, y ahí el riesgo de
   perder un matiz que este proyecto valora es real. Los candidatos, por tamaño: §7.3 (5,7 KB),
   §5 modelo de dominio (3,6 KB), §6.9 Ollama (3,3 KB), §7.2 (3,0 KB). **Que lo decida una
   persona**: la parte mecánica ya está hecha.


---

### 📋 Backlog de producto, traído desde CLAUDE.md — 2026-08-19

Pedido por el humano al cierre de S0 y guardado hasta hoy en la sección 12 de las reglas. Se
traslada aquí **entero y sin tocar** porque es trabajo pendiente —o sea estado— y en el fichero
de reglas costaba 1,5 KB de contexto a cada subagente que arranca. La sección 12 conserva lo que
sí es una regla: las acciones externas que no se hacen sin permiso.

No reordenar por criterio propio sin comentarlo primero; si alguno ya no aplica o contradice algo
de `CLAUDE.md`, **para y pregunta** antes de tocarlo.

### Contenido

- Texto reivindicativo al principio (pantalla Mapa/home): explicar el objetivo del proyecto,
  a quién protege y por qué existe, antes de que el usuario llegue al mapa. Contenido, no
  solo maquetación — pensar el mensaje con calma, no rellenar con genérico.

### Mapa

- Canarias no se renderiza bien (posición/escala rotas en el recuadro inferior izquierdo).
  Revisar el offset manual que trae `MapaCCAA`/`_design-export/data/ccaa-paths.json`.
- Hacer el mapa ampliable (zoom), para poder bajar de CCAA a provincia y localidad.
- Añadir división por provincias y localidades, no solo CCAA (implica geometría nueva, no
  solo la que ya tenemos — no inventar límites, buscar fuente oficial equivalente al IGN).
- Faltan las ciudades autónomas (Ceuta y Melilla) en el mapa actual — ni geometría ni datos
  mock las incluyen hoy.

### Datos / navegación

- El enlace a "Texto íntegro" / fuente oficial en la Ficha de norma no lleva al documento
  real todavía (hoy es un ancla muerta `#fuente`; no hay backend detrás). Puede quedar como
  TODO explícito hasta que exista almacenamiento real, pero no debería parecer un enlace
  funcional si no lo es.

**Dos apuntes de verificación del 2026-08-19**, para que nadie rehaga lo hecho: el **texto
reivindicativo ya está** en la portada («Un derecho no se pierde el día que sale en los
periódicos», visto en el navegador), y el enlace **«Texto íntegro»** de la ficha **ya lleva a la
fuente oficial** — apunta a `url_texto`, que existe desde la fase 2. Lo del mapa (Canarias, zoom,
provincias, Ceuta y Melilla) sigue como estaba; ojo con el zoom, que se quitó a propósito en el
commit `0a0a32d`.


---

### ✅ Cuatro casos más del gold set, del BOE — 2026-08-19 (cierre de sesión)

El corpus pasa a **26 casos**. Los cuatro son del BOE y cada uno mide algo que el corpus no
medía:

- **`BOE-A-2024-10765`, Ley de Presupuestos de Madrid.** El vehículo clásico del cambio que no
  sale en los periódicos. 327.937 caracteres, **una** coincidencia directa («educación afectivo
  sexual») en una frase programática de salud. Verificado buscando además «trans*», «identidad de
  género», «LGTB», «diversidad sexual», «Ley 2/2016» y «Ley 3/2016»: **cero apariciones**. O sea
  que la ley de presupuestos **no toca** la ley trans madrileña, aunque sea del mismo mes y la
  misma legislatura que la Ley 17/2023 que sí la recorta. Es el caso que impide dar por hecha una
  relación que no existe.
- **`BOE-A-2024-24104`, bases de subvención.** El vector que el análisis jurídico señala como más
  silencioso: el dinero se quita antes que el derecho. El «colectivo LGTBI» figura entre los
  destinatarios; sacarlo de esa enumeración no modificaría ninguna ley.
- **`BOE-A-2024-23757`, cualificaciones profesionales.** El documento más grande del corpus
  (1.975.355 caracteres, el que obliga a pensar en el truncado de 6.9.7) y el único que combina
  contenido del ámbito educativo-laboral —criterios de competencia sobre orientación sexual e
  identidad de género— con un título que dice «se actualizan y **suprimen**».
- **`BOE-A-2024-23937`, convenio del aplicativo SEGISS.** El caso más discutible, y está puesto
  para que la discusión quede escrita: su única coincidencia son tres apariciones de «Diversidad
  Familiar» **dentro del nombre del órgano que firma**. Se etiqueta `sospecha` y no `descartada`
  porque 7.3 mete el órgano emisor en el texto examinado **a propósito**; descartarlo sería
  etiquetar en contra de una decisión de diseño vigente en vez de medir su efecto. Con la
  medición al lado: «diversidad familiar» sale en 3 de 3.060 cuerpos y solo aquí es únicamente el
  órgano — **con 1 caso de 3.060 no se toca un vocabulario**, que es la lección del ADR 0021.

**623 tests en verde.** Gold set: 26 de 26 coincidiendo con su etiqueta.


---

### ✅ El caso que faltaba desde el 9 de agosto, encontrado preguntándole al BOE — 2026-08-19/20

El gold set llevaba once días pidiendo lo mismo: **una norma de título anodino que modifique una
norma de la watchlist**, cuyo arquetipo es una disposición final de una ley de acompañamiento
presupuestario. Sin ella, el eje referencial estaba **declarado pero no evaluado**: los tres
casos donde disparaba los detectaba también el léxico.

#### No se buscó ingiriendo días a ciegas: se le preguntó al BOE

El texto **consolidado** de cada norma vigilada trae en `<posteriores>` quién la ha modificado
después. 21 peticiones y salieron **29 normas modificadoras** con nombre y fecha, o sea
exactamente qué días había que ingerir. Queda en `backend/scripts/quien_modifica.py`.

El detalle que costó encontrarlo, y está escrito en el script para no repetirlo: **ese bloque no
tiene la forma del `<anteriores>`** del texto de una norma. Usa `<id_norma>` y `<relacion>` («SE
MODIFICA»), no el atributo `referencia` ni `<palabra>`.

#### Cuatro días ingeridos, tres casos nuevos, y el corpus a 29

De 3.232 normas a **4.081**, con 157 sumarios. Y los tres casos son un solo experimento:

| caso | qué es | resultado |
|---|---|---|
| `BOE-A-2022-2066` | **Presupuestos Generales de Navarra 2022** | `relevante` por eje referencial. Modifican el art. 7 de la ley trans navarra |
| `BOE-A-2021-1859` | **ley de medidas fiscales** de la Generalitat Valenciana | `relevante` por eje referencial. Modifica la ley LGTBI valenciana |
| `BOE-A-2021-1860` | **Presupuestos** de la Generalitat 2021, **mismo día** que la anterior | `sospecha`: solo la **cita** |

Lo que hace valioso al de Navarra: **161.104 caracteres y UN solo término directo** («lgtbi»).
Sin el eje referencial sería `sospecha` —el último puesto de la cola— en vez de `relevante`. Es
la demostración, con un documento real, de que el eje 2 **no duplica al léxico**.

Lo que hace valioso al par valenciano: son dos leyes de acompañamiento hermanas, publicadas el
**mismo día** por el **mismo parlamento**, con títulos igual de anodinos y **cuatro términos
directos cada una**. Una modifica la ley LGTBI y la otra solo la cita. Sin la segunda, un eje
referencial que disparase con cualquier mención pasaría el gold set igual de verde que uno
correcto; con ella, **se pone rojo si alguien afloja la condición `es_modificativa`**, que es la
única línea que separa «toca esta ley» de «la nombra».

#### Y el ADR 0022 tiene su primera validación en la naturaleza

Ejecutadas las dos fuentes de evidencia por separado sobre los cuerpos archivados:

- `BOE-A-2021-1859`: el `<analisis>` dice `MODIFICA` **y el eje por citas del texto también**, por
  su cuenta. Hasta este documento la aportación medida del eje por citas era cero.
- `BOE-A-2022-2066`: aquí la señal la aporta **solo el metadato**; la cita aparece sin verbo
  modificativo cerca y sale como `CITA`. Las dos fuentes se complementan y ninguna sobra.
- `BOE-A-2021-1860`: `<analisis>` vacío y cita sin verbo → **no dispara**, que es lo correcto.

#### Verificado

- **635 tests en verde**, `ruff` y `mypy` limpios. Gold set: **29 de 29 coincidiendo** con su
  etiqueta.
- Estado del corpus: 4.081 normas, 7 relevantes, 45 sospechas, 172 ilegibles, **0 pendientes**,
  0 en cola de fase 2.

#### Siguiente, por orden

1. **Seguir el filón**: quedan **26 normas modificadoras más** en la lista de
   `quien_modifica.py` sin ingerir, entre ellas varias órdenes que tocan la **cartera común de
   servicios del SNS** (`BOE-A-2024-12290`, `BOE-A-2025-9277`, `BOE-A-2026-8592`,
   `BOE-A-2026-16654`) — el vector sanitario, que el corpus todavía no tiene medido. Cada día
   cuesta unos 3 minutos de ingesta.
2. **Recuperar las 172 ilegibles del DOGC por PDF** (~25k + ADR).
3. **Terminar la poda de `docs/CLAUDE.md`** (62,2 KB con el límite en ~55).


---

### ✅ El gold set encontró un falso positivo del clasificador, y era grave (ADR 0023) — 2026-08-20

Esto es lo que un gold set existe para hacer, y ha tardado un día en hacerlo. Al ampliar el
corpus con normas que modifican la watchlist —buscadas a propósito con `quien_modifica.py`—
apareció que **R-SUP-001, la única regla que afirma un signo, iba 2 de 4 en falsos positivos**.

#### El error, y por qué es el peor posible aquí

`BOE-A-2026-8073` es la **nueva ley LGBTI catalana**: noventa y cinco artículos, deroga y
sustituye a la Ley 11/2014 vigilada ampliando protección, 34 términos directos (el máximo del
corpus). El catálogo la clasificó **`retroceso`, severidad 4**.

El motivo: R-SUP-001 exigía «hay una supresión en el texto» **y** «se toca una norma vigilada»,
sin comprobar que la supresión fuera *de esa norma*. Esta ley suprime, en una disposición final,
un apartado de la **Ley de finanzas públicas de Cataluña**. Eso bastaba. Una ley que amplía
derechos clasificada como lo contrario por una cláusula sobre presupuestos.

El mismo patrón afectaba a `BOE-A-2021-1859`, la ley de medidas fiscales valenciana: modifica la
ley LGTBI valenciana **y** suprime unas tasas de un centro público. Dos hechos sin relación en
457.720 caracteres.

#### El arreglo: el verbo tiene que ir pegado a la norma

Lo que separa los verdaderos positivos de los falsos ya estaba delante y no se leía: **la propia
referencia lo dice**. En los buenos, el `<analisis>` del BOE escribe «…y **SUPRIME** los arts. 7,
24 y 45, 48 y los títulos X y XIV»; en los falsos, solo «el art. 8.5 y la disposición final 2».

R-SUP-001 pasa a exigir que la referencia declare la supresión, y la evidencia del veredicto
nombra esa norma y no cualquier vigilada que el documento toque de paso. Vale para las dos
fuentes del ADR 0022 (el metadato y la cita del texto).

#### Y el mismo caso destapó el fallo simétrico

La disposición derogatoria catalana dice «**Se deroga** la Ley 11/2014, de 10 de octubre», y
R-DER-001 **no la veía**: el patrón excluía `se deroga` sin «expresamente». Con el primer arreglo
puesto, esa norma caía a R-SUP-002 con severidad 2 y con la cláusula de finanzas como evidencia —
el sistema le habría enseñado a quien revisa un asunto presupuestario cuando lo que pasó es que
la ley LGBTI catalana fue derogada y sustituida.

Al mirar juntas las tres formas de ruido del corpus se ve que **lo que las separa no es
«expresamente», es la posición**: la operativa abre frase y el ruido va incrustado, sea el título
de un reglamento europeo citado («…y por el que se deroga la Directiva 95/46/CE») o el preámbulo
contando lo que hará («Mediante la disposición derogatoria única se deroga la Ley 3/2007…»). Ese
segundo ejemplo es del caso insignia y es el que fija el criterio: sin él, la Ley 4/2023 emitiría
dos evidencias para una sola derogación y una sería el preámbulo hablando de derogar.

#### El efecto, medido sobre 5.229 normas

| | antes | después |
|---|---|---|
| `R-SUP-001` → **retroceso** | 4 (2 falsos) | **2**, las dos reformas madrileñas |
| `R-DER-001` → indeterminado | 1 | **2** (entra la ley catalana) |
| `R-MOD-001` → indeterminado | 2 | 6 |

**Las dos leyes que amplían derechos —la Ley 4/2023 y la Ley 13/2025 catalana— quedan las dos en
`indeterminado`**, severidad 4, a la cola de revisión. Las tres alertas ya emitidas conservan su
veredicto, y el aviso de «YA TIENE ALERTA EMITIDA y el catálogo reescribe su evidencia» saltó en
las tres como debía.

#### Un tropiezo propio que queda escrito en la constante

`VERSION_REGLAS` lleva sufijo numérico desde hoy (`2026.08.20.2`). Hice dos cambios del catálogo
el mismo día con la misma cadena de versión, y el segundo **no reevaluó nada**: `--reclasificar`
pregunta por la versión, la vio igual y se saltó las 56 filas. No falla nada visiblemente; el
arreglo simplemente no llega. Es el mismo modo de fallo mudo que este proyecto persigue en otros
sitios, esta vez dentro de casa.

#### Estado del corpus

- **5.229 normas** (desde 3.232 esta mañana), 157+8 sumarios, 11 relevantes, 45 sospechas, 172
  ilegibles, **0 pendientes**.
- **Gold set: 31 casos**, todos coincidiendo con su etiqueta, y desde hoy evaluados con **las
  dos fuentes de referencia** del ADR 0022 y no solo con el `<analisis>`: medir con menos
  evidencia que el sistema real da un recall que nadie puede usar.
- **La suite pasó de 2 a 35 minutos y vuelve a estar en 1:37.** Los cuerpos que entraron hoy
  —uno de 1.975.355 caracteres y varios de medio millón— se leían, parseaban y prefiltraban
  **tres veces por caso**, una por cada test que los mira. Se memoizan por `sha256`.
- El test `test_el_corpus_no_es_suficiente_para_medir_recall` saltó al pasar de 30 casos, que es
  para lo que estaba puesto. Reescrito: de sus tres condiciones, la primera (que el worker
  descargue texto íntegro) ya está cumplida desde la tarea 0.c, y se le añadió una cuarta que no
  existía cuando se escribió porque solo había una fuente — **qué parte de cada fuente es
  legible**. El próximo corte es 60, el mínimo del plan.

#### Siguiente, por orden

1. **Seguir el filón**: de las 29 normas que `quien_modifica.py` encontró, quedan unas 20 sin
   ingerir, casi todas órdenes que tocan la cartera común del SNS entre 2009 y 2022. La de 2014
   (`BOE-A-2014-11444`, anexos I, II y III) es la más interesante: es el año en que se restringió
   el acceso a la reproducción asistida, y sería el primer **retroceso histórico verificable** del
   corpus.
2. **Recuperar las 172 ilegibles del DOGC por PDF** (~25k + ADR).
3. **Terminar la poda de `docs/CLAUDE.md`** (63,5 KB con el límite en ~55).


---

### ✅ El eje referencial deja de valer cero, y lo que rescata son órdenes sanitarias — 2026-08-20

Doce días de BOE ingeridos a tiro hecho con `quien_modifica.py` —**doce días, doce aciertos**, un
`relevante` por día y siempre la norma buscada— y de ahí sale el resultado que al proyecto le
faltaba desde que existe el eje 2.

#### La cifra

De las **15 normas `relevante`** del corpus, **5 tienen CERO términos directos**. Las cinco son
órdenes ministeriales que modifican la cartera común de servicios del SNS. Desde el ADR 0021 el
eje léxico las descarta —sus únicas coincidencias son de contexto: «cartera de servicios»,
«reproducción humana asistida»— así que **sin el eje referencial las cinco se caen del sistema**.

Medido evaluando el mismo cuerpo archivado dos veces (`BOE-A-2014-11444`):

    con eje referencial -> relevante
    SIN eje referencial -> DESCARTADA

Hasta hoy, la aportación **única** del eje referencial medida sobre el corpus era **cero**: los
casos donde disparaba los cazaba también el léxico, y así estaba escrito en el README del gold
set y en el ADR 0022. **Ya no.** Y hay que separar dos cifras que es fácil sumar por error: lo
que deja de ser cero es la aportación del **eje**; la de su segunda fuente de evidencia —las
citas del texto, ADR 0022— sigue siendo cero, porque a estas cinco las caza el `<analisis>`.

#### Por qué importa que sean justo esas cinco

`BOE-A-2014-11444` está en el gold set como el caso insignia del eje. Es la **Orden SSI/2065/2014**
que concreta el alcance de la cartera común en, entre otras áreas, la **reproducción humana
asistida** — el instrumento por el que se fija quién accede a esa prestación en el sistema
público, que es lo que se restringió en 2014 y se rectificó en 2018. 43.510 caracteres, rango
bajo, un martes de octubre, y **ni una sola palabra del colectivo en el texto**.

Es, palabra por palabra, lo que CLAUDE.md 7.3 dice que el eje viene a tapar: «una instrucción que
elimina un derecho no dice "identidad de género", dice "se modifica el epígrafe 4.3 del anexo
II"». El corpus ya tiene el documento que lo demuestra.

#### Estado

- **5.700+ normas**, 164 boletines, 15 relevantes, 45 sospechas, 172 ilegibles.
- **Gold set: 32 casos**, todos coincidiendo.
- **El gate humano tiene 7 ítems pendientes**, y no son ruido: dos leyes de acompañamiento que
  modifican leyes LGTBI autonómicas, cuatro órdenes de la cartera del SNS y la nueva ley LGBTI
  catalana. Eso es el sistema entregando trabajo real a una persona.
- `version_norma` tiene **100 filas con texto anterior** sobre 6 normas vigiladas, 26 de ellas de
  la cartera del SNS: el «antes decía / ahora dice» que hace útil una alerta.
- La franja de la portada decía **«100 documentos archivados»** con 163 en el almacén, porque
  contaba la longitud de una lista topada a 100. Arreglado: el total sale de `/api/cobertura`, y
  de paso la petición baja de cien documentos a uno.

#### Siguiente, por orden

1. **Quedan ~14 normas modificadoras sin ingerir** de la lista de `quien_modifica.py`, casi todas
   órdenes de la cartera del SNS entre 2009 y 2019. Cada día son ~4 minutos y el acierto va 12
   de 12.
2. **Recuperar las 172 ilegibles del DOGC por PDF** (~25k + ADR).
3. **`docs/CLAUDE.md` está en 63,5 KB** con el límite en ~55. La parte mecánica de la poda está
   hecha; lo que queda son reescrituras de prosa normativa y **eso lo decide una persona**.


---

### ✅ El informe de apoyo entra en el producto, y el gate gana su segunda puerta — 2026-08-20/21

Dos ADR y el cierre del ciclo que empezó con el gold set: el sistema detecta, el catálogo
clasifica, un asistente prepara el trabajo y **decide una persona**.

#### ADR 0024 — la segunda puerta del gate

«Se suprime el Consejo LGTBI de Aragón» no nombra ninguna norma vigilada —ese consejo lo creó un
decreto que no está en la watchlist— así que la detección se creaba y **moría sin que nadie la
mirase**. Desaparecía quien vigila la ley y era invisible.

`R-SUP-003` exige las dos condiciones **sobre la misma cláusula**: nombre de órgano y término
directo. Es el ADR 0023 aplicado antes de cometer el error, con un test que siembra las dos
condiciones en cláusulas distintas y exige que **no** dispare. El gate lo comprueba por el
contenido de la evidencia (`organos_afectados`), no por el identificador de la regla.

**Medido antes de abrirla: de las 10 detecciones de R-SUP-002 del corpus, cero la cruzan.** Coste
en ruido, cero. Y por lo mismo **su precisión está sin observar**: es la primera regla del
catálogo que entra sin un documento del corpus delante, y queda escrito en el ADR.

#### ADR 0025 — el informe de apoyo, y el hallazgo que no es una alerta

El dosier que el `jurista-lgtbi` escribe para cada ítem deja de vivir en una conversación:
`informe_revision`, colgando de `cola_revision` y **nunca de `deteccion`**. Si se borrara la tabla
entera, ninguna alerta cambiaría de signo — esa es la prueba de que la separación es real.

Cuatro decisiones que no se relajan:

1. **`refutacion` es NOT NULL** en el esquema y se rechaza antes en el importador. Sin «qué me
   refutaría», la recomendación funciona como un sello de goma.
2. **El semáforo no es el signo.** «Alerta» significa «yo publicaría esto»: de los tres primeros
   informes en rojo, **dos son avances**. Enum propio y paleta de prioridad, no de retroceso.
3. **La generación vive fuera del sistema y se dice.** El único modelo que el proyecto puede
   permitirse es el 3B local, con 36 % de timeouts y la mitad de las respuestas sin anclar. Un
   panel que dijera «análisis del asistente» con eso detrás prometería lo que el sistema no hace.
4. **Un hallazgo histórico no entra nunca en la tabla `alerta`.** Se deriva de tener informe con
   semáforo `alerta` sin aprobación humana. Dos superficies en dos sitios distintos de la base, y
   por eso la frase de la portada sigue siendo literalmente cierta.

Y `corroboraciones` —lo que FELGTBI+, Amnistía o ILGA ya han documentado, con enlace— es lo que
hace publicable un hallazgo sin revisión humana: sin ese campo se publicaría la opinión de un
modelo; con él, **dos hechos verificables y ninguno nuestro**.

#### El panel

El informe se pinta **debajo de la evidencia y del diff, nunca encima**, y eso no es maquetación:
leer «yo publicaría esto» antes que el artículo convierte al gate en un trámite. Está escrito en
la cabecera del componente para que nadie lo reordene por hacer sitio. `refutacion` va con el
mismo peso visual que la recomendación y **jamás plegada**.

Verificado importando los tres informes reales del 2026-08-20. **665 tests en verde.**

#### La ingesta de fondo, y el cuello de botella que no era el pipeline

Corriendo hacia atrás desde hoy, por bloques mensuales, para que la cobertura sea **contigua y
llegue siempre hasta hoy** — un archivo que termina hace un mes se ve fatal en una demo.

**El ritmo real son 834 documentos/hora**, unos 20 minutos por día de BOE. La noche del 20 al 21
se perdieron **15 horas porque el ordenador se durmió**; con la suspensión desactivada, un año son
cuatro días de reloj. Si la ingesta parece lenta, mira eso antes que el código.

#### Siguiente, por orden

1. **Rehacer los siete informes con corroboraciones** (~15k). El campo existe y se pinta, pero los
   informes de hoy se escribieron antes que él. **Sin corroboración no hay hallazgo publicable**,
   así que esto bloquea el objetivo del histórico.
2. **La superficie pública de hallazgos** (~20k): lista y feed, con su etiqueta y separada de las
   alertas. Es la otra mitad del ADR 0025.
3. **Seguir la ingesta hacia atrás** mes a mes. Es tarea de fondo: se lanza y se deja.
4. **Gold set de 32 a 60-80 casos** (~20k). Ahora habrá corpus corriente contra el que medir.
5. **Las 172 ilegibles del DOGC por PDF** (~25k + ADR).
6. **La poda de `CLAUDE.md`**, en 63,5 KB con su límite en ~55. La parte mecánica está hecha; lo
   que queda son reescrituras de prosa normativa y **lo decide una persona**.

### ✅ Los informes tienen corroboración, y dos hallazgos ya son publicables — 2026-08-21

El campo `corroboraciones` del ADR 0025 existía y se pintaba desde ayer, pero **estaba vacío en
los tres informes que había**: se escribieron antes que él. Sin corroboración no hay hallazgo
publicable, así que esto era lo que bloqueaba el objetivo del histórico. Ya no.

Los **siete** ítems pendientes de la cola tienen informe nuevo, generado por el subagente
`jurista-lgtbi` sobre el **texto archivado real** —se le volcó el contenido alrededor de cada span
de evidencia, para que las citas salieran del fichero sellado y no de su memoria— y verificados de
punta a punta hasta el esquema de la API.

#### Lo que sale publicable, y lo que no

| | ítems | por qué |
|---|---|---|
| **Hallazgo publicable** | `BOE-A-2014-11444`, `BOE-A-2021-18287` | semáforo `alerta`, sin aprobación humana **y con corroboración** |
| Solo para el gate | los otros cinco | o no son `alerta`, o nadie los ha documentado |

Los dos publicables son el par exclusión→reparación de la reproducción asistida, y su respaldo es
el bueno: el **Ministerio reconociendo por escrito y en el BOE** que su propia orden de 2014 dejó
fuera a «las mujeres sin pareja, las lesbianas o las personas transexuales que conservan la
capacidad de gestar», más **FELGTBI+** y **Civio**, que cita el mismo requisito de «coito vaginal»
que está en nuestro texto archivado. Son dos hechos verificables por separado y ninguno nuestro,
que es exactamente lo que pide la decisión 4 del ADR 0025.

#### Lo que no se ha encontrado, dicho como toca

**Dos informes van con `corroboraciones: []` y eso es un resultado, no un hueco.** Las órdenes
SND/454/2025 y SND/44/2022 no las ha comentado ninguna organización: solo hay repositorios legales
y prensa sanitaria. Es coherente con que ninguna de las dos toque nada del colectivo, y es también
el perfil de lo que este proyecto existe para leer — cambios de anexo técnico sin titulares, que
casi nunca tienen a quién citar. Sirven igual para el gate humano; a la web no salen.

Se rechazaron corroboraciones que habrían colado fácil: un artículo de gTt-VIH de 2010 que habla de
la fase previa y no de la orden de 2015, y no se forzó ningún informe de Amnistía sobre 2014 —se
buscó y no existe—. Las dos que se conservan pese a no ser del todo directas (una nota de 2021 en
la orden de 2026, y un artículo de opinión de 2025 en la de 2019) **llevan la reserva escrita dentro
del propio campo `que_dice`**, para que quien revise la lea antes que el enlace.

#### Un hallazgo nuevo, y es de los silenciosos

La Orden SND/356/2026 —título: cribados prenatales, neonatales y de cáncer colorrectal— retoca de
paso el apartado `5.3.8.3.b)2.ºii)`, ovocitos donados, y ahí dice «la mujer **o persona transexual
que conserva la capacidad de gestar**». La reparación de 2021 modificó el subapartado hermano `i)`
—espermatozoides donados— y **no tocó el `ii)`**. Si el texto anterior no llevaba la fórmula, esto
es la reparación completándose cinco años después, dentro de una orden que habla de otra cosa.

**Comprobado en la misma sesión, y salió que no.** El texto anterior (`version_norma`, bloque
`A5-3`, que existe gracias al ADR 0018) decía ya literalmente «Edad de la mujer **o persona
transexual que conserva la capacidad de gestar**». Es continuidad, no extensión: no hay hallazgo.
Lo que sí cambia es otra cosa —desaparece «establecido antes de los 36 años» del fallo ovárico
prematuro—, que amplía el acceso de verdad pero no depende de la orientación ni de la identidad,
así que cae fuera de lo que este sistema publica. El informe se rehízo a `descartar` con las dos
redacciones citadas una al lado de otra.

**Esto es el campo `refutacion` funcionando tal y como se diseñó**, y conviene dejarlo escrito
porque es la primera vez que se ve: el informe traía «si el texto anterior ya lo incluía, esto es
descartar» como hipótesis alternativa, se comprobó, y la comprobación tumbó la recomendación del
propio asistente. Sin ese campo, la hipótesis bonita se habría quedado en pie por no llevarle nadie
la contraria.

#### La ingesta, y la prueba de que esto no es una demo

Sobrevivió al corte de cuota de las 20:40 sin que nadie la tocara: está desacoplada dentro del
contenedor y siguió sola. Va hacia atrás por meses (agosto→abril de 2026 hechos, ~1 mes/hora) y el
corpus está en **32.332 cuerpos archivados, de 2014 a hoy**. Para comparar: el ADR 0011 se decidió
midiendo sobre 436 normas.

Mientras se escribía todo esto **aparecieron dos ítems nuevos en la cola** (`BOE-A-2026-15302` y la
Ley 3/2026 de cribado neonatal), encontrados por el backfill en julio de 2026. El pipeline está
produciendo detecciones solo, sin que nadie lo lance.

#### Dos cosas que quedan dichas y no resueltas

1. **Los JSON de informes están en `.gitignore`** (línea 54, decisión explícita de una sesión
   anterior: «no son código ni archivo»). Es coherente con el ADR, pero cuestan una tanda de
   subagente y de búsqueda web, y son la única explicación de qué hay en `informe_revision`. Se
   intentó versionarlos y **se revirtió**: contradecía una decisión escrita, y eso lo decide una
   persona. Si se pierde `backend/data/`, se pierden.
2. **Ningún informe se ha aprobado.** La cola sigue con los nueve `pendiente`: el importador no
   resuelve nada y la regla de oro 4 sigue intacta.

#### Siguiente, por orden

1. **La superficie pública de hallazgos** (~20k): lista y feed, con su etiqueta y separada de las
   alertas. Ya hay dos hallazgos reales que enseñar, así que deja de ser trabajo a ciegas.
2. **Resolver la comprobación de la SND/356/2026** (~5k): leer el texto anterior del
   `5.3.8.3.b)2.ºii)`. Barato y puede convertir un `mirar` en el tercer hallazgo.
3. **Seguir la ingesta hacia atrás.** Tarea de fondo, se lanza y se deja.
4. **Gold set de 32 a 60-80 casos** (~20k).
5. **Las 172 ilegibles del DOGC por PDF** (~25k + ADR).
6. **La poda de `CLAUDE.md`**, en 63,5 KB con su límite en ~55. Lo decide una persona.

### ✅ La superficie pública de hallazgos existe, y el gate humano funcionó por primera vez — 2026-08-22

Cierra el ADR 0025: los hallazgos ya tienen su sitio en el producto, separado de las alertas.

#### El circuito completo, de punta a punta y con una persona dentro

La noche del 21, después de importar los siete informes, **el humano resolvió los nueve ítems de
la cola en once minutos**: cuatro aprobados y cinco descartados. Es la primera vez que el ciclo se
recorre entero —el pipeline detecta, el catálogo clasifica, un asistente prepara el dosier y
**decide una persona**— y conviene registrarlo porque es lo que el proyecto promete.

Efecto colateral que confundió al principio: `/api/hallazgos` devuelve `[]`, y es **correcto**. Un
hallazgo deja de serlo en cuanto alguien lo aprueba; pasa a `alerta` y a la otra pantalla. Hay un
test que lo exige (`test_aprobar_un_hallazgo_lo_saca_de_aqui`).

#### Dos signos publicados al revés, y cómo se corrigieron

De los cuatro aprobados, dos quedaron con el signo contrario al de su informe: la Orden
SSI/2065/2014 —la que **excluyó** a lesbianas, mujeres solas y personas trans de la RHA pública—
salió como `avance`, y la Orden SCB/480/2019 —que **crea** el cribado de cérvix— como `retroceso`.
Ya estaban servidos en `/api/alertas`.

**Causa probable, y es un hallazgo de producto:** los cuatro títulos aprobados esa noche son casi
idénticos («Orden …, por la que se modifican los anexos … del Real Decreto 1030/2006…») y en el
panel los radios «Avance» y «Retroceso» van pegados, con 12 px de separación. Nueve ítems en once
minutos. **El gate tiene que hacer el signo difícil de errar, no solo posible de fijar** — queda
como tarea.

Corregidos con autorización del humano en `backend/scripts/corregir_signos_20260822.sql`. Solo
toca `clasificacion_humana`: no reabre la cola (ADR 0017), no re-emite alertas, no toca
`deteccion.clasificacion`. **Va en un fichero con su porqué y no en un UPDATE suelto**, porque
cambiar en silencio un dato ya publicado es la desindexación sin registro que este proyecto
documenta para denunciarla.

#### Qué se publica de un hallazgo, y qué no

`GET /api/hallazgos` y su pantalla. Las tres condiciones viven **en el `where`** de
`services/hallazgos.consulta()` y no en un bucle: informe con semáforo `alerta`, sin fila en
`alerta`, y con al menos una corroboración. En el `where` no hay forma de pedir la lista sin
ellas, porque no existe una consulta sin ellas.

**La proyección pública del informe es más estrecha que la del panel, y esa es la decisión de
diseño de la tarea.** Salen `resumen`, `a_quien_afecta`, `citas`, `corroboraciones` y
`refutacion`. **No salen `recomendacion` ni `semaforo`**: son «yo publicaría esto», la opinión del
asistente, y la regla de oro 2 dice que el sistema nunca emite un juicio propio. Un hallazgo
afirma dos hechos verificables y ninguno nuestro —el cambio ocurrió, alguien lo denunció—, no un
veredicto. `revisado_por_humano` es un `Literal[False]`: no se puede poner a `True` sin que
Pydantic falle.

#### Lo que encontró el navegador y no habría encontrado ningún test

`formatearFecha` publicaba **«lo preparó un asistente de IA el NaN ago 2026»**. Recibía un
instante completo (`2026-08-21T20:50:00Z`) donde esperaba una fecha suelta, y su guarda comprobaba
que el día existiera pero no que fuera un número. Arreglado en la utilidad y no en la tarjeta,
porque el fallo era suyo y lo heredaba cualquier llamante. Es el argumento de 13.2 sobre verificar
en el navegador, otra vez.

#### Los dos tests rojos, que llevaban tiempo rojos

`test_el_historico_de_versiones_no_se_puede_alterar[UPDATE|DELETE]` fallaba **en la preparación**,
no en la comprobación: su `INSERT` es anterior al ADR 0018 y no tenía las columnas que se
volvieron obligatorias. O sea que **la inmutabilidad del archivo llevaba desde entonces sin
verificarse** — el trigger existía, pero su test no llegaba a ejecutarlo. Un control cuyo test no
lo alcanza no es un control comprobado. **678 tests en verde**, cero rojos.

#### La ingesta, que hoy se cayó dos veces y ninguna perdió datos

Se paró por suspensión del portátil (11,5 h) y luego por un cuelgue del motor de Docker. **Los
datos nunca estuvieron en riesgo** —cada documento se confirma en Postgres según se descarga, y el
volumen con nombre sobrevive a todo eso—, pero cada reinicio costaba ~5 horas repitiendo meses ya
hechos porque la lista vivía en la memoria del shell.

Ahora `backfill.sh` es **reanudable**: un fichero de marcas, una por bloque, escrita **solo si el
worker sale con 0**. Un bloque interrumpido se repite entero, que es barato por el `sha256` y es
lo único que evita huecos silenciosos. Probado: al relanzar saltó cinco meses en segundos.

Y dos causas arregladas fuera del código: la suspensión en batería estaba a 3 minutos (ahora
desactivada; apagar la **pantalla** es otro ajuste y no para nada, comprobado en el log), y
`backend` y `worker` ya llevan `restart: unless-stopped`. **Ojo con lo que eso no arregla**: el
backfill se lanza con `exec -d`, que no es el comando del contenedor, así que al reiniciarse
vuelve el contenedor pero no la ingesta. Hay que relanzarla a mano.

Corpus: **36.496 cuerpos archivados**, de 2014 a 2026.

#### Y un tercer fallo que encontro usar la web, no los tests

**El filtro de Alertas y la pantalla no hablaban de lo mismo.** El filtro preguntaba por
`deteccion.clasificacion` —el signo de la REGLA— y la tarjeta enseña `clasificacion_humana` cuando
existe. Como `R-MOD-001` deja las ordenes sanitarias en `indeterminado` y el signo se lo puso una
persona al aprobarlas, «Avances» devolvia **cero** y «Sin signo» devolvia seis, tres de ellas con
una tarjeta que pone «Avance». Ahora filtra por `coalesce(clasificacion_humana, clasificacion)`,
la misma precedencia que ya aplicaba `AlertCard`. Test de regresion que siembra el caso.

Los 679 tests pasaban con el filtro roto porque **ninguno cruzaba las dos columnas**. Junto con el
`NaN ago 2026`, son dos fallos en una sesion que solo aparecen al usar la web — 13.2, otra vez.

#### Las ocho alertas, ya con signo

Se fijo el signo humano de la **Ley 4/2023** y de la **Ley 19/2020**, que se aprobaron sin el y
salian como «sin signo». La primera es literalmente el caso que justifica que exista
`clasificacion_humana` —esta escrito en el docstring de `aprobar` desde que se implemento el
gate—: `R-DER-001` se abstiene a proposito porque derogar es lo que hace tanto quien desmonta una
ley como quien la sustituye por otra mejor, y solo leyendo el texto se sabe cual de las dos.

Queda **5 avances y 3 retrocesos, ninguna sin signo**, y el corpus publicado cuenta una historia
coherente: la exclusion de 2014 y su reparacion en 2021, el retroceso madrileño de 2023, y la Ley
4/2023 como avance. Script `fijar_signos_20260822b.sql`, con el mismo criterio que su hermano: no
reabre la cola, no re-emite alertas, no toca `deteccion.clasificacion`.

**Lo que esto vuelve a señalar** es la tarea 1 de abajo: el signo es opcional y facil de dejar en
blanco, ademas de facil de errar. Dos incidentes en dos dias sobre lo mismo.

#### El repositorio, al dia en GitHub

`main` y la rama del dia subidos a `github.com/papgar92/faro-cuir` (**publico**) el 2026-08-22,
tras seis dias sin push. Comprobado antes: `gitleaks` sobre 142 commits **sin filtraciones**,
`.env` nunca commiteado, ningun fichero con pinta de credencial. La rama va **sin mergear**: eso
lo decide una persona (13.3).

#### Siguiente, por orden

1. **Que el signo sea difícil de errar en el panel** (~10k). Lo pide el incidente de arriba:
   separar «Avance» y «Retroceso», y enseñar el identificador de la norma junto al selector.
2. **Gold set de 32 a 60-80 casos** (~20k). Ahora hay corpus de sobra contra el que medir.
3. **Las 172 ilegibles del DOGC por PDF** (~25k + ADR).
4. **Feed Atom de hallazgos**, si se decide que lo tenga: hoy solo hay lista y pantalla.
5. **La poda de `CLAUDE.md`**, en 63,5 KB con su límite en ~55. Lo decide una persona.

### ✅ El mapa deja de ser una mancha gris, y lo estatal deja de ser una disculpa — 2026-08-22

Pedido por el humano: «hay que pintar mucho más el mapa» y «las normas estatales, ahí arriba solas,
no representan si estamos en avance o retroceso». Su idea: un mapita de España. Se saco un agente
de diseño a explorar y **la descarto con un argumento que se sostiene**, asi que no se hizo.

#### Por que no hay una silueta de España coloreada

Colorear una silueta obliga a resumir todas las alertas estatales en **un** color. Con 4 avances y
1 retroceso hay que elegir uno, y la regla `GRAVEDAD` que ya existe en `lib/mapa.ts` elegiria
`retroceso`: la pantalla afirmaria «España: retroceso» teniendo el 80 % de sus alertas en avance.
Un veredicto nacional que ninguna regla emitio y que nadie aprobo — regla de oro 2 — y encima en el
pixel mas visible. **Si se quiere la silueta, la version que si vale es en contorno y sin rellenar**,
como rotulo; queda anotado por si el humano la pide.

#### Lo que si se hizo: una marca por alerta

`PanelEstatal` con **pictograma unitario**: un cuadrado por alerta aprobada, agrupados por signo.
No es un porcentaje ni una barra apilada ni una media — cada marca es una alerta concreta que una
persona reviso. Da color real sin agregar nada y escala sin rediseño. Y el copy se invirtio: **el
dato primero, el metodo despues y mas pequeño**. Antes el 62 % de lo que el sistema ha llegado a
afirmar se presentaba empezando por por que el mapa no puede pintarlo.

#### La ausencia, como informacion y no como hueco

Las quince comunidades sin vigilar se pintaban todas con la misma trama, y **no son iguales**:
Andalucia tiene 8 boletines provinciales conocidos sin integrar y La Rioja 1. Ahora hay **tres
densidades** por deuda de cobertura (`deudaCobertura`), con su leyenda y con la cifra tambien en la
etiqueta accesible — una informacion que solo existe en el color no existe para quien no lo ve.

Ojo con que variable es esa, porque es la unica que aqui se puede graduar sin mentir: **no habla del
territorio ni de sus derechos, habla de nosotros**. Un heatmap de «actividad» estaba descartado por
lo mismo: Catalunya saldria caliente por tener DOGC integrado y Galicia fria por no tenerlo, o sea
pintando nuestro esfuerzo como si fuera la realidad de la gente.

Y `CoberturaTotal` en el `aside`: 45 marcas, 2 encendidas. Ese numero vivia en un pie, en tamaño de
nota al margen, y es el que explica la pantalla entera. **Verificado en claro y en oscuro**: el
riesgo que aviso el agente —que el paso intermedio de la trama fuera indistinguible en oscuro— no
se materializa; en oscuro se separan incluso mejor.

#### Dos fallos encontrados de paso

1. **El mapa coloreaba con el signo de la REGLA, no con el que se ve.** Catalunya salia como «sin
   signo» (naranja) mientras su tarjeta ponia «Avance». Es el mismo fallo que el del filtro de
   Alertas, en la tercera superficie del mismo dato. Ahora hay `signoVisible()` exportada y usada
   por el mapa; la precedencia queda escrita en un sitio.
2. **«17 donde aun no hay ninguna fuente integrada»** era aritmeticamente correcto —19 territorios
   menos Madrid y Catalunya— pero se leia como «ninguna de las 17 comunidades», con la cabecera
   diciendo «17 CCAA + BOE» justo encima. Catalunya si esta vigilada. Ahora dice **«17 de los 19
   territorios del mapa»**. Un numero correcto que se lee al reves es un numero mal publicado, y
   esta pantalla mide precisamente huecos de cobertura.

Sin cambios de backend: `MapaPage` ya pedia alertas y cobertura, asi que todo el agregado nacional
se calcula en cliente con lo que ya tenia.

### 🔭 Referencias visuales investigadas (ILGA, TGEU, HRC, Civio, OWID) — 2026-08-22

Un agente de diseño investigó cómo se presentan ILGA-Europe (Rainbow Map y ficha de país), TGEU,
el HRC Accountability Tracker, HRW, FELGTBI+, Civio y Our World in Data. **Aplicado hoy solo lo
barato**; el resto queda aquí con su coste porque es material bueno y no conviene perderlo.

#### Aplicado

- **Emisor y rango en la tarjeta de alerta.** `organo_emisor` ya viajaba en la respuesta y no se
  pintaba en ningún sitio. Para una herramienta cuyo manifiesto dice que el retroceso llega en «una
  instrucción que no firma nadie con nombre conocido», el emisor es media noticia: no es lo mismo
  una ley de un parlamento que una orden de una consejería. Un `null` se dice, no se deja en hueco.
- **Las tres anclas muertas del pie** (`#repo`, `#metodologia`, `#datos`) apuntan ya al repositorio,
  a `docs/adr/` y a `/api/alertas`. En un proyecto cuya tesis es «no te fíes, compruébalo», un
  enlace que no lleva a ningún sitio no es maquetación pendiente: es un agujero en el argumento.

#### Pendiente, por orden de impacto/esfuerzo

1. **El catálogo de reglas, legible** (~media tarde). Hoy la tarjeta imprime `regla R-MOD-001` y
   **no hay ningún sitio donde leer qué dice esa regla**. Eso contradice literalmente la sección
   7.6: «una alerta publicada tiene que poder reconstruirla un tercero leyendo la regla y el texto
   archivado, sin ejecutar nuestro código» — hoy el tercero no tiene la regla. Un `<details>` con
   el enunciado, más una pantalla de Metodología con el catálogo entero (`lib/reglas.ts` derivado
   de `pipeline/reglas.py`, citando versión). **Es el que más peso tiene ante el tribunal.**
2. **Fecha de última lectura por fuente** (~media tarde, necesita campo de backend). «Vigilada, sin
   alertas» no está fechada, y sin fecha no es una medición sino una promesa. Añadir
   `ultima_lectura` a `CoberturaCcaa` y pintarla en `RegionDetailPanel` y `CoberturaTotal`, con
   aviso en `alr` si la fuente lleva días sin entregar. **No simularlo en cliente**: derivar la
   frescura del documento global afirmaría por Andalucía algo medido en el BOE.
3. **Bloque «Descargar y citar»** (~1-2 h). Endpoints reales y una cadena de cita con la huella,
   al estilo de Our World in Data. Reutilizable en Archivo y Ficha.
4. **Ficha de comunidad enlazable** (~1 día). `RegionDetailPanel` vive en estado de hover y no
   tiene URL, así que «mándame el enlace de Andalucía» —la acción de compartir número uno de un
   observatorio— hoy no se puede hacer. Bastaría `?ccaa=AN` sin meter un router.

#### Qué NO copiar, y esto vale tanto como lo anterior

- **El índice compuesto 0-100 % de ILGA.** Un porcentaje sobre 2 fuentes de 45 declara una
  cobertura que no existe. Las 45 marcas de `CoberturaTotal` ya lo resuelven mejor.
- **El semáforo aplicado al territorio.** ILGA puede pintar un país entero porque puntúa 75
  criterios estables; aquí se clasifican **cambios**, no estados. Pintar una comunidad de verde por
  una alerta de avance diría algo de su marco jurídico que el pipeline no ha medido.
- **La serie temporal tipo «Country Score Evolution».** Con el volumen de hoy dibujaría la
  actividad del ingestor y se leería como la de la administración.
- **El registro de campaña de FELGTBI+** (banners, fotos, arcoíris de fondo) y **el tono editorial
  del HRC** («Breaking: After Massive Outrage…»), que mezcla hecho y valoración en el titular.
- **Los descargables «listos para redes»**: una imagen se comparte descontextualizada y sin huella.

#### Paleta y tipografía: no se tocan

El agente las revisó expresamente y concluyó que en dos puntos **son mejores que las referencias**:
la regla «nunca solo color, siempre glifo + texto» resuelve la accesibilidad del semáforo que ILGA
no resuelve, y que `indeterminado` se pinte en `alr` y no en `reg` es una distinción que ninguna de
las referencias hace. Se conservan.

Queda anotado en el propio `AlertCard` por qué el título va en `font-sans` y no en `font-serif`: la
serif es la voz del proyecto y ese titular no es suya, es la del Estado.

### ✅ El catálogo de reglas se puede leer, y la cobertura dice hasta cuándo llega — 2026-08-22 (tarde)

Dos de las cuatro propuestas de diseño que quedaban, y la segunda ha destapado un hueco real.

#### El catálogo de reglas, publicado (7.6 deja de estar incumplida)

`CLAUDE.md` 7.6 exige que «una alerta publicada tiene que poder reconstruirla un tercero leyendo la
regla y el texto archivado, **sin ejecutar nuestro código**». Hasta hoy ese tercero tenía el texto,
los offsets y la huella — y **no tenía la regla**: la tarjeta imprimía `R-MOD-001` y no había dónde
leer qué dice. La exigencia estaba escrita y no se cumplía.

`frontend/src/lib/reglas.ts` publica las cinco reglas **en orden de evaluación** —que es
información y no presentación: el catálogo devuelve el primer veredicto que encaja, así que
R-SUP-001 tapa a R-MOD-001 en una norma que hace las dos cosas— con su enunciado, la evidencia que
exige y **qué signo emite**. Ese último campo es obligatorio en las cinco porque tres se abstienen:
sin decirlo, un `indeterminado` se lee como «no supo» cuando lo que pasa es que la regla **decidió
no afirmar**, y esa diferencia es medio proyecto.

Se pinta en un `<details>` cerrado y **después de la evidencia**, nunca antes: quien lee tiene que
toparse primero con la cita literal de la norma y solo después con nuestro criterio. Mismo orden y
mismo motivo que el informe de apoyo del ADR 0025.

**Lo que hace fiable al glosario es su test.** `test_catalogo_publicado.py` comprueba que la
versión publicada es `VERSION_REGLAS` y que están todas las reglas y ninguna de más. Un glosario
que se queda atrás es peor que no tenerlo, porque explica mal con aire de autoridad. Verificado que
el control **falla de verdad**: con la versión desfasada a mano, el test se pone rojo.

Detalle de montaje: el contenedor de backend no veía el frontend, así que el test se saltaba en
local y solo corría en CI — un control que se descubre roto con el commit ya hecho. Se monta
`./frontend:/frontend:ro` solo para eso; ningún código de producción lee de ahí.

#### La cobertura dice hasta cuándo llega, y lo primero que ha dicho es incómodo

`CoberturaCcaa.ultima_publicacion`: la fecha del boletín **más reciente** archivado de cada
comunidad. Es la fecha de publicación y no el sello de nuestra ingesta, a propósito — el sello dice
cuándo corrió el worker, que puede ser esta mañana aunque el último boletín sea de hace un año.

**Y al existir ha destapado esto:**

| fuente | sumarios | cobertura real |
|---|---|---|
| BOE | 211 | 2014-11-06 → **2026-08-21** (ayer) |
| DOGC | 142 | 2024-01-02 → **2024-12-31** |

El DOGC se ingirió como una **tanda histórica de 2024 y nunca se puso al día**. Llevamos veinte
meses sin leer nada de Catalunya, y el mapa la pintaba como «vigilada» todo este tiempo — que se
lee como «esto lo estamos mirando». Es exactamente la diferencia entre promesa y medición que
motivaba el campo, encontrada en nuestra propia casa a los cinco minutos de publicarlo.

La interfaz ya lo dice, con umbral de 30 días y en color de aviso (no de retroceso: que no hayamos
leído no dice nada del territorio, dice algo de nosotros).

**Consecuencia para el plan: poner al día el DOGC vale más que integrar una fuente nueva.** Una
fuente vigilada y desactualizada es peor que una no vigilada, porque la interfaz promete algo que
no está pasando. Va por delante de Andalucía o Galicia en la lista.

### ✅ Las cinco propuestas de diseño, cerradas — 2026-08-22 (tarde, cont.)

#### Datos y cita, en la propia vista

`DatosYCita` al pie de Alertas y de Hallazgos, con los endpoints **reales** y una cadena de cita
que **lleva el `sha256` dentro**. No es adorno: citar «Faro Cuir, alerta 12» no sirve de nada
dentro de cinco años, pero con la huella cualquiera puede comprobar que el documento citado es el
mismo aunque para entonces la administración lo haya retirado de su web — que es literalmente el
daño que este proyecto existe para documentar (6.5).

En Hallazgos **no se ofrece Atom**, porque los hallazgos todavía no tienen feed. Anunciar un
endpoint que no existe sería el mismo fallo que las tres anclas muertas del pie.

#### Todo tiene URL, que era un agujero más grande que el que señalaba el agente

El agente pedía que la ficha de comunidad fuera enlazable. Al mirarlo, resultó que **ninguna
pantalla tenía URL**: todo el estado vivía en `useState`, así que la raíz llevaba siempre al mapa
y no había forma de enlazar nada. Para un observatorio eso no es comodidad — «mándame el enlace de
Andalucía» o «mira esta alerta» es la acción de compartir principal, y es la que convierte una
consulta en una cita.

`?pantalla=hallazgos` y `?ccaa=CT`, con `URLSearchParams` y `replaceState`. **Sin router**: son
seis pantallas y un parámetro, y meter `react-router` para esto sería una capa más que auditar
(sección 3). Dos decisiones que no son obvias:

- **Se escribe la comunidad FIJADA, no la del ratón.** `?ccaa=CT` tiene que significar «alguien
  eligió Catalunya», no «el cursor pasó por encima».
- **`replaceState` y no `pushState`**, por lo mismo: empujar una entrada de historial por cada
  hover deja el botón «atrás» inservible.

Verificado en el navegador: `?pantalla=hallazgos` aterriza en Hallazgos y `?ccaa=CT` abre la ficha
de Catalunya.

#### Preparado y NO lanzado: la puesta al día del DOGC

`backend/backfill-dogc.sh`, reanudable como el del BOE pero **hacia adelante**: lo que falta ahí no
es historia, es actualidad. Queda sin lanzar a la espera de que lo decida el humano, porque es
tráfico saliente sostenido contra un tercero durante horas.

Y va escrito en el propio script lo que **no** arregla: se espera que buena parte de lo que entre
quede `ilegible`, porque el DOGC publica mucho solo en PDF y el pipeline aún no lo lee (172 de 264
en la tanda de 2024, el 65 %). Ponerlo al día resuelve «llevamos veinte meses sin mirar»; no
resuelve «de lo que miramos, dos tercios no se pueden analizar». Eso es el lector de PDF.

### ✅ Las ilegibles del DOGC se recuperan por PDF, y no hizo falta OCR (ADR 0026) — 2026-08-22

El hueco que llevaba abierto desde el ADR 0020 —172 normas del DOGC, el 65 % de esa fuente, con su
cuerpo archivado y **sin que el pipeline pudiera leerlo**— se cierra. Al empezar eran ya 235,
porque la puesta al día de la fuente las multiplicaba.

#### Lo que faltaba no era OCR, y se comprobó antes de decidir

El humano pidió levantar la prohibición de OCR de la sección 8. Antes de tocar la regla se midió un
PDF real del DOGC: **59 referencias de fuente, 18 bloques de texto, cero imágenes**. Es un PDF
digital con capa de texto, y extraerla da **8.295 caracteres limpios de un fichero de 795 KB**,
empezando por «DISPOSICIONES GENERALES / DEPARTAMENTO DE LA PRESIDENCIA / ORDEN PRE/292/2023…».

La prohibición se levantó igualmente —es decisión suya— pero escrita como regla razonada: el OCR es
**el último recurso y no el primero**, y antes de escribir una línea hay que demostrar con un
documento real que su PDF no tiene capa de texto. Lo que la sección 8 protege no es la técnica, es
el plazo.

#### `security/pdf_safe.py`, hermano de `xml_safe`

Puerta única —ningún módulo importa `pypdf`, con test que lo comprueba— y **tres topes porque son
tres ataques distintos**: bytes (lo que no se lee no hace daño), páginas (300 KB que declaran cien
mil) y caracteres de salida (bomba de expansión, el equivalente de las entidades del XML). Al
pasarse cualquiera, excepción y **ni un carácter devuelto**: medio documento archivado como entero
haría que el prefiltro dijera «aquí no hay nada» sobre un texto que nadie ha visto completo.

`RecursionError` capturada explícitamente: un PDF con referencias circulares la provoca y sin eso
se lleva al worker por delante.

`SinCapaDeTexto` es un tipo aparte de `MalformedPdf`, y esa distinción **es la cifra que decidirá
si el OCR llega a hacer falta**: «no se puede leer» y «se lee y no tiene letras» son cosas
distintas, y solo la segunda lo justificaría. Se publica en el log aunque valga cero. Hoy vale
**cero**.

#### Cómo se recupera, sin tocar el archivo

`worker.run --recuperar-pdf`. **No sustituye nada**: archiva el PDF como documento nuevo con su
huella y su sello, sufijo `#pdf`, y reapunta la norma. Lo que se descargó aquel día —aunque fuera
la página de error del portal— sigue estando, porque es un hecho sobre la fuente y merece
conservarse (6.5).

Y `cuerpo.leer_cuerpo` decide el formato **por los cinco primeros bytes**, nunca por la extensión
ni por la fuente: un PDF archivado con nombre `.xml` sigue siendo un PDF, y fiarse del nombre de un
fichero externo es el mismo error que 6.3 prohíbe para las rutas.

#### Resultado en caliente

Primera prueba: **3 intentadas → 3 recuperadas, 0 sin capa de texto, 0 fallidas**, y el prefiltro
las evaluó acto seguido sobre el texto real. La pasada completa está corriendo: las ilegibles bajan
de 235 a 212 y siguen.

Los `DtdForbidden` que aparecen en el log **no son un fallo**: son las ilegibles todavía sin
recuperar, cuyo cuerpo sigue siendo la página de error HTML. `xml_safe` las rechaza como debe.

#### Lo que esto no arregla

Las normas cuyo PDF sea de verdad un escaneo. Hoy son cero. Si algún día no lo son, el número
estará en el log y el OCR tendrá con qué justificarse en su propio ADR — que es exactamente la
diferencia entre decidir con datos y decidir por intuición.

### ⇨ CÓMO RETOMAR ESTO — escrito el 2026-08-22 al cierre

**Hay tres procesos de fondo corriendo dentro del contenedor.** Ninguno se relanza solo si el
contenedor se recrea (se lanzan con `exec -d`, que no es el comando del contenedor). Si al volver
los ves parados, esto los revive y todos saltan en segundos lo ya hecho:

```bash
docker compose exec -d worker sh //app/backfill.sh          # BOE hacia atras (quedan ~4 bloques)
docker compose exec -d worker sh //app/backfill-dogc.sh     # DOGC hacia adelante, hasta hoy
docker compose exec -d worker sh -c "FASE2_MAX_POR_EJECUCION=400 python -m worker.run --recuperar-pdf > //app/data/recuperacion-pdf.log 2>&1"
```

**Comprobar que siguen vivos**, que es lo primero que hay que mirar:

```bash
docker compose exec -T worker sh -c 'for p in /proc/[0-9]*; do [ -r $p/cmdline ] || continue; tr " " " " < $p/cmdline | grep -E "worker.run|backfill" ; done'
```

#### Lo que va a pasar solo, y no es un fallo

- **Las ilegibles siguen bajando** (235 → 96 al cierre). Cada una recuperada vuelve al prefiltro y
  se evalúa **sobre su texto real por primera vez**, así que van a aparecer detecciones nuevas y
  la cola de revisión va a crecer. Eso es el sistema funcionando, y quien las revise es una
  persona.
- **Catalunya seguirá con el aviso de «desactualizada»** hasta que el backfill del DOGC alcance el
  presente. El umbral son 30 días y va en color de aviso. Que el aviso desaparezca solo es
  exactamente lo que tiene que hacer un indicador honesto.

#### Lo que queda, por orden de valor

1. **Revisar la cola** cuando las recuperaciones terminen de poblarla. Es trabajo humano y es el
   cuello de botella del proyecto, no el código.
2. **Que el signo sea difícil de errar en el panel** (~10k). Dos incidentes en dos días sobre el
   mismo campo: signos invertidos el 21 y signos sin poner el 22. Separar los radios
   Avance/Retroceso, enseñar el identificador de la norma junto al selector, y **avisar al aprobar
   cuando la regla se abstiene y no se ha fijado signo** — que es justo donde el sistema depende de
   que la persona complete lo que la regla no puede.
3. **Gold set de 32 a 60-80 casos** (~20k). Ahora hay 55.000 normas de corpus contra las que medir,
   y con el DOGC legible por fin hay material de esa fuente que antes no se podía etiquetar.
4. **La poda de `CLAUDE.md`**, que ha vuelto a crecer con los ADR 0026 y la regla nueva de PDF.
   Sigue por encima del límite de ~55 KB y **lo decide una persona**.
5. **Fuentes nuevas**, con el aviso de siempre: la sección 8 las capa en 5 y vamos por 2. Y con la
   lección del DOGC delante — una fuente vigilada y desactualizada es peor que una no vigilada.

### ✅ El panel deja de facilitar el error, y los hallazgos tienen feed — 2026-08-22 (cierre)

#### El selector de signo, rehecho contra dos incidentes reales

No es una mejora estética: es la causa de los dos fallos de esta semana. El 21 se aprobaron cuatro
ítems en once minutos y **dos salieron con el signo invertido** —la orden de 2014 que excluyó a
lesbianas y personas trans de la RHA publicada como «avance», la de 2019 que crea el cribado de
cérvix como «retroceso»—. El 22 aparecieron otros dos **sin signo** siendo avances, la Ley 4/2023
entre ellos.

Las dos causas estaban en ese cuadro y hay una corrección para cada una:

1. **El identificador de la norma va DENTRO del selector.** Los cuatro títulos de aquella noche
   eran casi idénticos («Orden …, por la que se modifican los anexos … del RD 1030/2006…»): el de
   2014 y el de 2021 se distinguen por cuatro caracteres. Ahora se ve de qué norma se está
   eligiendo el signo sin levantar la vista.
2. **«Avance» y «Retroceso» dejan de ser dos radios pegados** a 12 px. Son botones separados con
   su color, su glifo y su texto — el criterio de `ClassificationBadge`: nunca solo color.
3. **Aviso cuando la regla se abstiene y no se ha fijado signo.** Solo en ese caso, que es donde el
   sistema depende de que la persona complete lo que la regla no puede sostener.

Sigue siendo **opcional** a propósito: obligar empujaría a inventarse un signo, y «sin signo» es
una respuesta legítima y a veces la única honesta.

**No verificado visualmente**: el panel está tras autenticación y la sesión no tenía la
credencial. Typecheck y CI en verde, pero conviene mirarlo con los ojos al abrirlo.

#### Feed Atom de hallazgos, separado del de alertas

`GET /api/hallazgos.xml`. **Feed aparte y no un parámetro**, porque afirman cosas distintas: quien
se suscribe a las alertas recibe lo que una persona revisó; quien se suscribe aquí recibe cambios
que **nadie ha mirado**.

Y el aviso va **en el título de cada entrada** (`SIN REVISAR · …`), no en una categoría. Un feed se
lee en un agregador: colores, categorías y etiquetas se pierden por el camino, y lo único que
sobrevive a cualquier lector es el título. Hay un test que lo fija y comprueba el título, no la
categoría — la categoría es un extra, el título es el control.

El contenido de cada entrada lleva las dos cosas que hacen publicable un hallazgo (ADR 0025,
decisión 4): el resumen y **quién lo ha documentado ya**. Sin la segunda esto sería la opinión de
un modelo publicada en un canal.

#### La recuperación por PDF, terminada

**De 235 ilegibles a 9.** El 96 % del hueco que llevaba abierto desde el ADR 0020, cerrado, y con
`sin_texto = 0`: ni un solo PDF del corpus necesitaba OCR.

**Y el efecto sobre la vigilancia real, que es lo que importaba:** el DOGC pasa de tener dos
tercios ciegos a **3 relevantes y 19 sospechas** evaluadas sobre su texto de verdad. Antes esas
normas estaban descargadas, selladas y sin que nadie pudiera leerlas.

**La recuperación hay que relanzarla mientras el DOGC siga ingiriendo.** Las ilegibles bajaron a 9
y volvieron a 12 en minutos: no es que fallara nada, es que el backfill del DOGC trae normas nuevas
—muchas en PDF— más rápido de lo que una pasada con tope de 400 las procesa. **Mientras esa ingesta
corra, `--recuperar-pdf` hay que volver a lanzarlo cada cierto tiempo**, y cuando termine, una
última vez. Es idempotente: lo ya recuperado no lo vuelve a tocar.

Vale la pena plantearse encadenarlo al final de `backfill-dogc.sh`, que es donde naturalmente
pertenece; no se hizo aquí para no tocar un script que estaba corriendo.

**Lo siguiente que hay que lanzar, y no está hecho:** `python -m worker.run --reclasificar`. El
catálogo de reglas todavía no ha pasado por las recuperadas —hay 45 detecciones y la cola sigue
con las 26 resueltas de ayer—, así que las detecciones nuevas del DOGC aparecerán al reclasificar.
No se lanzó aquí para no cruzarlo con los tres procesos de fondo que ya estaban corriendo.

### 📊 El prefiltro medido a escala real: reduce el coste del LLM 111 veces — 2026-08-23

Con 436 normas cualquier porcentaje era ruido y estaba dicho así en el ADR 0011. Con **66.660
normas con cuerpo archivado**, el embudo ya se puede medir:

| | |
|---|---|
| Normas con texto íntegro archivado | **66.660** |
| Pasan a la cola del LLM | **600 (0,90 %)** |
| Ilegibles | 89 (0,13 %) |

> **⚠️ CORRECCIÓN del mismo día — ese 0,90 % está diluido y no se debe volver a publicar solo.**
> El **61 % del corpus son anuncios** (`BOE-B-*`: licitaciones, edictos, nombramientos), que no son
> normativa. Separado por tipo de documento:
>
> | | normas | pasan | % |
> |---|---|---|---|
> | Anuncios (`BOE-B`) | 40.945 | 13 | **0,032 %** |
> | Disposiciones | 26.302 | 592 | **2,25 %** |
>
> **El número honesto sobre normativa de verdad es 2,25 %**, no 0,90 %. El factor de reducción del
> coste del LLM no cambia —se calcula sobre lo que hay que procesar, y hay que procesarlo todo—
> pero cualquier afirmación sobre *selectividad del prefiltro* tiene que ir sobre disposiciones.
>
> **Los 13 anuncios que pasan son todos `sospecha`, ninguno `relevante`**, y cinco son licitaciones
> de la Confederación Hidrográfica del Ebro. Es ruido, pero barato: 13 ítems de baja prioridad en
> una cola de 600.
>
> **Aun así NO se propone excluir `BOE-B` de la ingesta.** Los edictos judiciales de rectificación
> registral se publican ahí, y ese es justo el trámite que le importa a una persona trans. Un
> rendimiento del 0,03 % no autoriza a dejar de mirar el sitio donde vive el caso individual.

**Traducido a lo que cuesta**, que es donde el número significa algo. A 133,9 s por extracción
(medido en el ADR 0011, en esta máquina):

- Sin prefiltro: 66.660 × 133,9 s = **2.479 horas = 103 días** de CPU.
- Con prefiltro: 600 × 133,9 s = **22,3 horas**.
- **Factor de reducción: 111×.**

Ese es el número que justifica el prefiltro entero y que hasta hoy no se podía calcular. Y explica
por qué el ADR 0011 movió el prefiltro de ser «la puerta de la red» a ser «la puerta del LLM»: la
red cuesta 4,3 MB por día de BOE, el LLM cuesta 103 días.

**Cuidado con leerlo como recall.** Esto mide cuánto **filtra**, no cuánto **acierta**. Que pase el
0,9 % no dice nada sobre si lo que se queda fuera debía quedarse fuera; eso solo lo puede decir el
gold set, que sigue en 32 casos. No publicar este número junto a una afirmación de cobertura.

#### El eje referencial se gana su sitio, con nombre y apellidos

**2 de las 164 relevantes entraron sin un solo término del vocabulario**, o sea solo por el eje
referencial: una resolución de la **Mutualidad General Judicial** y otra de la **Dirección General
de Trabajo**, las dos modificando una norma vigilada sin nombrar nada del ámbito.

Es literalmente el caso que el ADR 0012 describía para justificar ese eje: «una instrucción que
elimina un derecho no dice *identidad de género*, dice *se modifica el epígrafe 4.3 del anexo II*».
Dos de 164 parece poco hasta que se recuerda que son dos normas que el diccionario **no habría
visto jamás**.

#### El trabajo del PDF, medido por su efecto

El DOGC aporta ahora **30 relevantes y 52 sospechas**. Antes de recuperar los PDF tenía **3**. El
lector de PDF no arregló una estadística de cobertura: multiplicó por diez la señal aprovechable de
esa fuente.

### ⚠️ El corpus creció 150 veces y la cola de revisión no creció nada — 2026-08-23

Medido tras reclasificar sobre las 66.660 normas archivadas. **El cuello de botella ya no son los
datos: son las reglas.**

| etapa | cantidad | |
|---|---|---|
| Normas con texto íntegro archivado | 66.660 | |
| Pasan el prefiltro | 600 | 0,90 % |
| **Producen veredicto** | **46** | **7,7 % de las 600** |
| Señalan una norma vigilada (llegan al gate) | 17 | |
| En cola de revisión | 27 | **todas ya resueltas** |

**Cero ítems nuevos.** Se ha pasado de 436 normas a 66.660 y el sistema encuentra lo mismo.

#### Por qué, y no es el prefiltro

El reparto por regla lo dice todo:

| regla | detecciones | señalan norma vigilada |
|---|---|---|
| `R-SUP-002` (supresión sin norma vigilada) | 29 | **0** |
| `R-MOD-001` (modificación de norma vigilada) | 13 | 13 |
| `R-SUP-001` (supresión de norma vigilada) | **2** | 2 |
| `R-DER-001` (derogación) | 2 | 2 |

El catálogo solo sabe buscar cuatro cosas, y **tres son variantes de supresión**. `R-SUP-001`, que
es la única regla que afirma `retroceso`, ha disparado **dos veces en 66.660 normas**. Y las 29 de
`R-SUP-002` no llegan al gate por diseño (ADR 0017, con datos: iba 10 de 10 descartada).

**El prefiltro no es el problema**: deja pasar 600 y de esas solo 46 tienen algo que una regla
sepa reconocer. El embudo se estrecha en el catálogo, no antes.

#### Lo que esto cambia en el plan

Añadir más fuentes o más corpus **no va a producir más hallazgos** mientras el catálogo tenga cinco
reglas. Lo que hace falta son **familias de reglas nuevas**, y para eso hace falta saber qué
mecanismos jurídicos de retroceso existen que estas cuatro no ven — que es conocimiento de dominio
y no de ingeniería.

Hay un encargo lanzado al `jurista-lgtbi` justo sobre eso: los puntos ciegos del filtro, ordenados
por lo invisible que es cada mecanismo, con la señal textual que delataría a cada uno y qué le
falta a la watchlist de 24 normas. **Sin etiquetar nada** (13.4): diseña el examen, no lo responde.

#### El aviso de método

Que la cola no crezca **no significa que no haya retrocesos ahí fuera**. Significa que este
catálogo no los ve. Es exactamente el falso negativo de 7.1: invisible, sin métrica que lo delate,
y el fallo total del sistema. Que se haya hecho visible al medir a escala es justamente el valor de
haber ingerido el corpus.

### 🔭 Los puntos ciegos del prefiltro, por el `jurista-lgtbi` — 2026-08-23

Encargo de **diseño del filtro, no de etiquetado** (13.4 se lo prohíbe: si pone las etiquetas del
examen que ayuda a diseñar, el sistema se mide contra sí mismo). La pregunta fue la que nadie había
hecho: no qué encuentra el filtro, sino **qué es estructuralmente incapaz de ver** — el falso
negativo de 7.1, que no aparece en ninguna métrica.

#### La asimetría, que es el hallazgo central

> **El filtro ve mejor el retroceso parcial —el que todavía nombra lo que recorta— que el
> completo, que lo borra. Cuanto más limpio es el trabajo del redactor, más invisible es.**

El eje léxico detecta **presencia** de vocabulario, y un retroceso consumado produce por definición
un documento donde ese vocabulario **ya no está**. Explica lo medido esta misma mañana: 66.660
normas y cero trabajo nuevo para el gate.

#### La distinción que faltaba: filtro vs canal

- **Punto ciego de filtro**: está archivado y el filtro no lo levanta. Se arregla con vocabulario o
  reglas.
- **Punto ciego de canal**: no llega nunca al archivo. **Ningún ajuste del vocabulario lo arregla.**

Y el mecanismo más silencioso de todos **no tiene señal textual ninguna**: no convocar la subvención
de este año, no renovar el convenio, dejar caducar el plan. No hay acto, no hay norma, no hay diff.
Es el más frecuente en el nivel local — el que el ADR 0014 dice que justifica el proyecto. Detectarlo
exigiría un **vigilante de periodicidad** sobre el archivo, que es otro servicio y no un prefiltro.

#### Diez mecanismos, ordenados por invisibilidad

| | mecanismo | tipo | ¿señal textual? |
|---|---|---|---|
| M-1 | No convocar / no renovar / dejar caducar | canal | **ninguna** |
| M-2 | Partida presupuestaria a cero o programa que desaparece | filtro | solo si el programa conserva el nombre |
| M-3 | Bases de subvención: requisito que excluye sin nombrar | filtro + canal (BOP) | **por ausencia** |
| M-4 | Criterio de acceso por **sexo registral** | filtro | **sí, y buena** |
| M-5 | Supresión de órgano por decreto de estructura | filtro | parcial, depende del nombre |
| M-6 | Instrucciones y protocolos que no se publican | canal | el vocabulario funciona; el documento no llega |
| M-7 | Currículo: contenido que desaparece de un listado | filtro | por ausencia |
| M-8 | Deslegalización (`reglamentariamente se determinará`) | filtro | sí, **pero para 7.6, no para el léxico** |
| M-9 | `deberá` → `podrá` | clasificador | tratable con el diff del ADR 0018 |
| M-10 | Conciertos, convenios y pliegos | canal | fuera de alcance (sección 8) |

**M-8 no se propone para el eje léxico y el motivo importa**: «se faculta a», «reglamentariamente
se determinará» aparecen en casi toda norma con rango de ley. Como término suelto serían el nuevo
«igualdad de trato». Su sitio es el catálogo de 7.6, exigidas **pegadas a la evidencia que nombra la
norma vigilada**, que es el criterio del ADR 0023. Vino con regla candidata esbozada
(`R-DES-001-remision-reglamentaria`, sentido `indeterminado`).

#### El problema de formato que hay que resolver ANTES de etiquetar en masa

M-2, M-3 y M-7 se caracterizan **por ausencia**: solo existen comparando con el documento anterior
de la serie. El esquema del gold set es un JSON por documento suelto, así que **un caso de ausencia
no es representable** — hoy el gold set no puede contener ni un caso del tipo de retroceso que este
informe señala como el más silencioso.

Hay que decidir antes de la tanda grande: o admite **casos-par** (documento N y N-1), o se acepta
por escrito que esos mecanismos quedan fuera de la medición. Las dos son legítimas; lo que no vale
es descubrirlo con 150 casos ya etiquetados.

#### Tres criterios de composición del gold set

- **Tasa base**: pasa el 0,90 %. Parte de los negativos debe salir de **muestreo aleatorio** y no de
  selección — «los negativos elegidos a mano miden lo que quien elige ya sospechaba».
- **Por fuente**: 21 BOE, 8 DOGC, **0 BOP**. Sin un documento provincial no se mide el nivel que
  justifica el proyecto.
- **Por rango**: si son todo leyes, se mide el filtro sobre lo que sale en prensa.

#### Lo que el informe NO dice, y lo dice él mismo

Que ninguno de esos mecanismos sea un retroceso: son formas jurídicas con usos legítimos. Lo que
afirma es dónde el filtro **no podría distinguirlo** — una afirmación sobre el sistema, no sobre las
normas.

Y no propone implementar nada sin medirlo: cada término y cada norma nueva tienen la misma prueba
pendiente, **contar sobre los 66.660 cuerpos ya archivados**, que no cuesta ni una petición de red.
Es lo que se está haciendo.

### 📏 Medidos los términos candidatos del jurista: no aportan **en este corpus** — 2026-08-23

Sobre **1.500 disposiciones descartadas** tomadas al azar (`scripts/medir_terminos_candidatos.py`,
sin una sola petición de red). El instrumento va **validado con controles**, y esto no es celo: las
dos primeras mediciones estaban mal y llevaban a la conclusión contraria.

| término | apariciones | rescataría |
|---|---|---|
| `articulo` (CONTROL) | 981 | — |
| `resolucion` (CONTROL) | 1.262 | — |
| `identidad de genero` (CONTROL) | **0** | — |
| `gay` | 2 | 2 |
| todos los demás candidatos | **0** | 0 |

**El tercer control merece una lectura**: `identidad de genero` da 0 y **eso es lo correcto**. Es un
término DIRECTO, así que ningún documento que lo contenga puede estar entre las descartadas. Es una
comprobación de coherencia del propio prefiltro, gratis.

#### Qué se concluye, y qué NO

**No se concluye que los términos sobren.** Se concluye que **en este corpus no aparecen**, que es
otra cosa. `sexo registral`, `sexo al nacer` o `alumnado trans` viven en normativa deportiva,
penitenciaria, de registro civil y educativa autonómica — tipos documentales de los que este corpus
(BOE + DOGC) tiene poco. Su frecuencia cero mide la composición del corpus tanto como el término.

**Coste medido de añadirlos: cero falsos positivos** en 1.500 disposiciones. Ese es el argumento
para añadirlos igualmente: no ensucian nada y cubren mecanismos que hoy nadie ve (M-4 del informe de
puntos ciegos). Lo que no se puede es **afirmar que mejoran el recall**, porque no hay con qué
demostrarlo.

#### Las dos mediciones malas, y por qué se cuentan

La primera dio **cero en todo** y estuvo a punto de cerrarse como «los términos del jurista no
aportan». Habría sido falso por dos motivos simultáneos:

1. **Sin controles positivos**, una tabla de ceros no distingue «no aportan» de «el script está
   roto». Ahora el script **se niega a dar resultados si los controles fallan**: avisa y sale con
   código 1. Un instrumento que no sabe decir cuándo está roto no sirve para medir.
2. **Muestreaba el corpus entero**, con un 61 % de anuncios donde un término jurídico no puede
   aparecer jamás. Dilución, no ausencia. Es el mismo error de denominador que el ADR 0011 evita.

#### Lo que se añadió al vocabulario, y lo que no (`VERSION_VOCABULARIO = 2026.08.23`)

| término | decisión | evidencia |
|---|---|---|
| `gays` | **añadido** | 0 apariciones espurias; es la forma que usan los títulos de las leyes vigiladas y `gais` no la encuentra |
| `gay` | **NO añadido** | 2 de 2 coincidencias son **apellidos de personas**: «M. Eugenia Gay Rosell» y «Daniel Araujo Gay». 100 % de falsos positivos |
| `sexo registral`, `sexo inscrito`, `sexo al nacer`, `sexo de nacimiento`, `sexo asignado al nacer`, `mencion registral relativa al sexo` | **añadidos** como DIRECTO | 0 falsos positivos en 1.500; cubren M-4 |

El caso de `gay` es el que mejor justifica haber medido: el jurista avisó del falso positivo
«Gay-Lussac» en temarios de física, y el real resultó ser **más común todavía** — un apellido
español corriente. Sin medir se habría añadido por buen criterio y habría metido ruido de firmas y
tribunales de oposición.

Los seis términos de M-4 resuelven además, sin tocarlas, el problema de `categoria femenina` y
`competicion femenina`: son CONTEXTO con razón —cualquier convocatoria deportiva las lleva— y desde
el ADR 0021 no disparan solas, así que un reglamento que restringiera por sexo registral **no
entraba en la cola**. Ahora entra por el término que decide, no por el que describe la materia.

103 tests en verde incluido el gold set: ningún caso etiquetado cambia de estado.

#### ⚠️ Pendiente y necesario: `--reprefiltrar`

Subir `VERSION_VOCABULARIO` marca como obsoletas **todas** las evaluaciones anteriores, que es
justo el mecanismo que existe para esto. Hasta que se lance `python -m worker.run --reprefiltrar`,
las 67.733 normas siguen evaluadas con el vocabulario viejo y los seis términos nuevos **no están
haciendo nada**.

No se lanzó en el momento porque había dos ingestas compitiendo por CPU. Es lo primero que hay que
hacer cuando terminen, y conviene mirar el embudo antes y después: si el número de `relevante` no
se mueve, es que en este corpus efectivamente no había nada que rescatar — que es lo que la
medición predice, y comprobarlo cierra el círculo.

#### Nota de higiene: tres sondeos se colaron en el repositorio, uno llegó a commitearse

El compose monta `./backend:/app`, así que un `docker compose cp` a `/app` **deja el fichero dentro
del repositorio**. Pasó tres veces (`probe.py`, `dbg.py`, `ver_gay.py`) y `medir_terminos.py` llegó
a entrar en el commit `355470f` por un `git add -A`. No rompía nada en producción —nadie lo importa—
pero sí rompía `ruff` en la puerta de CI, que es como se descubrió.

Arreglado de raíz en vez de por memoria: `.gitignore` ignora `backend/**/_sondeo_*.py`, y la
convención es que cualquier script de usar y tirar lleve ese prefijo. Acordarse de borrar no es un
control; ignorarlo por patrón sí.

### 📏 R-DES-001 (deslegalización) medida y **NO implementada** — 2026-08-23

Segunda aplicación del método que salvó lo de `gay`: medir el candidato antes de escribirlo. Aquí
el candidato era una **regla del catálogo**, no un término, y el resultado también es negativo —
con una diferencia que importa: esta vez la población medida es un **censo**, no una muestra.

`scripts/medir_deslegalizacion.py`, sin una sola petición de red.

| | remisión pegada a un precepto | + toca norma vigilada | + el catálogo calla (**NUEVA**) |
|---|---|---|---|
| **Censo dirigido** (52 normas) | 11 | 3 | **0** |
| Muestra aleatoria (1.493 disposiciones) | 9 (0,6 %) | 0 | 0 |

#### Las dos cosas que dice, y son distintas

1. **El riesgo que avisó el jurista no se materializa.** Predijo que «reglamentariamente se
   determinará» y «se faculta a» aparecerían «en casi toda norma con rango de ley», o sea que
   serían el nuevo «igualdad de trato». Medido: **0,6 % de las disposiciones**. Lo que lo evita
   ya estaba en la casa — exigir la construcción **en la misma cláusula que un precepto**
   (`_clausulas_con`, criterio del ADR 0023). El control del ADR 0023 resuelve el ruido de M-8
   sin que haya que inventar nada.
2. **Y aun así la regla no aporta: `NUEVA = 0`.** Las 3 normas con remisión *y* norma vigilada
   **ya producen veredicto hoy**, por R-MOD-001. R-DES-001 no llevaría ni un caso nuevo al gate
   humano; reetiquetaría tres que ya están.

Por eso **no se implementa**. El patrón queda en el script, que es donde vive una hipótesis
medida y descartada, y no en `pipeline/reglas.py`, que es donde viven las que producen veredictos.

#### El error de denominador, otra vez, y esta vez cazado a tiempo

La primera versión del script muestreaba 800 al azar y daba **0** en la columna que decide.
Parecía una respuesta. No lo era: solo **22 normas de 69.388** tocan la watchlist, así que en 800
al azar la esperanza de encontrar una es **0,25**. El cero medía el tamaño de la muestra.

Es el tercer episodio del mismo error en este repositorio (el umbral de la fase 2 en el ADR 0011,
el 61 % de anuncios en `medir_terminos_candidatos`). Ya no es mala suerte: **es el modo de fallo
característico de medir cosas raras en un corpus grande**, y la contramedida que funciona es
declarar qué población contesta a qué pregunta antes de contar. El script ahora mide dos y lo
dice en la cabecera: el censo dirigido contesta si la regla **aporta**, la muestra aleatoria si
hace **ruido**. Ninguna de las dos contesta lo de la otra.

#### ⚠️ El hallazgo de verdad: el cuello de botella NO son las reglas, es la watchlist

La entrada del 2026-08-23 concluyó «el cuello de botella ya no son los datos: son las reglas».
**Hay que afinarlo, porque lleva a trabajar en el sitio equivocado.** Los números:

| | |
|---|---|
| Normas en `config/watchlist.json` | **24** |
| Normas del corpus que la tocan (con verbo modificativo) | **22** |
| De esas, las que ya producen veredicto | **17** |

Toda regla que exija «toca una norma vigilada» —y las cuatro que llegan al gate lo exigen, porque
el ADR 0017 lo exige para entrar en la cola— **tiene un techo de 22 casos en 69.388 normas**. De
esos 22, 17 ya están cogidos. Escribir la quinta, la sexta y la séptima familia de reglas se
reparte un margen de **5 normas**.

Dicho de otro modo: **el catálogo no está ciego, está mirando por una rendija de 24 normas.**
Ampliar el catálogo no puede producir lo que la watchlist no deja entrar.

**Lo que esto reordena en el plan:** antes de la siguiente familia de reglas, **ampliar la
watchlist** — que es conocimiento de dominio (`jurista-lgtbi`, 13.4) y no ingeniería. Las 24 de
hoy son estatales y de cabecera; faltan las leyes trans autonómicas una a una, los decretos de
estructura de las consejerías con competencia, los currículos, y la normativa sanitaria de cada
servicio autonómico de salud. Es la misma lección que M-4: el filtro no ve lo que no le hemos
dicho que mire.

**Salvedad de método:** las cifras de eje referencial se leyeron con `--reprefiltrar` a medio
correr, así que están calculadas con `VERSION_VOCABULARIO = 2026.08.20`. El eje referencial
depende de la watchlist y no del vocabulario, y `VERSION_WATCHLIST` no ha subido, así que el 22 no
debería moverse — pero conviene reconfirmarlo cuando el barrido termine, no darlo por hecho.

### 🔭 La watchlist, ampliada por el `jurista-lgtbi` — y por qué NO se aplica entera — 2026-08-23

Encargo lanzado tras el hallazgo del techo de 22. 29 llamadas, 18 candidatas verificadas. El
informe trae **un aviso que invierte parte del encargo**, y es lo primero que hay que leer.

#### ⚠️ El aviso: R-SUP-001 asume que la watchlist son normas PROTECTORAS

Está escrito en el docstring de `clasificar` (`pipeline/reglas.py`) y **verificado ahí palabra
por palabra** antes de darlo por bueno:

> «la watchlist es un catálogo de normas **protectoras**, así que suprimir preceptos de una de
> ellas es presuntamente quitar protección»

Ese supuesto se sostiene con 24 leyes LGTBI/trans. **Se rompe en cuanto entran normas-vehículo**
—LOE, Ley 16/2003 del SNS, Reglamento Penitenciario, Ley 20/2011 del Registro Civil— donde el
derecho del colectivo vive en dos o tres preceptos y el resto es materia ajena. Suprimir el
artículo 33 de la Ley 16/2003 (formación sanitaria especializada) no es un retroceso LGTBI, y
R-SUP-001 lo llamaría **`retroceso` con signo afirmado y severidad 4**.

**Es el mismo error del ADR 0023 un nivel más arriba.** Allí la supresión y la norma vigilada
coexistían en el mismo documento sin tener que ver; aquí coexistirían dentro de la propia norma
vigilada. Y el precio es el mismo que ya se pagó: alertas de retroceso sobre materias ajenas
desgastan el gate humano, que es el control central del proyecto.

`NormaVigilada` (`pipeline/watchlist.py`) tiene cuatro campos y **ninguno distingue protectora de
vehículo** — comprobado. Añadir esa distinción es un cambio de esquema pequeño pero real.

#### Las 18 candidatas, verificadas dos veces

El jurista las verificó contra boe.es; después se comprobaron **con nuestro propio código**
(`scripts/verificar_identificadores.py`, por `url_guard` + `xml_safe`): **18 de 18 con el título
oficial exacto que él dio**. Su verificación era sólida, incluidos dos identificadores que él
mismo cazó como falsos antes de entregarlos (`BOE-A-2007-13022` es la LO 8/2007 de financiación
de partidos, no la Ley 19/2007 del deporte).

**Las tres protectoras** (no rompen el supuesto de R-SUP-001, aplicables sin tocar código):

| identificador | norma |
|---|---|
| `BOE-A-2022-11589` | Ley 15/2022 integral para la igualdad de trato y la no discriminación |
| `BOE-A-2023-13287` | Instrucción de 26/05/2023 de la DGSJFP sobre rectificación registral |
| `BOE-A-2018-14610` | Instrucción de 23/10/2018 sobre cambio de nombre de personas trans |

La Instrucción de 2023 es la que mejor encaja con la sección 1 de `CLAUDE.md`: **rango
instrucción, estatal, y consta vigente sin modificaciones**. Una instrucción se cambia con otra
instrucción, sin parlamento, sin prensa y un martes de agosto. Es el retroceso silencioso de rango
bajo, y por una vez dentro del alcance que ya se ingiere.

**Las quince norma-vehículo** quedan a la espera de la decisión de arriba. La más rentable por
frecuencia es la Ley 16/2003 del SNS (~24 modificaciones, última actualización 31/07/2026): es de
la que cuelga el RD 1030/2006 ya vigilado, y define **quién decide qué entra y sale de la cartera
común** — retirar una prestación sin tocar ninguna ley de derechos empieza por ahí.

#### Un hallazgo propio: puede que vigilemos el matrimonio igualitario de forma nominal

`BOE-A-2005-11364` (Ley 13/2005) es **la única de las 24 vigentes que falla**: 404 en la base
consolidada. No prueba que el identificador sea falso —no todo el BOE se consolida— pero encaja
con la hipótesis 6 del informe: esa ley **se agotó al modificar el Código Civil**. Hoy el derecho
vive en el art. 44 CC, así que una reforma futura del matrimonio modificaría el CC y el
`<analisis>` declararía afectado al CC, que no está en la lista.

Si se confirma, la entrada figura en la watchlist y **no puede disparar nunca**. Conviene revisar
las 24 con ese criterio: cuáles son normas vivas y cuáles leyes-instrumento ya consumidas. Es
barato y no sale a la red — se mira qué identificador declara el `<analisis>` en el corpus.

#### Otra limitación medida, que afecta al DOGC

`citas.py:_FORMA_LARGA` solo reconoce títulos que empiezan por `ley | ley orgánica | ley foral |
real decreto | decreto` con número y fecha. Las entradas de rango **instrucción** y **orden**, y
el Reglamento del Registro Civil de 1958 (sin número/año), **no encajan**: seguirán disparando por
el `<analisis>` del BOE, pero son invisibles para el eje de citas y por tanto para el DOGC. No es
motivo para excluirlas; sí para no afirmar una cobertura que no existe. El comentario de
`citas.py` que dice «el título ya empieza por esa forma en las 21 entradas» **dejará de ser cierto
en cuanto entre la primera instrucción**, y hay que actualizarlo entonces.

#### Descartes razonados, que valen tanto como la lista

- **Estatuto de los Trabajadores** y **Código Penal**: tentadores (art. 4.2.c ET, arts. 22.4 y 510
  CP) y descartados por **frecuencia excesiva en el sentido malo**. Se modifican varias veces al
  año por cualquier reforma, y cada una entraría en la cola del LLM (133,9 s) y llegaría al gate
  sin una línea sobre el colectivo. Es el modo de fallo que vació de sentido a R-SUP-002.
- **Orden SSI/2065/2014**: descartada por duplicación — es modificadora de los anexos del RD
  1030/2006, que ya se vigila. No aporta un caso nuevo, repite el que ya se detecta.

#### ⇨ Decisión pendiente, y es de una persona

O **(a)** entran solo las tres protectoras, hoy, sin tocar código; o **(b)** entran las dieciocho
junto con un campo de especificidad en `NormaVigilada` y el ajuste de R-SUP-001 para que no afirme
signo sobre normas-vehículo. **Aplicar las dieciocho sin ese ajuste es la opción que no está
sobre la mesa**: sube el recall y sube a la vez el número de alertas de retroceso afirmado sobre
materias sin relación con el colectivo.

Al aplicar cualquiera de las dos: subir `version` en el JSON, recontar la línea `_cobertura` —que
hoy solo habla del bloque autonómico— y relanzar `--reprefiltrar`.

### 📊 Censo de lo que el corpus modifica: 9 de las 24 vigiladas, y el matrimonio confirmado — 2026-08-23

`scripts/medir_normas_mas_modificadas.py` sobre el **censo** de 27.016 disposiciones (sin red).
Deja un índice reutilizable en `data/normas-modificadas.json`, para que la pregunta «¿cuánto
aportaría esta candidata?» no vuelva a costar un censo.

| | |
|---|---|
| Disposiciones leídas | 27.016 |
| Que modifican o derogan algo | 1.900 (7,0 %) |
| Normas distintas tocadas | 2.597 |
| **De ellas, en la watchlist** | **9 de las 24** |

#### Las 9 vivas y las 15 que nunca aparecen — con la distinción que NO hay que saltarse

**Vivas** (encabezadas por el RD 1030/2006 de cartera común, tocado **13** veces — es el que
produce casi todas las detecciones de R-MOD-001): las tres estatales que quedan, y seis leyes
autonómicas (CT, VC ×2, NC, MD ×2).

**Nunca tocadas: 15.** Y aquí hay **tres causas distintas que sería un error grave mezclar**:

1. **Agotamiento — la entrada no puede disparar nunca.** Solo la Ley 13/2005 (ver abajo).
2. **Nadie la ha modificado en el año que cubre el corpus.** Las 14 leyes autonómicas LGTBI. **No
   es un fallo: es el sistema esperando**, que es exactamente para lo que existe la watchlist. Un
   cero aquí no dice nada malo de la entrada.
3. **El canal no las alcanza**, y esto ya estaba escrito en `_limitacion_que_hay_que_tener_presente`
   del propio fichero: un **decreto u orden autonómico** que modifique la ley de su comunidad **no
   llega al BOE**. Las leyes autonómicas solo se detectan si las toca otra ley. El vaciado por vía
   reglamentaria autonómica sigue siendo invisible, y no lo arregla ninguna watchlist.

#### ✅ Confirmado: la Ley 13/2005 es vigilancia nominal

Dos evidencias independientes, y la pregunta era justo esta:

- **404 en la base consolidada del BOE** — la única de las 24 que falla (`verificar_identificadores`).
- **0 apariciones en el `<analisis>` de 27.016 disposiciones**, mientras el **Código Civil sí
  aparece** (`BOE-A-1889-4763`, 1 vez).

Encaja con el agotamiento: la Ley 13/2005 se consumió al modificar el CC, hoy el derecho vive en
el art. 44 CC y una reforma futura declararía afectado al CC. **La entrada figura en la lista y no
puede disparar.** Añadir el Código Civil la cubriría, con el mismo problema de ruido que el
Estatuto de los Trabajadores — o sea, otra vez el supuesto de R-SUP-001.

Cautela honesta: una sola aparición del CC es evidencia débil por sí sola; lo que sostiene la
conclusión es el 404 sumado al cero.

#### ⚠️ Y esto corrige lo que yo mismo escribí esta mañana

Escribí, dos entradas más arriba, que «el cuello de botella no son las reglas, es la watchlist».
**También era incompleto.** Medido el aporte de las 18 candidatas sobre este corpus:

| candidata | veces tocada en 27.016 disposiciones |
|---|---|
| Ley 20/2011 Registro Civil, Ley 16/2003 SNS, Ley 41/2002 paciente, RD 243/2022 Bachillerato, Ley 19/2007 deporte | **1 cada una** |
| **Las tres protectoras** (Ley 15/2022, Instrucción 2023, Instrucción 2018) | **0** |
| Las diez restantes | **0** |

**Total: 5 casos en un año de corpus.** El techo pasaría de 22 a ~27. Sigue siendo una rendija.

No contradice al jurista —él midió frecuencia histórica en el consolidado, que para la Ley 16/2003
son ~24 modificaciones en 23 años, o sea ~1/año, justo lo medido— sino que **la pone en escala**:
lo que él llamó «la candidata más rentable» rinde un caso al año.

**La conclusión que queda en pie, y es la buena para el TFM:** el sistema encuentra poco no porque
le falten reglas ni porque le falte watchlist, sino porque **el retroceso que este diseño sabe ver
—el que deja rastro referencial en el `<analisis>`— es raro**. Los mecanismos que el informe de
puntos ciegos ordenó por invisibilidad (M-1 no convocar, M-3 bases de subvención, M-7 currículo
por ausencia) **no dejan ese rastro por definición**, y son los frecuentes. Eso no es un fallo de
implementación que se arregle añadiendo entradas a un JSON: es el límite del enfoque, está medido,
y decirlo con estos números vale más que una cifra de recall alta sobre lo que sí se ve.

#### ✅ El círculo del vocabulario, cerrado

`--reprefiltrar` terminó: las **69.388** normas reevaluadas con `VERSION_VOCABULARIO = 2026.08.23`.

| estado | con 2026.08.20 | con 2026.08.23 |
|---|---|---|
| descartada | 68.630 | 68.627 |
| sospecha | 452 | **455** |
| relevante | 166 | **166** |
| ilegible | 102 | 102 |
| pendiente | 38 | 38 |

**`relevante` no se movió y `sospecha` subió 3**, que es lo que la medición de los términos
predijo: en este corpus no había casi nada que rescatar. Los 3 son de `gays`, el único término
añadido con apariciones distintas de cero. **Confirma la predicción y cierra el círculo**, que era
la condición que la entrada de esta mañana puso para dar la medición por buena.

### ✅ Tanda 1 de la watchlist aplicada: 24 → 27, y el matrimonio deja de mentir — 2026-08-23

Aplicada la opción que los datos sostienen sin ambigüedad. `VERSION_WATCHLIST = 2026.08.23`.

#### Lo que entra: las tres protectoras

`Ley 15/2022` de igualdad de trato, y las dos **Instrucciones de la DGSJFP** (rectificación
registral 2023, cambio de nombre 2018). Son las únicas tres de las 18 candidatas que **no rompen
el supuesto de R-SUP-001**, así que entran sin tocar código.

La Instrucción de 2023 es la entrada que mejor encaja con la sección 1 de `CLAUDE.md`: **rango
instrucción y estatal**. Fija cómo se tramita en la práctica la rectificación registral —
comparecencias, plazos, menores de 12 a 16, personas intersex — y una instrucción se cambia con
otra instrucción, sin parlamento, sin prensa y un martes de agosto.

**Corrección de algo que dije mal al reportar.** Presenté el «las tres protectoras rinden 0 en el
corpus» como argumento en contra. Es un mal argumento y contradice la distinción de tres causas
escrita una entrada más arriba: **un cero en una norma viva no es un fallo, es el sistema
esperando** — igual que las 14 leyes autonómicas que tampoco se han tocado este año.

#### La Ley 13/2005 se queda, pero su nota deja de prometer cobertura

Confirmado que su vigilancia es **nominal** (404 en consolidada + 0 apariciones frente al Código
Civil que sí aparece). Se mantiene por el rastro histórico, como la Ley 14/2012 de Euskadi, y su
`nota` lo dice ahora con todas las letras: **no cuenta como cobertura del matrimonio igualitario**.
Cubrirlo de verdad exige vigilar el Código Civil, con el problema de ruido del Estatuto de los
Trabajadores — o sea, otra vez el supuesto de R-SUP-001.

#### El test de citabilidad separó dos cosas que confundía

Al aplicar la tanda saltó `test_todas_las_normas_vigiladas_se_pueden_citar`, **exactamente donde
el jurista avisó** (su sección 1.2). Su premisa —toda norma vigilada tiene forma de cita— solo se
podía sostener mientras la watchlist fueron 24 leyes y reales decretos. Una **instrucción no tiene
número `N/AAAA`** y no se cita así en ninguna redacción posible: no hay título que arreglar.

Ahora `citas.cita_esperable()` distingue:

- **Título mal escrito** (lleva número y aun así no encaja) → **sigue rojo**, que es donde tiene
  que doler. Es el fallo mudo original.
- **Rango no numerado** (instrucción, orden, el Reglamento del Registro Civil de 1958) → se
  **declara y se cuenta**, mismo criterio que el estado `ilegible` (ADR 0020). Esas entradas
  disparan por el `<analisis>` del BOE, pero son **invisibles para el eje de citas** y por tanto
  para el DOGC.

El corte va por el número y **no por una lista de tipos**: «Decreto de 14 de noviembre de 1958»
empieza por un tipo normalmente numerado y no lleva número, y una lista lo daría por mal escrito
teniendo el título oficial exacto.

Validado saboteando —un título con número que no empieza por el tipo pone rojos los dos tests— y
de paso se sustituyó el comentario de `forma_larga` que afirmaba «el título ya empieza por esa
forma en las 21 entradas»: **una invariante que hay que recontar a mano cada vez que alguien toca
un JSON no es una invariante, es una nota que caduca sin avisar**. Ahora la comprueba un test.

694 tests en verde.

#### ⇨ Tanda 2, pendiente y con su bloqueo escrito en el propio fichero

Las **15 norma-vehículo** quedan anotadas en `_pendientes_de_verificar` con identificador ya
verificado, el motivo de que no entren, **y lo que rinden medido: 5 casos en un año de corpus**.
Antes de aplicarlas hace falta el campo de especificidad en `NormaVigilada` y que R-SUP-001 no
afirme signo sobre ellas. Lleva ADR, tests y subir `VERSION_REGLAS`; el dato de rendimiento está
ahí para decidir si merece una sesión.

### ⇨ CÓMO RETOMAR ESTO — cierre del 2026-08-23

**Todo está commiteado en `task/26-informes-con-corroboraciones`. Nada a medias salvo procesos de
fondo que se completan solos.**

#### Procesos vivos al cerrar

```bash
# Comprobar que siguen vivos (lo primero que hay que mirar):
docker compose exec -T worker sh -c 'for p in /proc/[0-9]*; do [ -r $p/cmdline ] || continue; tr "\0" " " < $p/cmdline | grep -E "worker.run|backfill"; done'
```

- **`--reprefiltrar` con la watchlist de 27** (log en `data/reprefiltrar-watchlist.log`). Iba por
  5.000 de 69.407 y **ahora confirma por lotes de 500**, así que se puede cortar sin perder nada y
  se ve avanzar. Si al volver no está, relanzarlo: es idempotente.
- **Los dos backfills** (BOE hacia atrás, DOGC hacia adelante). Se relanzan con los comandos de la
  entrada del 2026-08-22.

Cuando termine el reprefiltrado, mirar el embudo: es lo que dirá si las tres protectoras nuevas
mueven algo. **La predicción es que no** (rinden 0 en el censo), y confirmarlo cierra el círculo.

#### Lo que se hizo hoy, en una línea cada cosa

1. **El barrido del prefiltro confirma por lotes** y no se pierde entero al cortarlo. La
   paginación va por `id` y no por «las que falten», porque lo segundo no termina nunca con
   normas `ilegible` (ADR 0020). Validado saboteando el diseño.
2. **`R-DES-001` medida y NO implementada**: 0 casos nuevos sobre un censo.
3. **La watchlist pasa de 24 a 27** con las tres protectoras verificadas contra el BOE.
4. **La Ley 13/2005 estaba vigilada de forma nominal** — 404 en consolidada y 0 apariciones — y su
   nota ya no promete cobertura del matrimonio igualitario.
5. **ADR 0027**: el límite del eje referencial, medido. Ampliar la watchlist rinde 5 casos/año, así
   que **no es la palanca**; el sistema ve el retroceso que deja rastro referencial y los
   silenciosos no lo dejan por definición.
6. **`CLAUDE.md` podado de 64 KB a 56 KB** sin perder una sola regla.

#### Lo siguiente, por valor

1. **Podar `ESTADO.md`** (este fichero, 3.900+ líneas). Hay permiso del humano dado el 2026-08-23
   y **no se llegó a empezar**. Lo que se resume sin perder nada son las entradas cerradas del 9
   al 17 de agosto; lo que no se toca es el plan V1, esta sección y las entradas del 20 en
   adelante.
2. **Tanda 2 de la watchlist** (~20k): campo de especificidad en `NormaVigilada` y que R-SUP-001
   no afirme signo sobre norma-vehículo. Todo lo que hace falta saber está en
   `_pendientes_de_verificar` del propio `config/watchlist.json`, identificadores ya verificados
   incluidos. **Con su rendimiento medido delante: 5 casos al año.** Decidir si merece la sesión.
3. **Formato de casos-par del gold set** (~15k). Bloqueante antes de etiquetar en masa: M-2, M-3 y
   M-7 son retrocesos **por ausencia** y un JSON por documento suelto no los representa. Decidir
   si el esquema admite pares o se acepta por escrito que quedan fuera de la medición.

#### Dos instrumentos nuevos que conviene no olvidar

- `scripts/verificar_identificadores.py` — trae el título oficial de cada norma vigilada. **Correr
  tras tocar `watchlist.json`**: es lo único que caza un identificador bien formado que apunta a
  otra norma.
- `scripts/medir_normas_mas_modificadas.py` — deja un índice en `data/normas-modificadas.json`, así
  que «¿cuánto aportaría esta candidata?» es un lookup y no un censo.
