"""Tests del catálogo de reglas del clasificador (etapa 4, ADR 0016, CLAUDE.md 7.6).

Módulo puro: ni base de datos ni red ni LLM, así que aquí se prueba lo único que importa de
él — qué detecta, qué **no** detecta, y que sus offsets apuntan a lo que dicen apuntar.

La mayor parte de estos tests corre sobre texto **real** del BOE
(`fixtures/boe_a_2024_10767_recortado.xml`), no sobre frases inventadas para que pasen. Es
deliberado: un catálogo de patrones sobre lenguaje jurídico probado solo contra los ejemplos
que uno mismo escribe demuestra que el autor sabe escribir sus propios patrones.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models.deteccion import Clasificacion
from app.pipeline import reglas
from app.pipeline.referencias import ReferenciaAnterior, extraer_referencias_anteriores
from app.pipeline.texto import texto_plano
from app.pipeline.watchlist import NormaVigilada, Watchlist
from app.security import xml_safe

FIXTURE = Path(__file__).parent / "fixtures" / "boe_a_2024_10767_recortado.xml"

# La misma norma que trae `config/watchlist.json` (Ley 2/2016 de Madrid). Se declara aquí en
# vez de cargar la watchlist real para que estos tests no fallen el día que alguien reordene
# el fichero de configuración: lo que se prueba es la regla, no el contenido de la lista.
LEY_2_2016 = Watchlist(
    version="test",
    normas=(
        NormaVigilada(
            identificador="BOE-A-2016-6728",
            titulo="Ley 2/2016 de Identidad y Expresión de Género (Madrid)",
            nota="fixture",
            ambito="MD",
        ),
    ),
)
VACIA = Watchlist(
    version="test",
    normas=(NormaVigilada(identificador="BOE-A-9999-1", titulo="otra", nota="fixture"),),
)


@pytest.fixture(scope="module")
def documento_real() -> tuple[str, tuple[ReferenciaAnterior, ...]]:
    raiz = xml_safe.parse(FIXTURE.read_bytes())
    return texto_plano(raiz), extraer_referencias_anteriores(raiz)


class TestDeteccionDeSupresiones:
    def test_encuentra_las_doce_supresiones_del_documento_real(
        self, documento_real: tuple[str, tuple[ReferenciaAnterior, ...]]
    ) -> None:
        """Verificación 2 del ADR 0016, sobre el texto tal y como lo publicó el BOE.

        Doce y no diez: el sondeo a mano con el que se escribió el ADR se dejó dos. Que el
        número esté fijado aquí es lo que hace que bajarlo sea un test en rojo y no un silencio.
        """
        texto, _ = documento_real
        encontradas = reglas.supresiones(texto)

        assert len(encontradas) == 12

    def test_cada_span_recortado_del_texto_es_literalmente_lo_que_dice(
        self, documento_real: tuple[str, tuple[ReferenciaAnterior, ...]]
    ) -> None:
        """El control de 7.5 aplicado a nuestra propia salida, no solo a la del modelo.

        Unos offsets desplazados producirían una alerta que señala al párrafo equivocado del
        archivo, y eso es peor que no señalar nada: el revisor leería otra cosa y la daría por
        comprobada.
        """
        texto, _ = documento_real

        for prueba in reglas.supresiones(texto):
            assert prueba.verifica(texto)
            assert "suprim" in prueba.fragmento.lower()

    def test_no_confunde_el_infinitivo_de_una_redaccion_nueva_con_una_supresion(
        self, documento_real: tuple[str, tuple[ReferenciaAnterior, ...]]
    ) -> None:
        """«…presionada para ocultar, suprimir o negar su condición sexual» no suprime nada.

        Es texto **nuevo** del artículo 4, dentro de la propia reforma. Buscar el lema
        `suprim*` lo marcaría; buscar la construcción operativa no. Este es el caso que separa
        una cosa de la otra, y viene del documento real.
        """
        texto, _ = documento_real
        fragmentos = [prueba.fragmento for prueba in reglas.supresiones(texto)]

        assert not any("presionada para ocultar" in fragmento for fragmento in fragmentos)

    @pytest.mark.parametrize(
        "frase",
        [
            "Los apartados 1 y 8 del artículo 1 quedan suprimidos.",
            "Se suprime el artículo 7.",
            "Queda suprimido el apartado 2 del artículo 9.",
            "El artículo 24 queda suprimido.",
            "El Título X queda suprimido.",
        ],
    )
    def test_los_cinco_ordenes_sintacticos_del_documento_real(self, frase: str) -> None:
        """Cinco formas de decir lo mismo en un solo documento. El ADR las lista una a una."""
        assert len(reglas.supresiones(frase)) == 1

    def test_una_supresion_sin_precepto_no_cuenta(self) -> None:
        """«Se suprime la referencia a…» no dice qué precepto deja de existir.

        Sin la exigencia de una referencia a precepto en la misma cláusula, cualquier frase del
        preámbulo que hable de suprimir algo entraría en la cola de revisión.
        """
        assert reglas.supresiones("Se suprime la mención al organismo competente.") == ()

    def test_una_clausula_con_dos_construcciones_emite_una_sola_evidencia(self) -> None:
        """«Se suprime el Título XIV y se sustituye el Título XIII…», del documento real."""
        frase = "Veinticuatro. Se suprime el Título XIV y se suprime el Título XV."
        assert len(reglas.supresiones(frase)) == 1


class TestTopesDeTamano:
    def test_una_clausula_desmesurada_se_recorta_y_sigue_verificando(self) -> None:
        """El texto archivado es dato no confiable: no puede producir filas de tamaño libre."""
        relleno = "palabra " * 400
        texto = f"{relleno}se suprime el artículo 3 {relleno}"

        encontradas = reglas.supresiones(texto)

        assert len(encontradas) == 1
        assert len(encontradas[0].fragmento) <= reglas.MAX_CARACTERES_EVIDENCIA
        assert encontradas[0].verifica(texto)

    def test_al_recortar_se_exige_que_el_precepto_siga_dentro(self) -> None:
        """Si la referencia al precepto queda fuera de la ventana, la evidencia no vale.

        Es la decisión conservadora correcta: el span es lo que un revisor va a leer, y uno que
        diga «se suprime» sin decir qué no sostiene ningún veredicto.
        """
        lejos = "palabra " * 200
        texto = f"El artículo 3 de la ley {lejos} se suprime {lejos} y nada más."

        assert reglas.supresiones(texto) == ()


class TestVeredictos:
    def test_supresion_sobre_norma_vigilada_es_retroceso(
        self, documento_real: tuple[str, tuple[ReferenciaAnterior, ...]]
    ) -> None:
        texto, referencias = documento_real

        veredicto = reglas.clasificar(texto, referencias=referencias, lista=LEY_2_2016)

        assert veredicto is not None
        assert veredicto.regla == reglas.R_SUP_NORMA_VIGILADA
        assert veredicto.clasificacion is Clasificacion.RETROCESO
        assert veredicto.normas_vigiladas == ("BOE-A-2016-6728",)
        assert len(veredicto.evidencia) == 12
        assert veredicto.version_reglas == reglas.VERSION_REGLAS

    def test_sin_norma_vigilada_no_afirma_nada_pero_tampoco_calla(
        self, documento_real: tuple[str, tuple[ReferenciaAnterior, ...]]
    ) -> None:
        """Umbral de recall alto de 7.6: entra en la cola de revisión sin emitir un juicio."""
        texto, referencias = documento_real

        veredicto = reglas.clasificar(texto, referencias=referencias, lista=VACIA)

        assert veredicto is not None
        assert veredicto.regla == reglas.R_SUP_SIN_NORMA_VIGILADA
        assert veredicto.clasificacion is Clasificacion.INDETERMINADO
        assert veredicto.normas_vigiladas == ()

    def test_una_cita_no_es_una_modificacion(
        self, documento_real: tuple[str, tuple[ReferenciaAnterior, ...]]
    ) -> None:
        """El verbo del `<analisis>` decide. Citar la Ley 2/2016 no es tocarla."""
        texto, _ = documento_real
        cita = (ReferenciaAnterior(identificador="BOE-A-2016-6728", verbo="CITA", texto=""),)

        veredicto = reglas.clasificar(texto, referencias=cita, lista=LEY_2_2016)

        assert veredicto is not None
        assert veredicto.regla == reglas.R_SUP_SIN_NORMA_VIGILADA

    def test_sin_supresiones_no_hay_veredicto(self) -> None:
        """`None` es "este catálogo no tiene nada que decir", no "es neutro".

        Hoy solo sabe de supresiones; devolver `neutro` sería inventar una conclusión que nadie
        ha sacado (regla de oro 8).
        """
        texto = "El artículo 4 queda redactado como sigue: «Nueva redacción del precepto.»"

        assert reglas.clasificar(texto, lista=LEY_2_2016) is None


class TestPunterosInertes:
    """Verificación 3 del ADR 0016: un puntero no corroborado no produce clasificación."""

    def test_un_puntero_solo_no_produce_ningun_veredicto(self) -> None:
        """El modelo dice que el documento suprime el artículo 24; el archivo no lo dice.

        Es el caso de la alucinación, y la respuesta correcta es no clasificar nada. Las reglas
        leen el texto archivado, no la lista del modelo (regla de oro 10).
        """
        texto = "El artículo 24 queda redactado como sigue: «Nueva redacción.»"

        veredicto = reglas.clasificar(texto, lista=LEY_2_2016, punteros=("art. 24",))

        assert veredicto is None

    def test_los_punteros_se_reparten_en_corroborados_y_no(
        self, documento_real: tuple[str, tuple[ReferenciaAnterior, ...]]
    ) -> None:
        """Diagnóstico, no evidencia: se cuenta para poder medir, no para decidir."""
        texto, referencias = documento_real

        veredicto = reglas.clasificar(
            texto,
            referencias=referencias,
            lista=LEY_2_2016,
            punteros=("art. 24", "art. 999"),
        )

        assert veredicto is not None
        assert veredicto.punteros_corroborados == ("art. 24",)
        assert veredicto.punteros_sin_corroborar == ("art. 999",)

    def test_un_puntero_sin_corroborar_no_cambia_el_veredicto(
        self, documento_real: tuple[str, tuple[ReferenciaAnterior, ...]]
    ) -> None:
        texto, referencias = documento_real

        con_ruido = reglas.clasificar(
            texto, referencias=referencias, lista=LEY_2_2016, punteros=("art. 999",)
        )
        sin_ruido = reglas.clasificar(texto, referencias=referencias, lista=LEY_2_2016)

        assert con_ruido is not None and sin_ruido is not None
        assert con_ruido.clasificacion is sin_ruido.clasificacion
        assert con_ruido.evidencia == sin_ruido.evidencia


def test_el_catalogo_no_lee_ningun_campo_de_juicio_del_modelo() -> None:
    """7.6: ninguna regla puede depender de un campo que venga del juicio del modelo.

    `clasificar` recibe texto archivado, referencias del `<analisis>` oficial, la watchlist
    versionada del repo, los diffs archivados desde el consolidado (ADR 0018) y —solo para
    diagnóstico— los identificadores de los punteros. Si algún día aparece aquí un parámetro que
    venga de la extracción, este test es el que tiene que fallar, porque significaría que el
    veredicto ha dejado de ser reconstruible sin el modelo.

    **`diffs` entró en la lista con el ADR 0018 y no la debilita**: son dos textos archivados
    con su `sha256`, sacados de la propia fuente, no una opinión de nadie. La comprobación que
    de verdad sostiene esto es la de abajo — que el veredicto no cambie con los diffs presentes
    o ausentes.
    """
    import inspect

    parametros = set(inspect.signature(reglas.clasificar).parameters)

    assert parametros == {"texto", "referencias", "lista", "punteros", "diffs"}


class TestDocumentoRealCompleto:
    """Verificación 2 del ADR 0016 contra el cuerpo **entero**, no contra el recorte.

    Se salta cuando no hay almacén: `backend/data/` está en .gitignore, así que en CI no
    existe. Que se salte con el motivo escrito es preferible a no tenerlo — el recorte prueba
    los patrones, pero solo el documento entero prueba que no aparecen falsos positivos en los
    44.526 caracteres que el recorte deja fuera.
    """

    RUTA = Path("data/5e/42/5e420c30ba9913f578dd394a63d7be1a56a08c50dfc458cae922b0521df24317.xml")

    def test_el_cuerpo_archivado_da_las_mismas_doce(self) -> None:
        if not self.RUTA.exists():
            pytest.skip(
                f"No está el cuerpo archivado en {self.RUTA} (backend/data/ está en "
                ".gitignore). Para tenerlo: docker compose exec worker python -m worker.run "
                "--fuente boe --fecha 2024-05-29"
            )
        texto = texto_plano(xml_safe.parse(self.RUTA.read_bytes()))

        encontradas = reglas.supresiones(texto)

        assert len(encontradas) == 12
        assert all(prueba.verifica(texto) for prueba in encontradas)


# --- Familia de derogación (R-DER-001) ---------------------------------------------------

FIXTURE_DEROGACION = Path(__file__).parent / "fixtures" / "boe_a_2023_5366_recortado.xml"

# La Ley 3/2007, que `config/watchlist.json` vigila y que la Ley 4/2023 deroga. Declarada aquí
# por lo mismo que `LEY_2_2016`: lo que se prueba es la regla, no el contenido de la lista.
LEY_3_2007 = Watchlist(
    version="test",
    normas=(
        NormaVigilada(
            identificador="BOE-A-2007-5585",
            titulo="Ley 3/2007 reguladora de la rectificación registral de la mención al sexo",
            nota="fixture",
            ambito="estatal",
        ),
    ),
)


@pytest.fixture(scope="module")
def derogacion_real() -> tuple[str, tuple[ReferenciaAnterior, ...]]:
    raiz = xml_safe.parse(FIXTURE_DEROGACION.read_bytes())
    return texto_plano(raiz), extraer_referencias_anteriores(raiz)


class TestDeteccionDeDerogaciones:
    def test_encuentra_la_clausula_operativa_y_solo_esa(
        self, derogacion_real: tuple[str, tuple[ReferenciaAnterior, ...]]
    ) -> None:
        """Una sola evidencia sobre un documento que menciona la derogación cuatro veces.

        Las otras tres —el párrafo del preámbulo y los dos encabezados «Disposición derogatoria
        única. Derogación normativa.»— dicen la verdad y no derogan nada. Es la misma distinción
        que separa «se suprime» del infinitivo «suprimir» en la familia de supresión.
        """
        texto, _ = derogacion_real

        encontradas = reglas.derogaciones(texto)

        assert len(encontradas) == 1
        assert "Queda derogada la Ley" in encontradas[0].fragmento
        assert encontradas[0].verifica(texto)

    def test_el_espacio_duro_del_boe_no_rompe_el_patron(self) -> None:
        """El BOE publica «Ley 3/2007» con U+00A0, no con un espacio normal.

        Se prueba con la cláusula construida aquí y con el espacio duro explícito, en vez de
        inspeccionando el fixture: así el test sigue diciendo la verdad aunque alguien
        reescriba el fichero, y falla por lo que tiene que fallar —el patrón— y no por cómo se
        codificó un carácter. Es la clase de detalle que funciona en el ejemplo escrito a mano
        y falla contra el documento real.
        """
        clausula = (
            "Queda derogada la Ley\xa03/2007, de\xa015 de marzo, reguladora de la "
            "rectificación registral de la mención relativa al sexo de las personas."
        )

        assert len(reglas.derogaciones(clausula)) == 1

    def test_la_clausula_de_arrastre_no_es_evidencia(self) -> None:
        """El falso positivo que separa nombrar una norma de decir «ley».

        «Quedan derogadas cuantas disposiciones de igual o inferior rango se opongan…» aparece
        al final de casi toda norma reglamentaria —3 de las 8 cláusulas del corpus de tres días
        eran esto— y no dice qué norma cae, así que un revisor no puede verificarla contra el
        archivo. La primera versión de esta regla la aceptaba por traer la palabra «ley».
        """
        arrastre = (
            "Quedan derogadas cuantas disposiciones de igual o inferior rango se opongan a lo "
            "establecido en la presente ley."
        )

        assert reglas.derogaciones(arrastre) == ()

    def test_una_cita_de_derogacion_ajena_no_es_evidencia(self) -> None:
        """Ruido real del preámbulo: el título de un reglamento europeo que derogó otra cosa.

        `se deroga` sin «expresamente» queda fuera del patrón justamente por esto.
        """
        cita = (
            "…relativo a la protección de las personas físicas en lo que respecta al "
            "tratamiento de datos personales y por el que se deroga la Directiva 95/46/CE."
        )

        assert reglas.derogaciones(cita) == ()

    def test_la_derogacion_de_un_precepto_concreto_si_cuenta(self) -> None:
        """Verbatim de BOE-A-2023-5370. Nombra la norma con su número, luego es verificable."""
        clausula = (
            "Quedan derogados los artículos 97 y 98 Real Decreto 905/2022, de 25 de octubre, "
            "por el que se regula la Intervención Sectorial Vitivinícola."
        )

        assert len(reglas.derogaciones(clausula)) == 1


class TestVeredictoDeDerogacion:
    def test_derogar_una_norma_vigilada_no_afirma_un_retroceso(
        self, derogacion_real: tuple[str, tuple[ReferenciaAnterior, ...]]
    ) -> None:
        """**El test que impide la extensión ingenua de R-SUP-001.**

        La Ley 4/2023 deroga la Ley 3/2007, que está vigilada, y es un **avance**: la sustituye
        ampliando protección. Una regla «deroga norma vigilada → retroceso» clasificaría al
        revés el caso que este proyecto usa para explicar por qué existe. El signo de una
        derogación depende de qué ocupa el lugar de la norma derogada, y eso es el diff contra
        `version_norma`, que está vacía.
        """
        texto, referencias = derogacion_real

        veredicto = reglas.clasificar(texto, referencias=referencias, lista=LEY_3_2007)

        assert veredicto is not None
        assert veredicto.regla == reglas.R_DER_NORMA_VIGILADA
        assert veredicto.clasificacion is Clasificacion.INDETERMINADO
        assert veredicto.clasificacion is not Clasificacion.RETROCESO
        assert veredicto.normas_vigiladas == ("BOE-A-2007-5585",)
        assert veredicto.severidad == 4
        assert len(veredicto.evidencia) == 1
        assert all(prueba.verifica(texto) for prueba in veredicto.evidencia)

    def test_derogar_una_norma_que_no_se_vigila_no_produce_veredicto(
        self, derogacion_real: tuple[str, tuple[ReferenciaAnterior, ...]]
    ) -> None:
        """Sin norma vigilada no hay nada que decir: no existe un R-DER-002 a propósito.

        Derogar una norma ajena al ámbito es el 90 % de las derogaciones del boletín y no dice
        nada del colectivo. Un equivalente de R-SUP-002 aquí inundaría la cola de revisión, que
        es justo lo que el prefiltro existe para evitar.
        """
        texto, referencias = derogacion_real

        assert reglas.clasificar(texto, referencias=referencias, lista=VACIA) is None

    def test_modificar_no_es_derogar(
        self, derogacion_real: tuple[str, tuple[ReferenciaAnterior, ...]]
    ) -> None:
        """R-DER-001 exige el verbo `DEROGA`, no cualquier verbo modificativo.

        Sin esta distinción la regla dispararía sobre cualquier retoque de una norma vigilada y
        su severidad 4 —«desaparece una norma entera»— dejaría de significar nada.
        """
        texto, _ = derogacion_real
        modifica = (
            ReferenciaAnterior(identificador="BOE-A-2007-5585", verbo="MODIFICA", texto=""),
        )

        assert reglas.clasificar(texto, referencias=modifica, lista=LEY_3_2007) is None


class TestDerogacionEnElDocumentoRealCompleto:
    """Contra el cuerpo entero de la Ley 4/2023, no contra el recorte.

    Se salta cuando no hay almacén, con el mismo criterio que `TestDocumentoRealCompleto`: el
    recorte prueba los patrones, pero solo el documento entero prueba que no aparecen falsos
    positivos en los 137.000 caracteres que el recorte deja fuera.
    """

    RUTA = Path("data/da/d3/dad330d3c8cd8f152775ab9cfe5ca2254dc11fde6e02b7b2df4601435f97d87a.xml")

    def test_el_cuerpo_archivado_da_una_sola_derogacion(self) -> None:
        if not self.RUTA.exists():
            pytest.skip(
                f"No está el cuerpo archivado en {self.RUTA} (backend/data/ está en "
                ".gitignore). Para tenerlo: docker compose exec worker python -m worker.run "
                "--fuente boe --fecha 2023-03-01"
            )
        texto = texto_plano(xml_safe.parse(self.RUTA.read_bytes()))

        encontradas = reglas.derogaciones(texto)

        assert len(encontradas) == 1
        assert "Queda derogada la Ley" in encontradas[0].fragmento
        assert all(prueba.verifica(texto) for prueba in encontradas)


# --- Tercera familia: modificación (R-MOD-001, ADR 0018) -----------------------------------

DIFF_ARTICULO_4 = reglas.Diff(
    norma_afectada="BOE-A-2016-6728",
    bloque="a4",
    articulo="Artículo 4",
    # Las dos redacciones reales, sacadas del consolidado del BOE.
    texto_anterior=(
        "Artículo 4. Reconocimiento del derecho a la identidad de género libremente "
        "manifestada. 1. Toda persona tiene derecho a construir para sí una autodefinición "
        "con respecto a su cuerpo, sexo, género y su orientación sexual."
    ),
    texto_nuevo=(
        "Artículo 4. Reconocimiento del respeto a la libertad y dignidad de las personas "
        "transexuales. 1. Ninguna persona podrá ser presionada para ocultar, suprimir o negar "
        "su condición sexual, ni su transexualidad."
    ),
)


class TestModificacion:
    def test_detecta_la_clausula_de_nueva_redaccion_y_no_la_cita_de_un_titulo(self) -> None:
        """La línea es la misma que separó `queda derogada` de `se deroga` en R-DER-001."""
        operativa = "El artículo 4 queda redactado como sigue: «Artículo 4. Reconocimiento…»"
        cita = (
            "Ley 17/2023, de 27 de diciembre, por la que se modifica la Ley 2/2016, de 29 de "
            "marzo, de Identidad y Expresión de Género."
        )

        assert reglas.modificaciones(operativa)
        assert reglas.modificaciones(cita) == ()

    def test_exige_que_la_clausula_nombre_un_precepto(self) -> None:
        assert reglas.modificaciones("El texto queda redactado como sigue: «cualquier cosa».") == ()

    def test_una_norma_vigilada_reescrita_va_a_revision_sin_signo(self) -> None:
        """Que un artículo se reescriba no dice hacia dónde. Regla de oro 2."""
        texto = "Siete. El artículo 4 queda redactado como sigue: «Artículo 4. Reconocimiento…»"
        referencias = (
            ReferenciaAnterior(
                identificador="BOE-A-2016-6728", verbo="MODIFICA", texto="el art. 4"
            ),
        )

        veredicto = reglas.clasificar(
            texto, referencias=referencias, lista=LEY_2_2016, diffs=(DIFF_ARTICULO_4,)
        )

        assert veredicto is not None
        assert veredicto.regla == reglas.R_MOD_NORMA_VIGILADA
        assert veredicto.clasificacion is Clasificacion.INDETERMINADO
        assert veredicto.normas_vigiladas == ("BOE-A-2016-6728",)
        assert veredicto.preceptos_con_diff == 1
        assert all(prueba.verifica(texto) for prueba in veredicto.evidencia)

    def test_el_diff_no_cambia_el_veredicto_solo_lo_que_se_puede_enseñar(self) -> None:
        """El control que sostiene que `diffs` no debilita 7.6: no decide, ilustra."""
        texto = "Siete. El artículo 4 queda redactado como sigue: «Artículo 4. Reconocimiento…»"
        referencias = (
            ReferenciaAnterior(
                identificador="BOE-A-2016-6728", verbo="MODIFICA", texto="el art. 4"
            ),
        )

        con = reglas.clasificar(
            texto, referencias=referencias, lista=LEY_2_2016, diffs=(DIFF_ARTICULO_4,)
        )
        sin = reglas.clasificar(texto, referencias=referencias, lista=LEY_2_2016)

        assert con is not None and sin is not None
        assert (con.regla, con.clasificacion, con.severidad) == (
            sin.regla,
            sin.clasificacion,
            sin.severidad,
        )
        assert con.evidencia == sin.evidencia
        # Lo único que cambia es el diagnóstico, que es para quien revisa.
        assert con.terminos_perdidos and not sin.terminos_perdidos

    def test_una_reescritura_de_norma_no_vigilada_no_produce_veredicto(self) -> None:
        texto = "El artículo 3 queda redactado como sigue: «Artículo 3. Plazos.»"
        referencias = (
            ReferenciaAnterior(
                identificador="BOE-A-1999-00001", verbo="MODIFICA", texto="el art. 3"
            ),
        )

        assert reglas.clasificar(texto, referencias=referencias, lista=LEY_2_2016) is None

    def test_la_supresion_manda_sobre_la_modificacion(self) -> None:
        """Orden del catálogo: la única regla que afirma signo va primero."""
        texto = (
            "Siete. Se suprime el artículo 7. Ocho. El artículo 8 queda redactado como sigue: «…»"
        )
        referencias = (
            ReferenciaAnterior(identificador="BOE-A-2016-6728", verbo="MODIFICA", texto="arts."),
        )

        veredicto = reglas.clasificar(texto, referencias=referencias, lista=LEY_2_2016)

        assert veredicto is not None and veredicto.regla == reglas.R_SUP_NORMA_VIGILADA


class TestTerminosPerdidos:
    def test_enumera_lo_que_estaba_y_ya_no_esta(self) -> None:
        perdidos = reglas.terminos_perdidos((DIFF_ARTICULO_4,))

        assert "identidad de genero" in [t.lower() for t in perdidos] or "identidad de género" in [
            t.lower() for t in perdidos
        ]

    def test_un_alta_no_pierde_nada(self) -> None:
        """Sin texto anterior no hay comparación posible, y no se inventa una."""
        alta = reglas.Diff(
            norma_afectada="BOE-A-2016-6728",
            bloque="da1",
            articulo="Disposición adicional primera",
            texto_anterior=None,
            texto_nuevo="Las personas trans tendrán derecho a…",
        )

        assert reglas.terminos_perdidos((alta,)) == ()

    def test_no_cuenta_como_perdido_lo_que_sigue_estando(self) -> None:
        igual = reglas.Diff(
            norma_afectada="BOE-A-2016-6728",
            bloque="a1",
            articulo="Artículo 1",
            texto_anterior="Las personas trans tienen derecho a la identidad de género.",
            texto_nuevo="Las personas trans tienen derecho a la identidad de género y a más cosas.",
        )

        assert reglas.terminos_perdidos((igual,)) == ()
