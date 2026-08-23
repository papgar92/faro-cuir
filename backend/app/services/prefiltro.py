"""Aplica el prefiltro léxico a las normas guardadas y persiste el resultado.

Separado de `pipeline/prefiltro.py` con el mismo criterio que `ingesta.py` frente a
`ingest/boe.py`: allí vive la decisión (qué es relevante), aquí vive lo que la decisión hace
en la base de datos. Así el filtro se puede razonar y testear sin una sesión abierta.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.norma import EstadoPrefiltro, Norma
from app.pipeline import prefiltro, watchlist
from app.pipeline.texto import VERSION_TEXTO_PLANO
from app.services.cuerpo import CuerpoIlegible, leer_cuerpo

logger = logging.getLogger(__name__)


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
    # Cuerpo archivado que el pipeline no puede parsear (ADR 0020). **No se puede omitir del
    # embudo aunque sea cero**: es la única cifra que dice cuánto de la cobertura que el sistema
    # aparenta es en realidad un hueco, y mientras vivió mezclada con `pendientes` nadie la vio
    # durante dos días con 172 normas del DOGC dentro.
    ilegibles: int
    # De las que pasan, cuántas lo hicieron solo por términos genéricos. Mide el ruido que
    # aporta la lista de contexto, y por tanto qué se puede afinar sin tocar el recall de los
    # términos directos.
    solo_por_contexto: int
    # Cuántas disparó cada eje. Un eje que no dispara nunca es un eje que sobra; uno que
    # dispara siempre es uno que no filtra. Sin esto no se puede afinar uno sin tocar el otro.
    por_eje: dict[str, int]
    # De las evaluadas, cuántas lo fueron sobre el **texto íntegro** y no solo sobre el título.
    # Va en el resumen y no solo en la columna porque es la salvedad que acompaña a cualquier
    # cifra de cobertura (7.8): sobre título no hay recall, hay límite superior. Un embudo que
    # no diga sobre qué se evaluó invita a leerlo como si fuera lo segundo.
    sobre_texto_integro: int


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

    **La condición que añade la fase 2 (ADR 0015) es la última, y sin ella el trabajo de
    descargar 436 cuerpos no serviría de nada**: una norma evaluada sobre el título tiene las
    mismas versiones de vocabulario y watchlist que una evaluada sobre el texto íntegro, así
    que sin mirar `prefiltro_version_texto` ninguna de las 435 `pendiente` volvería a
    evaluarse nunca. Se quedarían esperando un texto que ya está en el disco.
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
                # Hay cuerpo archivado y la evaluación guardada no se hizo sobre él, o se hizo
                # con otra versión de la derivación del texto.
                and_(
                    Norma.documento_texto_id.is_not(None),
                    or_(
                        Norma.prefiltro_version_texto.is_(None),
                        Norma.prefiltro_version_texto != VERSION_TEXTO_PLANO,
                    ),
                ),
            )
        )
    return consulta.order_by(Norma.id)


# Cuántas normas se confirman de una vez. No es un parámetro de rendimiento del motor: es el
# techo de trabajo que se pierde si esto se interrumpe. 500 son ~30 s de barrido.
LOTE = 500


def _por_lotes(session: Session, consulta, tam: int | None = None):  # type: ignore[no-untyped-def]
    """Recorre la consulta confirmando cada `tam` normas, en vez de todo al final.

    **Esto era un solo `commit()` al final del barrido, y con 436 normas estaba bien.** Con
    69.388 dejó de estarlo por dos motivos que se ven a escala y no antes: media hora de trabajo
    se perdía entera si alguien cortaba el proceso —no había confirmación parcial que rescatar—
    y desde fuera no había forma de saber si avanzaba o estaba colgado, porque la base de datos
    no cambiaba hasta el final. Un barrido que no se puede observar y no se puede reanudar es
    indistinguible de uno atascado.

    **Se pagina por `id` y no re-consultando el primer lote, y esa diferencia es la que evita un
    bucle infinito.** Una norma `ilegible` deja `prefiltro_version_texto` a NULL a propósito (ADR
    0020) para que la siguiente pasada vuelva a intentarla, así que **nunca deja de cumplir la
    condición de `_pendientes`**: pedir repetidamente "las primeras que falten" devolvería las
    mismas 102 para siempre. Avanzar por `id` recorre cada norma una vez y deja el reintento
    donde el ADR 0020 lo quiere, en la pasada siguiente.
    """
    # `LOTE` se lee aquí y no como valor por defecto del parámetro: así un test puede bajarlo
    # sin pasar el argumento por toda la cadena de llamadas.
    tam = LOTE if tam is None else tam
    ultimo_id = 0
    while True:
        lote = list(session.scalars(consulta.where(Norma.id > ultimo_id).limit(tam)))
        if not lote:
            return
        # Antes del commit: después, los objetos están expirados y leer `.id` volvería a la
        # base de datos.
        ultimo_id = lote[-1].id
        yield from lote
        session.commit()
        # **Sin `expunge_all()` aquí, y no por descuido.** Desvincularlos acotaría la memoria de
        # forma explícita, pero rompe a cualquier llamador que conserve una referencia a una
        # norma —`--fase2` encadena `descargar()` y esto en la misma sesión— y lo hace con un
        # `InvalidRequestError` a distancia. No hace falta: lo que ocupaba 295 MB era
        # materializar las 69.388 de golpe, y la identity map guarda referencias débiles, así
        # que cada lote se libera solo al soltarlo la vuelta siguiente.
        logger.info("prefiltro: lote confirmado, hasta norma id=%s", ultimo_id)


def aplicar(
    session: Session,
    *,
    almacen_root: Path,
    documento_id: int | None = None,
    forzar: bool = False,
) -> ResumenPrefiltro:
    """Evalúa y persiste. Idempotente: repetirlo sobre lo mismo no cambia nada.

    `documento_id=None` barre toda la tabla; es lo que hay que lanzar tras subir
    `VERSION_VOCABULARIO`.
    """
    ahora = datetime.datetime.now(datetime.UTC)
    relevantes = sospechas = descartadas = pendientes = solo_contexto = 0
    ilegibles = con_texto = 0
    por_eje: dict[str, int] = {}

    # La watchlist se carga **una vez por pasada**, no por norma: son cientos de normas y el
    # fichero no cambia a mitad de ejecución. Que falte es un error ruidoso a propósito (ver
    # `watchlist.WatchlistNoDisponible`): una watchlist vacía no rompe nada, solo apaga en
    # silencio el único eje que detecta la instrucción que no se nombra.
    lista = watchlist.watchlist()

    evaluadas = 0
    for norma in _por_lotes(session, _pendientes(documento_id, forzar)):
        evaluadas += 1
        # Aquí entra la fase 2 (tarea 0.c, ADR 0011 y 0015). `texto_integro=None` significa
        # que el cuerpo todavía no está archivado, y `evaluar` ya sabe que sobre el título no
        # se descarta nunca (7.1): como mucho queda `pendiente`.
        # `CuerpoIlegible` es lo contrario de `None` y por eso no comparten rama (ADR 0020):
        # `None` es "todavía no hay cuerpo" y degrada a fase 1; la excepción es "hay cuerpo y no
        # se puede leer", que es un hueco de cobertura y tiene su propio estado.
        try:
            cuerpo = leer_cuerpo(norma, almacen_root=almacen_root, lista=lista)
        except CuerpoIlegible:
            cuerpo = None
            ilegible = True
        else:
            ilegible = False
        texto = cuerpo.texto if cuerpo is not None else None
        resultado = prefiltro.evaluar(
            norma.titulo,
            organo_emisor=norma.organo_emisor,
            texto_integro=texto,
            referencias=cuerpo.referencias if cuerpo is not None else (),
            lista=lista,
            cuerpo_ilegible=ilegible,
        )
        if texto is not None:
            con_texto += 1

        norma.prefiltro_estado = resultado.estado
        # Lista vacía y no NULL cuando no hay términos: NULL significaría "no evaluado", que
        # es otra cosa. Misma distinción que la del estado PENDIENTE.
        norma.prefiltro_terminos = list(resultado.terminos)
        norma.prefiltro_ejes = [eje.value for eje in resultado.ejes]
        norma.prefiltro_directos = resultado.directos
        norma.prefiltro_version = resultado.version
        norma.prefiltro_version_watchlist = resultado.version_watchlist
        # NULL cuando se evaluó solo sobre el título: es lo que hará que esta norma se vuelva
        # a mirar en cuanto su cuerpo esté archivado.
        #
        # **Una `ilegible` también queda a NULL, y eso significa que se reintenta en cada
        # pasada. Es deliberado** (ADR 0020): el reintento es lo único que la recupera sola el
        # día que su cuerpo se pueda leer —porque se vuelva a descargar en otro formato, o
        # porque el fallo fuera del almacén y no del documento— y marcarla como evaluada la
        # dejaría congelada como ilegible para siempre. Es el mismo criterio con el que el
        # catálogo de reglas no marca como evaluado lo que no ha podido leer.
        #
        # El coste está acotado y medido: son 172 ficheros de disco por pasada, ni red ni LLM.
        # Lo que sí sería un problema es que el número creciera sin que nadie lo viera, y para
        # eso está `ilegibles` en el embudo.
        norma.prefiltro_version_texto = VERSION_TEXTO_PLANO if texto is not None else None
        norma.prefiltro_evaluado_en = ahora

        for eje in resultado.ejes:
            por_eje[eje.value] = por_eje.get(eje.value, 0) + 1

        if resultado.estado is EstadoPrefiltro.RELEVANTE:
            relevantes += 1
        elif resultado.estado is EstadoPrefiltro.SOSPECHA:
            sospechas += 1
        elif resultado.estado is EstadoPrefiltro.PENDIENTE:
            pendientes += 1
        elif resultado.estado is EstadoPrefiltro.ILEGIBLE:
            ilegibles += 1
        else:
            descartadas += 1

        if resultado.entra_en_la_cola and resultado.solo_por_contexto:
            solo_contexto += 1

    # Cierra el último lote, que `_por_lotes` no llega a confirmar si el bucle termina o se
    # rompe a mitad. Repetirlo sobre una sesión ya limpia no cuesta nada.
    session.commit()

    return ResumenPrefiltro(
        evaluadas=evaluadas,
        relevantes=relevantes,
        sospechas=sospechas,
        descartadas=descartadas,
        pendientes=pendientes,
        ilegibles=ilegibles,
        solo_por_contexto=solo_contexto,
        por_eje=por_eje,
        sobre_texto_integro=con_texto,
    )
