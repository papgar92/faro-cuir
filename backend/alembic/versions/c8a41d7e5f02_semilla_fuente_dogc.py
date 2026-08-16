"""semilla de la fuente DOGC: la primera autonómica

Revision ID: c8a41d7e5f02
Revises: f6b3d90c48a1
Create Date: 2026-08-16 18:40:00.000000

ADR 0019. Da de alta el Diari Oficial de la Generalitat de Catalunya como **segunda fuente del
proyecto y primera autonómica**, y la deja **activa**, que es lo que la distingue de las 43 filas
provinciales sembradas por `c7e1b4a9d052`: aquellas están registradas y no vigiladas (`activa`
en falso), esta se vigila de verdad porque tiene ingestor.

**ESCRITA A MANO, NO AUTOGENERADA**, como las siete anteriores. No toca ninguna CHECK ni ninguna
columna: es solo un INSERT, así que las CHECK del proyecto **siguen siendo 13** después.

`formato='api'` y no `'html'`: el sumario es JSON y el texto íntegro XML, los dos por HTTP y sin
clave. Es el mismo valor que lleva el BOE y significa lo mismo — que hay una interfaz de datos, no
una página que raspar.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8a41d7e5f02"
down_revision: str | Sequence[str] | None = "f6b3d90c48a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOMBRE = "Diari Oficial de la Generalitat de Catalunya"


def upgrade() -> None:
    """Upgrade schema."""
    fuente = sa.table(
        "fuente",
        sa.column("nombre", sa.String),
        sa.column("tipo", sa.String),
        sa.column("ccaa", sa.String),
        sa.column("ambito_territorial", sa.String),
        sa.column("ccaa_codigo", sa.String),
        sa.column("provincia", sa.String),
        sa.column("formato", sa.String),
        sa.column("url_base", sa.String),
        sa.column("licencia_reutil", sa.String),
        sa.column("activa", sa.Boolean),
    )
    op.execute(
        fuente.insert().values(
            nombre=_NOMBRE,
            tipo="boletin_autonomico",
            ccaa="Cataluña",
            ambito_territorial="autonomico",
            # ISO 3166-2:ES, el mismo eje por el que cruza el mapa. Cruzar por el nombre visible
            # es como se consiguen los fallos silenciosos (ver `c7e1b4a9d052`).
            ccaa_codigo="CT",
            provincia=None,
            formato="api",
            # El portal donde vive la fuente. La URL exacta del sumario y del texto íntegro las
            # compone `ingest/dogc.py`; aquí va la base, que es lo que identifica al boletín.
            url_base="https://portaljuridic.gencat.cat/",
            # Dato abierto de la Generalitat. Se anota la licencia declarada y no se deduce:
            # `TODO(verificar)` sería más honesto que inventarla, pero aquí está publicada.
            licencia_reutil="CC BY 4.0",
            activa=True,
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Solo la fila de la fuente. **Los documentos y normas ingeridos NO se borran**: son archivo
    # con su huella y su sello (6.5), y una bajada de versión de esquema no es motivo para
    # destruir lo que se archivó. Si la FK lo impide, es que hay datos, y entonces el borrado
    # tiene que decidirlo una persona mirándolos.
    op.execute(sa.text(f"DELETE FROM fuente WHERE nombre = '{_NOMBRE}'"))
