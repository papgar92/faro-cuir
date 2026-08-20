# Gold set

Casos históricos etiquetados a mano para medir el pipeline con datos reales (CLAUDE.md
sección 7). El objetivo final son 150-200 casos; hoy hay **29** — 21 del BOE y 8 del DOGC.

**Lo que el corpus cubre y lo que no, para que nadie lea una cifra de más:**

- Las 8 del DOGC se etiquetaron el 2026-08-19 sobre las **92 normas legibles** de esa fuente.
  Las otras 172 (el 65 %) están en estado `ilegible` (ADR 0020): su cuerpo archivado es la
  página de error del portal, así que **no hay texto que etiquetar**. Cualquier medición sobre
  el DOGC es una medición sobre ese 35 %, y se publica diciéndolo.
- **En el DOGC no hay ni un caso con `referencial` en `ejes_esperados`, y no es un descuido.**
  Esa fuente no publica el bloque de referencias que alimenta el eje (medido: 0 de 92 cuerpos
  legibles, frente a 211 de 2.968 en el BOE). `dogc-24261095.json` es el caso que lo documenta:
  un decreto que deroga artículos del departamento que lleva las competencias LGTBI y al que el
  eje referencial no puede llegar.

## Cómo añadir un caso

Un fichero JSON por caso en `casos/`, con este formato (ver `esquema.py` para el detalle):

```json
{
  "identificador_oficial": "BOE-A-2023-5366",
  "fuente": "boe",
  "fecha_publicacion": "2023-03-01",
  "titulo": "Título literal tal y como lo publica la fuente",
  "organo_emisor": "Quién lo emite, si se conoce",
  "prefiltro_esperado": "relevante",
  "ejes_esperados": ["lexico", "referencial"],
  "clasificacion_esperada": null,
  "notas": "Por qué este caso importa: positivo conocido, negativo difícil, caso citado en el TFM..."
}
```

- `prefiltro_esperado`: `relevante` | `sospecha` | `descartada`. **Se etiqueta sobre el texto
  íntegro**, no sobre el título (7.8): es lo que el prefiltro ve desde que la fase 2 descarga
  el día entero. Los otros dos estados de 7.2 **no se etiquetan nunca**, y por el mismo motivo
  los dos: `pendiente` (falta el documento) e `ilegible` (está y no se puede parsear, ADR 0020)
  son estados del pipeline, no juicios humanos sobre la norma. Que el pipeline los produzca
  bien se comprueba en `tests/test_prefiltro_ilegible.py`, no aquí.
  - `relevante` y `sospecha` **cuentan igual para el recall**: las dos entran en la cola del
    extractor. La diferencia entre ellas es de orden en la cola, no de cobertura.
  - `descartada` solo es etiquetable si de verdad no hay nada; sobre el título nunca se
    descarta (7.1), y hasta la tarea 0.c ninguna etiqueta `descartada` era verificable.
- `ejes_esperados`: qué ejes deberían disparar, de `lexico` y `referencial` (7.3). Obligatorio
  si el caso pasa el filtro, y **se etiquetan los dos si aplican los dos**: es el dato que
  contesta si el eje referencial aporta casos que el léxico no ve o solo lo duplica.
- `clasificacion_esperada`: `avance` | `retroceso` | `neutro` | `indeterminado`, o `null`.
  **Desde el ADR 0016 ya es etiquetable para la familia de las supresiones**, que es la única
  que el clasificador sabe derivar hoy (una modificación necesita el texto anterior, y el BOE
  no lo publica). Dos reglas al rellenarlo:
  - Se etiqueta **lo que el documento hace**, comprobado contra el BOE, no lo que el
    clasificador diga. Copiar la salida del sistema es medir el sistema contra sí mismo.
  - Ante la duda, `null`. Un caso sin etiqueta mide poco; uno mal etiquetado miente.
- `notas`: obligatorio. Sin él, nadie sabe dentro de seis meses por qué se eligió ese caso.

**`es_relevante` es el formato viejo y ya no se etiqueta a mano.** `esquema.py` lo deriva de
`prefiltro_esperado` para no romper lo que ya lo leía. Si escribes un caso con `es_relevante`,
`test_todos_los_casos_usan_el_formato_definitivo` lo rechazará — y lo hará **después** de que
hayas gastado el recurso más caro del proyecto, que es tu tiempo de etiquetado. Este README
enseñaba el formato viejo hasta el 2026-08-09; si has copiado la plantilla antes de esa fecha,
compárala con la de arriba antes de seguir.

Casos que interesan especialmente, según el propio plan del proyecto: reformas rechazadas y
negativos difíciles (títulos de temática cercana pero fuera de alcance — sanidad reproductiva
no LGTBI+, igualdad de género no trans, etc.), no solo negativos triviales. La reforma
madrileña de 2023 ya está (`boe-a-2024-10767.json`).

**El caso que más faltaba ya está, desde el 2026-08-19.** Era «una norma con título anodino que
modifique una norma de la watchlist, cuyo arquetipo es una disposición final de una ley de
acompañamiento presupuestario», y hasta entonces el eje referencial estaba **declarado pero no
evaluado**. Ahora hay tres, y funcionan como un solo experimento:

- **`boe-a-2022-2066`** — *Presupuestos Generales de Navarra 2022*, que modifican el art. 7 de la
  ley trans navarra. **161.104 caracteres y UN solo término directo**: sin el eje referencial
  sería `sospecha`, el último puesto de la cola, en vez de `relevante`.
- **`boe-a-2021-1859`** — *ley de medidas fiscales de la Generalitat Valenciana*, que modifica la
  ley LGTBI valenciana entre cientos de artículos tributarios.
- **`boe-a-2021-1860`** — *Presupuestos de la Generalitat 2021*, publicada **el mismo día** que la
  anterior, con título igual de anodino y los mismos cuatro términos directos, pero que solo
  **cita** la ley LGTBI. Es el control: sin él, un eje referencial que disparase con cualquier
  mención pasaría el gold set igual de verde que uno correcto.

**Y el 2026-08-20 dejó de ser cierto que su aportación única fuera cero.**
`boe-a-2014-11444` —la orden que concreta el alcance de la reproducción humana asistida en la
cartera común del SNS— tiene **cero términos directos** en 43.510 caracteres, así que el eje
léxico la descarta desde el ADR 0021. Medido evaluando el mismo cuerpo dos veces: **con eje
referencial `relevante`, sin él `descartada`**. Es el caso que 7.3 describe palabra por palabra:
la instrucción que no dice «identidad de género», dice «se modifica el anexo II».

Cuidado con no mezclar dos cosas al leer esa cifra: lo que deja de ser cero es la aportación del
**eje**. La de la segunda fuente de evidencia del eje —las citas del texto, ADR 0022— sigue
siendo cero, porque aquí quien lo caza es el `<analisis>` del BOE.

No se encontraron ingiriendo días al azar: **se le preguntó al BOE**. El texto consolidado de
cada norma vigilada trae en `<analisis><referencias><posteriores>` quién la ha modificado
después, y de ahí salieron 29 normas modificadoras con la fecha exacta que había que ingerir.
Es la forma barata de buscar más casos de este tipo, y está en el repositorio como
`backend/scripts/quien_modifica.py`.

**Dos casos del DOGC hacen de raíles y conviene no tocarlos sin leer sus notas**, porque
sujetan el eje léxico por los dos lados (ADR 0021):

- `dogc-24310119.json` (`descartada`) es el falso positivo: 105.000 caracteres de currículo de
  arte floral cuya única coincidencia es «plan de igualdad» en un temario de derecho laboral.
  Es el que impide volver a dar por buena la *presencia* de un término de contexto.
- `dogc-24198092.json` (`sospecha`) entra por **un solo término directo** en 28.000 caracteres,
  y la señal es buena: el Consejo Nacional LGBTI figura en la composición de la comisión. Es el
  que impide subir el umbral de términos directos «porque los números salen mejor».

## Qué prueba hoy `test_gold_set_prefiltro.py`

El prefiltro (etapa 1) contra el **título**, sin red ni base de datos. Ojo con lo que eso
significa desde la tarea 0.c: los casos se etiquetan sobre texto íntegro y este test evalúa
sobre el título, así que **no mide el recall, mide un límite superior**. La medición de verdad
se hace contra la base de datos con los cuerpos ya archivados (`worker.run --fase2`), y ahí es
donde las etiquetas `descartada` y los ejes se pueden verificar.

## Qué prueba `test_gold_set_clasificacion.py`

La etapa 4 (catálogo de reglas, ADR 0016) contra los casos que ya tienen
`clasificacion_esperada`. Compara con la fila de `deteccion` **de la base de datos**, no con una
llamada directa al catálogo: lo que hay que medir es lo que el sistema concluye de punta a
punta, y un fallo en la cola del clasificador —que una norma ni siquiera llegue a evaluarse— es
invisible si se llama a la función a mano. Necesita PostgreSQL y el día ingerido; sin eso se
salta con el remedio escrito.

Hoy hay **una sola** etiqueta de clasificación (`boe-a-2024-10767.json`). Con una no se mide
cobertura, solo se comprueba que el mecanismo existe y que el caso que justifica el proyecto
sale bien.
