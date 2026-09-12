# ADR 0038 — Un fallo de red no puede costar un día de vigilancia

- **Fecha:** 2026-09-12
- **Estado:** aceptado
- **Relacionado con:** ADR 0006 (puerta única de salida HTTP), 0032 (la ingesta se va a la nube),
  0036 (el BON y su bisección), 0037 (el incidente del cupo), CLAUDE.md 6.2 y 6.9.6.

## Qué pasó

La pasada programada del **2026-09-11** era la prueba de fuego del ADR 0037: la primera con cuota
nueva de Backblaze después de mergear el arreglo. **El arreglo funcionó** —cero `Class B cap
exceeded` en todo el log, y los pasos que llevaban tres días cayéndose (BOA, BOCM, BOPV, fase 2 y
versionado) pasaron todos—, pero el job acabó en rojo igualmente:

```
httpx.ConnectTimeout: _ssl.c:993: The handshake operation timed out
  File "app/ingest/bon.py", line 274, in _bisecar
  File "app/security/url_guard.py", line 379, in fetch
```

Un handshake TLS que expiró en **una** de las hasta 16 peticiones que el BON necesita para
resolver qué boletín toca. El día de Navarra no se ingirió, y **nadie lo va a recuperar**: la
ingesta siempre pide «hoy», así que un día que se cae no vuelve a intentarse nunca salvo que una
persona lance el `workflow_dispatch` a mano.

## Las dos cosas que estaban mal, y son distintas

### 1. Nadie cogía los errores de transporte

`_ingerir_dia` (`worker/run.py`) atrapaba `SumarioNoDisponible`, `UrlGuardError`, `XmlSafeError` y
`BoeIngestError`. Un `httpx.ConnectTimeout` no es ninguna de las cuatro: subía hasta `__main__` y
**rompía el proceso con un traceback**.

Y hay una promesa escrita tres líneas más arriba, en el bucle de días de `main`:

> «Un día sin boletín o un fallo de red **no interrumpe el rango**: un domingo por medio no puede
> dejar sin ingerir el resto del mes.»

Eso era falso para un fallo de red de verdad. El `for` no llegaba a la siguiente iteración porque
la excepción no la cogía nadie: un backfill de seis meses se cortaba en el primer timeout. Un
comentario que afirma un comportamiento que el código no tiene es peor que no tenerlo, porque
quien lo lee deja de comprobarlo — la misma lección que la lista de siete pasos de TRABAJO.md.

### 2. No se reintentaba nada

El único remedio que había contra un fallo de red era el timeout, y ya se tocó: subió de 5 s a
20 s el 2026-09-05 al estrenar la ingesta en Actions. **No es la respuesta a esto.** El del 11 no
fue un margen corto —el handshake llegó a agotar los 20 s— sino un intento que no se repitió.

El BON es además el más expuesto por construcción y eso no es mala suerte: no tiene calendario y
su búsqueda por fecha miente, así que cada día se resuelve por bisección (ADR 0036) y hace hasta
16 peticiones donde las demás fuentes hacen una o dos. **Con 16 tiradas diarias contra un servidor
autonómico, que ninguna falle nunca no es una expectativa razonable.**

## Decisión

### 1. `url_guard` reintenta los fallos de transporte, y solo esos

`ESPERAS_REINTENTO = (1.0, 4.0)`: dos reintentos, o sea hasta tres intentos. La longitud de la
tupla **es** el número de reintentos, y hay un test que lo fija para que nadie lo lea al revés.

La raya está en qué se reintenta, y es lo único importante de este ADR:

| | Se reintenta | Por qué |
|---|---|---|
| `httpx.TransportError` (connect, handshake, read timeout del envío) | **Sí** | No hubo respuesta. Repetir es preguntar otra vez. |
| Rechazo del guardia (`UrlGuardError`) | **No, jamás** | Repetir una petición a una IP privada es repetir el intento de SSRF. |
| Error de estado de la fuente (`HTTPStatusError`) | **No** | Un 404 no mejora insistiendo, y hay quien lo interpreta (un 404 del BOCM significa «no hubo boletín»). |
| Corte a mitad del cuerpo | **No**, pero se tipa | Media descarga no se repite: no hay respuesta a medio consumir de la que volver atrás. |

Va en `url_guard` y no en cada fuente por lo mismo que va allí todo lo demás: **es la única
puerta de salida HTTP** (ADR 0006), así que la regla se escribe y se prueba una vez. Ponerlo en
`bon.py` habría dejado a las otras seis fuentes con el defecto, y a la octava también.

Lo que hace esto seguro de repetir es que **todas las peticiones del proyecto son `GET` de
documentos públicos**. Queda dicho en el docstring: si algún día sale un método con efectos, este
reintento no vale para él.

El primer fallo se registra a `warning` aunque el segundo intento salga bien. No es ruido: una
fuente que necesita dos intentos todos los días es una fuente que se está cayendo despacio, y sin
la línea en el log eso no se ve hasta que se cae del todo.

### 2. Un fallo de red tiene nombre propio: `FalloDeRed`

**No hereda de `UrlGuardError`**, y la distinción es la misma que el ADR 0037 celebró en
`AlmacenRemotoCaido`. `UrlGuardError` es la familia de los **rechazos**: llegó algo y decidimos no
aceptarlo, que es un hallazgo de seguridad y `_ingerir_dia` lo reporta como tal, con salida 3 y un
log aparte para que no se pierda entre los fallos rutinarios de red. Un timeout es lo contrario:
no llegó nada. Meterlo en esa familia habría llenado de fallos rutinarios de red exactamente el
registro que existe para que un rechazo no se pierda entre ellos.

**Sí hereda de `httpx.TransportError`**, y eso tampoco es cosmético: `texto_integro`, `versionado`
y `recuperacion_pdf` ya tratan los fallos de red **por documento** con `except httpx.HTTPError` —
anotan y siguen, que es por qué la fase 2 y el versionado sobrevivieron al día 11 mientras el BON
tiraba el job. Un tipo nuevo fuera de esa jerarquía habría convertido un fallo que hoy se anota y
se reintenta mañana en una pasada rota. Hay un test que fija esa herencia y dice por qué.

### 3. `_ingerir_dia` sale con 1, no con un traceback

Salida 1 es «hoy esta fuente no se ha ingerido»: el cron lo ve en rojo, como exige 6.9.6, pero se
distingue de un día sin boletín (0) y de un control de seguridad (3). Y el bucle de días del
backfill llega ahora a la iteración siguiente, que es lo que `main` prometía desde el principio.

El `except` va **antes** que el de `UrlGuardError` a propósito, aunque hoy no sean parientes: si
alguien los emparentara —tentador, porque salen del mismo módulo—, el orden sigue impidiendo que
un timeout se registre como hallazgo de seguridad.

## Lo que NO se hace

- **Subir otra vez el timeout.** Ya se probó y este incidente demuestra que no es eso. Un timeout
  más largo solo hace que una fuente caída retenga al worker más rato.
- **Reintentar los 5xx.** Es tentador y es otra decisión: un 503 sí podría mejorar insistiendo,
  pero un 500 persistente convertiría cada pasada en tres. Si hace falta, con su medición.
- **Recuperar automáticamente los días que se perdieron.** El sistema **sigue sin tener** ninguna
  forma de darse cuenta sola de que le falta el 11 de septiembre de Navarra. Este ADR hace que un
  timeout deje de crear el hueco; **no crea el mecanismo que rellena los que ya hay**. Lo que hoy
  lo hace visible es la página de cobertura, que publica `ultima_publicacion` por fuente — pero
  hace falta que alguien la mire. Un barrido de los últimos N días por fuente es la solución y
  necesita su propio ADR: cuesta peticiones a diario para un caso raro, y esa cuenta hay que
  echarla, no suponerla.
- **Tocar el tope de sondeos del BON.** Los reintentos son de transporte y no cuentan como
  sondeos: `MAX_SONDEOS` sigue acotando lo que se le pide a la fuente a ciegas, que es de lo que
  protege.

## Consecuencias

- Un handshake que expira deja de costar un día de boletín, y deja de cortar un backfill.
- En el peor caso una petición se convierte en tres, con 5 s de espera acumulada. Solo cuando
  falla: una pasada sana no cambia en nada.
- `fetch` gana `esperas_reintento`, inyectable, para que la suite pruebe el reintento sin dormir.
- Siete tests nuevos en `test_url_guard.py` y dos en `test_worker_argumentos.py`. Los que valen
  no son los que comprueban que reintenta, sino los cuatro que comprueban **qué no se reintenta**:
  ese fallo no daría ningún síntoma visible, porque la petición acaba rechazada igual.
