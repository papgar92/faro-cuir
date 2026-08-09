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


@dataclass(frozen=True)
class Cuerpo:
    """El texto íntegro derivado de una norma y las referencias que declara."""

    texto: str
    # Del bloque `<analisis>`, que se lee de la **raíz** del documento y no del texto derivado:
    # es metadato estructurado del BOE y `texto_plano` lo deja fuera a propósito.
    referencias: tuple[ReferenciaAnterior, ...]


def leer_cuerpo(norma: Norma, *, almacen_root: Path) -> Cuerpo | None:
    """El cuerpo archivado de una norma, o `None` si no se puede usar.

    `None` cubre dos situaciones que **no son la misma** y por eso solo una hace ruido:

    - No hay cuerpo archivado todavía (fase 1). Es el caso normal y no se registra nada.
    - Lo hay y no se puede leer o parsear. Se registra como error, porque "no lo hemos
      descargado" y "lo descargamos y está roto" son hechos distintos y confundirlos deja el
      segundo sin nadie que lo mire.

    Quien llame decide qué hacer con el `None`: el prefiltro degrada a fase 1 (sobre el título
    no se descarta nunca, 7.1), el catálogo de reglas se abstiene. Ninguno inventa un veredicto.
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
        return None
    except OSError as exc:
        logger.error(
            "Falta en el almacén el cuerpo de %s (%s): %s",
            norma.identificador_oficial,
            norma.documento_texto.ruta_almacen,
            exc,
        )
        return None
    return Cuerpo(texto=texto_plano(raiz), referencias=extraer_referencias_anteriores(raiz))
