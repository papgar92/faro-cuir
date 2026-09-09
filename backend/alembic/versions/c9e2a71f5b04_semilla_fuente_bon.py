"""semilla de la fuente BON: la sexta autonómica y la primera del nivel HTML

Revision ID: c9e2a71f5b04
Revises: b3d5f80a1c47
Create Date: 2026-09-06 19:00:00.000000

ADR 0036. Da de alta el Boletín Oficial de Navarra como **séptima fuente del proyecto y sexta
autonómica**, activa.

**ESCRITA A MANO, NO AUTOGENERADA.** No toca ninguna CHECK ni ninguna columna: es solo un
INSERT, así que el recuento de CHECK del proyecto **no cambia** al aplicarla (hoy 15; el
`SELECT ... FROM pg_constraint` de CLAUDE.md sección 10 debe dar lo mismo antes y después).

**`formato='html'`, y por primera vez esa columna dice literalmente la verdad de dónde sale el
texto que el sistema analiza.** En el BOCYL se anotó `api` porque el sumario era HTML pero el
articulado venía en XML (ADR 0029); aquí el articulado **es** la página. Es la fuente que
estrena el nivel HTML de `pipeline/texto_html.py`, con sus tres obligaciones: contenedor
declarado, canario de tamaño y caída a `ilegible` si cualquiera de las dos falla.

Que se vea en esta columna importa fuera del código: la página de cobertura la publica, así que
quien mire la web puede saber que la evidencia de Navarra se recorta de una página y no de un
documento estructurado. Esconderlo detrás de un `api` cómodo sería lo contrario de la 6.9.6.

**La licencia se deja en `TODO(verificar)`, no se deduce** (regla de oro 8). No se localizó una
declaración de reutilización en la comprobación del 2026-09-06.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9e2a71f5b04"
down_revision: str | Sequence[str] | None = "b3d5f80a1c47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOMBRE = "Boletín Oficial de Navarra"


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
            ccaa="Comunidad Foral de Navarra",
            ambito_territorial="autonomico",
            # ISO 3166-2:ES, el mismo eje por el que cruza el mapa, y la clave con la que
            # `worker/run.py` elige la fila. Si no cuadrara con la tabla `FUENTES`, el worker
            # archivaría el BON bajo otro boletín.
            ccaa_codigo="NC",
            provincia=None,
            formato="html",
            url_base="https://bon.navarra.es/",
            licencia_reutil="TODO(verificar)",
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
