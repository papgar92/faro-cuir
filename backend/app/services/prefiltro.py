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
from app.pipeline import prefiltro, watchlist


@dataclass(frozen=True)
class ResumenPrefiltro:
    """El embudo, que es lo que hay que poder enseñar de esta etapa."""

    evaluadas: int
    relevantes: int
    # Escalón nuevo del embudo (7.2). **No son descartes**: entran en la cola del extractor,
    # las últimas. Contarlas aparte es lo que permite ver si el umbral léxico está mandando
    # media ingesta al final de la cola.
    sospechas: int
    descartadas: int
    # Ni descartadas ni en cola: evaluadas solo sobre el título y a la espera del texto
    # íntegro. Sobre el sumario no se descarta nunca (7.1).
    pendientes: int
    # De las que pasan, cuántas lo hicieron solo por términos genéricos. Mide el ruido que
    # aporta la lista de contexto, y por tanto qué se puede afinar sin tocar el recall de los
    # términos directos.
    solo_por_contexto: int
    # Cuántas disparó cada eje. Un eje que no dispara nunca es un eje que sobra; uno que
    # dispara siempre es uno que no filtra. Sin esto no se puede afinar uno sin tocar el otro.
    por_eje: dict[str, int]


def _pendientes(documento_id: int | None, forzar: bool):  # type: ignore[no-untyped-def]
    """Normas que hay que (re)evaluar.

    Se incluyen las que se evaluaron con un vocabulario anterior, no solo las que nunca se han
    mirado. Ese es el motivo de guardar la versión: cuando se añade un término al diccionario,
    las normas ya descartadas con el viejo tienen que volver a pasar, o el término nuevo solo
    protegería a las normas futuras.

    **"Hay que evaluarla" se pregunta por `prefiltro_evaluado_en` y por la versión, NO por el
    estado.** Antes se preguntaba por `estado == PENDIENTE`, y eso dejó de valer con 7.1: sobre
    el título solo ya no se descarta nunca, así que una norma sin coincidencias se queda en
    `PENDIENTE` esperando su texto íntegro. Con la condición vieja, esas normas se reevaluaban
    enteras en cada pasada — no habría reventado nada, que es lo peligroso: simplemente el
    worker habría dejado de ser idempotente y nadie se habría enterado hasta ver la segunda
    pasada procesando 436 normas en vez de 0.

    `PENDIENTE` es ahora un estado de **espera** (falta el documento), no de **cola de
    trabajo** de esta etapa. Son dos preguntas distintas y ahora las contestan dos columnas
    distintas.
    """
    consulta = select(Norma)
    if documento_id is not None:
        consulta = consulta.where(Norma.documento_id == documento_id)
    if not forzar:
        consulta = consulta.where(
            or_(
                Norma.prefiltro_evaluado_en.is_(None),
                Norma.prefiltro_version.is_(None),
                Norma.prefiltro_version != prefiltro.VERSION_VOCABULARIO,
                # La watchlist se versiona aparte: subirla obliga a reevaluar igual que subir
                # el vocabulario (7.3), y sin esta condición un cambio en la watchlist solo
                # afectaría a las normas futuras.
                Norma.prefiltro_version_watchlist.is_(None),
                Norma.prefiltro_version_watchlist != watchlist.watchlist().version,
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
    relevantes = sospechas = descartadas = pendientes = solo_contexto = 0
    por_eje: dict[str, int] = {}

    # La watchlist se carga **una vez por pasada**, no por norma: son cientos de normas y el
    # fichero no cambia a mitad de ejecución. Que falte es un error ruidoso a propósito (ver
    # `watchlist.WatchlistNoDisponible`): una watchlist vacía no rompe nada, solo apaga en
    # silencio el único eje que detecta la instrucción que no se nombra.
    lista = watchlist.watchlist()

    normas = list(session.scalars(_pendientes(documento_id, forzar)))
    for norma in normas:
        # Sin texto íntegro todavía: esta etapa corre sobre el sumario. Cuando el worker
        # descargue el día entero (tarea 0.c, ADR 0011) aquí entrarán `texto_integro` y las
        # `referencias` del bloque <analisis>, y el resto de esta función no cambia.
        resultado = prefiltro.evaluar(norma.titulo, organo_emisor=norma.organo_emisor, lista=lista)

        norma.prefiltro_estado = resultado.estado
        # Lista vacía y no NULL cuando no hay términos: NULL significaría "no evaluado", que
        # es otra cosa. Misma distinción que la del estado PENDIENTE.
        norma.prefiltro_terminos = list(resultado.terminos)
        norma.prefiltro_ejes = [eje.value for eje in resultado.ejes]
        norma.prefiltro_directos = resultado.directos
        norma.prefiltro_version = resultado.version
        norma.prefiltro_version_watchlist = resultado.version_watchlist
        norma.prefiltro_evaluado_en = ahora

        for eje in resultado.ejes:
            por_eje[eje.value] = por_eje.get(eje.value, 0) + 1

        if resultado.estado is EstadoPrefiltro.RELEVANTE:
            relevantes += 1
        elif resultado.estado is EstadoPrefiltro.SOSPECHA:
            sospechas += 1
        elif resultado.estado is EstadoPrefiltro.PENDIENTE:
            pendientes += 1
        else:
            descartadas += 1

        if resultado.entra_en_la_cola and resultado.solo_por_contexto:
            solo_contexto += 1

    session.commit()

    return ResumenPrefiltro(
        evaluadas=len(normas),
        relevantes=relevantes,
        sospechas=sospechas,
        descartadas=descartadas,
        pendientes=pendientes,
        solo_por_contexto=solo_contexto,
        por_eje=por_eje,
    )
