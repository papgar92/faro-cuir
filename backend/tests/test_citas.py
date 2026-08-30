"""El eje referencial sacado del texto. ADR 0022.

Cada test de aquí corresponde a una trampa **medida**, no imaginada: las cuatro coincidencias
falsas que produjo la forma corta sobre los 264 cuerpos del DOGC el 2026-08-19. Un módulo que
busca citas de leyes en texto libre se llena de falsos positivos por caminos muy concretos, y son
esos los que hay que dejar clavados.
"""

from __future__ import annotations

import pytest

from app.pipeline.citas import cita_esperable, extraer_referencias_citadas, forma_larga
from app.pipeline.watchlist import NormaVigilada, Watchlist, watchlist

LISTA = Watchlist(
    version="test",
    normas=(
        NormaVigilada(
            identificador="BOE-A-2014-11990",
            titulo=(
                "Ley 11/2014, de 10 de octubre, para garantizar los derechos de lesbianas, gays, "
                "bisexuales, transgeneros e intersexuales (Catalunya)"
            ),
            nota="fixture",
            ambito="CT",
        ),
        NormaVigilada(
            identificador="BOE-A-2023-5366",
            titulo="Ley 4/2023, de 28 de febrero, para la igualdad real y efectiva de las personas",
            nota="fixture",
            ambito="estatal",
        ),
        NormaVigilada(
            identificador="BOE-A-2006-7899",
            titulo="Ley Organica 2/2006, de 3 de mayo, de Educacion",
            nota="fixture: la LOE, norma-vehiculo del ADR 0030",
            ambito="estatal",
            especificidad="vehiculo",
        ),
        NormaVigilada(
            identificador="BOE-A-2006-16212",
            titulo="Real Decreto 1030/2006, de 15 de septiembre, por el que se establece",
            nota="fixture: la cartera de servicios del SNS",
            ambito="estatal",
            especificidad="vehiculo",
        ),
        NormaVigilada(
            identificador="BOE-A-2021-11382",
            titulo="Ley 2/2021, de 7 de junio, de igualdad social y no discriminacion (Canarias)",
            nota="fixture",
            ambito="CN",
        ),
    ),
)


def _referencias(texto: str) -> dict[str, str]:
    return {r.identificador: r.verbo for r in extraer_referencias_citadas(texto, LISTA)}


class TestFormaLarga:
    def test_se_deriva_del_titulo(self) -> None:
        assert forma_larga("Ley 11/2014, de 10 de octubre, para garantizar") == (
            "Ley 11/2014, de 10 de octubre"
        )

    def test_un_titulo_sin_fecha_no_da_forma_de_cita(self) -> None:
        """Sin fecha solo queda la forma corta, y la forma corta **no vale** (ver la clase de
        abajo). Devolver `None` es lo correcto: esa entrada de la watchlist no se puede buscar
        en texto libre sin colisionar, y es mejor no buscarla que buscarla mal."""
        assert forma_larga("Ley 2/2016 de Identidad y Expresion de Genero (Madrid)") is None


class TestLasTrampasMedidas:
    """Las cuatro coincidencias falsas de la medición del 2026-08-19, una por test."""

    def test_decreto_ley_no_es_ley(self) -> None:
        """«Decreto ley 4/2023» contiene «ley 4/2023» y es otra norma, de otra administración."""
        texto = (
            "Artículo 3. Se modifica el artículo 1.2 letra b) del Decreto ley 4/2023, de 19 de "
            "diciembre, de necesidades financieras del sector público."
        )

        assert _referencias(texto) == {}

    def test_el_mismo_numero_en_otra_comunidad_no_cuenta(self) -> None:
        """La numeración de leyes se repite: la Ley 2/2021 de Canarias está vigilada, la Ley
        2/2021 de medidas fiscales de Catalunya no. Las separa la fecha, y por eso la fecha es
        obligatoria."""
        texto = (
            "Ciertamente, la Ley 2/2021, de 29 de diciembre, de medidas fiscales, financieras, "
            "administrativas y del sector público, mediante el artículo 81.3, añade un párrafo."
        )

        assert _referencias(texto) == {}

    def test_la_fecha_correcta_si_cuenta(self) -> None:
        """El control de que lo anterior no es un módulo que no encuentra nada nunca."""
        texto = "Se modifica el artículo 3 de la Ley 2/2021, de 7 de junio, de igualdad social."

        assert _referencias(texto) == {"BOE-A-2021-11382": "MODIFICA"}

    def test_citar_no_es_modificar(self) -> None:
        """El falso positivo que el eje léxico produce a destajo y que este eje existe para no
        repetir: mencionar una ley en el preámbulo no es tocarla."""
        texto = (
            "El presente decreto se dicta de conformidad con lo previsto en la Ley 11/2014, de "
            "10 de octubre, para garantizar los derechos de lesbianas."
        )
        referencias = extraer_referencias_citadas(texto, LISTA)

        assert [(r.identificador, r.verbo) for r in referencias] == [("BOE-A-2014-11990", "CITA")]
        assert not referencias[0].es_modificativa


class TestVerbos:
    @pytest.mark.parametrize(
        ("frase", "verbo"),
        [
            ("Se modifica el artículo 7 de la", "MODIFICA"),
            ("Se derogan los artículos 3 y 4 de la", "DEROGA"),
            ("Se añade una disposición adicional a la", "ANADE"),
            ("Se suprime el apartado 2 del artículo 8 de la", "SUPRIME"),
            ("Queda derogado el título III de la", "DEROGA"),
        ],
    )
    def test_el_verbo_de_delante_es_el_que_manda(self, frase: str, verbo: str) -> None:
        texto = f"{frase} Ley 11/2014, de 10 de octubre, para garantizar los derechos."

        assert _referencias(texto) == {"BOE-A-2014-11990": verbo}

    def test_un_verbo_demasiado_lejos_no_cuenta(self) -> None:
        """La ventana es de 200 caracteres hacia atrás. Sin límite, cualquier «se modifica» en
        la página anterior convertiría en modificación una cita del preámbulo."""
        texto = (
            "Se modifica el artículo 1 del Decreto 100/2020. " + "Relleno. " * 40 + "Todo ello "
            "conforme a la Ley 11/2014, de 10 de octubre."
        )

        assert _referencias(texto) == {"BOE-A-2014-11990": "CITA"}

    def test_gana_el_verbo_mas_fuerte_y_no_el_ultimo(self) -> None:
        """Si la norma aparece dos veces y solo una lleva verbo, la norma se modifica. Quedarse
        con la última coincidencia haría que el resultado dependiera del orden del documento."""
        texto = (
            "Visto lo dispuesto en la Ley 11/2014, de 10 de octubre. "
            "Artículo 1. Se deroga el artículo 5 de la Ley 11/2014, de 10 de octubre. "
            "Disposición final. Publíquese conforme a la Ley 11/2014, de 10 de octubre."
        )

        assert _referencias(texto) == {"BOE-A-2014-11990": "DEROGA"}


class TestFormaDelTexto:
    def test_las_tildes_no_estorban(self) -> None:
        texto = "Se modifica el artículo 7 de la Ley 11/2014, de 10 de octubre, para garantizar."

        assert _referencias(texto) == {"BOE-A-2014-11990": "MODIFICA"}

    def test_las_mayusculas_tampoco(self) -> None:
        texto = "SE MODIFICA EL ARTÍCULO 7 DE LA LEY 11/2014, DE 10 DE OCTUBRE."

        assert _referencias(texto) == {"BOE-A-2014-11990": "MODIFICA"}

    def test_un_salto_de_linea_dentro_de_la_cita_no_la_esconde(self) -> None:
        """El texto derivado viene con espacios colapsados, pero depender de eso ataría este
        módulo a una decisión de `texto_plano` y el fallo sería mudo."""
        texto = "Se modifica el artículo 7 de la Ley 11/2014,\n   de 10 de octubre."

        assert _referencias(texto) == {"BOE-A-2014-11990": "MODIFICA"}

    def test_el_recorte_que_se_guarda_sale_del_texto_original(self) -> None:
        """Lo que se enseña a quien revisa es el archivo, con sus tildes y sus mayúsculas, no la
        forma normalizada con la que se buscó. Si los offsets se desplazaran, esto lo delata."""
        texto = (
            "Disposición única. Se deroga el artículo 5 de la Ley 11/2014, de 10 de octubre, "
            "para garantizar los derechos."
        )
        (referencia,) = extraer_referencias_citadas(texto, LISTA)

        assert "Ley 11/2014, de 10 de octubre" in referencia.texto
        assert "Disposición" in referencia.texto

    def test_un_texto_vacio_no_rompe(self) -> None:
        assert extraer_referencias_citadas("", LISTA) == ()


def test_toda_norma_vigilada_de_rango_numerado_se_puede_citar() -> None:
    """Una entrada de la watchlist cuyo título no empiece por su forma de cita **queda fuera del
    eje referencial en texto sin que nada lo diga**, y ese es justo el fallo mudo que el proyecto
    no se permite.

    Se comprueba contra la watchlist real y no contra una de prueba: lo que hay que impedir es
    que alguien añada mañana una norma vigilada con el título escrito de otra forma y se quede a
    medio vigilar. Si esto se pone rojo, la solución es arreglar el título del fichero, no
    relajar el patrón — la forma corta ya se midió y no vale (ver `TestLasTrampasMedidas`).

    **El test se acotó a los rangos numerados el 2026-08-23, y no es una relajación.** Hasta
    entonces exigía forma de cita a *todas* las entradas, lo cual se pudo sostener mientras la
    watchlist fueron 24 leyes y reales decretos. Al entrar las dos Instrucciones de la DGSJFP —una
    de ellas la entrada que mejor encaja con la sección 1 de `CLAUDE.md`, porque una instrucción
    se cambia con otra instrucción y sin ruido— apareció la distinción que faltaba: una
    instrucción **no tiene número `N/AAAA` y por tanto no se cita así**, en ninguna redacción. No
    hay título que arreglar.

    Lo que el test sigue cazando es exactamente lo de antes: una norma que **sí lleva número** y
    aun así no encaja, que es la que está mal escrita. Lo que ya no hace es exigir lo imposible.
    """
    mal_escritas = [
        n.identificador
        for n in watchlist().normas
        if cita_esperable(n.titulo) and forma_larga(n.titulo) is None
    ]

    assert not mal_escritas, (
        f"estas normas vigiladas llevan número de norma y aun así no se pueden buscar como cita "
        f"en el texto: {mal_escritas}. El título tiene que EMPEZAR por «Ley N/AAAA, de D de mes» "
        "(o Real Decreto, Decreto, Ley Orgánica, Ley Foral)."
    )


def test_las_vigiladas_sin_forma_de_cita_estan_declaradas_y_contadas() -> None:
    """Las que quedan fuera del eje de citas se enumeran, para que el hueco no sea invisible.

    Es el mismo criterio que el estado `ilegible` del prefiltro (ADR 0020): lo que el sistema no
    puede hacer se cuenta aparte en vez de confundirse con lo que sí hace. Estas entradas **siguen
    disparando por el `<analisis>` del BOE**, que es donde viven sus modificaciones; lo que no
    pueden es detectarse por cita en el texto, y eso las hace invisibles para el DOGC y para
    cualquier fuente futura sin `<analisis>` — que es justo el agujero que el ADR 0022 abrió este
    eje para tapar.

    El test no fija **cuáles** son ni **cuántas**: fija que todas las que no se pueden citar sean
    de rango no numerado. Si algún día una con número acaba aquí, el test de arriba se pone rojo,
    que es donde tiene que doler.
    """
    sin_cita = [n for n in watchlist().normas if forma_larga(n.titulo) is None]

    assert all(not cita_esperable(n.titulo) for n in sin_cita), (
        "hay normas vigiladas sin forma de cita que sí llevan número: eso es un título mal "
        "escrito, no una limitación de rango"
    )


class TestElVerboDentroDeUnTituloAjeno:
    """«…por la que se modifica X» es el NOMBRE de otra norma, no una cláusula de este documento.

    El título oficial de la LOMLOE es literalmente «Ley Orgánica 3/2020, de 29 de diciembre, por
    la que se modifica la Ley Orgánica 2/2006, de 3 de mayo, de Educación». Toda norma educativa
    española la cita por su nombre completo, así que **todas parecían modificar la LOE** en cuanto
    la LOE entró en la watchlist (ADR 0030).

    Medido el 2026-08-30 sobre las 912 normas de la cola: **de 143 referencias modificativas a
    normas vigiladas se pasó a 62**. Ochenta y una eran esto, y 2 de ellas apuntaban a las leyes
    madrileñas, que son el caso insignia del proyecto.

    Es el error del ADR 0023 un paso más atrás: allí el verbo estaba suelto en el documento y no
    pegado a la norma; aquí está pegado, pero pertenece al nombre de otra.
    """

    TITULO_PROPIO = (
        "Orden SND/454/2025, de 9 de mayo, por la que se modifican los anexos I, II, III y VI "
        "del Real Decreto 1030/2006, de 15 de septiembre"
    )

    def test_el_verbo_del_nombre_de_otra_norma_no_cuenta(self) -> None:
        texto = (
            "El currículo derivado de la Ley Orgánica 3/2020, de 29 de diciembre, por la que se "
            "modifica la Ley Orgánica 2/2006, de 3 de mayo, de Educación, privilegia estos ámbitos."
        )

        verbos = _referencias(texto)

        assert verbos.get("BOE-A-2006-7899") == "CITA"

    def test_una_clausula_de_verdad_sigue_contando(self) -> None:
        """Lo que se quita es la construcción del nombre, no el verbo."""
        texto = "Se modifica el artículo 5 de la Ley Orgánica 2/2006, de 3 de mayo, de Educación."

        assert _referencias(texto).get("BOE-A-2006-7899") == "MODIFICA"

    def test_el_titulo_del_propio_documento_si_declara_lo_que_hace(self) -> None:
        """«Orden SND/454/2025, por la que se modifican los anexos del RD 1030/2006» es real.

        Sin esta salvedad el arreglo se llevaría por delante 12 casos de los 81 medidos, y uno
        toca el RD 1030/2006 —la cartera de servicios del SNS—, que está vigilado.
        """
        # El cuerpo archivado empieza por el título del propio documento, así que la
        # construcción aparece pegada a la cita igual que en una ajena. Lo que las separa es de
        # quién es el título.
        texto = (
            "Orden SND/454/2025, de 9 de mayo, por la que se modifican los anexos I, II, III y "
            "VI del Real Decreto 1030/2006, de 15 de septiembre, por el que se establece la "
            "cartera de servicios comunes del Sistema Nacional de Salud."
        )

        referencias = extraer_referencias_citadas(texto, LISTA, self.TITULO_PROPIO)

        assert {r.identificador: r.verbo for r in referencias} == {"BOE-A-2006-16212": "MODIFICA"}

    def test_el_mismo_texto_sin_su_titulo_no_cuenta(self) -> None:
        """La prueba de que lo que decide es de quién es el título, no la construcción."""
        texto = (
            "Orden SND/454/2025, de 9 de mayo, por la que se modifican los anexos I, II, III y "
            "VI del Real Decreto 1030/2006, de 15 de septiembre."
        )

        referencias = extraer_referencias_citadas(texto, LISTA, "Orden de otra cosa distinta")

        assert all(r.verbo == "CITA" for r in referencias)

    def test_el_titulo_propio_no_vale_para_una_norma_que_no_nombra(self) -> None:
        """El ruido exacto que motivó el arreglo, y el que más costó ver.

        «Orden EFD/998/2025, por la que se modifica la Orden EDU/2739/2009» lleva la construcción
        en su propio título — pero lo que modifica es esa orden, no la LOE, que solo aparece más
        abajo dentro del nombre de la LOMLOE.
        """
        titulo = (
            "Orden EFD/998/2025, de 6 de septiembre, por la que se modifica la Orden EDU/2739/2009"
        )
        texto = (
            "adaptación a los cambios derivados de la Ley Orgánica 3/2020, de 29 de diciembre, "
            "por la que se modifica la Ley Orgánica 2/2006, de 3 de mayo, de Educación."
        )

        referencias = extraer_referencias_citadas(texto, LISTA, titulo)

        assert all(r.verbo == "CITA" for r in referencias)

    def test_sin_titulo_la_construccion_se_trata_como_ajena(self) -> None:
        """Vacío es el lado conservador: sin título no se puede afirmar que sea propio."""
        texto = (
            "la Ley Orgánica 3/2020, de 29 de diciembre, por la que se modifica la Ley Orgánica "
            "2/2006, de 3 de mayo, de Educación"
        )

        assert _referencias(texto).get("BOE-A-2006-7899") == "CITA"
