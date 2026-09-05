# AGENTS.md — Faro Cuir

> **Esto es un RESUMEN de emergencia, no el contrato.** El contrato completo es
> [`docs/CLAUDE.md`](docs/CLAUDE.md) (~56 KB) y **no cabe aquí**: los ficheros de reglas están
> capados a 12.000 caracteres. Lo que sigue es lo que evita romper el proyecto; el porqué de cada
> cosa está allí.
>
> **Antes de escribir código, lee `docs/CLAUDE.md` entero.** Y antes de decidir qué hacer, lee
> [`docs/ESTADO.md`](docs/ESTADO.md), que dice dónde estamos (su última sección es «CÓMO RETOMAR
> ESTO»). Si vas a tomar una decisión que contradiga algo de `docs/CLAUDE.md`, **para y pregunta**.

## Qué es esto

Sistema de vigilancia normativa que monitoriza boletines oficiales españoles (BOE + DOGC hoy) para
detectar cambios que afecten a derechos LGTBI+, con foco en personas trans. Es la práctica final de
un máster de **Ciberseguridad e IA**, con plazo al 2026-09-10. **El rigor puntúa más que las
features**: ante la duda entre «una feature más» y «hacer bien lo que hay», siempre lo segundo.

Stack: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, PostgreSQL 16, React 18 +
TypeScript + Vite, Docker. Tests `pytest` y `vitest`. Lint `ruff`, tipos `mypy`.

## Las 10 reglas de oro (no negociables)

1. **Seguridad primero.** Cada entrada externa es hostil hasta que se demuestre lo contrario.
2. **Neutralidad política.** El sistema nunca emite un juicio propio. Publica el diff y la fuente.
   La clasificación avance/retroceso se **deriva del diff con reglas auditables**.
3. **El LLM extrae hechos, no dicta veredictos.** Su salida es estructurada. Nunca «esto es un
   retroceso».
4. **Gate humano obligatorio** antes de emitir cualquier alerta. Sin excepción, sin flag que lo
   salte.
5. **Minimización de datos.** Los suscriptores son dato sensible (revelan afinidad al colectivo).
6. **Nada de scope creep.** Ver «Fuera de alcance».
7. **Todo cambio de arquitectura → un ADR** en `docs/adr/NNNN-titulo.md`. El siguiente libre es el
   **0028**.
8. **Nunca inventes fuentes, plazos ni artículos legales.** Si no lo has verificado, márcalo como
   `TODO(verificar)` y avisa.
9. **Trazabilidad por offsets.** Todo hecho extraído por el LLM apunta a un rango de caracteres del
   texto archivado. Si no ancla, se descarta la extracción entera.
10. **Nada que emita el modelo acciona nada.** Su salida es dato, nunca una URL que se descargue,
    una ruta que se abra, un comando que se ejecute ni una consulta que se interpole.

## Seguridad: lo que no se toca

- **XML: `defusedxml` siempre**, vía la puerta única `security/xml_safe.py`. Prohibido `xml.etree`
  o `lxml` sin endurecer. Entidades externas OFF, DTD OFF, red OFF.
- **HTTP saliente: solo por `security/url_guard.py`** (allowlist de dominios, rechazo de IPs
  privadas/loopback, sin redirecciones fuera de la allowlist, timeouts, límite de bytes). La única
  excepción declarada es la URL local de Ollama (ADR 0006).
- **PDF: solo por `security/pdf_safe.py`** (ADR 0026), con sus tres topes.
- **LLM: solo por `llm/`.** Ningún otro módulo habla con Ollama ni conoce su URL.
- **Path traversal**: los nombres de fichero se derivan del `sha256`, nunca de un valor de la
  fuente.
- **Secretos solo por entorno.** `.env` está en `.gitignore` y **no debe entrar en tu contexto**:
  contiene la credencial del panel de revisión.
- **No se registran IPs** de quien consulta la web ni el feed. Los logs cubren qué normas se
  revisaron, nunca quién leyó qué. **No se guarda quién revisa.**
- Al descartar una extracción se registran los **campos** que fallan, **nunca lo que devolvió el
  modelo**.

## Fuera de alcance (guardarraíles)

Si te encuentras haciendo esto, para:

- Monitorización de prensa o redes sociales.
- Publicación automática sin gate humano.
- Almacenar el veredicto del LLM como si fuera la clasificación.
- Celery, colas distribuidas, microservicios. Un worker cron idempotente basta.
- Eje semántico por embeddings (hueco reservado, no implementar).
- **Fine-tuning, RAG o cambiar de modelo buscando calidad.** Antes de tocar el modelo hay que poder
  medir, y medir es el gold set. Sin él, un cambio de modelo es una opinión.
- OCR: la prohibición se levantó, pero **antes de escribir una línea hay que demostrar con un
  documento real que su PDF no tiene capa de texto**, y llevarlo a un ADR.
- Ninguna rama entra en `main` sin que **la autorice** una persona. Comprobarla es trabajo tuyo:
  el resultado del **merge** (no la rama) en un **clon limpio**, con la puerta entera del CI. Y
  luego pides permiso y esperas — nunca mergees por iniciativa propia, aunque salga todo verde.

## Coste y autonomía

- **Elige siempre la opción de coste 0 €** y la que exija menos cosas que conseguir (claves,
  cuentas, servicios de terceros, instalaciones).
- **Decide tú cualquier cosa reversible** y cuéntalo al terminar. Autonomía no es silencio: es no
  interrumpir.
- **Para y pregunta solo en cuatro casos:** cuesta dinero; hace falta una credencial o cuenta que
  no existe; es una acción externa e irreversible (publicar en redes, contactar con asociaciones,
  subir el repo); o contradice `docs/CLAUDE.md`.
- Si te falta un dato, **mira antes de preguntar** (el repo, la máquina, la API real).

## El pipeline, en corto

```
[1] Sumario → prefiltro sobre el título: SOLO prioriza, nunca descarta
[2] Texto íntegro de TODOS los items del día, sin umbral (ADR 0011)
    → [3] Prefiltro 3 ejes sobre el texto completo ──descartada──> fin
    → [4] Extractor LLM (hechos + offsets)  → [5] Clasificador por reglas  → [6] Gate humano
```

- **El descarte definitivo solo ocurre tras leer el documento completo.** Nunca sobre el título: es
  exactamente lo que un retroceso silencioso puede redactar de forma anodina.
- `prefiltro_estado` tiene **cinco** valores: `pendiente`, `sospecha`, `relevante`, `descartada`,
  `ilegible`. `pendiente` ≠ `descartada`. `ilegible` (ADR 0020) se cuenta **aparte y aunque sea
  cero**: cualquier cifra de cobertura va acompañada de cuántas normas son ilegibles.
- **Los tres ejes del prefiltro se combinan con OR, jamás con AND.**
- Las reglas del clasificador leen **el texto archivado**, no la salida del modelo, y cada veredicto
  emite `regla_aplicada` + spans de evidencia.
- **Antes de escribir una familia de reglas nueva, mídela sobre el corpus archivado** (ADR 0027).
  No cuesta ni una petición de red y ya evitó escribir una regla que aportaba cero.

## Versiones que obligan a reevaluar

`VERSION_VOCABULARIO`, `VERSION_WATCHLIST`, `VERSION_TEXTO_PLANO`, `VERSION_REGLAS`. Si tocas lo que
cubren, **súbelas**, o lo anterior no se reevalúa y el cambio solo afecta al futuro.

## Git y flujo

- **Conventional commits** (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `sec:`).
  Mensajes en **español**; código e identificadores en **inglés**.
- **Una rama por feature**, nunca commitear directo a `main`.
- **Nunca `alembic upgrade` desatendido.** El autogenerate ha propuesto borrar CHECKs ajenas cinco
  veces. Las migraciones las revisa una persona, siempre.
- **Parada al primer rojo.** No sigas construyendo sobre tests rotos.
- Al cerrar un trabajo, **actualiza `docs/ESTADO.md`** (no `docs/CLAUDE.md`, que son las reglas).

## Comandos

```bash
docker compose up --build                      # todo: db, backend, worker, web (5174)
ruff check . && ruff format --check . && mypy backend/app && pytest --cov   # lo que corre el CI
python -m worker.run --fuente boe --fecha 2024-12-19   # ingesta de un día
python -m worker.run --reprefiltrar            # tras subir VERSION_VOCABULARIO o _WATCHLIST
python -m worker.run --fase2                   # drenar cuerpos que falten
python -m worker.run --extraer                 # cola del LLM (133,9 s por norma: lánzalo y déjalo)
python -m worker.run --reclasificar            # tras subir VERSION_REGLAS
```

Tras cualquier `alembic upgrade`, comprobar que siguen vivas las CHECK:

```bash
psql -c "SELECT conrelid::regclass, conname FROM pg_constraint
         WHERE contype='c' AND conrelid <> 0 ORDER BY 1,2"
```

## Notas para agentes que no sean Claude Code

- Los subagentes de `.claude/agents/` (`jurista-lgtbi`, `revisor-seguridad`, `auditor-reglas`,
  `evaluador`) **son específicos de Claude Code y no funcionan aquí**. Sus criterios están
  documentados en la sección 13.4, que desde el 2026-08-30 vive en `docs/TRABAJO.md`.
- Si existe un `GEMINI.md` en la raíz, **tendrá precedencia sobre este fichero**. No crees uno sin
  saberlo: tener dos ficheros de reglas que se contradicen es peor que no tener ninguno.
