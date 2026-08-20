"""Mete en la base los informes de apoyo que un asistente de IA prepara fuera. ADR 0025.

**Por qué entra por un fichero y no por una llamada al modelo**, que es la pregunta obvia y tiene
una respuesta medida: el único modelo que el proyecto puede permitirse es el Ollama local de 3B
(ADR 0008, coste 0 €), y su rendimiento sobre este corpus está medido y no da para esto — 36 % de
timeouts a 180 s y la mitad de las respuestas sin anclar al archivo (ESTADO, 2026-08-18). Un panel
que dijera «análisis del asistente» con ese modelo detrás prometería algo que el sistema desplegado
no hace, que es exactamente lo que este proyecto se dedica a no hacer.

Así que la generación vive fuera —hoy, una sesión de Claude Code con el subagente `jurista-lgtbi`—
y **el sistema solo guarda y enseña, diciendo de dónde viene**. El día que haya un modelo local
capaz, lo único que cambia es quién escribe el JSON.

## Lo que este servicio NO hace, y es su razón de ser

- **No toca `deteccion`.** Ni la clasificación, ni la severidad, ni la evidencia. Si borraras la
  tabla entera de informes, ninguna alerta cambiaría de signo. Es el ADR 0004 intacto.
- **No resuelve nada de la cola.** `estado` sigue siendo `pendiente` hasta que una persona decida.
  Un informe es material de lectura, no una decisión.
- **No acepta un informe sin `refutacion`.** Sin «qué me refutaría», la recomendación funciona
  como un sello de goma: quien revisa lee el color y confirma. El esquema lo impide con NOT NULL
  y aquí se rechaza antes, con un mensaje que dice por qué.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.deteccion import ColaRevision, Deteccion, InformeRevision, Semaforo
from app.models.norma import Norma

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResumenImportacion:
    """Qué entró y qué no. `sin_item` no se omite: es el caso que más despista.

    Un informe cuyo identificador no está en la cola casi nunca es un error de dedo — suele ser
    que la norma se resolvió entre que se generó el informe y se importó, o que se escribió
    sobre una norma que nunca llegó al gate. Contarlo aparte evita leer "3 importados" como
    "los 5 están dentro".
    """

    leidos: int
    importados: int
    sustituidos: int
    sin_item: int
    invalidos: int


def _item_de(session: Session, identificador: str) -> ColaRevision | None:
    return session.scalar(
        select(ColaRevision)
        .join(Deteccion, Deteccion.id == ColaRevision.deteccion_id)
        .join(Norma, Norma.id == Deteccion.norma_id)
        .where(Norma.identificador_oficial == identificador)
    )


def importar(session: Session, ruta: Path, *, generado_por: str) -> ResumenImportacion:
    """Lee un JSON con una lista de informes y los guarda.

    Formato de cada entrada, y los cinco primeros campos son obligatorios::

        {
          "identificador_oficial": "BOE-A-2014-11444",
          "semaforo": "alerta" | "mirar" | "descartar",
          "resumen": "qué hace la norma, en una frase y sin jerga",
          "recomendacion": "qué haría el asistente y por qué",
          "refutacion": "qué tendría que ver quien revisa para decidir lo contrario",
          "a_quien_afecta": "opcional",
          "citas": [{"texto": "…", "apartado": "5.3.8.1.a)", "version": "nueva"}],
          "corroboraciones": [{"organizacion": "Amnistía Internacional",
                               "que_dice": "…", "url": "https://…"}]
        }

    Reimportar sustituye el informe anterior del mismo ítem: esto es material de trabajo, no
    archivo, y a diferencia de `version_norma` **sí** se puede reescribir.
    """
    entradas = json.loads(ruta.read_text(encoding="utf-8"))
    leidos = importados = sustituidos = sin_item = invalidos = 0

    for entrada in entradas:
        leidos += 1
        identificador = str(entrada.get("identificador_oficial", "")).strip()
        try:
            semaforo = Semaforo(str(entrada.get("semaforo", "")).strip())
        except ValueError:
            logger.warning("Informe de %s: semáforo no reconocido; se descarta.", identificador)
            invalidos += 1
            continue

        faltan = [c for c in ("resumen", "recomendacion", "refutacion") if not entrada.get(c)]
        if faltan:
            # `refutacion` es el que más importa y por eso el mensaje lo dice: un informe sin
            # ella convierte al gate humano en un trámite de confirmación.
            logger.warning(
                "Informe de %s: faltan %s; se descarta. Sin 'refutacion' un informe no se "
                "guarda, porque quien revisa tiene que poder llevarle la contraria.",
                identificador,
                ", ".join(faltan),
            )
            invalidos += 1
            continue

        item = _item_de(session, identificador)
        if item is None:
            logger.warning(
                "Informe de %s: no hay ítem en la cola de revisión con esa norma. ¿Se resolvió "
                "ya, o nunca llegó al gate?",
                identificador,
            )
            sin_item += 1
            continue

        informe = session.scalar(
            select(InformeRevision).where(InformeRevision.cola_revision_id == item.id)
        )
        if informe is None:
            informe = InformeRevision(cola_revision_id=item.id)
            session.add(informe)
            importados += 1
        else:
            sustituidos += 1

        informe.semaforo = semaforo
        informe.resumen = str(entrada["resumen"])
        informe.a_quien_afecta = entrada.get("a_quien_afecta") or None
        informe.recomendacion = str(entrada["recomendacion"])
        informe.refutacion = str(entrada["refutacion"])
        informe.citas = list(entrada.get("citas") or [])
        informe.corroboraciones = list(entrada.get("corroboraciones") or [])
        informe.generado_por = generado_por

    session.commit()
    return ResumenImportacion(
        leidos=leidos,
        importados=importados,
        sustituidos=sustituidos,
        sin_item=sin_item,
        invalidos=invalidos,
    )
