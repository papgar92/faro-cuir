"""prefiltro lexico en norma

Revision ID: ae3da0c963fe
Revises: 7f8c9d354e09
Create Date: 2026-08-06 20:10:22.021974

Guarda el resultado de la etapa 1 del pipeline (CLAUDE.md sección 7) en `norma`.

NOTA SOBRE EL AUTOGENERATE (cuarta vez, ver CLAUDE.md sección 11): el autogenerate propuso
además borrar OCHO restricciones CHECK —`estadorevision`, `clasificacion`,
`origenclasificacion`, `estadopipeline`, `formatofuente`, `tipofuente`, `ambitonorma` y
`rangonorma`—. No es un cambio real: son las CHECK que genera `Enum(native_enum=False,
create_constraint=True)`, que alembic no sabe reconocer en la base de datos y da por
eliminadas en cada migración. Esas líneas se han quitado a mano.

Aquí importa más que de costumbre: entre ellas estaba `origenclasificacion`, que es
justamente la CHECK que hace que el veredicto del LLM no sea representable en el esquema
(ADR 0004). Aplicar el autogenerate tal cual no habría sido un ruido cosmético, habría
desarmado un control del proyecto.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ae3da0c963fe"
down_revision: str | Sequence[str] | None = "7f8c9d354e09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Añade las columnas del prefiltro a `norma`."""
    op.add_column(
        "norma",
        sa.Column(
            "prefiltro_estado",
            sa.Enum(
                "pendiente",
                "relevante",
                "descartada",
                name="estadoprefiltro",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            # Las normas ya ingeridas quedan en 'pendiente', no en 'descartada': nadie las ha
            # evaluado todavía y decir lo contrario sería afirmar algo que no ha ocurrido.
            server_default="pendiente",
            nullable=False,
        ),
    )
    op.add_column("norma", sa.Column("prefiltro_terminos", sa.JSON(), nullable=True))
    op.add_column("norma", sa.Column("prefiltro_version", sa.String(length=20), nullable=True))
    op.add_column(
        "norma", sa.Column("prefiltro_evaluado_en", sa.DateTime(timezone=True), nullable=True)
    )
    # El worker consulta por estado para saber qué queda por evaluar y qué pasa al extractor.
    op.create_index(op.f("ix_norma_prefiltro_estado"), "norma", ["prefiltro_estado"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_norma_prefiltro_estado"), table_name="norma")
    op.drop_column("norma", "prefiltro_evaluado_en")
    op.drop_column("norma", "prefiltro_version")
    op.drop_column("norma", "prefiltro_terminos")
    op.drop_column("norma", "prefiltro_estado")
