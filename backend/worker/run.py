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

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.ingest.boe import BoeIngestError, SumarioNoDisponible
from app.llm.ollama import ProveedorOllama
from app.llm.provider import VERSION_PROMPT
from app.models.fuente import Fuente, TipoFuente
from app.pipeline import prefiltro, texto, watchlist
from app.security.url_guard import UrlGuardError
from app.security.xml_safe import XmlSafeError
from app.services import extraccion as servicio_extraccion
from app.services import ingesta, texto_integro
from app.services import prefiltro as servicio_prefiltro

logger = logging.getLogger("worker")

FUENTES_SOPORTADAS = ("boe",)


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
    args = parser.parse_args(argv)
    # `--fuente` deja de ser obligatorio porque ni `--reprefiltrar` ni `--fase2` ingieren; se
    # sigue exigiendo para todo lo demás, que sí necesita saber de dónde descargar.
    if not (args.reprefiltrar or args.fase2) and args.fuente is None:
        parser.error("--fuente es obligatorio salvo con --reprefiltrar o --fase2")
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

    with SessionLocal() as session:
        fuente = session.scalar(select(Fuente).where(Fuente.tipo == TipoFuente.BOE))
        if fuente is None:
            logger.error(
                "No hay ninguna fuente de tipo 'boe' en la base de datos. "
                "¿Falta aplicar las migraciones (alembic upgrade head)?"
            )
            return 2
        if not fuente.activa:
            logger.error("La fuente %r está marcada como inactiva; no se ingiere.", fuente.nombre)
            return 2

        try:
            resultado = ingesta.ingerir_sumario_boe(
                session,
                fuente_id=fuente.id,
                fecha=args.fecha,
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
            logger.error("No se pudo ingerir el sumario del %s: %s", args.fecha, exc)
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

        # Etapa 3, acoplada a la misma pasada por la misma razón: sin esto habría una ventana
        # con normas relevantes y nadie las habría mirado. Ya no toca la red (lee el cuerpo del
        # almacén, ADR 0015) pero sí el LLM (Ollama local, ADR 0008) y puede tardar; es
        # aceptable en un worker cron diario, no lo sería en una petición HTTP.
        resumen_extraccion = servicio_extraccion.aplicar(
            session,
            ProveedorOllama(),
            almacen_root=settings.almacen_root,
            documento_id=resultado.documento_id,
        )

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
        "Extracción (prompt %s): %s pendientes, %s extraídas, %s fallidas.",
        VERSION_PROMPT,
        resumen_extraccion.evaluadas,
        resumen_extraccion.extraidas,
        resumen_extraccion.fallidas,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
