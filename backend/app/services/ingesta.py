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
from app.models.norma import Norma
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
    # Cuántas normas nuevas se registraron. En una reingesta limpia será 0.
    normas_creadas: int


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


def _buscar_documento(session: Session, *, fuente_id: int, identificador: str) -> Documento | None:
    return session.scalar(
        select(Documento).where(
            Documento.fuente_id == fuente_id,
            Documento.identificador_oficial == identificador,
        )
    )


def _sincronizar_normas(session: Session, *, documento_id: int, sumario: Sumario) -> int:
    """Registra como `norma` los items del sumario que aún no estén.

    Se comparan los identificadores ya guardados contra los del sumario en vez de intentar
    insertar y capturar el error: así una ingesta que se quedó a medias (documento guardado
    pero normas no) se completa al reintentar, en vez de darse por buena porque el documento
    ya existía.
    """
    ya_guardados = set(
        session.scalars(
            select(Norma.identificador_oficial).where(Norma.documento_id == documento_id)
        ).all()
    )

    nuevas = [
        Norma(
            documento_id=documento_id,
            identificador_oficial=item.identificador,
            titulo=item.titulo,
            url_texto=item.url_xml,
            # El departamento del sumario es el órgano que emite: es dato real de la fuente,
            # no una deducción. `rango` y `ambito` se quedan en NULL a propósito — del título
            # no se pueden saber sin leer el texto completo, y rellenarlos a ojo sería
            # justamente lo que prohíbe la regla de oro 8.
            organo_emisor=item.departamento or None,
        )
        for item in sumario.items
        if item.identificador not in ya_guardados
    ]

    session.add_all(nuevas)
    return len(nuevas)


def ingerir_sumario_boe(
    session: Session,
    *,
    fuente_id: int,
    fecha: datetime.date,
    almacen_root: Path,
    client: httpx.Client | None = None,
) -> ResultadoIngesta:
    """Descarga, archiva y registra el sumario del BOE de una fecha, con sus normas.

    Idempotente: volver a lanzarlo sobre una fecha ya ingerida no duplica nada.
    """
    contenido = boe.descargar_sumario(fecha, client=client)
    sumario = boe.parsear_sumario(contenido, fecha_esperada=fecha)

    digest = hashing.sha256_hex(contenido)
    ruta_relativa = _archivar(contenido, digest, almacen_root=almacen_root)

    documento = _buscar_documento(session, fuente_id=fuente_id, identificador=sumario.identificador)
    creado = False

    if documento is None:
        documento = Documento(
            fuente_id=fuente_id,
            identificador_oficial=sumario.identificador,
            fecha_publicacion=sumario.fecha_publicacion,
            url_original=boe.url_sumario(fecha),
            sha256=digest,
            # Cuándo lo vimos nosotros, en UTC explícito. Junto al sha256 es lo que sostiene
            # la afirmación "el día X esto decía exactamente esto" (CLAUDE.md 6.5).
            sello_tiempo=datetime.datetime.now(datetime.UTC),
            ruta_almacen=ruta_relativa,
            estado_pipeline=EstadoPipeline.INGERIDO,
        )
        session.add(documento)
        try:
            session.flush()
            creado = True
        except IntegrityError:
            # Dos ejecuciones del cron solapadas pueden pasar las dos por el SELECT de arriba
            # antes de que ninguna inserte. La restricción única de la tabla es la que decide
            # de verdad; aquí solo se recoge el resultado de esa carrera.
            session.rollback()
            documento = _buscar_documento(
                session, fuente_id=fuente_id, identificador=sumario.identificador
            )
            if documento is None:
                raise

    normas_creadas = _sincronizar_normas(session, documento_id=documento.id, sumario=sumario)
    session.commit()

    return ResultadoIngesta(
        documento_id=documento.id,
        sumario=sumario,
        sha256=documento.sha256,
        ruta_almacen=documento.ruta_almacen,
        creado=creado,
        normas_creadas=normas_creadas,
    )
