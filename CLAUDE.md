# CLAUDE.md — Faro Cuir

> Instrucciones persistentes para Claude Code. Léete este archivo entero al inicio de cada
> sesión. Si vas a tomar una decisión que contradiga algo de aquí, **para y pregúntame**.

---

## 0. Decisiones abiertas (cámbialas si el humano lo pide)

- **Backend:** Python 3.12 + FastAPI. (Alternativa descartada por ahora: Node. Si se cambia,
  se rehace la sección de stack, no el diseño.)
- **Frontend:** React 18 + TypeScript + Vite + TailwindCSS.
- **Nombre del proyecto:** Faro Cuir. (Antes "Centinela"; renombrado en S0 — "cuir" deja claro
  desde el nombre que la herramienta es de y para la comunidad LGTBIQ+, no un vigilante genérico.
  La carpeta local del repo sigue llamándose `Centinela/`; no se ha movido, solo el nombre de
  producto. Historial de commits previos al cambio conserva el nombre antiguo, no se reescribe.)
- **LLM:** proveedor-agnóstico vía una interfaz propia (`llm/provider.py`). Por defecto se
  asume una API externa para clasificar (el input es **texto público** de boletines, no hay
  problema de privacidad ahí). Ollama local queda como opción documentada para independencia
  y coste.

---

## 1. Qué es esto

**Faro Cuir** es un sistema de vigilancia normativa que monitoriza a diario los boletines
oficiales y parlamentos autonómicos españoles (17 CCAA + BOE) para detectar cambios legislativos
que afecten a los derechos del colectivo LGTBI+, con foco especial en las personas trans.

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
   del diff con reglas auditables**, no de la opinión de un LLM. Ver sección 5.
3. **El LLM extrae hechos, no dicta veredictos.** Su salida es estructurada (qué norma, qué
   artículos, qué cambia, quién emite, qué ámbito). Nunca "esto es un retroceso".
4. **Gate humano obligatorio** antes de emitir cualquier alerta. Sin excepción.
5. **Minimización de datos.** Los suscriptores son dato sensible (revelan afinidad al colectivo).
   Ver sección 6.4.
6. **Nada de scope creep.** Ver sección 8. Si se te ocurre añadir monitorización de prensa o
   redes: no.
7. **Todo cambio de arquitectura → un ADR.** Ver sección 7.
8. **Nunca inventes fuentes, plazos ni artículos legales.** Si no lo has verificado, márcalo
   como `TODO(verificar)` y avisa al humano.

---

## 3. Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic |
| DB | PostgreSQL 16 (búsqueda full-text con configuración `spanish`) |
| Worker | Script Python idempotente lanzado por cron en su propio contenedor. **NO Celery** (overkill). |
| Parseo XML | `defusedxml` obligatorio. `lxml` solo con `resolve_entities=False`, sin DTD, sin red. |
| HTTP saliente | `httpx` con timeouts, allowlist de dominios y límite de tamaño de respuesta. |
| LLM | Interfaz propia en `llm/provider.py`. Cualquier proveedor detrás de ella. |
| Frontend | React 18, TypeScript, Vite, TailwindCSS |
| Tests | `pytest`, `pytest-cov` (back); `vitest` (front) |
| Lint/format | `ruff` (lint+format), `mypy` (estricto en `services/` y `llm/`) |
| Contenedores | Docker + docker-compose |
| CI | GitHub Actions: `ruff` → `mypy` → `pytest` → `gitleaks` |

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
│   │   ├── pipeline/          # prefiltro, extractor, clasificador, diff
│   │   ├── llm/               # provider.py + prompts versionados
│   │   ├── security/          # xml_safe.py, url_guard.py, hashing.py, sellado.py
│   │   └── webhooks/          # firma HMAC entrada/salida
│   ├── worker/                # entrypoint del cron de ingesta
│   ├── alembic/
│   ├── tests/
│   └── pyproject.toml
└── frontend/
    ├── src/
    │   ├── components/
    │   ├── pages/
    │   ├── api/               # cliente tipado del backend
    │   └── main.tsx
    └── package.json
```

---

## 5. Modelo de dominio

Entidades núcleo (nombres reales de tabla en snake_case):

- **fuente** — un origen de datos. Campos: `id`, `nombre`, `tipo` (`boe`|`boletin_autonomico`|
  `parlamento`), `ccaa`, `formato` (`api`|`rss`|`html`|`pdf`), `url_base`, `licencia_reutil`,
  `activa`.
- **documento** — un documento crudo ingerido. `id`, `fuente_id`, `identificador_oficial`,
  `fecha_publicacion`, `url_original`, `sha256`, `sello_tiempo`, `ruta_almacen`, `estado_pipeline`.
  El `sha256` + `sello_tiempo` forman el **archivo íntegro verificable** (ver sección 6.5).
- **norma** — un ítem normativo identificado dentro de un documento. `id`, `documento_id`,
  `titulo`, `rango` (ley|decreto|orden|instruccion|resolucion|proposicion), `organo_emisor`,
  `ambito` (sanitario|educativo|laboral|documental|general|...).
- **version_norma** — versionado. Una norma que modifica a otra genera una nueva versión con
  referencia a la anterior. Aquí vive el diff (texto_anterior / texto_nuevo por artículo).
- **deteccion** — el resultado del pipeline sobre una norma. `id`, `norma_id`,
  `extraccion_json` (hechos del LLM), `clasificacion` (avance|retroceso|neutro|indeterminado),
  `severidad`, `confianza`, `origen` (`derivado_diff`|`heuristica`), `revisada` (bool).
- **cola_revision** — items pendientes de gate humano. Estado: `pendiente`|`aprobada`|`descartada`.
- **alerta** — una detección aprobada y emitida. `id`, `deteccion_id`, `emitida_en`.
- **suscriptor** — destinatario de alertas. **Minimizado** (ver 6.4). `id`, `email_hash`,
  `webhook_url` (opcional), `ccaa_interes[]`, `token_baja_opaco`.

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

### 6.5 Archivo íntegro con sellado de tiempo
Al ingerir cada documento: `sha256` del contenido + sello de tiempo. Esto crea un archivo
verificable de lo que realmente se publicó, como respuesta técnica a las desindexaciones
administrativas sin registro público. Documentar el porqué en un ADR.

### 6.6 Webhooks
- **Salida** (a Slack/Discord/n8n de las ONGs): firma HMAC-SHA256 del payload + timestamp +
  nonce anti-replay en cabecera. Documentar cómo verifica el receptor.
- **Entrada** (aprobación desde el panel, si aplica): verificar firma antes de procesar.

### 6.7 Inyección de prompt
Contenido no confiable entrando en un LLM. Improbable en un BOE, pero es el patrón a defender:
delimitación clara del contenido, el prompt de sistema nunca es sobreescribible por el
documento, y la salida del LLM se valida contra un esquema Pydantic (si no valida, se descarta,
no se "interpreta").

### 6.8 Higiene general
- Secretos solo por entorno. `.env` en `.gitignore`. `gitleaks` en CI.
- Cabeceras de seguridad en las respuestas (CSP, HSTS, X-Content-Type-Options, etc.).
- Rate limiting en la API pública desde el principio, no al final.
- Dependencias fijadas y auditadas.

---

## 7. Pipeline de clasificación

```
Documento → [1] Prefiltro léxico → [2] Extractor LLM → [3] Clasificador → [4] Gate humano → Alerta
```

1. **Prefiltro léxico** — regex + diccionario (LGTBI, identidad de género, orientación sexual,
   coeducación, diversidad familiar, terapias de conversión, expresión de género, cartera de
   servicios, ...). Ajustado a **recall máximo**: mejor 50 falsos positivos que 1 falso negativo.
   Descarta la inmensa mayoría sin gastar un token.
2. **Extractor LLM** — devuelve JSON estructurado validado por Pydantic: norma afectada,
   artículos, texto anterior/nuevo, órgano, ámbito. **No clasifica.**
3. **Clasificador por diff** — reglas auditables sobre el diff derivan avance/retroceso/neutro/
   indeterminado + severidad. Dos umbrales: precisión alta para lo autopublicable, recall alto
   para lo que va a la cola de revisión.
4. **Gate humano** — un validador revisa la cola antes de emitir. Obligatorio.

**Set de evaluación:** `tests/gold_set/` con 150-200 documentos históricos etiquetados a mano
(incluir la reforma madrileña de 2023, reformas rechazadas, y muchos negativos). Sin esto la
parte de IA no es evaluable. **No lo recortes nunca.**

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

---

## 9. Git y flujo de trabajo

- **Conventional commits**: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `sec:`.
- **Una rama por feature**, PR aunque trabajes solo (el historial se lee en la evaluación).
- **ADRs** en `docs/adr/NNNN-titulo.md`. Formato: contexto, decisión, alternativas, consecuencias.
  Primeros ADRs esperados: 0001 arquitectura conocimiento-cero de suscriptores, 0002 el LLM
  extrae no juzga, 0003 gate humano obligatorio, 0004 no persistir veredicto del LLM,
  0005 archivo con sellado de tiempo.
- Mantén `SECURITY.md` y `THREAT-MODEL.md` vivos, no como trámite final.
- Mensajes de commit en español está bien; el código y los identificadores en inglés.

---

## 10. Comandos

```bash
# Levantar todo
docker compose up --build

# Backend en local
cd backend && uvicorn app.main:app --reload

# Migraciones
alembic revision --autogenerate -m "..."   &&   alembic upgrade head

# Calidad (lo que corre el CI)
ruff check . && ruff format --check . && mypy backend/app && pytest --cov

# Ingesta manual (una fecha concreta)
python -m worker.run --fuente boe --fecha 2024-12-19

# Frontend
cd frontend && npm run dev
```

---

## 11. Estado actual del proyecto

<!-- Claude Code: actualiza esta sección al terminar CADA trabajo, no solo al cerrar la sesión.
Dos cosas, siempre:
  1. Qué se ha hecho y qué toca. Es lo primero que se lee al retomar.
  2. Cada punto de "Siguiente" lleva su **coste estimado en tokens de contexto**, calculado
     por ti a partir del alcance real (qué hay que leer, cuánto código sale, qué verificación
     hace falta), no de una fórmula. Sirve para decidir si una tarea cabe en la sesión que
     empieza o hay que partirla; si la estimación no es obvia, di en qué se basa.
  3. **Calibra contra lo medido, no contra la intuición.** Las primeras estimaciones de esta
     sección salieron ~3x altas: se estimó el frontend en 40k y el prefiltro en 55k, y
     costaron del orden de 15k y 25k reales. Una tarea normal de este repo -un módulo, sus
     tests, migración si toca y verificación en navegador o curl- ronda los **15-30k**. Si te
     sale más de 50k, sospecha de la estimación antes que del alcance. -->

- **Semana actual:** S1 / backend y seguridad — en curso. Repo arrancado el **2026-08-04**.
- **Hecho en S1 (último trabajo): contrato de extracción del LLM (media etapa 2).**
  - Se hizo **la mitad verificable sin credenciales**, que además es donde están todas las
    decisiones de seguridad. El proveedor real y el cableado al pipeline quedan pendientes:
    no se da por bueno lo que no se ha podido ejecutar de verdad.
  - `schemas/extraccion.py` es un **control, no un DTO**: no tiene ningún campo de
    clasificación, severidad ni valoración, y `extra="forbid"` rechaza entera una respuesta
    que los traiga. Misma idea que la CHECK de `deteccion.origen` (ADR 0004) pero una capa
    antes: el veredicto del modelo no tiene dónde aterrizar. La ausencia de esos campos está
    escrita en el fichero para que nadie los añada creyendo que faltaban.
  - `llm/provider.py` — puerta única al modelo, mismo criterio que `url_guard` con el HTTP
    saliente. La interfaz no expone temperatura ni tokens: ataría el pipeline a un proveedor.
  - **Orden de las defensas contra inyección de prompt (6.7):** el documento va entre marcas
    largas, y si el propio documento las contiene se eliminan antes de envolver (si no,
    podría cerrar el bloque y escribir fuera de la zona delimitada). El prompt declara el
    contenido como no confiable — eso es **mitigación, no garantía**. La defensa que cuenta
    es que **al validador no se le convence**: hay un test que simula que la inyección
    funciona y comprueba que la salida se descarta igual.
  - Al descartar se registran los **campos** que fallan, nunca lo que devolvió el modelo: si
    fue manipulado para emitir un veredicto, ese texto no puede quedar en un log donde
    alguien lo lea como conclusión del sistema.
  - 219 tests.
- **Hecho en S1 (último trabajo): los dos controles que faltaban de la 6.8 y seguridad
  documentada de verdad.**
  - `security/headers.py` — CSP `default-src 'none'` (una respuesta JSON no debe cargar
    nada), `nosniff`, `no-referrer` —que aquí no es rutina: el referer revela por sí solo
    que alguien venía de esta web—, `frame-ancestors`, Permissions-Policy y HSTS sin
    `preload`. `/docs` lleva su propia CSP acotada al CDN de Swagger en vez de relajar la de
    la API entera.
  - `security/rate_limit.py` — 60 pet/min por IP, ventana **deslizante** (una fija deja pasar
    el doble a caballo entre dos ventanas). Sin dependencia nueva. Tres cosas que son el
    fondo: **no se lee `X-Forwarded-For`** (la escribe el cliente), el limitador tiene tope
    de clientes en memoria porque si no el propio control es el vector de agotamiento, y al
    llegar al tope **falla abierto** a propósito. `/health` exento o el healthcheck del
    contenedor declararía el servicio caído.
  - **Orden de los middlewares:** en Starlette el último `add_middleware` queda por fuera,
    así que las cabeceras van las últimas para que **el 429 salga también con ellas**. Hay un
    test que lo fija; casi se pone al revés.
  - `THREAT-MODEL.md` **real**: STRIDE por componente con cada control apuntando a su código,
    y lo no mitigado escrito, no omitido. `SECURITY.md`: su tabla decía "Pendiente" en todo
    desde S0 cuando la mayoría llevaba hecha desde S1 — corregido, con "Parcial" obligado a
    nombrar su limitación.
  - 194 tests. Verificado contra la API real: seis cabeceras presentes, 59 respuestas 200
    seguidas de 429 con `Retry-After`, y el 429 con `nosniff`.
- **Hecho en S1 (último trabajo): prefiltro léxico, etapa 1 del pipeline.**
  - `pipeline/prefiltro.py` — módulo **puro** (ni DB ni red) con ~90 términos. Sesgado a
    recall, no equilibrado: sin lista negra ni exclusiones, con las variantes antiguas y
    clínicas (`disforia de genero`, `reasignacion de sexo`) porque quien recorta derechos
    escribe con el léxico de hace veinte años, y con límites de palabra —sin ellos `trans`
    dispara con «transporte» y «transitoria», que salen en el BOE a diario—.
  - Dos categorías de término, `DIRECTO` y `CONTEXTO`, que **no cambian la decisión**: sirven
    para medir cuánto ruido mete la lista genérica y poder afinarla sin tocar el recall.
  - Persistido en `norma` (4 columnas + migración): estado, términos que dispararon, versión
    del vocabulario y cuándo. `pendiente` ≠ `descartada`, y al descartar se guarda lista
    vacía, no NULL. Subir `VERSION_VOCABULARIO` obliga a reevaluar lo anterior:
    `worker.run --reprefiltrar`. El worker aplica el filtro en la misma pasada que la ingesta.
  - **ADR 0007**, con la alternativa importante razonada: no se usa un LLM para filtrar
    porque cuesta una llamada por norma, no es auditable y no es reproducible.
  - Verificado sobre datos reales: se ingirió además el BOE del **2023-03-01** para tener un
    positivo conocido. 436 normas evaluadas, encuentra la **Ley 4/2023** por `lgtbi` y
    `personas trans`, descarta 435 sin un solo falso positivo de contexto, segunda pasada
    evalúa 0 (idempotente) y la CHECK rechaza un estado inventado. 178 tests.
  - **Aviso honesto:** eso demuestra que funciona, **no** que el recall sea alto. Con un solo
    positivo conocido no se puede estimar cuántos se pierden. El recall real solo se podrá
    medir con el gold set; hasta entonces no publicar ninguna cifra de recall.
  - Cuarta vez con la trampa del autogenerate, y la peor: proponía borrar **ocho** CHECK,
    incluida `origenclasificacion` de `deteccion` (ADR 0004). Ver aviso más abajo.
  - **El embudo, visible de punta a punta.** `NormaResumen` publica `prefiltro_estado` y
    `prefiltro_terminos`, y el Archivo y la Ficha los pintan con los **términos exactos**
    que hicieron pasar cada norma («pasó por 2 términos» no es auditable; «pasó por *lgtbi*
    y *personas trans*» sí), más el recuento del embudo y un filtro de solo relevantes. Se
    expone a propósito: un filtro que decide en silencio qué se mira es justo lo que este
    proyecto denuncia en la administración. `PrefiltroBadge` usa gris neutro y **no** la
    paleta de avance/retroceso, porque pasar el prefiltro no es una clasificación y el color
    habría sugerido un veredicto que nadie ha emitido. 180 tests; verificado en navegador
    sobre `BOE-S-2023-51`: «1 de 179 pasan el prefiltro».
- **Hecho antes en S1: el frontend deja de ser una maqueta.**
  - **Pantalla `Archivo` nueva** (`pages/ArchivoPage.tsx`), la primera que lee de la API:
    lista los documentos ingeridos con su `sha256` y su sello, y las 257 normas del sumario
    con buscador. Existe porque la Ficha necesita el id de una norma real y ni el Mapa ni
    las Alertas pueden dárselo, y porque el archivo con su huella es el entregable de la
    6.5, no material de relleno. `api/useRecurso.ts`: hook de veinte líneas en vez de
    react-query; lo único que hacía falta era cancelar la petición en curso y no confundir
    una cancelación con un error.
  - **Ficha de norma migrada a `GET /api/documentos/{id}`.** Ya no importa de `mocks.ts`.
    El ancla muerta `#fuente` apunta ahora a `norma.url_texto` con `rel="noopener
    noreferrer"`; si el sumario no publica enlace para esa norma, se dice en vez de pintar
    uno falso. **Lo relevante es lo que la Ficha ha dejado de enseñar porque no existe:**
    la insignia de clasificación (vive en `deteccion`, vacía — pintarla sería el veredicto
    sin gate humano que prohíben las reglas 2 y 4), el diff y el historial (`version_norma`,
    vacía), la autoridad TSA «freetsa.org» que el mock anunciaba (hoy el sello lo pone
    nuestro propio ingestor: se declara pendiente, ADR 0005) y el «✓ Íntegro», que afirmaba
    una recomprobación del hash que nadie hace todavía (pasa a «Archivado»). `rango` y
    `ambito` nulos se pintan como «pendiente de análisis», no como huecos.
  - **El Mapa y las Alertas se quedan con mocks, pero marcados.** `DemoDataNotice`: aviso a
    ancho completo arriba de las dos, diciendo de qué tabla depende cada una para dejar de
    ser una maqueta. La insignia de la cabecera se calcula por pantalla desde
    `PANTALLAS_CON_MOCK`; la franja de pulso, que anunciaba «1.284 documentos analizados
    hoy» también sobre las pantallas reales, consulta ahora la API en ellas. Los botones
    que prometían un diff llevan al Archivo y lo dicen.
  - Verificado en navegador de verdad (Playwright, 3 guiones, 55 comprobaciones sobre el
    DOM) contra la API real a través del proxy de Vite, contrastado con `psql` fila a fila,
    y comprobado que el proxy sigue sin necesitar ninguna cabecera CORS. Backend intacto:
    136 tests en verde.
- **Hecho antes en S1:**
  - `security/url_guard.py` — puerta **única** de salida HTTP (nada en `ingest/` importa
    `httpx` directamente). Solo https y puerto 443, allowlist por dominio con subdominio
    real, rechazo de credenciales en la URL, rechazo de toda IP no global vía `is_global`,
    redirecciones seguidas a mano revalidando cada salto, tope de bytes al leer el cuerpo,
    timeouts. La petición se **clava a la IP ya validada** con el nombre en `Host` y en
    `sni_hostname`, contra DNS rebinding, sin relajar la verificación del certificado.
  - `security/xml_safe.py` — único sitio donde se parsea XML. `forbid_dtd=True` (mata XXE y
    bombas de entidades de raíz) más límites propios de profundidad y número de nodos, que
    defusedxml no cubre, comprobados durante el parseo.
  - `security/hashing.py` — sha256 del contenido crudo y ruta de almacén derivada del hash
    (path traversal, 6.3) con lista blanca de extensiones.
  - Tabla `documento` + migración, con clave natural única `(fuente_id,
    identificador_oficial)` que es lo que hace idempotente al worker.
  - `ingest/boe.py` + `services/ingesta.py` + `worker/run.py`: **ingesta real funcionando
    contra el BOE**. Verificada de verdad, no solo con tests: 257 items del sumario del
    2024-12-19, segunda ejecución sin duplicar, `sha256sum` del fichero archivado igual a su
    propio nombre. Migración de datos con la fila del BOE.
  - Resto del modelo de dominio: `norma`, `version_norma`, `deteccion`, `cola_revision`,
    `alerta`, `suscriptor` + migración. Tres reglas del proyecto pasan de convención a
    esquema: `version_norma` es **inmutable** (trigger de PostgreSQL que rechaza UPDATE y
    DELETE, verificado), en `origen` de `deteccion` **no existe el valor `llm`** (la CHECK
    hace que el veredicto del modelo no sea representable), y `suscriptor` guarda el email
    solo como HMAC con pepper de entorno, con token de baja aleatorio.
  - ADRs 0002 (el LLM extrae no juzga), 0003 (gate humano), 0004 (no persistir el veredicto
    del LLM), 0005 (archivo con sellado de tiempo) y 0006 (puerta única de salida HTTP).
  - Persistencia de `norma` desde el sumario (257 normas reales del BOE del 19-12-2024) y
    **API pública de solo lectura**: `GET /api/documentos` y `GET /api/documentos/{id}`.
    Esquemas de salida escritos a mano, no generados del modelo; `ruta_almacen` no se expone,
    `sha256` y `sello_tiempo` sí (6.5). Tope duro de paginación y un test que falla si algún
    día aparece un método distinto de GET.
  - 135 tests (2 de ellos solo corren con PostgreSQL), ruff y mypy estricto limpios.
- **Hecho en S0:**
  - Backend: esqueleto del repo, `docker-compose.yml` (Postgres 16 con collation ICU
    `es-ES`, backend con hot-reload, worker idle sin cron todavía), FastAPI con `/health`
    verificando conexión real a la DB, config vía `pydantic-settings`, mypy estricto.
  - Alembic inicializado con la primera migración: solo la tabla `fuente` (enum como
    VARCHAR+CHECK, no ENUM nativo; valores en minúsculas coincidiendo con el vocabulario
    de la sección 5). Resto de tablas del modelo de dominio, pendientes.
  - CI en GitHub Actions: ruff → mypy → alembic upgrade → pytest → gitleaks, con un
    servicio de Postgres real en el job. Test trivial de `/health` en verde.
  - ADR 0001 (arquitectura y alcance) y arranque de `docs/fuentes.md` (18 fuentes, solo
    BOE confirmado; las 17 CCAA quedan `TODO(verificar)` a propósito).
  - Frontend (añadido en esta misma sesión a partir de un handoff de diseño en
    claude.ai/design, fuera del plan original de hoy): scaffold Vite + React 18 + TS +
    Tailwind v4, tokens de diseño con tema claro/oscuro, datos mock (`src/api/mocks.ts`),
    componentes compartidos (`ClassificationBadge`, `AlertCard`, `DiffBlock`) y las tres
    pantallas (Mapa, Alertas, Ficha de norma) con navegación real entre ellas. Verificado
    en navegador de verdad con Playwright headless (no solo "compila"), accesible por
    teclado en el mapa (mejora sobre el mock original) y con `sr-only` en el diff.
    Todavía corre 100% sobre datos mock, sin cablear a la API.
  - Proyecto renombrado de "Centinela" a "Faro Cuir" (decisión del humano). La carpeta
    local del repo sigue llamándose `Centinela/` a propósito (ver sección 0).
- **Siguiente (por orden sugerido).** El coste es contexto estimado para hacer la tarea
  entera *con verificación real*, no solo escribir el código. **Recalibrado a la baja** tras
  medir S1: casi todo cabe en una sesión.
  1. **Gold set** (`tests/gold_set/`) — **~35k, y aun así pártelo**. Sin él la parte de IA no es
     evaluable. No recortarlo. Lo caro no es el código sino traer y etiquetar 150-200
     documentos históricos —eso no lo acelera el contexto—; hazlo por tandas. **Ha subido de
     prioridad:** ahora es también lo único que puede medir el recall del prefiltro, que hoy
     está sin medir. Empieza apartando documentos candidatos aunque no toque todavía.
  2. **Cerrar el extractor** — **~20k**. El contrato, la interfaz y las defensas ya están
     (`llm/provider.py`, `schemas/extraccion.py`, 25 tests). Falta: un proveedor real detrás
     de `ProveedorLLM` —necesita **clave de API**, decidir proveedor y meterlo en `config.py`
     como el resto, nunca hardcodeado—, descargar el texto íntegro **vía `url_guard`** solo
     de las normas que pasan el prefiltro, y persistir en `deteccion.extraccion_json` con la
     versión del prompt. Luego el clasificador por diff — **~25k**, commit aparte: depende de
     que la salida del extractor esté ya estabilizada.
  3. Auditoría real de las 17 fuentes autonómicas en `docs/fuentes.md` — **~45k, pártelo**.
     Verificar contra cada fuente oficial, no completar por deducción. Es coste de lectura
     externa, no de código: ~2,5k por fuente. Es el único punto donde el coste escala con
     el número de fuentes y no con el código.
     **Candidata a recortar si aprieta el plazo:** la sección 8 ya autoriza documentar el
     resto como hoja de ruta, y compra poco frente al tribunal comparado con tener el
     pipeline entero funcionando sobre el BOE.
  4. Panel de revisión con autenticación (gate humano, ADR 0003) — **~35k**. Sube si hay que
     decidir el modelo de sesión y contraseñas desde cero.
  5. **Migrar el Mapa y las Alertas a la API** — **~20k**. Bloqueado hasta los puntos 1-2:
     hasta que `deteccion` y `alerta` tengan filas no hay nada real que enseñar. Cuando se
     migre cada una, quitarla de `PANTALLAS_CON_MOCK` (`frontend/src/lib/navigation.ts`) y
     el aviso de la interfaz desaparece solo. Los componentes `DiffBlock` y `ArticleHistory`
     están sin usar a propósito, esperando a ese momento; no borrarlos.
  - Pendiente transversal: **`docs/eipd.md` sigue en esqueleto** — **~25k**. Es lo único de
    seguridad que queda sin desarrollar; tiene material real que documentar (modelo de
    suscriptores de la 6.4) pero no se puede cerrar hasta que exista el flujo de alta y baja,
    porque sin él no hay consentimiento que evaluar. `THREAT-MODEL.md` ya está desarrollado.
  - Evolución documentada en el ADR 0005: sello RFC 3161 contra una TSA pública, para que
    la fecha del archivo sea verificable por terceros y no solo afirmación nuestra.
  - **Aviso para migraciones futuras:** el autogenerate de alembic propone en *cada*
    migración borrar las CHECK generadas por `Enum(native_enum=False, create_constraint=True)`.
    **Ha pasado cuatro veces.** Revisar y eliminar esas líneas SIEMPRE antes de aplicar. En la
    cuarta proponía borrar ocho de golpe, incluida `origenclasificacion` de `deteccion`, que
    es la que hace que el veredicto del LLM no sea representable en el esquema (ADR 0004):
    aplicarlo a ciegas no es ruido cosmético, desarma un control del proyecto. Después de
    cada `alembic upgrade`, comprobar que siguen vivas:
    `SELECT conrelid::regclass, conname FROM pg_constraint WHERE contype='c'` — hoy son 11.
  - **Aviso sobre el frontend:** no se ha añadido ningún endpoint nuevo al backend para el
    Archivo ni para la Ficha. La Ficha pide el documento entero y busca la norma dentro,
    porque el documento hace falta igualmente (la fecha, el hash y el sello son suyos). Si
    algún día hay muchos documentos ingeridos, lo que se queda corto primero es que
    `GET /api/documentos/{id}` devuelva las ~250 normas de golpe, no la pantalla.
  - Sección 12: el backlog del humano sigue **sin tocar salvo un punto**, que ha caído de
    paso: el ancla muerta `#fuente` de "Datos / navegación" ya apunta al texto real. El
    mapa (Canarias, zoom, provincias, Ceuta y Melilla), el texto reivindicativo y la
    difusión siguen pendientes tal cual se pidieron. La entrada del backlog **no** se ha
    editado: el backlog es del humano.
- **Bloqueos:** ninguno.
- **Deuda conocida:** `tests/test_health.py` necesita un Postgres accesible; en local falla
  con 503 si no está levantado el `docker compose`. En CI pasa. No es regresión de S1.

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
