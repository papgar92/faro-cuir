# Faro Cuir

**Vigilancia normativa de los derechos LGTBI+ en España.** Lee cada día el BOE buscando los
cambios que afectan al colectivo —con atención especial a las personas trans—, archiva cada
documento con su huella digital y publica **qué decía un artículo antes y qué dice ahora**, con
el enlace a la fuente oficial para que cualquiera lo compruebe sin fiarse de nosotros.

> El Rainbow Map de ILGA-Europe, pero por comunidad autónoma y en tiempo real.

Está pensado para detectar el **retroceso silencioso**: no la reforma que sale en prensa, sino la
instrucción de rango bajo publicada un martes de agosto que desmonta un derecho sin titulares.
El caso que mejor lo explica está en el sistema: la reforma madrileña de 2023 reescribió el
artículo 4 de la Ley 2/2016, que pasó de «Reconocimiento del **derecho a la identidad de género
libremente manifestada**» a «Reconocimiento del **respeto a la libertad y dignidad de las
personas transexuales**». El precepto sigue ahí, numerado igual. Solo se ve comparando.

## Tres reglas que definen lo que este sistema hace y lo que no

1. **No opina.** La clasificación entre avance y retroceso se deriva del propio texto con reglas
   escritas y auditables ([`docs/adr/0016`](docs/adr/0016-como-se-representa-una-supresion-sin-texto.md)),
   nunca del criterio de un modelo de lenguaje. El LLM extrae hechos con trazabilidad; no dicta
   veredictos ([`docs/adr/0002`](docs/adr/0002-el-llm-extrae-no-juzga.md)).
2. **Ninguna alerta se publica sin que una persona la revise** antes
   ([`docs/adr/0003`](docs/adr/0003-gate-humano-obligatorio.md) y
   [`0017`](docs/adr/0017-autenticacion-del-panel-de-revision.md)). No hay opción de saltarlo.
3. **No sabe quién lo lee.** El canal de difusión por defecto es un feed Atom sin registro: sin
   lista de suscriptores, porque estar en una lista de alertas sobre derechos trans ya dice algo
   de ti ([`docs/adr/0010`](docs/adr/0010-canal-pull-primero.md)).

## Documentación

Es un proyecto de máster de Ciberseguridad e IA, así que el porqué de cada decisión está escrito
y es parte del entregable:

| Documento | Qué contiene |
|---|---|
| [`docs/adr/`](docs/adr/) | **17 decisiones de arquitectura**, cada una con su contexto, sus alternativas descartadas y sus consecuencias. |
| [`THREAT-MODEL.md`](THREAT-MODEL.md) | Modelo de amenazas **STRIDE por componente**, con cada control apuntando a su código y lo no mitigado escrito, no omitido. |
| [`docs/eipd.md`](docs/eipd.md) | Evaluación de impacto en protección de datos. Su conclusión: el tratamiento de riesgo alto **se eliminó cambiando el canal**, no se mitigó. |
| [`SECURITY.md`](SECURITY.md) | Política de seguridad y estado de cada control. |
| [`docs/fuentes.md`](docs/fuentes.md) | Auditoría de las fuentes: BOE, 17 boletines autonómicos y los **43 Boletines Oficiales de la Provincia** ([ADR 0014](docs/adr/0014-la-capa-local-entra-en-alcance-via-bop.md)). |
| [`docs/CLAUDE.md`](docs/CLAUDE.md) | Las reglas del proyecto: requisitos de seguridad, diseño del pipeline y guardarraíles de alcance. |
| [`docs/ESTADO.md`](docs/ESTADO.md) | El diario de decisiones, con lo medido, lo verificado y los errores encontrados por el camino. |

## Cómo está construido

```
BOE (sumario del día)
  └─> fase 1: se ingiere y se archiva con sha256 + sello de tiempo
      └─> fase 2: se descarga el texto íntegro de TODAS las normas del día, sin umbral (ADR 0011)
          └─> prefiltro de dos ejes: léxico + referencial sobre la watchlist (ADR 0012)
              └─> extractor LLM local, sin clave ni coste (ADR 0008) — extrae hechos, no juicios
                  └─> catálogo de reglas sobre el texto archivado (ADR 0016)
                      └─> versionado: el texto anterior, desde el consolidado del BOE (ADR 0018)
                          └─> GATE HUMANO (regla de oro 4)
                              └─> web pública + feed Atom (ADR 0010)
```

- **Backend**: Python 3.12, FastAPI, PostgreSQL 16, SQLAlchemy, Alembic.
- **Frontend**: React 18, TypeScript, Vite, TailwindCSS. Mapa proyectado desde geometría del IGN.
- **LLM**: local con Ollama. Sin clave de API, sin coste y sin que ningún texto salga a un
  tercero ([ADR 0008](docs/adr/0008-proveedor-llm-local-sin-clave.md)).
- **Todo el HTTP saliente pasa por una puerta única** con allowlist, validación de IP y pin
  contra DNS rebinding ([ADR 0006](docs/adr/0006-puerta-unica-de-salida-http.md)); todo el XML,
  por otra con XXE y bombas de entidades desactivadas.

## Arranque rápido

```bash
cp .env.example .env        # y rellena las variables; NUNCA subas tu .env
docker compose up --build

# Ingesta de un día concreto
docker compose exec worker python -m worker.run --fuente boe --fecha 2024-12-19

# Frontend en desarrollo
cd frontend && npm run dev
```

El resto de comandos, en la sección 10 de [`docs/CLAUDE.md`](docs/CLAUDE.md).

## Estado

En desarrollo activo. El pipeline funciona de punta a punta sobre el BOE —ingesta, archivo con
huella, prefiltro, extracción, clasificación por reglas, gate humano y difusión— con **508 tests**
y análisis estático estricto en CI.

**Lo que todavía no está, dicho sin maquillar**: el corpus de evaluación tiene 32 documentos
etiquetados y necesita bastantes más para que cualquier cifra de cobertura signifique algo, así
que **este proyecto no publica ningún porcentaje de recall**; y de las 61 fuentes documentadas
hay **tres integradas** —BOE, DOGC y BOA (ADR 0019 y 0028)—, así que el mapa pinta con trama los
16 territorios donde todavía no mira nadie. El detalle honesto de cada hueco está en
[`docs/ESTADO.md`](docs/ESTADO.md).

## Aviso

Faro Cuir publica cambios normativos y su evidencia. **No es asesoramiento jurídico** ni
sustituye la lectura del boletín oficial, y sus clasificaciones son el resultado de reglas
públicas revisadas por una persona, no un dictamen.

## Licencia

[AGPL-3.0](LICENSE). Es copyleft de red a propósito: si alguien despliega una versión modificada
como servicio, el código de esa versión tiene que seguir siendo público. Una herramienta de
vigilancia de derechos que se pueda cerrar en una caja privada deja de servir para lo que existe.
