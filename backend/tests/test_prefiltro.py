"""Tests del prefiltro léxico (CLAUDE.md sección 7, etapa 1).

El criterio de estos tests es el del filtro: **recall antes que precisión**. Por eso hay
muchos más casos de "esto TIENE que pasar el filtro" que de "esto tiene que descartarse". Un
falso positivo cuesta una descarga; un falso negativo es una norma que recorta un derecho y
que nadie llega a mirar.
"""

from __future__ import annotations

import pytest

from app.pipeline import prefiltro
from app.pipeline.prefiltro import Categoria, EstadoPrefiltro

# Títulos reales o realistas que el sistema NO se puede permitir perder. La redacción imita
# la del BOE y los boletines autonómicos, incluido el registro administrativo neutro con el
# que se publica un recorte.
TITULOS_QUE_DEBEN_PASAR = [
    # Vocabulario explícito del colectivo.
    "Ley 4/2023, de 28 de febrero, para la igualdad real y efectiva de las personas trans y"
    " para la garantía de los derechos de las personas LGTBI",
    "Decreto por el que se regula el procedimiento de rectificación registral de la mención"
    " relativa al sexo",
    "Orden por la que se modifica el protocolo de acompañamiento al alumnado transexual",
    # Vocabulario clínico y antiguo: quien recorta rara vez usa el término actual.
    "Resolución sobre la atención a menores con disforia de género en el sistema sanitario",
    "Instrucción relativa a los tratamientos de reasignación de sexo",
    # Educativo.
    "Orden por la que se suprime el carácter obligatorio de la formación en coeducación",
    "Decreto sobre el tratamiento de la diversidad familiar en el currículo de primaria",
    # Terapias de conversión.
    "Ley por la que se prohíben las terapias de conversión en el ámbito sanitario",
    # Sanitario: el retroceso silencioso típico, sin nombrar al colectivo en el título.
    "Orden por la que se modifica la cartera de servicios del Servicio Andaluz de Salud",
    # Discriminación.
    "Resolución por la que se aprueba el protocolo frente a la LGTBIfobia en el deporte",
]

# Lo que sí debe descartarse: títulos del BOE real que no tienen nada que ver. Ojo, esta
# lista se mantiene CORTA a propósito. No es una lista negra ni una meta de precisión: solo
# comprueba que el filtro no acepta literalmente todo.
TITULOS_QUE_DEBEN_DESCARTARSE = [
    "Orden HAC/1432/2024, de 11 de diciembre, por la que se aprueba el modelo 190 para la"
    " Declaración del resumen anual de retenciones e ingresos a cuenta del IRPF",
    "Resolución por la que se publica el tipo de interés efectivo anual para el cuarto"
    " trimestre natural del año 2024",
    "Real Decreto por el que se regula la concesión directa de subvenciones para la"
    " transformación digital del transporte de mercancías",
]


@pytest.mark.parametrize("titulo", TITULOS_QUE_DEBEN_PASAR)
def test_no_pierde_normas_relevantes(titulo: str) -> None:
    """Lo que no puede fallar nunca: que una de estas se quede fuera de la cola del LLM.

    Se comprueba `entra_en_la_cola` y no `relevante`. Con el estado `sospecha` (7.2) hay dos
    estados que acaban pasando por el modelo, y exigir `RELEVANTE` a todas convertiría este
    test en una comprobación del **umbral** —que está sin validar y es provisional— en vez de
    una comprobación del **recall**, que es lo que aquí importa y lo que no se puede perder.
    """
    resultado = prefiltro.evaluar(titulo)
    assert resultado.entra_en_la_cola, f"FALSO NEGATIVO, que es el error caro: {titulo!r}"
    assert resultado.terminos, "si pasa el filtro debe decirse por qué"


@pytest.mark.parametrize("titulo", TITULOS_QUE_DEBEN_DESCARTARSE)
def test_sobre_el_titulo_no_se_descarta_nunca(titulo: str) -> None:
    """CLAUDE.md 7.1: **el descarte definitivo solo ocurre tras leer el documento completo.**

    Este test cambió de sentido con el ADR 0011 y el cambio es la parte importante. Antes
    exigía `DESCARTADA` sobre el título; ahora exige justo lo contrario, porque el título es
    exactamente lo que un retroceso silencioso puede redactar de forma anodina: decidir sobre
    él es decidir sobre lo que el redactor controla.

    Que estos títulos no disparen nada sigue siendo correcto y se comprueba (`terminos == ()`).
    Lo que ya no es correcto es cerrarles la puerta sin haber leído el texto.
    """
    resultado = prefiltro.evaluar(titulo)
    assert resultado.estado is EstadoPrefiltro.PENDIENTE
    assert resultado.terminos == ()
    assert not resultado.entra_en_la_cola, "sin señal no debe gastar una llamada al LLM todavía"


@pytest.mark.parametrize("titulo", TITULOS_QUE_DEBEN_DESCARTARSE)
def test_con_el_texto_integro_delante_si_se_descarta(titulo: str) -> None:
    """La otra mitad del contrato: con el documento leído, descartar sí es legítimo.

    Sin este test, el anterior se podría satisfacer con un prefiltro que no descarta nunca
    nada, que es un filtro inútil disfrazado de prudente.
    """
    resultado = prefiltro.evaluar(titulo, texto_integro=titulo)
    assert resultado.estado is EstadoPrefiltro.DESCARTADA
    assert resultado.terminos == ()
    assert resultado.ejes == ()


class TestNormalizacion:
    """La misma idea se escribe de varias formas en el BOE; una sola entrada debe cubrirlas."""

    @pytest.mark.parametrize(
        "variante",
        [
            "educación afectivo-sexual",
            "educacion afectivo sexual",
            "Educación Afectivo-Sexual",
            "EDUCACIÓN AFECTIVOSEXUAL",
            "educación «afectivo-sexual»",
        ],
    )
    def test_variantes_ortograficas_del_mismo_termino(self, variante: str) -> None:
        assert prefiltro.evaluar(f"Orden sobre {variante} en secundaria").relevante

    def test_la_ene_con_virgulilla_se_preserva(self) -> None:
        """Regresión: el término del diccionario lleva ñ y la normalización no la quita.

        Si `_normalizar` empezara a convertir ñ→n, este término dejaría de coincidir en
        silencio y se perderían las normas de acompañamiento escolar, que son justo el
        material del proyecto.
        """
        resultado = prefiltro.evaluar("Instrucción sobre el protocolo de acompañamiento")
        assert resultado.relevante
        assert "protocolo de acompañamiento" in resultado.terminos

    def test_las_tildes_no_impiden_coincidir(self) -> None:
        assert prefiltro.evaluar("Ley sobre la identidad de género").relevante


class TestLimitesDePalabra:
    """Sin límites de palabra el filtro se vuelve inútil por ruido, no por falta de recall."""

    @pytest.mark.parametrize(
        "titulo",
        [
            "Orden sobre el transporte de mercancías peligrosas",
            "Disposición transitoria segunda del reglamento",
            "Ley de transparencia y buen gobierno",
            "Resolución sobre transferencias corrientes entre administraciones",
        ],
    )
    def test_palabras_que_solo_empiezan_igual_no_coinciden(self, titulo: str) -> None:
        assert not prefiltro.evaluar(titulo).relevante

    def test_pero_la_palabra_completa_si(self) -> None:
        assert prefiltro.evaluar("Plan de empleo para personas trans").relevante


class TestOrganoEmisor:
    def test_el_organo_emisor_puede_activar_el_filtro(self) -> None:
        """A veces la señal no está en el título sino en quién firma."""
        titulo = "Resolución por la que se convocan subvenciones para entidades del tercer sector"
        assert not prefiltro.evaluar(titulo).relevante
        assert prefiltro.evaluar(
            titulo, organo_emisor="Dirección General de Diversidad Sexual y Derechos LGTBI"
        ).relevante


class TestAuditabilidad:
    """El filtro tiene que poder explicarse: qué término, con qué vocabulario."""

    def test_devuelve_los_terminos_que_coincidieron(self) -> None:
        resultado = prefiltro.evaluar(
            "Orden sobre identidad de género y orientación sexual en el ámbito educativo"
        )
        assert "identidad de genero" in resultado.terminos
        assert "orientacion sexual" in resultado.terminos

    def test_sella_la_version_del_vocabulario(self) -> None:
        resultado = prefiltro.evaluar("Ley de personas trans")
        assert resultado.version == prefiltro.VERSION_VOCABULARIO

    def test_tambien_sella_la_version_al_descartar(self) -> None:
        """Descartar sin decir con qué diccionario haría imposible reevaluar después."""
        resultado = prefiltro.evaluar("Orden sobre el modelo 190 del IRPF")
        assert resultado.version == prefiltro.VERSION_VOCABULARIO

    def test_distingue_lo_que_pasa_solo_por_terminos_genericos(self) -> None:
        """Los dos entran en la cola; lo que cambia es el puesto.

        Un título que solo dispara términos genéricos es exactamente el caso que 7.2 llama
        `sospecha`: no hay con qué descartarlo, pero tampoco con qué ponerlo primero. **Ni uno
        solo de estos casos se pierde** — que es la garantía que importa.
        """
        solo_contexto = prefiltro.evaluar(
            "Orden por la que se actualiza la cartera de servicios comunes"
        )
        assert solo_contexto.estado is EstadoPrefiltro.SOSPECHA
        assert solo_contexto.entra_en_la_cola, "sospecha NO es descarte: tiene que ir a la cola"
        assert solo_contexto.solo_por_contexto

        directo = prefiltro.evaluar("Orden sobre la identidad de género del alumnado")
        assert directo.estado is EstadoPrefiltro.RELEVANTE
        assert not directo.solo_por_contexto


class TestVocabulario:
    def test_no_hay_terminos_duplicados_al_normalizar(self) -> None:
        """Dos entradas que normalizan igual significan que una es inalcanzable."""
        assert len(prefiltro._VOCABULARIO_NORMALIZADO) == len(prefiltro._VOCABULARIO)

    def test_todo_termino_esta_ya_en_forma_normalizada(self) -> None:
        """Salvo la ñ, el diccionario se escribe como lo deja `_normalizar`.

        Escribir un término con tilde o con guion funcionaría igual (se normaliza), pero
        hace ilegible qué se está buscando de verdad. Este test mantiene el fichero honesto.
        """
        for termino in prefiltro._VOCABULARIO:
            assert termino == prefiltro._normalizar(termino), f"{termino!r} no está normalizado"

    def test_hay_terminos_de_las_dos_categorias(self) -> None:
        categorias = set(prefiltro._VOCABULARIO.values())
        assert categorias == {Categoria.DIRECTO, Categoria.CONTEXTO}
