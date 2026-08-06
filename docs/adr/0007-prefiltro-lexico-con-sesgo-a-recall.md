# 0007 — Prefiltro léxico sesgado a recall antes del LLM

## Contexto

El BOE publica unas 250 normas al día. Con las 17 CCAA serían varios miles. Mandarlas todas
al extractor LLM es inviable por coste y, sobre todo, innecesario: la inmensa mayoría son
órdenes tributarias, nombramientos y subvenciones que no rozan el objeto del proyecto.

La sección 7 de `CLAUDE.md` sitúa un prefiltro léxico como etapa 1, antes del extractor,
"ajustado a recall máximo: mejor 50 falsos positivos que 1 falso negativo". Este ADR
documenta cómo se ha implementado esa instrucción y qué implica.

Lo que hace especial a esta etapa es que **es la única del pipeline que puede perder una
norma para siempre en silencio**. Si el extractor se equivoca, hay un JSON que revisar; si el
clasificador se equivoca, la cola de revisión lo ve. Pero una norma que el prefiltro descarta
no vuelve a aparecer en ningún sitio: nadie la mira, nadie sabe que existió.

## Decisión

**El filtro no se equilibra: se sesga a recall, y se instrumenta para poder demostrarlo.**

1. **Solo el título y el órgano emisor.** Es lo único que trae un sumario, y decidir si vale
   la pena bajar al texto completo es precisamente la función de esta etapa.
2. **Sin lista negra ni exclusiones.** Ninguna regla puede descartar una norma que ya ha
   coincidido con un término. Cualquier "esto en realidad no cuenta" es una vía para perder
   verdaderos positivos, que es el error caro.
3. **Vocabulario con las variantes antiguas y clínicas** (`disforia de genero`,
   `transexualidad`, `reasignacion de sexo`) además de las actuales. Una norma que recorta
   derechos suele estar redactada con el léxico de hace veinte años.
4. **Dos categorías de término, `DIRECTO` y `CONTEXTO`, que no cambian la decisión.** Los
   genéricos del dominio (`cartera de servicios`, `convivencia escolar`) hacen pasar la norma
   igual. Separarlos solo sirve para *medir* cuánto ruido aporta la lista genérica y poder
   afinarla con datos sin tocar el recall de los términos específicos.
5. **El resultado se persiste con su justificación**: qué términos dispararon, con qué
   versión del vocabulario y cuándo. El estado `pendiente` es distinto de `descartada`.
6. **Subir `VERSION_VOCABULARIO` obliga a reevaluar** lo ya evaluado con la versión anterior
   (`worker.run --reprefiltrar`). Sin esto, añadir un término solo protegería al futuro.

## Alternativas descartadas

- **Un LLM decidiendo la relevancia.** Sería mejor filtro y es la solución obvia hoy. Se
  descarta por tres razones: cuesta una llamada por norma (justo lo que esta etapa evita),
  no es auditable —no se puede enseñar al tribunal *por qué* se descartó una norma concreta—
  y es no determinista, así que "esto se descartó" dejaría de ser reproducible. El LLM entra
  en la etapa 2, sobre las pocas que pasan, y con salida validada por esquema.
- **Búsqueda full-text de PostgreSQL** (`to_tsvector('spanish', ...)`). El *stemming* español
  ayudaría con las flexiones, pero mete la decisión dentro de la base de datos, la vuelve
  dependiente de la configuración de collation, y complica testearla sin un Postgres
  levantado. El vocabulario es de ~90 términos: no necesita un motor de búsqueda.
- **Un umbral por número de coincidencias** ("relevante si coinciden ≥2 términos"). Sube la
  precisión y baja el recall, que es exactamente la dirección contraria a la que pide el
  proyecto. La Ley 4/2023 coincide con dos, pero una instrucción autonómica de rango bajo
  —el objetivo declarado del sistema— puede coincidir con uno solo.
- **No persistir el resultado y recalcularlo al vuelo.** El filtro es determinista y barato,
  así que técnicamente sobra guardarlo. Se guarda porque el valor no está en el veredicto
  sino en poder sostenerlo: sin la versión del vocabulario, "esta norma se descartó el día 3"
  deja de ser comprobable en cuanto el diccionario cambia.

## Consecuencias

- **Se acepta ruido a cambio de cobertura.** Los términos de contexto harán pasar normas que
  no van del tema. Es el precio elegido, no un defecto a corregir: la métrica
  `solo_por_contexto` existe para vigilarlo, no para minimizarlo a toda costa.
- **El vocabulario es un artefacto vivo y es la pieza más frágil del sistema.** Un término
  que falta es un agujero invisible. Debe revisarse cada vez que aparezca un caso real que el
  filtro no cazó, y esa revisión es trabajo humano recurrente, no una tarea que se cierre.
- **La medición actual es insuficiente y hay que decirlo.** Sobre las 436 normas reales
  ingeridas, el filtro encuentra la Ley 4/2023 y descarta 435 sin un solo falso positivo de
  contexto. Eso demuestra que funciona, **no** que el recall sea alto: con un único positivo
  conocido no se puede estimar cuántos se pierden. **El recall real solo será medible con el
  gold set** (`tests/gold_set/`, sección 7). Hasta entonces, cualquier cifra de recall que se
  publique sería inventada.
- **El estado `pendiente` obliga a un barrido tras cada cambio de vocabulario.** Es una tarea
  operativa nueva, deliberada: la alternativa era que el diccionario mejorara sin que
  mejorase nada de lo ya archivado.
