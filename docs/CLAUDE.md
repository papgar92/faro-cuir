# CLAUDE.md — Faro Cuir

> Instrucciones persistentes para Claude Code. Léete este archivo entero al inicio de cada
> sesión. Si vas a tomar una decisión que contradiga algo de aquí, **para y pregúntame**.
>
> **Aquí están las reglas; en [`ESTADO.md`](ESTADO.md) está dónde estamos** (la sección 11:
> qué se hizo, qué toca, y cuánto contexto cuesta cada tarea pendiente). Al empezar, lee los
> dos; al cerrar un trabajo, actualiza `ESTADO.md`.
>
> **Mantén este fichero por debajo de ~55 KB.** No es estética: entra entero en el contexto de
> **cada subagente**, así que es el coste fijo de arrancar cualquier trabajo.
>
> Se ha desbordado dos veces y las dos se arregló igual: **sacando un bloque entero que el otro
> lado no necesita**, no recortando frases. La 11 se fue a [`ESTADO.md`](ESTADO.md) y la 13 a
> [`TRABAJO.md`](TRABAJO.md); las dos conservan su número.
>
> **Antes de recortar, mide.** Podar narrativa de las secciones 6 y 7 dio ~800 bytes: son reglas,
> no historial, y ahí un recorte a ojo se lleva un guardarraíl por delante.

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
  trabajo, qué verificar y cómo. No propongas un plan y esperes el OK salvo que el trabajo sea
  grande o cambie el rumbo; para lo demás, hazlo y cuéntalo al terminar.
- **Elige siempre la opción de coste 0 €** y la que exija menos cosas que conseguir (claves,
  cuentas, servicios de terceros). Si ahorra una clave de API a cambio de algo de calidad, ahorra
  la clave (ADR 0008).
- **Para y pregunta solo en cuatro casos:** cuesta dinero; hace falta una credencial o cuenta que
  no existe; es una acción externa e irreversible (sección 12); o contradice algo de este archivo.
- Cuando decidas algo no obvio, **déjalo escrito** (ADR si es arquitectura, comentario si es
  local) y avisa al terminar. Autonomía no es silencio: es no interrumpir.
- Si te falta un dato, **mira antes de preguntar** (el repo, la máquina, la API real). Preguntar
  algo que podías comprobar cuesta más que comprobarlo.

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

**61 fuentes en total.** La capa local se vigila por el BOP y no municipio a municipio porque una
ordenanza municipal **no entra en vigor si no se publica íntegra en el BOP** (Ley 5/2002,
`BOE-A-2002-6467`): el municipio no es una fuente, es un emisor que publica en la provincial. Eso
convierte 8.131 municipios en 43 boletines. Ver `docs/fuentes.md`.

**Registradas ≠ vigiladas:** el guardarraíl de la sección 8 (máximo 5 fuentes integradas en la
primera iteración) sigue en pie y con 61 fuentes importa más, no menos.

Detecta el **retroceso silencioso**: no la reforma que sale en prensa, sino la instrucción de
rango bajo publicada un martes de agosto que desmonta un derecho sin titulares.

Es la **práctica final de un máster de Ciberseguridad e IA**. **Entrega: 2026-10-01**; versión
«pro» pedida para el **2026-09-20**. Por tanto:

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

Sin dependencias nuevas para la watchlist ni para el driver de sesiones. Coste 0 € y una cosa
menos que auditar.

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

`config/vocabulario.yaml` es una migración pendiente y **no urgente** del diccionario que hoy vive
en `pipeline/prefiltro.py`. `VERSION_VOCABULARIO` manda en cualquier caso.

---

## 5. Modelo de dominio

Entidades núcleo (nombres reales de tabla en snake_case):

- **fuente** — un origen de datos. Campos: `id`, `nombre`, `tipo` (`boe`|`boletin_autonomico`|
  `parlamento`), `ccaa`, `formato` (`api`|`rss`|`html`|`pdf`), `url_base`, `licencia_reutil`,
  `activa`.
- **documento** — un documento crudo ingerido. `id`, `fuente_id`, `identificador_oficial`,
  `fecha_publicacion`, `url_original`, `sha256`, `sello_tiempo`, `ruta_almacen`, `estado_pipeline`,
  **`tipo`** (`sumario`|`texto_norma`|`consolidado`). El `sha256` + `sello_tiempo` forman el
  **archivo íntegro verificable** (ver sección 6.5). **Tres clases de fila**: el sumario del día, el cuerpo de cada norma (ADR 0015) y el **texto
  consolidado** de una norma vigilada (ADR 0018), de donde sale el texto anterior de un artículo
  modificado. La garantía de 6.5 se implementa aquí una sola vez, y por eso ninguna tiene tabla
  propia; `tipo` es columna y no convención porque `GET /api/documentos` tiene que filtrarla.
  **`consolidado` no es un `texto_norma` más** (ADR 0018): `texto_norma` es lo que la fuente
  publicó aquel día —el hecho que este archivo conserva— y `consolidado` es una elaboración
  posterior que cambia cada vez que alguien modifica la norma. Confundirlos haría que el archivo
  dejara de poder afirmar «el día X esto decía exactamente esto».
- **norma** — un ítem normativo identificado dentro de un documento. `id`, `documento_id`,
  **`documento_texto_id`** (dónde está archivado su cuerpo; NULL = cola de la fase 2),
  `titulo`, `rango` (ley|decreto|orden|instruccion|resolucion|proposicion), `organo_emisor`,
  `ambito` (sanitario|educativo|laboral|documental|general|...).
  Más las columnas del prefiltro: `prefiltro_estado`, `prefiltro_terminos`,
  `prefiltro_version`, `prefiltro_evaluado_en`. **`prefiltro_estado` tiene cinco valores**
  (ver 7.2): `pendiente` | `sospecha` | `relevante` | `descartada` | `ilegible`.
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

Regla de versionado: **nunca se sobrescribe una versión de norma**. El histórico es inmutable, y
esa inmutabilidad es parte del valor: es el archivo de lo que realmente se publicó.

---

## 6. Requisitos de seguridad (esto es lo que puntúa)

Estás ingiriendo XML, HTML y PDF de fuentes externas que no controlas. Esa es la superficie de
ataque principal. Trátalo así.

**Hoy son cuatro integradas de las 61 registradas** —BOE, DOGC, BOA y BOCYL (ADR 0019, 0028 y
0029)—, y cada una ha traído su propia forma de romper: el DOGC mete el articulado dentro de un
atributo XML, el BOA sirve su portada los días sin boletín y el BOCYL obliga a raspar HTML. **El
número de fuentes importa menos que el hecho de que ninguna se comporta como la anterior.**

### 6.1 Parseo de contenido no confiable
- **XXE:** `defusedxml` siempre. Prohibido `xml.etree` o `lxml` sin endurecer. Entidades
  externas OFF, resolución de red OFF, DTD OFF. Test que lo demuestre con un payload XXE.
- **Bombas XML / billion laughs:** límites de profundidad de anidamiento y de expansión de
  entidades. Test con payload.
- **Zip bombs:** si algún día se descomprime algo, límite de ratio y de tamaño total.
- **PDF:** extracción de la capa de texto. **El OCR deja de estar prohibido** (decisión del
  humano, 2026-08-22) pero sigue siendo **el último recurso, nunca el primero**: se intenta la
  capa de texto y solo si el PDF no la tiene se plantea OCR, con su propio ADR. Medido antes de
  cambiar la regla: un PDF del DOGC trae 59 referencias de fuente, 18 bloques de texto y **cero
  imágenes**, así que para esta fuente el OCR no hace falta. Límite de tamaño y de páginas,
  siempre: un PDF es entrada hostil como cualquier otra.

### 6.2 SSRF en la ingesta
El worker sigue URLs que vienen de los sumarios. Si no se validan, se convierte en tu proxy a la
red interna. `security/url_guard.py`: allowlist de dominios oficiales, rechazo de IPs privadas/
loopback/link-local, sin redirecciones a hosts fuera de la allowlist, timeouts y límite de bytes.

**La fase 2 (7.1) multiplica el número de URLs seguidas por día.** No es una excepción a nada:
toda URL de fase 2 pasa por `url_guard` igual que las de fase 1, y la única fuente legítima de
una URL sigue siendo el sumario oficial parseado. Añadir un límite de peticiones por ejecución
y una pausa entre descargas — cortesía con la fuente y freno propio si un sumario manipulado
declara miles de items.

**Solo hay dos excepciones declaradas a esta allowlist**, y por el mismo motivo: el destino sale
de la configuración, no de un documento. Son Ollama (6.9.2) y el almacén de objetos donde vive el
archivo (ADR 0032). Las dos se validan al arrancar. Una tercera necesita su ADR.

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

**Canal pull primero (ADR 0010).** El canal principal de difusión es *pull*: web pública + feed
Atom en `GET /api/alertas.xml`. Quien quiera enterarse se suscribe con su lector y el sistema **no
sabe quién es**. Sin lista, sin fichero, sin brecha posible. El correo y los webhooks quedan como
vías **secundarias y opcionales**, con doble opt-in y todo lo anterior.

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

Ya implementado: marcas largas de delimitación, eliminación de esas marcas si el propio documento
las contiene, y un test que **simula que la inyección funciona** y comprueba que la salida se
descarta igual. Esa es la defensa que cuenta.

- El bloque `<analisis>` del BOE es **entrada igual de hostil** que el articulado. El eje
  referencial (7.3) lo parsea; los identificadores que saque se validan contra formato conocido
  antes de compararse con la watchlist, y nunca se usan para construir una URL (6.10).
- Los offsets (7.5) son también control anti-inyección: una respuesta que afirme un texto que no
  está en el rango que ella misma declara se descarta sola. Una inyección que haga inventar
  contenido tiene además que acertar sus coordenadas en un texto que no controla.

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
2. **La URL de Ollama es la primera de las dos excepciones a la allowlist de `url_guard`** (6.2):
   destino local y fijo de configuración, no una URL que venga de una fuente. Se valida al
   arrancar (host, esquema y puerto esperados) y nunca se compone con nada dinámico. En docker,
   `host.docker.internal` vía `extra_hosts`; fuera, `127.0.0.1`.
3. **Salida estructurada siempre.** El adaptador pasa el esquema JSON derivado del modelo
   Pydantic (`Extraccion.model_json_schema()`) en el campo `format`, cuando el backend lo soporta.
   **Es una ayuda, no el control**: el control sigue siendo la validación Pydantic con
   `extra="forbid"`. Si falla se descarta, con **un solo reintento**, y a la vía de fallo normal
   (sin fila → la norma vuelve sola a la cola). Nunca parseo de texto suelto, nunca «interpretar»
   una respuesta inválida, nunca reintento libre en bucle.
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
6. **Degradación ruidosa.** Si Ollama no responde no hay respaldo heurístico ni «seguimos con lo
   que se pueda»: el worker marca el trabajo como no procesado, lo dice en el log y sale con
   código distinto de cero. Un sistema de vigilancia que falla en silencio es peor que uno que no
   existe, porque genera confianza infundada.
7. **Presupuesto de contexto, MEDIDO el 2026-08-28 y peor de lo que se temía.**
   `MAX_CARACTERES_DOCUMENTO` (hoy 4.000) es rendimiento del modelo pequeño en CPU, no calidad.
   Sobre 150 normas de la cola: **2 caben enteras (1 %)**, mediana 82.309 caracteres, y de las ya
   enviadas el modelo vio el **2,6 %**. Por eso `extraccion_json` registra `caracteres_enviados` y
   `caracteres_documento`: sin ellos, «el extractor no encontró nada aquí» no se distingue de «no
   lo miró», y sobre esta cola es lo segundo el 99 % de las veces.
   **La ventana deslizante es la solución correcta y NO se implementa**: la extracción no alimenta
   el gate humano —lo hace el catálogo de reglas leyendo el texto completo (ADR 0016)—, así que
   multiplicar por ~38 el coste de CPU no desbloquearía ni una alerta. Si algún día se hace, los
   offsets de 7.5 se rebasan a la posición absoluta.
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
  modelo: si fue manipulado para emitir un veredicto, ese texto no puede quedar en un log donde
  alguien lo lea como conclusión del sistema.

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

El sumario diario trae título, emisor y metadatos. **El título es exactamente lo que un retroceso
silencioso puede redactar de forma anodina**, así que decidir sobre el título es decidir sobre lo
que el redactor controla. De ahí la regla:

- **Fase 1 (barata):** sumario XML del día. Se evalúan todos los items.
- **Fase 2:** descarga del texto íntegro **de todos los items del día, sin umbral**.
- **El descarte definitivo solo ocurre después de leer el documento completo.** Nunca sobre el
  título.

Un falso positivo en fase 1 cuesta una petición HTTP. Un falso negativo es invisible, no aparece
en ninguna métrica y es el fallo total del sistema. La asimetría es deliberada.

**MEDIDO Y DECIDIDO (ADR 0011).** El umbral de la fase 2 **es cero**: se descarga el día
entero, porque un día de BOE cuesta ~4,3 MB y ~10 s de red y la información no está en el
título. **Lo caro es el LLM: 133,9 s por extracción**, o sea ~16 h de CPU por día completo. Por
eso **el prefiltro deja de ser la puerta de la red y pasa a ser la puerta del LLM**, evaluándose
sobre el texto íntegro; sobre el título solo prioriza la cola, nunca descarta. El `sha256` hace
idempotente la descarga. Números y método en el ADR 0011 y `scripts/medir_fase2.py`.

### 7.2 Estados del prefiltro

`prefiltro_estado` tiene **cinco** valores. Cada uno costó su migración y su **ADR**:

| Estado | Significado | Consecuencia |
|---|---|---|
| `pendiente` | aún no evaluada, o sin cuerpo archivado todavía | — |
| `sospecha` | indicio débil **sobre el texto íntegro ya descargado** | cola del extractor con prioridad baja; nunca se descarta sin revisar |
| `relevante` | indicio fuerte sobre el texto íntegro | cola del extractor con prioridad alta |
| `descartada` | descartada **tras** ver el texto completo | fin |
| `ilegible` | hay cuerpo archivado y **el pipeline no puede parsearlo** (ADR 0020) | fuera de todas las colas automáticas; trabajo para una persona |

**Ojo, esto cambió con el ADR 0011 y es fácil leerlo mal:** ningún estado del prefiltro decide ya
qué se descarga —se descarga todo— sino qué entra en el LLM y en qué orden. `sospecha` no es
«descárgalo para mirar», es «ya está descargado y mirado, y merece un puesto en la cola».

`pendiente` ≠ `descartada` es regla. Se guarda además **qué eje disparó** cada evaluación, no solo
los términos: sin eso no se puede afinar un eje sin tocar los otros.

**`ilegible` es el único estado que no habla de la norma sino de nosotros** (ADR 0020), y sus
tres reglas no son detalles de implementación:

- **Manda por encima de cualquier señal del título.** Un cuerpo ilegible apaga los **dos** ejes:
  el léxico queda reducido al título —que 7.1 dice que no sirve para decidir— y el referencial
  desaparece, porque el `<analisis>` vive dentro del documento que no se pudo parsear.
- **No es un descarte ni fin de trayecto.** Se reintenta en cada pasada (`prefiltro_version_texto`
  se deja a NULL a propósito): es lo único que recupera la norma sola si su cuerpo pasa a ser
  legible. Se conservan los términos del título, que son la pista para priorizar el rescate a mano.
- **El embudo lo cuenta aparte y no se omite aunque sea cero.** Cualquier cifra de cobertura de
  una fuente va acompañada de cuántas de sus normas son ilegibles, o afirma una vigilancia que no
  existe. Mezclado con `pendiente`, el 65 % del DOGC se leyó dos días como «esperando su texto».

**Que exista este estado no autoriza a relajar `xml_safe`** (6.1): en el caso que lo motivó, ese
control es lo único que impidió que 172 páginas de error entraran como si fueran normas.

**Aviso de migración (ha pasado cinco veces):** al tocar una CHECK, el autogenerate de alembic
propone borrar CHECKs ajenas. Revisar SIEMPRE antes de aplicar y comprobar después con el
`SELECT ... FROM pg_constraint` de la sección 10.

### 7.3 Prefiltro de tres ejes (OR, no AND)

Un item pasa si dispara **cualquier** eje. No se combinan con AND jamás: eso convierte dos
filtros de alto recall en uno de bajo recall.

**Eje 1 — léxico (existe, `pipeline/prefiltro.py`).** ~90 términos con variantes morfológicas
y clínicas antiguas, límites de palabra, categorías `DIRECTO`/`CONTEXTO` que no cambian la
decisión. No se toca su lógica; solo se le añade el estado `sospecha` para términos débiles.

**Dos decisiones distintas gobiernan este eje sobre texto íntegro, y confundirlas es fácil:**

1. **Al menos un término `DIRECTO`, o no se entra en la cola** (ADR 0021). Los de `CONTEXTO` por
   sí solos ya no bastan **sobre el texto íntegro**; sobre el título siguen bastando. Sin esto, el
   71 % de la cola entraba por «igualdad de trato», «plan de igualdad» o «registro civil» —
   fórmulas de cualquier documento administrativo largo. Es la única regla del eje que **produce
   descartes**, así que el ADR 0021 lleva el recuento de lo que se pierde.
2. **`UMBRAL_DIRECTOS_RELEVANTE` separa `relevante` de `sospecha` y NO decide ningún descarte.**
   Sigue **sin validar** y el gold set actual no da para validarlo: no publiques ese umbral como
   si estuviera comprobado.

**Antes de tocar este eje, mira los dos casos del gold set que lo sujetan por los dos lados**:
`dogc-24310119` es un falso positivo de 105.000 caracteres cuya única coincidencia es «plan de
igualdad» en un temario, y `dogc-24198092` entra por **un solo término directo** con señal buena.
Cualquier cambio que recupere el primero o pierda el segundo está mal.

**Eje 2 — referencial. Dos fuentes de evidencia desde el ADR 0022:** el bloque `<analisis>` del
BOE **y las citas dentro del texto** (`pipeline/citas.py`). La segunda existe porque la primera no
vale fuera del BOE — esa fuente no publica en ningún metadato a quién afecta la norma, solo en el
texto. Reglas que **no** se relajan: solo la forma larga de la cita (número **y** fecha; la corta
produjo 4 falsos positivos de 4), el verbo se busca 200 caracteres hacia atrás, y sin verbo la
referencia es `CITA`, que no dispara nada. **Y el verbo tiene que *gobernar* la cita, no solo caer
cerca** (ADR 0031): no cuenta si en medio empieza la redacción nueva, si hay otra norma que lo
reclame antes, si se cierra una frase, si la cita es el término de una referencia («a que se
refiere») o si la forma casó dentro de otra palabra («se modific**aron**»). **La ventana no se
recorta**: está medido que con 60 caracteres sale el mismo total y se pierden modificaciones
reales.

`config/watchlist.json` lleva las normas objetivo por identificador. **Cualquier disposición que
modifique una norma de la watchlist pasa el filtro por definición, diga lo que diga su texto.**
Este eje cubre el agujero estructural del diccionario: una instrucción que elimina un derecho no
dice «identidad de género», dice «se modifica el epígrafe 4.3 del anexo II».

**No dice solo «menciona esta norma»: trae el verbo** (`MODIFICA`, `DEROGA`, `AÑADE`,
`SUSTITUYE`) y qué artículos toca. `posteriores` son las que modificaron a esta *después*, así que
no sirven para decidir en el día. **La estructura exacta del bloque está verificada en el ADR
0011 (decisión 5); no la deduzcas otra vez.** El sumario de fase 1 no lo trae, así que este eje
es por construcción de fase 2— con el ADR 0011 eso deja de importar porque se descarga todo.

**Su alcance está medido y es limitado (ADR 0027):** solo el 7 % de las disposiciones modifican
algo, y ampliar la watchlist rinde ~5 casos al año. El sistema ve el retroceso que **deja rastro
referencial**; los mecanismos silenciosos —no convocar, dejar caducar, vaciar por ausencia— no lo
dejan por definición. No prometas más cobertura que esa.

`VERSION_WATCHLIST` con la misma mecánica que `VERSION_VOCABULARIO`: subirla obliga a reevaluar
lo anterior (`worker.run --reprefiltrar`).

**Eje 3 — semántico (hueco reservado, NO implementar ahora).** Similitud por embeddings locales
contra corpus etiquetado, para capturar perífrasis que esquiven diccionario y watchlist. Depende
del gold set y no cabe en el plazo (sección 8): interfaz preparada y hoja de ruta.

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

Las reglas, y el porqué de cada una está en el ADR 0013:

- **Los offsets los calcula el sistema (`pipeline/anclaje.py`), no los pide al modelo.** La
  búsqueda **es** el control: habría que buscar el texto igualmente para validar lo que dijera.
- **No hay una segunda normalización.** Se ancla sobre el mismo texto que usan las reglas
  (`pipeline/texto.texto_plano`, con `VERSION_TEXTO_PLANO`): dos derivaciones del mismo documento
  son dos sistemas de coordenadas, y un span del clasificador dejaría de poder contrastarse con un
  offset de la extracción. `pipeline/normalizacion.py` **no existe y no hace falta**.
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
salida del modelo** (ADR 0016). Por qué la supresión fue la primera familia y qué desbloqueó el
texto consolidado está en el docstring de ese módulo y en los ADR 0016 y 0018. La regla que queda
aquí: **R-MOD-001 no afirma signo** — establece el hecho, no el veredicto.

**R-SUP-001 tampoco lo afirma siempre, desde el ADR 0030**: solo si la norma suprimida es
**protectora** (`especificidad: lgtbi` en la watchlist). Sobre una **norma-vehículo** —la Ley del
SNS, el Registro Civil, la LOE, donde el derecho vive en dos o tres preceptos y el resto es materia
ajena— cae a `indeterminado` conservando regla y evidencia. Suprimir el art. 33 de la Ley 16/2003
no es un retroceso LGTBI.

**Regla que costó 2 falsos positivos de 4 y que no se relaja (ADR 0023): el verbo tiene que ir
pegado a la norma vigilada.** No basta con que el documento contenga una supresión *y* toque una
norma de la watchlist; hace falta que **la propia referencia declare** que la supresión es de esa
norma. Comprobadas por separado, las dos cosas coinciden en cualquier ley extensa sin tener que
ver: así fue como una ley «de los derechos de las personas LGBTI» acabó clasificada como
**retroceso** severidad 4 por una cláusula sobre finanzas públicas en una disposición final.

**Antes de escribir una familia nueva, mídela sobre el corpus archivado** (ADR 0027). No cuesta
una sola petición de red y ya evitó escribir una regla que aportaba cero.

Dos corolarios que valen para cualquier regla futura:

- **La condición que sostiene un signo se comprueba sobre la evidencia que lo nombra**, no sobre
  el documento entero. Es el mismo criterio que el eje referencial del prefiltro (7.3) y el que
  `pipeline/citas.py` aplica al verbo: un verbo suelto a 400.000 caracteres no dice de qué norma
  habla.
- **Perder el signo no es perder la vigilancia.** Cuando la evidencia no sostiene el signo, la
  norma cae a una regla `indeterminado` y sigue yendo a la cola de revisión. Afirmar un signo que
  no se puede sostener es lo que prohíbe la regla de oro 2; callarlo solo cuesta que lo decida
  una persona, que es lo que 7.7 existe para hacer.

### 7.7 Gate humano

Un validador revisa la cola antes de emitir. Obligatorio, sin flag que lo salte.

**Implementado el 2026-08-14 (ADR 0017).** `services/revision.py` es el **único** sitio del
código que escribe en `alerta`, y solo al aprobar; `security/panel.py` es la puerta única de
autenticación y `api/revision.py` la única parte de la API que escribe. Tres reglas que no son
detalles de implementación:

- **Solo entra en la cola lo que tiene veredicto** (`regla_aplicada IS NOT NULL`) **y señala
  una norma vigilada concreta** (`evidencia_json.normas_vigiladas` no vacío). El centinela del
  extractor (ADR 0009) no es un veredicto, y pedirle a una persona que apruebe la ausencia de
  conclusión llena la cola de ruido hasta que deja de mirarse — que es como un gate humano se
  vacía por dentro sin que nadie lo desactive. La segunda condición salió de revisiones reales:
  las reglas que identifican norma vigilada iban 3 de 3 aprobadas y R-SUP-002 **10 de 10
  descartadas**. **No se pierde recall** —la detección se sigue creando con su regla y sus spans—
  y se comprueba por el contenido de la evidencia, no por una lista de reglas, para que una regla
  futura entre o se quede fuera sola.
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

- ~~**OCR** de PDFs escaneados~~ — **prohibición levantada el 2026-08-22**, pero sigue sin hacer
  falta (la capa de texto del DOGC existe y se lee). **Antes de escribir una línea de OCR hay que
  demostrar con un documento real que su PDF no tiene capa de texto**, y llevarlo a un ADR. Lo que
  esta sección protege no es la técnica, es el plazo.
- ~~**Monitorización de prensa o redes sociales.** No.~~ — **relajado por el humano el
  2026-08-30**, con un motivo de plazo dicho tal cual: la entrega es el 10 de septiembre y
  construir a mano la configuración del proyecto es trabajo muy arduo. **En fase de construcción
  la IA puede ayudar a investigar**, prensa y fuentes secundarias incluidas; en fase de
  mantenimiento se volverá a revisar una a una.

  **Lo que esto autoriza y lo que no, porque la diferencia es todo el proyecto:**

  - **SÍ**: usar búsqueda web, prensa y fuentes de referencia (ILGA-Europe, FELGTBI+, Amnistía)
    para **construir y contrastar la configuración** — la watchlist, `docs/fuentes.md`, candidatos
    del gold set. Ya se hizo así una vez y salió bien: el `jurista-lgtbi` encontró contrastando
    con esas fuentes que a Aragón le faltaba una de sus dos leyes.
  - **SÍ, con una condición que no se negocia**: todo lo que entre en la configuración **se ancla
    a un identificador oficial verificado** (`BOE-A-…`) y se anota con su fecha de comprobación en
    el campo `nota`. La prensa sirve para **encontrar** una norma, nunca para afirmarla. Una
    entrada sin identificador comprobado no entra.
  - **NO**: que nada procedente de prensa o redes sea **entrada del pipeline** ni contenido
    publicado. Ni se ingiere, ni se archiva, ni se clasifica, ni alimenta una alerta. El archivo
    de la 6.5 solo contiene boletines oficiales.
  - **NO**: que un modelo emita «esta comunidad va a peor» y eso llegue a una pantalla. Sigue
    intacta la **regla de oro 2** —la clasificación avance/retroceso se deriva del diff con reglas
    auditables— y la **3** —el LLM extrae hechos, no dicta veredictos—. La CHECK
    `origenclasificacion` lo hace cumplir, y no se toca.

  Dicho corto: **la IA ayuda a construir la lista de lo que hay que vigilar; no ayuda a decidir
  qué ha pasado.** Lo primero es investigación con verificación humana detrás; lo segundo es el
  veredicto que este proyecto existe para no delegar.
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
  criterio. El agente comprueba el resultado del merge en un clon limpio; **autoriza el humano**.

---

## 9. Git y flujo de trabajo

- **Conventional commits**: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `sec:`.
- **Una rama por feature**, PR aunque trabajes solo (el historial se lee en la evaluación).
  Las tareas ejecutadas por el driver van en `task/NN-nombre` (sección 13.3).
- **ADRs** en `docs/adr/NNNN-titulo.md`. Formato: contexto, decisión, alternativas,
  consecuencias. **Están todos escritos del 0001 al 0032** y su título dice de qué van: `ls
  docs/adr/` es el índice, y duplicarlo aquí solo creaba dos listas que se desincronizan.
  **El siguiente número libre es el 0033.** No queda ninguno reservado.
  Los cuatro que más se citan desde el código: **0011** (se descarga el día entero), **0013**
  (trazabilidad por offsets), **0023** (el verbo pegado a la norma vigilada, con el **0031** que
  lo lleva un paso más allá) y **0027** (el límite medido del eje referencial). El **0025** es el único implementado a medias: falta la
  interfaz.
- Mantén `SECURITY.md` y `THREAT-MODEL.md` vivos, no como trámite final. Esta revisión añade
  entradas al modelo de amenazas: volumen de peticiones en fase 2 (6.2), `<analisis>` como
  entrada hostil (6.7) y salida del modelo como vector de acción (6.10).
- Mensajes de commit en español está bien; el código y los identificadores en inglés.

---

## 10. Comandos

```bash
# Levantar todo: base de datos, backend, worker y la web (desde 2026-08-17 el frontend también
# es un servicio del compose). PUERTOS FIJOS del host: web 5174, API 8010 (no 8000: ocupado).
docker compose up --build

# Backend en local
cd backend && uvicorn app.main:app --reload

# Migraciones
alembic revision --autogenerate -m "..."   &&   alembic upgrade head
# y DESPUÉS de cada upgrade, comprobar que siguen vivas las CHECK (hoy 15). El filtro honesto
# lleva `conrelid <> 0`: sin él salen dos filas de information_schema que no son del proyecto.
psql -c "SELECT conrelid::regclass, conname FROM pg_constraint
         WHERE contype='c' AND conrelid <> 0 ORDER BY 1,2"

# Calidad (lo que corre el CI)
ruff check . && ruff format --check . && mypy backend/app && pytest --cov

# Ingesta manual (una fecha concreta). Las cuatro fuentes integradas:
#   boe | dogc | boa | bocyl   (la tabla FUENTES de worker/run.py manda)
python -m worker.run --fuente boe --fecha 2024-12-19
python -m worker.run --fuente bocyl --fecha 2024-01-10

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

# La ingesta DIARIA la corre ya GitHub Actions, con la base en Neon y el archivo en un bucket
# (ADR 0032): `.github/workflows/ingesta.yml`. Va sin extracción —en un runner no hay Ollama— y
# eso no cuesta vigilancia (ADR 0016). Los reprocesados masivos siguen siendo de casa.

# --- Backfills de fondo, uno por fuente -----------------------------------------------------
# REANUDABLES por marcas e IDEMPOTENTES por el sha256: relanzarlos salta en segundos lo hecho.
# OJO: un `exec` NO sobrevive al cierre de la sesión ni al reinicio del contenedor. Hay que
# relanzarlos a mano después de cada `docker compose up`; ha costado tiempo dos veces.
docker compose exec -d worker sh //app/backfill.sh          # BOE
docker compose exec -d worker sh //app/backfill_boa.sh      # BOA
docker compose exec -d worker sh //app/backfill_bocyl.sh    # BOCYL

# Quién ha reformado a cada norma vigilada, preguntándoselo al consolidado del BOE (ADR 0018).
# UNA petición por ley vigilada da su historial completo de reformas, sin backfillear años. NO
# ingiere ni clasifica: imprime qué días harían falta y el gasto lo decide una persona.
docker compose exec -T backend python -m scripts.reformas_de_vigiladas

# Elegir candidatos para el gold set y escribir sus borradores. NO los etiqueta (7.8): deja
# rellenado lo que es un hecho y omite los tres campos de juicio, para que el esquema rechace
# el fichero mientras nadie lo haya mirado. Muestreo estratificado con semilla fija.
docker compose exec -T backend python -m scripts.preparar_gold_set

# Ollama (local, sin clave, sin coste)
ollama serve                        # normalmente ya corre como servicio
ollama list                         # modelos disponibles
ollama show qwen2.5:3b-instruct     # digest del modelo, que va en extraccion_json
curl -s localhost:11434/api/tags    # comprobación rápida de que responde

# Frontend: normalmente NO hace falta, lo levanta el compose en http://localhost:5174.
# Solo para trabajar sin docker; el proxy apunta por defecto al 8010 del host, que es la API.
cd frontend && npm run dev -- --host 127.0.0.1

# Driver de sesiones (sección 13.3)
./run_agent.sh 1                    # una tarea del backlog; empezar por 1 para calibrar
```

---

## 11. Estado actual del proyecto → **[`ESTADO.md`](ESTADO.md)**

El estado vive en un fichero aparte desde el 2026-08-09, porque este entra entero en el contexto
de cada subagente y el historial era más de la mitad.

- **Al retomar el proyecto**, `ESTADO.md` es lo primero que hay que leer.
- **Al cerrar un trabajo**, se actualiza `ESTADO.md`, no este fichero. Aquí solo se toca lo que
  cambia de verdad las reglas: el modelo de dominio, la seguridad, el pipeline.
- **Las referencias a «sección 11» del repositorio siguen siendo válidas**: conserva su número,
  solo cambia de fichero.

---

## 12. Acciones externas: qué no se hace sin permiso

> Pedido tal cual al cierre de S0. No reordenar por criterio propio sin comentarlo primero;
> si alguno de estos puntos ya no aplica o contradice algo de este archivo, **para y pregunta**
> antes de tocarlo. El resto del backlog de producto vive en [`ESTADO.md`](ESTADO.md): aquí solo
> se queda lo que es una **regla**, o sea las acciones externas.

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

## 13. Cómo se ejecuta el trabajo con Claude Code → **[`TRABAJO.md`](TRABAJO.md)**

Límites de cuota, backlog de tareas, el driver de sesiones y los cuatro subagentes. Salió a un
fichero propio el 2026-08-30 por el motivo de la cabecera —este entra entero en el contexto de
cada subagente— y porque es justo la parte que ningún subagente puede ejecutar.

**Las referencias a «sección 13» del repositorio siguen siendo válidas**: conserva su número, solo
cambia de fichero. Lo que hay que saber sin abrirlo, porque son reglas y no procedimiento:

- **Una tarea = una sesión limpia.** El estado vive en `ESTADO.md`, no en la conversación.
- **Nunca `--dangerously-skip-permissions`** ni `alembic upgrade` desatendido.
- **Los subagentes se lanzan de uno en uno** y no por encima del 60 % de consumo; son de ámbito
  de proyecto, así que la sesión se abre **en la raíz del repositorio** o no existen.
- **Ninguna rama entra en `main` sin que la autorice el humano** (13.3), y ninguna de la 12
  entra en el backlog automático.
