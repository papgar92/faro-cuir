# ADR 0013 — Trazabilidad por offsets de la extracción

- **Fecha**: 2026-08-16
- **Estado**: aceptado
- **Contexto de tarea**: la última regla de oro que el sistema incumplía (la 9). Su número estaba
  **reservado desde el 2026-08-07** y se ha respetado sin reutilizarlo durante once ADRs.
- **Números libres**: el siguiente es el 0019.

## Contexto

La regla de oro 9 dice, literalmente:

> Todo hecho extraído por el LLM apunta a un rango de caracteres del texto archivado. Si el rango
> no se corresponde con lo que dice el modelo, la extracción se descarta. El revisor humano
> verifica contra la fuente, no contra la palabra del modelo.

Hasta hoy no se cumplía. El extractor devolvía `texto_anterior` y `texto_nuevo` como cadenas
sueltas dentro de `extraccion_json`, y **una alucinación era indistinguible de una cita**: las dos
son una cadena en un JSON. El resto del sistema lo compensaba a base de no fiarse de esa salida
—el catálogo de reglas lee el archivo y no la extracción (ADR 0016), y un puntero es inerte— pero
eso es aislar el problema, no resolverlo.

## Decisión

**Cada texto que la extracción afirma haber leído se localiza en el texto archivado y se guarda
con su rango de caracteres. Si alguno no se encuentra, se descarta la extracción entera.**

`pipeline/anclaje.py` es un módulo puro que recibe dos cadenas y devuelve coordenadas. Lo que se
persiste en `extraccion_json.anclas` es el **recorte del archivo**, no lo que devolvió el modelo:
la cadena del modelo sirve para localizar y después se tira.

Cuatro decisiones que van con esta:

1. **Los offsets los calcula el sistema, no los pide al modelo.** 7.5 se escribió suponiendo lo
   contrario —que el LLM los emitiría y aquí solo se comprobarían—, y se implementa al revés
   porque es más fuerte: (a) un modelo de 3B parámetros contando caracteres es una fuente de
   error nueva, y un fallo de aritmética descartaría una cita correcta, o sea un falso negativo
   introducido por el propio control; (b) aunque los diera habría que buscarlos igualmente en el
   texto para validarlos, así que la búsqueda **es** el control y el offset del modelo sería
   redundante; (c) un campo menos en el esquema es una superficie menos que un documento hostil
   puede intentar dirigir (6.7).
2. **Se ancla sobre el mismo texto que usan las reglas** (`pipeline/texto.texto_plano`,
   versionado). **No hay una segunda normalización**, en contra de lo que 7.5 anticipaba: dos
   derivaciones del mismo documento archivado son dos sistemas de coordenadas, y entonces un span
   del clasificador y un offset de la extracción no se pueden contrastar ni entre sí ni sobre el
   mismo texto. Un archivo con dos reglas para medir no sirve para lo que este proyecto lo usa.
3. **La única licencia es colapsar espacios.** El modelo reproduce una cita con un espacio donde
   el archivo tiene un salto de línea; exigir igualdad byte a byte descartaría citas correctas.
   Cambiar una palabra, no: una paráfrasis no ancla, y por tanto se descarta.
4. **Se descarta la extracción completa, no el campo que falla.** Si el modelo se ha inventado
   una redacción, lo que ha escrito en los demás campos tampoco merece crédito. Sigue la vía de
   fallo que ya existía (6.9.3): no se crea fila, así que la norma vuelve sola a la cola en la
   siguiente pasada del worker, sin estado de error que mantener.

Un **puntero** (ADR 0016: precepto citado sin texto por ninguno de los dos lados) no ancla nada y
no invalida nada: no hay cita que verificar, y por eso mismo sigue sin accionar nada por sí solo.

## Alternativas consideradas

- **Pedir los offsets al modelo y validarlos**, que es lo que 7.5 describía. Descartada por lo
  dicho arriba: añade un modo de fallo y no quita ninguno.
- **Aceptar la cita sin anclar y marcarla como “no verificada”.** Es la opción cómoda y es la que
  este proyecto no puede tomar: una etiqueta de “no verificado” en una interfaz se lee como
  matiz, no como advertencia, y acaba publicándose igual. Lo que no se puede señalar en el
  archivo no existe para el sistema.
- **Similitud aproximada** (distancia de edición, umbral de parecido). Convierte el control en un
  parámetro que hay que calibrar, y su fallo silencioso —dejar pasar una paráfrasis— es
  exactamente lo que se quería impedir. Si algún día hace falta, con el gold set delante.

## Consecuencias

- **La revisión humana pasa de confianza a verificación.** El panel puede resaltar el fragmento
  sobre el texto archivado, porque ahora hay coordenadas y el recorte sale del archivo.
- **Es también un control anti-inyección** (6.7): una inyección que consiga que el modelo invente
  contenido tiene que además conseguir que ese contenido esté en un documento que no controla.
- **Puede bajar el número de extracciones que se persisten**, y eso es el control funcionando, no
  una regresión. Se ve en el contador `fallidas` del resumen del worker. Con el modelo pequeño en
  CPU (ADR 0008) todavía no hay medida de cuántas se van por esto: es lo primero que habrá que
  mirar cuando el gold set tenga volumen.
- **`extraccion_json` gana `anclas`, `version_texto_plano` y `version_anclaje`.** Las versiones
  viajan porque un offset sin saber sobre qué derivación y con qué criterio se midió no es
  reproducible, que es el mismo motivo por el que la evidencia del clasificador ya las llevaba.
- Las filas de `deteccion` anteriores a este ADR no tienen `anclas`. No se rellenan hacia atrás:
  se reextraen o se quedan como están, y el campo ausente dice exactamente eso.
