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
from app.pipeline import prefiltro
from app.security.url_guard import UrlGuardError
from app.security.xml_safe import XmlSafeError
from app.services import extraccion as servicio_extraccion
from app.services import ingesta
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
            "lanzar después de tocar el diccionario."
        ),
    )
    args = parser.parse_args(argv)
    # `--fuente` deja de ser obligatorio porque `--reprefiltrar` no ingiere; se sigue
    # exigiendo para todo lo demás, que sí necesita saber de dónde descargar.
    if not args.reprefiltrar and args.fuente is None:
        parser.error("--fuente es obligatorio salvo con --reprefiltrar")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parsear_argumentos(argv)
    logging.basicConfig(
        level=get_settings().log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = get_settings()

    if args.reprefiltrar:
        with SessionLocal() as session:
            resumen = servicio_prefiltro.aplicar(session)
        logger.info(
            "Prefiltro reaplicado (vocabulario %s): %s evaluadas, %s relevantes "
            "(%s solo por términos de contexto), %s descartadas.",
            prefiltro.VERSION_VOCABULARIO,
            resumen.evaluadas,
            resumen.relevantes,
            resumen.solo_por_contexto,
            resumen.descartadas,
        )
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

        # Etapa 1 del pipeline, en la misma pasada que la ingesta. Va aquí y no en un cron
        # aparte porque es determinista y barato (no toca la red ni el LLM): separarlo solo
        # añadiría una ventana en la que hay normas ingeridas que nadie ha mirado todavía.
        resumen = servicio_prefiltro.aplicar(session, documento_id=resultado.documento_id)

        # Etapa 2, acoplada a la misma pasada por la misma razón: sin esto habría una ventana
        # con normas relevantes y nadie las habría mirado. A diferencia del prefiltro, esta
        # etapa sí toca red y LLM (Ollama local, ADR 0008) y puede tardar; es aceptable en un
        # worker cron diario, no lo sería en una petición HTTP.
        resumen_extraccion = servicio_extraccion.aplicar(
            session, ProveedorOllama(), documento_id=resultado.documento_id
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
    # El embudo se registra siempre, incluso cuando no se creó nada: es la cifra que dice
    # cuánto trabajo se ahorra el extractor, y perderla en las reejecuciones dejaría el log
    # sin la única métrica interesante de esta etapa.
    logger.info(
        "Prefiltro (vocabulario %s): %s evaluadas, %s relevantes (%s solo por términos de "
        "contexto), %s descartadas.",
        prefiltro.VERSION_VOCABULARIO,
        resumen.evaluadas,
        resumen.relevantes,
        resumen.solo_por_contexto,
        resumen.descartadas,
    )
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
