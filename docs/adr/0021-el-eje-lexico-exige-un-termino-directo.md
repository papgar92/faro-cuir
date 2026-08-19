# ADR 0021 — Sobre el texto íntegro, una fórmula administrativa no es una señal

- **Fecha**: 2026-08-19
- **Estado**: aceptado
- **Contexto de tarea**: primera tanda del gold set con casos del DOGC (7.8), que es lo que hizo
  visible el problema con un documento delante en vez de con una intuición.
- **Números libres**: el siguiente libre tras este es el **0022**.

## Contexto

El eje léxico (7.3) reparte sus ~90 términos en dos categorías, `DIRECTO` y `CONTEXTO`, y hasta
hoy **esa distinción no cambiaba la decisión**: bastaba con que apareciera cualquiera de los dos
para entrar en la cola del extractor. Se etiquetaban aparte solo para poder medir el ruido.

Eso era razonable cuando el prefiltro leía títulos. Un título son quince palabras: si dice «plan
de igualdad», está hablando de un plan de igualdad. Con el ADR 0011 el eje pasó a evaluarse sobre
el **texto íntegro**, y el propio 7.3 dejó escrito el aviso:

> «El vocabulario está pensado para títulos y mide *presencia*; sobre 200.000 caracteres hay que
> mirar **cuántos** términos directos aparecen.»

El aviso llevaba desde el 2026-08-07 sin aplicarse, porque nadie tenía con qué sostener el
cambio. La primera tanda del gold set del DOGC lo puso delante:

> **`DOGC-24310119`**, DECRETO 429/2024 del currículo del ciclo formativo de **arte floral**.
> 105.101 caracteres. Única coincidencia del vocabulario: «plan de igualdad», dentro del módulo
> de formación y orientación laboral — *«Fases para la elaboración de un plan de igualdad en la
> empresa»*. El prefiltro lo mandaba a la cola del LLM.

Es el equivalente en el DOGC de la convocatoria de oposición que cita la Ley 4/2023 en el
temario, y no es un caso suelto: hay una veintena de decretos hermanos de currículo en el mismo
corpus.

### Lo medido, que es lo que decide

Sobre las **140 normas que había en la cola** del extractor (`scripts/medir_ruido_lexico.py`,
2026-08-19):

| | |
|---|---|
| entraban **solo por términos de contexto** | **100 (71 %)** |
| entraban con al menos un término directo | 40 |
| longitud de las «solo contexto» | mediana **54.099** caracteres, máximo **2.035.373** |
| términos responsables | «igualdad de trato» (51), «plan de igualdad» (24), «no discriminación» (20), «registro civil» (18) |

Cuatro fórmulas que aparecen en cualquier documento administrativo largo estaban llenando siete
de cada diez puestos de una cola cuyo siguiente paso cuesta **133,9 s por norma**.

## Decisión

**Sobre el texto íntegro, el eje léxico exige al menos un término `DIRECTO` para entrar en la
cola. Los términos de `CONTEXTO` por sí solos ya no bastan.**

Y lo que **no** cambia, que importa igual:

1. **Sobre el título, nada cambia.** Un término de contexto en un título sigue metiendo la norma
   en la cola. La regla nueva se aplica solo cuando hay texto íntegro, porque solo entonces la
   presencia deja de significar algo.
2. **Sigue sin poder descartarse nada sin haber leído el documento** (7.1). Esta regla decide
   *después* de leerlo, nunca antes.
3. **Un solo término directo sigue bastando.** No se sube ningún umbral de conteo:
   `UMBRAL_DIRECTOS_RELEVANTE` sigue separando `RELEVANTE` de `SOSPECHA` y sigue sin decidir
   ningún descarte.
4. El eje referencial no se toca: modificar una norma de la watchlist sigue pasando el filtro
   por definición, diga lo que diga el texto.

`VERSION_VOCABULARIO` sube a `2026.08.19` aunque no se haya tocado ni un término: la versión
cubre **el eje entero**, no la lista de palabras, y es lo que hace que `--reprefiltrar` recoja el
cambio. Queda dicho en el propio comentario de la constante, porque es contraintuitivo.

## Lo que se pierde, con números y no con adjetivos

Esta decisión **sí produce descartes**, así que no vale con decir que mejora la precisión.

- **Recall del gold set: intacto.** Ninguno de los 22 casos etiquetados con etiqueta de cola
  tiene cero términos directos. Los 22 siguen coincidiendo con su etiqueta después del cambio;
  antes fallaba uno, el falso positivo.
- **Detecciones del catálogo de reglas: 3 de 13.** De las 13 detecciones con `regla_aplicada`
  existentes, 3 venían de normas sin ningún término directo, y **las 3 eran `R-SUP-002`** — la
  regla de supresión sin norma vigilada, que el gate humano descartó **10 de 10 veces** y que por
  eso ya no se encola (ADR 0017). Se pierde exactamente lo que ya se había decidido no mirar.
- **`R-SUP-001` y `R-DER-001` no se ven afectadas**: sus normas tienen 7, 22 y 31 términos
  directos.

El riesgo residual, dicho claramente: una norma que **regule** sobre el ámbito sin usar ni una
sola vez ninguno de los ~60 términos directos, y que además no modifique nada de la watchlist,
ahora se descarta en vez de quedarse la última de la cola. Es el escenario que el eje 3
(semántico) cubriría y que sigue fuera de alcance (sección 8). Contra eso hay dos cosas y ninguna
es un adjetivo: el gold set, que es donde ese caso tiene que aparecer para que se vea, y que el
descarte queda **registrado con su versión y sus términos**, así que subir `VERSION_VOCABULARIO`
lo reevalúa todo sin volver a descargar nada.

## Alternativas descartadas

**Quitar los cuatro términos ruidosos del vocabulario.** Es la más tentadora y la peor: «registro
civil» es exactamente donde vive la rectificación registral de sexo y nombre, y «igualdad de
trato» es el nombre de una ley. El problema no son los términos, es qué se hace con ellos sobre
100.000 caracteres. Quitarlos los perdería también en los títulos, donde sí discriminan.

**Subir `UMBRAL_DIRECTOS_RELEVANTE`.** No resuelve nada aquí —estos documentos tienen cero
directos, no pocos— y además rompería `DOGC-24198092`, que entra por **un** término directo en
28.000 caracteres y cuya señal es buena: el Consejo Nacional LGBTI está en la composición de la
comisión que regula. Está en el gold set para eso.

**Contar apariciones en vez de términos distintos.** Un currículo que repita «plan de igualdad»
cinco veces subiría, y una norma que diga «personas trans» una vez bajaría. Cuenta la clase de
término, no su insistencia.

**Dejarlo como estaba y aceptar el ruido.** Era defendible mientras la cola fuera pequeña. Con
100 de 140 puestos ocupados por fórmulas y 133,9 s por extracción, «la cola está sesgada a
recall» deja de describir la realidad: describe una cola que nadie va a drenar nunca, y una cola
que no se drena es un falso negativo con otro nombre.

## Consecuencias

- El descarte se aplica a lo ya evaluado en cuanto se lanza `worker.run --reprefiltrar`, sin
  tocar la red: los cuerpos están archivados (ADR 0015).
- `scripts/medir_ruido_lexico.py` queda en el repo para poder reproducir la medición, igual que
  `medir_fase2.py` con el ADR 0011. Con `--todas` mira toda la tabla y no solo la cola, que es lo
  que hay que usar después de este cambio.
- El gold set gana dos casos que sujetan la decisión por los dos lados y que **no hay que tocar
  sin leer sus notas**: `dogc-24310119` (el falso positivo que se cae) y `dogc-24198092` (el
  positivo de un solo término que tiene que seguir entrando).
- 7.3 deja de tener un aviso pendiente de aplicar. El que queda abierto es el otro: el umbral de
  conteo sigue **sin validar**, y con 22 casos sigue sin poder validarse.
