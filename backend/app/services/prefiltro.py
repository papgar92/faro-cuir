"""Aplica el prefiltro léxico a las normas guardadas y persiste el resultado.

Separado de `pipeline/prefiltro.py` con el mismo criterio que `ingesta.py` frente a
`ingest/boe.py`: allí vive la decisión (qué es relevante), aquí vive lo que la decisión hace
en la base de datos. Así el filtro se puede razonar y testear sin una sesión abierta.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.norma import EstadoPrefiltro, Norma
from app.pipeline import prefiltro


@dataclass(frozen=True)
class ResumenPrefiltro:
    """El embudo, que es lo que hay que poder enseñar de esta etapa."""

    evaluadas: int
    relevantes: int
    descartadas: int
    # De las relevantes, cuántas pasaron solo por términos genéricos. Es la medida del ruido
    # que aporta la lista de contexto, y por tanto lo único que se puede afinar sin tocar el
    # recall de los términos directos.
    solo_por_contexto: int


def _pendientes(documento_id: int | None, forzar: bool):  # type: ignore[no-untyped-def]
    """Normas que hay que (re)evaluar.

    Se incluyen las que se evaluaron con un vocabulario anterior, no solo las que nunca se
    han mirado. Ese es justamente el motivo de guardar la versión: cuando se añade un término
    al diccionario, las normas ya descartadas con el diccionario viejo tienen que volver a
    pasar, o el término nuevo solo protegería a las normas futuras.
    """
    consulta = select(Norma)
    if documento_id is not None:
        consulta = consulta.where(Norma.documento_id == documento_id)
    if not forzar:
        consulta = consulta.where(
            or_(
                Norma.prefiltro_estado == EstadoPrefiltro.PENDIENTE,
                Norma.prefiltro_version.is_(None),
                Norma.prefiltro_version != prefiltro.VERSION_VOCABULARIO,
            )
        )
    return consulta.order_by(Norma.id)


def aplicar(
    session: Session,
    *,
    documento_id: int | None = None,
    forzar: bool = False,
) -> ResumenPrefiltro:
    """Evalúa y persiste. Idempotente: repetirlo sobre lo mismo no cambia nada.

    `documento_id=None` barre toda la tabla; es lo que hay que lanzar tras subir
    `VERSION_VOCABULARIO`.
    """
    ahora = datetime.datetime.now(datetime.UTC)
    relevantes = descartadas = solo_contexto = 0

    normas = list(session.scalars(_pendientes(documento_id, forzar)))
    for norma in normas:
        resultado = prefiltro.evaluar(norma.titulo, organo_emisor=norma.organo_emisor)

        norma.prefiltro_estado = resultado.estado
        # Lista vacía y no NULL cuando se descarta: NULL significaría "no evaluado", que es
        # otra cosa. La distinción es la misma que la del estado PENDIENTE.
        norma.prefiltro_terminos = list(resultado.terminos)
        norma.prefiltro_version = resultado.version
        norma.prefiltro_evaluado_en = ahora

        if resultado.relevante:
            relevantes += 1
            if resultado.solo_por_contexto:
                solo_contexto += 1
        else:
            descartadas += 1

    session.commit()

    return ResumenPrefiltro(
        evaluadas=len(normas),
        relevantes=relevantes,
        descartadas=descartadas,
        solo_por_contexto=solo_contexto,
    )
