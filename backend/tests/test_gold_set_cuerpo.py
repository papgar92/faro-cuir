"""El gold set evaluado sobre el **texto íntegro archivado**. CLAUDE.md 7.1, 7.3 y 7.8.

Esto es lo que convierte el corpus en una medición. `test_gold_set_prefiltro.py` evalúa sobre el
**título** y por eso solo puede comprobar el límite superior del recall: que ningún caso se
descarte antes de leer el documento. Aquí se evalúa lo que de verdad decide el pipeline desde el
ADR 0011 —el cuerpo entero— y por eso aquí sí se puede contestar la pregunta que justifica el eje
referencial: ¿aporta casos que el léxico no ve, o solo duplica?

**Se salta entero si no hay almacén**, igual que `TestDocumentoRealCompleto` en `test_reglas.py`:
`backend/data/` está en `.gitignore` y en CI no existe. Un test que se salta diciendo por qué es
mejor que uno que no existe, y mucho mejor que uno que finge medir con datos sintéticos.

## Qué falla y qué solo se informa, que no es lo mismo

- **Falla**: que un caso etiquetado para entrar en la cola no entre, o al revés. Es la decisión
  irreversible del pipeline —lo descartado no lo mira nadie más— y el único error que este
  proyecto no se puede permitir (7.1).
- **Falla**: que no dispare un eje que la etiqueta declara. Si un caso dice `referencial` y el
  eje no lo ve, el eje ha dejado de cubrir lo que justifica su existencia.
- **Solo se informa**: la diferencia entre `relevante` y `sospecha`, y los ejes de más. El umbral
  que separa esos dos estados está declarado provisional y sin calibrar en el propio código
  (`UMBRAL_DIRECTOS_RELEVANTE`), y **ninguno de los dos descarta nada**: solo cambian el orden de
  la cola del LLM. Convertir en rojo una diferencia de orden sería fijar como verdad un número
  que nadie ha medido.

**Ninguna cifra de recall se publica desde aquí.** Con 14 casos no se puede, y hay un test en
`test_gold_set_prefiltro.py` que falla a propósito cuando el corpus pase de 30 para obligar a
revisar esa afirmación. Lo que sí se puede es enseñar el desglose por caso, que es lo que sirve
para trabajar.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.pipeline import prefiltro
from app.pipeline.referencias import extraer_referencias_anteriores
from app.pipeline.texto import texto_plano
from app.pipeline.watchlist import cargar
from app.security import xml_safe
from tests.gold_set.esquema import CasoGoldSet, cargar_casos

CASOS = cargar_casos()

# La watchlist **real** del repositorio, no una de prueba: aquí se mide el sistema tal y como
# está configurado, y una lista inventada mediría otra cosa.
WATCHLIST = cargar()

# Misma convención que el almacén (`security/hashing.py`): dos niveles de dos caracteres.
ALMACEN = Path("data")


def _ruta(sha256: str) -> Path:
    return ALMACEN / sha256[:2] / sha256[2:4] / f"{sha256}.xml"


def _evaluar(caso: CasoGoldSet):  # type: ignore[no-untyped-def]
    """Evalúa el caso sobre su cuerpo archivado, o salta diciendo qué falta."""
    if caso.sha256_cuerpo is None:
        pytest.skip(f"{caso.identificador_oficial}: el caso no declara `sha256_cuerpo`")
    ruta = _ruta(caso.sha256_cuerpo)
    if not ruta.exists():
        pytest.skip(
            f"No está el cuerpo archivado en {ruta} (backend/data/ está en .gitignore). "
            "Para tenerlo: docker compose exec worker python -m worker.run --fase2"
        )
    raiz = xml_safe.parse(ruta.read_bytes())
    return prefiltro.evaluar(
        caso.titulo,
        organo_emisor=caso.organo_emisor,
        texto_integro=texto_plano(raiz),
        referencias=extraer_referencias_anteriores(raiz),
        lista=WATCHLIST,
    )


@pytest.mark.parametrize("caso", CASOS, ids=lambda c: c.identificador_oficial)
def test_la_decision_de_cola_coincide_con_la_etiqueta(caso: CasoGoldSet) -> None:
    """Lo único irreversible del prefiltro: entrar en la cola o no entrar.

    Un falso negativo aquí no aparece en ninguna métrica del sistema —la norma no vuelve a
    mirarse— y es el fallo total que describe la sección 1. Por eso esto sí es rojo.
    """
    resultado = _evaluar(caso)
    esperado_entra = caso.prefiltro_esperado in ("relevante", "sospecha")

    assert resultado.entra_en_la_cola == esperado_entra, (
        f"{caso.identificador_oficial}: etiquetado '{caso.prefiltro_esperado}' y el prefiltro "
        f"dice '{resultado.estado.value}' (términos: {list(resultado.terminos)[:6]}, "
        f"directos: {resultado.directos}). {caso.notas}"
    )


@pytest.mark.parametrize("caso", CASOS, ids=lambda c: c.identificador_oficial)
def test_dispara_los_ejes_que_la_etiqueta_declara(caso: CasoGoldSet) -> None:
    """Recall **por eje** (7.3), que es lo que un número agregado no contesta.

    Se exige que estén los declarados, no que no haya más: un eje de más mete ruido en la cola
    del LLM y eso se afina; un eje de menos es cobertura perdida.
    """
    resultado = _evaluar(caso)
    disparados = {eje.value for eje in resultado.ejes}
    faltan = set(caso.ejes_esperados) - disparados

    assert not faltan, (
        f"{caso.identificador_oficial}: la etiqueta declara {caso.ejes_esperados} y han "
        f"disparado {sorted(disparados) or 'ninguno'}. Falta: {sorted(faltan)}. {caso.notas}"
    )


def test_desglose_por_caso(capsys: pytest.CaptureFixture[str]) -> None:
    """Imprime la tabla que sirve para trabajar, y **no afirma ninguna cifra de cobertura**.

    Sale con `pytest -s`. Lo que enseña es cada caso con su etiqueta, lo que el prefiltro dijo y
    por qué ejes; las diferencias entre `relevante` y `sospecha` se marcan como orden de cola,
    que es lo que son, y no como error.
    """
    lineas = []
    disponibles = 0
    for caso in CASOS:
        if caso.sha256_cuerpo is None or not _ruta(caso.sha256_cuerpo).exists():
            continue
        disponibles += 1
        raiz = xml_safe.parse(_ruta(caso.sha256_cuerpo).read_bytes())
        resultado = prefiltro.evaluar(
            caso.titulo,
            organo_emisor=caso.organo_emisor,
            texto_integro=texto_plano(raiz),
            referencias=extraer_referencias_anteriores(raiz),
            lista=WATCHLIST,
        )
        marca = "=" if resultado.estado.value == caso.prefiltro_esperado else "~orden"
        lineas.append(
            f"{caso.identificador_oficial:<18} etiqueta={caso.prefiltro_esperado:<11}"
            f" prefiltro={resultado.estado.value:<11} {marca:<7}"
            f" ejes={sorted(e.value for e in resultado.ejes) or '-'}"
            f" directos={resultado.directos}"
        )

    if not disponibles:
        pytest.skip("No hay ningún cuerpo archivado en data/; nada que desglosar.")

    with capsys.disabled():
        print(f"\n--- Gold set sobre texto íntegro ({disponibles} de {len(CASOS)} casos) ---")
        for linea in lineas:
            print(linea)
        print(
            "Esto es un desglose, NO una medición de recall: con este tamaño de corpus "
            "cualquier porcentaje tendría un intervalo de confianza inservible.\n"
        )

    # El único aserto de esta función es que se ha podido mirar algo. Lo demás lo comprueban los
    # dos tests de arriba, caso a caso, que es donde un fallo dice qué se ha roto.
    assert lineas


def test_los_casos_que_miden_declaran_su_cuerpo() -> None:
    """Un caso sin `sha256_cuerpo` no participa en la medición, y eso tiene que verse.

    Sin este test, añadir una tanda sin el puntero al archivo dejaría el corpus creciendo y la
    medición congelada, sin que nada avisara: los tests de arriba se saltarían en silencio.
    """
    sin_cuerpo = [c.identificador_oficial for c in CASOS if c.sha256_cuerpo is None]

    assert not sin_cuerpo, (
        "estos casos no declaran el cuerpo archivado y por tanto NO se evalúan sobre texto "
        f"íntegro: {sin_cuerpo}. Se etiquetan sobre el documento completo (7.8), así que el "
        "puntero al archivo es parte del caso."
    )
