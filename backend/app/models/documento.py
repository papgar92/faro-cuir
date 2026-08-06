from __future__ import annotations

import datetime
import enum
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.norma import Norma


class EstadoPipeline(enum.StrEnum):
    """Dónde está el documento dentro del pipeline de la sección 7 de CLAUDE.md.

    El vocabulario sigue las etapas de ese pipeline (prefiltro → extractor → clasificador →
    gate humano), más dos estados terminales. `descartado` es el camino normal y mayoritario:
    la inmensa mayoría de un boletín no habla de derechos LGTBI+ y el prefiltro léxico la
    descarta sin gastar un token de LLM. Se guarda igualmente el documento y su hash, porque
    el archivo íntegro de la sección 6.5 tiene que cubrir también lo que no nos interesó —
    si solo archiváramos lo relevante, no podríamos demostrar qué más se publicó ese día.
    """

    INGERIDO = "ingerido"
    PREFILTRADO = "prefiltrado"
    EXTRAIDO = "extraido"
    CLASIFICADO = "clasificado"
    DESCARTADO = "descartado"
    ERROR = "error"


class Documento(Base):
    """Un documento crudo ingerido de una fuente. CLAUDE.md sección 5."""

    __tablename__ = "documento"
    __table_args__ = (
        # Clave natural. Es lo que hace idempotente al worker (CLAUDE.md sección 3): volver a
        # lanzar la ingesta de una fecha ya procesada no duplica filas, y la restricción vive
        # en la base de datos y no solo en el código del worker, porque dos ejecuciones
        # solapadas del cron pueden pasar a la vez por el "¿existe ya?" del ORM.
        UniqueConstraint("fuente_id", "identificador_oficial", name="uq_documento_fuente_ident"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fuente_id: Mapped[int] = mapped_column(
        ForeignKey("fuente.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # El identificador que le da la propia fuente (p. ej. "BOE-A-2024-26484"). Se guarda tal
    # cual llega; NO se usa jamás para construir rutas de fichero (ver security/hashing.py).
    identificador_oficial: Mapped[str] = mapped_column(String(200), nullable=False)
    fecha_publicacion: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    url_original: Mapped[str] = mapped_column(String(1000), nullable=False)

    # --- Archivo íntegro verificable (CLAUDE.md 6.5) ---
    # sha256 del contenido exacto descargado. Indexado, no único: dos fuentes distintas
    # pueden republicar el mismo texto y ambas publicaciones son hechos separados que el
    # archivo debe conservar por separado.
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Cuándo lo vimos nosotros, en UTC con zona explícita. No es la fecha de publicación:
    # el par (sha256, sello_tiempo) es lo que permite afirmar "el día X este documento decía
    # exactamente esto".
    sello_tiempo: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Ruta relativa dentro del almacén, derivada del sha256 (ver security/hashing.py).
    ruta_almacen: Mapped[str] = mapped_column(String(300), nullable=False)

    estado_pipeline: Mapped[EstadoPipeline] = mapped_column(
        # Mismo criterio que en `fuente`: VARCHAR + CHECK en vez de ENUM nativo (evolucionar
        # un ENUM nativo exige ALTER TYPE), con values_callable para que se guarde el valor
        # en minúsculas y no el nombre del miembro de Python.
        Enum(
            EstadoPipeline,
            native_enum=False,
            length=20,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=EstadoPipeline.INGERIDO,
        server_default=EstadoPipeline.INGERIDO.value,
        index=True,
    )

    # Relación ORM, no columna nueva: no cambia el esquema y por tanto no necesita migración.
    # Sin cascade de borrado a propósito — la FK es RESTRICT y el archivo no se borra en
    # cascada por accidente.
    normas: Mapped[list[Norma]] = relationship(back_populates="documento")
