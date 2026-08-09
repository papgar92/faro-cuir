# Gold set

Casos históricos etiquetados a mano para medir el pipeline con datos reales (CLAUDE.md
sección 7). El objetivo final son 150-200 casos; hoy hay 4, de arranque, para dejar montado
el mecanismo — el etiquetado en volumen lo hace el humano, por tandas.

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

- `prefiltro_esperado`: uno de los cuatro estados de 7.2 — `relevante` | `sospecha` |
  `descartada` | `pendiente`. **Se etiqueta sobre el texto íntegro**, no sobre el título
  (7.8): es lo que el prefiltro ve desde que la fase 2 descarga el día entero.
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

**El caso que hoy más falta**, y no es un negativo: una norma con **título anodino que
modifique una norma de la watchlist** — el arquetipo es una disposición final de una ley de
acompañamiento presupuestario. Mientras no exista, el eje referencial no está evaluado sino
solo declarado: los tres casos donde dispara hoy los detecta también el léxico, así que su
aportación única medida sigue siendo cero.

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
