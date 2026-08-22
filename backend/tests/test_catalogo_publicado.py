"""El catálogo que se publica en la web tiene que ser el catálogo que clasifica.

`CLAUDE.md` 7.6 exige que «una alerta publicada tiene que poder reconstruirla un tercero leyendo la
regla y el texto archivado, sin ejecutar nuestro código». Para cumplirlo, la interfaz publica los
enunciados de las reglas en `frontend/src/lib/reglas.ts`.

**Ese fichero es una traducción a castellano, no la fuente**, y una traducción se desincroniza
sola: alguien añade una regla en `pipeline/reglas.py`, sube `VERSION_REGLAS`, y el glosario de la
web sigue explicando el catálogo del mes pasado con aire de autoridad. Eso es peor que no tener
glosario, porque un tercero que audite una alerta leerá una regla que no es la que se le aplicó.

Este test es el único control que lo impide. No comprueba que los enunciados sean *buenos* —eso no
lo puede comprobar una máquina— sino las dos cosas que sí son verificables: que la versión coincide
y que están todas las reglas y ninguna de más.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.pipeline import reglas

# Dos sitios donde puede estar, y hacen falta los dos:
#   * Desde `backend/tests/` hacia la raíz del repositorio. Es como lo ve **CI**, que hace
#     checkout completo y lanza pytest desde `backend/` — ahí es donde este control tiene que
#     cumplirse sí o sí, porque es la puerta que impide mergear el desfase.
#   * `/frontend` dentro del contenedor de backend, montado en SOLO LECTURA por el compose. Sin
#     eso, en local el test se saltaba siempre: `/app` es `backend/` y el frontend no existe
#     dentro. Un control que solo corre en CI se descubre roto tarde y con el commit ya hecho.
_CANDIDATOS = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "reglas.ts",
    Path("/frontend/src/lib/reglas.ts"),
)
CATALOGO_TS = next((ruta for ruta in _CANDIDATOS if ruta.exists()), None)


@pytest.fixture(scope="module")
def fuente_ts() -> str:
    if CATALOGO_TS is None:
        # `skip` y no `fail`: que el arbol del frontend no este montado no significa que el
        # catalogo este mal. El motivo se escribe entero para que nadie lea el salto como un
        # aprobado — en CI este test NO se salta nunca, porque alli el fichero siempre esta.
        pytest.skip(
            "No se encuentra frontend/src/lib/reglas.ts desde aquí "
            f"(probado: {', '.join(str(r) for r in _CANDIDATOS)}). En CI sí existe y el control "
            "se aplica; en local, monta el frontend en el contenedor o lanza pytest desde el host."
        )
    return CATALOGO_TS.read_text(encoding="utf-8")


def test_la_version_publicada_es_la_que_clasifica(fuente_ts: str) -> None:
    """Un enunciado sin la versión correcta no sirve para auditar.

    Las reglas cambian y una alerta de hace un mes se clasificó con el catálogo de hace un mes. Si
    la web publica otra versión, quien audite comparará contra el criterio equivocado.
    """
    encontrado = re.search(r'VERSION_REGLAS_PUBLICADA\s*=\s*"([^"]+)"', fuente_ts)
    assert encontrado is not None, "Falta `VERSION_REGLAS_PUBLICADA` en el catálogo publicado."
    assert encontrado.group(1) == reglas.VERSION_REGLAS, (
        f"El catálogo publicado dice {encontrado.group(1)!r} y el que clasifica es "
        f"{reglas.VERSION_REGLAS!r}. Si has tocado una regla, actualiza también los enunciados de "
        "frontend/src/lib/reglas.ts: la web estaría explicando un criterio que ya no se aplica."
    )


def test_estan_todas_las_reglas_y_ninguna_de_mas(fuente_ts: str) -> None:
    """Ni faltan ni sobran.

    Que falte una es publicar una alerta cuyo `regla_aplicada` no se puede consultar. Que sobre una
    es explicar un criterio que el sistema no aplica, lo cual es peor: es describir una vigilancia
    que no existe, que es justo lo que este proyecto se dedica a detectar en otros.
    """
    # Los identificadores reales salen del módulo, no de una lista escrita a mano aquí: si se
    # añade una regla nueva a `reglas.py`, este test la exige sin que nadie tenga que acordarse.
    del_codigo = {
        valor
        for nombre, valor in vars(reglas).items()
        if nombre.startswith("R_") and isinstance(valor, str) and valor.startswith("R-")
    }
    publicados = set(re.findall(r'id:\s*"(R-[A-Z]+-\d+)"', fuente_ts))

    assert del_codigo, "No se ha encontrado ninguna constante de regla en pipeline/reglas.py."
    assert publicados == del_codigo, (
        f"Sin publicar: {sorted(del_codigo - publicados)}. "
        f"Publicadas y no existentes: {sorted(publicados - del_codigo)}."
    )


def test_cada_regla_publicada_dice_que_signo_emite(fuente_ts: str) -> None:
    """Tres de las cinco reglas se abstienen, y eso hay que decirlo en cada una.

    Si el glosario no dice qué signo emite cada regla, quien lea una alerta `indeterminado`
    pensará que el sistema no supo, cuando lo que pasa es que la regla **decidió no afirmar**. Es
    la diferencia entre no saber y no poder sostenerlo, y es medio proyecto.
    """
    bloques = re.findall(r'id:\s*"(R-[A-Z]+-\d+)".*?signo:\s*\n?\s*"', fuente_ts, re.DOTALL)
    publicados = re.findall(r'id:\s*"(R-[A-Z]+-\d+)"', fuente_ts)
    assert set(bloques) == set(publicados), (
        f"Alguna regla publicada no declara su signo: {sorted(set(publicados) - set(bloques))}"
    )
