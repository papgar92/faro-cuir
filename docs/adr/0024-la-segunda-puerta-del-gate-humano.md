# ADR 0024 — La segunda puerta del gate humano: suprimir a quien vigila

- **Fecha**: 2026-08-20
- **Estado**: aceptado
- **Contexto de tarea**: investigación del `jurista-lgtbi` sobre ILGA-Europe, FELGTBI+ y Amnistía
  (entrada de ESTADO del 2026-08-20). Decisión tomada por el humano con la medición delante.
- **Números libres**: el siguiente libre tras este es el **0025**.

## Contexto

El ADR 0017 cerró el gate humano a lo que no señala una norma vigilada, y lo cerró con datos:
`R-SUP-002` —«hay una supresión pero no se identifica ninguna norma de la watchlist»— iba **10 de
10 descartadas** por la persona que revisa, porque dispara con cualquier «se suprime el artículo
7» de cualquier materia. Una cola llena de ruido deja de mirarse, y ahí es donde un gate humano
se vacía por dentro sin que nadie lo desactive.

Ese filtro también dejaba fuera un caso que **nadie había mirado**, y lo señaló el jurista al
contrastar el catálogo con los vectores que documentan las organizaciones de referencia:

> Un decreto autonómico de reestructuración dice «Se suprime el Consejo LGTBI de Aragón».

Desaparece el órgano que vigila el cumplimiento de la ley. Pero **ese consejo lo creó un decreto
que no está en la watchlist** —la watchlist tiene leyes, no los decretos que crean consejos— así
que la evidencia no nombra ninguna norma vigilada, la detección se crea, no se encola y **nadie la
ve jamás**. No se pierde un derecho: se pierde el mecanismo que lo hace exigible, que es el vector
7 de la lista del proyecto.

## Decisión

**El gate humano acepta una segunda cosa: que la evidencia señale un órgano del ámbito.** Se
comprueba por el **contenido** de la evidencia (`evidencia_json.organos_afectados`) y no por el
identificador de la regla, exactamente igual que `normas_vigiladas` — así una regla futura entra
o se queda fuera sola, sin que nadie tenga que acordarse de mantener una lista.

Y una regla que lo produzca, **R-SUP-003**, con las dos condiciones **sobre la misma cláusula**:

1. La cláusula la ha detectado ya `supresiones()` (construcción operativa + precepto).
2. Esa misma cláusula nombra un **órgano** (`consejo`, `observatorio`, `comisión`, `mesa`,
   `dirección general`, `comisionado`) **y** contiene un **término DIRECTO** del vocabulario.

Veredicto `indeterminado`, severidad 3, **sin signo** — por lo mismo que R-DER-001: suprimir un
consejo puede ser desmantelarlo o fundirlo con otro, y cuál de las dos cosas es exige saber qué
ocupa su lugar. Eso lo decide una persona.

**Las dos condiciones van juntas sobre la misma cláusula, y eso es el ADR 0023 aplicado antes de
cometer el error en vez de después.** Comprobar «hay una supresión de órgano» y «se habla del
colectivo» por separado sobre un documento de 400.000 caracteres las hace coincidir por azar: es
literalmente el fallo que costó 2 falsos positivos de 4 en R-SUP-001. Hay un test que siembra las
dos condiciones en cláusulas distintas del mismo texto y exige que **no** dispare.

## Lo que se midió antes de abrir la puerta, y lo que no se puede medir

**Cuántos ítems añade hoy a la cola: cero.** De las 10 detecciones de `R-SUP-002` del corpus
(5.999 normas, 164 boletines), **ninguna** tiene un término directo dentro de la cláusula
suprimida, y ninguna nombra un órgano. La puerta se abre y hoy no pasa nadie por ella.

Eso tiene dos lecturas y las dos son ciertas:

- **A favor:** el coste en ruido es exactamente cero, así que no reabre lo que el ADR 0017 cerró.
- **En contra, y hay que decirlo:** **la precisión de R-SUP-003 está sin observar**. Es la primera
  regla del catálogo que entra sin un documento del corpus delante — R-SUP-001 salió de la reforma
  madrileña, R-DER-001 de la Ley 4/2023, el ADR 0021 de un currículo de arte floral y el 0023 de
  la ley catalana. Esta entra por un vector documentado por las organizaciones de referencia
  (supresión de consejos y observatorios autonómicos y municipales) pero **no verificado sobre
  texto real de este archivo**.

Se acepta esa excepción a la costumbre de la casa a sabiendas y con la excepción escrita, del
mismo modo que `_SUPRESION` incluye «queda sin contenido» sin haberla visto nunca en el corpus.
**Si algún día dispara mucho, este es el primer sitio donde mirar.**

## Alternativas descartadas

**Dejarlo como límite conocido y escribirlo en `docs/`.** Era la recomendación con la que llegué
al humano tras ver el cero, y la descartó él. Su argumento es bueno: el coste es nulo y el día que
ocurra el caso, ocurrirá **una sola vez y en un boletín autonómico**, sin segunda oportunidad.

**Aceptar cualquier `R-SUP-002` que contenga un término directo en el documento.** Es la puerta
ancha que el ADR 0017 cerró con 10 descartes de 10. No se reabre.

**Meter «servicio», «área» o «instituto» en la lista de órganos.** Los tres son demasiado
frecuentes en el BOE —«instituto» es casi siempre un centro docente— y devolverían el problema de
precisión por la puerta de atrás. La lista es corta a propósito, igual que `VERBOS_MODIFICATIVOS`.

## Consecuencias

- `VERSION_REGLAS` sube a `2026.08.20.3`. La reclasificación no cambia ninguna detección
  existente, como estaba previsto.
- `Veredicto` gana `organos_afectados`, que viaja a `evidencia_json` junto a `normas_vigiladas`.
  Las dos hacen el mismo trabajo: decirle al gate por qué esta detección merece que alguien la
  mire.
- El aviso del informe del jurista —«esta regla hoy no llegaría a nadie»— queda resuelto: la regla
  y la puerta se han escrito **a la vez**, que es lo que él pedía y por lo que lo señalaba.
- Lo que sigue sin verse, y no lo arregla este ADR: **el caso peor del vector 3 es que una
  convocatoria de subvenciones simplemente no se publique**. Ningún catálogo de reglas sobre
  documentos puede ver la ausencia de un documento.
