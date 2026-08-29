"""semilla de la fuente BOA: la segunda autonómica

Revision ID: e3f7a1c92b64
Revises: d7b2c85fa419
Create Date: 2026-08-29 12:00:00.000000

ADR 0028. Da de alta el Boletín Oficial de Aragón como **tercera fuente del proyecto y segunda
autonómica**, y la deja **activa**, igual que hizo `c8a41d7e5f02` con el DOGC: activa significa
que tiene ingestor y se vigila de verdad, frente a las 43 filas provinciales de `c7e1b4a9d052`,
que están registradas y no vigiladas.

**ESCRITA A MANO, NO AUTOGENERADA.** No toca ninguna CHECK ni ninguna columna: es solo un
INSERT, así que el recuento de CHECK del proyecto **no cambia** al aplicarla (hoy 14; el
`SELECT ... FROM pg_constraint` de CLAUDE.md sección 10 debe dar lo mismo antes y después).

`formato='api'` y no `'html'`, el mismo valor que el BOE y el DOGC y por el mismo motivo: hay
una interfaz de datos —`SEC=OPENDATABOAXML` devuelve XML estructurado con el texto íntegro
dentro— y no una página que raspar.

La licencia **no se deduce**: el propio catálogo de datos abiertos de Aragón la declara como
`CC-BY-4.0` en el conjunto "Boletín Oficial de Aragón", comprobado el 2026-08-29 contra
`opendata.aragon.es/api/action/package_search`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3f7a1c92b64"
down_revision: str | Sequence[str] | None = "d7b2c85fa419"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOMBRE = "Boletín Oficial de Aragón"


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
            ccaa="Aragón",
            ambito_territorial="autonomico",
            # ISO 3166-2:ES, el mismo eje por el que cruza el mapa. Es también la clave con la
            # que `worker/run.py` elige la fila: si este código no cuadrara con el de la tabla
            # `FUENTES`, el worker archivaría el BOA bajo otro boletín.
            ccaa_codigo="AR",
            provincia=None,
            formato="api",
            # El portal del diario. Las URL exactas del sumario y del cuerpo las compone
            # `ingest/boa.py`; aquí va la base, que es lo que identifica al boletín.
            url_base="https://www.boa.aragon.es/",
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
    op.execute(sa.text("DELETE FROM fuente WHERE nombre = :nombre").bindparams(nombre=_NOMBRE))
