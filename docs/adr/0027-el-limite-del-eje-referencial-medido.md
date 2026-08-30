# ADR 0027 — El límite del eje referencial, medido: la watchlist no es la palanca

- **Fecha**: 2026-08-23
- **Estado**: aceptado
- **Contexto de tarea**: se midió a escala el catálogo de reglas sobre 69.388 normas y no producía
  trabajo nuevo para el gate humano. Al buscar la causa se encontró otra distinta de la que se
  había supuesto dos veces.
- **Números libres**: el siguiente libre tras este es el **0028**.

## Contexto

El 2026-08-23, tras reclasificar sobre 66.660 normas archivadas, el sistema seguía produciendo
**cero ítems nuevos** para la cola de revisión. El corpus había crecido 150 veces y los hallazgos
no habían crecido nada. Se buscó la causa y se acertó dos veces a medias:

**Primer diagnóstico: «el cuello de botella son las reglas».** El catálogo tenía cinco reglas y
tres eran variantes de supresión; `R-SUP-001`, la única que afirma signo, había disparado dos
veces en 66.660 normas. Parecía evidente que faltaban familias de reglas.

Se midió antes de escribir la sexta (`R-DES-001`, deslegalización, propuesta por el
`jurista-lgtbi`). Resultado sobre un **censo** de las 52 normas donde podía aportar: **0 casos
nuevos**. Las que cumplían sus condiciones ya producían veredicto por `R-MOD-001`.

**Segundo diagnóstico: «el cuello de botella es la watchlist».** Los números lo sostenían: 24
normas vigiladas, 22 tocadas por el corpus, 17 ya con veredicto. Como las cuatro reglas que llegan
al gate exigen «toca una norma vigilada» (ADR 0017), **el techo del sistema entero eran 22 casos**,
con un margen libre de cinco. El catálogo no estaba ciego: miraba por una rendija.

Se encargó la ampliación al `jurista-lgtbi`, que devolvió 18 candidatas verificadas. **Y se midió
también, antes de aplicarlas.**

## La medición que cambia el diagnóstico

Censo de 27.016 disposiciones del corpus (`scripts/medir_normas_mas_modificadas.py`, sin red):

| | |
|---|---|
| Disposiciones leídas | 27.016 |
| Que modifican o derogan algo | 1.900 (7,0 %) |
| Normas distintas tocadas | **2.597** |
| De ellas, en la watchlist | **9** de 24 |

Y el aporte de las 18 candidatas nuevas sobre ese mismo corpus:

| candidata | veces tocada |
|---|---|
| Ley 20/2011 Registro Civil, Ley 16/2003 SNS, Ley 41/2002 paciente, RD 243/2022 Bachillerato, Ley 19/2007 deporte | 1 cada una |
| Las trece restantes | 0 |

**Cinco casos en un año de corpus.** El techo pasaría de 22 a ~27.

Eso no contradice al jurista: él midió frecuencia histórica en los textos consolidados, y para la
Ley 16/2003 son ~24 modificaciones en 23 años, o sea ~1/año — exactamente lo medido. Lo que hace la
medición es **ponerla en escala**: lo que él llamó «la candidata más rentable» rinde un caso al año.

## Decisión

**Se acepta que ampliar la watchlist no es la palanca que parecía, y se documenta el límite del
enfoque en vez de seguir buscando la pieza que falta.**

En concreto:

1. **Entra solo la tanda protectora** (tres normas: Ley 15/2022 y las dos Instrucciones de la
   DGSJFP). No rompen el supuesto de `R-SUP-001` y no exigen tocar código.
2. **Las quince norma-vehículo no entran** hasta que exista un campo de especificidad en
   `NormaVigilada` y `R-SUP-001` deje de afirmar signo sobre ellas — con su rendimiento medido
   anotado al lado, para que la decisión de invertir esa sesión se tome con el dato delante.
3. **No se escriben más familias de reglas buscando recall** sin medir antes su aporte sobre el
   corpus archivado, que no cuesta ni una petición de red.

## El porqué, que es lo que este ADR existe para dejar escrito

El sistema encuentra poco **no porque le falten reglas ni porque le falte watchlist**, sino porque
el retroceso que este diseño sabe ver —**el que deja rastro referencial**, una disposición que
declara en el `<analisis>` que modifica una norma protectora concreta— **es raro**.

Los mecanismos que el informe de puntos ciegos ordenó por invisibilidad no dejan ese rastro **por
definición**:

- **M-1**, no convocar la subvención, no renovar el convenio, dejar caducar el plan: no hay acto,
  no hay norma, no hay diff. Es el más frecuente en el nivel local, el que el ADR 0014 dice que
  justifica el proyecto.
- **M-3** y **M-7**, bases de subvención y currículos: se caracterizan **por ausencia**, y solo
  existen comparando con el documento anterior de la serie.
- **M-2**, partida presupuestaria a cero: solo visible si el programa conserva el nombre.

Ninguno se arregla añadiendo entradas a un JSON. Detectarlos exigiría un **vigilante de
periodicidad** sobre el archivo, que es otro servicio y no un prefiltro, y queda fuera del plazo
(sección 8).

**La asimetría, dicha entera:** el filtro ve mejor el retroceso parcial —el que todavía nombra lo
que recorta— que el completo, que lo borra. **Cuanto más limpio es el trabajo del redactor, más
invisible es para este sistema.**

## Consecuencias

- **Lo que el proyecto puede afirmar cambia de forma, y a mejor.** Deja de ser «detectamos
  retrocesos» y pasa a ser «detectamos los retrocesos que dejan rastro referencial, y **sabemos
  medir cuántos son y cuáles se nos escapan**». Es una afirmación más pequeña y mucho más
  defendible ante un tribunal, y es la que sostienen los datos.
- **La cifra de recall que salga del gold set hay que leerla sobre esa base.** Un recall alto sobre
  lo que sí deja rastro no dice nada del retroceso silencioso; publicarlo sin esta salvedad sería
  exactamente la confianza infundada que la sección 6.9.6 prohíbe.
- **No se toca ninguna regla del catálogo.** Las cinco siguen como están; lo que cambia es que
  ninguna nueva se escribe sin medirla antes.
- **El instrumento queda hecho y es barato de repetir:**
  `scripts/medir_normas_mas_modificadas.py` deja un índice reutilizable en
  `data/normas-modificadas.json`, así que preguntar «¿cuánto aportaría esta candidata?» pasa a ser
  un lookup en vez de un censo.
- **Se conserva el hallazgo lateral**: la Ley 13/2005 (matrimonio igualitario) estaba vigilada de
  forma **nominal** —404 en consolidada y cero apariciones frente al Código Civil que sí aparece—
  porque se agotó al modificar el CC. Se mantiene por el rastro histórico con la advertencia
  escrita en su nota. Cubrirla de verdad exige vigilar el Código Civil, con el problema de ruido
  del Estatuto de los Trabajadores.

## Alternativas descartadas

- **Escribir más familias de reglas.** Medido: `R-DES-001` aportaba 0 sobre un censo. El embudo no
  se estrecha ahí.
- **Ampliar la watchlist agresivamente (Código Civil, Estatuto de los Trabajadores, Código
  Penal).** Subiría el recall y subiría a la vez el ruido en el gate humano, que es el control
  central del proyecto: son normas que se modifican varias veces al año por cualquier reforma y
  cada modificación llegaría a la cola sin una línea sobre el colectivo. Es el modo de fallo que ya
  vació de sentido a `R-SUP-002` (10 de 10 descartadas, ADR 0017).
- **Construir el vigilante de periodicidad ahora.** Es la respuesta correcta a M-1 y a M-3, y no
  cabe en el plazo (sección 8). Queda documentado como hoja de ruta, que es lo que la sección 8
  autoriza.
- **Callarlo y publicar el recall bueno.** Es lo que haría que el sistema generase confianza
  infundada, que la sección 6.9.6 llama peor que no existir.
