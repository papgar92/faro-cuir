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
from app.models.fuente import Fuente, TipoFuente
from app.security.url_guard import UrlGuardError
from app.security.xml_safe import XmlSafeError
from app.services import ingesta

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
    parser.add_argument("--fuente", required=True, choices=FUENTES_SOPORTADAS)
    parser.add_argument(
        "--fecha",
        type=_fecha,
        default=datetime.date.today(),
        help="Fecha del sumario en formato AAAA-MM-DD. Por defecto, hoy.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parsear_argumentos(argv)
    logging.basicConfig(
        level=get_settings().log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = get_settings()

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

    if resultado.creado:
        logger.info(
            "Ingerido %s (%s items) sha256=%s -> %s",
            resultado.sumario.identificador,
            len(resultado.sumario.items),
            resultado.sha256,
            resultado.ruta_almacen,
        )
    else:
        logger.info(
            "Ya estaba ingerido %s (documento id=%s); nada que hacer.",
            resultado.sumario.identificador,
            resultado.documento_id,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
