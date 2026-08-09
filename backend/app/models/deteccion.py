import datetime
import enum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# JSONB en PostgreSQL (indexable, tipado) pero JSON genérico en cualquier otro dialecto, para
# que la suite de tests pueda montar el esquema en SQLite sin arrastrar Postgres.
_JSON_PORTABLE = JSON().with_variant(postgresql.JSONB(), "postgresql")


class Clasificacion(enum.StrEnum):
    AVANCE = "avance"
    RETROCESO = "retroceso"
    NEUTRO = "neutro"
    INDETERMINADO = "indeterminado"


class OrigenClasificacion(enum.StrEnum):
    """De dónde sale la clasificación.

    Fíjate en lo que **no** hay aquí: no existe un valor `llm`. Es deliberado y es el núcleo
    de la regla de oro 2 y de la sección 7 de CLAUDE.md. La clasificación avance/retroceso se
    deriva del diff con reglas auditables; el LLM solo extrae hechos a `extraccion_json` y
    nunca dicta veredictos. Al no existir el valor en el vocabulario, la CHECK de la base de
    datos hace que ni siquiera sea representable guardar "esto lo dijo el modelo".
    """

    DERIVADO_DIFF = "derivado_diff"
    HEURISTICA = "heuristica"


class EstadoRevision(enum.StrEnum):
    PENDIENTE = "pendiente"
    APROBADA = "aprobada"
    DESCARTADA = "descartada"


class Deteccion(Base):
    """Resultado del pipeline sobre una norma. CLAUDE.md sección 5."""

    __tablename__ = "deteccion"
    __table_args__ = (
        # La confianza es una probabilidad. Acotarla en la base de datos evita que un cambio
        # futuro en el clasificador meta un 1.4 y nadie se entere hasta que alguien lo pinte
        # en un porcentaje.
        CheckConstraint("confianza >= 0 AND confianza <= 1", name="ck_deteccion_confianza"),
        CheckConstraint("severidad >= 1 AND severidad <= 5", name="ck_deteccion_severidad"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    norma_id: Mapped[int] = mapped_column(
        ForeignKey("norma.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # Hechos extraídos por el LLM, validados contra un esquema Pydantic antes de llegar aquí
    # (sección 6.7: si no valida, se descarta, no se "interpreta"). Es materia prima para el
    # clasificador y para que un humano revise, nunca la clasificación en sí.
    extraccion_json: Mapped[dict[str, Any] | None] = mapped_column(_JSON_PORTABLE)

    clasificacion: Mapped[Clasificacion] = mapped_column(
        Enum(
            Clasificacion,
            native_enum=False,
            length=20,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        index=True,
    )
    origen: Mapped[OrigenClasificacion] = mapped_column(
        Enum(
            OrigenClasificacion,
            native_enum=False,
            length=20,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    # Qué regla concreta produjo esta clasificación. No está en la lista de la sección 5; se
    # añade porque sin ella "reglas auditables" es una promesa que no se puede cumplir: ante
    # la pregunta "¿por qué esto es un retroceso?" hay que poder señalar la regla, no un
    # número de confianza.
    regla_aplicada: Mapped[str | None] = mapped_column(String(100), index=True)
    # Los **spans de evidencia** que 7.6 exige junto a `regla_aplicada`, más la versión del
    # catálogo y de la derivación del texto sobre la que se midieron. Va en una columna propia
    # y no dentro de `extraccion_json` por un motivo de fondo: son dos procedencias distintas.
    # `extraccion_json` es lo que dijo el modelo; esto es lo que dice el archivo. Mezclarlas
    # dejaría de poder contestarse "¿esto lo afirma el LLM o lo afirma el BOE?", que es la
    # pregunta que separa este proyecto de uno que publica lo que le sale del modelo.
    #
    # Es nullable porque el extractor inserta antes de que exista veredicto (ADR 0009), y una
    # detección derivada de reglas puede existir con `extraccion_json` a NULL y esta llena: son
    # las dos caras y ninguna implica la otra.
    evidencia_json: Mapped[dict[str, Any] | None] = mapped_column(_JSON_PORTABLE)

    severidad: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    confianza: Mapped[float] = mapped_column(nullable=False, default=0.0)
    revisada: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    creada_en: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ColaRevision(Base):
    """Items pendientes del gate humano obligatorio. CLAUDE.md sección 5 y regla de oro 4."""

    __tablename__ = "cola_revision"

    id: Mapped[int] = mapped_column(primary_key=True)
    deteccion_id: Mapped[int] = mapped_column(
        ForeignKey("deteccion.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    estado: Mapped[EstadoRevision] = mapped_column(
        Enum(
            EstadoRevision,
            native_enum=False,
            length=20,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=EstadoRevision.PENDIENTE,
        server_default=EstadoRevision.PENDIENTE.value,
        index=True,
    )
    creada_en: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resuelta_en: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    # Nota libre de quien revisa. No se guarda su identidad: para auditar el gate basta saber
    # que se resolvió y cuándo, y almacenar quién revisa qué en un proyecto sobre derechos
    # LGTBI+ crearía un dato personal sensible que no necesitamos (sección 6.4).
    nota_revision: Mapped[str | None] = mapped_column(Text)


class Alerta(Base):
    """Una detección aprobada y emitida. CLAUDE.md sección 5.

    Que exista una fila aquí significa que un humano la aprobó: nada llega a esta tabla sin
    pasar por `cola_revision` en estado `aprobada`. Es la materialización de la regla de
    oro 4 en el modelo de datos.
    """

    __tablename__ = "alerta"

    id: Mapped[int] = mapped_column(primary_key=True)
    deteccion_id: Mapped[int] = mapped_column(
        ForeignKey("deteccion.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    emitida_en: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
