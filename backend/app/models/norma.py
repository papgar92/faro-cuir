from __future__ import annotations

import datetime
import enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.documento import Documento


class RangoNorma(enum.StrEnum):
    LEY = "ley"
    DECRETO = "decreto"
    ORDEN = "orden"
    INSTRUCCION = "instruccion"
    RESOLUCION = "resolucion"
    PROPOSICION = "proposicion"


class AmbitoNorma(enum.StrEnum):
    """Ámbito sobre el que actúa la norma. Vocabulario de CLAUDE.md sección 5.

    Estos son los ámbitos donde el retroceso silencioso se materializa en la práctica: la
    cartera de servicios sanitarios, el currículo educativo, el acceso al empleo, y el
    procedimiento de rectificación registral de sexo y nombre (`documental`).
    """

    SANITARIO = "sanitario"
    EDUCATIVO = "educativo"
    LABORAL = "laboral"
    DOCUMENTAL = "documental"
    DEPORTIVO = "deportivo"
    GENERAL = "general"


class EstadoPrefiltro(enum.StrEnum):
    """Resultado de la etapa 1 del pipeline sobre una norma (CLAUDE.md sección 7).

    Vive aquí y no en `pipeline/prefiltro.py` para que la dependencia vaya en la dirección
    correcta: el pipeline conoce el modelo, no al revés.

    `PENDIENTE` es un estado real, no un hueco: una norma ingerida antes de que existiera el
    prefiltro —o después de subir la versión del vocabulario— está sin evaluar, y eso no es
    lo mismo que estar descartada.
    """

    PENDIENTE = "pendiente"
    RELEVANTE = "relevante"
    DESCARTADA = "descartada"


class Norma(Base):
    """Un ítem normativo identificado dentro de un documento. CLAUDE.md sección 5."""

    __tablename__ = "norma"
    __table_args__ = (
        # Un mismo documento no puede traer dos veces el mismo identificador oficial. Igual
        # que en `documento`, es lo que hace que reprocesar un sumario no duplique filas.
        UniqueConstraint("documento_id", "identificador_oficial", name="uq_norma_doc_ident"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    documento_id: Mapped[int] = mapped_column(
        ForeignKey("documento.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # No está en la lista de la sección 5, se añade porque la ingesta ya lo produce: es el
    # identificador que da la fuente a cada ítem del sumario (p. ej. "BOE-A-2024-26484") y sin
    # él no hay forma estable de reconocer que un ítem ya se había visto.
    identificador_oficial: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    titulo: Mapped[str] = mapped_column(Text, nullable=False)
    # También añadido: la URL del texto completo que publica el sumario. Es lo que el pipeline
    # descargará (vía url_guard) solo para las normas que pasen el prefiltro léxico.
    url_texto: Mapped[str | None] = mapped_column(String(1000))

    # Nulos hasta que el extractor los determine. Al ingerir un sumario solo tenemos el
    # título; deducir el rango o el ámbito de él a ojo sería justo el tipo de invención que
    # prohíbe la regla de oro 8. Mejor NULL explícito que un valor plausible inventado.
    rango: Mapped[RangoNorma | None] = mapped_column(
        Enum(
            RangoNorma,
            native_enum=False,
            length=20,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
    organo_emisor: Mapped[str | None] = mapped_column(String(300))
    ambito: Mapped[AmbitoNorma | None] = mapped_column(
        Enum(
            AmbitoNorma,
            native_enum=False,
            length=20,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        index=True,
    )

    # --- Etapa 1 del pipeline: prefiltro léxico -------------------------------------------
    # Se guarda el resultado en vez de recalcularlo al vuelo, aunque el filtro sea
    # determinista y barato, porque lo que importa no es el veredicto sino poder sostenerlo:
    # con qué vocabulario se evaluó, qué término disparó y cuándo. Recalculando, "esta norma
    # se descartó el día 3" dejaría de ser comprobable en cuanto cambiara el diccionario.
    prefiltro_estado: Mapped[EstadoPrefiltro] = mapped_column(
        Enum(
            EstadoPrefiltro,
            native_enum=False,
            length=20,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=EstadoPrefiltro.PENDIENTE,
        server_default=EstadoPrefiltro.PENDIENTE.value,
        index=True,
    )
    # Términos del vocabulario que hicieron saltar la norma. JSON genérico y no JSONB: aquí
    # no se consulta por contenido, solo se lee junto a su fila; JSONB añadiría un tipo
    # específico del dialecto a cambio de nada.
    prefiltro_terminos: Mapped[list[str] | None] = mapped_column(JSON)
    # Versión del vocabulario con la que se evaluó. Es lo que permite saber qué normas hay
    # que reevaluar cuando el diccionario cambia.
    prefiltro_version: Mapped[str | None] = mapped_column(String(20))
    prefiltro_evaluado_en: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))

    documento: Mapped[Documento] = relationship(back_populates="normas")


class VersionNorma(Base):
    """Versionado de una norma: aquí vive el diff. CLAUDE.md sección 5.

    **El histórico es inmutable.** No es una convención de código: la migración instala un
    trigger en PostgreSQL que rechaza cualquier UPDATE o DELETE sobre esta tabla. Esa
    inmutabilidad es parte del valor del proyecto — si el archivo de lo que se publicó se
    pudiera editar después, no serviría como archivo. Corregir un error significa insertar
    una versión nueva que lo diga, nunca reescribir la anterior.
    """

    __tablename__ = "version_norma"

    id: Mapped[int] = mapped_column(primary_key=True)
    norma_id: Mapped[int] = mapped_column(
        ForeignKey("norma.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Encadenamiento: una norma que modifica a otra genera una versión nueva que apunta a la
    # anterior. NULL en la primera versión conocida de una norma.
    version_anterior_id: Mapped[int | None] = mapped_column(
        ForeignKey("version_norma.id", ondelete="RESTRICT"), index=True
    )
    # Número de orden dentro de la norma, para poder recorrer el histórico sin depender de
    # los ids autoincrementales.
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # El diff, artículo a artículo. `articulo` es el identificador dentro de la norma
    # ("art. 3.2", "disposición adicional segunda"); se guarda como texto libre porque la
    # forma de citar varía entre boletines y normalizarla sería inventar una taxonomía.
    articulo: Mapped[str | None] = mapped_column(String(300))
    # NULL en una alta (no había texto anterior) y en una derogación (no hay texto nuevo).
    # La combinación de cuál de los dos es NULL es, de hecho, la señal más limpia de si el
    # cambio es un alta, una modificación o una derogación.
    texto_anterior: Mapped[str | None] = mapped_column(Text)
    texto_nuevo: Mapped[str | None] = mapped_column(Text)

    creada_en: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
