"""qué vigiladas toca cada norma, persistido: el versionado deja de releer el archivo

Revision ID: d1f4b62e830c
Revises: c9e2a71f5b04
Create Date: 2026-09-12 21:30:00.000000

ADR 0039. Añade dos columnas a `norma` y **no toca ninguna otra cosa**.

**ESCRITA A MANO, NO AUTOGENERADA** (7.2, aviso de migración): el autogenerate ha propuesto
borrar CHECKs ajenas cinco veces en este proyecto. Aquí no hay ninguna CHECK implicada, así que
el recuento del `SELECT ... FROM pg_constraint` de la sección 10 **tiene que dar 15 antes y 15
después**. Si da otra cosa, algo se ha colado.

Las dos columnas:

- `referencias_watchlist` (JSON, nullable) — qué normas vigiladas modifica esta, por
  identificador. El prefiltro ya lo calculaba desde el ADR 0022 y lo tiraba por no tener dónde
  guardarlo.
- `referencias_watchlist_version` (varchar 20, nullable) — con qué versión de la watchlist se
  calculó. Va aparte de `prefiltro_version_watchlist` porque esta columna también la rellena el
  versionado cuando encuentra un NULL, y escribir en aquella desde allí afirmaría que se
  reevaluó el prefiltro entero.

**Nullable y sin relleno, a propósito.** Las ~84.000 filas existentes quedan a NULL, que es
justamente lo que significa: «no se sabe». Rellenarlas aquí exigiría leer sus cuerpos del
almacén —lo que esta migración existe para no tener que hacer— y encima dentro de una
transacción de esquema. Se pueblan solas: el prefiltro al reevaluar, y el versionado al pasar
por una de ellas (una lectura cada una, y nunca más).

`downgrade` borra las dos columnas y se pierde el dato cacheado. No es pérdida real: se puede
recalcular desde el archivo, que es de donde salió.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1f4b62e830c"
down_revision: str | Sequence[str] | None = "c9e2a71f5b04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("norma", sa.Column("referencias_watchlist", sa.JSON(), nullable=True))
    op.add_column(
        "norma", sa.Column("referencias_watchlist_version", sa.String(length=20), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("norma", "referencias_watchlist_version")
    op.drop_column("norma", "referencias_watchlist")
