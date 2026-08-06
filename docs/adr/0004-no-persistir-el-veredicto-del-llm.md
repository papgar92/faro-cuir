# 0004 — La clasificación no puede almacenarse como salida del LLM

## Contexto

El ADR 0002 fija que el LLM extrae hechos y no juzga. Pero una regla que solo vive en el
prompt y en la revisión de código se erosiona: llega un día con prisa, alguien añade un campo
"valoración" al esquema de extracción "solo para depurar", y seis semanas después ese campo
alimenta la clasificación que se publica. Nadie decidió cambiar el diseño; simplemente pasó.

La pregunta de este ADR no es *qué* regla queremos, sino **dónde vive**, para que romperla
requiera un cambio deliberado y visible en vez de un descuido.

## Decisión

La regla se hace cumplir en el **esquema de base de datos**, donde no depende de que nadie la
recuerde.

### 1. No existe un origen "llm"

`deteccion.origen` es un vocabulario cerrado con exactamente dos valores:

```
derivado_diff | heuristica
```

No hay `llm`. Y como los enums se materializan como `VARCHAR + CHECK` en PostgreSQL, no es una
convención del ORM: la base de datos rechaza cualquier otro valor. Guardar "esta clasificación
la dictó el modelo" **no es representable**. Para hacerlo habría que escribir una migración que
añada el valor al CHECK, que es exactamente el cambio deliberado y visible que se busca.

### 2. Los hechos y el veredicto viven en columnas separadas

`extraccion_json` guarda lo que dijo el LLM: hechos estructurados y validados contra Pydantic.
`clasificacion`, `severidad` y `origen` guardan lo que decidió el clasificador por reglas. No
hay ningún camino en el código que copie del primero a los segundos, y la separación de
columnas hace que ese camino, si apareciera, se vea de inmediato en el diff.

### 3. Toda clasificación nombra su regla

`deteccion.regla_aplicada` guarda el identificador de la regla concreta que produjo el
resultado. No está en la lista original de la sección 5 de `CLAUDE.md`; se añade porque sin
ella "reglas auditables" es una promesa incumplible. Ante la pregunta "¿por qué esto es un
retroceso?", la respuesta tiene que ser el nombre de una regla que se puede leer y discutir, no
un número de confianza — un 0.87 no explica nada, solo suena a que sí.

## Alternativas consideradas

- **Guardar el veredicto del LLM en una columna aparte, "solo informativo", sin publicarlo.**
  Descartado, y es la propuesta más razonable de las malas. En cuanto el dato existe, alguien
  lo pinta en el panel de revisión "para ayudar al revisor", y a partir de ahí el gate humano
  deja de ser una revisión independiente y pasa a ser gente confirmando lo que sugiere un
  modelo. El sesgo de automatización está bien documentado; la forma de evitarlo es no tener
  el dato.
- **Confiar en la revisión de código para que nadie persista el veredicto.** Descartado: es lo
  que este ADR existe para no tener que hacer. Los controles que dependen de la atención humana
  sostenida fallan en el peor momento.
- **Validar la regla con un CHECK contra un catálogo de reglas en otra tabla.** Considerado y
  aplazado: hoy no hay ninguna regla escrita todavía, y una FK a un catálogo vacío obligaría a
  poblarlo antes de poder insertar nada. Se revisita cuando el clasificador exista.

## Consecuencias

- El pipeline necesita que el clasificador por reglas exista para poder insertar una
  `deteccion`: no hay atajo para arrancar publicando lo que diga el LLM. Es una restricción
  incómoda al principio y es intencionada.
- Cualquier análisis futuro del tipo "¿qué tal clasificaría el modelo?" tiene que hacerse
  fuera de la tabla `deteccion` — por ejemplo, en un experimento contra el gold set. No entra
  en el flujo de producción.
- Las tres columnas (`origen`, `regla_aplicada`, `extraccion_json`) hacen que el sistema pueda
  responder por escrito y por fila a "¿de dónde sale esta afirmación?". Eso es lo que separa
  una herramienta de vigilancia normativa defendible de un generador de opiniones con aspecto
  técnico.
