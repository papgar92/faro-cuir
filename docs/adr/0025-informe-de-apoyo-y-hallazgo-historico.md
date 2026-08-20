# ADR 0025 — El informe de apoyo, y el hallazgo histórico que no es una alerta

- **Fecha**: 2026-08-20
- **Estado**: aceptado
- **Contexto de tarea**: decisión de producto del humano tras leer el primer dosier del
  `jurista-lgtbi` sobre la cola de revisión (entrada de ESTADO del 2026-08-20).
- **Números libres**: el siguiente libre tras este es el **0026**.

## Contexto

El pipeline llega hasta la cola del gate humano con la evidencia del catálogo de reglas: la
cláusula, sus offsets sobre el texto archivado y, desde el ADR 0018, el antes y el después. Eso es
suficiente para que decida quien conoce el dominio. **No lo es para quien no.**

El proyecto está pensado para que lo use una asociación, y quien revise puede ser una persona
voluntaria. El primer dosier escrito por el subagente `jurista-lgtbi` sobre las siete normas
pendientes redujo esa cola a cuatro minutos de trabajo: semáforo, qué hace la norma en una frase
sin jerga, la cita literal, a quién afecta, una recomendación y **qué la refutaría**.

Ese material vivía en una conversación. La decisión es meterlo en el producto.

## Decisión 1 — El informe vive en su propia tabla y no toca lo que el sistema afirma

`informe_revision`, colgando de `cola_revision`. **Nunca de `deteccion`.** La clasificación
`avance`/`retroceso` la siguen escribiendo las reglas (ADR 0004 y 0016) y la CHECK
`origenclasificacion` lo sigue haciendo cumplir. Si se borrara la tabla entera de informes,
**ninguna alerta cambiaría de signo**: esa es la prueba de que la separación es real y no
nominal.

Tres campos son obligatorios y los tres por el mismo motivo — que quien revise pueda llevarle la
contraria sin releerse el BOE:

- **`citas`**, los fragmentos literales del texto archivado. Sin ellos esto es una opinión.
- **`recomendacion`**, qué haría el asistente y por qué.
- **`refutacion`**, qué tendría que ver quien revisa para decidir lo contrario. Es **NOT NULL en
  el esquema** y se rechaza antes en el importador: sin ese campo, la recomendación funciona como
  un sello de goma y el gate humano se convierte en un trámite de confirmación. Es el mismo
  riesgo de anclaje que la sección 13.4 describe para este agente, resuelto donde se puede
  imponer.

**El semáforo no es el signo.** `alerta` significa «yo publicaría esto», no «esto es un
retroceso»: de los tres primeros informes que recomiendan alerta, **dos son avances**. Por eso es
un enum propio y no `Clasificacion`.

## Decisión 2 — La generación vive fuera del sistema, y se dice

El informe entra por `worker.run --importar-informes fichero.json`, escrito hoy por una sesión de
Claude Code con el subagente `jurista-lgtbi`. **No lo genera el backend, y no es por comodidad.**

El único modelo que el proyecto puede permitirse es el Ollama local de 3B (ADR 0008, coste 0 €), y
su rendimiento sobre este corpus está medido: **36 % de timeouts a 180 s y la mitad de las
respuestas sin anclar al archivo** (ESTADO, 2026-08-18). Ese modelo no escribe estas fichas. Un
panel que dijera «análisis del asistente» con un 3B detrás prometería algo que el sistema
desplegado no hace, que es exactamente lo que este proyecto se dedica a denunciar.

Por eso cada informe guarda `generado_por` y `generado_en`, y la interfaz tiene que enseñarlos:
**«esto lo preparó un asistente de IA el día X y no lo ha revisado nadie»**. El día que exista un
modelo local capaz, lo único que cambia es quién escribe el JSON.

## Decisión 3 — El hallazgo histórico, y por qué no es una alerta

El humano necesita que, para la presentación, el trabajo de arrastre venga hecho: años de
boletines cuyos ítems nadie ha revisado uno a uno.

**Un hallazgo histórico no entra nunca en la tabla `alerta`.** Se deriva de tener informe con
`semaforo = alerta` **y no tener aprobación humana**. Dos superficies distintas, en dos sitios
distintos de la base:

| | de dónde sale | qué afirma |
|---|---|---|
| **alerta** | fila en `alerta`, creada solo por `services/revision.aprobar` | una persona lo revisó y decidió publicarlo |
| **hallazgo histórico** | informe con semáforo `alerta` sin fila en `alerta` | el archivo prueba el cambio; nadie lo ha revisado |

Así, la frase que preside la portada —*«nada se publica sin revisión humana»*— **sigue siendo
literalmente cierta**, porque un hallazgo no es una alerta. No es una etiqueta de interfaz que
alguien pueda quitar en un refactor: es que viven en tablas distintas y se construyen de forma
distinta.

## Decisión 4 — Sin corroboración externa, un hallazgo no se publica solo

`corroboraciones`: lista de `{organizacion, que_dice, url}` con lo que **FELGTBI+, Amnistía
Internacional, ILGA-Europe** u organizaciones equivalentes hayan documentado ya sobre ese cambio.

Es lo que hace publicable un hallazgo sin revisión humana, y conviene ver por qué. Sin ese campo,
lo que la web enseñaría es *«un asistente de IA cree que esto es un retroceso»* — una opinión de
un modelo, publicada, en un proyecto cuya regla de oro 2 dice que el sistema **nunca emite un
juicio propio**. Con el campo se enseñan **dos hechos verificables por separado y ninguno
nuestro**:

1. **Que el cambio ocurrió** — lo prueba el documento archivado con su `sha256` y su sello (6.5).
2. **Que alguien con nombre ya lo denunció** — lo prueba el enlace a la organización.

Que esos dos hechos existan no es una conclusión: es una cita doble. Y quien lea puede comprobar
las dos por su cuenta, que es todo el valor que el proyecto dice pretender.

**Un informe sin corroboraciones es legítimo y significa algo**: nadie de las fuentes de
referencia lo ha señalado todavía. Puede seguir siendo cierto, y por eso sirve igual para el gate
humano — pero no sale a la web como hallazgo, porque ahí no habría más respaldo que el del propio
modelo.

## Consecuencias

- Dos migraciones, `c3a9e1f04b72` y `d7b2c85fa419`. **15 CHECK** tras aplicarlas (entra
  `semaforo`), `origenclasificacion` intacta.
- `--importar-informes` es idempotente por sustitución: reimportar reescribe el informe de ese
  ítem. Es material de trabajo, no archivo, y a diferencia de `version_norma` **sí** se reescribe.
- El importador **no resuelve nada de la cola**: `estado` sigue en `pendiente` hasta que decida
  una persona. Un informe es material de lectura.
- Queda pendiente y es lo que falta para cerrar el ADR: exponerlo en `GET /api/revision/cola`,
  pintarlo en el panel **debajo de la evidencia y no encima** —el orden importa por lo mismo que
  el campo `refutacion` existe— y la superficie pública de hallazgos con su etiqueta.
- Y queda dicho lo que no arregla: los informes de hoy **no tienen corroboraciones** porque se
  escribieron antes de que existiera el campo. Hay que rehacerlos con las fuentes delante antes
  de publicar ningún hallazgo.
