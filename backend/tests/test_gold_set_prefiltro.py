"""Etapa 1 evaluada contra el gold set (CLAUDE.md sección 7).

Hoy solo hay tres casos reales cargados (ver `gold_set/casos/`): esto no mide el recall del
prefiltro, mide que el mecanismo de carga y evaluación funciona de punta a punta. La cifra de
recall real solo existe con 150-200 casos, y hasta entonces el proyecto no la afirma (aviso de
S1 en CLAUDE.md sección 11). No convertir este test en una promesa de cobertura que el corpus
todavía no tiene.
"""

from __future__ import annotations

import pytest

from app.pipeline import prefiltro
from tests.gold_set.esquema import CasoGoldSet, cargar_casos

CASOS = cargar_casos()


def test_hay_casos_cargados() -> None:
    """Si esto falla, el loader se ha roto o el directorio se ha vaciado por accidente."""
    assert len(CASOS) >= 3


@pytest.mark.parametrize("caso", CASOS, ids=lambda c: c.identificador_oficial)
def test_prefiltro_coincide_con_la_etiqueta(caso: CasoGoldSet) -> None:
    resultado = prefiltro.evaluar(caso.titulo, organo_emisor=caso.organo_emisor)
    assert resultado.relevante == caso.es_relevante, (
        f"{caso.identificador_oficial}: se esperaba relevante={caso.es_relevante}, "
        f"dio {resultado.relevante} (términos: {resultado.terminos}). {caso.notas}"
    )
