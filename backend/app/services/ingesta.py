"""Persistencia de lo ingerido: convierte un sumario descargado en filas y ficheros.

Separado de `ingest/boe.py` a propósito. Ahí vive lo que es específico de cada fuente
(cómo se descarga y cómo se lee su XML); aquí vive lo que es igual para las 18: calcular la
huella, archivar el contenido crudo y crear la fila de `documento` sin duplicar.
"""

from __future__ import annotations

import datetime
import os
from dataclasses import dataclass
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ingest import boe
from app.ingest.boe import Sumario
from app.models.documento import Documento, EstadoPipeline
from app.security import hashing


@dataclass(frozen=True)
class ResultadoIngesta:
    documento_id: int
    sumario: Sumario
    sha256: str
    ruta_almacen: str
    # False cuando el sumario ya estaba ingerido. Es el caso normal al reintentar, no un
    # error: el worker es idempotente por diseño (CLAUDE.md sección 3).
    creado: bool


def _archivar(contenido: bytes, digest: str, *, almacen_root: Path) -> str:
    """Escribe el contenido crudo en el almacén y devuelve su ruta relativa.

    Si el fichero ya existe no se reescribe: mismo hash es mismo contenido, así que
    reescribirlo solo añadiría el riesgo de dejarlo a medias sin ganar nada.
    """
    ruta_relativa = hashing.relative_storage_path(digest, ".xml")
    destino = hashing.storage_path(digest, ".xml", root=almacen_root)

    if destino.exists():
        return ruta_relativa

    destino.parent.mkdir(parents=True, exist_ok=True)
    # Escritura atómica: primero un temporal en el mismo directorio y luego `os.replace`, que
    # es atómico dentro del mismo sistema de ficheros. Si el proceso muere a mitad, el almacén
    # nunca queda con un fichero truncado cuyo nombre promete un sha256 que su contenido ya no
    # cumple — y eso rompería justo la propiedad que hace útil al archivo de la sección 6.5.
    temporal = destino.with_name(f"{destino.name}.{os.getpid()}.tmp")
    temporal.write_bytes(contenido)
    os.replace(temporal, destino)
    return ruta_relativa


def ingerir_sumario_boe(
    session: Session,
    *,
    fuente_id: int,
    fecha: datetime.date,
    almacen_root: Path,
    client: httpx.Client | None = None,
) -> ResultadoIngesta:
    """Descarga, archiva y registra el sumario del BOE de una fecha.

    Idempotente: volver a lanzarlo sobre una fecha ya ingerida no duplica nada.
    """
    contenido = boe.descargar_sumario(fecha, client=client)
    sumario = boe.parsear_sumario(contenido, fecha_esperada=fecha)

    digest = hashing.sha256_hex(contenido)
    ruta_relativa = _archivar(contenido, digest, almacen_root=almacen_root)

    existente = session.scalar(
        select(Documento).where(
            Documento.fuente_id == fuente_id,
            Documento.identificador_oficial == sumario.identificador,
        )
    )
    if existente is not None:
        return ResultadoIngesta(
            documento_id=existente.id,
            sumario=sumario,
            sha256=existente.sha256,
            ruta_almacen=existente.ruta_almacen,
            creado=False,
        )

    documento = Documento(
        fuente_id=fuente_id,
        identificador_oficial=sumario.identificador,
        fecha_publicacion=sumario.fecha_publicacion,
        url_original=boe.url_sumario(fecha),
        sha256=digest,
        # Cuándo lo vimos nosotros, en UTC explícito. Junto al sha256 es lo que sostiene la
        # afirmación "el día X esto decía exactamente esto" (CLAUDE.md 6.5).
        sello_tiempo=datetime.datetime.now(datetime.UTC),
        ruta_almacen=ruta_relativa,
        estado_pipeline=EstadoPipeline.INGERIDO,
    )
    session.add(documento)

    try:
        session.flush()
    except IntegrityError:
        # Dos ejecuciones del cron solapadas pueden pasar las dos por el SELECT de arriba
        # antes de que ninguna inserte. La restricción única de la tabla es la que decide de
        # verdad; aquí solo se recoge el resultado de esa carrera.
        session.rollback()
        ganador = session.scalar(
            select(Documento).where(
                Documento.fuente_id == fuente_id,
                Documento.identificador_oficial == sumario.identificador,
            )
        )
        if ganador is None:
            raise
        return ResultadoIngesta(
            documento_id=ganador.id,
            sumario=sumario,
            sha256=ganador.sha256,
            ruta_almacen=ganador.ruta_almacen,
            creado=False,
        )

    session.commit()
    return ResultadoIngesta(
        documento_id=documento.id,
        sumario=sumario,
        sha256=digest,
        ruta_almacen=ruta_relativa,
        creado=True,
    )
