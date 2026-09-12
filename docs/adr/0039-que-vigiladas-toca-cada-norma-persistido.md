# ADR 0039 — Qué vigiladas toca cada norma, persistido: el versionado deja de releer el archivo

- **Fecha:** 2026-09-12
- **Estado:** aceptado
- **Relacionado con:** ADR 0037 (el incidente del cupo, arreglado a medias), 0032 (el archivo se
  va a un bucket), 0022 (las citas dentro del texto), 0018 (el versionado), 0020 (`ilegible`),
  CLAUDE.md 6.2, 6.9.6 y 7.2.

## Contexto

El ADR 0037 dejó escrito, en su propio apartado de «lo que no se hace», qué faltaba:

> **Persistir `referencias_watchlist` en una columna.** El prefiltro ya calcula qué normas
> vigiladas toca cada una (`pipeline/prefiltro.py`, línea 433) y **no lo guarda**. Persistirlo
> bajaría las lecturas de ~120 a **cero** y es la solución completa; se deja fuera de este ADR
> porque exige columna y migración, y el filtro por eje ya resuelve el incidente.

Esto es esa columna. Y el diagnóstico era exacto: el valor **ya se calculaba** desde el ADR 0022,
viajaba dentro de `ResultadoPrefiltro` con su propio campo y su comentario, y `services/prefiltro`
lo tiraba al escribir la fila porque no había dónde ponerlo.

Lo que quedaba después del 0037 eran ~120 lecturas del bucket cada día para recalcular, norma a
norma, un dato que ya se había calculado esa misma mañana unas líneas más arriba.

## Decisión

### 1. Dos columnas en `norma`, las dos nullable

- **`referencias_watchlist`** (JSON) — los identificadores de las vigiladas que esta norma
  modifica o deroga.
- **`referencias_watchlist_version`** (varchar 20) — con qué versión de la watchlist se calculó.

**`prefiltro_version_watchlist` no vale para esto**, y el motivo es el punto 3. La segunda columna
parece un duplicado hasta que se ve quién más escribe la primera.

### 2. NULL y `[]` significan cosas distintas, y ahí está todo el riesgo

| Valor | Significa | Qué hace quien lo lee |
|---|---|---|
| `[]` | Se leyó el cuerpo y **no toca ninguna** vigilada | Nada. No hay objetivos. |
| `NULL` | **No se sabe** | Ir al almacén. |

Por eso la columna **solo se escribe cuando el prefiltro evaluó sobre el cuerpo**. Sobre el título
no hay referencias que mirar (7.1) y una norma `ilegible` tampoco las tiene (ADR 0020): en los dos
casos un `[]` afirmaría «no toca ninguna» cuando lo cierto es «no se ha mirado».

Es exactamente la misma regla que ya gobierna `prefiltro_version_texto`, tres líneas más arriba en
el mismo bloque, y se escribió al lado a propósito para que se lean juntas.

**Y el fallo que esto evita no tiene síntoma.** Si NULL se tratara como vacío, el versionado se
saltaría normas con objetivos reales, la pasada saldría verde, el resumen diría «0 candidatas» sin
mentir, y la vigilancia estaría rota. Es el fallo silencioso de 6.9.6, con la agravante de que
aquí se manifestaría como un ahorro: menos lecturas, menos tiempo, todo aparentemente mejor.

### 3. El versionado rellena la columna cuando la encuentra a NULL

Si hubiera que esperar a un `--reprefiltrar` para poblarla, las ~120 normas que **ya** están en la
cola seguirían leyéndose del bucket cada día hasta que alguien lanzase un reproceso de ~82.000
normas — que es justo lo que la nube no puede permitirse y está escrito en la nota final de
`.github/workflows/ingesta.yml`. Rellenándola al paso, el coste es **una lectura por norma y nunca
más**: la diferencia entre pagar una vez y pagar a diario.

Eso obliga a la segunda columna. El versionado **no puede** escribir en
`prefiltro_version_watchlist`: diría que se reevaluó el prefiltro entero cuando solo se ha
recalculado un dato, y la próxima reevaluación se saltaría esa norma creyéndola al día.

### 4. La caché caduca sola

`_cache_utilizable` exige que `referencias_watchlist_version` sea **la de la watchlist en uso**. Al
subir `VERSION_WATCHLIST`, una norma puede pasar a tocar una vigilada nueva sin que su fila cambie;
sin la comprobación, el versionado usaría una lista de objetivos calculada con la watchlist
anterior.

Esto **no elimina** la dependencia que el ADR 0037 dejó escrita —`--reprefiltrar` antes que
`--versionar`, porque la cola sigue filtrándose por el eje referencial, que también se queda
viejo— pero tampoco la agrava, y dentro de su alcance se protege sola en vez de confiar en que
alguien recuerde el orden.

### 5. El tope de lecturas pasa a contar lecturas de verdad

`max_lecturas` acota lecturas del almacén (ADR 0037). Con la columna, una norma servida desde ella
cuesta **cero**, así que gastar presupuesto con ella dejaría fuera de la pasada trabajo que ya no
cuesta nada — lo contrario de lo que el freno protege. Ahora solo consume tope quien de verdad
va al archivo.

### 6. El resumen publica cuántas lecturas hizo

`ResumenVersionado.lecturas_almacen`, y sale en el log del worker. Eran ~928 al día antes del ADR
0037, ~120 después, y deben tender a 0. **Un ahorro que no se puede ver desde fuera es un ahorro
que nadie nota el día que deja de producirse**, y este proyecto ya se comió un incidente por no
tener a la vista lo que costaba una etapa.

## Alternativas descartadas

- **Rellenar las ~84.000 filas en la migración.** Exigiría leer sus cuerpos del almacén —lo que
  esta columna existe para no hacer— y encima dentro de una transacción de esquema. Quedan a NULL,
  que es literalmente lo que significa: no se sabe.
- **Reutilizar `prefiltro_version_watchlist` y no añadir la segunda columna.** Obligaría a que solo
  el prefiltro pudiera escribir la caché, y con eso vuelve el goteo diario del punto 3.
- **Guardar las referencias completas** (con verbo y texto citado) en vez de los identificadores.
  El versionado solo necesita a quién toca; el resto ya está en el cuerpo archivado, que es la
  evidencia, y duplicarlo crearía dos copias que pueden discrepar.

## Consecuencias

- Las lecturas del almacén por pasada de versionado tienden a **0** en régimen. Con el ADR 0037
  eran ~120; antes de él, ~928.
- La primera pasada tras desplegar esto **sí** lee: una vez por norma en cola, y ya no más.
- Nueve tests nuevos. Los que importan no son los que comprueban el ahorro, sino los que fijan que
  NULL no es `[]`, que una versión caducada obliga a releer y que rellenar la caché no miente
  sobre el prefiltro. El ahorro se nota si falla; lo otro, no.
- **La migración añade dos columnas nullable y ninguna CHECK.** El recuento del `SELECT ... FROM
  pg_constraint` de la sección 10 sigue en 15, comprobado sobre base vacía.
