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

### 📚 Del 16 al 19 de agosto: la segunda fuente y lo que enseñó — condensado el 2026-08-23

> Resumido a sus hallazgos el 2026-08-23; el desarrollo está en los commits y en los ADR 0019 a
> 0022. **Es el tramo donde el proyecto pasó de una fuente a dos y descubrió, midiendo, casi todo
> lo que hoy sabe sobre sus propios límites.**

| fecha | trabajo | ADR |
|---|---|---|
| 08-16/17 | Regla de oro 9 (offsets), volumen de verdad y el **DOGC como segunda fuente** | 0013, 0019 |
| 08-18 | Primera medición del extractor a escala, **y no fue buena** | — |
| 08-18/19 | 172 normas del DOGC eran invisibles: nace el estado `ilegible` | 0020 |
| 08-19 | El gold set mide el DOGC, y lo primero que mide es **un falso positivo propio** | 0021 |
| 08-19 | El eje referencial existe fuera del BOE, **y su aportación medida es cero** | 0022 |

#### Los hallazgos que siguen valiendo

- **El estado `ilegible` y sus tres reglas** (hoy en 7.2 de `CLAUDE.md`): gana a cualquier señal
  del título, se reintenta en cada pasada dejando `prefiltro_version_texto` a NULL, y se conservan
  los términos del título como pista para el rescate a mano.
- **`xml_safe` no se relajó, y hay que decirlo al revés de como parece:** ese control fue **lo
  único** que impidió que 172 páginas de error entraran en el pipeline como si fueran normas. El
  prefiltro las habría descartado por falta de vocabulario y nada habría fallado visiblemente.
- **Las citas: solo forma larga, número y fecha.** La corta produjo **4 coincidencias falsas de 4**
  sobre el DOGC. El verbo se busca 200 caracteres hacia atrás; sin verbo es `CITA` y no dispara.
  Mencionar una ley no es tocarla.
- **El DOGC no publica emisor:** su `organo_emisor` es literalmente «DOGC». Y empotra fórmulas de
  lenguaje inclusivo y de desagregación estadística en casi todos sus documentos — de ahí vino el
  falso positivo que el gold set cazó, y de ahí salió el ADR 0021.
- **La watchlist se pasa por parámetro, no se carga dentro de `leer_cuerpo`.** Lo delató el propio
  código al escribir el eje.
- **El color del mapa se calcula con `vigiladas`, no con la parte legible.** Anotado entonces como
  deuda consciente.

#### Cuatro casos de gold set elegidos por su vector, no por su claridad

`BOE-A-2024-10765` (Ley de Presupuestos de Madrid, el vehículo clásico del cambio que no se
anuncia), `BOE-A-2024-24104` (bases de subvención, el vector que el análisis jurídico señala como
más silencioso), `BOE-A-2024-23757` (cualificaciones profesionales, el documento más grande del
corpus) y `BOE-A-2024-23937` (convenio SEGISS, **puesto a propósito por ser el más discutible**).

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

### 📚 Cierre del 19/20 de agosto: el caso que faltaba — condensado el 2026-08-23

Los cuatro casos nuevos del gold set están descritos en la entrada resumida de arriba. Lo que
cierra este tramo es **el caso que el gold set llevaba pidiendo desde el 9 de agosto y que no
aparecía ingiriendo días seguidos**: se encontró **preguntándole al BOE** quién había modificado
cada norma vigilada (`scripts/quien_modifica.py`), en vez de esperar a que cayera. De ahí salieron
la Ley Foral de Presupuestos de Navarra 2022 y la ley de medidas fiscales valenciana de 2021, las
dos modificando leyes trans autonómicas.

**La lección de método, que es lo que se conserva:** cuando el corpus no trae un tipo de caso, se
puede preguntar por él en vez de ampliar el corpus a ciegas. 635 tests en verde y el gold set
coincidiendo 29 de 29.

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

### ✅ El círculo de la tanda 1, cerrado: las tres protectoras no mueven nada (y era la predicción) — 2026-08-23

`--reprefiltrar` con `VERSION_WATCHLIST = 2026.08.23` terminó sobre las **69.446** normas.

| | antes (24 normas) | después (27) |
|---|---|---|
| Eje referencial dispara en | **22** | **22** |
| relevante | 166 | 166 |
| sospecha | 455 | 456 |

**Cero movimiento, y es exactamente lo que el censo predijo**: las tres protectoras rinden 0 en
este corpus. Confirmarlo cierra el círculo, igual que se hizo con los seis términos del
vocabulario esa misma mañana.

**Y no es un argumento para quitarlas** (la distinción de las tres causas): un cero en una norma
viva es el sistema esperando. La Instrucción de 2023 rinde 0 porque **nadie la ha modificado
todavía**, que es precisamente la situación en la que quieres tenerla vigilada.

#### ⚠️ Lo que sí se movió, y hacia el lado malo: las ilegibles de 102 a 143

El worker lo avisa él solo, que para eso se hizo así (ADR 0020):

> «135 normas tienen su texto archivado y el pipeline NO PUEDE LEERLO: no hay vigilancia sobre
> ellas, por mucho que su fuente figure como activa.»

**No es una regresión, es el efecto conocido del backfill del DOGC**, ya descrito el 2026-08-22:
la ingesta trae normas nuevas —muchas solo en PDF— más rápido de lo que una pasada con tope las
procesa. Se ha relanzado `--recuperar-pdf` (log en `data/recuperacion-pdf.log`); lo que quede
ilegible **después** de esa pasada sí es un hueco de verdad.

Recordatorio que no se negocia: cualquier cifra de cobertura del DOGC va acompañada de cuántas de
sus normas son ilegibles, o afirma una vigilancia que no existe.

### ⚠️ El extractor a escala: el timeout era un bug y el modelo ve el 3 % de la norma — 2026-08-28

Primera tanda larga del extractor sobre la cola real (620 normas). Dos hallazgos, y el primero
llevaba cinco días fallando **sin romper nada visiblemente**, que es la peor forma de fallar.

#### 1. `llm_timeout_segundos` estaba mal calibrado: 180 s → 600 s

| | |
|---|---|
| Documentos enviados al LLM | 43 |
| **Descartados por timeout de Ollama** | **22 (51 %)** |
| Descartados por esquema | 2 |

La extracción medida son **133,9 s de media** (ADR 0011). Un timeout de 180 s es un margen del
34 % sobre una media: **cualquier documento por encima de la media lo revienta**. No era una
elección conservadora, era un error de calibración.

**Y no se notó porque el fallo es silencioso por diseño:** sin fila, la norma vuelve sola a la
cola (6.9.3). El worker parecía avanzar mientras reintentaba en bucle las mismas normas. Es el
mismo patrón que el estado `ilegible` vino a resolver en el prefiltro — algo que no se puede
hacer, repitiéndose sin que nadie lo cuente.

Corregido en `config.py` y no en `.env`, porque es una corrección **medida** que debe quedar en el
repositorio: 600 s son 4,5 veces la media y absorben la cola de documentos grandes.

#### 2. El modelo ve menos del 5 % de la norma, y ahora ese dato viaja con la extracción

Medido sobre 150 normas de la cola de 607:

| | |
|---|---|
| **Caben enteras en el tope de 4.000** | **2 de 150 = 1 %** (~8 de 607) |
| Mediana de la cola | 82.309 caracteres |
| p75 | 138.530 |
| De los 43 ya enviados, mediana original | 153.428 → el modelo vio el **2,6 %** |

La sección 6.9.7 avisaba de que `MAX_CARACTERES_DOCUMENTO` estaba **sin medir**. Ya está medido, y
es peor de lo que el aviso sugería.

**Corrección de algo que se dijo mal al diagnosticar:** primero se afirmó que anotar offsets sobre
ese 2,6 % «promete una trazabilidad que no existe». **Es falso.** Los offsets los calcula el
sistema buscando sobre el texto archivado **completo** (ADR 0013), así que lo que el modelo cite
del fragmento ancla perfectamente. Lo que es parcial es la **cobertura**, no el anclaje. Son cosas
distintas y confundirlas lleva a desconfiar de un control que funciona.

Lo que sí hacía falta: **`extraccion_json` registra ahora `caracteres_enviados` y
`caracteres_documento`**. Sin eso, «el extractor no encontró nada aquí» no se distingue de «el
extractor no lo miró» — y sobre esta cola eso pasa el 99 % de las veces. Mismo criterio que
`ilegible` (ADR 0020): lo que el sistema no puede hacer se cuenta, no se omite.

#### Qué se decidió y qué no, y por qué

**La ventana deslizante de 6.9.7 —trocear con solapamiento y rebasar los offsets a posición
absoluta— es la solución correcta y NO se implementa ahora.** El argumento no es el esfuerzo, es
este:

> **La extracción del LLM no produce las detecciones que llegan al gate humano.** Las produce el
> catálogo de reglas, que lee el texto archivado **completo** (ADR 0016). Los punteros del
> extractor son diagnóstico, no veredicto.

O sea que multiplicar por ~38 el coste de CPU no desbloquearía ni una alerta ni un ítem de cola.
Con el plazo del 10 de septiembre y el gold set como cuello real, la sección 8 dice que no.

**Tampoco se restringe la cola a lo que cabe entero**, que era la otra opción barata: dejaría al
extractor con **8 normas de 607**. Medido antes de descartarla.

Así que el extractor sigue, con el timeout arreglado y **diciendo sobre cuánto documento se
pronuncia**. Cualquier cifra que salga de él se lee con esa salvedad, y ahora la salvedad está en
el dato y no en la memoria de quien lo mire.

#### La causa raíz de verdad: `num_predict` no estaba fijado (misma fecha, hallazgo posterior)

Lo anterior de esta entrada culpaba al timeout. **El timeout era un síntoma.** Un diagnóstico
hecho desde fuera del repositorio encontró la causa: el bloque `options` de `llm/ollama.py` fijaba
`temperature` y `seed` pero **no `num_predict`**, así que la generación era **ilimitada**. El
modelo no terminaba el JSON nunca, la petición caducaba, la norma volvía a la cola y vuelta a
empezar — **cinco días quemando tres de los cuatro núcleos para tirar el 100 % de los resultados**.

El `500 | 3m0s | POST /api/generate` del log de Ollama era ininterrumpido desde el 23 de agosto.

**Dimensionado con datos**, no a ojo: las 22 extracciones ya completadas miden 430 caracteres de
mediana, 939 en el p90 y 2.086 la mayor. Fijado en **1536 tokens**.

**Verificado que no trunca**, porque el primer caso medido fuera de esa muestra (3.391 caracteres)
la superaba y daba miedo: la respuesta cierra limpia, parsea y valida contra el esquema con 5
artículos extraídos.

##### Lo que hay que saber antes de tocar cualquiera de los dos números

> **`num_predict` y `llm_timeout_segundos` están atados.** El tiempo de una extracción lo manda lo
> que el modelo **genera**, no el documento de entrada: medido, **3,2 tokens/s** en esta máquina.
> 1536 tokens son ~480 s y caben en 600. **2048 serían ~640 s y volverían a caducar todas las
> peticiones.** Al tocar uno hay que recalcular el otro: `num_predict / tokens_por_segundo < timeout`.

##### El coste medido, y por qué NO se vació la cola

`scripts/medir_extraccion.py` (separa la llamada fría, que carga 4,8 GB de modelo, de las
calientes, que son las que presupuestan):

| | tiempo | generado | del documento |
|---|---|---|---|
| 1 (fría) | 119,3 s | 339 car | 5,8 % |
| 2 | 174,4 s | 727 car | 3,5 % |
| 3 | 462,6 s | 3.386 car | 10,4 % |

**318 s por norma → 54 horas para las 607.** Se decidió **no vaciar la cola**, por el mismo
argumento del ADR 0027: **la extracción no alimenta el gate humano** —las detecciones las produce
el catálogo de reglas, que lee el texto completo (ADR 0016)— así que serían 54 horas que no
producen ni una alerta más. Se extrae solo una **muestra** para tener material de diagnóstico de
`corroborar()`: si el modelo ve supresiones que las reglas no ven.

##### La lección, que es la de siempre en este repositorio

Un fallo que **no rompe nada visiblemente** puede correr cinco días. Sin fila, la norma vuelve
sola a la cola (6.9.3), así que el worker *parecía* avanzar. Es el mismo patrón que motivó el
estado `ilegible` (ADR 0020) y la misma razón por la que el embudo cuenta lo que no puede hacer:
**lo que no se cuenta, no se ve.** El log lo decía desde el 23 de agosto y nadie lo miró.

### ⇨ CÓMO RETOMAR ESTO — cierre del 2026-08-28

**Todo commiteado. La máquina se apagó con dos procesos a medias y ninguno pierde trabajo**, que
es por diseño: el backfill es reanudable por marcas y la cola del extractor es una consulta.

#### Lo que quedó a medias y cómo se retoma

```bash
docker compose up -d
docker compose exec -d worker sh //app/backfill.sh                              # falta 1 bloque
docker compose exec -d worker sh -c "python -m worker.run --extraer --limite 40 > /app/data/extraer-muestra.log 2>&1"
```

- **Backfill del BOE: 11 de 12 bloques.** El de 2025-10 se completó al reintentarlo; **falta
  2025-09**, que también murió con un `502 Bad Gateway` del BOE. Relanzar salta los 11 hechos.
- **Muestra del extractor: 9 de 40.** Se puede relanzar tal cual; lo ya extraído no se repite.

#### El resultado de la muestra, que es lo que había que saber

| | |
|---|---|
| Extracciones OK | 4 |
| Descartadas por esquema | 2 |
| **Descartadas por anclaje (regla de oro 9)** | **1** |
| **Timeouts** | **0** |

**Cero timeouts confirma que `num_predict` era la causa.** Y el descarte por anclaje es el sistema
funcionando: «el campo `texto_anterior` del artículo 0 afirma un texto que no está en el documento
archivado». **Es la regla de oro 9 cazando una alucinación en producción**, que era exactamente
para lo que se diseñó el ADR 0013. Que aparezca con esta frecuencia sobre datos reales es el mejor
argumento que tiene el proyecto para defender ese control ante el tribunal.

#### Lo siguiente, por valor

1. **Terminar la muestra de 40** y mirar `corroborar()`: ¿ve el modelo supresiones que las reglas
   no ven? Es la única pregunta que reabriría el ADR 0016, y con ~30 extracciones se puede
   contestar. **No vaciar la cola entera**: son 54 horas de CPU que no producen ni una alerta
   (ADR 0027 y la entrada de esta misma fecha).
2. **Gold set de 32 a 60-80 casos.** Sigue siendo el cuello de botella real del plazo y es tiempo
   humano, no de máquina.
3. **Tanda 2 de la watchlist** (~20k): campo de especificidad en `NormaVigilada` + que R-SUP-001
   no afirme signo sobre norma-vehículo. Todo lo necesario está en `_pendientes_de_verificar` del
   propio `config/watchlist.json`, con su rendimiento medido: 5 casos al año.

#### Y una herramienta nueva que conviene no olvidar

`--extraer --limite N`. El problema de fondo del incidente de esta semana no fue solo
`num_predict`: fue que **no había forma de acotar el gasto**, así que la única manera de gastar
menos era matar el proceso a mano. Ahora una tanda se puede presupuestar.

### ✅ Tercera fuente: el BOA, y el mapa deja de pintar dos territorios — 2026-08-29

Pedido por el humano: *«levanta el backend para poder ver la interfaz gráfica. La ingesta cómo
fue? Quiero que el mapa se vaya rellenando.»* El mapa se rellena con **fuentes**, no con más BOE:
lo estatal no colorea comunidades a propósito (pintarlas todas diría que hay diecisiete cambios
donde hay uno). Así que la tarea era una fuente autonómica nueva.

**Esto reordena el PLAN A V1**, y conviene decirlo claro: la auditoría de las 17 autonómicas
estaba **explícitamente fuera de V1** como el recorte grande. Sigue fuera; lo que ha entrado es
**una** fuente integrada de verdad, que es otra cosa y cabe en el límite de cinco de la sección 8
(vamos por 3). El cuello de botella del plazo **no se ha movido**: sigue siendo el gold set.

#### Lo que hay ahora

| | |
|---|---|
| Fuentes activas | **3** (BOE, DOGC, **BOA**) |
| Territorios pintados en el mapa | **3 de 19** (era 2) |
| Documentos archivados | 671 sumarios + 75.986 textos + 7 consolidados |
| Normas | ~75.700 |
| Alertas emitidas (con gate humano) | 8 |

#### La fuente, en corto (el detalle está en el ADR 0028)

El BOA es **la fuente más barata integrada hasta ahora**, y por una pieza que no está documentada
en ninguna parte: BRSCGI acepta `OUTPUTMODE=XML` sobre `SEC=OPENDATABOAXML`, y ese endpoint
devuelve **sumario y texto íntegro en la misma petición**, filtrable por fecha exacta.

Dos cosas que importan más que la comodidad:

1. **Trae resoluciones.** El ADR 0019 dejó escrito que el DOGC publica solo disposiciones
   generales y que **sus resoluciones e instrucciones no están, y son un vector de retroceso
   real**. En el día verificado, **15 de las 38 disposiciones del BOA son resoluciones**. Esta
   fuente cubre ese hueco para una comunidad.
2. **Cobertura completa desde el primer día: 38 de 38 cuerpos, 0 fallidas, 0 `ilegible`.** El
   DOGC iba con 172 de 264 ilegibles (65 %). Aquí no existe el problema de los cuerpos que la
   fuente promete y no sirve.

**Su única particularidad, y gobierna el módulo entero: no se puede pedir un documento por su
identificador.** Probados siete nombres de campo, los siete devuelven cero registros; la URI ELI
solo sirve HTML y solo para algunos rangos. La única dirección es la **posición ordinal dentro
del día**, así que el cuerpo descargado **se verifica contra el `<docn>` que trae** antes de
archivarlo. Sin esa comprobación, un día reordenado en origen archivaría el texto de una norma
bajo el identificador de otra — corrupción de archivo silenciosa, que es el modo de fallo que la
6.5 existe para impedir. Tiene su test.

#### Qué se tocó

- `backend/app/ingest/boa.py` (nuevo) y `backend/tests/test_ingest_boa.py` (15 tests).
- `security/url_guard.py`: una entrada, `boa.aragon.es` (aquí sumario y cuerpo salen del mismo
  host, sin la gimnasia de dos dominios que necesitó el DOGC).
- `services/texto_integro.py`: registro de validadores del cuerpo por prefijo. **Una fuente entra
  ahí solo si su forma de direccionar el cuerpo puede devolver otro documento**; el BOE y el DOGC
  no lo necesitan.
- `pipeline/texto.py`: rama para `documento > registro > texto`. **`VERSION_TEXTO_PLANO` NO sube**
  y está razonado en el código: gobierna las colas de reproceso y subirla reprocesaría 75.000
  normas cuya derivación esta rama no toca.
- `worker/run.py`: el despacho de fuentes deja de ser un `if fuente != "boe"` con el código de
  comunidad a mano y pasa a ser la tabla `FUENTES`. Con dos colaba; con tres, no.
- Migración `e3f7a1c92b64` **escrita a mano**. Solo un INSERT: las CHECK siguen siendo **15**
  antes y después, comprobado con el `SELECT ... FROM pg_constraint` de la sección 10.
- `docs/adr/0028-*.md`, `docs/fuentes.md` (BOA + tabla de las 10 candidatas sondeadas), `README.md`.

#### Dos cosas que se arreglaron de paso, y no eran del encargo

- **`scripts/medir_extraccion.py` dejaba `ruff` en rojo** (dos líneas largas del trabajo del
  2026-08-28). El CI estaba rojo desde entonces.
- **El README afirmaba tres cosas falsas**: 14 casos de gold set (son 32), que faltaba la
  trazabilidad por offsets (está desde el ADR 0013) y que solo el BOE estaba integrado.

#### Corriendo de fondo al cerrar

```bash
docker compose exec -d worker sh //app/backfill.sh          # BOE, falta el bloque 2025-09
docker compose exec -d worker sh //app/backfill_boa.sh      # BOA, 12 bloques hacia atrás desde 2026-08
```

Los dos son **reanudables por marcas** y **idempotentes por el sha256**: relanzarlos salta en
segundos lo ya hecho. Un `exec` no sobrevive al reinicio del contenedor, así que hay que
relanzarlos a mano tras un `docker compose up`.

#### El bug que encontró la primera tanda real, y por qué importa el patrón

A los tres minutos de lanzar el backfill del BOA — que es justo para lo que sirve lanzarlo.

**Un día sin boletín no da 404 ni una lista vacía: el BOA devuelve 200 con la portada del
diario** (8.127 bytes de HTML, idénticos el sábado y el domingo verificados). En cadena: el HTML
llega a `xml_safe`, salta `DtdForbidden` —**correctamente**, un DOCTYPE es la vía de entrada de
XXE—, el worker lo trata como fallo de control de seguridad y sale con código 3. El bloque se
aborta entero y no se marca, así que **cada fin de semana mataba una tanda y la dejaba
reintentándose sola**.

Es el mismo patrón que el `num_predict` sin fijar del 2026-08-28 y que motivó el estado
`ilegible` (ADR 0020): **algo que no se puede hacer, repitiéndose sin que nadie lo cuente.** La
diferencia es que esta vez se vio en tres minutos, porque el script escribe marcas y el log dice
qué bloque va por dónde.

Se reconoce por el prólogo XML **antes** de tocar el parser y se trata como el 404 del BOE.
**No relaja `xml_safe` en nada** —ese HTML no se parsea, se rechaza— y hay un test que lo fija
comprobando que el DOCTYPE no aparece ni en el mensaje de error.

**Lección para la cuarta fuente:** «cómo dice esta fuente que un día no tiene boletín» es una
pregunta que hay que hacerle explícitamente a cada una. El BOE contesta 404, el DOGC una lista
vacía, el BOA su portada. Ninguna lo documenta.

#### Ritmo medido del backfill del BOA

**~11 minutos por día de boletín**, y el coste no es la red (37 peticiones, ~380 KB) sino las
etapas globales que corren en cada pasada. Un mes de BOA son ~20 días hábiles, o sea ~3,7 horas
por bloque. Los 12 bloques son del orden de **dos días de reloj**, igual que pasó con el BOE.

#### Lo siguiente, por valor (sin cambios respecto al cierre anterior salvo el punto 3)

1. **Gold set de 32 a 60-80 casos.** Sigue siendo el cuello de botella real del plazo, y ahora
   más: hay una fuente más que evaluar y el corpus no ha crecido. Es tiempo humano.
2. **Terminar la muestra de 40 del extractor** y mirar `corroborar()`: ¿ve el modelo supresiones
   que las reglas no ven? Es la única pregunta que reabriría el ADR 0016.
3. **Cuarta fuente, si se quiere seguir rellenando el mapa** (~20k). Las candidatas sondeadas y
   su estado están en `docs/fuentes.md`; las dos con mejor relación son **BOPV (Euskadi)**, que
   solo necesita resolver fecha → número de boletín, y **BOCM (Madrid)**, que es donde ocurrió el
   caso insignia y es la que peor formato tiene. Quedan dos huecos en el límite de la sección 8.

### ✅ Cuarta fuente: el BOCYL, y la raya escrita del raspado — 2026-08-29 (tarde)

Pedido por el humano: *«a por otra CCAA»*. Se integra el **Boletín Oficial de Castilla y León**
(ADR 0029). El mapa pasa de 3 a **4 de 19 territorios**, y con el que más superficie ocupa.

**Queda un hueco** dentro del límite de cinco fuentes de la sección 8.

#### Por qué esta y no otra

Segunda tanda de sondeo, otra vez descargando. Y corrigió un error de la primera: **el BOCYL se
había descartado porque su RSS por fecha devolvía 500**, y eso era cierto e irrelevante — el RSS
no es su interfaz de datos. Su XML por disposición es **el más estructurado de las cuatro fuentes
integradas**, y a diferencia del BOA **se direcciona por identificador**: la URL nombra el
documento, así que desaparece la fragilidad ordinal que gobierna aquel módulo.

Ingesta real del día verificado: **27 items, 27 cuerpos, 0 fallidas, 0 ilegibles**, y el texto
derivado son decenas de miles de caracteres de articulado real (comprobado sobre el archivo, no
sobre el log).

#### Lo nuevo que trae al proyecto: raspar HTML, con una raya escrita

Es la primera fuente cuyo **sumario** hay que leer de HTML (no hay sumario XML: `BOCYL-S-*.xml`
da 500 y el RSS **ignora el parámetro de fecha** — pedido el 10/01/2024, devuelve el 28/08/2026).
La regla que lo hace aceptable, y que no se negocia:

> **El HTML aporta identificadores y metadatos. El texto que una alerta llegue a citar sale
> siempre del XML.** La cadena de evidencia (6.5, 7.5) no pasa por el raspado en ningún punto.

**Cualquier fuente futura que exija raspar el *texto* choca con esto y necesita su propio ADR.**
Es lo que aplazó a Euskadi (BOPV), cuyo cuerpo es HTML.

#### Tres trampas verificadas, y las tres rompen en silencio

1. **Todas las páginas llevan un enlace fijo a una disposición de noviembre de 2022**, incluidas
   las de días sin boletín. Sin filtrar por la fecha que va dentro del identificador, cada día del
   archivo ingeriría esa norma **bajo la fecha equivocada**.
2. **El título es de cada disposición; sección y organismo son cabeceras de grupo.** La primera
   versión trataba los tres igual, así que una disposición sin título propio **heredaba el de la
   anterior** y se habría archivado con el título de otra norma. **Lo encontró su test, no el
   diseño** — y es peor que descartarla, porque no rompe nada visible.
3. **Sumario en UTF-8, cuerpo en ISO-8859-15.** Cruzarlas no falla: ensucia el texto.

#### Y la cuarta manera distinta de decir «hoy no hay boletín»

El BOE contesta 404, el DOGC una lista vacía, el BOA su portada, el BOCYL una página corta que
tras el filtro por fecha deja cero disposiciones. **Cuatro fuentes, cuatro maneras, ninguna
documentada.** Es la primera pregunta que hay que hacerle a una fuente nueva: no habérsela hecho
al BOA costó que cada fin de semana abortara un bloque entero de backfill.

#### El BORM (Murcia) queda descartado, y NO por formato

Su portal responde a la petición del texto con **un captcha de Radware**. Sortearlo sería eludir
una detección de bots deliberada del titular de la fuente: no se hace y no se intenta. Queda
documentado como lo que es —una fuente que no quiere ser leída por programa—, no como un formato
difícil.

#### Qué se tocó

- `backend/app/ingest/bocyl.py` (nuevo) y `backend/tests/test_ingest_bocyl.py` (15 tests).
- `security/url_guard.py`: una entrada, `bocyl.jcyl.es`.
- `services/texto_integro.py`: el BOCYL entra en el registro de validadores **por un motivo
  distinto al del BOA**, y el comentario lo distingue — el BOA porque no se puede direccionar por
  identificador, el BOCYL porque su cuerpo declara una fecha contrastable.
- `pipeline/texto.py`: tercera rama, `disposicion > contenido > texto`. Apunta a `<texto>` y no a
  `<contenido>` porque `<titulo>` es su hermano. **`VERSION_TEXTO_PLANO` sigue sin subir.**
- `worker/run.py` y `services/ingesta.py`: una fila más en la tabla `FUENTES`. El refactor del
  ADR 0028 se paga aquí: añadir la cuarta fuente al despacho fue una línea.
- Migración `f4a8d21e7c93` **a mano**. Solo un INSERT: CHECK a **15** antes y después.
- `docs/adr/0029-*.md`, `docs/fuentes.md`, `README.md`.

#### Estado al cerrar

| | |
|---|---|
| Fuentes activas | **4** (BOE, DOGC, BOA, BOCYL) |
| Territorios pintados | **4 de 19** |
| Normas | BOE 75.501 · DOGC 645 · BOA 483 · BOCYL 27 |
| Suite | 727 tests, `ruff` + `mypy` limpios |

**Aviso operativo que ya ha costado tiempo dos veces:** los backfills se lanzan con
`docker compose exec -d`, y **un `exec` no sobrevive al cierre de la sesión ni al reinicio del
contenedor**. Los dos murieron al acabar la sesión anterior. Son reanudables por marcas, así que
relanzarlos salta en segundos lo hecho:

```bash
docker compose exec -d worker sh //app/backfill.sh          # BOE, falta el bloque 2025-09
docker compose exec -d worker sh //app/backfill_boa.sh      # BOA, 12 bloques
```

#### Lo siguiente, por valor

1. **Gold set de 32 a 60-80 casos.** Sigue siendo el cuello de botella real del plazo, y cada
   fuente nueva lo agrava: hay cuatro fuentes que evaluar con un corpus que no ha crecido. Es
   tiempo humano, no de máquina.
2. **Backfill del BOCYL**, cuando convenga darle volumen (aún solo tiene el día de verificación).
3. **Quinta y última fuente**, si se quiere cerrar el límite de la sección 8. La candidata con
   mejor relación es **BOPV (Euskadi)**, pero antes hay que resolver dos cosas: el índice
   fecha → número de boletín, y que su cuerpo es HTML — lo segundo choca con la raya del ADR 0029
   y necesitaría su propio ADR.

### ⚠️ La «ventana de 90 días» del mapa no existía, y dos silencios se pintaban igual — 2026-08-29 (cierre)

Salió de una pregunta del humano —*«CyL está vigilada sin alertas… ¿no hay forma de saber si lo
último es avance o retroceso?»*— y destapó dos cosas, la primera de ellas una afirmación falsa en
la portada pública.

#### 1. El mapa decía «Ventana de evaluación: últimos 90 días» y era mentira

**No hay ninguna ventana, en ningún sitio.** Ni `GET /api/cobertura` ni `construirRegiones` ni el
componente filtran por fecha: se agregan **todas** las alertas aprobadas. Era herencia de la época
de datos de maqueta y nadie la volvió a mirar.

Lo que lo hace grave y no cosmético: **con una ventana real de 90 días el mapa estaría hoy
vacío**, porque las 8 alertas son de publicaciones de 2024. O sea que la etiqueta no solo era
falsa, era falsa en la dirección que más engaña — decía que el mapa era reciente cuando lo que
enseña es todo el histórico.

Corregido diciendo lo que hace: **«Todas las alertas aprobadas, sin límite de fecha»**. No se
implementa una ventana real: un archivo de vigilancia no debe olvidar (6.5). Lo que no puede es
decir que olvida.

#### 2. «Vigilada sin alertas» significaba dos cosas opuestas, con el mismo relleno

| | Aragón | Castilla y León |
|---|---|---|
| Días ingeridos | 24, hasta 2026-08-28 | 1, de 2024-01-10 |
| Leyes en la watchlist | **2** (Ley 18/2018 y Ley 4/2018 de identidad y expresión de género) | **ninguna** |
| Qué significa «sin alertas» | hay marco y **nadie lo ha tocado** | **no hay marco que tocar** |

Castilla y León y Asturias son **las dos únicas comunidades sin ley autonómica LGTBI**, verificado
el 2026-08-08 y escrito desde entonces en `_sin_ley_autonomica` de la watchlist. **El dato existía
y no llegaba a ninguna pantalla**, así que el mapa pintaba las dos situaciones con el mismo blanco
y la segunda se leía como tranquilidad.

Es el **retroceso por ausencia** del ADR 0027 —el que no deja rastro referencial porque no hay
norma a la que referirse— y es el único de esa familia del que el proyecto tiene dato verificado.

**Quinto estado del mapa: «Sin ley autonómica LGTBI».** Relleno de **puntos**, no de rayas, y la
distinción no es estética: las tres tramas rayadas hablan de **nuestra** cobertura —cuánto se nos
escapa—, y esta habla del **territorio**. Y **sin color de estado**: el mapa dice que no hay marco,
no dice si eso está bien o mal, que es lo que prohíbe la regla de oro 2.

#### Lo que costó descubrir, y por eso tiene test

`por_ccaa` se construye agrupando la tabla `fuente`, y **Asturias es uniprovincial: no tiene BOP
propio, así que no tiene ninguna fila**. No aparecía en la respuesta, de modo que su ausencia de
marco no habría llegado nunca al mapa — la mitad del dato, y la mitad que menos se ve. Ahora la
entrada se crea aunque no haya fuentes, sin tocar los totales.

#### Qué se tocó

- `schemas/cobertura.py` y `api/cobertura.py`: campo `sin_ley_autonomica` + 3 tests.
- `frontend/`: `api/client.ts`, `lib/mapa.ts`, `components/MapaCCAA/MapaCCAA.tsx` (relleno,
  patrón y etiqueta accesible), `pages/MapaPage.tsx` (leyenda y la etiqueta falsa).
- `backend/backfill_bocyl.sh` (nuevo), lanzado.

#### Y una respuesta que hay que tener a mano, porque la pregunta va a volver

**El sistema solo firma avance o retroceso cuando la evidencia nombra una norma vigilada** con el
verbo pegado (ADR 0023); lo demás cae a `indeterminado` y va a la cola humana. El ADR 0027 ya midió
el alcance: solo el **7 % de las disposiciones modifican algo** y el eje referencial rinde **~5
casos al año**. **El silencio es el estado normal esperado, no un fallo.**

«Vigilada, sin alertas» quiere decir literalmente *«leímos su boletín y nada tocó las leyes que
vigilamos»*. No quiere decir *«aquí todo va bien»*, y ahora el mapa tiene un estado más para no
dejar que se lea así.

### ✅ La línea base: el mapa deja de pintar solo el movimiento y pinta el estado — 2026-08-30

Pedido por el humano tras ver que quince comunidades salían en blanco. **El mapa solo sabía
pintar *cambios*** —alertas aprobadas— y el ADR 0027 midió que eso son **~5 casos al año**: un
mapa vacío casi siempre, que se lee como «no pasa nada» cuando lo que dice es «no ha cambiado
nada». Ahora tiene dos vistas y **arranca en la línea base**.

#### El hallazgo que lo hizo barato: la watchlist ya estaba completa

No hizo falta investigar nada. `config/watchlist.json` ya tenía **las 17 comunidades cubiertas**,
auditadas una a una contra boe.es entre el 2026-08-08 y el 2026-08-20: 20 leyes autonómicas en 15
CCAA, más Asturias y Castilla y León verificadas **sin ley**. El dato estaba y no llegaba a
ninguna pantalla.

| categoría | CCAA |
|---|---|
| Ley trans **y** ley LGTBI | 4 |
| Solo ley LGTBI integral | 8 |
| Solo ley de identidad de género | 3 |
| Sin ley autonómica | 2 (AS, CL) |

#### Dos campos nuevos en la watchlist, y el segundo evitó una mentira

- **`tipo`** (`trans` | `lgtbi`), solo en las 20 autonómicas. **Escrito a mano leyendo el título
  oficial de cada una, no deducido con un regex**: «transgénero» aparece dentro de casi todas las
  LGTBI integrales y un regex las habría cruzado.
- **`vigente`**, que solo aparece cuando es `false`. Hoy una: **la Ley 14/2012 vasca, derogada por
  la 4/2024**. Se sigue vigilando a propósito —una norma derogada aparece en las referencias de
  las que la citan— pero **no cuenta como marco vigente**. Sin este campo la línea base habría
  dicho que Euskadi tiene una ley que ya no existe.

**La `version` de la watchlist NO sube por esto**, y está razonado en el propio fichero: subirla
devuelve las ~78.000 normas a la cola del prefiltro y no cambiaría ni un resultado, porque ni el
eje referencial ni las reglas miran estos campos. Mismo criterio que `VERSION_TEXTO_PLANO`.

#### Lo que la línea base NO hace

**Enumera lo que hay; no puntúa.** Cada comunidad enseña sus leyes con su `BOE-A-…`; decir cuál
está «mejor» sería el juicio propio que prohíbe la regla de oro 2. Por eso:

- La paleta es **de tono propio (violeta) y está fuera de la de alertas**: en verde o rojo se
  leería como avance/retroceso, que es el veredicto reservado al clasificador por reglas.
- **«Solo ley trans» y «solo ley LGTBI» comparten claridad** y se distinguen por trama, no por
  intensidad: son dos **ámbitos** distintos, no dos peldaños de una escala.

#### Qué se tocó

`config/watchlist.json`, `pipeline/watchlist.py`, `schemas/cobertura.py`, `api/cobertura.py`
(+3 tests, 11 en total en ese fichero), `frontend/`: `index.css` (3 tokens en claro y oscuro),
`api/client.ts`, `lib/mapa.ts`, `MapaCCAA.tsx`, `MapaPage.tsx`.

#### ⚠️ Cambio de regla: la sección 8 de CLAUDE.md se relaja

**Pedido por el humano el 2026-08-30**, con motivo de plazo: la entrega es el 10 de septiembre y
construir la configuración a mano es trabajo muy arduo. La prohibición de monitorizar prensa y
redes queda relajada **para la fase de construcción**; en mantenimiento se revisará una a una.

Escrito en la sección 8 con sus límites, que son lo que hay que respetar: la IA puede **investigar
para construir la configuración** (watchlist, fuentes, gold set) siempre que **todo lo que entre
se ancle a un identificador oficial verificado** con su fecha en la `nota`; y **nada de prensa
entra en el pipeline, ni se archiva, ni se clasifica, ni llega a una pantalla**. Las reglas de oro
2 y 3 y la CHECK `origenclasificacion` siguen intactas.

Dicho corto: **la IA ayuda a construir la lista de lo que hay que vigilar; no ayuda a decidir qué
ha pasado.**

### 🔎 Preguntarle al consolidado quién te ha reformado: 6 comunidades donde había 2 — 2026-08-30

Pedido por el humano: *«necesito que se revisen más comunidades»*. El diagnóstico llevó a un
método nuevo y a **el hallazgo más grave que ha producido el proyecto**.

#### Primero, el embudo medido, porque descarta las explicaciones fáciles

| | |
|---|---|
| Normas archivadas | 80.693 |
| Llegan al clasificador (`sospecha`/`relevante`) | 792 |
| Detecciones | 72 · **50 con veredicto** |
| Nombran una norma vigilada (2ª puerta, ADR 0024) | **17** |
| En cola de revisión / alertas | 27 / 8 |

**Nada estaba roto.** Se comprobó además que el eje de citas (ADR 0022) **sí corre** sobre las
fuentes autonómicas vía `services/cuerpo.py`, y se midió sobre los 3.123 cuerpos de BOA y BOCYL:
encuentra **48 citas de 5 normas vigiladas** —incluidas las dos leyes de Aragón— pero **todas con
verbo `CITA`**. Menciones, no reformas. El sistema funcionaba; el corpus no tenía qué encontrar.

#### La causa real: el archivo del BOE no es continuo

| año | días con boletín |
|---|---|
| 2026 | 201 |
| 2025 | 106 |
| 2024 | **11** |
| 2023 y anteriores | 1-4 por año (días sueltos del gold set) |

O sea: **~un año de cobertura real**. Con ~5 casos referenciales al año (ADR 0027), dos comunidades
es exactamente lo que cabía esperar.

#### El método nuevo, que evita backfillear años

**El texto consolidado de una ley ES su historial de reformas.** Cada versión de bloque que sirve
el BOE lleva el `id_norma` que la introdujo (ADR 0018), así que **una petición por ley vigilada**
da todas sus reformas desde su publicación hasta hoy. 19 peticiones frente a años de boletín a ~20
minutos por día.

Vive en `backend/scripts/reformas_de_vigiladas.py`. **No ingiere ni clasifica**, a propósito:
imprime qué días haría falta ingerir, y el coste lo decide una persona.

Resultado de la primera ejecución: **14 normas modificadoras en 6 comunidades** —AN, AR, CT, MD,
NC, VC— frente a las 2 que el mapa podía pintar. **7 de las 14 caían en huecos del archivo.**

#### El hallazgo, y es el que mejor explica para qué existe este proyecto

> **`BOE-A-2025-11959` — «Ley 5/2025, de 30 de mayo, de medidas fiscales, de gestión administrativa
> y financiera» — reescribió 31 bloques de la ley trans valenciana** (`BOE-A-2017-5118`).

Treinta y un bloques es **el mismo tamaño que la reforma madrileña de 2023** (34), que es el caso
insignia del proyecto y el que está en el gold set. Y su título **no contiene ni una sola palabra
del vocabulario del prefiltro**: el eje léxico no la ve, y sin su día ingerido el eje referencial
no tenía dónde mirar.

Es la definición literal de la sección 1: *la instrucción de rango bajo publicada un martes de
agosto que desmonta un derecho sin titulares* — aquí, dentro de una ley de acompañamiento
presupuestario. **Ninguna búsqueda por vocabulario la habría encontrado nunca.**

La Comunitat Valenciana tiene además otras dos de 2026 (`BOE-A-2026-9794`, `BOE-A-2026-16931`), ya
en el archivo.

#### Qué se lanzó

`backend/ingesta_reformas.sh`: ingesta **dirigida** de los 6 días que faltaban —2018-11-07,
2019-02-27, 2024-07-22, 2024-12-26, 2025-05-15, 2025-06-14—, reanudable por marcas como los otros
backfill. Los otros 8 modificadores ya estaban archivados y el prefiltro los tenía en
`relevante`.

**Aviso para leer los resultados sin pasarse de frenada:** que una norma reforme una ley vigilada
**no la convierte en un retroceso**. El signo lo deriva el catálogo de reglas y lo aprueba una
persona (reglas de oro 2 y 4). El recuento de bloques mide el **tamaño** del cambio, no su
dirección: una ley que amplía derechos también toca treinta bloques.
