"""Eje 2 del prefiltro: watchlist, bloque `<analisis>` y su combinación en OR. CLAUDE.md 7.3.

Este eje existe para cubrir el agujero estructural del diccionario: **una instrucción que
elimina un derecho no dice "identidad de género", dice "se modifica el epígrafe 4.3 del anexo
II"**. Por eso los tests se centran en un solo escenario y lo miran desde varios lados: una
norma cuyo texto no contiene ni un término del vocabulario y que aun así tiene que pasar.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.norma import EjePrefiltro, EstadoPrefiltro
from app.pipeline import prefiltro
from app.pipeline.referencias import ReferenciaAnterior, extraer_referencias_anteriores
from app.pipeline.watchlist import (
    PATRON_IDENTIFICADOR,
    WatchlistNoDisponible,
    cargar,
)
from app.security import xml_safe

# Fragmento con la forma REAL del bloque, verificada contra un documento del BOE en la
# medición del ADR 0011 y escrita en CLAUDE.md 7.3. No es una estructura inventada para el
# test: si el BOE cambiara de forma, este XML dejaría de parecerse al real y el test seguiría
# pasando — por eso la estructura está documentada en la sección 7.3 y no solo aquí.
XML_CON_ANALISIS = """<?xml version="1.0" encoding="UTF-8"?>
<documento>
  <metadatos><identificador>BOE-A-2026-0001</identificador></metadatos>
  <analisis>
    <referencias>
      <anteriores>
        <anterior referencia="BOE-A-2023-5366">
          <palabra codigo="270">MODIFICA</palabra>
          <texto>el art. 43.2 y AÑADE la disposición adicional cuarta</texto>
        </anterior>
        <anterior referencia="BOE-A-2015-11431">
          <palabra codigo="290">CITA</palabra>
          <texto>en el temario de la convocatoria</texto>
        </anterior>
      </anteriores>
      <posteriores>
        <posterior referencia="BOE-A-2027-9999">
          <palabra codigo="270">MODIFICA</palabra>
        </posterior>
      </posteriores>
    </referencias>
  </analisis>
  <texto><p>Se modifica el epígrafe 4.3 del anexo II en los términos siguientes.</p></texto>
</documento>
"""


# Códigos ISO 3166-2:ES de las 17 comunidades autónomas. Los mismos que usa el mapa del
# frontend (`ccaa-paths.ts`), a propósito: si algún día divergen, el desglose de cobertura de la
# interfaz dejaría de cruzar con la watchlist y no fallaría — enseñaría cero.
CCAA = {
    "AN",
    "AR",
    "AS",
    "CB",
    "CL",
    "CM",
    "CN",
    "CT",
    "EX",
    "GA",
    "IB",
    "MC",
    "MD",
    "NC",
    "PV",
    "RI",
    "VC",
}


def _watchlist_real():  # type: ignore[no-untyped-def]
    """La watchlist versionada del proyecto, o salta si `config/` no está montado."""
    real = Path("/config/watchlist.json")
    if not real.is_file():  # pragma: no cover - fuera de docker
        pytest.skip("config/ no está montado en este entorno")
    return cargar(real)


@pytest.fixture
def lista_de_prueba(tmp_path: Path):  # type: ignore[no-untyped-def]
    """Watchlist propia, para no atar los tests al contenido de `config/watchlist.json`.

    Ese fichero cambia cuando se añaden normas vigiladas, y un test que dependa de su
    contenido se rompería por un motivo que no tiene nada que ver con lo que comprueba.
    """
    ruta = tmp_path / "watchlist.json"
    ruta.write_text(
        json.dumps(
            {
                "version": "test-1",
                "normas": [
                    {"identificador": "BOE-A-2023-5366", "titulo": "Ley 4/2023", "nota": "x"}
                ],
            }
        ),
        encoding="utf-8",
    )
    return cargar(ruta)


class TestParseoDelAnalisis:
    def test_saca_identificador_verbo_y_articulos(self) -> None:
        raiz = xml_safe.parse(XML_CON_ANALISIS.encode("utf-8"))
        referencias = extraer_referencias_anteriores(raiz)

        assert len(referencias) == 2
        primera = referencias[0]
        assert primera.identificador == "BOE-A-2023-5366"
        assert primera.verbo == "MODIFICA"
        assert "art. 43.2" in primera.texto

    def test_ignora_las_posteriores(self) -> None:
        """`posteriores` son las normas que modificaron a esta *después*.

        El día que se ingiere un documento no existen todavía, así que no pueden decidir nada.
        Incluirlas haría que el eje disparase por normas del futuro.
        """
        raiz = xml_safe.parse(XML_CON_ANALISIS.encode("utf-8"))
        identificadores = {r.identificador for r in extraer_referencias_anteriores(raiz)}
        assert "BOE-A-2027-9999" not in identificadores

    def test_distingue_modificar_de_citar(self) -> None:
        """La distinción que hace útil a este eje.

        `CITA` es exactamente el falso positivo que produce el eje léxico sobre el texto
        íntegro: la convocatoria de oposición que menciona la Ley 4/2023 en su temario.
        """
        raiz = xml_safe.parse(XML_CON_ANALISIS.encode("utf-8"))
        por_id = {r.identificador: r for r in extraer_referencias_anteriores(raiz)}
        assert por_id["BOE-A-2023-5366"].es_modificativa
        assert not por_id["BOE-A-2015-11431"].es_modificativa

    def test_un_documento_sin_analisis_no_es_un_error(self) -> None:
        """Es el caso normal: solo el 9,9 % de las normas traen referencias anteriores."""
        raiz = xml_safe.parse(b"<documento><texto>nada</texto></documento>")
        assert extraer_referencias_anteriores(raiz) == ()

    def test_una_referencia_sin_identificador_se_descarta(self) -> None:
        """Aceptarla con cadena vacía la haría cruzar con cualquier otra igual de vacía."""
        raiz = xml_safe.parse(
            b"<documento><analisis><referencias><anteriores>"
            b"<anterior><palabra>MODIFICA</palabra></anterior>"
            b"</anteriores></referencias></analisis></documento>"
        )
        assert extraer_referencias_anteriores(raiz) == ()

    def test_anade_con_tilde_cuenta_como_modificativo(self) -> None:
        """El BOE escribe `AÑADE`; sin normalizar la ñ, el verbo no cruzaría nunca."""
        referencia = ReferenciaAnterior("BOE-A-2023-5366", "ANADE", "")
        assert referencia.es_modificativa


class TestWatchlist:
    def test_rechaza_un_identificador_con_formato_invalido(self, tmp_path: Path) -> None:
        """Falla al CARGAR, no al cruzar. Es la diferencia entre un rojo y un silencio.

        Un identificador mal escrito no rompe nada visible: simplemente no cruza nunca, y el
        eje referencial parece funcionar mientras deja pasar justo lo que debía detectar.
        """
        ruta = tmp_path / "w.yaml"
        ruta.write_text(
            json.dumps(
                {
                    "version": "1",
                    "normas": [{"identificador": "Ley 4/2023", "titulo": "", "nota": ""}],
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(WatchlistNoDisponible, match="formato inválido"):
            cargar(ruta)

    def test_una_watchlist_vacia_es_un_error(self, tmp_path: Path) -> None:
        """Vacía no falla sola: apaga el eje en silencio. Mejor no arrancar."""
        ruta = tmp_path / "w.yaml"
        ruta.write_text(json.dumps({"version": "1", "normas": []}), encoding="utf-8")
        with pytest.raises(WatchlistNoDisponible, match="vacía"):
            cargar(ruta)

    def test_sin_version_es_un_error(self, tmp_path: Path) -> None:
        """Sin versión no se sabe qué reevaluar cuando la lista cambia."""
        ruta = tmp_path / "w.yaml"
        ruta.write_text(
            json.dumps({"normas": [{"identificador": "BOE-A-2023-5366"}]}), encoding="utf-8"
        )
        with pytest.raises(WatchlistNoDisponible, match="version"):
            cargar(ruta)

    @pytest.mark.parametrize(
        "malo",
        [
            "BOE-A-2023-5366/../../etc/passwd",
            "BOE-A-2023-5366\n",
            "../BOE-A-2023-5366",
            "BOE-A-2023-5366 OR 1=1",
        ],
    )
    def test_no_cruza_nada_que_no_sea_un_identificador_limpio(
        self, lista_de_prueba, malo: str
    ) -> None:
        """CLAUDE.md 6.10: lo que sale de un documento externo es dato, nunca una instrucción.

        Hoy este valor no construye ninguna URL ni ninguna ruta, y por eso mismo la garantía
        tiene que vivir en el validador: si mañana alguien lo usa para construir algo, el
        control ya está puesto y no depende de que se acuerde.
        """
        assert not lista_de_prueba.contiene(malo)

    def test_el_patron_esta_anclado_por_los_dos_extremos(self) -> None:
        assert PATRON_IDENTIFICADOR.match("BOE-A-2023-5366")
        assert not PATRON_IDENTIFICADOR.match("BOE-A-2023-5366-extra")
        assert not PATRON_IDENTIFICADOR.match("xBOE-A-2023-5366")

    def test_la_watchlist_real_del_proyecto_carga_y_valida(self) -> None:
        """El fichero versionado en `config/` tiene que ser válido siempre.

        Sin este test, un error de sintaxis al añadir una norma vigilada no se descubriría
        hasta la siguiente pasada del worker en producción.
        """
        lista = _watchlist_real()
        assert lista.version
        assert lista.normas
        # La norma central del ámbito no puede faltar: es el positivo conocido del gold set.
        assert lista.contiene("BOE-A-2023-5366")

    def test_cubre_las_17_comunidades(self) -> None:
        """Auditoría de cobertura, cerrada el 2026-08-08 verificando una a una contra boe.es.

        **Este es el test que convierte la watchlist en algo auditable.** Sin él, que falte la
        ley de una comunidad entera no se distingue de que esa comunidad no tenga ley — y esas
        dos cosas se parecen mucho mirando el fichero, pero una es un agujero de cobertura y la
        otra es un dato. Cada una de las 17 tiene que estar en un sitio o en el otro.
        """
        lista = _watchlist_real()
        con_ley = {n.ambito for n in lista.normas if n.ambito and n.ambito != "estatal"}
        sin_ley = set(lista.sin_ley)

        assert not (con_ley & sin_ley), "una comunidad no puede tener ley y no tenerla"
        faltan = CCAA - con_ley - sin_ley
        assert not faltan, f"comunidades sin auditar: {sorted(faltan)}"
        sobran = (con_ley | sin_ley) - CCAA
        assert not sobran, f"códigos que no son de ninguna comunidad: {sorted(sobran)}"

    def test_asturias_y_castilla_y_leon_siguen_sin_ley(self) -> None:
        """Verificado el 2026-08-08: son las dos únicas comunidades sin ley autonómica LGTBI.

        Este test **está pensado para fallar algún día**, y ese día será una buena noticia:
        Asturias aprobó un anteproyecto el 2026-03-09. Cuando se publique, hay que añadir su
        `BOE-A` a `normas` y quitarla de `_sin_ley_autonomica`, y este test lo recuerda.
        """
        assert set(_watchlist_real().sin_ley) == {"AS", "CL"}

    def test_no_hay_normas_sin_ambito(self) -> None:
        """Sin ámbito no se puede comprobar la cobertura, y el test de arriba se volvería ciego."""
        huerfanas = [n.identificador for n in _watchlist_real().normas if not n.ambito]
        assert not huerfanas, huerfanas


class TestEjeReferencialEnElPrefiltro:
    def test_una_norma_sin_vocabulario_pasa_por_modificar_la_watchlist(
        self, lista_de_prueba
    ) -> None:
        """**El caso que justifica el eje entero.**

        Ni el título ni el texto contienen un solo término del vocabulario. El eje léxico la
        descartaría, y sería un falso negativo de manual: una norma que modifica la Ley 4/2023
        sin nombrar nada del colectivo.
        """
        titulo = "Orden por la que se modifica el epígrafe 4.3 del anexo II"
        texto = "Se modifica el epígrafe 4.3 del anexo II en los términos siguientes."

        solo_lexico = prefiltro.evaluar(titulo, texto_integro=texto, lista=lista_de_prueba)
        assert solo_lexico.estado is EstadoPrefiltro.DESCARTADA, (
            "control: sin referencias se descarta"
        )

        raiz = xml_safe.parse(XML_CON_ANALISIS.encode("utf-8"))
        con_referencias = prefiltro.evaluar(
            titulo,
            texto_integro=texto,
            referencias=extraer_referencias_anteriores(raiz),
            lista=lista_de_prueba,
        )
        assert con_referencias.estado is EstadoPrefiltro.RELEVANTE
        assert con_referencias.ejes == (EjePrefiltro.REFERENCIAL,)
        assert con_referencias.referencias_watchlist == ("BOE-A-2023-5366",)
        assert con_referencias.terminos == (), "no disparó el léxico y no debe decir que sí"

    def test_citar_una_norma_vigilada_no_basta(self, lista_de_prueba) -> None:
        """Si citar bastara, este eje metería en la cola el 10 % del boletín diario."""
        referencias = (ReferenciaAnterior("BOE-A-2023-5366", "CITA", "en el temario"),)
        resultado = prefiltro.evaluar(
            "Convocatoria de oposiciones",
            texto_integro="temario",
            referencias=referencias,
            lista=lista_de_prueba,
        )
        assert resultado.estado is EstadoPrefiltro.DESCARTADA

    def test_modificar_algo_que_no_esta_vigilado_no_dispara(self, lista_de_prueba) -> None:
        referencias = (ReferenciaAnterior("BOE-A-2015-11431", "MODIFICA", "el art. 33"),)
        resultado = prefiltro.evaluar(
            "Orden técnica", texto_integro="cosas", referencias=referencias, lista=lista_de_prueba
        )
        assert resultado.estado is EstadoPrefiltro.DESCARTADA

    def test_los_ejes_van_en_or_y_se_registran_los_dos(self, lista_de_prueba) -> None:
        """CLAUDE.md 7.3: OR, jamás AND. Y que dispararon los dos es un dato distinto."""
        referencias = (ReferenciaAnterior("BOE-A-2023-5366", "DEROGA", "el capítulo III"),)
        resultado = prefiltro.evaluar(
            "Orden sobre identidad de género",
            texto_integro="identidad de genero y personas trans",
            referencias=referencias,
            lista=lista_de_prueba,
        )
        assert set(resultado.ejes) == {EjePrefiltro.LEXICO, EjePrefiltro.REFERENCIAL}

    def test_el_eje_referencial_no_depende_del_umbral_lexico(self, lista_de_prueba) -> None:
        """Modificar una norma vigilada pasa "diga lo que diga su texto" (7.3).

        Con un solo término directo el eje léxico daría `SOSPECHA`; el referencial manda.
        """
        referencias = (ReferenciaAnterior("BOE-A-2023-5366", "MODIFICA", "el art. 1"),)
        resultado = prefiltro.evaluar(
            "Orden",
            texto_integro="menciona lgtbi una vez",
            referencias=referencias,
            lista=lista_de_prueba,
        )
        assert resultado.directos < prefiltro.UMBRAL_DIRECTOS_RELEVANTE
        assert resultado.estado is EstadoPrefiltro.RELEVANTE


class TestUmbralLexico:
    """Lo que de verdad protege del umbral mal calibrado (ver el encabezado del módulo)."""

    def test_por_debajo_del_umbral_no_se_descarta_nunca(self) -> None:
        """**La garantía que hace que equivocarse con el umbral salga barato.**

        Si esto se rompiera, un umbral mal puesto dejaría de costar latencia y pasaría a costar
        falsos negativos, que es el único error que este proyecto no se puede permitir.
        """
        resultado = prefiltro.evaluar(
            "Orden técnica", texto_integro="el texto menciona lgtbi una sola vez"
        )
        assert 0 < resultado.directos < prefiltro.UMBRAL_DIRECTOS_RELEVANTE
        assert resultado.estado is EstadoPrefiltro.SOSPECHA
        assert resultado.entra_en_la_cola, "sospecha va a la cola del LLM, no a la basura"

    def test_muchos_terminos_directos_dan_relevante(self) -> None:
        texto = (
            "personas trans, identidad de genero, expresion de genero, orientacion sexual, "
            "transexual, intersexual, lgtbi, homosexual, transfobia, queer"
        )
        resultado = prefiltro.evaluar("Ley integral", texto_integro=texto)
        assert resultado.directos >= prefiltro.UMBRAL_DIRECTOS_RELEVANTE
        assert resultado.estado is EstadoPrefiltro.RELEVANTE
