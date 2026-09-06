"""Tests del tercer nivel de cuerpo: HTML de portal (ADR 0036).

**El test que importa de este fichero es `test_una_pagina_de_error_sigue_siendo_ilegible`.** Es
la comprobación de que abrir el nivel HTML no ha abierto una puerta: la página de error real del
DOGC —la que motivó el estado `ilegible` en el ADR 0020, y de la que llegaron a colarse 172 como
si fueran normas— tiene que seguir sin producir ni un carácter de texto.

Lo demás son las tres obligaciones del nivel:

1. Contenedor **declarado y cerrado**: de un HTML cualquiera no se extrae nada.
2. Canario de tamaño: un contenedor que casa pero viene casi vacío no cuenta como cuerpo.
3. El recorte deja fuera el menú y el pie, que es lo que separa evidencia de mobiliario.
"""

from __future__ import annotations

from pathlib import Path

from app.pipeline.texto_html import (
    CONTENEDORES,
    MINIMO_CARACTERES,
    es_html,
    texto_de_html,
)

FIXTURES = Path(__file__).parent / "fixtures"

_CONTENEDOR_BON = "portlet_es_navarra_bon_detalle_portlet_anuncio_DetalleAnuncioPortlet"

_RELLENO = "El articulado de la norma, repetido lo bastante para pasar el canario de tamaño. " * 6


def _pagina(cuerpo: str) -> bytes:
    """Una página con la forma del BON: menú antes, pie después y el portlet en medio."""
    return f"""<!DOCTYPE html>
<html lang="es"><head><title>Anuncio</title>
<script>var seguimiento = "esto no es contenido";</script></head>
<body>
  <nav><ul><li><a href="/es/boletines">Índice de boletines</a></li></ul></nav>
  <section id="{_CONTENEDOR_BON}">
    <div class="portlet-body">{cuerpo}</div>
  </section>
  <footer><div class="contenido-boletin-oficial">
    Boletín Oficial de Navarra. Paseo Pablo Sarasate, 38. 31001 Pamplona.
  </div></footer>
</body></html>""".encode()


def test_reconoce_una_pagina_html_por_su_prologo() -> None:
    """Por el contenido, no por la extensión ni por la fuente. Mismo criterio que el `%PDF-`."""
    assert es_html(b"<!DOCTYPE html><html><body>x</body></html>")
    assert es_html(b"\n  <HTML>\n")
    assert not es_html(b'<?xml version="1.0"?><documento/>')
    assert not es_html(b"%PDF-1.7")


def test_recorta_el_articulado_y_deja_fuera_el_menu_y_el_pie() -> None:
    texto = texto_de_html(_pagina(f"<p>{_RELLENO}</p>"))

    assert texto.startswith("El articulado de la norma")
    assert "Índice de boletines" not in texto
    assert "Paseo Pablo Sarasate" not in texto
    # El `<script>` de la cabecera tampoco es contenido, ni aunque estuviera dentro.
    assert "seguimiento" not in texto


def test_de_un_html_sin_contenedor_declarado_no_se_extrae_nada() -> None:
    """La lista de contenedores es **cerrada**: no hay recorte genérico ni «el div más grande».

    Sin esto, cualquier página que llegara al almacén se convertiría en un cuerpo plausible, y el
    prefiltro la evaluaría como si fuera una norma.
    """
    ajena = f"<!DOCTYPE html><html><body><div class='texto'>{_RELLENO}</div></body></html>"

    assert texto_de_html(ajena.encode()) == ""


def test_un_contenedor_casi_vacio_no_cuenta_como_cuerpo() -> None:
    """El canario. Una plantilla vacía daría un texto corto que el prefiltro leería como
    «aquí no hay nada relevante»: el falso negativo invisible de 7.1."""
    corto = "Contenido no disponible."
    assert len(corto) < MINIMO_CARACTERES

    assert texto_de_html(_pagina(f"<p>{corto}</p>")) == ""


def test_una_pagina_de_error_sigue_siendo_ilegible() -> None:
    """La regresión que este nivel no puede permitirse (ADR 0020).

    Del DOGC llegaron 172 páginas de error archivadas como si fueran normas, y lo único que
    impidió que entraran al pipeline fue que `xml_safe` no podía parsearlas. Ahora hay una rama
    que sí sabe leer HTML, así que la protección tiene que venir de otro sitio: **de que esa
    página no trae ninguno de los contenedores declarados**.
    """
    error = (FIXTURES / "dogc_pagina_de_error_recortada.html").read_bytes()

    assert texto_de_html(error) == ""


def test_el_recorte_sobrevive_a_etiquetas_sin_cerrar() -> None:
    """El HTML real trae `<p>` y `<li>` sin cerrar. Un desapilado a ciegas dejaría la pila
    desalineada y el recorte se cortaría a mitad del articulado, o se comería el pie."""
    sucio = f"<p>{_RELLENO}<li>Uno<li>Dos<p>{_RELLENO}"
    texto = texto_de_html(_pagina(sucio))

    assert texto.count("El articulado de la norma") >= 2
    assert "Paseo Pablo Sarasate" not in texto


def test_la_lista_de_contenedores_es_explicita() -> None:
    """Añadir una fuente de este nivel es añadir una entrada aquí, con su ADR. No hay atajo."""
    assert [c.fuente for c in CONTENEDORES] == ["BON"]
    assert CONTENEDORES[0].valor == _CONTENEDOR_BON
