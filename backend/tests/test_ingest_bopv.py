"""Tests del ingestor del BOPV (ADR 0035), sexta fuente y quinta autonómica.

Sobre las tres piezas reales recortadas —calendario, sumario y cuerpo—, no inventadas.

**La prueba que justifica este módulo entero es `test_un_dia_puede_traer_dos_ediciones`.** El
BOPV publica dos boletines el mismo día unas cinco veces cada 33 meses, y `enlaces` es una lista
de listas: quien la lea como si fuera una lista de cadenas se queda con la primera y **pierde un
boletín extraordinario entero, en silencio**. Es el modo de fallo que este proyecto existe para
no tener.

Las otras tres que importan:

1. Que las dos listas del calendario **no se emparejan si no cuadran en longitud**: emparejar por
   posición dos listas desiguales asigna a cada fecha el boletín de otra.
2. Que la **subsección se reinicia al cambiar de sección** — hay secciones que no la traen, y sin
   el reinicio heredarían la anterior. Es la familia del bug del título en el BOCYL.
3. Que el articulado del cuerpo se separa de sus metadatos, que aquí son **hermanos suyos** y no
   antepasados.
"""

from __future__ import annotations

import datetime

import pytest

from app.ingest import bopv
from app.ingest.boe import SumarioInvalido, SumarioNoDisponible
from app.pipeline.texto import texto_plano
from app.security import xml_safe

FECHA = datetime.date(2026, 9, 4)

# Calendario real recortado (`/bopv2/datos/092026.shtml`, descargado el 2026-09-06). Va en
# ISO-8859-1 como el original. Lo que importa es la forma de los dos arrays.
_CALENDARIO = """<html><head><script type='text/javascript'>
var rutaRaiz = cogerRutaRaiz();
var bopvIdioma = 'es';
var diasHabilitados = ['20260901','20260902','20260903','20260904'];
var enlaces = [['s26_0166.shtml'],['s26_0167.shtml'],['s26_0168.shtml'],['s26_0169.shtml']];
</script></head><body><div id='datepicker'></div></body></html>""".encode("iso-8859-1")

# El caso medido: el 4 de mayo de 2026 el BOPV publicó dos ediciones.
_CALENDARIO_DOBLE = """<html><head><script type='text/javascript'>
var diasHabilitados = ['20260430','20260504','20260505'];
var enlaces = [['s26_0079.shtml'],['s26_0080.shtml','s26_0081.shtml'],['s26_0082.shtml']];
</script></head></html>""".encode("iso-8859-1")


def test_un_dia_puede_traer_dos_ediciones() -> None:
    """Medido: cinco días en 33 meses. Quedarse con la primera pierde un extraordinario entero.

    `enlaces` es una lista **de listas**, y ese es el detalle en el que se pierde: leída como una
    lista de cadenas, `enlaces[i]` da el primer boletín del día y el segundo no existe para el
    sistema. Un boletín extraordinario es justo donde cae una disposición con prisa.
    """
    ediciones = bopv.parsear_calendario(_CALENDARIO_DOBLE, datetime.date(2026, 5, 4))
    assert ediciones == ("s26_0080", "s26_0081")


def test_el_calendario_resuelve_la_fecha_a_su_edicion() -> None:
    assert bopv.parsear_calendario(_CALENDARIO, FECHA) == ("s26_0169",)
    assert bopv.parsear_calendario(_CALENDARIO, datetime.date(2026, 9, 1)) == ("s26_0166",)


def test_un_dia_que_no_esta_en_el_calendario_es_un_dia_sin_boletin() -> None:
    """La sexta manera distinta de decirlo, y la única que lo dice para el mes entero.

    El BOE contesta 404, el DOGC una lista vacía, el BOA su portada, el BOCYL una página corta,
    el BOCM otro 404. El BOPV simplemente no pone ese día en el calendario.
    """
    assert bopv.parsear_calendario(_CALENDARIO, datetime.date(2026, 9, 5)) == ()


def test_dos_listas_de_distinta_longitud_no_se_emparejan() -> None:
    """Emparejar por posición dos listas desiguales asigna a cada fecha el boletín de otra."""
    roto = """<script>
    var diasHabilitados = ['20260901','20260902','20260903'];
    var enlaces = [['s26_0166.shtml'],['s26_0167.shtml']];
    </script>""".encode("iso-8859-1")

    with pytest.raises(SumarioInvalido, match="No se emparejan por posición"):
        bopv.parsear_calendario(roto, FECHA)


def test_un_calendario_sin_sus_arrays_no_se_interpreta() -> None:
    with pytest.raises(SumarioInvalido, match="no tiene la forma esperada"):
        bopv.parsear_calendario(b"<html><body>mantenimiento</body></html>", FECHA)


def test_las_urls_se_componen_con_la_carpeta_del_mes() -> None:
    """La carpeta del mes es estricta: `s26_0169.xml` da 404 bajo `/2026/08/`, comprobado."""
    assert bopv.url_calendario(FECHA) == "https://www.euskadi.eus/bopv2/datos/092026.shtml"
    assert bopv.url_sumario(FECHA, "s26_0169") == (
        "https://www.euskadi.eus/bopv2/datos/2026/09/s26_0169.xml"
    )
    # El sumario no publica la URL de cada disposición: se deriva del orden, con cinco dígitos.
    assert bopv.url_texto(FECHA, 3788) == (
        "https://www.euskadi.eus/bopv2/datos/2026/09/2603788a.xml"
    )
    assert bopv.url_texto(datetime.date(2024, 1, 2), 1) == (
        "https://www.euskadi.eus/bopv2/datos/2024/01/2400001a.xml"
    )


def test_una_edicion_inventada_no_llega_a_componer_una_url() -> None:
    """El nombre de la edición viene del calendario, o sea de fuera. Se valida antes de usarlo."""
    with pytest.raises(ValueError, match="mal formada"):
        bopv.url_sumario(FECHA, "../../etc/passwd")


# --- El sumario -----------------------------------------------------------------------------
#
# Recortado del real (`s24_0001.xml`). Es **plano**: sección, subsección y organismo van sueltas
# entre los pares título/orden, no los contienen. Y la segunda sección no trae subsección, que es
# lo que obliga a reiniciarla.
_SUMARIO = """<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><SUMARIO>
<BOPVSumarioSeccion>AUTORIDADES Y PERSONAL</BOPVSumarioSeccion>
<BOPVSumarioSubseccion>Oposiciones y concursos</BOPVSumarioSubseccion>
<BOPVSumarioOrganismo>AYUNTAMIENTO DE BASAURI</BOPVSumarioOrganismo>
<BOPVSumarioTitulo>ANUNCIO relativo a la Oferta de Empleo Público.</BOPVSumarioTitulo>
<BOPVSumarioOrden>1</BOPVSumarioOrden>
<BOPVSumarioOrganismo>AYUNTAMIENTO DE TRAPAGARAN</BOPVSumarioOrganismo>
<BOPVSumarioTitulo>ANUNCIO relativo a la Oferta de Empleo Público 2023.</BOPVSumarioTitulo>
<BOPVSumarioOrden>2</BOPVSumarioOrden>
<BOPVSumarioSeccion>OTRAS DISPOSICIONES</BOPVSumarioSeccion>
<BOPVSumarioOrganismo>DEPARTAMENTO DE TRABAJO Y EMPLEO</BOPVSumarioOrganismo>
<BOPVSumarioTitulo>RESOLUCIÓN de 13 de diciembre, del Director.</BOPVSumarioTitulo>
<BOPVSumarioOrden>3</BOPVSumarioOrden>
</SUMARIO>""".encode()

FECHA_SUMARIO = datetime.date(2024, 1, 2)


def test_el_sumario_plano_arrastra_las_cabeceras_de_grupo() -> None:
    sumario = bopv.parsear_sumario(_SUMARIO, FECHA_SUMARIO, "s24_0001")

    assert [item.identificador for item in sumario.items] == [
        "BOPV-D-20240102-1",
        "BOPV-D-20240102-2",
        "BOPV-D-20240102-3",
    ]
    # La sección se arrastra a las dos primeras; el organismo cambia en cada una.
    assert sumario.items[0].seccion_nombre == "AUTORIDADES Y PERSONAL"
    assert sumario.items[1].seccion_nombre == "AUTORIDADES Y PERSONAL"
    assert sumario.items[0].departamento == "AYUNTAMIENTO DE BASAURI"
    assert sumario.items[1].departamento == "AYUNTAMIENTO DE TRAPAGARAN"


def test_la_subseccion_se_reinicia_al_cambiar_de_seccion() -> None:
    """Hay secciones sin subsección. Sin el reinicio, heredarían la de la sección anterior.

    Es la misma familia que el bug del título en el BOCYL (ADR 0029): un valor de grupo que se
    arrastra más allá de su grupo y acaba etiquetando una norma con lo que dice otra.
    """
    items = bopv.parsear_sumario(_SUMARIO, FECHA_SUMARIO, "s24_0001").items

    assert items[0].epigrafe == "Oposiciones y concursos"
    assert items[2].epigrafe is None


def test_la_edicion_va_dentro_del_identificador_del_sumario() -> None:
    """Si no fuera así, las dos ediciones de un mismo día colisionarían.

    `_buscar_documento` busca por `identificador_oficial`: con el mismo, el segundo boletín se
    daría por ya ingerido y no se archivaría nunca.
    """
    primera = bopv.parsear_sumario(_SUMARIO, FECHA_SUMARIO, "s24_0001")
    segunda = bopv.parsear_sumario(_SUMARIO, FECHA_SUMARIO, "s24_0002")

    assert primera.identificador == "BOPV-S-20240102-0001"
    assert segunda.identificador == "BOPV-S-20240102-0002"
    assert primera.identificador != segunda.identificador


def test_un_orden_sin_titulo_delante_no_se_vigila() -> None:
    """No se inventa un título ni se hereda el de la anterior: se deja fuera y se dice."""
    sin_titulo = """<SUMARIO>
    <BOPVSumarioSeccion>ANUNCIOS</BOPVSumarioSeccion>
    <BOPVSumarioOrden>7</BOPVSumarioOrden>
    <BOPVSumarioTitulo>El que sí tiene título.</BOPVSumarioTitulo>
    <BOPVSumarioOrden>8</BOPVSumarioOrden>
    </SUMARIO>""".encode()

    items = bopv.parsear_sumario(sin_titulo, FECHA_SUMARIO, "s24_0001").items

    assert [item.identificador for item in items] == ["BOPV-D-20240102-8"]


def test_un_sumario_que_repite_un_orden_no_se_ingiere() -> None:
    repetido = b"""<SUMARIO>
    <BOPVSumarioTitulo>Una.</BOPVSumarioTitulo><BOPVSumarioOrden>4</BOPVSumarioOrden>
    <BOPVSumarioTitulo>Otra.</BOPVSumarioTitulo><BOPVSumarioOrden>4</BOPVSumarioOrden>
    </SUMARIO>"""

    with pytest.raises(SumarioInvalido, match="repite el orden 4"):
        bopv.parsear_sumario(repetido, FECHA_SUMARIO, "s24_0001")


# --- El cuerpo ------------------------------------------------------------------------------
#
# Recortado del real (`2400001a.xml`). Los metadatos son **hermanos** del articulado, no
# antepasados suyos: no hay contenedor que señalar.
_CUERPO = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<DOCUMENTO NEXPEI="196408"><BOPVSeccion>AUTORIDADES Y PERSONAL</BOPVSeccion>
<BOPVSubseccion>Oposiciones y concursos</BOPVSubseccion>
<BOPVOrganismo>AYUNTAMIENTO DE BASAURI</BOPVOrganismo>
<BOPVOrden>1</BOPVOrden>
<BOPVTitulo>ANUNCIO relativo a la Oferta de Empleo Público.</BOPVTitulo>
<BOPVDetalle>Por Resolución de Alcaldía se aprueba la modificación de la oferta.</BOPVDetalle>
<BOPVDetalle1>Contra la presente cabe recurso.</BOPVDetalle1>
<BOPVFirmaLugFec>En Basauri, a 18 de diciembre de 2023.</BOPVFirmaLugFec>
</DOCUMENTO>""".encode()


def test_el_cuerpo_se_valida_por_su_orden() -> None:
    """El cuerpo del BOPV no declara su fecha, así que se contrasta lo que sí declara."""
    raiz = bopv.parsear_cuerpo(_CUERPO, "BOPV-D-20240102-1")
    assert raiz.findtext("./BOPVOrden") == "1"


def test_un_cuerpo_que_no_es_el_pedido_no_se_archiva() -> None:
    with pytest.raises(SumarioInvalido, match="orden 1"):
        bopv.parsear_cuerpo(_CUERPO, "BOPV-D-20240102-2")


def test_el_articulado_se_separa_de_unos_metadatos_que_son_sus_hermanos() -> None:
    """Sin esta rama, `texto_plano` caería al árbol completo.

    Y entonces el prefiltro léxico vería el título, la sección y el organismo como si fueran
    articulado: la misma fuente de falsos positivos que el `<analisis>` del BOE.
    """
    texto = texto_plano(xml_safe.parse(_CUERPO))

    assert texto.startswith("Por Resolución de Alcaldía")
    assert "Contra la presente cabe recurso." in texto
    assert "AUTORIDADES Y PERSONAL" not in texto
    assert "AYUNTAMIENTO DE BASAURI" not in texto
    assert "ANUNCIO relativo" not in texto


def test_resolver_ediciones_avisa_de_un_dia_sin_boletin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un día sin boletín es una respuesta válida del mundo: el worker sale con 0."""
    monkeypatch.setattr(bopv, "descargar_calendario", lambda fecha, client=None: _CALENDARIO)

    with pytest.raises(SumarioNoDisponible, match="no publicó boletín"):
        bopv.resolver_ediciones(datetime.date(2026, 9, 5))
