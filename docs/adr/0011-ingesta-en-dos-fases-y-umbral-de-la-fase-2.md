# 0011 — Ingesta en dos fases: la fase 2 se descarga entera, y el prefiltro deja de decidir qué se descarga

## Contexto

`CLAUDE.md` 7.1 planteaba la ingesta en dos fases —sumario (barata) y texto íntegro (cara)— y
dejaba abierto el umbral con el que se dispara la segunda, con una instrucción explícita:

> *Pendiente de medir antes de fijar el umbral. Si descargar el día entero resulta asumible
> —y con esos volúmenes es plausible—, entonces la opción más segura es no filtrar nada en
> fase 1 y usar el prefiltro solo para priorizar, no para descartar. Decidirlo con números
> medidos y escribirlo en un ADR, no por intuición en ninguna de las dos direcciones.*

Este ADR es esa decisión, y los números son medidos.

El problema de fondo es que hoy el prefiltro léxico (ADR 0007) decide **sobre el título del
sumario**, que es lo único que trae la fase 1. Y el título es exactamente lo que quien redacta
un retroceso controla: una instrucción que desmonta un derecho no se titula a sí misma como
tal. Decidir sobre el título es delegar el filtro en el redactor.

## Medición

Script: `backend/scripts/medir_fase2.py`, ejecutable contra los sumarios ya ingeridos:

```bash
docker compose exec worker python -m scripts.medir_fase2 --pausa 0.3 --salida /tmp/fase2.json
```

Muestra: los **dos días completos** del BOE que hay ingeridos, **436 normas**, descargadas
todas (`BOE-S-2023-51` del 2023-03-01, 179 normas; `BOE-S-2024-305` del 2024-12-19, 257).
436 descargas, **0 errores**, todas a través de `security/url_guard` (ADR 0006).

### 1. Descargar el día entero cuesta prácticamente nada

| | dos días (436 normas) | por día de BOE |
|---|---|---|
| Bytes | 8,54 MB | ~4,3 MB |
| Tiempo de red puro | 20,3 s | ~10 s |
| Reloj con pausa de cortesía de 0,3 s | 168,8 s | ~85 s |
| Latencia por petición | media 46,5 ms · mediana 35,3 ms · p95 79 ms · máx 1.118 ms | |
| Tamaño del texto | media 12.031 car. · mediana 2.513 · máx 645.534 | |

Un día entero del BOE son **cuatro megas y diez segundos de red**. Ese es todo el ahorro que
un umbral podría disputar.

### 2. El umbral bajo candidato no aporta casi nada, y lo poco que ahorra no vale lo que cuesta

Umbral candidato = léxico actual sobre el título **OR** patrones estructurales
(«se modifica», «queda sin efecto», «se deroga», «cartera de servicios», «anexo»,
«instrucción»…).

- Dispara en **12 de 436** items (2,8 %).
- Ahorraría **7,75 MB de 8,54** — es decir, unos 4 MB y 9 segundos al día.

### 3. El número que decide: decidir sobre el título pierde lo que importa

Reevaluando el **mismo vocabulario léxico** sobre el texto íntegro descargado:

- El título marca relevante **1** norma de 436. El texto íntegro marca **24**.
- **23 normas que el título descartaba, el cuerpo las dispara.** De ellas, **9 con término
  directo** (no de contexto genérico).
- **El umbral bajo candidato rescata 1 de esas 23. Y 1 de las 9 directas.**

Ese último dato es el que cierra la discusión: un umbral sobre el título **no recupera lo que
el título pierde**, porque el problema no es que el umbral esté mal calibrado, es que la
información no está en el título. Entre las 9 hay la Ley 3/2023 de Empleo (titulada «de
Empleo», y su texto contiene `lgtbi`, `identidad de género`, `expresión de género`) y una
Resolución de la Secretaría de Estado de Sanidad cuyo título es puramente administrativo.

### 4. Pero el LLM sí es caro, y muchísimo

Una extracción real medida en esta máquina (CPU, `qwen2.5:3b-instruct`, ADR 0008), con el tope
actual de 4.000 caracteres: **133,9 segundos**. A 436 normas por día eso son **~16 horas de
CPU por cada día de BOE**. La descarga es gratis; la llamada al modelo no lo es ni de lejos.

### 5. El bloque `<analisis>` confirma el eje referencial y es mejor de lo previsto

- **100 %** de los documentos de texto íntegro traen `<analisis>`. Solo **43 de 436** (9,9 %)
  traen referencias a normas anteriores; **132 referencias** en total.
- La estructura real (verificada, no deducida) es
  `analisis > referencias > anteriores > anterior[@referencia]`, y cada una trae **el verbo**
  (`MODIFICA` ×67, `DEROGA` ×7, `AÑADE`, `SUSTITUYE`…) y el texto de qué artículos toca.
- **13 normas de 436 modifican o derogan otra norma. De ellas, el léxico sobre el título
  detecta 1.** El eje referencial no duplica al léxico: cubre un hueco que el léxico no ve.
- Ese bloque **solo existe en el XML de texto íntegro**: en fase 1 no está. El eje referencial
  es, por construcción, un eje de fase 2.

## Decisión

**1. La fase 2 se descarga entera, sin umbral. El prefiltro deja de decidir qué se descarga.**

Todo item del sumario baja su texto íntegro. No hay estado del prefiltro que impida la
descarga. Cuesta 4 MB y 10 s al día, y elimina de raíz la clase de fallo más grave del
sistema: el falso negativo invisible por un título anodino.

**2. El prefiltro pasa a ser la puerta del LLM, no la de la red.** Es donde el coste está de
verdad (134 s por llamada). Se evalúa **sobre el texto íntegro**, no sobre el título.

**3. El prefiltro sigue evaluándose también sobre el título, pero solo para priorizar.** Sirve
para ordenar la cola del extractor —lo que más señal da, primero— y para poder medir después
cuánto habría perdido decidir ahí. Nunca para descartar.

**4. Límite de peticiones por ejecución y pausa entre descargas** (6.2), ya implementados en el
script de medición y obligatorios en el worker: 0,3 s de pausa, que es lo que convierte 10 s de
red en 85 s de reloj. Es cortesía con la fuente y freno propio si un sumario manipulado
declarara miles de items.

**5. El umbral asimétrico de 7.1 se cumple llevándolo al extremo: el umbral de descarga es
cero.** La asimetría que describía la sección sigue siendo la razón — un falso positivo cuesta
una petición HTTP, un falso negativo es el fallo total del sistema — solo que medida, resulta
que el lado barato es *tan* barato que el umbral óptimo es no tener ninguno.

## Alternativas consideradas

- **Mantener el umbral bajo sobre el título** (lo que 7.1 proponía por defecto). Descartada por
  los números: ahorra 4 MB al día y deja fuera 8 de las 9 normas con término directo que el
  título no delata. Paga un precio nulo por un riesgo alto.
- **Descargar todo y además mandarlo todo al LLM.** Es lo más seguro sobre el papel y cuesta 16
  horas de CPU por día de boletín. Inviable con el modelo local (ADR 0008), y subir de modelo
  para conseguirlo entra en «cambiar de modelo buscando calidad» sin gold set, prohibido por la
  sección 8. Si algún día hay GPU, esta decisión se revisa: el archivo íntegro ya estará ahí, y
  reprocesar es idempotente por `sha256`.
- **Filtrar por órgano emisor en fase 1.** Reduciría mucho, y por el motivo equivocado: el
  retroceso puede venir de cualquier ministerio (los ejemplos medidos incluyen Justicia,
  Sanidad y Trabajo), y una lista de emisores «sospechosos» sería un juicio político del
  sistema, contra la regla de oro 2.
- **Descargar solo lo que el eje referencial marque.** Imposible por orden de los hechos: el
  bloque `<analisis>` que alimenta ese eje viene *dentro* del texto íntegro. Habría que
  descargarlo para saber si hay que descargarlo.

## Consecuencias

- **`prefiltro_estado` cambia de significado, no solo de valores.** Ya no dice «esto se
  descarga o no», dice «esto va al extractor o no». La migración de 7.2 (tarea 0.b, ADR 0012)
  se hace con esta lectura: `sospecha` no es «descárgalo para mirar», es «ya está descargado y
  mirado, y merece un puesto en la cola del LLM».
- **El prefiltro se reevalúa sobre el texto íntegro**, lo que cambia su calibración por
  completo y lo hace ahora mismo poco preciso: de las 23 normas que el cuerpo dispara y el
  título no, buena parte son convocatorias de oposición que citan la Ley 4/2023 en el temario.
  El vocabulario actual, pensado para títulos, marca presencia; sobre un texto de 200.000
  caracteres hay que mirar **cuántos** términos directos aparecen, no si aparece alguno. Dato
  medido que lo respalda: la Ley 4/2023 dispara **43** términos, la Ley Orgánica 1/2023 (el
  negativo difícil del gold set) **11**, y la Ley de Empleo **9**. Calibrar ese corte es
  trabajo de la tarea 0.b y solo se podrá validar con el gold set (7.8).
  **Este ADR no lo resuelve y no debe leerse como si lo resolviera.**
- **El gold set se etiqueta sobre el texto íntegro** (7.8), lo cual ya era el plan, y ahora
  además es coherente con lo que el pipeline hace de verdad.
- El archivo íntegro con sello (6.5) gana cobertura completa: se archiva el cuerpo de **todas**
  las normas del día, no solo el de las que un filtro dejó pasar. Para un proyecto cuyo valor
  es documentar lo que se publicó, esto es una mejora por sí sola, al margen de la detección.
- Almacenamiento: ~4,3 MB/día → **~1,6 GB/año** de un solo boletín. Asumible, y hay que tenerlo
  presente al añadir las fuentes autonómicas.
- El script `backend/scripts/medir_fase2.py` queda en el repo para poder rehacer esta medición
  cuando se añadan fuentes con otro volumen. No es código de producción y nadie del pipeline lo
  importa.
