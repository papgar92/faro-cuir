# CLAUDE.md — Faro Cuir

> Instrucciones persistentes para Claude Code. Léete este archivo entero al inicio de cada
> sesión. Si vas a tomar una decisión que contradiga algo de aquí, **para y pregúntame**.
>
> **Aquí están las reglas; en [`ESTADO.md`](ESTADO.md) está dónde estamos** (la sección 11:
> qué se hizo, qué toca, y cuánto contexto cuesta cada tarea pendiente). Al empezar, lee los
> dos; al cerrar un trabajo, actualiza `ESTADO.md`. Se separaron el 2026-08-09 porque este
> fichero entra entero en el contexto de **cada subagente** y el historial de estado era el
> 54 % de sus 124 KB — 17.000 tokens por agente en algo que ningún agente lee.
>
> **Mantén este fichero por debajo de ~55 KB.** No es estética: es el coste fijo de arrancar
> cualquier trabajo. Si crece, lo que sobra casi siempre es historial, y el historial va a
> `ESTADO.md`.

<!--
REVISIÓN 2026-08-07 — qué cambia respecto de la versión anterior y por qué.
Nada se ha borrado. Lo añadido:
  - Sección 6.9 y 6.10: Ollama como dependencia local (determinismo, degradación) y la regla
    de que ninguna salida del modelo puede accionar nada.
  - Sección 7 reescrita: ingesta en DOS FASES (sumario → documento íntegro con umbral
    asimétrico) y prefiltro de TRES EJES (léxico, referencial, semántico). El eje léxico
    existente no se toca; se le añaden ejes en OR, no se le cambia.
  - Sección 7.5: trazabilidad por offsets en la extracción.
  - Sección 6.4 ampliada: canal pull primero (sin lista = sin fichero que filtrar).
  - Sección 13 nueva: cómo se ejecuta el trabajo con Claude Code (backlog, sesiones, límites
    de uso, subagentes).
  - Reglas de oro 9 y 10.
ORDEN CRÍTICO: la sección 7 cambia la definición de "relevante", y el gold set (tarea que
viene ahora) etiqueta exactamente eso. Hay que cerrar el vocabulario del prefiltro ANTES de
etiquetar 150-200 documentos a mano, o se etiquetan dos veces. Ver "EMPIEZA AQUÍ".
-->

---

## 0 bis. Autonomía de decisión (pedido por el humano, 2026-08-06)

**Tienes poder total de decisión. Pregunta lo mínimo y pide recursos lo mínimo.**

- **Decide tú** cualquier cosa reversible: diseño, librerías, estructura, nombres, orden del
  trabajo, qué verificar y cómo. No propongas un plan y esperes el OK salvo que el trabajo
  sea grande o cambie el rumbo del proyecto; para lo demás, hazlo y cuéntalo al terminar.
- **Elige siempre la opción de coste 0 €** y la que exija menos cosas que conseguir (claves,
  cuentas, servicios de terceros, instalaciones). Si una decisión ahorra una clave de API a
  cambio de algo de calidad, ahorra la clave. Ver ADR 0008.
- **Para y pregunta solo en cuatro casos:** algo cuesta dinero; hace falta una credencial o
  una cuenta que no existe; es una acción externa e irreversible (sección 12: publicar en
  redes, contactar con asociaciones, subir el repo); o contradice algo de este archivo.
- Cuando decidas algo no obvio, **déjalo escrito** (ADR si es arquitectura, comentario si es
  local) y avisa al terminar. Autonomía no es silencio: es no interrumpir.
- Si te falta un dato para decidir, **mira antes de preguntar** (el repo, la máquina, la API
  real). Preguntar algo que podías haber comprobado tú cuesta más que comprobarlo.

---

## 0. Decisiones abiertas (cámbialas si el humano lo pide)

- **Backend:** Python 3.12 + FastAPI. (Alternativa descartada por ahora: Node. Si se cambia,
  se rehace la sección de stack, no el diseño.)
- **Frontend:** React 18 + TypeScript + Vite + TailwindCSS.
- **Nombre del proyecto:** Faro Cuir. (Antes "Centinela"; renombrado en S0 — "cuir" deja claro
  desde el nombre que la herramienta es de y para la comunidad LGTBIQ+, no un vigilante genérico.
  La carpeta local del repo sigue llamándose `Centinela/`; no se ha movido, solo el nombre de
  producto. Historial de commits previos al cambio conserva el nombre antiguo, no se reescribe.)
- **LLM:** proveedor-agnóstico vía una interfaz propia (`llm/provider.py`). **Por defecto,
  Ollama en local: sin clave de API, sin coste y sin cuota** (ADR 0008). Se invirtió la
  decisión original —que asumía una API externa de pago— por la restricción de coste 0 € del
  humano y porque el gold set son cientos de llamadas. El input es texto público de
  boletines, así que no había motivo de privacidad en ninguna dirección. Modelo y URL salen
  de entorno: cambiar de proveedor es una variable, no un refactor.
  **Las reglas operativas de esa integración están en la sección 6.9. La abstracción no se
  toca: el determinismo y el esquema viven en el adaptador (`llm/ollama.py`), no en la
  interfaz.**

---

## 1. Qué es esto

**Faro Cuir** es un sistema de vigilancia normativa que monitoriza a diario los boletines
oficiales españoles en **tres niveles de administración** para detectar cambios normativos que
afecten a los derechos del colectivo LGTBI+, con foco especial en las personas trans:

- **Estatal:** BOE (1 fuente).
- **Autonómico:** 17 boletines/diarios oficiales.
- **Local:** **43 Boletines Oficiales de la Provincia** (ADR 0014, decidido el 2026-08-08).

**61 fuentes en total.** La capa local se vigila por el BOP y no municipio a municipio porque
una ordenanza municipal **no entra en vigor si no se publica íntegra en el BOP** (Ley 5/2002,
`BOE-A-2002-6467`): el municipio no es una fuente, es un emisor que publica en la fuente
provincial. Eso convierte 8.131 municipios en 43 boletines. Ver `docs/fuentes.md`.

**Registradas ≠ vigiladas:** el guardarraíl de la sección 8 (máximo 5 fuentes integradas en la
primera iteración) sigue en pie y con 61 fuentes importa más, no menos.

Detecta el **retroceso silencioso**: no la reforma que sale en prensa, sino la instrucción de
rango bajo publicada un martes de agosto que desmonta un derecho sin titulares.

Es la **práctica final de un máster de Ciberseguridad e IA**. Plazo: ~6 semanas. Por tanto:

- El rigor de seguridad y la calidad del diseño **puntúan más** que la cantidad de features.
- Todo lo relevante se **documenta** (ADRs, THREAT-MODEL, EIPD). El tribunal lee el repo.
- Ante la duda entre "una feature más" y "hacer bien lo que hay", siempre lo segundo.

**Pitch:** "El Rainbow Map de ILGA-Europe, pero por comunidad autónoma y en tiempo real."

---

## 2. Reglas de oro (no negociables)

1. **Seguridad primero.** Es un máster de ciberseguridad. Cada entrada externa es hostil hasta
   que se demuestre lo contrario. Ver sección 6.
2. **Neutralidad política.** El sistema **nunca emite un juicio propio**. Publica el *diff*
   (qué decía antes / qué dice ahora) y la fuente. La clasificación avance/retroceso se **deriva
   del diff con reglas auditables**, no de la opinión de un LLM. Ver sección 7.
3. **El LLM extrae hechos, no dicta veredictos.** Su salida es estructurada (qué norma, qué
   artículos, qué cambia, quién emite, qué ámbito). Nunca "esto es un retroceso".
4. **Gate humano obligatorio** antes de emitir cualquier alerta. Sin excepción.
5. **Minimización de datos.** Los suscriptores son dato sensible (revelan afinidad al colectivo).
   Ver sección 6.4.
6. **Nada de scope creep.** Ver sección 8. Si se te ocurre añadir monitorización de prensa o
   redes: no.
7. **Todo cambio de arquitectura → un ADR.** Ver sección 9.
8. **Nunca inventes fuentes, plazos ni artículos legales.** Si no lo has verificado, márcalo
   como `TODO(verificar)` y avisa al humano.
9. **Trazabilidad por offsets.** Todo hecho extraído por el LLM apunta a un rango de
   caracteres del texto archivado. Si el rango no se corresponde con lo que dice el modelo,
   la extracción se descarta. El revisor humano verifica contra la fuente, no contra la
   palabra del modelo. Ver 7.5.
10. **Nada que emita el modelo acciona nada.** Su salida es dato, nunca una URL que se
    descargue, una ruta que se abra, un comando que se ejecute ni una consulta que se
    interpole. Ver 6.10.

---

## 3. Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic |
| DB | PostgreSQL 16 (búsqueda full-text con configuración `spanish`) |
| Worker | Script Python idempotente lanzado por cron en su propio contenedor. **NO Celery** (overkill). |
| Parseo XML | `defusedxml` obligatorio. `lxml` solo con `resolve_entities=False`, sin DTD, sin red. |
| HTTP saliente | `httpx` con timeouts, allowlist de dominios y límite de tamaño de respuesta. |
| LLM | Interfaz propia en `llm/provider.py`. Cualquier proveedor detrás de ella. Adaptador por defecto: `llm/ollama.py` contra Ollama local. Ver 6.9. |
| Frontend | React 18, TypeScript, Vite, TailwindCSS |
| Tests | `pytest`, `pytest-cov` (back); `vitest` (front) |
| Lint/format | `ruff` (lint+format), `mypy` (estricto en `services/` y `llm/`) |
| Contenedores | Docker + docker-compose |
| CI | GitHub Actions: `ruff` → `mypy` → `alembic` → `pytest` → `pip-audit` → `gitleaks` |

Sin dependencias nuevas para la watchlist ni para el driver de sesiones: YAML versionado y
bash. Coste 0 € y una cosa menos que auditar.

---

## 4. Estructura del repositorio

```
farocuir/                      # nombre canónico del proyecto; la carpeta local sigue siendo Centinela/
├── CLAUDE.md                  # este archivo
├── README.md
├── SECURITY.md                # política de seguridad + resumen del modelo de amenaza
├── THREAT-MODEL.md            # STRIDE + actores de abuso
├── docker-compose.yml
├── .env.example               # variables; NUNCA .env con secretos reales en el repo
├── .github/workflows/ci.yml
├── .claude/
│   └── agents/                # subagentes de proyecto (sección 13.4)
├── tasks/
│   ├── backlog/               # una tarea por fichero, ejecutable en sesión limpia (13.2)
│   ├── done/
│   └── log/                   # salida jsonl de cada sesión headless (gitignored)
├── run_agent.sh               # driver de sesiones (13.3)
├── config/
│   ├── vocabulario.yaml       # eje léxico del prefiltro (hoy en pipeline/prefiltro.py)
│   └── watchlist.json         # eje referencial: normas objetivo (7.3)
├── docs/
│   ├── adr/                   # Architecture Decision Records (0001-*.md, ...)
│   ├── fuentes.md             # AUDITORÍA DE LAS 18 FUENTES (entregable clave)
│   └── eipd.md                # Evaluación de Impacto en Protección de Datos
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app
│   │   ├── config.py          # settings vía pydantic-settings, todo desde entorno
│   │   ├── models/            # SQLAlchemy
│   │   ├── schemas/           # Pydantic
│   │   ├── api/               # routers (público sin auth + panel de revisión con auth)
│   │   ├── services/          # lógica de negocio
│   │   ├── ingest/            # un módulo por tipo de fuente (boe.py, boja.py, ...)
│   │   ├── pipeline/          # prefiltro, watchlist, normalizacion, extractor, clasificador, diff
│   │   ├── llm/               # provider.py + ollama.py + prompts versionados
│   │   ├── security/          # xml_safe.py, url_guard.py, hashing.py, sellado.py
│   │   └── webhooks/          # firma HMAC entrada/salida
│   ├── worker/                # entrypoint del cron de ingesta
│   ├── alembic/
│   ├── tests/
│   │   └── gold_set/          # corpus dorado (esquema.py, casos/, README.md)
│   └── pyproject.toml
└── frontend/
    ├── src/
    │   ├── components/
    │   ├── pages/
    │   ├── api/               # cliente tipado del backend
    │   └── main.tsx
    └── package.json
```

`config/vocabulario.yaml` es una migración pendiente y **no urgente** del diccionario que hoy
vive en `pipeline/prefiltro.py`; se hará cuando toque tocar el vocabulario por otra razón, no
como trabajo propio. `VERSION_VOCABULARIO` sigue mandando en cualquier caso.

---

## 5. Modelo de dominio

Entidades núcleo (nombres reales de tabla en snake_case):

- **fuente** — un origen de datos. Campos: `id`, `nombre`, `tipo` (`boe`|`boletin_autonomico`|
  `parlamento`), `ccaa`, `formato` (`api`|`rss`|`html`|`pdf`), `url_base`, `licencia_reutil`,
  `activa`.
- **documento** — un documento crudo ingerido. `id`, `fuente_id`, `identificador_oficial`,
  `fecha_publicacion`, `url_original`, `sha256`, `sello_tiempo`, `ruta_almacen`, `estado_pipeline`,
  **`tipo`** (`sumario`|`texto_norma`|`consolidado`). El `sha256` + `sello_tiempo` forman el
  **archivo íntegro verificable** (ver sección 6.5). **Tres clases de fila**: el sumario del día
  y el cuerpo de cada norma (ADR 0015), más el **texto consolidado** de una norma vigilada (ADR
  0018), que es de donde sale el texto anterior de un artículo modificado. La garantía de 6.5 se
  implementa aquí una sola vez y por eso ninguna de las tres tiene tabla propia; `tipo` es una
  columna y no una convención porque `GET /api/documentos` tiene que poder filtrarla — sin ella
  listaría cientos de cuerpos al día como si fueran boletines, en silencio.
  **`consolidado` no es un `texto_norma` más y la distinción es del ADR 0018**: `texto_norma` es
  lo que la fuente publicó aquel día —el hecho que este archivo existe para conservar— y
  `consolidado` es una elaboración posterior de la propia fuente, que cambia cada vez que alguien
  modifica la norma. Confundirlos haría que el archivo dejara de poder afirmar «el día X esto
  decía exactamente esto».
- **norma** — un ítem normativo identificado dentro de un documento. `id`, `documento_id`,
  **`documento_texto_id`** (dónde está archivado su cuerpo; NULL = cola de la fase 2),
  `titulo`, `rango` (ley|decreto|orden|instruccion|resolucion|proposicion), `organo_emisor`,
  `ambito` (sanitario|educativo|laboral|documental|general|...).
  Más las columnas del prefiltro: `prefiltro_estado`, `prefiltro_terminos`,
  `prefiltro_version`, `prefiltro_evaluado_en`. **`prefiltro_estado` pasa a tener cuatro
  valores** (ver 7.2): `pendiente` | `sospecha` | `relevante` | `descartada`.
- **version_norma** — versionado. Una norma que modifica a otra genera una nueva versión con
  referencia a la anterior. Aquí vive el diff (texto_anterior / texto_nuevo por artículo).
  **Se puebla desde el ADR 0018**, con el texto consolidado del BOE: `norma_id` es la norma
  **modificadora** (la que ingerimos), `norma_afectada` el identificador de la modificada —que
  casi nunca tiene fila en `norma`, porque es de hace años y no salió de ningún sumario nuestro—,
  `bloque` el ancla dentro del consolidado y `documento_consolidado_id` la evidencia archivada
  con su huella. `texto_anterior` a NULL significa **alta**, no «no lo sabemos».
- **deteccion** — el resultado del pipeline sobre una norma. `id`, `norma_id`,
  `extraccion_json` (hechos del LLM, **con offsets**, ver 7.5), `clasificacion`
  (avance|retroceso|neutro|indeterminado), `severidad`, `confianza`, `origen`
  (`derivado_diff`|`heuristica`), `regla_aplicada`, `revisada` (bool).
- **cola_revision** — items pendientes de gate humano. Estado: `pendiente`|`aprobada`|`descartada`.
- **alerta** — una detección aprobada y emitida. `id`, `deteccion_id`, `emitida_en`.
- **suscriptor** — destinatario de alertas. **Minimizado** (ver 6.4). `id`, `email_hash`,
  `webhook_url` (opcional), `ccaa_interes[]`, `token_baja_opaco`. **El canal principal no
  crea filas aquí** (ver 6.4).

Regla de versionado: **nunca se sobrescribe una versión de norma**. El histórico es inmutable;
esa inmutabilidad es parte del valor (archivo de lo que realmente se publicó).

---

## 6. Requisitos de seguridad (esto es lo que puntúa)

Estás ingiriendo XML y PDF de 18 fuentes externas que no controlas. Esa es la superficie de
ataque principal. Trátalo así.

### 6.1 Parseo de contenido no confiable
- **XXE:** `defusedxml` siempre. Prohibido `xml.etree` o `lxml` sin endurecer. Entidades
  externas OFF, resolución de red OFF, DTD OFF. Test que lo demuestre con un payload XXE.
- **Bombas XML / billion laughs:** límites de profundidad de anidamiento y de expansión de
  entidades. Test con payload.
- **Zip bombs:** si algún día se descomprime algo, límite de ratio y de tamaño total.
- **PDF:** extracción de texto solo. **Nada de OCR** (fuera de alcance, sección 8). Límite de
  tamaño y de páginas.

### 6.2 SSRF en la ingesta
El worker sigue URLs que vienen de los sumarios. Si no se validan, se convierte en tu proxy a la
red interna. `security/url_guard.py`: allowlist de dominios oficiales, rechazo de IPs privadas/
loopback/link-local, sin redirecciones a hosts fuera de la allowlist, timeouts y límite de bytes.

**La fase 2 (7.1) multiplica el número de URLs seguidas por día.** No es una excepción a nada:
toda URL de fase 2 pasa por `url_guard` igual que las de fase 1, y la única fuente legítima de
una URL sigue siendo el sumario oficial parseado. Añadir un límite de peticiones por ejecución
y una pausa entre descargas — cortesía con la fuente y freno propio si un sumario manipulado
declara miles de items.

### 6.3 Path traversal
Al nombrar ficheros descargados, nunca uses un valor de la fuente como nombre de archivo sin
sanear. Genera nombres a partir del `sha256`, no del título.

### 6.4 Datos de suscriptores (categoría especial, art. 9 RGPD)
Estar suscrito a alertas de derechos trans revela afinidad al colectivo. Por tanto:
- Sin perfilado, sin analítica de comportamiento, sin cookies de terceros.
- Email guardado como **hash con sal** siempre que el flujo lo permita; en claro solo el mínimo
  imprescindible para enviar, y cifrado en reposo si se persiste.
- Token de baja **opaco** (aleatorio), nunca derivado del email ni predecible.
- Los suscriptores **nunca** entran en el LLM ni en logs.

**Canal pull primero (ADR 0010, escrito e implementado el 2026-08-14).** El canal principal de
difusión es *pull*: web pública + feed Atom en `GET /api/alertas.xml`. Quien quiera enterarse se
suscribe con su lector y el sistema **no sabe quién es**. Sin lista, sin fichero, sin brecha
posible, y desaparece medio capítulo de cumplimiento. El correo y los webhooks quedan como vías
**secundarias y opcionales**, con doble opt-in y todo lo anterior.

**Nada de feeds personalizados ni de tokens por suscriptor**: una URL única por persona es una
lista de suscriptores con otro nombre, y encima una que viaja en la barra de direcciones. Hay un
test que lo fija.

Consecuencias operativas:
- La tabla `suscriptor` no se elimina, pero deja de ser el camino por defecto. El feed no
  tiene suscriptores que enumerar.
- **No se registran IPs de quien consulta la web ni el feed.** Los logs de acceso cubren qué
  normas se revisaron y quién aprobó qué; nunca quién leyó qué. Registrar IPs recrearía
  exactamente el fichero que el canal pull elimina, con menos control y sin consentimiento.
- El rate limiting de 6.8 ya funciona sin persistir IP (ventana en memoria, sin escritura).
  Mantenerlo así es requisito, no detalle.
- `docs/eipd.md` se articula sobre esta decisión: la evaluación cambia radicalmente cuando el
  tratamiento por defecto no recoge datos personales.

### 6.5 Archivo íntegro con sellado de tiempo
Al ingerir cada documento: `sha256` del contenido + sello de tiempo. Esto crea un archivo
verificable de lo que realmente se publicó, como respuesta técnica a las desindexaciones
administrativas sin registro público. Documentar el porqué en un ADR.

Con la fase 2 (7.1) esto se refuerza solo: se archiva el **texto íntegro** de todo lo que se
descarga, no solo la entrada del sumario. El sello aplica a cada cuerpo descargado.

### 6.6 Webhooks
- **Salida** (a Slack/Discord/n8n de las ONGs): firma HMAC-SHA256 del payload + timestamp +
  nonce anti-replay en cabecera. Documentar cómo verifica el receptor.
- **Entrada** (aprobación desde el panel, si aplica): verificar firma antes de procesar.

### 6.7 Inyección de prompt
Contenido no confiable entrando en un LLM. Improbable en un BOE, pero es el patrón a defender:
delimitación clara del contenido, el prompt de sistema nunca es sobreescribible por el
documento, y la salida del LLM se valida contra un esquema Pydantic (si no valida, se descarta,
no se "interpreta").

Ya implementado y verificado (ver sección 11): marcas largas de delimitación, eliminación de
esas marcas si el propio documento las contiene, y un test que **simula que la inyección
funciona** y comprueba que la salida se descarta igual. Esa es la defensa que cuenta.

Añadidos por la fase 2 y el eje referencial:
- El bloque `<analisis>` del XML del BOE (referencias a otras normas) es **entrada igual de
  hostil** que el articulado. El eje referencial (7.3) lo parsea; los identificadores que
  saque se validan contra formato conocido antes de compararse con la watchlist, y nunca se
  usan para construir una URL (ver 6.10).
- Los offsets (7.5) son también un control anti-inyección: una respuesta que afirme un texto
  que no está en el rango que ella misma declara se descarta automáticamente. Una inyección
  que consiga que el modelo invente contenido tiene que además acertar con las coordenadas
  del contenido inventado en un texto que no controla.

### 6.8 Higiene general
- Secretos solo por entorno. `.env` en `.gitignore`. `gitleaks` en CI.
- Cabeceras de seguridad en las respuestas (CSP, HSTS, X-Content-Type-Options, etc.).
- Rate limiting en la API pública desde el principio, no al final.
- Dependencias fijadas y auditadas.

### 6.9 Ollama como dependencia local (integración del LLM)

Todo el trabajo de LLM corre en Ollama local. Ni texto de boletines ni nada del sistema sale a
un servicio externo. La abstracción de `llm/provider.py` **no se rompe**: lo que sigue vive en
el adaptador `llm/ollama.py`, no en la interfaz.

1. **Puerta única.** Solo `llm/ollama.py` habla HTTP con Ollama. Mismo criterio que
   `url_guard` con el HTTP saliente y `xml_safe` con el XML. Ningún otro módulo importa el
   cliente ni conoce la URL.
2. **La URL de Ollama es la excepción declarada a la allowlist de `url_guard`** (ADR 0006):
   es un destino local y fijo de configuración, no una URL que venga de una fuente. Por eso
   mismo se valida al arrancar (host de la config, esquema y puerto esperados) y nunca se
   compone con nada dinámico. En docker vale `host.docker.internal` vía `extra_hosts`; fuera
   de docker, `127.0.0.1`. Ver sección 11.
3. **Salida estructurada siempre.** El adaptador pasa el esquema JSON derivado del modelo
   Pydantic (`Extraccion.model_json_schema()`) en el campo `format` de la petición, cuando el
   backend lo soporta. **Esto es una ayuda, no el control**: el control sigue siendo la
   validación Pydantic con `extra="forbid"`. Si la validación falla, se descarta; **un solo
   reintento** y a la vía de fallo normal (sin fila → la norma se reintenta sola en la
   siguiente pasada del worker). Nunca parseo de texto suelto, nunca "interpretar" una
   respuesta inválida, nunca reintento libre en bucle.
4. **Determinismo.** `temperature: 0`, `top_p` fijo y `seed` fijo, **fijados dentro del
   adaptador**, no expuestos en la interfaz (la interfaz no lleva parámetros de muestreo a
   propósito, ADR 0008 y sección 11). Una extracción del mismo texto con el mismo modelo y el
   mismo prompt debe dar el mismo resultado; hay un test que lo comprueba contra Ollama real
   y se salta si no hay Ollama disponible.
5. **Procedencia registrada.** Dentro de `extraccion_json` viajan: `modelo`, **`digest` del
   modelo** (de `/api/show`, porque una etiqueta como `qwen2.5:3b-instruct` puede apuntar a
   pesos distintos con el tiempo), `seed`, `version_prompt`, hash del prompt renderizado y
   `version_normalizacion` (7.5). Sin esto una evaluación del gold set no es reproducible ni
   comparable entre sesiones.
6. **Degradación ruidosa.** Si Ollama no responde, no hay respaldo heurístico, no hay
   "seguimos con lo que se pueda": el worker marca el trabajo como no procesado, lo dice en
   el log y sale con código distinto de cero. Un sistema de vigilancia que falla en silencio
   es peor que uno que no existe, porque genera confianza infundada.
7. **Presupuesto de contexto medido, no supuesto.** `MAX_CARACTERES_DOCUMENTO` es un
   parámetro de rendimiento del modelo pequeño en CPU (hoy 4.000, ver sección 11), no una
   decisión de calidad. **Está sin medir si un artículo cortado se entiende bien.** Cuando el
   gold set exista, medir; si hace falta, ventana deslizante con solapamiento en lugar de
   truncado, y los offsets de 7.5 se rebasan a la posición absoluta. No hacer esto antes de
   tener con qué medirlo.
8. **Ollama no se instala ni se descarga solo.** Si falta el modelo, se dice y se para; no se
   lanza un `pull` de gigabytes sin avisar.

### 6.10 La salida del modelo no acciona nada

Regla de oro 10, en concreto. La salida del LLM es **dato para revisión humana**, nunca una
instrucción para el sistema. En particular, y aunque el modelo lo devuelva:

- **Ninguna URL propuesta por el modelo se descarga.** Las URLs legítimas vienen del sumario
  oficial y pasan por `url_guard`. Si el modelo emite algo con forma de URL, se trata como
  texto.
- **Ninguna ruta de fichero propuesta por el modelo se abre ni se escribe.** Las rutas se
  derivan del `sha256` (6.3).
- Nada de la salida se interpola en SQL, en shell, en una plantilla ejecutable ni en HTML sin
  escapar. El frontend escapa la salida como contenido no confiable, porque lo es.
- Un identificador de norma extraído por el modelo se compara con la watchlist tras validar
  formato, pero **no se usa para construir una petición**.
- Al descartar una extracción se registran los **campos** que fallan, nunca lo que devolvió el
  modelo (ya implementado, ver sección 11): si fue manipulado para emitir un veredicto, ese
  texto no puede quedar en un log donde alguien lo lea como conclusión del sistema.

---

## 7. Pipeline de detección

```
[1] Ingesta fase 1 (sumario)  → prefiltro sobre el título: SOLO prioriza, nunca descarta
[2] Ingesta fase 2 (texto íntegro de TODOS los items del día, sin umbral — ADR 0011)
      → [3] Prefiltro 3 ejes sobre el texto completo  ──descartada──> fin
      → sospecha o relevante (= orden de la cola del LLM, que es lo caro)
      → [4] Extractor LLM (hechos + offsets)
      → [5] Clasificador por diff (reglas)
      → [6] Gate humano
      → Alerta
```

### 7.1 Ingesta en dos fases (umbral asimétrico)

El sumario diario trae título, emisor y metadatos. **El título es exactamente lo que un
retroceso silencioso puede redactar de forma anodina**, así que decidir sobre el título es
decidir sobre lo que el redactor controla. De ahí la regla:

- **Fase 1 (barata):** sumario XML del día. Se evalúan todos los items.
- **Fase 2:** descarga del XML de texto íntegro **de todos los items del día, sin umbral**.
- **El descarte definitivo solo ocurre después de leer el documento completo.** Nunca sobre
  el título.

En fase 1 un falso positivo cuesta una petición HTTP. Un falso negativo es invisible, no
aparece en ninguna métrica y es el fallo total del sistema. La asimetría es deliberada.

**MEDIDO Y DECIDIDO (2026-08-07, ADR 0011).** El umbral de la fase 2 **es cero**: se descarga
el día entero. Los números, sobre las 436 normas de los dos días ingeridos, descargadas todas:
un día de BOE son **~4,3 MB y ~10 s de red** (85 s de reloj con la pausa de cortesía). El
umbral bajo candidato ahorraba 4 MB al día y **rescataba 1 de las 23 normas que el título
descartaba y el texto íntegro dispara** (1 de las 9 con término directo). No es que el umbral
estuviera mal calibrado: la información no está en el título.

**Lo que sí es caro es el LLM:** 133,9 s por extracción medidos en esta máquina, o sea ~16 h
de CPU si se le mandara el día entero. Por eso **el prefiltro deja de ser la puerta de la red
y pasa a ser la puerta del LLM**, evaluándose sobre el texto íntegro; sobre el título solo
sirve para priorizar la cola, nunca para descartar. Reproducir la medición:
`backend/scripts/medir_fase2.py`. El `sha256` ya hace idempotente la descarga, así que
reprocesar no duplica.

### 7.2 Estados del prefiltro

`prefiltro_estado` pasa de tres a cuatro valores. Requiere migración y **ADR**:

| Estado | Significado | Consecuencia |
|---|---|---|
| `pendiente` | aún no evaluada | — |
| `sospecha` | indicio débil **sobre el texto íntegro ya descargado** | cola del extractor con prioridad baja; nunca se descarta sin revisar |
| `relevante` | indicio fuerte sobre el texto íntegro | cola del extractor con prioridad alta |
| `descartada` | descartada **tras** ver el texto completo | fin |

**Ojo, esto cambió con el ADR 0011 y es fácil leerlo mal:** ningún estado del prefiltro decide
ya qué se descarga —se descarga todo— sino qué entra en el LLM y en qué orden. `sospecha` no
es "descárgalo para mirar", es "ya está descargado y mirado, y merece un puesto en la cola".

`pendiente` ≠ `descartada` sigue siendo regla (ya está así). Se guarda además **qué eje
disparó** cada evaluación, no solo los términos: sin eso no se puede afinar un eje sin tocar
los otros.

**Aviso de migración (cuarta vez, ver sección 11):** al añadir el valor a la CHECK, el
autogenerate de alembic propondrá borrar CHECKs ajenas. Revisar SIEMPRE antes de aplicar y
comprobar después: `SELECT conrelid::regclass, conname FROM pg_constraint WHERE contype='c'`.

### 7.3 Prefiltro de tres ejes (OR, no AND)

Un item pasa si dispara **cualquier** eje. No se combinan con AND jamás: eso convierte dos
filtros de alto recall en uno de bajo recall.

**Eje 1 — léxico (existe, `pipeline/prefiltro.py`).** ~90 términos con variantes morfológicas
y clínicas antiguas, límites de palabra, categorías `DIRECTO`/`CONTEXTO` que no cambian la
decisión. No se toca su lógica; solo se le añade el estado `sospecha` para términos débiles.

**Aviso medido (ADR 0011), léelo antes de tocar este eje:** al pasar a evaluarse sobre el
texto íntegro en vez del título, este eje **cambia de calibración por completo** y ahora mismo
es poco preciso. De las 23 normas que el cuerpo dispara y el título no, buena parte son
convocatorias de oposición que citan la Ley 4/2023 en el temario. El vocabulario está pensado
para títulos y mide *presencia*; sobre 200.000 caracteres hay que mirar **cuántos** términos
directos aparecen. Los números que enseñan el corte: Ley 4/2023 → **43** términos; Ley Orgánica
1/2023 (el negativo difícil del gold set) → **11**; Ley 3/2023 de Empleo → **9**; una
resolución de Sanidad → **3**. Fijar ese corte es la tarea 0.b, y **validarlo solo lo puede
hacer el gold set**: no publiques un umbral numérico como si estuviera comprobado.

**Eje 2 — referencial (NUEVO, prioritario).** `config/watchlist.json` con normas objetivo por
identificador: Ley 4/2023, leyes trans autonómicas, reales decretos de cartera común de
servicios del SNS, currículos educativos, normativa de documentación e identidad. **Cualquier
disposición que modifique una norma de la watchlist pasa el filtro por definición, diga lo que
diga su texto.**

Este eje es el que cubre el agujero estructural del diccionario: una instrucción que elimina
un derecho no dice "identidad de género", dice "se modifica el epígrafe 4.3 del anexo II". Y
tiene una fuente de datos que ya conocemos: **el bloque `<analisis>` del XML de texto íntegro
del BOE, que trae las referencias a normas relacionadas.** Es el mismo bloque que se
despriorizó en `_texto_plano` por ruido para el LLM (sección 11) — ruido para el extractor,
señal para este eje. En fase 1 el sumario no lo trae, así que el eje referencial es **por
construcción un eje de fase 2**: habría que descargar el documento para saber si hay que
descargarlo. Con el ADR 0011 eso deja de ser un problema, porque se descarga todo.

**Estructura real del bloque, ya verificada (medición del ADR 0011), no la deduzcas otra vez:**

```
analisis > referencias > anteriores > anterior[@referencia="BOE-A-2015-11431"]
                                        ├── <palabra codigo="270">MODIFICA</palabra>
                                        └── <texto>el art. 33.4 f) de la Ley de Empleo…</texto>
                                    > posteriores > posterior[@referencia]
```

Es mejor materia prima de lo que esta sección suponía: **no dice solo "menciona esta norma",
trae el verbo** (`MODIFICA`, `DEROGA`, `AÑADE`, `SUSTITUYE`) y qué artículos toca. `posteriores`
son las normas que modificaron a esta *después*, así que no sirven para decidir en el día.
Números medidos sobre 436 normas: el 100 % de los documentos traen `<analisis>`, pero solo
**43 (9,9 %)** traen referencias anteriores y **13 modifican o derogan algo**. De esas 13, el
eje léxico sobre el título detecta **1**. El eje referencial no duplica al léxico: cubre lo que
el léxico no ve, y es barato porque afecta a una de cada diez normas.

`VERSION_WATCHLIST` con la misma mecánica que `VERSION_VOCABULARIO`: subirla obliga a
reevaluar lo anterior (`worker.run --reprefiltrar`).

**Eje 3 — semántico (hueco reservado, NO implementar ahora).** Similitud por embeddings
locales contra corpus de normas ya etiquetadas, para capturar perífrasis que esquive tanto el
diccionario como la watchlist. Depende del gold set y no cabe en el plazo. Dejar la interfaz
preparada y documentarlo como hoja de ruta. Ver sección 8.

### 7.4 Extractor LLM

Devuelve JSON estructurado validado por Pydantic: norma afectada, artículos, texto
anterior/nuevo, órgano, ámbito, **más los offsets de 7.5**. **No clasifica**: `extra="forbid"`
y la ausencia deliberada de campos de valoración hacen que el veredicto del modelo no tenga
dónde aterrizar. Ver 6.9 para las reglas de la llamada.

**Un artículo citado sin texto por ninguno de los dos lados es válido** desde el ADR 0016, y se
conserva como *puntero*. Antes se rechazaba la extracción entera, y eso hacía que el mejor caso
del corpus —una ley que suprime preceptos sin reproducirlos— fuera el único que el pipeline no
podía procesar. Las dos condiciones del ADR son parte de la regla, no detalles: **un puntero no
acciona nada por sí solo** (regla de oro 10; solo el catálogo de 7.6, leyendo el texto
archivado, produce clasificación) y **cuántos trae cada extracción se registra**. El resto del
contrato no se toca.

### 7.5 Trazabilidad por offsets — **implementada el 2026-08-16 (ADR 0013)**

Cada texto que la extracción afirma haber leído se localiza en el texto archivado y se guarda
con su rango de caracteres. Esto convierte la revisión humana en verificación en lugar de
confianza, y hace que una alucinación se detecte sola.

**Dos cosas cambiaron respecto a como estaba escrita esta sección, y las dos están razonadas en
el ADR 0013:**

- **Los offsets los calcula el sistema (`pipeline/anclaje.py`), no los pide al modelo.** Pedirle
  a un modelo de 3B parámetros que cuente caracteres añade un modo de fallo —un error de
  aritmética descartaría una cita correcta— y no quita ninguno, porque habría que buscar el
  texto igualmente para validar lo que dijera. La búsqueda **es** el control.
- **No hay una segunda normalización.** Se ancla sobre el mismo texto que usan las reglas
  (`pipeline/texto.texto_plano`, con `VERSION_TEXTO_PLANO`). Dos derivaciones del mismo
  documento son dos sistemas de coordenadas, y entonces un span del clasificador y un offset de
  la extracción no se pueden contrastar entre sí. `pipeline/normalizacion.py` **no existe y no
  hace falta**.
- Los offsets son **absolutos sobre el documento entero**, no relativos a la ventana enviada
  al modelo. Con truncado o ventana deslizante (6.9.7) hay que sumar el desplazamiento de la
  ventana antes de persistir. Test explícito de esto: es el error fácil.
- **Lo que no ancla se descarta, y se descarta la extracción entera** (no el campo): si el
  modelo se ha inventado una redacción, lo demás tampoco merece crédito. Sigue la misma vía que
  un fallo de esquema (6.9.3) — sin fila, la norma vuelve sola a la cola. Es también control
  anti-inyección (6.7). **La única licencia al comparar es colapsar espacios**; una paráfrasis
  no ancla.
- **Lo que se guarda es el recorte del archivo, no la cadena del modelo**, que solo sirve para
  localizar y después se tira. Un **puntero** (ADR 0016) no ancla nada y no invalida nada.
- El frontend enseña el fragmento resaltado sobre el texto archivado, no el texto que devolvió
  el modelo. Lo que ve el revisor humano es la fuente.

### 7.6 Clasificador por diff

Reglas auditables sobre el diff derivan avance/retroceso/neutro/indeterminado + severidad. Dos
umbrales: precisión alta para lo autopublicable, recall alto para lo que va a la cola de
revisión.

**Cada veredicto emite `regla_aplicada` (identificador estable de la regla) más los spans de
evidencia** sobre los que se aplicó. Requisito de auditabilidad, no adorno: una alerta
publicada tiene que poder reconstruirla un tercero leyendo la regla y el texto archivado, sin
ejecutar nuestro código. Las reglas se versionan como el vocabulario.

Ninguna regla puede consultar al modelo ni depender de un campo que venga de su juicio. Si una
regla necesita algo que el extractor no da como hecho objetivo, la regla está mal planteada.

**El catálogo vive en `pipeline/reglas.py` (`VERSION_REGLAS`) y lee el texto archivado, no la
salida del modelo** (ADR 0016). La primera familia escrita es la **supresión**, y es la primera
por una razón que conviene no olvidar: el BOE modificativo publica la redacción *nueva*, no la
vieja, así que hasta el ADR 0018 **el diff de una modificación no se podía construir**: la
supresión y la derogación son los dos únicos cambios que no necesitan texto anterior.

**Ese muro lo tira el ADR 0018**, que trae el texto anterior desde la legislación consolidada del
BOE y puebla `version_norma`. Lo que eso desbloquea es una familia de reglas sobre modificación,
y **no está escrita**: el ADR 0018 establece el hecho (antes decía esto, ahora dice esto otro),
no el veredicto. Escribirla sigue exigiendo lo de siempre — `regla_aplicada`, spans de evidencia
sobre el texto archivado, y nada que dependa del juicio del modelo.

### 7.7 Gate humano

Un validador revisa la cola antes de emitir. Obligatorio, sin flag que lo salte.

**Implementado el 2026-08-14 (ADR 0017).** `services/revision.py` es el **único** sitio del
código que escribe en `alerta`, y solo al aprobar; `security/panel.py` es la puerta única de
autenticación y `api/revision.py` la única parte de la API que escribe. Tres reglas que no son
detalles de implementación:

- **Solo entra en la cola lo que tiene veredicto** (`regla_aplicada IS NOT NULL`). El centinela
  del extractor (ADR 0009) no es un veredicto, y pedirle a una persona que apruebe la ausencia
  de conclusión llena la cola de ruido hasta que deja de mirarse — que es como un gate humano se
  vacía por dentro sin que nadie lo desactive.
- **Un ítem resuelto no se reabre.** Reabrirlo permite emitir dos veces la misma alerta o retirar
  una emitida sin dejar constancia.
- **No se guarda quién revisa** (6.4). Para auditar el gate basta con que se resolvió, cuándo y
  con qué nota; almacenar qué persona aprueba qué alerta sobre derechos trans crea el dato
  sensible que este proyecto se dedica a no crear. Por eso la credencial es una y vive en el
  entorno: **el día que revisen dos personas, esto se rehace con su propio ADR**.

### 7.8 Set de evaluación

`tests/gold_set/` con 150-200 documentos históricos etiquetados a mano (incluir la reforma
madrileña de 2023, reformas rechazadas, y muchos negativos). Sin esto la parte de IA no es
evaluable. **No lo recortes nunca.**

**El formato de caso tiene que cerrarse ANTES de etiquetar en masa**, con:
- `prefiltro_esperado`: uno de los cuatro estados de 7.2.
- `ejes_esperados`: qué ejes deberían disparar. Permite medir el recall **por eje** y saber si
  el eje referencial aporta o duplica.
- Etiquetado sobre el **texto íntegro**, no sobre el título: es lo que decide 7.1.
- `clasificacion_esperada` sigue en `null` a propósito hasta que exista el clasificador.

Etiquetar 200 documentos con el formato viejo y volver a etiquetarlos es el peor uso posible
del recurso más caro del proyecto, que es el tiempo humano de anotación.

---

## 8. Fuera de alcance (guardarraíles)

Si te encuentras haciendo cualquiera de estas, para:

- **OCR** de PDFs escaneados. Agujero negro. Esas fuentes se documentan como hoja de ruta.
- **Monitorización de prensa o redes sociales.** No.
- **Publicación totalmente automática** sin gate humano. No.
- **Almacenar el veredicto del LLM como si fuera la clasificación.** La clasificación se deriva
  del diff.
- **Celery / colas distribuidas / microservicios.** Es un proyecto de 6 semanas. Un worker cron
  idempotente basta.
- Más de 5 fuentes en la primera iteración. Con 5 se demuestra; el resto, documentado.
- **Eje semántico por embeddings** (7.3, eje 3). Depende del gold set y no cabe en el plazo.
  Hueco reservado y documentado; nada de implementarlo "ya que estamos".
- **Fine-tuning, RAG, o cambiar de modelo buscando calidad.** Antes de tocar el modelo hay que
  poder medir, y medir es el gold set. Cualquier cambio de modelo sin gold set es una opinión.
- **Bucle de agente que mergee solo.** Ver 13.3: el driver automatiza el tecleo, no el
  criterio. Ninguna rama entra en `main` sin que la mire el humano.

---

## 9. Git y flujo de trabajo

- **Conventional commits**: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `sec:`.
- **Una rama por feature**, PR aunque trabajes solo (el historial se lee en la evaluación).
  Las tareas ejecutadas por el driver van en `task/NN-nombre` (sección 13.3).
- **ADRs** en `docs/adr/NNNN-titulo.md`. Formato: contexto, decisión, alternativas, consecuencias.
  Primeros ADRs esperados: 0001 arquitectura conocimiento-cero de suscriptores, 0002 el LLM
  extrae no juzga, 0003 gate humano obligatorio, 0004 no persistir veredicto del LLM,
  0005 archivo con sellado de tiempo.
  ADRs nuevos que exige esta revisión: ~~0010 canal pull primero~~ (6.4) — **escrito e
  implementado el 2026-08-14**, ~~0011 ingesta en dos
  fases con umbral asimétrico~~ (7.1) — **escrito el 2026-08-07**, con el título ajustado a lo
  que la medición decidió: `0011-ingesta-en-dos-fases-y-umbral-de-la-fase-2.md`,
  **0012 prefiltro de tres ejes y watchlist** (7.3), ~~**0013 trazabilidad por offsets**~~ (7.5)
  — **escrito e implementado el 2026-08-16**.
  Añadidos después: 0014 la capa local entra en alcance vía BOP, **0015 dónde vive el texto
  íntegro archivado** (tarea 0.c, escrito el 2026-08-09), **0016 cómo se representa una
  supresión sin texto** (escrito e implementado el 2026-08-09) y **0017 autenticación del panel
  de revisión** (escrito e implementado el 2026-08-14) y **0018 de dónde sale el texto anterior**
  (escrito e implementado el 2026-08-15). Con el 0013 escrito **ya no queda ningún número
  reservado**: el siguiente libre es el **0019**.
- Mantén `SECURITY.md` y `THREAT-MODEL.md` vivos, no como trámite final. Esta revisión añade
  entradas al modelo de amenazas: volumen de peticiones en fase 2 (6.2), `<analisis>` como
  entrada hostil (6.7) y salida del modelo como vector de acción (6.10).
- Mensajes de commit en español está bien; el código y los identificadores en inglés.

---

## 10. Comandos

```bash
# Levantar todo: base de datos, backend, worker y la web (desde 2026-08-17 el frontend también
# es un servicio del compose, con `restart: unless-stopped`). La web queda en el 5174 del host.
docker compose up --build

# Backend en local
cd backend && uvicorn app.main:app --reload

# Migraciones
alembic revision --autogenerate -m "..."   &&   alembic upgrade head
# y DESPUÉS de cada upgrade, comprobar que siguen vivas las CHECK (hoy 13). El filtro honesto
# lleva `conrelid <> 0`: sin él salen dos filas de information_schema que no son del proyecto.
psql -c "SELECT conrelid::regclass, conname FROM pg_constraint
         WHERE contype='c' AND conrelid <> 0 ORDER BY 1,2"

# Calidad (lo que corre el CI)
ruff check . && ruff format --check . && mypy backend/app && pytest --cov

# Ingesta manual (una fecha concreta)
python -m worker.run --fuente boe --fecha 2024-12-19

# Backfill: un rango de días, sin llamar al LLM. Es lo que hace viable traer meses de boletín
# (una extracción cuesta 133,9 s, ADR 0011). Lo que se salta NO se pierde: la cola del extractor
# es una consulta, así que una pasada normal posterior lo recoge.
python -m worker.run --fuente boe --fecha 2024-11-15 --hasta 2024-12-16 --sin-extraccion

# Reevaluar prefiltro tras subir VERSION_VOCABULARIO o VERSION_WATCHLIST
python -m worker.run --reprefiltrar

# Drenar la cola de la fase 2 (texto íntegro que falte de toda la tabla)
python -m worker.run --fase2

# Reintentar el versionado: texto consolidado de lo que se modifica (ADR 0018). Sale a la red.
# El BOE consolida con retraso, así que lo normal es que hoy complete cambios de días atrás.
python -m worker.run --versionar

# Drenar la cola del extractor (lo que deja pendiente un backfill --sin-extraccion).
# 133,9 s por norma: se lanza y se deja. Interrumpirlo no pierde nada.
python -m worker.run --extraer

# Repasar el catálogo de reglas tras subir VERSION_REGLAS (ni red ni LLM)
python -m worker.run --reclasificar

# Ollama (local, sin clave, sin coste)
ollama serve                        # normalmente ya corre como servicio
ollama list                         # modelos disponibles
ollama show qwen2.5:3b-instruct     # digest del modelo, que va en extraccion_json
curl -s localhost:11434/api/tags    # comprobación rápida de que responde

# Frontend: normalmente NO hace falta, lo levanta el compose en http://localhost:5174.
# Esto es solo para trabajar sin docker; entonces el proxy apunta al 8000 del host por defecto.
cd frontend && npm run dev -- --host 127.0.0.1

# Driver de sesiones (sección 13.3)
./run_agent.sh 1                    # una tarea del backlog; empezar por 1 para calibrar
```

---

## 11. Estado actual del proyecto → **[`ESTADO.md`](ESTADO.md)**

El estado vive en un fichero aparte desde el 2026-08-09. **No es una reorganización estética**:
este fichero entra entero en el contexto de cada subagente, y el historial de estado era el
54 % de sus 124 KB. Sacarlo baja el coste de arrancar un agente de ~31.000 a ~14.000 tokens.

- **Al retomar el proyecto**, `ESTADO.md` es lo primero que hay que leer: qué se hizo, qué toca
  y cuánto contexto cuesta cada tarea pendiente.
- **Al cerrar un trabajo**, se actualiza `ESTADO.md`, no este fichero. Aquí solo se toca lo que
  cambia de verdad las reglas: el modelo de dominio, los requisitos de seguridad, el pipeline.
- **Las referencias a "sección 11" repartidas por el repositorio siguen siendo válidas**: la
  sección conserva su número, solo cambia de fichero.

Este fichero es **las reglas**. `ESTADO.md` es **dónde estamos**. Mezclarlos fue lo que lo hizo
crecer hasta ser caro de leer para todo el mundo, personas incluidas.

---

## 12. Backlog de mejoras (pedido por el humano, para S1)

> Pedido tal cual al cierre de S0. No reordenar por criterio propio sin comentarlo primero;
> si al empezar S1 alguno de estos puntos ya no aplica o contradice algo de este archivo,
> **para y pregunta** antes de tocarlo.

### Contenido

- Texto reivindicativo al principio (pantalla Mapa/home): explicar el objetivo del proyecto,
  a quién protege y por qué existe, antes de que el usuario llegue al mapa. Contenido, no
  solo maquetación — pensar el mensaje con calma, no rellenar con genérico.

### Mapa

- Canarias no se renderiza bien (posición/escala rotas en el recuadro inferior izquierdo).
  Revisar el offset manual que trae `MapaCCAA`/`_design-export/data/ccaa-paths.json`.
- Hacer el mapa ampliable (zoom), para poder bajar de CCAA a provincia y localidad.
- Añadir división por provincias y localidades, no solo CCAA (implica geometría nueva, no
  solo la que ya tenemos — no inventar límites, buscar fuente oficial equivalente al IGN).
- Faltan las ciudades autónomas (Ceuta y Melilla) en el mapa actual — ni geometría ni datos
  mock las incluyen hoy.

### Datos / navegación

- El enlace a "Texto íntegro" / fuente oficial en la Ficha de norma no lleva al documento
  real todavía (hoy es un ancla muerta `#fuente`; no hay backend detrás). Puede quedar como
  TODO explícito hasta que exista almacenamiento real, pero no debería parecer un enlace
  funcional si no lo es.

### Difusión (acciones externas — confirmar con el humano antes de ejecutar cada una, no encadenarlas)

- Subir el repositorio a GitHub (público) y valorar promocionarlo en LinkedIn. Publicar en
  redes es una acción visible e irreversible: proponer el texto, no publicarlo sin
  aprobación explícita en el momento.
- Investigar opciones para desplegar una versión pública en la web (hosting del frontend
  y, más adelante, del backend).
- Contactar con asociaciones LGTBI+/trans para dar a conocer el proyecto — carácter
  totalmente altruista, sin monetización. Esto es contacto con terceros reales: preparar
  materiales/mensaje con el humano, no enviar nada en su nombre sin que lo revise antes.

---

## 13. Cómo se ejecuta el trabajo con Claude Code

Sección operativa. No cambia el diseño del producto; cambia cómo se gasta el recurso escaso,
que aquí no es el dinero (todo es coste 0 €) sino la **cuota de la suscripción y el tiempo
humano de revisión**.

### 13.1 Límites de uso, en corto

La suscripción tiene dos límites solapados: una ventana móvil de 5 horas y **un tope
semanal**, y la cuota es compartida con el chat web. El tope semanal es el límite real: una
sesión larga con mucho contexto arrastrado se lo come rápido.

Consecuencias prácticas, y son reglas:
- **Una tarea = una sesión limpia.** Nada de arrastrar contexto entre tareas distintas. El
  estado del proyecto vive en la sección 11 de este archivo, no en la conversación.
- **`/clear` al cambiar de tarea.** Cambiar de modelo a mitad de una conversación larga es
  caro (se pierde la caché de prompt); si hay que cambiar, se cambia al empezar.
- Trabajo rutinario contra un criterio de aceptación claro: modelo rápido. Diseño, ADRs y
  decisiones de seguridad: el modelo bueno.
- `/usage` para ver el consumo antes de arrancar algo grande.
- Las estimaciones de contexto de la sección 11 sirven justamente para decidir si una tarea
  cabe en la sesión que empieza.

### 13.2 Backlog de tareas (`tasks/backlog/`)

Un fichero por tarea, `NN-nombre-corto.md`, ordenados por dependencia. Cada tarea debe ser
**autosuficiente**: se le pasa a una sesión nueva que solo tiene este CLAUDE.md como contexto.
Contenido mínimo:

- Objetivo en una frase.
- Ficheros exactos que se van a tocar.
- Criterio de aceptación **verificable con `pytest`** (más la verificación real que
  corresponda: `psql`, `curl`, navegador — en este repo eso ha encontrado fallos que ningún
  test veía).
- Restricciones de este archivo que la tarea no puede violar (citar sección).
- Coste estimado de contexto.

Al terminar una tarea: actualizar la sección 11, mover el fichero a `tasks/done/`.

### 13.3 Driver de sesiones (`run_agent.sh`)

Ejecuta tareas del backlog en modo headless, una sesión limpia por tarea. **Automatiza el
tecleo, no el criterio**: cada tarea va a su rama y el merge lo hace el humano tras mirar el
diff. Es el mismo principio que el gate humano del producto (regla 4) aplicado al código.

```bash
#!/usr/bin/env bash
# run_agent.sh — ejecuta N tareas del backlog, una sesión limpia por tarea
set -uo pipefail
MAX=${1:-1}
mkdir -p tasks/done tasks/log

for _ in $(seq 1 "$MAX"); do
  TAREA=$(ls -1 tasks/backlog/*.md 2>/dev/null | head -n1)
  [ -z "$TAREA" ] && { echo "Backlog vacío."; exit 0; }
  ID=$(basename "$TAREA" .md)
  echo "▶ $ID"

  git checkout -B "task/$ID" >/dev/null 2>&1

  claude -p "$(cat "$TAREA")" \
    --model sonnet \
    --permission-mode acceptEdits \
    --allowedTools "Read,Write,Edit,Grep,Glob,Bash(pytest:*),Bash(ruff:*),Bash(mypy:*),Bash(git:*)" \
    --output-format stream-json --verbose \
    > "tasks/log/$ID.jsonl" 2> "tasks/log/$ID.err"
  RC=$?

  if grep -qiE "usage limit|rate.?limit" "tasks/log/$ID.err" "tasks/log/$ID.jsonl"; then
    echo "⏸ Límite de uso alcanzado en $ID. Reanuda cuando reinicie la ventana."; exit 2
  fi
  [ $RC -ne 0 ] && { echo "✗ Error en $ID (rc=$RC)"; exit 1; }

  if pytest -q && ruff check . && mypy backend/app; then
    git add -A && git commit -qm "$ID"
    mv "$TAREA" tasks/done/
    echo "✓ $ID — revisa el diff de task/$ID antes de mergear"
  else
    echo "✗ Calidad en rojo tras $ID. Rama task/$ID para revisión manual."; exit 1
  fi
done
```

Reglas del driver, no negociables:
- **Nunca `--dangerously-skip-permissions`.** La allowlist de herramientas es la que hay
  arriba: escribir código y correr las comprobaciones del CI, nada más.
- **Nunca `alembic upgrade` desatendido.** El aviso del autogenerate (sección 11) ha aparecido
  cuatro veces y una de ellas habría desarmado un control del proyecto. Las migraciones las
  revisa una persona, siempre.
- **Parada al primer rojo.** Un agente que sigue sobre tests rotos genera deuda más rápido de
  lo que se revisa.
- Ninguna acción de la sección 12 "Difusión" entra jamás en el backlog automático.
- `tasks/log/` en `.gitignore`.

### 13.4 Subagentes (`.claude/agents/`)

Ficheros Markdown con frontmatter, ámbito de proyecto. Contexto propio: la lectura pesada no
contamina la sesión principal. **Se cargan al arrancar**: si se crea uno con la sesión
abierta, hay que reiniciarla.

- **`revisor-seguridad`** — audita un diff buscando: fugas de datos de suscriptores, IPs o
  identificadores en logs, superficies de inyección nuevas, HTTP fuera de `url_guard`, XML
  fuera de `xml_safe`, llamadas al LLM fuera de `llm/`, y cualquier camino que salte el gate
  humano. `Read, Grep, Glob` más **`Bash` acotado a lectura del historial** (`git diff`, `log`,
  `show`, `status`): sin eso auditaba el árbol y no el diff, y un import **nuevo** —el hallazgo
  que su propio fichero llama el más importante— es indistinguible de uno de siempre.
- **`auditor-reglas`** — comprueba que el clasificador siga siendo determinista y auditable:
  que ninguna regla dependa de la salida valorativa del modelo, que cada veredicto emita
  `regla_aplicada` y spans, y que el esquema de extracción no haya ganado campos de juicio.
  `Read, Grep, Glob` más **`Bash` solo de verificación**: `git diff` sobre `alembic/` y el
  `SELECT ... FROM pg_constraint` de la sección 10. Leer la cadena de migraciones prueba que
  ninguna borra la CHECK; no prueba que la CHECK esté en la base de datos.
- **`evaluador`** — corre el gold set y reporta recall **desglosado por eje** (7.3),
  enumerando los falsos negativos uno a uno. Un número agregado no sirve: lo que importa es
  qué se escapó y por qué eje debería haber entrado.
- **`jurista-lgtbi`** — analiza normas de los tres niveles (estatal, autonómico,
  provincial/local) desde el derecho antidiscriminatorio. Produce **reglas candidatas para el
  clasificador (7.6)** en el formato que 7.6 necesita, e informes de apoyo al etiquetado y al
  gate humano. Aporta el conocimiento de dominio que no estaba escrito en ningún sitio: los
  instrumentos por nivel (con las **bases de subvención** como vector local), diez vectores de
  retroceso ordenados por lo silenciosos que son, y la lista de **lo que parece cambio y no lo
  es** — que es de donde saldrían los falsos positivos del clasificador.

  **Sí señala "posible retroceso, a verificar"; no emite veredictos.** La diferencia no es de
  grado, es de naturaleza: una hipótesis va dirigida a una persona y **muere cuando esa persona
  decide**; un veredicto se persiste, se publica y hay que poder defenderlo ante un tercero sin
  ejecutar nuestro código. El proyecto ya tenía ese concepto en dos sitios —el estado
  `sospecha` (7.2) y el umbral de recall alto de 7.6—, así que señalar para que alguien mire
  encaja; lo que no cabe es que eso llegue a `deteccion` o a la API, y la CHECK
  `origenclasificacion` lo hace cumplir.

  **El riesgo que se diseñó en contra es el anclaje.** Si quien revisa lee "posible retroceso"
  antes que el artículo, ya no lo juzga: lo confirma, y el gate humano (regla 4) se vacía. Por
  eso el orden del informe es fijo —**texto citado → pregunta → hipótesis → qué la refutaría**—
  y el último punto es obligatorio siempre. Eso convierte la señal de ancla en lista de
  comprobación. También tiene prohibido etiquetar el gold set: si lo etiquetara él, el sistema
  se mediría contra sí mismo.

Ninguno de los cuatro escribe código. Su salida es un informe para la sesión principal o para
el humano.

**Estado: los cuatro creados el 2026-08-08 y ejecutados por primera vez el 2026-08-09.** Hasta
esa fecha eran especificación sin probar. Lo que dio la ejecución está en la sección 11.

**Ojo con dos cosas que costaron una tanda entera de cuota:**

1. **Los subagentes se cargan al arrancar y son de ámbito de proyecto.** Si la sesión se abre
   fuera del repositorio, `subagent_type: auditor-reglas` devuelve *not found* y los cuatro son
   inalcanzables. Abrir la sesión **en la raíz del repositorio**, siempre.
2. **Gastan cuota muy rápido.** Los cuatro en paralelo agotaron el límite de sesión a mitad de
   trabajo y hubo que retomarlos. Regla: lanzarlos **de uno en uno**, con un presupuesto de
   llamadas dicho en el encargo, y no arrancar ninguno por encima del 60 % de consumo. Se
   retoman por su identificador conservando el contexto, así que un corte no obliga a repetir
   desde cero — pero lo barato es no provocarlo.