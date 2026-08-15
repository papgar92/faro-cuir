"""Tests del lector de legislación consolidada del BOE (ADR 0018).

Sobre un **recorte del consolidado real** de `BOE-A-2016-6728` (Ley 2/2016 de Madrid), no sobre
XML inventado para que pase: mismo criterio que `test_reglas.py`. El recorte conserva tres
bloques que cubren los tres casos que importan —un artículo intacto, uno modificado por la
reforma de 2023 y uno suprimido por ella— con los párrafos acortados.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from app.ingest import boe_consolidado
from app.ingest.boe_consolidado import ConsolidadoError, IdentificadorInvalido, NoConsolidado
from app.security import xml_safe

FIXTURE = Path(__file__).parent / "fixtures" / "boe_a_2016_6728_consolidado_recortado.xml"
REFORMA = "BOE-A-2024-10767"


@pytest.fixture
def raiz():  # type: ignore[no-untyped-def]
    # Por `xml_safe` y no por `ElementTree` directamente: el XML archivado sigue siendo dato no
    # confiable (regla de oro 1) y los tests tienen que enseñar el camino correcto.
    return xml_safe.parse(FIXTURE.read_bytes())


class TestUrl:
    def test_compone_la_url_del_consolidado(self) -> None:
        assert boe_consolidado.url_consolidado("BOE-A-2016-6728").endswith(
            "/legislacion-consolidada/id/BOE-A-2016-6728"
        )

    @pytest.mark.parametrize(
        "valor",
        [
            "BOE-A-2016-6728/../../etc/passwd",
            "https://evil.example/BOE-A-2016-6728",
            "BOE-A-2016-6728 OR 1=1",
            "",
        ],
    )
    def test_rechaza_lo_que_no_es_un_identificador(self, valor: str) -> None:
        """6.10: el control vive en el constructor de la URL, no en la buena costumbre."""
        with pytest.raises(IdentificadorInvalido):
            boe_consolidado.url_consolidado(valor)


class TestRespuesta:
    def test_acepta_un_consolidado_publicado(self, raiz) -> None:  # type: ignore[no-untyped-def]
        boe_consolidado.comprobar_respuesta(raiz)  # no levanta

    def test_distingue_no_consolidado_de_averia(self) -> None:
        """La API contesta 404 en su propio `<status>`, y eso NO es un fallo (es el caso normal)."""
        sin = xml_safe.parse(
            b"<response><status><code>404</code>"
            b"<text>La informacion solicitada no existe</text></status><data/></response>"
        )
        with pytest.raises(NoConsolidado):
            boe_consolidado.comprobar_respuesta(sin)

        rota = xml_safe.parse(
            b"<response><status><code>500</code><text>error</text></status><data/></response>"
        )
        with pytest.raises(ConsolidadoError) as error:
            boe_consolidado.comprobar_respuesta(rota)
        assert not isinstance(error.value, NoConsolidado)


class TestBloques:
    def test_lee_las_redacciones_sucesivas_de_cada_bloque(self, raiz) -> None:  # type: ignore[no-untyped-def]
        bloques = boe_consolidado.extraer_bloques(raiz)

        assert [b.id for b in bloques] == ["a2", "a4", "a7"]
        a4 = next(b for b in bloques if b.id == "a4")
        assert a4.titulo == "Artículo 4"
        assert [v.id_norma for v in a4.versiones] == ["BOE-A-2016-6728", REFORMA]
        assert a4.versiones[1].fecha_vigencia == datetime.date(2023, 12, 30)

    def test_excluye_las_notas_del_consolidador(self, raiz) -> None:  # type: ignore[no-untyped-def]
        """La anotación «Se suprime por el art. único.7…» es del BOE, no de la norma.

        Dejarla dentro ensuciaría el diff con texto que nadie legisló, y haría que toda
        redacción tocada pareciera distinta por la nota antes que por el cambio.
        """
        a7 = next(b for b in boe_consolidado.extraer_bloques(raiz) if b.id == "a7")
        vigente = a7.versiones[-1].texto

        assert "(Suprimido)" in vigente
        assert "Se suprime por el art" not in vigente
        assert "Ref. BOE-A-2024-10767" not in vigente


class TestCambios:
    def test_empareja_el_texto_anterior_con_el_nuevo(self, raiz) -> None:  # type: ignore[no-untyped-def]
        """El caso que justifica todo el ADR 0018: un retroceso que solo se ve comparando."""
        cambios = boe_consolidado.cambios_de(boe_consolidado.extraer_bloques(raiz), REFORMA)

        assert [c.bloque for c in cambios] == ["a4", "a7"]
        a4 = cambios[0]
        assert a4.texto_anterior is not None
        assert "derecho a la identidad de género libremente manifestada" in a4.texto_anterior
        assert "respeto a la libertad y dignidad de las personas transexuales" in a4.texto_nuevo
        assert a4.fecha_vigencia == datetime.date(2023, 12, 30)

    def test_una_supresion_deja_texto_nuevo_marcado_y_texto_anterior_completo(
        self,
        raiz,  # type: ignore[no-untyped-def]
    ) -> None:
        a7 = boe_consolidado.cambios_de(boe_consolidado.extraer_bloques(raiz), REFORMA)[1]

        assert a7.texto_anterior is not None
        assert "Documentación administrativa" in a7.texto_anterior
        assert "(Suprimido)" in a7.texto_nuevo

    def test_una_norma_que_no_toco_el_texto_no_produce_cambios(self, raiz) -> None:  # type: ignore[no-untyped-def]
        """Y esto NO es 'no hay diff todavía': es que esta norma no aparece en el consolidado."""
        assert (
            boe_consolidado.cambios_de(boe_consolidado.extraer_bloques(raiz), "BOE-A-1999-1") == ()
        )

    def test_un_bloque_creado_por_la_norma_no_tiene_texto_anterior(self) -> None:
        """NULL significa alta. No se rellena con cadena vacía: son hechos distintos."""
        raiz = xml_safe.parse(
            b"<response><status><code>200</code></status><data><texto>"
            b'<bloque id="da1" tipo="precepto" titulo="Disposicion adicional primera">'
            b'<version id_norma="BOE-A-2024-10767" fecha_vigencia="20231230">'
            b"<p>Texto nuevo.</p></version></bloque></texto></data></response>"
        )
        cambio = boe_consolidado.cambios_de(boe_consolidado.extraer_bloques(raiz), REFORMA)[0]

        assert cambio.texto_anterior is None
        assert cambio.texto_nuevo == "Texto nuevo."

    def test_si_la_norma_toco_dos_veces_el_mismo_bloque_manda_la_ultima(self) -> None:
        raiz = xml_safe.parse(
            b"<response><status><code>200</code></status><data><texto>"
            b'<bloque id="a1" tipo="precepto" titulo="Articulo 1">'
            b'<version id_norma="BOE-A-2016-6728"><p>Original.</p></version>'
            b'<version id_norma="BOE-A-2024-10767"><p>Primera redaccion.</p></version>'
            b'<version id_norma="BOE-A-2024-10767"><p>Segunda redaccion.</p></version>'
            b"</bloque></texto></data></response>"
        )
        cambios = boe_consolidado.cambios_de(boe_consolidado.extraer_bloques(raiz), REFORMA)

        assert len(cambios) == 1
        assert cambios[0].texto_anterior == "Primera redaccion."
        assert cambios[0].texto_nuevo == "Segunda redaccion."

    def test_una_fecha_de_vigencia_ilegible_no_tira_el_diff(self) -> None:
        raiz = xml_safe.parse(
            b"<response><status><code>200</code></status><data><texto>"
            b'<bloque id="a1" tipo="precepto" titulo="Articulo 1">'
            b'<version id_norma="BOE-A-2024-10767" fecha_vigencia="ayer">'
            b"<p>Texto.</p></version></bloque></texto></data></response>"
        )
        cambio = boe_consolidado.cambios_de(boe_consolidado.extraer_bloques(raiz), REFORMA)[0]

        assert cambio.fecha_vigencia is None
        assert cambio.texto_nuevo == "Texto."


class TestBloquesEditoriales:
    def test_ignora_la_nota_inicial_del_consolidador(self) -> None:
        """La encontró la primera ejecución real, no un test: parecía un alta y no lo era.

        El bloque `nota_inicial` lo añade la norma modificadora, así que llegaba como una
        versión sin texto anterior — o sea, indistinguible de un precepto nuevo. Y no es
        articulado: es la glosa del consolidador diciendo que la norma quedó derogada o
        renombrada.
        """
        raiz = xml_safe.parse(
            b"<response><status><code>200</code></status><data><texto>"
            b'<bloque id="no" tipo="nota_inicial">'
            b'<version id_norma="BOE-A-2024-10767"><p>Norma derogada, con efectos desde 2023.</p>'
            b"</version></bloque>"
            b'<bloque id="a1" tipo="precepto" titulo="Articulo 1">'
            b'<version id_norma="BOE-A-2016-6728"><p>Original.</p></version>'
            b'<version id_norma="BOE-A-2024-10767"><p>Nueva.</p></version>'
            b"</bloque></texto></data></response>"
        )

        assert [b.id for b in boe_consolidado.extraer_bloques(raiz)] == ["a1"]
        cambios = boe_consolidado.cambios_de(boe_consolidado.extraer_bloques(raiz), REFORMA)
        assert [c.bloque for c in cambios] == ["a1"]
        assert cambios[0].texto_anterior == "Original."
