"""Entrypoint del cron de ingesta (CLAUDE.md secciones 3 y 10).

    python -m worker.run --fuente boe --fecha 2024-12-19

Un script idempotente: mismo input, mismo resultado, seguro de re-ejecutar. Esa propiedad es
lo que permite que no haga falta Celery ni una cola distribuida — si una ejecución falla a
mitad, se vuelve a lanzar y ya está.
"""

from __future__ import annotations

import argparse
import datetime
import logging
import sys
import time

from sqlalchemy import select

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.ingest import boe_consolidado
from app.ingest.boe import BoeIngestError, SumarioNoDisponible
from app.llm.ollama import ProveedorOllama
from app.llm.provider import VERSION_PROMPT
from app.models.fuente import Fuente, TipoFuente
from app.pipeline import prefiltro, reglas, texto, watchlist
from app.security.url_guard import UrlGuardError
from app.security.xml_safe import XmlSafeError
from app.services import clasificacion as servicio_clasificacion
from app.services import extraccion as servicio_extraccion
from app.services import ingesta, texto_integro, versionado
from app.services import prefiltro as servicio_prefiltro
from app.services import revision as servicio_revision

logger = logging.getLogger("worker")

FUENTES_SOPORTADAS = ("boe", "dogc")


def _fecha(valor: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(valor)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Fecha inválida {valor!r}, se espera AAAA-MM-DD") from exc


def _parsear_argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="worker.run", description="Ingesta de boletines oficiales"
    )
    parser.add_argument("--fuente", choices=FUENTES_SOPORTADAS)
    parser.add_argument(
        "--fecha",
        type=_fecha,
        default=datetime.date.today(),
        help="Fecha del sumario en formato AAAA-MM-DD. Por defecto, hoy.",
    )
    parser.add_argument(
        "--hasta",
        type=_fecha,
        help=(
            "Ingiere el rango [--fecha, --hasta], un día por pasada. Existe para poder traer "
            "meses de boletín sin lanzar treinta órdenes a mano; un día sin boletín (domingo, "
            "festivo) no interrumpe el rango, se registra y se sigue."
        ),
    )
    parser.add_argument(
        "--sin-extraccion",
        action="store_true",
        help=(
            "Ingiere, archiva, prefiltra y clasifica, pero NO llama al LLM. Es lo que hace "
            "viable un backfill: una extracción cuesta 133,9 s (ADR 0011), así que un mes de "
            "BOE serían horas de CPU. Lo que quede sin extraer sigue en cola y se procesa "
            "después con una pasada normal, sin perder nada."
        ),
    )
    parser.add_argument(
        "--reprefiltrar",
        action="store_true",
        help=(
            "No ingiere nada: vuelve a pasar el prefiltro léxico por las normas ya guardadas "
            "que estén pendientes o evaluadas con un vocabulario anterior. Es lo que hay que "
            "lanzar después de tocar el diccionario. No toca la red: lee los cuerpos ya "
            "archivados (ADR 0015)."
        ),
    )
    parser.add_argument(
        "--fase2",
        action="store_true",
        help=(
            "No ingiere nada: descarga el texto íntegro de las normas que aún no lo tienen, "
            "de toda la tabla y no solo del día, y vuelve a pasar el prefiltro sobre ellas. "
            "Es lo que drena el atasco de normas en 'pendiente' (tarea 0.c). Respeta el tope "
            "por ejecución, así que un atasco grande se vacía en varias pasadas."
        ),
    )
    parser.add_argument(
        "--versionar",
        action="store_true",
        help=(
            "No ingiere nada: descarga el texto consolidado de las normas vigiladas que alguna "
            "norma ya ingerida modifica, y guarda el diff en version_norma (ADR 0018). Barre "
            "toda la tabla. Es lo que hay que lanzar a mano cuando se quiera forzar el "
            "reintento de lo que el BOE todavía no había consolidado."
        ),
    )
    parser.add_argument(
        "--reclasificar",
        action="store_true",
        help=(
            "No ingiere nada: vuelve a pasar el catálogo de reglas (ADR 0016) por las normas "
            "con cuerpo archivado que estén sin evaluar o evaluadas con una versión anterior "
            "del catálogo o de la derivación del texto. Es lo que hay que lanzar después de "
            "tocar una regla. No toca la red ni el LLM."
        ),
    )
    args = parser.parse_args(argv)
    # `--fuente` deja de ser obligatorio porque ninguno de los modos de mantenimiento ingiere;
    # se sigue exigiendo para todo lo demás, que sí necesita saber de dónde descargar.
    mantenimiento = args.reprefiltrar or args.fase2 or args.reclasificar or args.versionar
    if not mantenimiento and args.fuente is None:
        parser.error(
            "--fuente es obligatorio salvo con --reprefiltrar, --fase2, --versionar "
            "o --reclasificar"
        )
    return args


def _registrar_embudo(resumen: servicio_prefiltro.ResumenPrefiltro, *, reaplicado: bool) -> None:
    """Escribe el embudo del prefiltro en el log, con sus cuatro escalones.

    El embudo se registra siempre, incluso cuando no se ha creado nada: es la cifra que dice
    cuánto trabajo se ahorra el extractor, y perderla en las reejecuciones dejaría el log sin
    la única métrica interesante de esta etapa.

    **Las cuatro cifras van juntas y ninguna se omite por ser cero.** El log anterior decía
    "N relevantes, M descartadas" y con el estado `sospecha` (7.2) eso habría dejado fuera
    justo el escalón nuevo: un embudo al que le falta un peldaño no cuadra, y quien lo lea
    dará por hecho que las que faltan se descartaron. `pendientes` es hoy la cifra grande y
    tiene que verse — significa "esperando su texto íntegro", que es la tarea 0.c, no que
    nadie las quiera.
    """
    logger.info(
        "Prefiltro%s (vocabulario %s, watchlist %s, texto %s): %s evaluadas → %s relevantes, "
        "%s sospechas, %s descartadas, %s pendientes de texto íntegro. "
        "%s de las evaluadas lo fueron sobre texto íntegro. "
        "%s pasan solo por términos de contexto. Por eje: %s.",
        " reaplicado" if reaplicado else "",
        prefiltro.VERSION_VOCABULARIO,
        watchlist.watchlist().version,
        texto.VERSION_TEXTO_PLANO,
        resumen.evaluadas,
        resumen.relevantes,
        resumen.sospechas,
        resumen.descartadas,
        resumen.pendientes,
        # Va en la misma línea que el embudo y no en otra a propósito: es la salvedad que
        # convierte estas cifras en una medición o en un límite superior (7.8), y separarla
        # sería invitar a copiar el embudo sin ella.
        resumen.sobre_texto_integro,
        resumen.solo_por_contexto,
        resumen.por_eje or "ninguno",
    )


def _registrar_fase2(resumen: texto_integro.ResumenFase2) -> None:
    """Escribe el resultado de la fase 2, con lo que queda en cola.

    `pendientes_restantes` no se omite nunca aunque sea cero: es la diferencia entre "ya está
    todo" y "esta pasada llegó al tope y queda trabajo", y un log que solo diga cuántas se
    descargaron se lee como lo primero en los dos casos.
    """
    logger.info(
        "Fase 2 (texto íntegro): %s candidatas → %s descargadas (%s KB), %s fallidas. "
        "Quedan %s en cola.",
        resumen.candidatas,
        resumen.descargadas,
        round(resumen.bytes_descargados / 1024),
        resumen.fallidas,
        resumen.pendientes_restantes,
    )


def _registrar_clasificacion(resumen: servicio_clasificacion.ResumenClasificacion) -> None:
    """Escribe el resultado del catálogo de reglas, con el desglose por regla.

    `con_veredicto` es y debe ser una cifra pequeña —7 de 652 documentos en el corpus de tres
    días—, así que el desglose por regla es lo único que dice si el catálogo sigue vivo.
    `obsoletos` no se omite nunca aunque sea cero: significa veredictos que el catálogo actual
    ya no sostiene y que **no se retiran solos**, así que quien lee el log tiene que enterarse.
    """
    logger.info(
        "Clasificación (reglas %s, texto %s): %s evaluadas → %s con veredicto, "
        "%s ilegibles, %s veredictos obsoletos. Por regla: %s.",
        reglas.VERSION_REGLAS,
        texto.VERSION_TEXTO_PLANO,
        resumen.evaluadas,
        resumen.con_veredicto,
        resumen.ilegibles,
        resumen.obsoletos,
        resumen.por_regla or "ninguna",
    )


def _registrar_versionado(resumen: versionado.ResumenVersionado) -> None:
    """Escribe el resultado del versionado, con lo que la fuente aún no ha consolidado.

    `sin_consolidar` es la cifra que no se puede omitir y la que más se malinterpreta: no
    significa que la norma no cambiara nada, sino que el BOE todavía no lo ha incorporado a su
    texto consolidado. Un log que solo diga "0 diffs" se lee como lo primero y es mentira.
    """
    logger.info(
        "Versionado (consolidado %s): %s candidatas → %s consultadas, %s con diff "
        "(%s versiones), %s sin consolidar todavía, %s fallidas. Quedan %s en cola. "
        "Por norma vigilada: %s.",
        boe_consolidado.VERSION_CONSOLIDADO,
        resumen.candidatas,
        resumen.consultadas,
        resumen.con_diff,
        resumen.filas,
        resumen.sin_consolidar,
        resumen.fallidas,
        resumen.pendientes_restantes,
        resumen.por_norma_afectada or "ninguna",
    )


def _versionar(session) -> versionado.ResumenVersionado:  # type: ignore[no-untyped-def]
    settings = get_settings()
    return versionado.poblar(
        session,
        almacen_root=settings.almacen_root,
        pausa=settings.versionado_pausa_segundos,
        limite=settings.versionado_max_por_ejecucion,
    )


def _encolar_revision(session) -> servicio_revision.ResumenEncolado:  # type: ignore[no-untyped-def]
    """Etapa 6: mete en la cola del gate humano lo que el clasificador dejó con veredicto.

    Va pegado a la clasificación en las dos rutas del worker (la pasada diaria y
    `--reclasificar`) y no en un modo aparte, por el mismo motivo por el que el prefiltro va
    pegado a la ingesta: separarlo abriría una ventana con detecciones clasificadas que no están
    en ninguna cola, o sea que nadie va a mirar. Es barato —una consulta— e idempotente.
    """
    resumen = servicio_revision.encolar(session)
    session.commit()
    logger.info(
        "Gate humano (regla de oro 4): %s detecciones con veredicto, %s encoladas para revisión. "
        "Ninguna se emite sin que una persona la apruebe.",
        resumen.candidatas,
        resumen.encoladas,
    )
    return resumen


def _dias(desde: datetime.date, hasta: datetime.date | None) -> list[datetime.date]:
    """Los días del rango, en orden. Sin `--hasta`, solo el día pedido."""
    if hasta is None or hasta <= desde:
        return [desde]
    return [desde + datetime.timedelta(days=n) for n in range((hasta - desde).days + 1)]


def main(argv: list[str] | None = None) -> int:
    args = _parsear_argumentos(argv)
    logging.basicConfig(
        level=get_settings().log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = get_settings()

    if args.reprefiltrar:
        with SessionLocal() as session:
            resumen = servicio_prefiltro.aplicar(session, almacen_root=settings.almacen_root)
        _registrar_embudo(resumen, reaplicado=True)
        return 0

    if args.fase2:
        # Drena el atasco: descarga los cuerpos que falten de **toda** la tabla y reevalúa.
        # Las dos cosas van juntas porque separarlas dejaría el trabajo a medias — cuerpos
        # archivados que nadie ha mirado — y esa es exactamente la ventana que el resto del
        # worker se cuida de no abrir.
        # Sin `try/except UrlGuardError` aquí a propósito: `descargar` ya lo captura **por
        # norma** y lo registra como `CONTROL DE SEGURIDAD`, porque una URL hostil en un ítem
        # no puede abortar el día entero. Un catch aquí sería código muerto que sugiere un
        # camino que no existe.
        with SessionLocal() as session:
            resumen_fase2 = texto_integro.descargar(
                session,
                almacen_root=settings.almacen_root,
                pausa=settings.fase2_pausa_segundos,
                limite=settings.fase2_max_por_ejecucion,
            )
            resumen = servicio_prefiltro.aplicar(session, almacen_root=settings.almacen_root)
        _registrar_fase2(resumen_fase2)
        _registrar_embudo(resumen, reaplicado=True)
        return 0

    if args.versionar:
        with SessionLocal() as session:
            resumen_versionado = _versionar(session)
        _registrar_versionado(resumen_versionado)
        return 0

    if args.reclasificar:
        with SessionLocal() as session:
            resumen_clasificacion = servicio_clasificacion.aplicar(
                session, almacen_root=settings.almacen_root
            )
            _encolar_revision(session)
        _registrar_clasificacion(resumen_clasificacion)
        return 0

    dias = _dias(args.fecha, args.hasta)
    if len(dias) > 1:
        logger.info(
            "Backfill de %s días, del %s al %s.%s",
            len(dias),
            dias[0],
            dias[-1],
            " Sin extracción: el LLM no se toca." if args.sin_extraccion else "",
        )

    codigo = 0
    for indice, dia in enumerate(dias):
        resultado_dia = _ingerir_dia(
            dia, settings, fuente_pedida=args.fuente, sin_extraccion=args.sin_extraccion
        )
        # Un día sin boletín o un fallo de red **no interrumpe el rango**: un domingo por medio
        # no puede dejar sin ingerir el resto del mes. Se queda el peor código de salida para
        # que el cron se entere igualmente de que algo fue mal.
        codigo = max(codigo, resultado_dia)
        if len(dias) > 1 and indice < len(dias) - 1:
            # Cortesía con la fuente entre días, igual que dentro de la fase 2 (6.2).
            time.sleep(settings.fase2_pausa_segundos)
    return codigo


def _ingerir_dia(  # noqa: C901
    fecha: datetime.date,
    settings: Settings,
    *,
    fuente_pedida: str = "boe",
    sin_extraccion: bool = False,
) -> int:
    """Una pasada completa del pipeline sobre un día de boletín."""
    with SessionLocal() as session:
        tipo = TipoFuente.BOE if fuente_pedida == "boe" else TipoFuente.BOLETIN_AUTONOMICO
        consulta = select(Fuente).where(Fuente.tipo == tipo)
        if fuente_pedida != "boe":
            # Hay 17 boletines autonómicos posibles en el modelo; hoy solo uno integrado.
            consulta = consulta.where(Fuente.ccaa_codigo == "CT")
        fuente = session.scalar(consulta)
        if fuente is None:
            logger.error(
                "No hay ninguna fuente %r en la base de datos. "
                "¿Falta aplicar las migraciones (alembic upgrade head)?",
                fuente_pedida,
            )
            return 2
        if not fuente.activa:
            logger.error("La fuente %r está marcada como inactiva; no se ingiere.", fuente.nombre)
            return 2

        ingerir = (
            ingesta.ingerir_sumario_boe if fuente_pedida == "boe" else ingesta.ingerir_sumario_dogc
        )
        try:
            resultado = ingerir(
                session,
                fuente_id=fuente.id,
                fecha=fecha,
                almacen_root=settings.almacen_root,
            )
        except SumarioNoDisponible as exc:
            # Salida 0: un día sin boletín es una respuesta válida del mundo, no un fallo.
            logger.info("%s", exc)
            return 0
        except (UrlGuardError, XmlSafeError) as exc:
            # Un fallo de control de seguridad no es un error de ingesta cualquiera: significa
            # que la fuente nos ha devuelto algo que no deberíamos aceptar. Se registra
            # aparte para que no se pierda entre los fallos rutinarios de red.
            logger.error("CONTROL DE SEGURIDAD: %s: %s", type(exc).__name__, exc)
            return 3
        except BoeIngestError as exc:
            logger.error("No se pudo ingerir el sumario del %s: %s", fecha, exc)
            return 1

        # Fase 2 (ADR 0011 y 0015): el texto íntegro del día entero, **antes** del prefiltro.
        # El orden no es negociable: el prefiltro sobre el título solo puede dejar normas en
        # `pendiente` (7.1), así que ejecutarlo antes de tener los cuerpos significa no
        # descartar ni promocionar nada. Cuesta ~10 s por día de BOE (ADR 0011).
        resumen_fase2 = texto_integro.descargar(
            session,
            almacen_root=settings.almacen_root,
            pausa=settings.fase2_pausa_segundos,
            limite=settings.fase2_max_por_ejecucion,
            documento_id=resultado.documento_id,
        )

        # Etapa 1 del pipeline, en la misma pasada que la ingesta. Va aquí y no en un cron
        # aparte porque es determinista y barato (no toca la red ni el LLM): separarlo solo
        # añadiría una ventana en la que hay normas ingeridas que nadie ha mirado todavía.
        resumen = servicio_prefiltro.aplicar(
            session, almacen_root=settings.almacen_root, documento_id=resultado.documento_id
        )

        # Versionado (ADR 0018): el texto anterior de lo que las normas modifican, desde el
        # consolidado del BOE. Barre **toda** la tabla y no solo el documento del día, y esa es
        # justo la razón de que exista como etapa y no como un paso más de la ingesta: la
        # consolidación llega con retraso, así que lo que hoy se puede completar casi nunca es lo
        # de hoy, sino lo de días anteriores. Sale a la red, con el tope y la pausa de 6.2.
        resumen_versionado = _versionar(session)

        # Etapa 3, acoplada a la misma pasada por la misma razón: sin esto habría una ventana
        # con normas relevantes y nadie las habría mirado. Ya no toca la red (lee el cuerpo del
        # almacén, ADR 0015) pero sí el LLM (Ollama local, ADR 0008) y puede tardar; es
        # aceptable en un worker cron diario, no lo sería en una petición HTTP.
        # `--sin-extraccion` es lo que hace viable un backfill (133,9 s por norma, ADR 0011).
        # Lo que se salta **no se pierde**: la cola del extractor es una consulta —normas en
        # cola sin `deteccion`— así que una pasada normal posterior las recoge todas.
        resumen_extraccion = (
            servicio_extraccion.ResumenExtraccion(evaluadas=0, extraidas=0, fallidas=0, punteros=0)
            if sin_extraccion
            else servicio_extraccion.aplicar(
                session,
                ProveedorOllama(),
                almacen_root=settings.almacen_root,
                documento_id=resultado.documento_id,
            )
        )

        # Etapa 4 (ADR 0016): el catálogo de reglas sobre el texto archivado. Va **después**
        # del extractor y no antes por una sola razón: así puede contar cuántos de los
        # punteros que el modelo citó quedan corroborados por el archivo. El veredicto no
        # depende de eso —las reglas leen el texto, no la extracción— pero el diagnóstico sí,
        # y es lo único que puede contestar si el modelo ve supresiones que las reglas no ven.
        # Es barato: ni red ni LLM, solo leer del almacén.
        resumen_clasificacion = servicio_clasificacion.aplicar(
            session,
            almacen_root=settings.almacen_root,
            documento_id=resultado.documento_id,
        )

        # Etapa 6 (regla de oro 4, ADR 0003 y 0017). Barre **toda** la tabla y no solo el
        # documento del día a propósito: la cola es el inventario de lo que falta por revisar,
        # y un veredicto de anteayer que se quedó sin encolar seguiría sin encolarse nunca.
        _encolar_revision(session)

    if resultado.creado:
        logger.info(
            "Ingerido %s (%s items, %s normas nuevas) sha256=%s -> %s",
            resultado.sumario.identificador,
            len(resultado.sumario.items),
            resultado.normas_creadas,
            resultado.sha256,
            resultado.ruta_almacen,
        )
    elif resultado.normas_creadas:
        # El documento ya estaba pero le faltaban normas: una ingesta anterior se quedó a
        # medias y esta la ha completado. Decir "nada que hacer" aquí sería mentir en el log.
        logger.info(
            "El documento %s (id=%s) ya estaba, pero le faltaban normas: %s añadidas.",
            resultado.sumario.identificador,
            resultado.documento_id,
            resultado.normas_creadas,
        )
    else:
        logger.info(
            "Ya estaba ingerido %s (documento id=%s) con sus %s normas; nada que hacer.",
            resultado.sumario.identificador,
            resultado.documento_id,
            len(resultado.sumario.items),
        )
    _registrar_fase2(resumen_fase2)
    # El embudo se registra siempre, incluso cuando no se creó nada: es la cifra que dice
    # cuánto trabajo se ahorra el extractor, y perderla en las reejecuciones dejaría el log
    # sin la única métrica interesante de esta etapa.
    _registrar_embudo(resumen, reaplicado=False)
    logger.info(
        "Extracción (prompt %s): %s pendientes, %s extraídas, %s fallidas, "
        "%s punteros (preceptos citados sin texto, ADR 0016).",
        VERSION_PROMPT,
        resumen_extraccion.evaluadas,
        resumen_extraccion.extraidas,
        resumen_extraccion.fallidas,
        resumen_extraccion.punteros,
    )
    _registrar_versionado(resumen_versionado)
    _registrar_clasificacion(resumen_clasificacion)
    return 0


if __name__ == "__main__":
    sys.exit(main())
