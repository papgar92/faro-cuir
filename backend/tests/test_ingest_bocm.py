"""Tests del ingestor del BOCM (ADR 0034), quinta fuente y cuarta autonómica.

Sobre XML **real recortado** (`fixtures/bocm_sumario_20260904_recortado.xml`), no inventado: lo
que hay que fijar es la estructura que el BOCM tiene, no la que uno recuerda.

Cuatro cosas se prueban aquí, y las dos primeras son las que rompen en silencio:

1. **La deduplicación.** El sumario del BOCM repite la lista entera en triángulo: el 2026-09-04
   trae 2.701 elementos `<disposicion>` para 73 disposiciones reales. Sin deduplicar, la fase 2
   pediría 2.701 cuerpos y el archivo tendría 37 copias de cada norma.
2. **Que la fecha se contrasta contra `<identificador>` y NO contra `<fecha_publicacion>`**, que
   en esta fuente es sistemáticamente el día anterior. Es el test que impide que alguien
   "arregle" el módulo usando el campo de nombre obvio y desplace la fuente entera un día.
3. Que el contexto (sección, apartado, organismo) llega hasta cada disposición, incluida la
   sección local — que es lo que hace que esta fuente aporte el nivel local de la sección 1.
4. Que un cuerpo que no es el que se pidió no se archiva.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from app.ingest import bocm
from app.ingest.boe import SumarioInvalido
from app.pipeline.texto import texto_plano
from app.security import xml_safe

FECHA = datetime.date(2026, 9, 4)

_FIXTURE = Path(__file__).parent / "fixtures" / "bocm_sumario_20260904_recortado.xml"


@pytest.fixture(scope="module")
def sumario_crudo() -> bytes:
    return _FIXTURE.read_bytes()


def test_url_del_sumario_solo_lleva_la_fecha() -> None:
    """Ni número de edición ni nada que haya que resolver antes. Es lo que abarata esta fuente."""
    assert bocm.url_sumario(FECHA) == (
        "https://www.bocm.es/boletin/CM_Boletin_BOCM/2026/09/04/BOCM-20260904.xml"
    )


def test_deduplica_la_lista_repetida(sumario_crudo: bytes) -> None:
    """La trampa 1: la fixture trae cinco `<disposicion>` para tres disposiciones reales."""
    assert sumario_crudo.count(b"<disposicion ") == 5

    sumario = bocm.parsear_sumario(sumario_crudo, FECHA)

    identificadores = [item.identificador for item in sumario.items]
    assert identificadores == [
        "BOCM-20260904-1",
        "BOCM-20260904-2",
        "BOCM-20260904-3",
    ]


def test_la_fecha_se_toma_del_identificador_y_no_de_fecha_publicacion(
    sumario_crudo: bytes,
) -> None:
    """La trampa 2, y es la que envenena el archivo sin hacer ruido.

    El sumario del 4 de septiembre declara `<fecha_publicacion>2026/09/03</fecha_publicacion>`.
    Verificado en tres días seguidos: siempre es el día anterior. Si el módulo se apoyara en ese
    campo, o rechazaría todos los días o archivaría cada boletín bajo el día de antes, y la
    afirmación de la 6.5 —«el día X esto decía exactamente esto»— quedaría desplazada para toda
    la fuente sin que fallara nada visiblemente.
    """
    assert b"<fecha_publicacion>2026/09/03</fecha_publicacion>" in sumario_crudo

    sumario = bocm.parsear_sumario(sumario_crudo, FECHA)

    assert sumario.fecha_publicacion == FECHA
    assert sumario.identificador == "BOCM-20260904"
    assert sumario.numero_diario == "211"


def test_pedir_un_dia_y_recibir_otro_no_se_ingiere(sumario_crudo: bytes) -> None:
    """Archivar el contenido del día Y bajo el día X es la corrupción que la 6.5 no admite."""
    with pytest.raises(SumarioInvalido, match="dice ser BOCM-20260904"):
        bocm.parsear_sumario(sumario_crudo, datetime.date(2026, 9, 3))


def test_cada_disposicion_conserva_su_contexto(sumario_crudo: bytes) -> None:
    """Sección, apartado y organismo son de grupo, y tienen que llegar a la disposición correcta.

    La tercera es del ayuntamiento de Alcalá de Henares: **el nivel local de la sección 1**, que
    entra en el sistema por primera vez con esta fuente porque Madrid es uniprovincial y no tiene
    BOP donde publicar sus ordenanzas.
    """
    items = {item.identificador: item for item in bocm.parsear_sumario(sumario_crudo, FECHA).items}

    autonomica = items["BOCM-20260904-1"]
    assert autonomica.seccion_nombre == "I. COMUNIDAD DE MADRID"
    assert autonomica.epigrafe == "A) Disposiciones Generales"
    assert autonomica.departamento.startswith("CONSEJERÍA DE MEDIO AMBIENTE")

    local = items["BOCM-20260904-3"]
    assert local.seccion_nombre == "III. ADMINISTRACIÓN LOCAL AYUNTAMIENTOS"
    assert local.departamento == "ALCALÁ DE HENARES"


def test_la_url_del_cuerpo_la_declara_la_propia_fuente(sumario_crudo: bytes) -> None:
    """No se compone a mano: el sumario trae `url_xml` por disposición y se usa esa.

    Sigue pasando por `url_guard` como cualquier otra URL de la fase 2 (6.2): que la declare el
    sumario oficial es lo que la hace legítima, no lo que la exime.
    """
    primera = bocm.parsear_sumario(sumario_crudo, FECHA).items[0]
    assert primera.url_xml == (
        "https://www.bocm.es/boletin/CM_Orden_BOCM/2026/09/04/BOCM-20260904-1.xml"
    )
    assert primera.url_pdf is not None
    assert primera.url_pdf.endswith("BOCM-20260904-1.PDF")


def test_un_sumario_sin_metadatos_no_se_da_por_bueno() -> None:
    with pytest.raises(SumarioInvalido, match="no contiene metadatos"):
        bocm.parsear_sumario(b"<sumario><diario/></sumario>", FECHA)


def test_una_disposicion_de_otro_dia_dentro_del_sumario_lo_invalida() -> None:
    """El BOCYL arrastra un enlace fijo de 2022 en todas sus páginas (ADR 0029).

    El BOCM no lo hace, pero la comprobación está igual: cuesta una línea y cierra la puerta a
    que el archivo afirme que algo se publicó un día en el que no se publicó.
    """
    intruso = """<sumario>
      <metadatos><identificador>BOCM-20260904</identificador><numero>211</numero></metadatos>
      <diario numero="211"><secciones><seccion nombre="I"><apartado nombre="A">
        <organismo nombre="X"><disposicion numero="1">
          <identificador>BOCM-20220118-9</identificador>
          <titulo>De otro día</titulo>
          <url_xml>https://www.bocm.es/x.xml</url_xml>
        </disposicion></organismo>
      </apartado></seccion></secciones></diario>
    </sumario>""".encode()

    with pytest.raises(SumarioInvalido, match="no es del 2026-09-04"):
        bocm.parsear_sumario(intruso, FECHA)


# --- El cuerpo ------------------------------------------------------------------------------
#
# Recortado del real (`BOCM-20260904-1`, descargado el 2026-09-06). **Sin prólogo `<?xml`**: el
# BOCM sirve así su XML, sumario y cuerpo, y por eso `parsear_cuerpo` no lo exige.
_CUERPO = b"""<documento>
  <metadatos>
    <identificador>BOCM-20260904-1</identificador>
    <departamento>CONSEJER\xc3\x8dA DE MEDIO AMBIENTE</departamento>
    <rango>DECRETO</rango>
    <fecha_publicacion>2026/09/04</fecha_publicacion>
  </metadatos>
  <analisis>
    <seccion>I. COMUNIDAD DE MADRID</seccion>
    <apartado>A) Disposiciones Generales</apartado>
    <tipo_disposicion>DECRETO</tipo_disposicion>
  </analisis>
  <texto>Decreto 71/2026, de 2 de septiembre, por el que se aprueba el Reglamento.</texto>
</documento>"""


def test_el_cuerpo_se_valida_por_identificador_exacto() -> None:
    """El XML declara el suyo, así que la comprobación es una igualdad, no una reconstrucción."""
    raiz = bocm.parsear_cuerpo(_CUERPO, "BOCM-20260904-1")
    assert raiz.findtext("./metadatos/identificador") == "BOCM-20260904-1"


def test_un_cuerpo_que_no_es_el_pedido_no_se_archiva() -> None:
    with pytest.raises(SumarioInvalido, match="dice ser BOCM-20260904-1"):
        bocm.parsear_cuerpo(_CUERPO, "BOCM-20260904-2")


def test_texto_plano_ya_sabia_leer_el_cuerpo_del_bocm() -> None:
    """La forma del cuerpo del BOCM es la del BOE: `documento > metadatos, analisis, texto`.

    Por eso esta fuente no añadió una rama a `pipeline/texto.py` —y `VERSION_TEXTO_PLANO` no
    sube—: el `./texto` de primer nivel que el BOE estrenó vale tal cual. Que el `<analisis>` se
    quede fuera importa: es ruido para el extractor y falsos positivos para el prefiltro léxico.
    """
    texto = texto_plano(xml_safe.parse(_CUERPO))

    assert texto.startswith("Decreto 71/2026")
    assert "COMUNIDAD DE MADRID" not in texto
