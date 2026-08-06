"""Contrato de salida del extractor LLM (ADR 0002, CLAUDE.md 6.7 y regla de oro 3).

Este esquema es un **control de seguridad**, no un DTO. Su trabajo es hacer que el modelo no
pueda emitir un veredicto aunque quiera, del mismo modo que la CHECK de `deteccion.origen`
hace que ese veredicto no sea representable en la base de datos (ADR 0004). Aquí la defensa
está una capa antes: si el modelo devuelve "esto es un retroceso", ese campo **no existe** en
el esquema y `extra="forbid"` hace que la respuesta entera se rechace.

Por eso no hay ningún campo de clasificación, severidad, gravedad ni valoración. No es un
olvido y no se añade "por comodidad": añadirlo convertiría este fichero en la puerta por la
que entra justo lo que el proyecto promete que no hace.

La estrategia frente a una respuesta inválida es **descartar, nunca interpretar** (6.7). No se
"arregla" un JSON a medias ni se rellenan huecos con valores por defecto plausibles: una
extracción a medias que parece completa es peor que ninguna, porque nadie vuelve a mirarla.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Topes de tamaño. Un modelo puede devolver texto arbitrariamente largo, por error o porque
# alguien se lo ha pedido desde el contenido del boletín; sin límites, eso acaba en la base de
# datos y en la interfaz. Son generosos para un artículo real y ridículos para un ataque.
MAX_ARTICULOS = 50
MAX_LONGITUD_TEXTO = 20_000
MAX_LONGITUD_CAMPO = 500


class ArticuloExtraido(BaseModel):
    """Un artículo afectado, con su texto antes y después según el documento."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # Texto libre a propósito: cada boletín cita a su manera ("art. 7.2", "disposición
    # adicional segunda") y normalizarlo sería inventar una taxonomía que no existe.
    identificador: str = Field(min_length=1, max_length=MAX_LONGITUD_CAMPO)
    # NULL en un alta (no había texto anterior) y en una derogación (no hay texto nuevo). Qué
    # lado falta es la señal más limpia de qué tipo de cambio es.
    texto_anterior: str | None = Field(default=None, max_length=MAX_LONGITUD_TEXTO)
    texto_nuevo: str | None = Field(default=None, max_length=MAX_LONGITUD_TEXTO)

    @field_validator("texto_anterior", "texto_nuevo")
    @classmethod
    def _vacio_es_nulo(cls, valor: str | None) -> str | None:
        """Cadena vacía y ausencia son lo mismo aquí, y deben guardarse igual.

        Si no, el clasificador vería `""` como "hay texto nuevo, y está vacío" en vez de "no
        hay texto nuevo", y confundiría una derogación con una modificación a nada.
        """
        return valor or None


class ExtraccionNorma(BaseModel):
    """Hechos que el LLM extrae de una norma. **Ningún juicio.**"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # Qué norma se modifica, tal y como la cita el documento. Si el documento no lo dice, se
    # deja a None: deducirlo es inventar (regla de oro 8).
    norma_afectada: str | None = Field(default=None, max_length=MAX_LONGITUD_CAMPO)
    organo_emisor: str | None = Field(default=None, max_length=MAX_LONGITUD_CAMPO)
    # Vocabulario cerrado, el mismo de `AmbitoNorma`. Un valor fuera de la lista rompe la
    # validación y descarta la extracción, en vez de crear un ámbito nuevo sobre la marcha.
    ambito: str | None = Field(default=None, max_length=30)
    articulos: list[ArticuloExtraido] = Field(default_factory=list, max_length=MAX_ARTICULOS)

    # Lo que el modelo NO puede devolver, escrito aquí para que quede constancia de que es
    # deliberado: clasificacion, severidad, confianza, valoracion, recomendacion, resumen
    # interpretativo. `extra="forbid"` los rechaza; este comentario evita que alguien los
    # añada dentro de seis meses pensando que faltaban.

    @field_validator("ambito")
    @classmethod
    def _ambito_del_vocabulario(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        # Import local: el esquema no debe arrastrar el modelo de SQLAlchemy a quien solo
        # quiera validar una respuesta.
        from app.models.norma import AmbitoNorma

        normalizado = valor.strip().lower()
        if normalizado not in {miembro.value for miembro in AmbitoNorma}:
            raise ValueError(f"ámbito fuera del vocabulario: {valor!r}")
        return normalizado

    @field_validator("articulos")
    @classmethod
    def _articulos_con_algun_texto(cls, valor: list[ArticuloExtraido]) -> list[ArticuloExtraido]:
        """Un artículo sin texto por ninguno de los dos lados no aporta nada al diff."""
        for articulo in valor:
            if articulo.texto_anterior is None and articulo.texto_nuevo is None:
                raise ValueError(
                    f"el artículo {articulo.identificador!r} no trae texto anterior ni nuevo"
                )
        return valor
