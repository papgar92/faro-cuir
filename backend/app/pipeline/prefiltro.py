"""Etapa 1 del pipeline: prefiltro léxico sobre los títulos del sumario (CLAUDE.md sección 7).

Decide de qué normas merece la pena descargar el texto completo. Va antes que el extractor
porque es lo que evita gastar una llamada al LLM (y una descarga) en las ~250 normas diarias
del BOE que no tienen nada que ver con el objeto del proyecto.

**Ajustado a recall máximo, no a precisión.** La regla del proyecto es explícita: mejor 50
falsos positivos que 1 falso negativo. Un falso positivo cuesta una descarga y una llamada al
extractor; un falso negativo es una norma que recorta un derecho y que el sistema no llegó a
mirar nunca. No son errores comparables, así que el filtro no se equilibra: se sesga.

De ahí tres decisiones:

- **Solo se mira el título** (más el órgano emisor). Es lo único que trae el sumario, y bajar
  al texto completo es justo lo que este filtro decide. Un título del BOE es informativo:
  el legislador está obligado a describir en él lo que la norma hace.
- **No hay lista negra ni exclusiones.** Nada descarta a una norma que ya ha coincidido.
  Cualquier regla de "esto en realidad no cuenta" es una vía para perder verdaderos positivos.
- **Se registra qué término hizo saltar la norma.** Sin eso el filtro es una caja negra y no
  se puede auditar ni afinar: no se sabe qué parte del ruido viene de qué palabra.

El módulo es **puro**: no toca la base de datos ni la red. Persistir el resultado es trabajo
de `services/prefiltro.py`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

# Versión del vocabulario. Se guarda junto a cada resultado para que una norma evaluada con
# un diccionario viejo sea reconocible y se pueda reevaluar. Súbela SIEMPRE que cambien los
# términos: sin eso, "esta norma se descartó" deja de ser una afirmación comprobable.
VERSION_VOCABULARIO = "2026.08.06"


class Categoria(StrEnum):
    """Para qué sirve cada término. No cambia la decisión, sí permite medir el ruido."""

    # Coincidir con uno de estos es señal suficiente por sí sola: son términos que no
    # aparecen en un título del BOE por casualidad.
    DIRECTO = "directo"
    # Términos del dominio donde el retroceso se materializa (sanidad, educación, registro
    # civil) pero que también salen en normas que no van de esto. Se aceptan igual —recall
    # máximo— y se etiquetan aparte para poder medir cuánto ruido aporta cada uno y decidir
    # con datos, no de oídas, si alguno hay que ajustar.
    CONTEXTO = "contexto"


# Términos en minúsculas y sin tildes: la normalización de `_normalizar` se aplica igual al
# texto y al término, así que aquí se escriben ya en esa forma.
#
# Cada entrada cubre una forma de nombrar lo mismo, incluidas las que usa quien redacta para
# no nombrarlo. Se incluyen a propósito las variantes antiguas o clínicas ("disforia de
# genero", "transexualidad") porque una norma que recorta derechos suele usar el vocabulario
# de hace veinte años, no el actual.
_VOCABULARIO: dict[str, Categoria] = {
    # --- Colectivo e identidad ------------------------------------------------------------
    "lgtbi": Categoria.DIRECTO,
    "lgtb": Categoria.DIRECTO,
    "lgtbiq": Categoria.DIRECTO,
    "lgbti": Categoria.DIRECTO,
    "lgbt": Categoria.DIRECTO,
    "homosexual": Categoria.DIRECTO,
    "homosexualidad": Categoria.DIRECTO,
    "bisexual": Categoria.DIRECTO,
    "lesbiana": Categoria.DIRECTO,
    "lesbianas": Categoria.DIRECTO,
    "gais": Categoria.DIRECTO,
    "transexual": Categoria.DIRECTO,
    "transexuales": Categoria.DIRECTO,
    "transexualidad": Categoria.DIRECTO,
    "transgenero": Categoria.DIRECTO,
    "intersexual": Categoria.DIRECTO,
    "intersexualidad": Categoria.DIRECTO,
    "no binario": Categoria.DIRECTO,
    "no binaria": Categoria.DIRECTO,
    "personas trans": Categoria.DIRECTO,
    "poblacion trans": Categoria.DIRECTO,
    "menores trans": Categoria.DIRECTO,
    "queer": Categoria.DIRECTO,
    # --- Identidad y expresión de género ---------------------------------------------------
    "identidad de genero": Categoria.DIRECTO,
    "identidad sexual": Categoria.DIRECTO,
    "expresion de genero": Categoria.DIRECTO,
    "autodeterminacion de genero": Categoria.DIRECTO,
    "libre desarrollo de la personalidad": Categoria.CONTEXTO,
    "disforia de genero": Categoria.DIRECTO,
    "identidad de genero sentida": Categoria.DIRECTO,
    "genero sentido": Categoria.DIRECTO,
    "sexo sentido": Categoria.DIRECTO,
    # --- Orientación ------------------------------------------------------------------------
    "orientacion sexual": Categoria.DIRECTO,
    # Las formas pegadas («afectivosexual») se listan aparte porque la normalización solo
    # colapsa separadores: sin guion ni espacio no hay nada que colapsar, y sin estas
    # entradas se perderían en silencio. Un test lo fija.
    "orientacion afectivo sexual": Categoria.DIRECTO,
    "orientacion afectivosexual": Categoria.DIRECTO,
    "diversidad sexual": Categoria.DIRECTO,
    "diversidad afectivo sexual": Categoria.DIRECTO,
    "diversidad afectivosexual": Categoria.DIRECTO,
    # --- Discriminación y odio ---------------------------------------------------------------
    "lgtbifobia": Categoria.DIRECTO,
    "lgtbfobia": Categoria.DIRECTO,
    "homofobia": Categoria.DIRECTO,
    "transfobia": Categoria.DIRECTO,
    "bifobia": Categoria.DIRECTO,
    "lesbofobia": Categoria.DIRECTO,
    "delitos de odio": Categoria.CONTEXTO,
    "discriminacion por razon de sexo": Categoria.CONTEXTO,
    "igualdad de trato": Categoria.CONTEXTO,
    "no discriminacion": Categoria.CONTEXTO,
    # --- Terapias de conversión --------------------------------------------------------------
    "terapia de conversion": Categoria.DIRECTO,
    "terapias de conversion": Categoria.DIRECTO,
    "terapias de aversion": Categoria.DIRECTO,
    "terapias reparativas": Categoria.DIRECTO,
    # --- Educativo ---------------------------------------------------------------------------
    "coeducacion": Categoria.DIRECTO,
    "coeducativo": Categoria.DIRECTO,
    "diversidad familiar": Categoria.DIRECTO,
    "diversidad familiar y afectiva": Categoria.DIRECTO,
    "educacion afectivo sexual": Categoria.DIRECTO,
    "educacion afectivosexual": Categoria.DIRECTO,
    "educacion sexual": Categoria.CONTEXTO,
    "convivencia escolar": Categoria.CONTEXTO,
    "acoso escolar": Categoria.CONTEXTO,
    "plan de igualdad": Categoria.CONTEXTO,
    # Con ñ: `_normalizar` la preserva, así que el término debe escribirse con ella o no
    # coincidiría nunca. Hay un test que lo fija.
    "protocolo de acompañamiento": Categoria.DIRECTO,
    "acompañamiento a la identidad de genero": Categoria.DIRECTO,
    # --- Sanitario ----------------------------------------------------------------------------
    "cartera de servicios": Categoria.CONTEXTO,
    "cartera comun de servicios": Categoria.CONTEXTO,
    "unidad de identidad de genero": Categoria.DIRECTO,
    "tratamiento hormonal": Categoria.DIRECTO,
    "hormonacion": Categoria.DIRECTO,
    "bloqueadores de la pubertad": Categoria.DIRECTO,
    "cirugia de reasignacion": Categoria.DIRECTO,
    "reasignacion de sexo": Categoria.DIRECTO,
    "reproduccion humana asistida": Categoria.CONTEXTO,
    "reproduccion asistida": Categoria.CONTEXTO,
    # --- Documental / registral ----------------------------------------------------------------
    "rectificacion registral": Categoria.DIRECTO,
    "rectificacion registral del sexo": Categoria.DIRECTO,
    "mencion registral del sexo": Categoria.DIRECTO,
    "mencion del sexo": Categoria.DIRECTO,
    "cambio de nombre": Categoria.CONTEXTO,
    "registro civil": Categoria.CONTEXTO,
    "filiacion": Categoria.CONTEXTO,
    "familias homoparentales": Categoria.DIRECTO,
    "homoparental": Categoria.DIRECTO,
    # --- Deportivo ------------------------------------------------------------------------------
    "categoria femenina": Categoria.CONTEXTO,
    "competicion femenina": Categoria.CONTEXTO,
}


def _normalizar(texto: str) -> str:
    """Baja a minúsculas, quita tildes y colapsa cualquier cosa que no sea letra o dígito.

    Lo tercero es lo que importa: en el BOE la misma idea aparece como «afectivo-sexual»,
    «afectivo sexual» y «afectivosexual», y con comillas angulares en medio. Al convertir
    todo separador en un espacio único, un solo término del vocabulario cubre las variantes
    en vez de tener que enumerarlas.

    La ñ se preserva: quitarle la tilde a `acompañamiento` lo convertiría en `acompanamiento`
    y ese es justamente el término que se escribe en el diccionario, así que ambos lados
    acaban en la misma forma.
    """
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    sin_tildes = "".join(
        caracter
        for caracter in descompuesto
        # Se conserva la tilde de la ñ (U+0303) para no fusionar `ano`/`año`; el resto de
        # marcas diacríticas se descartan.
        if unicodedata.category(caracter) != "Mn" or caracter == "̃"
    )
    recompuesto = unicodedata.normalize("NFC", sin_tildes)
    return " ".join(re.sub(r"[^0-9a-zñ]+", " ", recompuesto).split())


# El vocabulario ya se escribe normalizado, pero se vuelve a pasar por `_normalizar` para que
# un término mal escrito (con tilde, con guion) no deje de coincidir nunca en silencio.
_VOCABULARIO_NORMALIZADO: dict[str, tuple[str, Categoria]] = {
    _normalizar(termino): (termino, categoria) for termino, categoria in _VOCABULARIO.items()
}


class EstadoPrefiltro(StrEnum):
    """Resultado del prefiltro sobre una norma."""

    PENDIENTE = "pendiente"
    RELEVANTE = "relevante"
    DESCARTADA = "descartada"


@dataclass(frozen=True)
class ResultadoPrefiltro:
    estado: EstadoPrefiltro
    # Términos del vocabulario que han coincidido, en el orden en que se escriben en el
    # diccionario. Vacío si se descarta.
    terminos: tuple[str, ...]
    version: str

    @property
    def relevante(self) -> bool:
        return self.estado is EstadoPrefiltro.RELEVANTE

    @property
    def solo_por_contexto(self) -> bool:
        """True si pasó únicamente por términos genéricos.

        Es la métrica que dice cuánto ruido está metiendo la lista de contexto, y por tanto
        qué se puede afinar sin tocar el recall de los términos directos.
        """
        return self.relevante and all(
            _VOCABULARIO_NORMALIZADO[_normalizar(t)][1] is Categoria.CONTEXTO for t in self.terminos
        )


def _contiene(texto_normalizado: str, termino_normalizado: str) -> bool:
    """Busca el término respetando límites de palabra.

    Sin esto, `lgtb` coincidiría dentro de cualquier palabra que lo contuviera y `trans`
    dispararía con «transporte», «transitoria» o «transparencia», que en el BOE salen cada
    día. Como el texto ya está normalizado a palabras separadas por un espacio, basta con
    exigir espacio (o extremo) a cada lado.
    """
    patron = rf"(?:^| ){re.escape(termino_normalizado)}(?:$| )"
    return re.search(patron, texto_normalizado) is not None


def evaluar(titulo: str, *, organo_emisor: str | None = None) -> ResultadoPrefiltro:
    """Aplica el prefiltro al título de una norma.

    El órgano emisor entra en el texto examinado porque a veces es donde está la señal: una
    resolución de la «Dirección General de Igualdad y Diversidad» puede tener un título
    puramente administrativo. Añadirlo solo puede subir el recall, que es lo que se busca.
    """
    texto = _normalizar(f"{titulo} {organo_emisor or ''}")

    coincidencias = tuple(
        original
        for normalizado, (original, _) in _VOCABULARIO_NORMALIZADO.items()
        if _contiene(texto, normalizado)
    )

    if not coincidencias:
        return ResultadoPrefiltro(EstadoPrefiltro.DESCARTADA, (), VERSION_VOCABULARIO)

    return ResultadoPrefiltro(EstadoPrefiltro.RELEVANTE, coincidencias, VERSION_VOCABULARIO)
