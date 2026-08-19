"""Del almacén al material sobre el que trabajan las etapas del pipeline.

Una norma con `documento_texto_id` tiene su texto íntegro archivado (ADR 0015). Tres etapas lo
necesitan —prefiltro sobre texto íntegro, extractor y catálogo de reglas— y las tres necesitan
exactamente lo mismo: leer del disco, parsear con `xml_safe`, derivar el texto con la versión
vigente de `texto_plano` y sacar las referencias del `<analisis>`.

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
from app.pipeline.referencias import ReferenciaAnterior, extraer_referencias_anteriores
from app.pipeline.texto import texto_plano
from app.security import xml_safe
from app.security.hashing import UnsafeStoragePath
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
    # Del bloque `<analisis>`, que se lee de la **raíz** del documento y no del texto derivado:
    # es metadato estructurado del BOE y `texto_plano` lo deja fuera a propósito.
    referencias: tuple[ReferenciaAnterior, ...]


def leer_cuerpo(norma: Norma, *, almacen_root: Path) -> Cuerpo | None:
    """El cuerpo archivado de una norma. `None` **solo** si todavía no hay cuerpo.

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
        raiz = xml_safe.parse(contenido)
    except (XmlSafeError, UnsafeStoragePath) as exc:
        logger.error(
            "CONTROL DE SEGURIDAD al leer el cuerpo archivado de %s: %s: %s",
            norma.identificador_oficial,
            type(exc).__name__,
            exc,
        )
        raise CuerpoIlegible(norma.identificador_oficial) from exc
    except OSError as exc:
        logger.error(
            "Falta en el almacén el cuerpo de %s (%s): %s",
            norma.identificador_oficial,
            norma.documento_texto.ruta_almacen,
            exc,
        )
        raise CuerpoIlegible(norma.identificador_oficial) from exc
    return Cuerpo(texto=texto_plano(raiz), referencias=extraer_referencias_anteriores(raiz))
