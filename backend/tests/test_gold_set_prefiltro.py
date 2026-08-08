"""Etapa 1 evaluada contra el gold set (CLAUDE.md secciones 7.2, 7.3 y 7.8).

Hoy solo hay tres casos reales cargados (ver `gold_set/casos/`): esto **no mide el recall del
prefiltro**, mide que el mecanismo de carga y evaluación funciona de punta a punta. La cifra de
recall real solo existe con decenas de casos, y hasta entonces el proyecto no la afirma (aviso
de S1 en CLAUDE.md sección 11). No convertir este test en una promesa de cobertura que el
corpus todavía no tiene.

## Lo que este test NO puede comprobar todavía, y por qué

Con la tarea 0.b, el gold set pasa a etiquetarse sobre el **texto íntegro** (7.8), que es lo que
decide 7.1. Pero el worker todavía no descarga texto íntegro — eso es la tarea 0.c — así que
aquí solo hay título y órgano emisor.

**Comparar una etiqueta hecha sobre el texto completo con una evaluación hecha sobre el título
sería comparar dos cosas distintas y llamarlo medición.** Así que este test comprueba la única
propiedad que sí se sostiene con la información disponible, y que además es la que importa:

> Ningún caso que deba pasar el filtro puede quedar **descartado** por su título.

Es un límite superior del recall, no el recall. Cuando exista 0.c, este fichero tiene que pasar
a comparar `prefiltro_esperado` contra la evaluación sobre el texto real, y solo entonces el
número que salga será una medida.
"""

from __future__ import annotations

import pytest

from app.models.norma import EstadoPrefiltro
from app.pipeline import prefiltro
from tests.gold_set.esquema import CasoGoldSet, cargar_casos

CASOS = cargar_casos()


def test_hay_casos_cargados() -> None:
    """Si esto falla, el loader se ha roto o el directorio se ha vaciado por accidente."""
    assert len(CASOS) >= 3


def test_todos_los_casos_usan_el_formato_definitivo() -> None:
    """Formato de 7.8, cerrado en la tarea 0.b.

    Este test es el que impide que se etiquete una tanda con el formato viejo. Etiquetar 200
    documentos dos veces es el peor uso posible del tiempo humano de anotación, que es el
    recurso más caro del proyecto — y el motivo de que 0.b fuera antes que el gold set.
    """
    sin_migrar = [c.identificador_oficial for c in CASOS if c.prefiltro_esperado is None]
    assert not sin_migrar, f"casos con el formato viejo: {sin_migrar}"


@pytest.mark.parametrize("caso", CASOS, ids=lambda c: c.identificador_oficial)
def test_el_titulo_no_descarta_lo_que_deberia_pasar(caso: CasoGoldSet) -> None:
    """El falso negativo es el único error que este proyecto no se puede permitir.

    Sobre el título solo, el prefiltro no puede devolver `DESCARTADA` de todos modos (7.1), así
    que este test comprueba también esa garantía de camino: si alguien la rompiera, aquí se
    vería sobre casos reales y no solo sobre ejemplos sintéticos.
    """
    resultado = prefiltro.evaluar(caso.titulo, organo_emisor=caso.organo_emisor)

    assert resultado.estado is not EstadoPrefiltro.DESCARTADA, (
        f"{caso.identificador_oficial}: descartada por su TÍTULO, y CLAUDE.md 7.1 dice que el "
        f"descarte definitivo solo ocurre tras leer el documento completo. {caso.notas}"
    )

    if caso.prefiltro_esperado == "relevante" and "lexico" in caso.ejes_esperados:
        # Un caso etiquetado como relevante por el eje léxico y cuyo título ya lo dice es lo
        # más barato de detectar que hay. Si esto falla, el vocabulario ha perdido un término.
        assert resultado.entra_en_la_cola, (
            f"{caso.identificador_oficial}: el título contiene la señal y aun así no entra en "
            f"la cola. {caso.notas}"
        )


@pytest.mark.parametrize("caso", CASOS, ids=lambda c: c.identificador_oficial)
def test_la_etiqueta_declara_sus_ejes(caso: CasoGoldSet) -> None:
    """Sin ejes esperados no se puede medir el recall **por eje** (7.3).

    Y esa es la pregunta que justifica el eje referencial entero: ¿aporta casos que el léxico
    no ve, o solo duplica? Un recall agregado no la contesta.
    """
    if caso.prefiltro_esperado in ("relevante", "sospecha"):
        assert caso.ejes_esperados, f"{caso.identificador_oficial}: falta por qué eje pasa"
    else:
        assert not caso.ejes_esperados


def test_el_corpus_no_es_suficiente_para_medir_recall() -> None:
    """Un test que existe para dejar constancia, no para comprobar código.

    Con tres casos no hay recall que publicar. Este test **falla a propósito el día que el
    corpus crezca**, y su mensaje dice qué hay que hacer entonces: no basta con tener más casos,
    hay que cambiar la forma de medir (comparar contra el texto íntegro, tarea 0.c) antes de
    afirmar ninguna cifra. Es la forma de que el aviso de la sección 11 no se olvide justo
    cuando deja de ser obvio.
    """
    assert len(CASOS) < 30, (
        "El corpus ha crecido. Antes de publicar NINGUNA cifra de recall: (1) el worker tiene "
        "que descargar texto íntegro (tarea 0.c) para poder comparar contra lo que se etiquetó, "
        "(2) el recall se reporta DESGLOSADO POR EJE (7.3) y (3) siempre con el tamaño de la "
        "muestra y su intervalo de confianza. Reescribe este test cuando eso esté."
    )
