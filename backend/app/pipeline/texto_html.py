"""El tercer nivel de cuerpo: HTML de portal. ADR 0036.

Módulo **puro**: recibe los bytes archivados y devuelve texto. No toca disco ni red, igual que
`pipeline/texto.py`.

## Por qué existe, y por qué no contradice al ADR 0029

El ADR 0029 dejó escrita esta raya, y sigue en pie con una palabra distinta:

> El HTML aporta identificadores y metadatos. El texto que una alerta llegue a citar sale
> siempre del XML.

Lo que esa frase protegía nunca fue el XML: era **que la evidencia salga de un recorte declarado
y reproducible, y no de raspar lo que haya en una página**. El proyecto ya admite PDF desde el
ADR 0026, así que la regla real siempre fue «un formato documental con derivación versionada»,
no «XML». Aquí se hace explícita y se le añade el tercer nivel, con sus obligaciones.

**El nivel es del documento, no de la comunidad.** El DOGC ya publica unas normas en XML y otras
solo en PDF (ADR 0026): agrupar por CCAA se rompería con la fuente que llevamos más tiempo
ingiriendo. Por eso quien decide el nivel es `services/cuerpo.py` mirando los bytes, como ya
hacía con el PDF.

## Las tres obligaciones de este nivel

1. **Contenedor declarado y cerrado.** `CONTENEDORES` es una lista explícita. De un HTML que no
   traiga uno de esos contenedores **no se extrae nada**: no hay recorte genérico, no hay «coge
   el div más grande». Un portal que rediseñe deja de casar y su norma cae a `ilegible`.
2. **Canario de tamaño.** Un recorte que casa pero devuelve menos de `MINIMO_CARACTERES` se
   trata como fallo. Una plantilla vacía, una página de mantenimiento o un contenedor que quedó
   en la maqueta darían un texto corto que el prefiltro leería como «aquí no hay nada
   relevante», que es exactamente el falso negativo invisible de 7.1.
3. **Degradación ruidosa** (6.9.6). Los dos fallos anteriores acaban en `CuerpoIlegible`, o sea
   en el estado `ilegible` de 7.2: fuera de las colas automáticas, **reintentado en cada
   pasada**, y contado aparte en el embudo. Un rediseño del portal se convierte en un montón
   visible de `ilegible`, no en vigilancia que dejó de funcionar sin avisar.

## Lo que este módulo NO relaja

**`xml_safe` sigue rechazando el HTML, y eso no cambia** (6.1 y ADR 0020): en el caso que motivó
el estado `ilegible`, ese control es lo único que impidió que 172 páginas de error del DOGC
entraran como si fueran normas. La obligación 1 es lo que mantiene esa protección aquí: una
página de error **no trae ninguno de los contenedores declarados**, así que sigue siendo
`ilegible` igual que antes. Hay un test que lo fija con la página de error real.

Se usa `html.parser` de la biblioteca estándar. Sin dependencias nuevas (sección 3), y sin
ejecutar nada de lo que traiga la página.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser

# Sube cuando cambie **cómo** se recorta un cuerpo HTML ya archivado. Se registra en la
# evidencia junto a `derivacion`, por lo mismo que `VERSION_TEXTO_PLANO`: un offset sin saber
# sobre qué derivación se midió no es reproducible (7.5).
#
# **Ojo, no es la versión que gobierna el reprocesado.** Esa sigue siendo `VERSION_TEXTO_PLANO`
# y es una sola para toda la capa de derivación a propósito: `services/prefiltro.py` y
# `services/clasificacion.py` deciden qué reevaluar comparando esa columna con esa constante, y
# una versión distinta por documento haría que las normas HTML parecieran caducadas siempre —
# el bucle infinito contra el que ya avisa `services/prefiltro.py`.
VERSION_TEXTO_HTML = "2026.09.06"

# Un cuerpo legítimo del BON más corto que esto no se ha visto: el más pequeño medido pasa de
# 600 caracteres. El tope está bajo a propósito — es un canario contra la plantilla vacía, no un
# juicio sobre si la norma es sustanciosa, y **de eso no decide este módulo**.
MINIMO_CARACTERES = 200

# Etiquetas sin cierre: no entran en la pila de profundidad o la cerrarían antes de tiempo.
_VACIAS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)

_ESPACIOS = re.compile(r"\s+")

# Un HTML se reconoce por su prólogo, no por el nombre del fichero ni por la fuente: el mismo
# criterio con el que `services/cuerpo.py` reconoce un PDF por `%PDF-` (6.3).
_PROLOGOS_HTML = (b"<!doctype html", b"<html")


@dataclass(frozen=True)
class Contenedor:
    """Dónde vive el articulado en una fuente concreta. Declarado, no adivinado."""

    etiqueta: str
    atributo: str
    valor: str
    fuente: str


# **La lista es cerrada.** Añadir una fuente de este nivel es añadir una entrada aquí, con su
# comprobación contra un documento real, y decirlo en su ADR.
CONTENEDORES: tuple[Contenedor, ...] = (
    # BON (Navarra), ADR 0036. Verificado contra `/es/anuncio/-/texto/2024/6/1` el 2026-09-06:
    # el recorte da 47.380 caracteres que empiezan en la cabecera del boletín y acaban en
    # «Código del anuncio», sin pie de página ni menú de navegación.
    #
    # Se ancla en el **id de la sección del portlet** y no en una clase: `portlet-body` aparece
    # también en la cabecera y en el pie, y recortando por ahí entraban la dirección postal y el
    # menú. Un id de portlet de Liferay es lo más parecido a un contrato que da esta página.
    Contenedor(
        etiqueta="section",
        atributo="id",
        valor="portlet_es_navarra_bon_detalle_portlet_anuncio_DetalleAnuncioPortlet",
        fuente="BON",
    ),
)


def es_html(contenido: bytes) -> bool:
    """Si estos bytes son una página HTML. Por el prólogo, no por el nombre ni por la fuente."""
    cabeza = contenido[:512].lstrip().lower()
    return cabeza.startswith(_PROLOGOS_HTML)


class _Recorte(HTMLParser):
    """Acumula el texto del subárbol del primer contenedor que case, y solo de ese."""

    def __init__(self, contenedor: Contenedor) -> None:
        super().__init__(convert_charrefs=True)
        self._contenedor = contenedor
        self._pila: list[str] = []
        self._dentro = False
        self._cerrado = False
        self._saltar = 0
        self.trozos: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._cerrado:
            return
        if not self._dentro:
            atributos = dict(attrs)
            if (
                tag == self._contenedor.etiqueta
                and atributos.get(self._contenedor.atributo) == self._contenedor.valor
            ):
                self._dentro = True
                self._pila = [tag]
            return
        # `script` y `style` llevan texto que no es contenido. Se cuentan por profundidad y no
        # con un booleano porque pueden anidarse dentro de plantillas.
        if tag in ("script", "style"):
            self._saltar += 1
        if tag not in _VACIAS:
            self._pila.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if self._cerrado or not self._dentro:
            return
        if tag in ("script", "style") and self._saltar:
            self._saltar -= 1
        if tag in self._pila:
            # Se desapila hasta la etiqueta que cierra: el HTML real trae etiquetas sin cerrar y
            # un `pop()` a ciegas dejaría la pila desalineada para siempre.
            while self._pila and self._pila.pop() != tag:
                pass
            if not self._pila:
                self._cerrado = True

    def handle_data(self, data: str) -> None:
        if self._dentro and not self._cerrado and not self._saltar:
            texto = data.strip()
            if texto:
                self.trozos.append(texto)


def texto_de_html(contenido: bytes) -> str:
    """El articulado de un cuerpo HTML, o **cadena vacía** si no se puede afirmar cuál es.

    Cadena vacía significa «no se ha podido recortar», nunca «esta norma no dice nada»: quien
    llama (`services/cuerpo.py`) la convierte en `CuerpoIlegible`, que es un estado que se
    reintenta y se cuenta, no un descarte.

    Se decodifica como UTF-8 con sustitución. Los portales declaran su codificación en una
    cabecera HTTP que aquí ya no está —lo que se archiva son los bytes, 6.5— y un byte suelto mal
    decodificado no debe costar la norma entera: lo que se pierde es un carácter, no el
    articulado. Si algún día una fuente de este nivel llega en otra codificación, se declara aquí
    junto a su contenedor y no se adivina.
    """
    texto_bruto = contenido.decode("utf-8", errors="replace")
    for contenedor in CONTENEDORES:
        recorte = _Recorte(contenedor)
        recorte.feed(texto_bruto)
        recorte.close()
        if not recorte.trozos:
            continue
        texto = _ESPACIOS.sub(" ", " ".join(recorte.trozos)).strip()
        if len(texto) >= MINIMO_CARACTERES:
            return texto
    return ""


__all__ = [
    "CONTENEDORES",
    "MINIMO_CARACTERES",
    "VERSION_TEXTO_HTML",
    "Contenedor",
    "es_html",
    "texto_de_html",
]
