# 0001 — Arquitectura y alcance de Faro Cuir

## Contexto

Faro Cuir es la práctica final de un máster de Ciberseguridad e IA, con un plazo de
~6 semanas. Es un sistema de vigilancia normativa: monitoriza a diario 18 fuentes
oficiales (BOE + 17 boletines/parlamentos autonómicos) para detectar cambios legislativos
que afecten a los derechos del colectivo LGTBI+, con foco especial en las personas trans.

Dado el plazo y que el tribunal evalúa tanto el rigor de seguridad y diseño como el
código en sí, había que fijar desde el arranque: qué stack, qué arquitectura de
ejecución para la ingesta periódica, y — la decisión más delicada, porque el dominio
es políticamente sensible — qué papel juega el sistema frente al contenido que procesa.
Estas tres decisiones condicionan todo lo que viene después, así que quedan documentadas
aquí en vez de derivarse implícitamente del código.

## Decisión

### Stack

| Capa | Elección | Por qué |
|---|---|---|
| Backend | Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2.0 | Tipado estático real (Pydantic + mypy estricto), ecosistema maduro para lo que pesa aquí: parseo de XML/PDF hostil y validación de datos, no rendimiento bruto. |
| DB | PostgreSQL 16 | Full-text search con configuración `spanish` incorporada, sin dependencias externas. Collation ICU `es-ES` para ordenar/comparar texto en español correctamente. |
| Worker | Script Python idempotente en su propio contenedor, lanzado por cron | Ver sección siguiente. |
| Frontend | React 18 + TypeScript + Vite + TailwindCSS | Rapidez de iteración sobre UI de datos (mapa, feed, diffs) sin escribir infraestructura de build a mano. |
| LLM | Interfaz propia (`llm/provider.py`), proveedor-agnóstica | El input al LLM es texto público de boletines oficiales — no hay problema de privacidad en usar una API externa — pero no queremos acoplar el pipeline a un proveedor concreto. Ollama local queda documentado como alternativa de independencia/coste, no como plan A. |

### Worker cron, no Celery

La ingesta es: una vez al día (o bajo demanda manual), recorrer 18 fuentes, descargar
sumarios, filtrar, extraer y clasificar. Es un batch periódico con volumen bajo — no un
sistema que necesite colas distribuidas, reintentos con backoff sofisticado entre
workers, ni escalado horizontal. Un script Python idempotente (mismo input, mismo
resultado, seguro de re-ejecutar) lanzado por cron dentro de su propio contenedor cubre
esto sin añadir una pieza de infraestructura (broker, workers, monitorización de colas)
que ninguna parte del sistema necesita explotar.

### El sistema publica el diff y la fuente, nunca un juicio propio

Regla de oro número 2 de `CLAUDE.md`. El pipeline es:

```
Documento → Prefiltro léxico → Extractor LLM → Clasificador por diff → Gate humano → Alerta
```

El LLM **extrae hechos** (qué norma, qué artículos, qué cambia, quién emite, qué ámbito) en
un JSON estructurado y validado contra un esquema Pydantic. Nunca escribe ni emite "esto es
un retroceso". La clasificación avance/retroceso/neutro/indeterminado la deriva un
**clasificador por reglas auditables** que compara el texto anterior y el nuevo — no la
opinión de un modelo. Y antes de que cualquier detección se convierta en alerta pública,
pasa por un gate humano obligatorio, sin excepción.

Lo que el sistema publica siempre es: el texto de antes, el texto de después, la fuente
oficial, y la clasificación derivada del diff con la regla que la produjo. Nunca un
veredicto no verificable de "esto es bueno o malo".

## Alternativas consideradas

- **Node.js en vez de Python para el backend.** Descartado por ahora: el ecosistema Python
  tiene mejor soporte para lo que domina este proyecto (parseo XML endurecido, tipado con
  mypy, librerías de NLP si hicieran falta más adelante). Si se cambia, se documenta en un
  ADR nuevo que rehaga esta sección de stack, no el diseño del pipeline.
- **Celery + Redis/RabbitMQ para la ingesta.** Descartado explícitamente (ver sección 8 de
  `CLAUDE.md`, "fuera de alcance"). Es la arquitectura correcta para *otro* problema —
  alto volumen, necesidad real de paralelismo entre workers — que este proyecto no tiene
  en 6 semanas ni en el volumen de 18 fuentes/día.
- **Dejar que el LLM clasifique directamente (avance/retroceso) sin una capa de reglas
  intermedia.** Descartado: un LLM clasificando cambios legislativos como "avance" o
  "retroceso" sin una regla auditable detrás es, de facto, el sistema emitiendo una opinión
  política encubierta como un hecho técnico. Es exactamente el riesgo que la regla de oro
  número 2 existe para evitar, y además sería imposible de defender ante el tribunal o ante
  un usuario que pregunte "¿por qué esto es un retroceso?".
- **Publicación totalmente automática, sin revisión humana.** Descartado (sección 8 de
  `CLAUDE.md`). El coste de un falso positivo publicado sin revisar — una alerta pública
  incorrecta sobre un cambio legislativo en un dominio politizado — es alto y asimétrico
  frente al coste de un pequeño retraso por el gate humano.

## Consecuencias

- El worker cron es más simple de operar y depurar que una arquitectura de colas, pero no
  escala horizontalmente; si algún día el volumen de fuentes creciera muy por encima de 18,
  habría que revisitar esta decisión explícitamente.
- La separación estricta extracción/clasificación/gate humano añade una etapa más al
  pipeline (y un modelo de datos con `deteccion` y `cola_revision` como entidades propias,
  ver sección 5 de `CLAUDE.md`) en vez de "el LLM decide y ya" — es más trabajo de
  implementación, pero es la única forma de que la sección 6.7 (inyección de prompt) y la
  regla de neutralidad política sean cumplibles de verdad, no solo aspiracionales.
- Ningún dato de `deteccion.clasificacion` puede derivarse jamás de un campo de texto libre
  del LLM; siempre de una regla versionada y testeada contra el gold set (`tests/gold_set/`,
  sección 7 de `CLAUDE.md`). Esto es una restricción de diseño permanente sobre cualquier
  cambio futuro al clasificador, no solo la primera implementación.
