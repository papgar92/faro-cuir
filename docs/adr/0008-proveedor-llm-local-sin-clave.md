# 0008 — Proveedor LLM local (Ollama), sin clave y sin coste

## Contexto

El extractor (etapa 2) necesita un modelo. La interfaz `ProveedorLLM` ya deja la elección
abierta; este ADR fija cuál es la opción por defecto y por qué.

Restricción del humano, explícita: **coste 0 € y el mínimo de recursos que tenga que
conseguir**. A eso se suman dos condiciones del proyecto que empujan en la misma dirección:

- El **gold set** son 150-200 documentos que habrá que pasar por el extractor, más las
  reejecuciones al ajustar el prompt. Son cientos o miles de llamadas.
- El input es **texto público** de boletines oficiales, así que no hay razón de privacidad
  que obligue a lo local — pero tampoco ninguna que lo desaconseje.

Hardware disponible: 32 GB de RAM, sin GPU dedicada (gráfica integrada). Inferencia en CPU.

## Decisión

**Ollama en local como proveedor por defecto. Ninguna clave de API en ningún sitio.**

- `llm/ollama.py` implementa `ProveedorLLM` contra `http://127.0.0.1:11434`.
- Modelo, URL y timeout salen de `config.py` (entorno), nunca del código. Cambiar de modelo
  es una variable de entorno.
- Se pide a Ollama `format: "json"`, `temperature: 0` y `seed` fijo. El determinismo importa:
  una extracción de hechos que varíe entre ejecuciones sobre el mismo documento no es
  reproducible, y sin reproducibilidad el gold set no mide nada.

## Alternativas descartadas

- **API alojada de pago** (la opción por defecto que asumía `CLAUDE.md` sección 0). Mejor
  calidad por llamada, pero incumple la restricción de coste y, con el volumen del gold set,
  el gasto no sería simbólico.
- **Nivel gratuito de un proveedor alojado.** Es la alternativa real y no es mala: cero coste
  y mejor modelo. Se descarta por tres motivos: obliga a conseguir y custodiar una clave
  (justo lo que se pide evitar), impone cuotas por minuto que estorban al construir el gold
  set, y el modelo detrás de un nombre comercial cambia sin avisar — lo que hace que "el
  modelo dijo esto el día X" deje de ser reproducible para el tribunal.
- **Un modelo grande en local.** Sin GPU dedicada, un 7-8B en CPU es utilizable pero lento.
  Se empieza por uno pequeño (~3B) y se sube solo si el gold set demuestra que hace falta:
  el esquema Pydantic descarta lo que no cumpla el contrato, así que un modelo pequeño que
  falla a veces cuesta un reintento, no una extracción mala colada.

## Consecuencias

- **El proyecto no depende de ningún tercero ni de ningún secreto.** No hay clave que rotar,
  filtrar ni meter en CI. Para un proyecto de un máster de ciberseguridad, eso vale más que
  unos puntos de calidad del modelo.
- **La calidad de la extracción bajará** respecto a un modelo grande. Es aceptable
  precisamente porque el LLM no dicta veredictos (ADR 0002): extrae hechos que después se
  validan contra un esquema y se clasifican con reglas auditables. El coste de un fallo del
  modelo es una extracción descartada, no una alerta falsa.
- **La medida real la dará el gold set.** Hasta entonces, no se afirma nada sobre la calidad
  del extractor. Si el gold set muestra que el modelo pequeño no llega, la vía de escape es
  una variable de entorno.
- **Excepción documentada a la puerta única de salida HTTP (ADR 0006).** `llm/ollama.py` no
  pasa por `url_guard`, que rechaza toda IP no global y por tanto bloquearía `127.0.0.1`.
  La excepción es correcta porque url_guard existe para URLs **propuestas por una fuente
  hostil** (los enlaces de un sumario), e impedir que un tercero elija el destino. La URL de
  Ollama la escribimos nosotros en la configuración. La excepción queda acotada a ese único
  destino; si algún día el endpoint del LLM pudiera venir de contenido ingerido, esta
  decisión deja de valer.
- **En CI no hay Ollama**, así que los tests usan un transporte simulado y `ProveedorGuionizado`.
  Lo que se prueba es el contrato y el manejo de errores, no la calidad del modelo.

## Cómo se arranca

```bash
# Una vez: instalar Ollama (gratis) y descargar el modelo.
ollama pull qwen2.5:3b-instruct
```

Nada más. Si Ollama no está escuchando, el proveedor falla con un mensaje que dice
exactamente qué ejecutar.
