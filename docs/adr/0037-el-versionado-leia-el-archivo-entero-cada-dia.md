# ADR 0037 — El versionado leía el archivo entero cada día, y en la nube eso cuesta dinero

- **Fecha:** 2026-09-09
- **Estado:** aceptado
- **Relacionado con:** ADR 0032 (el archivo se va a un bucket), 0018 (el versionado), 0027 (el
  límite medido del eje referencial), CLAUDE.md 6.2 y 6.9.6.

## Qué pasó

El 2026-09-09 la ingesta diaria de GitHub Actions empezó a fallar:

```
botocore.errorfactory.AccessDenied: Cannot download file, download bandwidth
or transaction (Class B) cap exceeded.
```

Se había agotado el **cupo diario gratuito de Backblaze B2**. No fue un pico de uso ni una
fuente que creciera: es un defecto que llevaba desde el ADR 0032 y que solo podía manifestarse
al mover el archivo a un bucket.

**Una cosa funcionó exactamente como se diseñó**, y conviene anotarlo: `AlmacenRemotoCaido` no
hereda de `OSError` a propósito, así que el fallo **paró la pasada en alto** en vez de marcar
miles de normas como `ilegible`. Un archivo inaccesible no es una norma ilegible, y esa
distinción —que en su día parecía un detalle de tipos— es lo único que impidió que un problema
de facturación se convirtiera en corrupción del embudo.

## La causa, medida

`services/versionado.poblar` recorre su cola y llama a `_objetivos(norma)` para cada una.
`_objetivos` **lee el cuerpo archivado** para ver qué normas vigiladas toca.

Sobre la base del 2026-09-09:

| | |
|---|---|
| Normas en la cola del versionado | **928** |
| De esas, con el eje referencial disparado | **120** |
| Leídas del almacén cada día para devolver una tupla vacía | **808** |

Y no era una vez: **`versionado_intentado_en` solo se escribe cuando la norma llega a
consultarse contra el BOE**, o sea nunca para las 808. Así que volvían a leerse enteras al día
siguiente, y al otro, indefinidamente.

Con el archivo en un disco local eso era una lectura gratis y nadie lo habría notado nunca. Con
el archivo en un bucket, cada una es una transacción facturable.

### El agujero conceptual, que es lo que hay que llevarse de aquí

La sección 6.2 pone dos frenos —tope por ejecución y pausa— y los pone **sobre las peticiones a
las fuentes externas**. `versionado_max_por_ejecucion = 20` acota las consultas al BOE, y lo
hace bien. Lo que nadie puso, porque cuando se escribió no hacía falta, es un freno sobre las
lecturas del **archivo propio**.

El ADR 0032 movió el archivo a un servicio de terceros con cuota y **no revisó qué partes del
pipeline lo leen en barrido completo**. Esa es la lección: mover un recurso de local a remoto no
es solo cambiar dónde está; es cambiar qué cuesta tocarlo, y hay que ir a mirar quién lo toca.

## Decisión

Dos cambios, y el primero no es una optimización.

### 1. La cola del versionado se filtra por el eje referencial

`_cola` añade `prefiltro_ejes` contiene `referencial`.

**Es sin pérdida por construcción, no por probabilidad**, y se comprobó leyendo las dos
condiciones una al lado de la otra:

| | Condición |
|---|---|
| `_objetivos` (versionado) | `referencia.es_modificativa and lista.buscar(id)` |
| Eje 2 (prefiltro) | `referencia.es_modificativa and lista.contiene(id)` |

El mismo predicado, sobre las mismas referencias del mismo cuerpo. Una norma sin ese eje tiene
`_objetivos` vacío necesariamente.

Y se comprobó además **contra el corpus real**, no solo leyendo el código: se recorrieron las
808 normas que el filtro descarta y se ejecutó `_objetivos` sobre cada una. Ninguna tenía
objetivos. Una equivalencia razonada que además se mide es lo que separa esto de una
optimización con los dedos cruzados.

**La dependencia que crea, escrita para que no se descubra tarde:** el versionado pasa a
depender de que el prefiltro se haya pasado con la watchlist vigente. Al subir
`VERSION_WATCHLIST` hay que lanzar `--reprefiltrar` **antes** que `--versionar`. Ese orden ya
era el correcto por otros motivos; ahora además es obligatorio, y está dicho en el propio
`_cola` y en la sección 10.

### 2. Un tope de lecturas del almacén, que es el freno que faltaba

`versionado_max_lecturas_por_ejecucion = 400`. Con el filtro anterior la cola real son ~120, así
que **este tope no debería morder nunca**, y está justamente para eso: es lo que sigue habiendo
el día que alguien amplíe esa cola sin darse cuenta de lo que cuesta. Un límite que solo se nota
cuando el diseño falla es lo que la 6.2 llama freno propio.

Lo que queda fuera del tope **se cuenta como pendiente y sale en el resumen**: no se trunca en
silencio, por el mismo motivo que el resto de topes del proyecto.

## Lo que NO se hace

- **Subir el cupo de B2.** Cuesta dinero, y el proyecto es de coste 0 € (sección 0 bis). Además
  sería pagar por seguir leyendo 808 ficheros al día que no aportan nada.
- **Persistir `referencias_watchlist` en una columna.** El prefiltro ya calcula qué normas
  vigiladas toca cada una (`pipeline/prefiltro.py`, línea 433) y **no lo guarda**. Persistirlo
  bajaría las lecturas de ~120 a **cero** y es la solución completa; se deja fuera de este ADR
  porque exige columna y migración, y el filtro por eje ya resuelve el incidente. Queda anotado
  como lo siguiente que hacer aquí, no como una idea.
- **Dejar de reintentar lo que nunca se consolida.** Sigue igual (ver el docstring del módulo):
  una petición al día contra una fuente pública es asumible, y marcarla como agotada haría que
  el sistema dejara de mirar justo lo que puede aparecer más tarde.

## Consecuencias

- La ingesta diaria vuelve a caber en el cupo gratuito. Las lecturas del almacén por pasada
  bajan de ~928 a ~120.
- `poblar` gana el parámetro `max_lecturas`, y `worker/run.py` lo pasa desde la configuración.
- **Un backfill local no toca el bucket**, y para que eso sea difícil de hacer mal existe
  `docker-compose.local.yml`: el `.env` de la máquina apunta a Neon y a B2 porque hace falta
  para operar la nube, y trabajar con esa configuración era escribir en producción sin querer.
