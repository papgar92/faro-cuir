"""cuándo se intentó versionar cada norma, y cuántas veces

Revision ID: d1e5c93a7b48
Revises: c8a41d7e5f02
Create Date: 2026-08-17 10:15:00.000000

Arregla el **hallazgo 1 (ALTO)** de la auditoría de `revisor-seguridad` del 2026-08-16: la cola
del versionado (ADR 0018) se ordenaba por `norma.id` ascendente y el tope por ejecución se
aplicaba sobre esa lista. Las parejas irresolubles —derogaciones totales, consolidados que nunca
incorporarán el cambio, fallos permanentes— **nunca salen de la cola y ocupan siempre las
primeras posiciones**, así que con veinte de ellas el versionado dejaría de mirar lo nuevo y el
resumen seguiría diciendo «20 consultadas» tan tranquilo. Hoy hay una; con 61 fuentes en el
horizonte, veinte es cuestión de semanas.

Con estas dos columnas la cola se ordena por **quién lleva más tiempo sin intentarse**, así que
una pareja muerta se reintenta igual pero **al final**, y nunca desplaza a una norma nueva.

**ESCRITA A MANO, NO AUTOGENERADA.** No toca ninguna CHECK: son dos columnas. Las del proyecto
siguen siendo 13 después.

`versionado_intentos` lleva `server_default='0'` y `versionado_intentado_en` no lleva ninguno, y
la diferencia es deliberada: cero intentos es la verdad de todas las filas existentes, pero una
fecha inventada haría creer que se intentaron. NULL significa «nunca se ha intentado», que es lo
que ordena primero.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e5c93a7b48"
down_revision: str | Sequence[str] | None = "c8a41d7e5f02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "norma", sa.Column("versionado_intentado_en", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "norma",
        sa.Column("versionado_intentos", sa.Integer(), nullable=False, server_default="0"),
    )
    # El índice es el que hace barata la ordenación de la cola, que se recorre entera en cada
    # pasada. `NULLS FIRST` es el orden por defecto de PostgreSQL para ASC, y es justo el que se
    # quiere: lo nunca intentado va primero.
    op.create_index("ix_norma_versionado_intentado_en", "norma", ["versionado_intentado_en"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_norma_versionado_intentado_en", table_name="norma")
    op.drop_column("norma", "versionado_intentos")
    op.drop_column("norma", "versionado_intentado_en")
