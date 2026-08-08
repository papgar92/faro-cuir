"""Referencias que una norma hace a otras: materia prima del eje 2. CLAUDE.md 7.3.

Módulo **puro**: recibe un árbol XML ya parseado y devuelve datos. No parsea nada por su
cuenta a propósito — todo el XML del proyecto entra por `security/xml_safe.py` (CLAUDE.md 6.1)
y aceptar aquí una cadena abriría una segunda puerta.

Estructura del bloque, **verificada contra el documento real** en la medición del ADR 0011 y
escrita en 7.3 para no volver a descubrirla:

    documento > analisis > referencias > anteriores > anterior[@referencia="BOE-A-2015-11431"]
                                            ├── <palabra codigo="270">MODIFICA</palabra>
                                            └── <texto>el art. 33.4 f) de la Ley de Empleo…</texto>
                                        > posteriores > posterior[@referencia]

Dos cosas que decidieron el diseño de este módulo:

- **Trae el verbo, no solo el identificador.** `MODIFICA`, `DEROGA`, `AÑADE`. Eso permite que
  el eje referencial distinga "esta norma toca la Ley 4/2023" de "esta norma la cita en el
  temario de una oposición", que es exactamente el falso positivo que el eje léxico produce a
  destajo sobre el texto íntegro.
- **`posteriores` no sirve para decidir en el día.** Son las normas que modificaron a esta
  *después*; el día que se ingiere una norma no existen todavía. Se ignoran, y se dice aquí
  para que nadie las añada creyendo que faltaban.

Números medidos sobre 436 normas reales: el 100 % de los documentos traen `<analisis>`, pero
solo 43 (9,9 %) traen referencias anteriores y **13 modifican o derogan algo**. De esas 13, el
eje léxico sobre el título detecta 1. Este eje no duplica al léxico: cubre lo que no ve.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from xml.etree.ElementTree import Element

# Verbos que significan que la norma **toca** a la otra, no que la mencione. Son los que
# publica el propio BOE en `<palabra>`, en mayúsculas y sin tildes en unos casos y con ellas
# en otros, así que la comparación se hace normalizada.
#
# La lista es deliberadamente **corta y explícita**: cualquier verbo desconocido NO cuenta como
# modificación. Es la decisión conservadora en el eje equivocado —podría perderse una forma
# rara— pero el eje léxico sigue cubriendo esas normas y, sobre todo, un verbo desconocido
# tratado como modificación metería en la cola del LLM todas las normas que citan cualquier
# cosa, que son el 10 % del boletín diario.
VERBOS_MODIFICATIVOS = frozenset(
    {
        "MODIFICA",
        "DEROGA",
        "ANADE",
        "SUSTITUYE",
        "SUPRIME",
        "DEJA SIN EFECTO",
        "CORRIGE ERRORES",
    }
)

_ESPACIOS = re.compile(r"\s+")


def _normalizar_verbo(texto: str) -> str:
    """Mayúsculas, sin tildes y con espacios colapsados. `AÑADE` → `ANADE`."""
    sin_tildes = (
        texto.upper()
        .replace("Á", "A")
        .replace("É", "E")
        .replace("Í", "I")
        .replace("Ó", "O")
        .replace("Ú", "U")
        .replace("Ñ", "N")
    )
    return _ESPACIOS.sub(" ", sin_tildes).strip()


@dataclass(frozen=True)
class ReferenciaAnterior:
    """Una norma anterior a la que esta hace referencia."""

    identificador: str
    verbo: str
    # Qué artículos toca, tal como lo redacta el BOE ("el art. 33.4 f) de la Ley de Empleo").
    # Texto libre a propósito: normalizarlo sería inventar una taxonomía de citas.
    texto: str

    @property
    def es_modificativa(self) -> bool:
        return self.verbo in VERBOS_MODIFICATIVOS


def extraer_referencias_anteriores(raiz: Element) -> tuple[ReferenciaAnterior, ...]:
    """Saca las referencias `anteriores` del bloque `<analisis>`.

    Tolerante con la ausencia y estricta con el contenido: un documento sin `<analisis>`
    devuelve una tupla vacía —es el caso normal, no un error— pero una referencia sin
    identificador se descarta en vez de aceptarse con una cadena vacía, que cruzaría con
    cualquier cosa que también la tuviera vacía.
    """
    referencias = []
    # `.//` y no una ruta fija: el bloque cuelga de `documento > analisis` en el XML del BOE,
    # pero este módulo recibe a veces la raíz del documento y a veces el propio `<analisis>`,
    # según quién llame. Anclar la ruta obligaría a que todos los llamantes coincidieran.
    for nodo in raiz.iterfind(".//referencias/anteriores/anterior"):
        identificador = (nodo.get("referencia") or "").strip()
        if not identificador:
            continue
        palabra = nodo.findtext("palabra") or ""
        referencias.append(
            ReferenciaAnterior(
                identificador=identificador,
                verbo=_normalizar_verbo(palabra),
                texto=(nodo.findtext("texto") or "").strip(),
            )
        )
    return tuple(referencias)
