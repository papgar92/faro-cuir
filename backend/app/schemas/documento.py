"""Esquemas de salida de la API pública.

Son deliberadamente distintos de los modelos de SQLAlchemy y no se generan a partir de ellos.
Un `from_attributes` sobre el modelo entero publicaría cualquier columna que se añada mañana
sin que nadie lo decida; escribir el esquema a mano hace que exponer un campo nuevo sea un
acto explícito. En una API pública sin autenticación eso importa.
"""

from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict


class NormaResumen(BaseModel):
    """Una norma tal y como se lista en la API pública."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    identificador_oficial: str
    titulo: str
    organo_emisor: str | None
    # Nulos mientras el extractor no haya procesado la norma. Se exponen igualmente para que
    # el cliente distinga "todavía no analizado" de "analizado y sin ámbito claro".
    rango: str | None
    ambito: str | None
    url_texto: str | None


class DocumentoResumen(BaseModel):
    """Un documento ingerido. Incluye la huella para que el archivo sea comprobable."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    identificador_oficial: str
    fecha_publicacion: datetime.date
    url_original: str
    # El sha256 y el sello se publican a propósito (CLAUDE.md 6.5): quien reciba una alerta
    # debe poder verificar por su cuenta que el contenido archivado es el que se publicó.
    sha256: str
    sello_tiempo: datetime.datetime
    estado_pipeline: str
    # `ruta_almacen` NO se expone: es una ruta del sistema de ficheros del servidor y no le
    # sirve de nada a un cliente. Publicar rutas internas solo regala información.


class DocumentoDetalle(DocumentoResumen):
    normas: list[NormaResumen]
