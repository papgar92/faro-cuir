"""Tests del ingestor del BOA (ADR 0028), la tercera fuente y segunda autonómica.

Sobre XML **real recortado** de la fuente, no inventado: igual que con el DOGC, lo que hubo que
aprender de esta fuente no fue su formato documentado —no hay documentación— sino sus rarezas, y
una fixture escrita de memoria no las tendría. En particular el prólogo `ISO-8859-1`, que aquí
va literal porque es lo que llega por el cable.

El test que sostiene el diseño es `TestParsearCuerpo`: el BOA no deja pedir un documento por su
identificador y hay que direccionarlo por su posición dentro del día, así que la comprobación de
que lo devuelto es lo pedido es lo único que separa este archivo de archivar el texto de una
norma bajo el identificador de otra.
"""

from __future__ import annotations

import datetime

import pytest

from app.ingest import boa
from app.ingest.boe import SumarioInvalido, SumarioNoDisponible
from app.pipeline.texto import texto_plano
from app.security import xml_safe

FECHA = datetime.date(2024, 1, 10)

# Registro real del BOA del 2024-01-10, recortado. El acento en `ECONOMÍA` va como el byte
# 0xCD de ISO-8859-1 al codificar, que es lo que hace este XML distinto de todos los demás
# del proyecto.
_REGISTRO = """<registro>
<docn>007938287</docn>
<id-NTI></id-NTI>
<fecha>20240110</fecha>
<rango>ORDEN</rango>
<seccion>I. Disposiciones Generales</seccion>
<subseccion></subseccion>
<emisor>DEPARTAMENTO DE ECONOMÍA, EMPLEO E INDUSTRIA</emisor>
<numeroboletin>7</numeroboletin>
<titulo>ORDEN EEI/1987/2023, de 28 de diciembre, de bases reguladoras.</titulo>
<texto>El Estatuto de Autonomía de Aragón, reformado por la Ley Orgánica 5/2007.</texto>
<url>&lt;enlace&gt;https://www.boa.aragon.es/cgi-bin/EBOA/BRSCGI?CMD=VEROBJ&lt;/enlace&gt;</url>
</registro>"""

_SEGUNDO = _REGISTRO.replace("007938287", "007938288").replace("ORDEN", "RESOLUCIÓN")


def _documento(*registros: str) -> bytes:
    cuerpo = "\n".join(registros)
    return (
        f'<?xml version="1.0" encoding="ISO-8859-1" standalone="yes" ?>\n'
        f"<documento>\n{cuerpo}\n</documento>"
    ).encode("iso-8859-1")


class TestUrlDelSumario:
    def test_filtra_por_la_fecha_exacta_en_el_servidor(self) -> None:
        """El filtro lo hace la fuente: así dos ejecuciones del mismo día piden lo mismo."""
        assert "PUBL=20240110" in boa.url_sumario(FECHA)

    def test_pide_la_seccion_que_devuelve_xml_estructurado(self) -> None:
        """`OUTPUTMODE=XML` sin la sección correcta lo ignora y devuelve el HTML del diario."""
        url = boa.url_sumario(FECHA)

        assert "SEC=OPENDATABOAXML" in url
        assert "OUTPUTMODE=XML" in url

    def test_la_url_del_cuerpo_acota_a_un_solo_registro(self) -> None:
        assert "DOCS=12-12" in boa.url_texto(FECHA, 12)

    def test_rechaza_una_posicion_imposible(self) -> None:
        """BRSCGI es 1-based. Un 0 sería un error nuestro, no de la fuente."""
        with pytest.raises(ValueError):
            boa.url_texto(FECHA, 0)


class TestParsearSumario:
    def test_lee_los_campos_que_el_pipeline_necesita(self) -> None:
        sumario = boa.parsear_sumario(_documento(_REGISTRO), FECHA)

        assert sumario.identificador == "BOA-S-2024-01-10"
        assert sumario.fecha_publicacion == FECHA
        assert sumario.numero_diario == "7"
        assert len(sumario.items) == 1

        item = sumario.items[0]
        assert item.identificador == "BOA-007938287"
        assert item.titulo.startswith("ORDEN EEI/1987/2023")
        assert item.seccion_nombre == "I. Disposiciones Generales"
        assert item.epigrafe == "ORDEN"
        # El acento sobrevive al prólogo ISO-8859-1 sin que este módulo lo toque: lo resuelve
        # `xml_safe` leyendo la declaración del propio documento.
        assert "ECONOMÍA" in item.departamento

    def test_la_url_del_cuerpo_apunta_a_la_posicion_del_registro(self) -> None:
        """La posición es la única dirección que ofrece la fuente; se compone aquí, 1-based."""
        sumario = boa.parsear_sumario(_documento(_REGISTRO, _SEGUNDO), FECHA)

        assert "DOCS=1-1" in sumario.items[0].url_xml
        assert "DOCS=2-2" in sumario.items[1].url_xml

    def test_descarta_el_registro_de_otra_fecha_y_no_lo_corrige(self) -> None:
        """Pedir el día X y archivar el Y corrompe el archivo de la 6.5 sin dejar rastro."""
        otro_dia = _REGISTRO.replace("<fecha>20240110</fecha>", "<fecha>20240111</fecha>")

        sumario = boa.parsear_sumario(_documento(_REGISTRO, otro_dia), FECHA)

        assert [i.identificador for i in sumario.items] == ["BOA-007938287"]

    def test_descarta_el_registro_sin_numero_de_control_valido(self) -> None:
        malo = _REGISTRO.replace("<docn>007938287</docn>", "<docn>../../etc/passwd</docn>")

        sumario = boa.parsear_sumario(_documento(malo, _SEGUNDO), FECHA)

        assert [i.identificador for i in sumario.items] == ["BOA-007938288"]

    def test_falla_si_no_queda_ningun_registro_utilizable(self) -> None:
        """Un sumario vacío no se ingiere como día sin boletín: es una respuesta anómala."""
        malo = _REGISTRO.replace("<docn>007938287</docn>", "<docn></docn>")

        with pytest.raises(SumarioInvalido):
            boa.parsear_sumario(_documento(malo), FECHA)

    def test_falla_si_la_respuesta_no_trae_registros(self) -> None:
        with pytest.raises(SumarioInvalido):
            boa.parsear_sumario(_documento(), FECHA)

    def test_no_ingiere_a_medias_un_dia_que_llega_al_tope(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Truncar en silencio deja invisible lo que falta, que es el fallo que no se permite."""
        monkeypatch.setattr(boa, "MAX_ITEMS_POR_DIA", 2)

        with pytest.raises(SumarioInvalido, match="tope"):
            boa.parsear_sumario(_documento(_REGISTRO, _SEGUNDO), FECHA)


class TestParsearCuerpo:
    """El control que sostiene el direccionamiento por posición (ADR 0028)."""

    def test_acepta_el_cuerpo_de_la_norma_pedida(self) -> None:
        registro = boa.parsear_cuerpo(_documento(_REGISTRO), "BOA-007938287")

        assert registro.findtext("docn") == "007938287"

    def test_rechaza_el_cuerpo_de_otra_norma(self) -> None:
        """Si la fuente reordena el día, la posición 1 deja de ser la misma disposición.

        Sin esta comprobación se archivaría el texto de una norma bajo el identificador de
        otra, y el archivo afirmaría en falso qué decía cada cual. Es el modo de fallo que la
        6.5 existe para impedir, y el único que este direccionamiento puede producir.
        """
        with pytest.raises(SumarioInvalido, match="007938288"):
            boa.parsear_cuerpo(_documento(_SEGUNDO), "BOA-007938287")

    def test_rechaza_una_respuesta_con_varios_registros(self) -> None:
        with pytest.raises(SumarioInvalido):
            boa.parsear_cuerpo(_documento(_REGISTRO, _SEGUNDO), "BOA-007938287")


class TestTextoPlano:
    def test_deriva_el_articulado_y_no_los_metadatos_del_registro(self) -> None:
        """Sin la rama del BOA caería al árbol completo y el emisor entraría como articulado.

        Eso no rompe nada visiblemente: llena el texto de vocabulario administrativo que el
        prefiltro léxico lee como señal. Es el mismo tipo de falso positivo que el bloque
        `<analisis>` del BOE cuando se cae al caso de respaldo.
        """
        texto = texto_plano(xml_safe.parse(_documento(_REGISTRO)))

        assert texto.startswith("El Estatuto de Autonomía de Aragón")
        assert "DEPARTAMENTO DE ECONOMÍA" not in texto
        assert "ORDEN EEI/1987/2023" not in texto


class TestDiaSinBoletin:
    """Un día sin boletín no da 404 ni una lista vacía: sirve la portada del diario.

    Y hay que reconocerlo **antes** de tocar el parser. Si el HTML llegara a `xml_safe` saltaría
    `DtdForbidden` —correctamente— pero el worker lo trata como fallo de control de seguridad y
    aborta la tanda entera: cada fin de semana mataría un bloque de backfill. Pasó de verdad, en
    la primera ejecución del backfill del BOA (2026-08-01 y 02, sábado y domingo).
    """

    PORTADA = b'<!DOCTYPE html><html lang="es-ES"><head><title>BOA</title></head></html>'

    def test_el_sumario_lo_trata_como_dia_sin_boletin(self) -> None:
        with pytest.raises(SumarioNoDisponible):
            boa.parsear_sumario(self.PORTADA, FECHA)

    def test_el_cuerpo_lo_trata_como_respuesta_invalida(self) -> None:
        """Aquí no vale «no hay boletín»: el día existe, su sumario se parseó."""
        with pytest.raises(SumarioInvalido):
            boa.parsear_cuerpo(self.PORTADA, "BOA-007938287")

    def test_el_html_no_llega_nunca_al_parser_de_xml(self) -> None:
        """Que esto se reconozca aquí NO relaja `xml_safe`: el HTML no se parsea, se rechaza."""
        with pytest.raises(SumarioNoDisponible) as capturado:
            boa.parsear_sumario(b"   " + self.PORTADA, FECHA)

        assert "DOCTYPE" not in str(capturado.value)
