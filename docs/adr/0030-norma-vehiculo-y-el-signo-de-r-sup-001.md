# ADR 0030 — La norma-vehículo, y por qué R-SUP-001 deja de afirmar signo sobre ella

- **Fecha:** 2026-08-30
- **Estado:** aceptado
- **Continúa a:** ADR 0023 (el verbo tiene que ir pegado a la norma) y ADR 0027 (el límite medido
  del eje referencial).

## Contexto

La watchlist tenía 27 normas y **todas eran protectoras**: leyes LGTBI y trans, autonómicas o
estatales. Sobre ese supuesto se escribió R-SUP-001, la única regla del catálogo que afirma signo:

> Si el documento suprime preceptos y la referencia declara que los suprimidos son de una norma
> vigilada, entonces es **retroceso, severidad 4**.

El razonamiento está en el docstring de `clasificar()` y era correcto: *suprimir un precepto de una
norma de derechos no tiene lectura buena; no hace falta saber qué ocupa su lugar, porque no lo
ocupa nada.*

El informe del `jurista-lgtbi` del 2026-08-23 dejó preparadas **15 candidatas más**, todas con
identificador y título ya verificados contra boe.es, y **bloqueadas a propósito** por este motivo,
escrito entonces en `_pendientes_de_verificar`. El humano pidió el 2026-08-30 ampliar la lista.

## El problema, en una frase

**Esas 15 no son protectoras: son vehículos.** La LOE, el Registro Civil, la Ley 16/2003 del SNS,
el Reglamento Penitenciario, la Ley del Deporte. El derecho del colectivo vive en dos o tres
preceptos y el resto es materia ajena.

Con el supuesto de R-SUP-001 intacto, **suprimir el artículo 33 de la Ley 16/2003 —formación
sanitaria especializada— se publicaría como retroceso LGTBI de severidad 4.** Eso es un juicio
falso, y de los caros: publicado, con signo, y sin nada del colectivo dentro.

Es **el error del ADR 0023 un nivel más arriba**. Allí la supresión y la norma vigilada coexistían
en el **documento** sin tener que ver —una ley extensa que suprime algo y además toca la
watchlist—. Aquí coexistirían **dentro de la norma vigilada**.

## Lo que se midió antes de decidir

Con `scripts/reformas_de_vigiladas.py` (creado el mismo día) se consultó el historial completo de
reformas de las 15 candidatas: **95 normas modificadoras distintas**, frente a **14** para las 19
leyes autonómicas protectoras. La Ley del SNS sola lleva 21; el Reglamento del Registro Civil, 16.

Ese contraste es el argumento entero: son normas de alta frecuencia de reforma, y la inmensa
mayoría de esas reformas no tiene nada que ver con el colectivo.

**Lo que llega a la cola es otra cosa y también está medido:** el censo de 27.016 disposiciones del
2026-08-23 dio **5 casos en un año de corpus** para estas 15. El 95 es el histórico de décadas; a
la cola llega lo que esté archivado. O sea que ampliar la lista **no inunda el gate**, siempre que
no afirme signo donde no puede.

## Decisión

**Entran las 15, con un campo que dice qué clase de norma es cada una.**

### 1. `NormaVigilada.especificidad`: `lgtbi` | `vehiculo`

- `lgtbi`: norma protectora, toda ella sobre derechos del colectivo. Las 27 anteriores.
- `vehiculo`: norma de materia ajena donde el derecho vive en unos pocos preceptos. Las 15 nuevas.

**El valor por defecto es `lgtbi`**, y la asimetría es deliberada: equivocarse hacia `vehiculo`
apagaría el signo de una norma que sí lo merece, y eso se nota mucho menos que lo contrario.

### 2. R-SUP-001 afirma signo solo si lo suprimido es protector

Si todas las normas suprimidas son `vehiculo`, el veredicto cae a `indeterminado` con severidad 3.

**Y no pierde nada más:** conserva su regla, su evidencia con offsets, sus normas suprimidas y su
diff archivado, y **sigue entrando en la cola de revisión** porque identifica una norma vigilada
(ADR 0024). Lo resuelve una persona leyendo qué precepto se suprimió, que es exactamente lo que el
gate humano existe para hacer.

Es literalmente la frase del ADR 0023: **perder el signo no es perder la vigilancia.**

### 3. Suben las dos versiones, y una es cara

- `VERSION_REGLAS` → `2026.08.30.2`. Cambia un veredicto, así que hay que reclasificar.
- La `version` de la watchlist → `2026.08.30`. **Esta sí devuelve las ~82.000 normas a la cola del
  prefiltro**, y es correcto: 15 normas vigiladas nuevas cambian de verdad lo que el eje
  referencial puede detectar, y lo evaluado antes se evaluó sin ellas. Es lo contrario del caso de
  `tipo` y `vigente` del mismo día, que no subieron versión porque no cambiaban ningún resultado.

Y con ella el catálogo publicado en `frontend/src/lib/reglas.ts`, que ahora enuncia la distinción:
lo obliga `test_catalogo_publicado`, para que la web no explique un criterio que ya no se aplica.

## Alternativas consideradas

- **No añadirlas.** Es lo que llevaba una semana. Deja fuera el Registro Civil y la Ley del SNS,
  que son por donde pasan el cambio registral de nombre y sexo y el acceso a tratamientos: dos de
  los caminos por los que un derecho se pierde sin tocar ninguna ley LGTBI.
- **Añadirlas sin el campo.** Es el juicio falso descrito arriba, publicado con severidad 4.
- **Vigilar preceptos concretos en vez de normas enteras** (`preceptos: ["art. 33"]`). Es la
  solución **más precisa** y probablemente la correcta a medio plazo: convertiría 95 candidatas
  históricas en un puñado. Se descarta hoy por dos motivos: exige investigación jurídica norma a
  norma —qué artículo exacto sostiene el derecho en cada una— y el ADR 0024 ya filtra por otra vía.
  **Queda anotada como la continuación natural de este ADR**, no como un descarte.
- **Excluir las de frecuencia excesiva**, como ya se hizo con el Estatuto de los Trabajadores y el
  Código Penal. Se mantiene ese descarte —siguen fuera— pero no se extiende: la Ley del SNS se
  modifica a menudo y aun así es donde vive la cartera de servicios.

## Consecuencias

- **La watchlist pasa de 27 a 42 normas.** 27 protectoras y 15 vehículo.
- **R-SUP-001 deja de ser «la regla que siempre afirma signo»** y pasa a afirmarlo condicionado.
  Es el primer criterio del catálogo que depende de un atributo de la watchlist y no solo del
  texto; la watchlist es un fichero versionado del repositorio, así que la auditabilidad se
  mantiene: un tercero puede reconstruir el veredicto leyendo la regla, el texto archivado y el
  JSON.
- **Un reprocesado completo del prefiltro**, que es la parte cara de esta decisión.
- **El Reglamento del Registro Civil de 1958 es invisible para el eje de citas.** Su rango no lleva
  número, así que `cita_esperable()` es `False` (ADR 0022) y solo puede disparar por el `<analisis>`
  del BOE. Queda dicho aquí porque es un hueco real y no un descuido.
- **Dos de las 15 tienen historial cero** (el RD 217/2022 de la ESO y el RD 255/2025 del DNI). Se
  vigilan por lo que puede pasarles, no por lo que les ha pasado. *Un cero en una norma viva no es
  un fallo: es la lista haciendo su trabajo, esperando.*
