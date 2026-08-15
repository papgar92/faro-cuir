"""texto consolidado archivado y el diff en version_norma

Revision ID: f6b3d90c48a1
Revises: a9d3e6f10b52
Create Date: 2026-08-15 11:20:00.000000

Implementa el ADR 0018: el **texto anterior** de un artículo modificado sale de la legislación
consolidada del BOE, se archiva como un documento más (`tipo='consolidado'`) y el par
(texto_anterior, texto_nuevo) se guarda en `version_norma`, que existía vacía desde
`7f8c9d354e09`.

**ESCRITA A MANO, NO AUTOGENERADA**, como las seis anteriores. Y esta toca una CHECK —
`tipodocumento`, para admitir el tercer valor—, que es exactamente el caso donde el autogenerate
ha propuesto cinco veces borrar CHECKs ajenas, incluida `origenclasificacion` (ADR 0004). A mano
el problema no puede ni presentarse.

Comprobación obligatoria tras aplicar: las CHECK del proyecto **siguen siendo 13**
(`tipodocumento` se sustituye, no se suma) y `origenclasificacion` sigue viva.

    SELECT conrelid::regclass, conname FROM pg_constraint
    WHERE contype='c' AND conrelid <> 0 ORDER BY 1,2;

De las cinco columnas nuevas de `version_norma`, tres son **NOT NULL y sin `server_default`**
(`norma_afectada`, `documento_consolidado_id`, `version_derivacion`) y dos nullable (`bloque`,
`fecha_vigencia`). Eso es una decisión, no un descuido: la tabla está vacía —nunca se ha
poblado— así que no hay filas que rellenar, y un `server_default` haría posible insertar mañana
un diff sin decir sobre qué norma es ni de qué documento archivado salió. Si la tabla tuviera
filas, esta migración falla en vez de inventarles un valor; es el fallo ruidoso que se prefiere.

`version_norma` tiene un trigger que rechaza UPDATE y DELETE (`7f8c9d354e09`). Esto es DDL, no
DML: añadir columnas no lo dispara, y el trigger sigue vivo después. No se toca.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6b3d90c48a1"
down_revision: str | Sequence[str] | None = "a9d3e6f10b52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TIPOS_ANTES = ("sumario", "texto_norma")
_TIPOS_AHORA = ("sumario", "texto_norma", "consolidado")


def _lista(valores: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


def upgrade() -> None:
    """Upgrade schema."""
    # --- documento.tipo admite 'consolidado' ------------------------------------------------
    # Se SUSTITUYE la CHECK, no se añade otra: dos CHECK sobre la misma columna se cumplen en
    # AND, así que la vieja seguiría prohibiendo el valor nuevo y el fallo aparecería en el
    # primer INSERT, no aquí. Misma lección que la d4f2a8c61b90 con `estadoprefiltro`.
    op.drop_constraint("tipodocumento", "documento", type_="check")
    op.create_check_constraint("tipodocumento", "documento", f"tipo IN ({_lista(_TIPOS_AHORA)})")

    # --- version_norma: el diff, con su procedencia ------------------------------------------
    op.add_column(
        "version_norma", sa.Column("norma_afectada", sa.String(length=200), nullable=False)
    )
    op.add_column("version_norma", sa.Column("bloque", sa.String(length=100), nullable=True))
    op.add_column(
        "version_norma", sa.Column("documento_consolidado_id", sa.Integer(), nullable=False)
    )
    op.add_column("version_norma", sa.Column("fecha_vigencia", sa.Date(), nullable=True))
    op.add_column(
        "version_norma", sa.Column("version_derivacion", sa.String(length=20), nullable=False)
    )

    op.create_foreign_key(
        "fk_version_norma_documento_consolidado",
        "version_norma",
        "documento",
        ["documento_consolidado_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_version_norma_norma_afectada", "version_norma", ["norma_afectada"])
    op.create_index(
        "ix_version_norma_documento_consolidado_id", "version_norma", ["documento_consolidado_id"]
    )
    # La clave natural del diff. Es la que hace idempotente al servicio de versionado, y tiene
    # que estar en la base de datos y no solo en el `SELECT` previo del código: la tabla es de
    # solo inserción, así que una fila duplicada no se podría borrar después.
    op.create_unique_constraint(
        "uq_version_norma_bloque", "version_norma", ["norma_id", "norma_afectada", "bloque"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Antes de estrechar la CHECK hay que resolver las filas que usan el valor nuevo, o el ALTER
    # falla a mitad. Se borran las versiones primero porque apuntan a esos documentos con una FK
    # RESTRICT; y se borran, en vez de reetiquetarse como `texto_norma`, porque un consolidado
    # disfrazado de texto publicado es peor que no tenerlo: haría creer que el archivo conserva
    # lo que se publicó aquel día cuando conserva una elaboración posterior.
    #
    # **El trigger de inmutabilidad hay que desactivarlo para esto y no es una excepción a la
    # regla, es su límite.** `trg_version_norma_inmutable` (migración `7f8c9d354e09`) rechaza
    # todo DELETE sobre `version_norma`: esa garantía es para la aplicación, que jamás debe
    # reescribir el histórico. Una bajada de versión de esquema es otra cosa —está quitando la
    # columna que da sentido a esas filas— y sin desactivarlo el `downgrade` fallaría a mitad,
    # que es peor: dejaría el esquema a medio bajar. Se vuelve a activar acto seguido.
    op.execute(sa.text("ALTER TABLE version_norma DISABLE TRIGGER trg_version_norma_inmutable"))
    op.execute(
        sa.text(
            "DELETE FROM version_norma WHERE documento_consolidado_id IN "
            "(SELECT id FROM documento WHERE tipo = 'consolidado')"
        )
    )
    op.execute(sa.text("ALTER TABLE version_norma ENABLE TRIGGER trg_version_norma_inmutable"))
    op.execute(sa.text("DELETE FROM documento WHERE tipo = 'consolidado'"))

    op.drop_constraint("uq_version_norma_bloque", "version_norma", type_="unique")
    op.drop_index("ix_version_norma_documento_consolidado_id", table_name="version_norma")
    op.drop_index("ix_version_norma_norma_afectada", table_name="version_norma")
    op.drop_constraint(
        "fk_version_norma_documento_consolidado", "version_norma", type_="foreignkey"
    )
    op.drop_column("version_norma", "version_derivacion")
    op.drop_column("version_norma", "fecha_vigencia")
    op.drop_column("version_norma", "documento_consolidado_id")
    op.drop_column("version_norma", "bloque")
    op.drop_column("version_norma", "norma_afectada")

    op.drop_constraint("tipodocumento", "documento", type_="check")
    op.create_check_constraint("tipodocumento", "documento", f"tipo IN ({_lista(_TIPOS_ANTES)})")
