import enum

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TipoFuente(str, enum.Enum):
    BOE = "boe"
    BOLETIN_AUTONOMICO = "boletin_autonomico"
    PARLAMENTO = "parlamento"


class FormatoFuente(str, enum.Enum):
    API = "api"
    RSS = "rss"
    HTML = "html"
    PDF = "pdf"


class Fuente(Base):
    """Un origen de datos (BOE, un boletín autonómico, un parlamento). CLAUDE.md sección 5."""

    __tablename__ = "fuente"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    # native_enum=False: guarda VARCHAR + CHECK en vez de un tipo ENUM nativo de Postgres.
    # Los ENUM nativos requieren ALTER TYPE para añadir valores; con 18 fuentes por integrar
    # y vocabulario que aún puede cambiar, un CHECK es mucho más barato de evolucionar.
    # create_constraint=True: sin esto SQLAlchemy no añade el CHECK y la validez del valor
    # solo se comprobaría en el ORM, no en la base de datos (dato hostil / escritura directa
    # a la DB podría colar un valor fuera del vocabulario).
    # values_callable: por defecto SQLAlchemy guarda el .name del Enum de Python (p.ej.
    # "BOLETIN_AUTONOMICO"); forzamos que guarde el .value en minúsculas ("boletin_autonomico")
    # para que coincida con el vocabulario de la sección 5 de CLAUDE.md.
    tipo: Mapped[TipoFuente] = mapped_column(
        Enum(
            TipoFuente,
            native_enum=False,
            length=30,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    # Nulo para el BOE (fuente estatal, no autonómica).
    ccaa: Mapped[str | None] = mapped_column(String(100))
    formato: Mapped[FormatoFuente] = mapped_column(
        Enum(
            FormatoFuente,
            native_enum=False,
            length=10,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    url_base: Mapped[str] = mapped_column(String(500), nullable=False)
    # Nulo mientras la licencia de reutilización de esa fuente esté TODO(verificar).
    licencia_reutil: Mapped[str | None] = mapped_column(String(200))
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
