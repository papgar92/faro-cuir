# ADR 0031 — El verbo tiene que **gobernar** la cita, no solo caer cerca

- **Fecha:** 2026-09-03
- **Estado:** aceptado
- **Afecta a:** `pipeline/citas.py`, `VERSION_REGLAS`, la cola del gate humano (7.7)
- **Continúa:** ADR 0022 (el eje referencial lee las citas del texto), ADR 0023 (el verbo pegado
  a la norma vigilada), ADR 0030 (norma-vehículo)

## Contexto

El 2026-08-30 el humano miró la cola de revisión y dijo que **había alertas que no tocaban nada
LGTBIQ+**. Tenía razón dos veces. La primera causa se arregló ese día: «…por la que se modifica
la Ley Orgánica 2/2006» es el **nombre** de la LOMLOE, no una cláusula, y hacía que toda norma
educativa pareciera modificar la LOE. De 143 referencias modificativas se pasó a 62.

La segunda quedó anotada en `ESTADO.md` sin tocar, y con dos avisos:

> «Es un problema distinto y más difícil: no hay una construcción que lo delate, solo distancia.
> Queda anotado y **no se toca a ojo** — estrechar la ventana sin medir perdería modificaciones
> reales.»

El caso: el verbo está suelto en el documento, cae dentro de los 200 caracteres de
`VENTANA_VERBO`, y **la cita no es su objeto**.

    «Se modifica el anexo III del Reglamento de ingreso, accesos y adquisición de nuevas
     especialidades en los cuerpos docentes A QUE SE REFIERE LA Ley Orgánica 2/2006…»

Ahí no se modifica la LOE: se modifica un reglamento que la LOE menciona. El eje referencial la
daba por modificada, la norma entraba en la cola del clasificador y una persona tenía que
descartarla a mano.

## Lo que se midió antes de decidir (`scripts/medir_ventana_verbo.py`)

Sobre las **925 normas de la cola** con cuerpo archivado, **89 referencias modificativas** a
normas vigiladas. Desglose de las que no deberían estar:

| criterio | descarta | qué es |
|---|---|---|
| **R** | 15 | la cita es el término de una referencia: «a que se refiere», «regulado por», «dada por» |
| **N** | 9 | otra norma citada entre el verbo y la nuestra: **el verbo lo reclama la más cercana** |
| **C** | 8 | empieza un texto citado («…queda redactado como sigue: "…"»): lo de dentro es del documento **modificado** |
| **F** | 5 | se cierra una frase en medio |
| **P** | 1 | el verbo casa dentro de otra palabra: «se modifica» dentro de «se modific**aron**», que narra en pasado lo que hizo otra norma |

**22 referencias descartadas —los cinco criterios se solapan—, y las 22 se leyeron una a una: las
22 son ruido.** Quedan **67**.

### Y la distancia, que era la solución evidente, es la mala

Recortar `VENTANA_VERBO` de 200 a 60 deja **el mismo número: 67**. Por dentro es lo contrario:

- **Pierde dos modificaciones reales.** El apartado 5 del art. 8 de la ley LGTBI valenciana
  (`BOE-A-2021-1859`, 67 caracteres) y cinco preceptos de la ley trans valenciana
  (`BOE-A-2026-16931`, 105 caracteres, entre ellos el art. 16 y el art. 23.2).
- **Conserva ruido de 4 caracteres**, como «se derogan … y **la** Ley 4/2023» dentro de una lista
  de leyes de protección de datos.

La misma cifra por fuera y lo contrario por dentro. Es exactamente para lo que existía la
medición, y es la razón por la que `ESTADO.md` prohibía tocarlo a ojo.

## Decisión

`_verbo_previo` deja de aceptar cualquier verbo de la ventana: exige que **gobierne** la cita.
`_gobierna(forma, entre)` mira el texto que va del final del verbo al principio de la cita y lo
rechaza si aparece cualquiera de los cinco criterios de la tabla.

En una cláusula de verdad, ese hueco solo tiene el **objeto** del verbo: «el apartado 2 del
artículo 8 de la», «los anexos I, II y III del», «el punto 9 del artículo 4, definiciones, de la».

Tres decisiones dentro de la decisión:

1. **Es una lista de lo que descarta, no de lo que acepta.** Una lista de formas admitidas
   convertiría cualquier redacción no prevista en un falso negativo, y un falso negativo aquí es
   invisible (7.1). Lo que no esté en los cinco criterios sigue pasando.
2. **La comprobación de la flexión (P) completa la palabra antes de juzgarla.** `_VERBOS` es una
   alternancia y casa la **primera** forma que encaja, así que sobre «se modifican» casa «se
   modifica» y deja una «n» detrás. La primera versión de la medición, que solo miraba si seguía
   una letra, se llevaba por delante **todos los plurales** —15 de 89— que son la mitad del
   articulado real. Quedó como test.
3. **`VENTANA_VERBO` no se toca.** Sigue en 200 y con su comentario.

## Consecuencias

- **La cola del gate humano deja de recibir estas 22.** Las que ya estaban creadas **no se
  retiran solas** (`services/clasificacion.py`: *«No se retira sola: revísala»*), igual que con
  el ADR 0023 y con el arreglo del 2026-08-30: un cambio de catálogo no reescribe en silencio lo
  ya producido. Se descartan a mano; lo importante es que no vuelven a aparecer.
- **`VERSION_REGLAS` sube a `2026.09.03`** (y con ella `VERSION_REGLAS_PUBLICADA` del frontend),
  que es lo que hace que `--reclasificar` vuelva a mirar lo ya clasificado.
- **`VERSION_WATCHLIST` no sube**, con el mismo criterio del ADR 0030: se sube cuando cambia
  **qué se vigila**. Aquí cambia cómo se lee una cita, y devolver ~82.000 normas a la cola del
  prefiltro costaría cuatro horas para mover, como mucho, las mismas 22 filas que
  `--reclasificar` ya toca.
- **El eje referencial pierde recall si alguna de las cinco construcciones aparece en una
  modificación real.** No se ha visto ninguna en el corpus —los 22 descartes se leyeron uno a
  uno— pero es la exposición honesta de esta decisión, y la razón de que los criterios sean
  cinco formas concretas medidas y no una heurística general.
- **`scripts/medir_ventana_verbo.py` importa los predicados de producción y compara su desglose
  con `citas._gobierna` en cada referencia.** Un script de medición con su propia copia de la
  regla mide su copia: este ya divergió una vez, antes de que la regla existiera.

## Alternativas descartadas

- **Estrechar `VENTANA_VERBO`.** Medida y peor: ver arriba.
- **Exigir que el hueco solo contenga vocabulario de objeto** (artículo, anexo, apartado, número,
  conjunciones). Es la regla más precisa sobre este corpus, pero convierte toda redacción no
  prevista en un descarte silencioso, y el coste de un falso negativo en este proyecto no es
  simétrico al de un falso positivo (7.1).
- **Que lo decida el LLM.** Prohibido por la sección 7.6: ninguna regla puede depender de un
  campo que venga del juicio del modelo.
- **Vigilar preceptos y no normas enteras** (`preceptos: ["art. 33"]`), que es lo que el ADR 0030
  dejó anotado como solución de fondo. Sigue pendiente y sigue siendo mejor: quitaría el ruido
  que estos cinco criterios no tocan —el que apunta de verdad a una norma-vehículo, pero a un
  precepto que no sostiene ningún derecho del colectivo—. Exige investigación jurídica norma a
  norma y no cabe antes de la entrega.
