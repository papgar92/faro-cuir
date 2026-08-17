"""Tests del ingestor del DOGC (ADR 0019), la segunda fuente del proyecto.

Sobre respuestas **reales recortadas** de la fuente, no sobre JSON inventado: lo que hizo falta
aprender de esta fuente no fue su formato documentado sino sus rarezas, y una fixture escrita de
memoria no las tendría.
"""

from __future__ import annotations

import datetime
import json

import pytest

from app.ingest import dogc
from app.ingest.boe import SumarioInvalido, SumarioNoDisponible

FECHA = datetime.date(2024, 12, 19)

# Fila real del sumario del 2024-12-19, recortada a los campos que el ingestor usa.
FILA = {
    "any": "2024",
    "n_mero_de_control": "24353009",
    "rang_de_norma": "Decret llei",
    "t_tol_de_la_norma": "DECRET LLEI 11/2024, de 17 de desembre, de necessitats financeres…",
    "t_tol_de_la_norma_es": "DECRETO LEY 11/2024, de 17 de diciembre, de necesidades financieras…",
    "data_de_publicaci_del_diari": "2024-12-19T00:00:00.000",
    "n_mero_de_diari": "9314",
    "diari_oficial": "DOGC",
    "url_es_format_xml": {
        "url": "https://portaljuridic.gencat.cat/eli/es-ct/dl/2024/12/17/11/dof/spa/xml"
    },
}


def _sumario(*filas: dict[str, object]) -> bytes:
    return json.dumps(list(filas)).encode("utf-8")


class TestUrlDelSumario:
    def test_filtra_por_la_fecha_exacta_en_el_servidor(self) -> None:
        """Se filtra en la fuente y no descargando 31.094 filas para tirar 31.090."""
        url = dogc.url_sumario(FECHA)

        assert "2024-12-19" in url
        assert "$limit" in url

    def test_dos_llamadas_del_mismo_dia_piden_lo_mismo(self) -> None:
        """Idempotencia también en la petición: sin orden fijo, dos pasadas no son comparables."""
        assert dogc.url_sumario(FECHA) == dogc.url_sumario(FECHA)
        assert "$order" in dogc.url_sumario(FECHA)


class TestParseo:
    def test_una_disposicion_real_se_convierte_en_item_de_sumario(self) -> None:
        sumario = dogc.parsear_sumario(_sumario(FILA), FECHA)

        assert sumario.identificador == "DOGC-S-2024-12-19"
        assert sumario.numero_diario == "9314"
        item = sumario.items[0]
        assert item.identificador == "DOGC-24353009"
        # Castellano, que es lo que el vocabulario del prefiltro sabe leer (ADR 0019).
        assert item.titulo.startswith("DECRETO LEY")
        assert item.url_xml.endswith("/spa/xml")
        assert item.seccion_nombre == "Decret llei"

    def test_un_dia_sin_disposiciones_no_es_un_fallo(self) -> None:
        """Domingos y festivos. Igual que el 404 del BOE: una respuesta válida del mundo."""
        with pytest.raises(SumarioNoDisponible):
            dogc.parsear_sumario(b"[]", FECHA)

    def test_una_fila_sin_version_castellana_se_descarta_sin_tumbar_el_dia(self) -> None:
        """Ocurre de verdad, y por eso no se aborta: el resto del boletín sí se puede vigilar."""
        sin_castellano = {**FILA, "n_mero_de_control": "24353010"}
        del sin_castellano["url_es_format_xml"]

        sumario = dogc.parsear_sumario(_sumario(FILA, sin_castellano), FECHA)

        assert [i.identificador for i in sumario.items] == ["DOGC-24353009"]

    def test_un_numero_de_control_con_forma_rara_no_compone_ningun_identificador(self) -> None:
        """6.10: lo que viene de fuera se valida antes de usarlo para nombrar nada."""
        hostil = {**FILA, "n_mero_de_control": "../../etc/passwd"}

        with pytest.raises(SumarioInvalido):
            dogc.parsear_sumario(_sumario(hostil), FECHA)

    def test_una_respuesta_que_no_es_json_falla_como_sumario_invalido(self) -> None:
        with pytest.raises(SumarioInvalido):
            dogc.parsear_sumario(b"<html>vaya</html>", FECHA)

    def test_el_tope_de_items_acota_lo_que_decide_la_fuente(self) -> None:
        """El número de filas lo decide la fuente; sin tope, una respuesta anómala son miles
        de descargas de texto íntegro (6.2)."""
        muchas = [
            {**FILA, "n_mero_de_control": f"2435{i:04d}"}
            for i in range(dogc.MAX_ITEMS_POR_DIA + 50)
        ]

        sumario = dogc.parsear_sumario(_sumario(*muchas), FECHA)

        assert len(sumario.items) == dogc.MAX_ITEMS_POR_DIA


# --- La trampa del Akoma Ntoso del DOGC (ADR 0019) -----------------------------------------

# Recorte **real** del XML de `DECRETO LEY 11/2024`, descargado el 2026-08-16. Lo que hay que
# mirar no es la estructura —que es Akoma Ntoso de manual— sino dónde está el texto: dentro de
# un ATRIBUTO, escapado como HTML. `itertext()` sobre esto devuelve cadena vacía.
AKN_REAL = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="no"?>'
    b'<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0">'
    b'<act contains="singleVersion" name="9"><meta><identification/></meta>'
    b'<body><hcontainer><heading/><content period="&lt;div&gt;&lt;p&gt;El presidente de la '
    b"Generalitat&lt;/p&gt;&#10;&lt;p&gt;&amp;nbsp;&lt;/p&gt;&lt;p&gt;Se suprime el "
    b'art\xc3\xadculo 7 del Decreto 100/2020.&lt;/p&gt;&lt;/div&gt;"/>'
    b"</hcontainer></body></act></akomaNtoso>"
)


class TestTextoDelAkomaNtoso:
    def test_el_articulado_sale_del_atributo_y_no_del_arbol(self) -> None:
        """Si esto se rompe, se archivan normas con texto vacío y **nada falla visiblemente**.

        El prefiltro las descartaría todas por no encontrar ningún término, el embudo diría
        «descartadas» con toda naturalidad y el sistema aparentaría vigilar una fuente que en
        realidad no está mirando. Es el falso negativo invisible de la sección 1, y por eso este
        test existe con XML real y no con un ejemplo escrito de memoria.
        """
        from app.pipeline.texto import texto_plano
        from app.security import xml_safe

        texto = texto_plano(xml_safe.parse(AKN_REAL))

        assert "El presidente de la Generalitat" in texto
        assert "Se suprime el artículo 7 del Decreto 100/2020." in texto

    def test_no_deja_marcado_ni_entidades_a_medio_desescapar(self) -> None:
        """`&amp;nbsp;` llega doblemente escapado en todos los documentos verificados.

        Sin la segunda pasada de desescapado, el texto se llena de `&nbsp;` literales y el
        vocabulario del prefiltro tendría que aprender a ignorarlos — que es como un diccionario
        empieza a describir el formato en vez del dominio.
        """
        from app.pipeline.texto import texto_plano
        from app.security import xml_safe

        texto = texto_plano(xml_safe.parse(AKN_REAL))

        assert "<p>" not in texto
        assert "&nbsp;" not in texto
        assert "&lt;" not in texto
