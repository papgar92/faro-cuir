"""Tests del anclaje de la extracción al texto archivado. Regla de oro 9, 7.5, ADR 0013.

Lo que se prueba aquí es un control, no una utilidad: si esto se rompe, el sistema vuelve a
publicar afirmaciones de un modelo que nadie puede contrastar contra el archivo.
"""

from __future__ import annotations

from app.pipeline.anclaje import anclar

# Un trozo del artículo 4 real de la Ley 2/2016 de Madrid, con los espacios tal y como salen del
# XML: saltos de línea y dobles espacios incluidos. Es el caso que hay que tolerar.
TEXTO = (
    "Artículo 4.  Reconocimiento del\nderecho a la identidad de género "
    "libremente manifestada. 1. Toda persona tiene derecho a construir para sí una "
    "autodefinición con respecto a su cuerpo."
)


class TestCitaLocalizada:
    def test_una_cita_literal_se_ancla_donde_esta(self) -> None:
        ancla = anclar(TEXTO, "Toda persona tiene derecho")

        assert ancla is not None
        assert ancla.verifica(TEXTO)
        assert TEXTO[ancla.inicio : ancla.fin] == "Toda persona tiene derecho"

    def test_tolera_que_el_modelo_normalice_los_espacios(self) -> None:
        """El modelo reproduce la cita con un espacio donde el archivo tiene un salto de línea.

        Exigir igualdad byte a byte descartaría una cita correcta, y ese falso negativo lo
        habría introducido el propio control.
        """
        ancla = anclar(TEXTO, "Reconocimiento del derecho a la identidad de género")

        assert ancla is not None
        # Lo que se guarda es el recorte del ARCHIVO, con sus espacios originales, no la cadena
        # que devolvió el modelo.
        assert ancla.fragmento == "Reconocimiento del\nderecho a la identidad de género"
        assert ancla.verifica(TEXTO)

    def test_el_fragmento_guardado_sale_del_archivo_y_no_del_modelo(self) -> None:
        ancla = anclar(TEXTO, "Artículo 4. Reconocimiento")

        assert ancla is not None
        assert ancla.fragmento == TEXTO[ancla.inicio : ancla.fin]
        assert "  " in ancla.fragmento  # el doble espacio del original, conservado


class TestAlucinacion:
    def test_lo_que_no_esta_en_el_documento_no_se_ancla(self) -> None:
        """Este `None` es lo que hace que una alucinación se detecte sola."""
        assert anclar(TEXTO, "El Gobierno suprime la prestación sanitaria") is None

    def test_una_parafrasis_tampoco_cuela(self) -> None:
        """Colapsar espacios es la única licencia; cambiar palabras no lo es."""
        assert anclar(TEXTO, "Toda persona tendrá derecho a construir") is None

    def test_cadena_vacia_no_ancla_en_cualquier_sitio(self) -> None:
        """`"".find()` devuelve 0, así que sin este caso una cita vacía "encajaría" siempre."""
        assert anclar(TEXTO, "") is None
        assert anclar(TEXTO, "   ") is None


class TestVentana:
    def test_el_desplazamiento_lleva_los_offsets_al_documento_entero(self) -> None:
        """El error fácil de esta etapa, y por eso tiene test propio (7.5).

        Al modelo se le manda una ventana del documento (hoy los primeros 4.000 caracteres,
        6.9.7). Si los offsets se guardaran relativos a la ventana, apuntarían a otro párrafo
        del archivo en cuanto la ventana no empiece en cero — y una alerta que señala al sitio
        equivocado es peor que una que no señala.
        """
        documento = "Preámbulo larguísimo. " * 200
        ventana_inicio = len(documento)
        completo = documento + TEXTO

        ancla = anclar(TEXTO, "Toda persona tiene derecho", desplazamiento=ventana_inicio)

        assert ancla is not None
        # La comprobación que importa: el rango recorta lo mismo sobre el DOCUMENTO ENTERO.
        assert completo[ancla.inicio : ancla.fin] == "Toda persona tiene derecho"
        assert ancla.verifica(completo)
