"""Parseo endurecido de XML no confiable: CLAUDE.md 6.1.

Los sumarios de los boletines llegan en XML de servidores que no controlamos. Un parser XML
con la configuración de fábrica no es un lector de datos: es un intérprete con acceso al
disco y a la red, controlado por quien escribe el documento.

Igual que `url_guard` es la única salida HTTP, **este módulo es el único sitio donde se
parsea XML**. Nada debe importar `xml.etree`, `lxml` ni `defusedxml` directamente.

Ataques que cierra:

- **XXE** — `<!ENTITY xxe SYSTEM "file:///etc/passwd">` para leer ficheros del contenedor, o
  `SYSTEM "http://169.254.169.254/..."` para convertir el parser en un segundo canal de SSRF
  que se saltaría por completo a `url_guard`.
- **Billion laughs / expansión cuadrática** — entidades anidadas que ocupan kilobytes en el
  fichero y gigabytes en memoria.
- **Bomba por anidamiento** — decenas de miles de etiquetas abiertas para agotar memoria y
  reventar por recursión cualquier recorrido posterior del árbol.
- **Documentos desmesurados** — tope de bytes antes de tocar el parser.

Sobre la elección de fondo: `forbid_dtd=True` prohíbe el DOCTYPE entero, no solo las
entidades peligrosas. Es más estricto que lo mínimo y es a propósito — sin DTD no hay
declaración de entidades posible, así que XXE y las bombas de entidades dejan de tener por
dónde entrar en vez de depender de que el filtro de entidades no tenga un hueco. Si alguna
fuente real resultara publicar XML con DOCTYPE legítimo, se revisita con un ADR; no se
relaja aquí sin dejar rastro.
"""

from __future__ import annotations

import io

# De la stdlib solo se importan tipos y la excepción de sintaxis; el parseo lo hace
# defusedxml. Importar `Element`/`ParseError` no habilita ningún parser inseguro.
from xml.etree.ElementTree import Element, ParseError

# Cualificado a propósito: nuestras excepciones de abajo se llaman casi igual, y un import
# suelto haría que la clase local tapara a la de defusedxml dejando su `except` muerto.
from defusedxml import common as defused
from defusedxml.ElementTree import iterparse

# Tope de entrada. Coincide con el de url_guard: lo que no se puede descargar tampoco hace
# falta poder parsearlo.
MAX_XML_BYTES: int = 20 * 1024 * 1024

# Un sumario del BOE es esencialmente una lista plana de secciones y documentos. 100 niveles
# es holgadísimo para eso y sigue estando muy por debajo de lo que hace daño.
MAX_DEPTH: int = 100

# Tope de elementos: la defensa contra el fichero que no anida pero trae millones de nodos
# hermanos. El tope de bytes ya acota esto, pero un XML muy repetitivo cabe en pocos MB y
# aun así cuesta mucha memoria una vez convertido en objetos de Python.
MAX_ELEMENTS: int = 500_000


class XmlSafeError(Exception):
    """El documento se rechaza. Nunca se degrada a aviso ni se parsea 'a lo que salga'."""


class XmlTooLarge(XmlSafeError):
    pass


class DtdForbidden(XmlSafeError):
    pass


class EntityForbidden(XmlSafeError):
    pass


class ExternalReferenceForbidden(XmlSafeError):
    pass


class MaxDepthExceeded(XmlSafeError):
    pass


class MaxElementsExceeded(XmlSafeError):
    pass


class MalformedXml(XmlSafeError):
    pass


def parse(
    data: bytes,
    *,
    max_bytes: int = MAX_XML_BYTES,
    max_depth: int = MAX_DEPTH,
    max_elements: int = MAX_ELEMENTS,
) -> Element:
    """Parsea `data` con todos los controles y devuelve el elemento raíz.

    Lanza la subclase de `XmlSafeError` correspondiente al primer control que falle.
    """
    if len(data) > max_bytes:
        raise XmlTooLarge(f"El XML ocupa {len(data)} bytes, por encima del tope de {max_bytes}")

    # iterparse en vez de fromstring: los límites de profundidad y de número de elementos se
    # comprueban mientras se parsea, así que una bomba por anidamiento se corta a mitad del
    # documento en vez de después de haber construido el árbol entero en memoria.
    depth = 0
    elements = 0
    root: Element | None = None

    try:
        for event, element in iterparse(
            io.BytesIO(data),
            events=("start", "end"),
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        ):
            if event == "start":
                if root is None:
                    root = element
                depth += 1
                elements += 1
                if depth > max_depth:
                    raise MaxDepthExceeded(
                        f"Anidamiento por encima de {max_depth} niveles: posible bomba XML"
                    )
                if elements > max_elements:
                    raise MaxElementsExceeded(f"Más de {max_elements} elementos: posible bomba XML")
            else:
                depth -= 1
    except defused.DTDForbidden as exc:
        raise DtdForbidden(
            "El documento declara un DOCTYPE. Prohibido: es la vía de entrada de XXE y de "
            "las bombas de entidades."
        ) from exc
    except defused.EntitiesForbidden as exc:
        raise EntityForbidden("El documento declara entidades personalizadas. Prohibido.") from exc
    except defused.ExternalReferenceForbidden as exc:
        raise ExternalReferenceForbidden(
            "El documento referencia un recurso externo. Prohibido: el parser no sale a "
            "disco ni a la red."
        ) from exc
    except ParseError as exc:
        raise MalformedXml(f"XML mal formado: {exc}") from exc

    if root is None:
        raise MalformedXml("El documento no contiene ningún elemento")

    return root
