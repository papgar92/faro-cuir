"""Tests del ingestor del BOCYL (ADR 0029), la cuarta fuente y tercera autonómica.

Sobre HTML y XML **reales recortados**, no inventados. Con esta fuente eso importa más que con
las anteriores, porque es la primera cuyo sumario se lee de HTML: una fixture escrita de memoria
tendría la estructura que yo *creo* que tiene el BOCYL, y lo que hay que fijar es la que tiene.

Tres cosas se prueban aquí porque las tres rompen en silencio si fallan:

1. **El filtro por fecha.** Todas las páginas del BOCYL llevan un enlace fijo a una disposición
   de noviembre de 2022. Sin filtrar, cada día ingeriría esa norma bajo la fecha equivocada.
2. **Las dos codificaciones.** El sumario es UTF-8 y el cuerpo ISO-8859-15. Cruzarlas no falla,
   solo llena el texto de basura.
3. **El día sin boletín**, que aquí no da 404 sino una página corta.
"""

from __future__ import annotations

import datetime

import pytest

from app.ingest import bocyl
from app.ingest.boe import SumarioInvalido, SumarioNoDisponible
from app.pipeline.texto import texto_plano
from app.security import xml_safe

FECHA = datetime.date(2024, 1, 10)

# Enlace fijo del pie, presente en TODAS las páginas del BOCYL incluidas las de días sin
# boletín. Es real y es la trampa de esta fuente.
_PIE_2022 = (
    "<li><a href='https://bocyl.jcyl.es/boletines/2022/11/18/pdf/BOCYL-D-18112022-30.pdf'>"
    "normas</a></li>"
)


def _sumario(*bloques: str) -> bytes:
    cuerpo = "".join(bloques) + _PIE_2022
    return f"<html><body><div id='resultados'>{cuerpo}</div></body></html>".encode()


def _bloque(numero: int, titulo: str, *, seccion: str = "", organismo: str = "") -> str:
    """Un bloque de disposición con la forma real del sumario del BOCYL."""
    cabeceras = ""
    if seccion:
        cabeceras += f'<h3 id="I"><span>{seccion}</span></h3>'
    if organismo:
        cabeceras += f'<h5 class="encabezado6">{organismo}</h5>'
    return (
        f"{cabeceras}<p>{titulo}</p>"
        f'<ul class="descargaBoletin"><li><a href='
        f"'https://bocyl.jcyl.es/boletines/2024/01/10/pdf/BOCYL-D-10012024-{numero}.pdf'>"
        f"BOCYL-D-10012024-{numero}.pdf - 680 KB</a></li></ul>"
    )


# Cuerpo real recortado. El prólogo declara ISO-8859-15 y los acentos van en esa codificación:
# es lo que llega por el cable, y lo que `xml_safe` resuelve solo.
_CUERPO = """<?xml version="1.0" encoding="ISO-8859-15"?>
<disposicion>
<numeroEdicion>7/2024</numeroEdicion>
<fechaPublicacion>2024-01-10</fechaPublicacion>
<seccion>I. COMUNIDAD DE CASTILLA Y LEÓN</seccion>
<organismo>CONSEJERÍA DE LA PRESIDENCIA</organismo>
<rango>ORDEN</rango>
<numeroOficial>PRE/2/2024</numeroOficial>
<contenido>
<titulo>CORRECCIÓN de errores de la Orden PRE/2/2024, por la que se nombra personal.</titulo>
<texto content-type="application/xml">
 <p class='parrafo'>Advertido error en el texto remitido para su publicación.</p>
</texto>
</contenido>
</disposicion>"""


def _cuerpo(xml: str = _CUERPO) -> bytes:
    return xml.encode("iso-8859-15")


class TestUrls:
    def test_el_sumario_se_pide_por_fecha_exacta(self) -> None:
        assert bocyl.url_sumario(FECHA).endswith("fechaBoletin=10/01/2024")

    def test_el_cuerpo_se_direcciona_por_identificador(self) -> None:
        """La mejora sobre el BOA: la URL **nombra** el documento, no su posición."""
        url = bocyl.url_texto("BOCYL-D-10012024-3")

        assert url == "https://bocyl.jcyl.es/boletines/2024/01/10/xml/BOCYL-D-10012024-3.xml"

    def test_rechaza_un_identificador_mal_formado(self) -> None:
        with pytest.raises(ValueError):
            bocyl.url_texto("../../etc/passwd")


class TestParsearSumario:
    def test_lee_identificador_titulo_seccion_y_organismo(self) -> None:
        contenido = _sumario(
            _bloque(
                1,
                "ORDEN PRE/1/2024 por la que se nombra personal eventual.",
                seccion="I. COMUNIDAD DE CASTILLA Y LEÓN",
                organismo="CONSEJERÍA DE LA PRESIDENCIA",
            )
        )

        sumario = bocyl.parsear_sumario(contenido, FECHA)

        assert sumario.identificador == "BOCYL-S-2024-01-10"
        assert len(sumario.items) == 1
        item = sumario.items[0]
        assert item.identificador == "BOCYL-D-10012024-1"
        assert item.titulo.startswith("ORDEN PRE/1/2024")
        assert item.seccion_nombre == "I. COMUNIDAD DE CASTILLA Y LEÓN"
        assert item.departamento == "CONSEJERÍA DE LA PRESIDENCIA"
        assert item.url_xml.endswith("/xml/BOCYL-D-10012024-1.xml")

    def test_la_seccion_y_el_organismo_se_arrastran_a_las_siguientes(self) -> None:
        """Son cabeceras de grupo: valen para todas las disposiciones que vienen debajo."""
        contenido = _sumario(
            _bloque(1, "Primera disposición del día.", seccion="I. COMUNIDAD", organismo="SANIDAD"),
            _bloque(2, "Segunda disposición del día."),
        )

        sumario = bocyl.parsear_sumario(contenido, FECHA)

        assert [i.departamento for i in sumario.items] == ["SANIDAD", "SANIDAD"]

    def test_ignora_el_enlace_fijo_de_2022(self) -> None:
        """Sin este filtro, cada día del archivo ingeriría una norma de noviembre de 2022.

        Y no fallaría nada visiblemente: se archivaría con la fecha del día pedido, así que el
        archivo afirmaría que se publicó un día en el que no se publicó. Es exactamente lo que
        la 6.5 existe para impedir.
        """
        sumario = bocyl.parsear_sumario(_sumario(_bloque(1, "La única del día.")), FECHA)

        assert [i.identificador for i in sumario.items] == ["BOCYL-D-10012024-1"]

    def test_no_duplica_una_disposicion_enlazada_dos_veces(self) -> None:
        """El sumario repite cada enlace y deja además copias comentadas en el HTML."""
        bloque = _bloque(1, "Disposición enlazada por duplicado.")

        sumario = bocyl.parsear_sumario(_sumario(bloque, bloque), FECHA)

        assert len(sumario.items) == 1

    def test_descarta_la_disposicion_sin_titulo(self) -> None:
        sin_titulo = (
            '<ul class="descargaBoletin"><li><a href='
            "'https://bocyl.jcyl.es/boletines/2024/01/10/pdf/BOCYL-D-10012024-9.pdf'>x</a></li></ul>"
        )

        sumario = bocyl.parsear_sumario(_sumario(_bloque(1, "Con título."), sin_titulo), FECHA)

        assert [i.identificador for i in sumario.items] == ["BOCYL-D-10012024-1"]

    def test_los_acentos_del_sumario_se_leen_como_utf8(self) -> None:
        """El sumario es UTF-8 y el cuerpo ISO-8859-15. Cruzarlos no falla, solo ensucia."""
        sumario = bocyl.parsear_sumario(
            _sumario(_bloque(1, "ORDEN de modificación de la Consejería de Educación.")), FECHA
        )

        assert "modificación" in sumario.items[0].titulo

    def test_desescapa_las_entidades_del_titulo(self) -> None:
        sumario = bocyl.parsear_sumario(
            _sumario(_bloque(1, "ORDEN sobre educaci&oacute;n y sanidad.")), FECHA
        )

        assert "educación" in sumario.items[0].titulo


class TestDiaSinBoletin:
    def test_un_dia_sin_disposiciones_de_esa_fecha_no_es_un_fallo(self) -> None:
        """No da 404: da una página corta con solo el enlace fijo de 2022."""
        with pytest.raises(SumarioNoDisponible):
            bocyl.parsear_sumario(_sumario(), FECHA)


class TestParsearCuerpo:
    def test_acepta_el_cuerpo_de_la_disposicion_pedida(self) -> None:
        raiz = bocyl.parsear_cuerpo(_cuerpo(), "BOCYL-D-10012024-1")

        assert raiz.findtext("./numeroOficial") == "PRE/2/2024"

    def test_rechaza_un_cuerpo_con_otra_fecha_de_publicacion(self) -> None:
        """La URL nombra el documento, pero puede servirse otra cosa bajo ella.

        El archivo afirma «el día X esto decía exactamente esto»; un documento resellado con
        otra fecha rompe esa afirmación sin romper nada visible.
        """
        otro = _CUERPO.replace("2024-01-10", "2024-02-20")

        with pytest.raises(SumarioInvalido, match="2024-02-20"):
            bocyl.parsear_cuerpo(_cuerpo(otro), "BOCYL-D-10012024-1")

    def test_rechaza_una_pagina_de_error_sin_tocar_el_parser(self) -> None:
        """Un `<!DOCTYPE html>` haría saltar `xml_safe` y el worker abortaría la tanda entera.

        Reconocerlo antes NO relaja `xml_safe`: ese HTML no se parsea, se rechaza.
        """
        with pytest.raises(SumarioInvalido) as capturado:
            bocyl.parsear_cuerpo(
                b"<!DOCTYPE html><html><body>error</body></html>", "BOCYL-D-10012024-1"
            )

        assert "DOCTYPE" not in str(capturado.value)


class TestTextoPlano:
    def test_deriva_el_articulado_y_no_el_titulo_ni_los_metadatos(self) -> None:
        """`<titulo>` es hermano de `<texto>` dentro de `<contenido>`.

        Apuntar a `<contenido>` metería el título en el articulado, y el prefiltro léxico lo
        leería como señal del cuerpo cuando es metadato — el mismo falso positivo que produce
        el bloque `<analisis>` del BOE cuando se cae al caso de respaldo.
        """
        texto = texto_plano(xml_safe.parse(_cuerpo()))

        assert texto.startswith("Advertido error")
        assert "CORRECCIÓN de errores" not in texto
        assert "CONSEJERÍA" not in texto
