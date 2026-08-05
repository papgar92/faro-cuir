"""Tests de la ingesta del BOE.

El fixture `boe_sumario_20241219_recortado.xml` es un recorte de un sumario **real**
descargado de la API del BOE (2024-12-19): se han quitado secciones e items para dejarlo
manejable, pero ni la estructura ni los textos son inventados. Conserva a propósito los dos
encajes distintos del `item` (bajo `departamento` y bajo `epigrafe`).
"""

from __future__ import annotations

import datetime
from pathlib import Path

import httpx
import pytest

from app.ingest import boe
from app.ingest.boe import SumarioInvalido, SumarioNoDisponible
from app.security.url_guard import HostNotAllowed
from app.security.xml_safe import DtdForbidden

FIXTURES = Path(__file__).parent / "fixtures"
FECHA = datetime.date(2024, 12, 19)


@pytest.fixture
def sumario_crudo() -> bytes:
    return (FIXTURES / "boe_sumario_20241219_recortado.xml").read_bytes()


# --- Construcción de la URL ---------------------------------------------------------------


def test_la_url_del_sumario_usa_el_formato_de_fecha_del_boe() -> None:
    assert boe.url_sumario(FECHA) == "https://www.boe.es/datosabiertos/api/boe/sumario/20241219"


# --- Parseo ---------------------------------------------------------------------------------


def test_lee_los_metadatos_del_sumario(sumario_crudo: bytes) -> None:
    sumario = boe.parsear_sumario(sumario_crudo)
    assert sumario.identificador == "BOE-S-2024-305"
    assert sumario.fecha_publicacion == FECHA
    assert sumario.numero_diario == "305"


def test_recoge_los_items_de_los_dos_encajes(sumario_crudo: bytes) -> None:
    """En el sumario real unos items cuelgan del departamento y otros de un epígrafe.

    Recorrer solo `departamento/item` deja fuera casi la mitad de las disposiciones del día,
    y el fallo sería silencioso: parecería que el BOE publicó menos cosas.
    """
    sumario = boe.parsear_sumario(sumario_crudo)
    epigrafes = {item.epigrafe for item in sumario.items}
    assert None in epigrafes, "falta el item que cuelga directo del departamento"
    assert epigrafes - {None}, "falta el item que cuelga de un epigrafe"


def test_conserva_el_contexto_de_cada_item(sumario_crudo: bytes) -> None:
    sumario = boe.parsear_sumario(sumario_crudo)
    item = next(i for i in sumario.items if i.identificador == "BOE-A-2024-26484")
    assert item.seccion_codigo == "1"
    assert item.seccion_nombre == "I. Disposiciones generales"
    assert item.departamento == "MINISTERIO DE HACIENDA"
    assert item.titulo.startswith("Orden HAC/1432/2024")
    assert item.url_xml == "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2024-26484"
    assert item.url_pdf is not None


def test_comprueba_que_la_fecha_del_contenido_es_la_pedida(sumario_crudo: bytes) -> None:
    """Pedir el día X y archivar el día Y corrompería el archivo de forma difícil de detectar."""
    with pytest.raises(SumarioInvalido, match="2024-12-18"):
        boe.parsear_sumario(sumario_crudo, fecha_esperada=datetime.date(2024, 12, 18))


def test_acepta_la_fecha_correcta(sumario_crudo: bytes) -> None:
    sumario = boe.parsear_sumario(sumario_crudo, fecha_esperada=FECHA)
    assert sumario.fecha_publicacion == FECHA


def test_detecta_que_no_hay_sumario_para_esa_fecha() -> None:
    """Los domingos y festivos no hay BOE. No es un error nuestro, es un dia sin boletin."""
    payload = b"""<?xml version="1.0"?>
    <response><status><code>404</code><text>No se encontro el sumario</text></status></response>
    """
    with pytest.raises(SumarioNoDisponible):
        boe.parsear_sumario(payload)


@pytest.mark.parametrize(
    ("payload", "motivo"),
    [
        (b"<response><status><code>200</code></status></response>", "sin data/sumario"),
        (
            b"<response><status><code>200</code></status><data><sumario>"
            b"<metadatos><fecha_publicacion>no-es-fecha</fecha_publicacion></metadatos>"
            b"</sumario></data></response>",
            "fecha ilegible",
        ),
        (
            b"<response><status><code>200</code></status><data><sumario>"
            b"<metadatos><fecha_publicacion>20241219</fecha_publicacion></metadatos>"
            b"</sumario></data></response>",
            "sin diario",
        ),
    ],
)
def test_rechaza_sumarios_incompletos(payload: bytes, motivo: str) -> None:
    """No se rellena a ojo lo que falte: si el sumario no tiene la forma esperada, se para."""
    with pytest.raises(SumarioInvalido):
        boe.parsear_sumario(payload)


def test_rechaza_identificadores_con_caracteres_inesperados() -> None:
    """El identificador acaba en base de datos y en logs; no se acepta cualquier texto."""
    payload = b"""<?xml version="1.0"?>
    <response><status><code>200</code></status><data><sumario>
      <metadatos><fecha_publicacion>20241219</fecha_publicacion></metadatos>
      <diario numero="305">
        <sumario_diario><identificador>../../etc/passwd</identificador></sumario_diario>
      </diario>
    </sumario></data></response>
    """
    with pytest.raises(SumarioInvalido, match="caracteres inesperados"):
        boe.parsear_sumario(payload)


def test_el_parseo_pasa_por_xml_safe() -> None:
    """Un sumario con DOCTYPE muere en xml_safe, no en el codigo de este modulo."""
    payload = b"""<?xml version="1.0"?>
    <!DOCTYPE response [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
    <response><status><code>200</code></status></response>
    """
    with pytest.raises(DtdForbidden):
        boe.parsear_sumario(payload)


# --- Descarga --------------------------------------------------------------------------------


def test_la_descarga_pasa_por_el_guardia_de_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    """No es un test del guardia, es un test de que la ingesta no lo esquiva.

    Se apunta la plantilla de URL a un dominio que no esta en la allowlist. Si
    `descargar_sumario` usara httpx directamente, la peticion saldria; al pasar por
    `url_guard.fetch` se rechaza antes de abrir ningun socket.
    """
    monkeypatch.setattr(boe, "PLANTILLA_URL_SUMARIO", "https://atacante.example/sumario/{fecha}")
    with pytest.raises(HostNotAllowed):
        boe.descargar_sumario(FECHA)


def test_un_dia_sin_boletin_no_es_un_error_del_sistema() -> None:
    """El BOE devuelve 404 los domingos. Si eso escalara como fallo, el cron avisaria cada
    domingo y esa alarma acabaria ignorandose, que es como se pierden las de verdad."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b"")

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(SumarioNoDisponible),
    ):
        boe.descargar_sumario(datetime.date(2024, 12, 22), client=client)


def test_otros_errores_http_si_se_propagan() -> None:
    """Un 500 del BOE no es 'no hay boletin': es que algo va mal y hay que enterarse."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"")

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        boe.descargar_sumario(FECHA, client=client)


def test_descarga_devuelve_los_bytes_sin_tocar(sumario_crudo: bytes) -> None:
    """Crudos e idénticos: el sha256 del archivo integro se calcula sobre esto."""
    peticiones: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        peticiones.append(request)
        return httpx.Response(200, content=sumario_crudo)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        contenido = boe.descargar_sumario(FECHA, client=client)

    assert contenido == sumario_crudo
    assert peticiones[0].headers["Host"] == "www.boe.es"
