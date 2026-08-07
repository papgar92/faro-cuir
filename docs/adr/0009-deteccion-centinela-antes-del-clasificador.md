# 0009 — `deteccion` se inserta con un valor centinela antes de que exista el clasificador

## Contexto

`deteccion.clasificacion` y `deteccion.origen` son `NOT NULL` (ver el modelo en
`app/models/deteccion.py` y el ADR 0004). El ADR 0004 dice explícitamente, en sus
consecuencias: *"el pipeline necesita que el clasificador por reglas exista para poder
insertar una `deteccion`: no hay atajo para arrancar publicando lo que diga el LLM"*.

La etapa 2 (extractor, `services/extraccion.py`) ya está lista, pero la etapa 3 (clasificador
por diff) todavía no existe — está planificada como el siguiente bloque de trabajo, a
propósito en un commit aparte porque depende de que la salida del extractor esté ya
estabilizada (`CLAUDE.md` sección 11). Con el esquema tal cual, el extractor no puede insertar
ninguna fila en `deteccion` sin decidir algo para `clasificacion` y `origen`.

Este ADR responde a esa pregunta concreta, que el ADR 0004 dejó planteada pero no resuelta:
¿qué valor va ahí mientras el clasificador no existe?

## Decisión

El extractor inserta la `deteccion` con:

- `clasificacion = INDETERMINADO`
- `origen = HEURISTICA`
- `regla_aplicada = NULL`
- `extraccion_json` con los hechos validados del LLM, más `version_prompt` y `modelo`

**Esto no es una excepción al ADR 0004, es su cumplimiento literal.** `INDETERMINADO` no sale
de nada que haya dicho el modelo: es un valor centinela fijo, igual en todas las filas,
elegido antes de mirar la extracción y sin ningún camino de código que lo derive de
`extraccion_json`. La separación de columnas que pide el ADR 0004 se mantiene intacta — el
LLM sigue sin tener ningún campo por el que colar un veredicto, y esta fila tampoco se lo da.

`regla_aplicada = NULL` es honesto: no se ha aplicado ninguna regla todavía, porque no existe
ninguna. Es exactamente el vocabulario que ya preveía el ADR 0004 en su alternativa
aplazada nº 3 ("hoy no hay ninguna regla escrita todavía").

Cuando exista el clasificador (etapa 3), su trabajo será buscar las filas con
`clasificacion = INDETERMINADO AND origen = HEURISTICA AND regla_aplicada IS NULL` — que hoy
son *todas* las que crea el extractor — y decidir su clasificación real a partir del diff
(`version_norma`), actualizando `clasificacion`, `origen` y `regla_aplicada`. Hasta entonces,
estas filas son extracciones sin clasificar, no clasificaciones provisionales: no deben
llegar a `cola_revision` ni a ningún sitio visible como si fueran un veredicto (siguen
sin pasar el gate humano, regla de oro 4, porque ninguna fila con `INDETERMINADO` es apta para
`Alerta`).

## Alternativas consideradas

- **No insertar nada en `deteccion` hasta que exista el clasificador; guardar la extracción en
  otro sitio mientras tanto.** Habría exigido una tabla o columna nueva solo para un estado de
  tránsito de unas pocas semanas, y esa tabla se habría vuelto código muerto en cuanto el
  clasificador llegara. Además contradice la instrucción operativa de `CLAUDE.md` sección 11,
  que pide persistir en `deteccion.extraccion_json` explícitamente.
- **Añadir un valor `sin_clasificar` al enum `OrigenClasificacion`.** Más explícito que
  reutilizar `HEURISTICA`, pero cambia un CHECK que el ADR 0004 describe como la defensa
  central del proyecto, por una necesidad que dura solo hasta la etapa 3. Se descarta: el
  vocabulario existente (`INDETERMINADO` + `HEURISTICA` + `regla_aplicada NULL`) ya expresa
  "no hay clasificación real todavía" sin tocar el esquema.
- **Adelantar un clasificador mínimo (todo indeterminado) como parte de esta misma tarea.**
  Es literalmente lo que esto hace, solo que vive en el extractor en vez de en un módulo
  `pipeline/clasificador.py` separado. No se crea ese módulo aparte porque sería una capa sin
  ninguna regla dentro; cuando la etapa 3 escriba las reglas de verdad, el filtro de arriba
  (`INDETERMINADO`/`HEURISTICA`/`regla_aplicada IS NULL`) es exactamente su "pendientes".

## Consecuencias

- El clasificador (etapa 3) no parte de cero: su "cola de trabajo" es
  `SELECT * FROM deteccion WHERE clasificacion = 'indeterminado' AND origen = 'heuristica' AND
  regla_aplicada IS NULL`, sin necesidad de ningún flag nuevo.
- Mientras no exista el clasificador, todas las `deteccion` de la base de datos están en este
  estado centinela. Es visible y consultable — no oculto — y así debe quedar hasta que la
  etapa 3 lo resuelva de verdad.
- Si algún día se listaran `deteccion` en una pantalla del frontend, `INDETERMINADO` no debe
  pintarse igual que un `neutro` decidido por reglas: la ficha de norma ya sigue este criterio
  (ver `CLAUDE.md` sección 11, "Ficha de norma migrada") al no pintar clasificaciones que no
  existen todavía.
