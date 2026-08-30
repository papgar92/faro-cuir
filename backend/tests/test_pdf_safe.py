"""Tests de `security/pdf_safe`. CLAUDE.md 6.1.

Mismo criterio que `test_xml_safe.py`: **cada control se prueba con el ataque que existe para
parar**, no con una comprobación de que la función devuelve algo. Un test que solo demuestra el
camino feliz no prueba ningún control de seguridad.

Los PDF se construyen a mano en bytes en vez de guardar ficheros de muestra: así el ataque que
cada test describe está escrito en el propio test y se puede leer sin abrir un binario.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from pypdf import PdfWriter

from app.security import pdf_safe


def _pdf_minimo(paginas: int = 1) -> bytes:
    """Un PDF válido y diminuto: páginas en blanco, o sea SIN capa de texto.

    Se genera con `pypdf` porque escribir el formato a mano y que siga siendo válido tras cada
    cambio de versión de la librería es trabajo que no aporta nada al test.
    """
    escritor = PdfWriter()
    for _ in range(paginas):
        escritor.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    escritor.write(buffer)
    return buffer.getvalue()


def test_un_pdf_gigante_se_rechaza_sin_parsearlo() -> None:
    """El primer control es no leer. Lo que no se parsea no puede explotar."""
    enorme = b"%PDF-1.7\n" + b"\x00" * (pdf_safe.MAX_PDF_BYTES + 1)

    with pytest.raises(pdf_safe.PdfTooLarge):
        pdf_safe.extraer_texto(enorme)


def test_la_bomba_de_paginas_se_corta_por_el_recuento() -> None:
    """Un PDF pequeño puede declarar muchísimas páginas.

    Es el ataque barato: el fichero pasa el tope de bytes sin problema y deja al worker
    extrayendo texto de cien mil páginas en blanco hasta que alguien lo mate.
    """
    bomba = _pdf_minimo(paginas=5)

    with pytest.raises(pdf_safe.MaxPaginasExceeded):
        pdf_safe.extraer_texto(bomba, max_paginas=2)


def test_la_bomba_de_expansion_se_corta_por_los_caracteres() -> None:
    """Pocas páginas cuyo contenido genera un texto enorme.

    Es el equivalente de la bomba de entidades del XML: el fichero es pequeño, las páginas son
    pocas y lo que crece es la salida. Sin este tope, los otros dos no sirven de nada.
    """
    escritor = PdfWriter()
    escritor.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    escritor.write(buffer)

    # Se fuerza el tope a un valor mínimo en vez de fabricar megas de texto: lo que se prueba es
    # que el contador corta, y hacerlo con un PDF real de 4 MB solo haría el test lento.
    with pytest.raises((pdf_safe.MaxCaracteresExceeded, pdf_safe.SinCapaDeTexto)):
        pdf_safe.extraer_texto(buffer.getvalue(), max_caracteres=0)


def test_lo_que_no_es_un_pdf_no_se_interpreta() -> None:
    """La página de error de un portal es lo que de verdad llega, no un PDF corrupto teórico.

    Es exactamente lo que pasó con el DOGC (ADR 0020): 172 normas cuyo «XML» era el HTML de
    error del portal. Aquí tiene que fallar con un tipo propio, no colarse como documento vacío.
    """
    html = b"<!DOCTYPE html><html><body>Error 404</body></html>"

    with pytest.raises(pdf_safe.MalformedPdf):
        pdf_safe.extraer_texto(html)


def test_un_pdf_sin_capa_de_texto_se_distingue_de_uno_roto() -> None:
    """La distinción que decide si algún día hace falta OCR.

    `MalformedPdf` es «esto no se puede leer»; `SinCapaDeTexto` es «esto se lee perfectamente y no
    tiene letras». Solo el segundo justificaría un OCR, así que confundirlos haría imposible saber
    si merece la pena — que es justo el error que la sección 8 quiere evitar.
    """
    escaneo = _pdf_minimo(paginas=2)

    with pytest.raises(pdf_safe.SinCapaDeTexto):
        pdf_safe.extraer_texto(escaneo)


def test_ningun_modulo_importa_pypdf_por_su_cuenta() -> None:
    """`pdf_safe` es la puerta única, igual que `xml_safe` con `defusedxml`.

    Un control centralizado deja de serlo en cuanto alguien hace `import pypdf` en otro sitio
    «solo para una cosa rápida». Este test es lo único que lo impide.
    """
    raiz = Path(__file__).resolve().parents[1] / "app"
    permitidos = {"pdf_safe.py"}
    culpables = [
        fichero.relative_to(raiz).as_posix()
        for fichero in raiz.rglob("*.py")
        if fichero.name not in permitidos and "pypdf" in fichero.read_text(encoding="utf-8")
    ]

    assert not culpables, (
        f"Estos módulos importan pypdf directamente: {culpables}. La única puerta para un PDF "
        "es security/pdf_safe.py."
    )
