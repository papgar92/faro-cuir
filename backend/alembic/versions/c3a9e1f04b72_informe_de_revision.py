"""informe de apoyo para el gate humano

Revision ID: c3a9e1f04b72
Revises: b8d2e40a71c5
Create Date: 2026-08-20 21:30:00.000000

ADR 0025. Una tabla nueva para el informe que un asistente de IA prepara sobre cada ítem de la
cola de revisión: semáforo, resumen, citas, recomendación y **qué la refutaría**.

**ESCRITA A MANO, NO AUTOGENERADA**, como todas las que tocan este esquema. Aquí el riesgo no es
`estadoprefiltro` sino el contrario: el autogenerate no sabe que esta tabla **no debe** tener
ninguna relación con `deteccion.clasificacion`, y esa ausencia es el ADR entero.

Comprobación obligatoria tras aplicar: las CHECK del proyecto pasan de 14 a **15** —entra
`semaforo`, y no se sustituye ninguna— y `origenclasificacion` sigue viva. Es la que impide que
lo que escribe un modelo acabe siendo lo que el sistema afirma (ADR 0004).

    SELECT conrelid::regclass, conname FROM pg_constraint
    WHERE contype='c' AND conrelid <> 0 ORDER BY 1,2;

`ON DELETE CASCADE` y no `RESTRICT`, al revés que en el resto del esquema, y es deliberado: el
informe **no es archivo**. Si el ítem de la cola desapareciera, su material de trabajo no tiene
por qué sobrevivirle; lo que sí es archivo —el documento, su huella, el diff— vive en otras
tablas y ahí sigue siendo intocable.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3a9e1f04b72"
down_revision: str | Sequence[str] | None = "b8d2e40a71c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SEMAFOROS = ("alerta", "mirar", "descartar")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "informe_revision",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cola_revision_id", sa.Integer(), nullable=False),
        sa.Column("semaforo", sa.String(length=20), nullable=False),
        sa.Column("resumen", sa.Text(), nullable=False),
        sa.Column("a_quien_afecta", sa.Text(), nullable=True),
        sa.Column("recomendacion", sa.Text(), nullable=False),
        # NOT NULL a propósito: un informe sin «qué me refutaría» es un sello de goma, y el
        # esquema es el sitio donde eso se impide de verdad.
        sa.Column("refutacion", sa.Text(), nullable=False),
        sa.Column("citas", sa.JSON(), nullable=False),
        sa.Column("generado_por", sa.String(length=120), nullable=False),
        sa.Column(
            "generado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["cola_revision_id"], ["cola_revision.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # Uno por ítem: rehacer un informe lo sustituye, no lo duplica.
        sa.UniqueConstraint("cola_revision_id", name="uq_informe_cola"),
        sa.CheckConstraint(
            "semaforo IN (" + ", ".join(f"'{s}'" for s in _SEMAFOROS) + ")", name="semaforo"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Se pierden los informes y no pasa nada: no son archivo, son material de trabajo. Ninguna
    # alerta cambia de signo por esto, que es justo lo que el ADR 0025 quería garantizar.
    op.drop_table("informe_revision")
