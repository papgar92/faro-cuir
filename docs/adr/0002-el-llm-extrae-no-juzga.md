# 0002 — El LLM extrae hechos, no dicta veredictos

## Contexto

Faro Cuir procesa cambios legislativos sobre derechos LGTBI+ y los etiqueta como avance o
retroceso. Es un dominio políticamente disputado: la misma norma que una parte describe como
protección de menores, otra la describe como recorte de derechos. Cualquier herramienta que
publique etiquetas en este terreno va a ser cuestionada, y con razón.

Un LLM es muy bueno leyendo un texto legal denso y sacando de él qué norma se modifica, qué
artículos, qué decía antes y qué dice ahora. Y es igual de capaz de contestar "esto es un
retroceso" en un tono perfectamente convincente. La tentación de usar lo segundo es enorme
porque es una línea de prompt y ahorra todo el trabajo de reglas.

## Decisión

El LLM ocupa **una sola etapa** del pipeline (sección 7 de `CLAUDE.md`, etapa 2) y su
contrato es estrictamente de extracción:

- **Entrada:** el texto del documento, delimitado explícitamente como contenido no confiable.
- **Salida:** un JSON de hechos — norma afectada, artículos, texto anterior, texto nuevo,
  órgano emisor, ámbito — validado contra un esquema Pydantic.
- **Prohibido:** cualquier campo que exprese valoración. No hay campo "es_retroceso", ni
  "gravedad", ni "opinión". No existen en el esquema, así que el modelo no puede rellenarlos.

Si la salida no valida contra el esquema, **se descarta**. No se intenta reparar, ni se pide
otra vez con la respuesta anterior en el contexto, ni se "interpreta lo que quiso decir". Un
JSON que no valida es una salida no confiable, y tratar de arreglarla es hacer justo lo que un
intento de inyección de prompt necesita para prosperar.

La clasificación avance/retroceso la produce después un **clasificador por reglas auditables**
sobre el diff. Ver ADR 0004 para cómo el esquema de base de datos impide almacenar un veredicto
del modelo.

### Defensa de inyección de prompt (sección 6.7)

El contenido de un boletín oficial es texto no confiable entrando en un LLM. Que sea
improbable que el BOE contenga un intento de inyección no cambia el patrón a defender:

- El prompt de sistema no es sobreescribible por el documento; el documento va en un bloque
  delimitado e identificado como datos, nunca como instrucciones.
- La salida se valida contra el esquema, que es la defensa que de verdad sostiene el sistema:
  aunque una inyección lograra que el modelo obedezca, lo único que puede emitir es un JSON
  con los campos previstos. No hay campo por el que colar un veredicto.
- El modelo no tiene herramientas, ni acceso a red, ni capacidad de escribir en base de datos.

## Alternativas consideradas

- **Que el LLM clasifique directamente.** Descartado. Un modelo clasificando cambios
  legislativos como avance o retroceso sin regla auditable detrás es el sistema emitiendo una
  opinión política encubierta de hecho técnico. Sería indefendible ante el tribunal y ante
  cualquier usuario que pregunte "¿por qué esto es un retroceso?", porque la única respuesta
  honesta sería "porque un modelo lo dijo".
- **LLM como clasificador con explicación en texto libre.** Descartado, y es la opción más
  peligrosa de las tres: una explicación fluida da *apariencia* de auditabilidad sin serlo. La
  explicación no es el motivo de la decisión, es una racionalización generada después.
- **Prescindir del LLM y hacerlo todo con reglas.** Considerado en serio. Se descarta porque
  la extracción de estructura de un texto legal en prosa (qué artículo se modifica, qué decía
  antes) es exactamente donde las reglas se rompen y un modelo funciona bien. La decisión no
  es "LLM sí o no", es dónde ponerlo: en la lectura, no en el juicio.

## Consecuencias

- Hay que escribir y mantener un clasificador por reglas, con su gold set (`tests/gold_set/`).
  Es bastante más trabajo que un prompt. Es el coste de que el resultado sea defendible.
- La calidad del sistema depende de la calidad de la extracción, no de lo "listo" que sea el
  modelo juzgando. Eso hace que cambiar de proveedor sea barato (`llm/provider.py`) y que la
  evaluación sea posible: la extracción se puede medir contra el gold set, una opinión no.
- Cualquier campo nuevo en la salida del LLM debe pasar por este ADR. Añadir uno valorativo no
  es una mejora incremental, es cambiar lo que el sistema afirma ser.
