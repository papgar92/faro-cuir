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

    @property
    def es_puntero(self) -> bool:
        """Ni texto anterior ni nuevo: el documento **nombra** este precepto y no lo reproduce.

        Es la forma que tiene una supresión de presentarse («El artículo 24 queda suprimido»),
        y hasta el ADR 0016 se rechazaba la extracción entera por ello. Ahora se conserva, con
        la condición que ese ADR pone y que no es negociable: **un puntero no acciona nada**
        (regla de oro 10). Por sí solo no produce clasificación ninguna; solo el catálogo de
        reglas sobre el texto archivado (`pipeline/reglas.py`) puede producirla, y lo hace
        buscando la supresión en el archivo, no creyéndose esta lista. Un puntero alucinado es
        inerte.

        No es un campo del esquema a propósito: es una lectura de lo que hay, no un dato que el
        modelo pueda emitir. Si fuera campo, el modelo podría marcarlo o desmarcarlo.
        """
        return self.texto_anterior is None and self.texto_nuevo is None


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

    @property
    def punteros(self) -> tuple[ArticuloExtraido, ...]:
        """Artículos citados sin texto por ninguno de los dos lados (ADR 0016).

        Aquí vivía `_articulos_con_algun_texto`, un validador que rechazaba la extracción
        **entera** si aparecía uno de estos. La premisa era «un artículo sin texto no aporta
        nada al diff», y era cierta mientras se esperase encontrar el diff dentro del propio
        documento. Dejó de serlo: una supresión no reproduce lo que borra, lo nombra («El
        artículo 24 queda suprimido»), así que el artículo sin texto es *precisamente* la forma
        en que se presenta el cambio más grave que este proyecto vigila.

        El coste de aquel rechazo, medido sobre `BOE-A-2024-10767` —la reforma madrileña, el
        caso que 7.8 señala como el más importante del corpus—: se perdían también las trece
        modificaciones del mismo documento que sí traían redacción nueva, no quedaba fila en
        `deteccion`, la norma no llegaba nunca al gate humano, y como la ausencia de fila es lo
        que define la cola del extractor, cada pasada volvía a gastar los 133,9 s de LLM sin
        producir nada.

        Se cuenta y se registra (`services/extraccion.py`) por el mismo motivo por el que se
        registra el embudo del prefiltro: lo que no se cuenta no se afina. Que un documento
        traiga muchos punteros es la señal barata de que ahí hay supresiones que mirar.
        """
        return tuple(articulo for articulo in self.articulos if articulo.es_puntero)
