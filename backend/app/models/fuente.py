import enum

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TipoFuente(enum.StrEnum):
    BOE = "boe"
    BOLETIN_AUTONOMICO = "boletin_autonomico"
    # Boletín Oficial de la Provincia. Es donde publican los ayuntamientos: una ordenanza
    # municipal no entra en vigor si no se publica íntegra aquí (Ley 5/2002). Ver ADR 0014.
    BOLETIN_PROVINCIAL = "boletin_provincial"
    PARLAMENTO = "parlamento"


class AmbitoTerritorial(enum.StrEnum):
    """Hasta dónde alcanza lo que publica una fuente. ADR 0014.

    **Eje independiente de `TipoFuente`, y por eso una columna aparte.** `tipo` dice qué clase
    de fuente es (un boletín provincial, un parlamento); el ámbito dice a qué nivel de
    administración alcanza lo que sale en ella. Meterlos en el mismo enum obligaría a enumerar
    el producto cartesiano y a inventar valores como `parlamento_autonomico` que no aportan.

    El caso que lo justifica de verdad son las **7 CCAA uniprovinciales** (Asturias, Cantabria,
    Illes Balears, Madrid, Murcia, Navarra, La Rioja): no tienen BOP, así que su boletín
    autonómico es a la vez `tipo=boletin_autonomico` y la vía por la que publican sus
    ayuntamientos. Una sola fuente cubriendo dos niveles solo se puede expresar si los dos ejes
    van separados.
    """

    ESTATAL = "estatal"
    AUTONOMICO = "autonomico"
    PROVINCIAL = "provincial"
    LOCAL = "local"


class FormatoFuente(enum.StrEnum):
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
    ccaa: Mapped[str | None] = mapped_column(String(100), index=True)
    # Código ISO 3166-2:ES de la comunidad ("AN", "CT", "PV"...). Va aparte del nombre porque
    # es la **clave de cruce** con el mapa del frontend, que ya trabaja con esos códigos. Cruzar
    # por el nombre visible es como se consiguen los fallos silenciosos: la misma comunidad
    # aparece como "Euskadi" en la interfaz y "País Vasco / Euskadi" en la auditoría, y un
    # desglose de cobertura que no encuentra sus fuentes no falla, simplemente enseña cero.
    ccaa_codigo: Mapped[str | None] = mapped_column(String(2), index=True)
    # A qué nivel de administración alcanza. NOT NULL: toda fuente tiene un ámbito, y dejarlo
    # opcional habría hecho que el desglose de cobertura por comunidad tuviera una categoría
    # "sin clasificar" que no significa nada.
    ambito_territorial: Mapped[AmbitoTerritorial] = mapped_column(
        Enum(
            AmbitoTerritorial,
            native_enum=False,
            length=20,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        index=True,
    )
    # Solo para las fuentes provinciales. Nulo en el BOE y en los boletines autonómicos,
    # incluidos los de las CCAA uniprovinciales: allí el boletín cubre la provincia entera
    # pero **no es** un boletín provincial, y rellenar esto sería afirmar lo contrario.
    provincia: Mapped[str | None] = mapped_column(String(100), index=True)
    # **Nulo mientras el formato de esa fuente esté TODO(verificar) en docs/fuentes.md.**
    # Pasa de NOT NULL a nullable con el ADR 0014, y el motivo importa: al registrar los 43
    # boletines provinciales se conoce su nombre y su URL (verificados contra el directorio
    # oficial) pero no su formato. Poner "html" en 43 filas porque es lo más probable sería
    # exactamente la invención que prohíbe la regla de oro 8, y encima una invención que
    # después se lee como dato auditado. NULL aquí significa "no comprobado", que es verdad.
    formato: Mapped[FormatoFuente | None] = mapped_column(
        Enum(
            FormatoFuente,
            native_enum=False,
            length=10,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
    url_base: Mapped[str] = mapped_column(String(500), nullable=False)
    # Nulo mientras la licencia de reutilización de esa fuente esté TODO(verificar).
    licencia_reutil: Mapped[str | None] = mapped_column(String(200))
    activa: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
