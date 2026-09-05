"""Del almacén al material sobre el que trabajan las etapas del pipeline.

Una norma con `documento_texto_id` tiene su texto íntegro archivado (ADR 0015). Cuatro etapas lo
necesitan —prefiltro sobre texto íntegro, extractor, catálogo de reglas y versionado— y las
cuatro necesitan exactamente lo mismo: leer del disco, parsear con `xml_safe`, derivar el texto
con la versión vigente de `texto_plano` y reunir **las referencias a otras normas**, que desde el
ADR 0022 vienen de dos sitios: el bloque `<analisis>` del BOE y las citas dentro del propio texto
(`pipeline/citas.py`), que es lo único que hay en las fuentes que no publican ese bloque.

Vivía como `_cuerpo` privado dentro de `services/prefiltro.py`. Se saca aquí al aparecer el
tercer llamante, por el mismo motivo por el que `texto_plano` salió de `services/extraccion.py`
(ADR 0015): **si el degradado ante un cuerpo ilegible se escribe tres veces, son tres
degradados distintos en cuanto alguien toque uno**, y este en concreto tiene que tratar de la
misma forma a las tres etapas o el prefiltro y las reglas dejarían de estar de acuerdo sobre
qué normas tienen cuerpo.

**El XML archivado sigue siendo dato no confiable** (regla de oro 1): pasa por `xml_safe` igual
que cuando llegó de la fuente. Archivarlo no lo hace confiable, solo reproducible.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.models.norma import Norma
from app.pipeline.citas import extraer_referencias_citadas
from app.pipeline.referencias import ReferenciaAnterior, extraer_referencias_anteriores
from app.pipeline.texto import texto_plano
from app.pipeline.watchlist import Watchlist
from app.security import pdf_safe, xml_safe
from app.security.hashing import UnsafeStoragePath
from app.security.pdf_safe import PdfSafeError
from app.security.xml_safe import XmlSafeError
from app.services.archivo import leer

logger = logging.getLogger(__name__)


class CuerpoIlegible(Exception):
    """Hay cuerpo archivado y no se puede usar. ADR 0020.

    Existe porque el `None` que devolvía antes esta función cubría dos hechos distintos —"no lo
    hemos descargado" y "lo descargamos y no se puede leer"— y el segundo se quedaba sin nadie
    que lo mirase: el prefiltro degradaba a fase 1 y la norma acababa en `pendiente`, o sea
    confundida con las que esperan su texto íntegro. Medido sobre el DOGC el 2026-08-18: 172 de
    264 normas en esa situación, y ninguna cifra del embudo las señalaba.

    Se levanta como excepción y no se devuelve como variante del valor a propósito: obliga a
    cada uno de los cuatro llamantes —prefiltro, extractor, catálogo de reglas y versionado— a
    decidir qué hace con ella, que es lo contrario de lo que pasaba con el `None` compartido.

    El motivo real (`DtdForbidden`, fichero ausente…) viaja en `__cause__` y ya se ha registrado
    en el log; no se persiste, porque se puede reproducir en cualquier momento sobre el documento
    archivado, que es de lo que va 6.5.
    """


@dataclass(frozen=True)
class Cuerpo:
    """El texto íntegro derivado de una norma y las referencias que declara."""

    texto: str
    # **Dos orígenes, un solo tipo** (ADR 0022):
    #
    # - El bloque `<analisis>`, que se lee de la **raíz** del documento y no del texto derivado:
    #   es metadato estructurado del BOE y `texto_plano` lo deja fuera a propósito.
    # - Las **citas dentro del texto** (`pipeline/citas.py`), que es lo único que hay en las
    #   fuentes que no publican ese bloque. El DOGC es una: 0 de sus 92 cuerpos legibles traen
    #   referencias utilizables, frente a 211 de 2.968 en el BOE.
    #
    # Se fusionan aquí y no en cada llamante para que el prefiltro, el versionado y las reglas
    # no tengan que saber de qué boletín viene una norma — el mismo criterio con el que
    # `ingest/dogc.py` devuelve el `Sumario` del BOE en vez de un tipo propio.
    referencias: tuple[ReferenciaAnterior, ...]


def leer_cuerpo(
    norma: Norma, *, almacen_root: Path, lista: Watchlist | None = None
) -> Cuerpo | None:
    """El cuerpo archivado de una norma. `None` **solo** si todavía no hay cuerpo.

    `lista` es la watchlist con la que buscar **citas en el texto** (ADR 0022). Se pasa y no se
    carga aquí dentro a propósito: cargarla por su cuenta metería estado global en una función de
    lectura, haría que el resultado dependiera de un fichero que el llamante no ve, y —lo que
    delató el diseño— dejaría fuera de juego a los tests que sustituyen la watchlist. Sin `lista`
    solo se devuelven las referencias del metadato, que es lo que necesita el extractor.

    Las dos situaciones que antes compartían el `None` ahora se distinguen en el tipo, y esa
    separación es todo el ADR 0020:

    - No hay cuerpo archivado todavía (fase 1). Devuelve `None`. Es el caso normal y no se
      registra nada.
    - Lo hay y no se puede leer o parsear. **Levanta `CuerpoIlegible`**, tras registrarlo. "No
      lo hemos descargado" y "lo descargamos y no se puede leer" son hechos distintos, y
      devolverlos con el mismo valor dejaba el segundo sin nadie que lo mirase.

    Quien llame decide qué hacer con cada uno: el prefiltro degrada el `None` a fase 1 (sobre el
    título no se descarta nunca, 7.1) y marca la excepción como `ilegible`; el extractor y el
    catálogo de reglas se abstienen y la cuentan. Ninguno inventa un veredicto.
    """
    if norma.documento_texto is None:
        return None
    try:
        contenido = leer(norma.documento_texto.ruta_almacen, almacen_root=almacen_root)
    except (OSError, UnsafeStoragePath) as exc:
        logger.error(
            "No se puede leer del almacén el cuerpo de %s: %s: %s",
            norma.identificador_oficial,
            type(exc).__name__,
            exc,
        )
        raise CuerpoIlegible(norma.identificador_oficial) from exc

    # **El formato se decide por el contenido, no por la extensión ni por la fuente.** Un PDF
    # archivado con nombre `.xml` sigue siendo un PDF, y confiar en el nombre de un fichero que
    # viene de fuera es exactamente el error que 6.3 prohíbe para las rutas.
    #
    # Que esta rama exista es el ADR 0026: el DOGC publica muchas normas solo en PDF, y hasta
    # ahora sus cuerpos se marcaban `ilegible` porque `xml_safe` no podía con ellos. La capa de
    # texto está ahí —medido: 795 KB de PDF dan 8.295 caracteres limpios— así que lo que faltaba
    # no era OCR, era mirar.
    if contenido[:5] == b"%PDF-":
        try:
            texto_pdf = pdf_safe.extraer_texto(contenido)
        except PdfSafeError as exc:
            logger.error(
                "CONTROL DE SEGURIDAD al leer el PDF de %s: %s: %s",
                norma.identificador_oficial,
                type(exc).__name__,
                exc,
            )
            raise CuerpoIlegible(norma.identificador_oficial) from exc
        # **Sin referencias del metadato, y eso no es un descuido.** Un PDF no trae el bloque
        # `<analisis>` del BOE, así que el eje referencial aquí solo puede alimentarse de las
        # citas del propio texto (ADR 0022) — que es justo lo que ese ADR existía para cubrir en
        # las fuentes que no publican metadatos.
        citadas_pdf = (
            extraer_referencias_citadas(texto_pdf, lista, norma.titulo or "")
            if lista is not None
            else ()
        )
        return Cuerpo(texto=texto_pdf, referencias=citadas_pdf)

    try:
        raiz = xml_safe.parse(contenido)
    except XmlSafeError as exc:
        logger.error(
            "CONTROL DE SEGURIDAD al leer el cuerpo archivado de %s: %s: %s",
            norma.identificador_oficial,
            type(exc).__name__,
            exc,
        )
        raise CuerpoIlegible(norma.identificador_oficial) from exc
    # Aquí ya NO se captura `OSError`: la lectura del disco se movió arriba, antes de decidir el
    # formato, y `xml_safe.parse` trabaja sobre bytes que ya están en memoria. Dejar el `except`
    # habría sido código muerto que además insinúa que este bloque toca el disco, y no lo toca.
    texto = texto_plano(raiz)
    # Primero lo que declara la fuente y después lo que dice el texto. Las dos listas se
    # **concatenan sin deduplicar**: una norma puede salir en las dos, y eso no estorba porque
    # quien las consume las trata como indicios sueltos —`prefiltro.evaluar` pregunta si alguna
    # es modificativa, `versionado._objetivos` mete los objetivos en un `dict`— y ninguna cuenta
    # cuántas hay. Deduplicar aquí obligaría a decidir cuál de los dos verbos gana, que es una
    # decisión de pipeline y no de lectura.
    citadas = (
        extraer_referencias_citadas(texto, lista, norma.titulo or "") if lista is not None else ()
    )
    return Cuerpo(texto=texto, referencias=extraer_referencias_anteriores(raiz) + citadas)
