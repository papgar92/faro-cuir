"""Tests del ingestor del BON (ADR 0036), séptima fuente y primera del nivel HTML.

Cuatro cosas, y las dos primeras son las que rompen en silencio:

1. **Que la cabecera manda.** El BON no tiene calendario y su búsqueda por fecha **miente**
   —`?anio=&mes=&dia=` devuelve siempre el último boletín—, así que la única garantía de que lo
   archivado es del día que se pidió es que el propio sumario lo declare. Un sumario que no lo
   declare, o que declare otro día, no se archiva.
2. **Que un día puede traer dos boletines.** Los 253 y 254 son los dos del 16 de diciembre de
   2024, y el 254 trae una sola disposición. Quedarse con el primero perdería un extraordinario
   entero.
3. Que el título sale del **texto del enlace** y no de su atributo `title`, que lleva comillas
   sin escapar.
4. Que ámbito y sección se arrastran, y que la sección se reinicia al cambiar de ámbito.
"""

from __future__ import annotations

import datetime

import pytest

from app.ingest import bon
from app.ingest.boe import SumarioInvalido, SumarioNoDisponible

FECHA = datetime.date(2024, 1, 9)

# Cabecera real. La `º` va como entidad, que es como la sirve el portal.
_CABECERA = "BOLET&Iacute;N N&ordm; 6 - 9 de enero de 2024"

# Título real recortado. **Lleva comillas dentro del atributo `title` sin escapar**, tal cual:
# es la trampa, y por eso el título se lee del texto del enlace.
_TITULO = (
    "RESOLUCI&Oacute;N 834E/2023, por la que se aprueba la convocatoria de la subvenci&oacute;n "
    '"Subvenciones a entidades ciudadanas". Identificaci&oacute;n BDNS: 729128.'
)


def _sumario(cabecera: str = _CABECERA, cuerpo: str | None = None) -> bytes:
    if cuerpo is None:
        cuerpo = f"""
      <p class="hd r-hn3 b-ambito">1. Comunidad Foral de Navarra</p>
      <p class="hd r-hn4 b-seccion">1.4. Subvenciones, ayudas y becas</p>
      <p><a href="https://bon.navarra.es/es/anuncio/-/texto/2024/6/0" title="{_TITULO}">
        {_TITULO}</a></p>
      <p><a href="https://bon.navarra.es/es/anuncio/-/texto/2024/6/1" title="Otra">
        ORDEN FORAL 1/2024, por la que se regula el procedimiento.</a></p>
      <p class="hd r-hn3 b-ambito">2. Administraci&oacute;n Local de Navarra</p>
      <p><a href="https://bon.navarra.es/es/anuncio/-/texto/2024/6/2" title="Tres">
        ANUNCIO del Ayuntamiento de Pamplona.</a></p>"""
    return f"""<!DOCTYPE html><html><body>
      <nav><a href="/es/boletines">&Iacute;ndice de boletines</a></nav>
      <h2><a href="https://bon.navarra.es/es/boletin/-/sumario/2024/6">{cabecera}</a></h2>
      {cuerpo}
    </body></html>""".encode()


def test_las_urls_se_componen_con_ano_numero_y_orden() -> None:
    assert bon.url_sumario(2024, 6) == "https://bon.navarra.es/es/boletin/-/sumario/2024/6"
    # **El orden empieza en 0**, comprobado contra la fuente. Un rango que empezara en 1 dejaría
    # fuera la primera disposición de cada boletín, y nadie lo notaría.
    assert bon.url_texto(2024, 6, 0) == "https://bon.navarra.es/es/anuncio/-/texto/2024/6/0"


def test_un_numero_de_boletin_inventado_no_llega_a_componer_una_url() -> None:
    with pytest.raises(ValueError, match="fuera de rango"):
        bon.url_sumario(2024, 0)
    with pytest.raises(ValueError, match="fuera de rango"):
        bon.url_sumario(2024, bon.MAX_NUMERO + 1)


def test_lee_la_cabecera_que_declara_el_boletin() -> None:
    cabecera = bon.parsear_cabecera(_sumario())

    assert cabecera is not None
    assert cabecera.numero == 6
    assert cabecera.fecha == FECHA
    assert cabecera.extraordinario is False


def test_reconoce_un_extraordinario_porque_la_fuente_lo_dice() -> None:
    """El BON etiqueta sus extraordinarios; el BOPV (ADR 0035) no. Se aprovecha."""
    cabecera = bon.parsear_cabecera(
        _sumario("BOLET&Iacute;N N&ordm; 254 - 16 de diciembre de 2024 - EXTRAORDINARIO")
    )

    assert cabecera is not None
    assert cabecera.numero == 254
    assert cabecera.extraordinario is True


def test_un_numero_que_no_existe_no_trae_cabecera() -> None:
    """El BON responde **200 con página vacía**, no 404. Es su forma de decir que no hay."""
    assert bon.parsear_cabecera(b"<!DOCTYPE html><html><body></body></html>") is None


def test_un_sumario_que_dice_ser_de_otro_dia_no_se_archiva() -> None:
    """La garantía entera de esta fuente. Su búsqueda por fecha miente, así que si el documento
    no declara el día que se pidió, archivarlo sería afirmar algo que no consta."""
    with pytest.raises(SumarioInvalido, match="dice ser el 6 del 2024-01-09"):
        bon.parsear_sumario(_sumario(), datetime.date(2024, 1, 10), 6)


def test_un_sumario_sin_cabecera_no_se_archiva() -> None:
    vacio = b"<!DOCTYPE html><html><body><p>Mantenimiento</p></body></html>"

    with pytest.raises(SumarioInvalido, match="no declara su cabecera"):
        bon.parsear_sumario(vacio, FECHA, 6)


def test_el_titulo_sale_del_texto_del_enlace_y_no_del_atributo() -> None:
    """El `title` lleva comillas sin escapar: leerlo como atributo lo trunca en la primera.

    El título es lo que prioriza la cola del extractor (7.1) y lo que lee una persona en el
    panel. Uno truncado a mitad no falla nada visiblemente, solo empeora las dos cosas.
    """
    items = bon.parsear_sumario(_sumario(), FECHA, 6).items

    assert items[0].titulo.startswith("RESOLUCIÓN 834E/2023")
    assert items[0].titulo.endswith("BDNS: 729128.")
    assert '"Subvenciones a entidades ciudadanas"' in items[0].titulo


def test_ambito_y_seccion_se_arrastran_y_la_seccion_se_reinicia() -> None:
    """Cabeceras de grupo, como en el BOCYL y el BOPV. Y la sección vive dentro del ámbito: sin
    reiniciarla, la disposición local heredaría «Subvenciones, ayudas y becas»."""
    items = bon.parsear_sumario(_sumario(), FECHA, 6).items

    assert [i.identificador for i in items] == [
        "BON-D-2024-6-0",
        "BON-D-2024-6-1",
        "BON-D-2024-6-2",
    ]
    assert items[0].seccion_nombre == "1. Comunidad Foral de Navarra"
    assert items[0].epigrafe == "1.4. Subvenciones, ayudas y becas"
    assert items[2].seccion_nombre == "2. Administración Local de Navarra"
    assert items[2].epigrafe is None


def test_un_sumario_con_cabecera_pero_sin_disposiciones_no_se_da_por_bueno() -> None:
    with pytest.raises(SumarioInvalido, match="no trae ninguna disposición"):
        bon.parsear_sumario(_sumario(cuerpo=""), FECHA, 6)


# --- La resolución de fecha -----------------------------------------------------------------


def _portal(por_numero: dict[int, tuple[int, int, int]]):  # type: ignore[no-untyped-def]
    """Un BON de mentira: números de boletín con la fecha que declara cada uno."""

    def cabecera(anyo: int, numero: int, *, client: object = None) -> bon.Cabecera | None:
        if numero not in por_numero:
            return None
        d, m, a = por_numero[numero]
        return bon.Cabecera(numero=numero, fecha=datetime.date(a, m, d), extraordinario=False)

    return cabecera


def _un_boletin_al_dia(hasta: int) -> dict[int, tuple[int, int, int]]:
    """Un año de mentira con un boletín por día natural: monótono, que es lo que la bisección
    necesita y lo que la fuente real cumple."""
    origen = datetime.date(2024, 1, 1)
    fechas = {}
    for n in range(1, hasta + 1):
        f = origen + datetime.timedelta(days=n - 1)
        fechas[n] = (f.day, f.month, f.year)
    return fechas


def test_encuentra_el_boletin_de_una_fecha_por_biseccion(monkeypatch: pytest.MonkeyPatch) -> None:
    """El número es monótono en la fecha dentro del año, comprobado sobre 2024."""
    calendario = _un_boletin_al_dia(200)
    monkeypatch.setattr(bon, "_cabecera_de", _portal(calendario))

    numeros = bon.resolver_ediciones(datetime.date(2024, 3, 20))

    assert numeros == (80,)
    assert calendario[80] == (20, 3, 2024)


def test_recoge_las_dos_ediciones_de_un_dia(monkeypatch: pytest.MonkeyPatch) -> None:
    """El 16 de diciembre de 2024 el BON publicó el 253 y el 254. Los dos, o se pierde uno.

    La bisección puede caer en cualquiera de los dos; por eso después se barren los vecinos en
    las dos direcciones hasta que la fecha cambia.
    """
    calendario = _un_boletin_al_dia(252)
    calendario[253] = (16, 12, 2024)
    calendario[254] = (16, 12, 2024)
    monkeypatch.setattr(bon, "_cabecera_de", _portal(calendario))

    assert bon.resolver_ediciones(datetime.date(2024, 12, 16)) == (253, 254)


def test_un_dia_sin_boletin_no_es_un_fallo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bon, "_cabecera_de", _portal({1: (2, 1, 2024), 2: (3, 1, 2024)}))

    with pytest.raises(SumarioNoDisponible, match="no publicó boletín"):
        bon.resolver_ediciones(datetime.date(2024, 6, 15))


def test_la_busqueda_tiene_tope_y_para_diciendolo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Seguir pidiendo a ciegas contra un portal ajeno no es aceptable (6.2).

    Se simula un portal donde **todos** los boletines declaran la misma fecha: el barrido de
    vecinos no encontraría nunca el borde, así que el tope es lo único que lo para.
    """
    monkeypatch.setattr(bon, "_cabecera_de", _portal({n: (9, 1, 2024) for n in range(1, 400)}))

    with pytest.raises(SumarioInvalido, match="agotado el tope"):
        bon.resolver_ediciones(FECHA)


# --- El cuerpo ------------------------------------------------------------------------------


def _cuerpo(cabecera: str = _CABECERA) -> bytes:
    return f"""<!DOCTYPE html><html><body>
      <section id="portlet_es_navarra_bon_detalle_portlet_anuncio_DetalleAnuncioPortlet">
        <h2>{cabecera}</h2><p>El articulado.</p>
      </section></body></html>""".encode()


def test_el_cuerpo_se_valida_por_la_cabecera_de_su_boletin() -> None:
    """No devuelve árbol, a diferencia de las otras seis: aquí el texto lo saca `texto_html`."""
    assert bon.parsear_cuerpo(_cuerpo(), "BON-D-2024-6-0") is None


def test_un_cuerpo_de_otro_boletin_no_se_archiva() -> None:
    with pytest.raises(SumarioInvalido, match="dice ser del boletín 6"):
        bon.parsear_cuerpo(_cuerpo(), "BON-D-2024-99-0")


def test_un_cuerpo_sin_cabecera_no_se_archiva() -> None:
    with pytest.raises(SumarioInvalido, match="no declara la cabecera"):
        bon.parsear_cuerpo(b"<!DOCTYPE html><html><body>error</body></html>", "BON-D-2024-6-0")
