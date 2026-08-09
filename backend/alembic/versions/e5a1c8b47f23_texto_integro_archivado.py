"""texto íntegro archivado: documento.tipo y norma.documento_texto_id

Revision ID: e5a1c8b47f23
Revises: d4f2a8c61b90
Create Date: 2026-08-09 12:00:00.000000

Tarea 0.c de CLAUDE.md. Implementa el ADR 0015: el cuerpo de cada norma se archiva como una
fila más de `documento`, con `tipo='texto_norma'`, y `norma.documento_texto_id` apunta a ella.

**ESCRITA A MANO, NO AUTOGENERADA.** Es la tercera seguida, y por el motivo de siempre: el
`autogenerate` lleva cinco intentos de borrar CHECKs generadas por
`Enum(native_enum=False, create_constraint=True)`, incluida `origenclasificacion`, que es la
que hace que el veredicto del LLM no sea representable (ADR 0004). Esta migración **añade** una
CHECK (`tipodocumento`) y no toca ninguna existente.

Comprobación obligatoria tras aplicar: las CHECK del proyecto pasan de 12 a **13** —una más,
`tipodocumento`, ninguna menos— y `origenclasificacion` sigue viva.

    SELECT conrelid::regclass, conname FROM pg_constraint WHERE contype='c' ORDER BY 1,2;

**Ojo al contar con esa consulta: devuelve 14, no 12.** Dos de las filas
(`cardinal_number_domain_check` y `yes_or_no_check`) son de `information_schema`, las pone
PostgreSQL y no tienen tabla propia — salen con `-` en la columna `tabla`. Las del proyecto son
las 12 que sí la tienen, y tras esta migración son 13. Se deja escrito aquí porque quien
compare el total contra el "12" de CLAUDE.md va a pensar que sobran dos y que algo se ha
duplicado; el filtro honesto es `WHERE contype='c' AND conrelid <> 0`.

**Ningún UPDATE de datos aquí más allá del relleno del discriminador.** `documento.tipo` entra
con `server_default='sumario'`, que es lo que las filas existentes son: hasta hoy la única cosa
que se archivaba era el sumario del día. `norma.documento_texto_id` entra en NULL para todas, y
eso no es un hueco: **es la cola de trabajo de la fase 2**, que el worker drena con
`--fase2`. Rellenarla desde aquí exigiría descargar del BOE dentro de una migración, que es
justo donde no debe vivir una decisión de pipeline.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5a1c8b47f23"
down_revision: str | Sequence[str] | None = "d4f2a8c61b90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TIPOS = ("sumario", "texto_norma")


def upgrade() -> None:
    """Upgrade schema."""
    # --- documento.tipo -------------------------------------------------------------------
    # `server_default` y NOT NULL en el mismo paso: sin el default, añadir una columna NOT NULL
    # a una tabla con filas falla; con él, las filas existentes quedan marcadas como 'sumario',
    # que es exactamente lo que son.
    op.add_column(
        "documento",
        sa.Column("tipo", sa.String(length=20), nullable=False, server_default="sumario"),
    )
    op.create_check_constraint(
        "tipodocumento", "documento", "tipo IN ({})".format(", ".join(f"'{t}'" for t in _TIPOS))
    )
    # Toda consulta de la API filtra por esta columna y los cuerpos van a ser dos órdenes de
    # magnitud más numerosos que los sumarios: sin índice, listar sumarios pasa a ser un
    # recorrido completo de la tabla en cuanto la fase 2 lleve unas semanas corriendo.
    op.create_index("ix_documento_tipo", "documento", ["tipo"])

    # --- norma.documento_texto_id ---------------------------------------------------------
    # Segunda FK de `norma` a `documento` (ADR 0015). Nullable a propósito: NULL significa
    # "cuerpo no descargado todavía" y es la condición que define la cola de la fase 2.
    op.add_column("norma", sa.Column("documento_texto_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_norma_documento_texto",
        "norma",
        "documento",
        ["documento_texto_id"],
        ["id"],
        # RESTRICT como el resto del modelo: el archivo no se borra en cascada por accidente.
        ondelete="RESTRICT",
    )
    op.create_index("ix_norma_documento_texto_id", "norma", ["documento_texto_id"])

    # --- norma.prefiltro_version_texto ----------------------------------------------------
    # Con qué versión de `pipeline/texto.texto_plano` se derivó el cuerpo evaluado, o NULL si
    # se evaluó solo sobre el título. Entra en NULL para todas las filas y es correcto: todo
    # lo evaluado hasta hoy lo fue sobre el título. Esa misma NULL es lo que hace que el
    # reprefiltrado las vuelva a mirar en cuanto tengan cuerpo.
    op.add_column(
        "norma", sa.Column("prefiltro_version_texto", sa.String(length=20), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("norma", "prefiltro_version_texto")

    op.drop_index("ix_norma_documento_texto_id", table_name="norma")
    op.drop_constraint("fk_norma_documento_texto", "norma", type_="foreignkey")
    op.drop_column("norma", "documento_texto_id")

    # Las filas de cuerpos se borran antes de quitar el discriminador. No es limpieza
    # cosmética: sin `tipo` no hay forma de distinguirlas de los sumarios, así que dejarlas
    # convertiría cientos de cuerpos en sumarios falsos y `GET /api/documentos` los listaría
    # como boletines. El fichero del almacén no se toca — el archivo de 6.5 no se borra en un
    # downgrade de esquema, y volver a subir de versión los vuelve a enlazar sin red.
    op.execute(sa.text("DELETE FROM documento WHERE tipo = 'texto_norma'"))

    op.drop_index("ix_documento_tipo", table_name="documento")
    op.drop_constraint("tipodocumento", "documento", type_="check")
    op.drop_column("documento", "tipo")
