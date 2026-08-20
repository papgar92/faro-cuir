"""Etapa 6 del pipeline: el gate humano. Regla de oro 4, ADR 0003 y 0017.

Es la etapa que convierte una clasificación en algo publicable, y la única del pipeline cuya
decisión no la toma el código. Aquí vive lo que esa decisión hace en la base de datos; la
autenticación de quien la toma está en `security/panel.py` y la interfaz en `api/revision.py`.

## Qué entra en la cola, y por qué no todo

Solo las detecciones **con veredicto**: `regla_aplicada IS NOT NULL`. Las que dejó el extractor
son el centinela del ADR 0009 (`indeterminado` / `heuristica` / `regla_aplicada` a NULL) y no
son un veredicto que nadie haya emitido — encolarlas sería pedirle a una persona que apruebe la
ausencia de conclusión, y llenaría la cola de ruido hasta que dejara de mirarse, que es la forma
habitual en la que un gate humano se vacía por dentro sin que nadie lo desactive.

`indeterminado` **sí entra** cuando lo produce una regla (R-SUP-002, R-DER-001): ahí el catálogo
sí ha dicho algo — «esto es una supresión / una derogación y no sé de qué signo» — y es
exactamente el umbral de recall alto de 7.6, cuyo destino declarado es la cola de revisión.

## Qué pasa al resolver

- **Aprobar** crea la fila de `alerta`. Que exista una fila ahí significa que una persona la
  aprobó: no hay ningún otro camino hasta esa tabla, ni flag que lo salte (regla de oro 4).
- **Descartar** no crea nada. La detección se queda con su veredicto y su evidencia, marcada
  como revisada: el rastro de auditoría no se borra, igual que un veredicto obsoleto no se
  retira solo (ver `services/clasificacion.py`).
- **Una vez resuelto, no se vuelve a resolver.** Reabrir un ítem sería poder emitir dos veces la
  misma alerta o retirar una ya emitida sin dejar constancia. Si hiciera falta rectificar, eso
  es una decisión con su propio rastro y no un segundo `POST` al mismo sitio.

## Qué no se guarda

Quién revisó. `cola_revision` tiene `nota_revision` y no tiene autor, y es deliberado (6.4): para
auditar el gate basta con saber que se resolvió, cuándo y con qué nota. Almacenar qué persona
aprueba qué alerta sobre derechos trans crea un dato personal sensible que este proyecto no
necesita.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.deteccion import (
    Alerta,
    Clasificacion,
    ColaRevision,
    Deteccion,
    EstadoRevision,
)

logger = logging.getLogger(__name__)

# Tope de longitud de la nota de revisión. La escribe una persona autenticada, así que no es
# entrada hostil en el sentido de la sección 6, pero un campo de texto sin tope es un campo de
# texto sin tope.
MAX_NOTA = 2000


class RevisionError(RuntimeError):
    """Error de uso del gate. Se traduce a 4xx en la API, nunca a un 500."""


class ItemNoEncontrado(RevisionError):
    pass


class YaResuelta(RevisionError):
    """El ítem ya se aprobó o se descartó. No se reabre; ver la cabecera del módulo."""


@dataclass(frozen=True)
class ResumenEncolado:
    """Qué encontró esta pasada. `candidatas` incluye las que ya estaban en cola."""

    candidatas: int
    encoladas: int


def _identifica_norma_vigilada(evidencia: object) -> bool:
    """¿El veredicto señala algo concreto del ámbito: una norma vigilada **o un órgano**?

    La segunda puerta la abre el ADR 0024 y cubre un caso que la primera dejaba fuera: «se
    suprime el Consejo LGTBI de Aragón» no nombra ninguna norma de la watchlist —ese consejo lo
    creó un decreto que no está en ella— así que la detección se creaba y **moría sin que nadie
    la mirase**. Desaparece quien vigila la ley, y era invisible.

    Sigue sin ser la puerta ancha que el ADR 0017 cerró: R-SUP-003 exige término directo **y**
    nombre de órgano en la misma cláusula. Medido antes de abrirla: de las 10 detecciones de
    R-SUP-002 del corpus, **cero** la cruzan.

    Se lee de `evidencia_json.normas_vigiladas` y **no de una lista de reglas escrita a mano**:
    así, una regla futura que identifique una norma vigilada entra en la cola sola, y una de
    recall alto se queda fuera sola. Una lista de identificadores habría que acordarse de
    mantenerla, y el día que no se mantenga el fallo es silencioso.
    """
    if not isinstance(evidencia, dict):
        return False
    for clave in ("normas_vigiladas", "organos_afectados"):
        senalado = evidencia.get(clave)
        if isinstance(senalado, list) and len(senalado) > 0:
            return True
    return False


def encolar(session: Session) -> ResumenEncolado:
    """Mete en la cola de revisión toda detección con veredicto **que señale una norma vigilada**.

    Idempotente por construcción: la unicidad de `cola_revision.deteccion_id` es la garantía en
    la base de datos, y la consulta ya excluye lo encolado. Se puede llamar en cada pasada del
    worker sin duplicar nada, y por eso mismo se llama justo después del clasificador: una
    detección clasificada que no está en ninguna cola es una detección que nadie va a mirar.

    **No commitea.** Lo hace quien lo llama, para que encolar y clasificar quepan en la misma
    transacción y no exista un instante con veredictos fuera de la cola.

    ## Por qué no entra todo lo que tiene veredicto (2026-08-17, con datos)

    Entraba, y la cola se llenó de ruido. Los números de las primeras 13 revisiones reales:

    | regla | qué exige | resultado |
    |---|---|---|
    | R-SUP-001 | supresión **en una norma de la watchlist** | 2 de 2 aprobadas |
    | R-DER-001 | derogación de una norma vigilada | 1 de 1 aprobada |
    | R-SUP-002 | supresión **sin** norma vigilada | **10 de 10 descartadas** |

    R-SUP-002 dispara con cualquier «se suprime el artículo 7» de cualquier materia —pesca,
    puertos, subvenciones agrarias— siempre que el prefiltro haya dejado pasar la norma por una
    mención suelta. Quien revisa abría la norma, la leía entera buscando el recorte y no lo
    encontraba, porque no lo había.

    **Eso no es un inconveniente, es el mecanismo por el que un gate humano se vacía por
    dentro.** Lo dice la propia 7.7 sobre el centinela del ADR 0009: pedirle a una persona que
    apruebe la ausencia de conclusión llena la cola de ruido hasta que deja de mirarse, y
    entonces la revisión sigue existiendo en el organigrama y no en la práctica.

    **Qué NO se hace, y es importante:** no se borra la detección ni se pierde recall. R-SUP-002
    sigue produciendo su fila, con su regla y sus spans, consultable y contable; lo único que
    cambia es que no se le pide a una persona que la valide. Si mañana la watchlist crece y esa
    norma pasa a señalar algo vigilado, la reclasificación la encola sola.
    """
    encoladas = candidatas = 0
    for deteccion_id, cola_id, evidencia in session.execute(
        select(Deteccion.id, ColaRevision.id, Deteccion.evidencia_json)
        .outerjoin(ColaRevision, ColaRevision.deteccion_id == Deteccion.id)
        .where(Deteccion.regla_aplicada.is_not(None))
        .order_by(Deteccion.id)
    ):
        if not _identifica_norma_vigilada(evidencia):
            continue
        candidatas += 1
        if cola_id is None:
            session.add(ColaRevision(deteccion_id=deteccion_id, estado=EstadoRevision.PENDIENTE))
            encoladas += 1
    return ResumenEncolado(candidatas=candidatas, encoladas=encoladas)


def _resolver(
    session: Session,
    cola_id: int,
    *,
    estado: EstadoRevision,
    nota: str | None,
) -> ColaRevision:
    # `with_for_update`: sin él, dos POST simultáneos sobre el mismo ítem (dos pestañas, un
    # doble clic) leen los dos `pendiente` y los dos siguen adelante. La unicidad de
    # `alerta.deteccion_id` impide que salgan dos alertas —el control aguanta— pero a costa de
    # un error de integridad, y una comprobación que solo funciona porque la base de datos la
    # rescata no es una comprobación. En SQLite (los tests) el dialecto lo ignora sin fallar.
    item = session.get(ColaRevision, cola_id, with_for_update=True)
    if item is None:
        raise ItemNoEncontrado(f"No hay ningún ítem de revisión con id {cola_id}.")
    if item.estado is not EstadoRevision.PENDIENTE:
        raise YaResuelta(
            f"El ítem {cola_id} ya está en estado {item.estado.value}; el gate no se reabre."
        )
    if nota is not None and len(nota) > MAX_NOTA:
        raise RevisionError(f"La nota de revisión excede {MAX_NOTA} caracteres.")

    item.estado = estado
    item.resuelta_en = datetime.datetime.now(datetime.UTC)
    item.nota_revision = nota or None

    deteccion = session.get(Deteccion, item.deteccion_id)
    if deteccion is None:  # pragma: no cover - la FK con ondelete=RESTRICT lo impide
        raise ItemNoEncontrado(f"El ítem {cola_id} apunta a una detección que no existe.")
    deteccion.revisada = True
    return item


def aprobar(
    session: Session,
    cola_id: int,
    *,
    nota: str | None = None,
    clasificacion: str | None = None,
) -> Alerta:
    """Aprueba un ítem y **emite** la alerta. Es el único sitio del código que escribe en `alerta`.

    El log dice qué se aprobó y con qué regla, nunca quién ni con qué nota: lo primero es
    trazabilidad del sistema y lo segundo sería un dato de la persona que revisa.

    `clasificacion` es **el signo que fija la persona**, y es opcional. Lo pidió el humano con el
    caso que lo justifica: la Ley 4/2023 sale como «sin signo» porque R-DER-001 se abstiene a
    propósito —derogar es lo que hace tanto quien desmonta una ley como quien la sustituye por
    otra mejor— y quien lee el texto sabe perfectamente que es un avance.

    **No sobrescribe `deteccion.clasificacion`.** Aquella es lo que derivó una regla auditable del
    archivo; esta es lo que decidió una persona. Se guardan por separado porque son dos fuentes
    de autoridad distintas, y mezclarlas rompería la propiedad que sostiene el proyecto: que un
    tercero pueda reconstruir el veredicto de la regla leyendo la regla (7.6).
    """
    item = _resolver(session, cola_id, estado=EstadoRevision.APROBADA, nota=nota)
    if clasificacion is not None:
        item.clasificacion_humana = Clasificacion(clasificacion)
    alerta = Alerta(deteccion_id=item.deteccion_id)
    session.add(alerta)
    session.commit()
    logger.info(
        "Gate humano: aprobada la revisión %s (detección %s). Alerta emitida.",
        item.id,
        item.deteccion_id,
    )
    return alerta


def descartar(session: Session, cola_id: int, *, nota: str | None = None) -> ColaRevision:
    """Descarta un ítem. No crea alerta y no borra la detección: el rastro se conserva."""
    item = _resolver(session, cola_id, estado=EstadoRevision.DESCARTADA, nota=nota)
    session.commit()
    logger.info(
        "Gate humano: descartada la revisión %s (detección %s). No se emite alerta.",
        item.id,
        item.deteccion_id,
    )
    return item
