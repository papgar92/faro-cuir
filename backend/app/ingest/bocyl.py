"""Ingesta del BOCYL (Boletín Oficial de Castilla y León). ADR 0029.

**Cuarta fuente del proyecto y tercera autonómica.** Y la primera cuyo sumario hay que leer de
HTML, lo que obliga a trazar una línea que conviene tener clara antes de tocar nada:

> **El HTML aporta identificadores y metadatos. El texto que una alerta llegue a citar sale
> siempre del XML.** La cadena de evidencia (6.5, 7.5) no pasa por el raspado en ningún punto.

## De dónde sale cada cosa, verificado descargando

- **Sumario de un día:** `boletin.do?fechaBoletin=dd/mm/aaaa`, HTML **en UTF-8**. De ahí salen
  los identificadores de las disposiciones del día, su título, su sección y su organismo.
- **Cuerpo de una disposición:** `boletines/AAAA/MM/DD/xml/BOCYL-D-ddmmaaaa-N.xml`, XML **en
  ISO-8859-15**, con `seccion`, `organismo`, `rango`, `numeroOficial` y el articulado en
  `contenido > texto`.

**Los dos documentos usan codificaciones distintas y es el error fácil de esta fuente.** El XML
lo resuelve solo por su prólogo; el HTML se decodifica como UTF-8 porque así lo declara su
cabecera `Content-Type`, comprobado.

## Lo que la distingue del BOA (ADR 0028), y es una mejora

**Aquí el cuerpo se direcciona por su identificador, no por su posición dentro del día.** La URL
nombra el documento, así que desaparece la fragilidad que obligó al BOA a verificar el `<docn>`
de cada cuerpo antes de archivarlo. Aun así se comprueba la `<fechaPublicacion>` del XML contra
la fecha que lleva el propio identificador: es barato y caza el caso de que el portal sirva otra
cosa bajo la misma URL, que es lo que la 6.5 no puede permitirse.

## Dos particularidades del sumario que hay que conocer

1. **Hay un enlace fijo a una disposición de 2022 en todas las páginas**, incluidas las de días
   sin boletín. Por eso los identificadores **se filtran por la fecha pedida** y no se toman
   todos los que aparezcan: sin ese filtro, cada sábado ingeriría una norma de noviembre de 2022
   y el archivo diría que se publicó ese sábado.
2. **Un día sin boletín no da 404**: devuelve una página corta que, tras el filtro por fecha,
   deja cero disposiciones. Se trata como el 404 del BOE y la lista vacía del DOGC. Es la misma
   pregunta que hubo que hacerle al BOA y que ninguna fuente documenta: *cómo dices tú que un día
   no tiene boletín*.

## Lo que NO trae

No hay equivalente del `<analisis>` del BOE: el XML no dice a qué norma afecta la disposición.
El eje referencial (7.3) depende aquí de las citas del texto (`pipeline/citas.py`, ADR 0022),
igual que en el DOGC y en el BOA. **La estructura de referencias es una particularidad del BOE,
no un estándar.**
"""

from __future__ import annotations

import datetime
import html
import logging
import re
from xml.etree.ElementTree import Element

import httpx

from app.ingest.boe import ItemSumario, Sumario, SumarioInvalido, SumarioNoDisponible
from app.security import url_guard, xml_safe

_BASE = "https://bocyl.jcyl.es"

# Tope de disposiciones por día. Un día normal trae del orden de 30; el tope existe porque el
# número lo decide la fuente y no nosotros, y sin él una respuesta anómala se convertiría en
# miles de descargas de cuerpo (6.2).
MAX_ITEMS_POR_DIA = 300

CABECERAS_SUMARIO = {"Accept": "text/html"}
CABECERAS_TEXTO = {"Accept": "application/xml"}

logger = logging.getLogger(__name__)

_LONGITUD_MAXIMA_TITULO = 2000

# Los cuatro elementos que hacen falta del sumario, en orden de documento. Se buscan a la vez
# —una sola pasada— para poder llevar el estado de sección y organismo vigentes cuando aparece
# cada identificador. Es raspado, sí, pero acotado: de aquí no sale ni un carácter de articulado.
_MARCADOR = re.compile(
    r"<h3[^>]*>(?P<seccion>.*?)</h3>"
    r"|<h5[^>]*class=\"encabezado6\"[^>]*>(?P<organismo>.*?)</h5>"
    r"|<p>(?P<titulo>[^<]{10,}?)</p>"
    r"|BOCYL-D-(?P<fecha>\d{8})-(?P<numero>\d+)\.pdf",
    re.DOTALL | re.IGNORECASE,
)

_ETIQUETA = re.compile(r"<[^>]+>")
_ESPACIOS = re.compile(r"\s+")

# Un día con boletín sirve el XML con su prólogo. Cualquier otra cosa —una página de error del
# portal— se rechaza antes de tocar el parser, por lo mismo que en el BOA: un `<!DOCTYPE html>`
# haría saltar `xml_safe` y el worker lo trataría como fallo de control de seguridad, abortando
# la tanda entera. Reconocerlo aquí no relaja `xml_safe`: ese HTML no se parsea, se rechaza.
_PROLOGO_XML = b"<?xml"


def _limpiar(bruto: str) -> str:
    """Quita marcado y desescapa entidades. Solo para metadatos, nunca para articulado."""
    return _ESPACIOS.sub(" ", html.unescape(_ETIQUETA.sub(" ", bruto))).strip()


def url_sumario(fecha: datetime.date) -> str:
    """El sumario del día. La fuente filtra por fecha exacta, no nosotros."""
    return f"{_BASE}/boletin.do?fechaBoletin={fecha.strftime('%d/%m/%Y')}"


def url_texto(identificador: str) -> str:
    """El XML de una disposición, direccionado **por su identificador**.

    A diferencia del BOA (ADR 0028), aquí la URL nombra el documento: no hay posiciones
    ordinales que puedan dejar de significar lo mismo si la fuente reordena un día.
    """
    encontrado = re.fullmatch(r"BOCYL-D-(\d{2})(\d{2})(\d{4})-(\d+)", identificador)
    if encontrado is None:
        # El identificador lo acuñamos nosotros al parsear el sumario, así que llegar aquí con
        # uno mal formado sería un fallo nuestro. Se valida igual antes de componer una URL con
        # él, porque su contenido viene de una fuente externa (6.10).
        raise ValueError(f"Identificador del BOCYL mal formado: {identificador!r}")
    dia, mes, anyo, _ = encontrado.groups()
    return f"{_BASE}/boletines/{anyo}/{mes}/{dia}/xml/{identificador}.xml"


def descargar_sumario(fecha: datetime.date, *, client: httpx.Client | None = None) -> bytes:
    """Descarga el sumario de un día. Devuelve los bytes crudos, sin tocar.

    Crudos a propósito: el `sha256` del archivo íntegro (6.5) tiene que calcularse sobre
    exactamente lo que envió el servidor.
    """
    return url_guard.fetch(url_sumario(fecha), headers=CABECERAS_SUMARIO, client=client)


def parsear_sumario(contenido: bytes, fecha: datetime.date) -> Sumario:
    """Lee un sumario del BOCYL ya descargado.

    El HTML se decodifica como **UTF-8**, que es lo que declara la fuente en su `Content-Type`
    (y lo contrario que el XML de los cuerpos, que va en ISO-8859-15). Los errores se sustituyen
    en vez de reventar: un byte suelto mal codificado no debe costar el día entero, y lo que se
    saca de aquí son metadatos, no la evidencia que se cita.
    """
    texto = contenido.decode("utf-8", errors="replace")
    esperada = fecha.strftime("%d%m%Y")

    seccion = organismo = titulo = ""
    vistos: set[str] = set()
    items: list[ItemSumario] = []
    otras_fechas = 0

    for marca in _MARCADOR.finditer(texto):
        if marca.group("seccion") is not None:
            seccion = _limpiar(marca.group("seccion"))
            continue
        if marca.group("organismo") is not None:
            organismo = _limpiar(marca.group("organismo"))
            continue
        if marca.group("titulo") is not None:
            titulo = _limpiar(marca.group("titulo"))
            continue

        if marca.group("fecha") != esperada:
            # Particularidad 1: todas las páginas llevan un enlace fijo a una disposición de
            # 2022. Sin este filtro, cada día sin boletín ingeriría esa norma y el archivo
            # afirmaría que se publicó ese día.
            otras_fechas += 1
            continue

        identificador = f"BOCYL-D-{marca.group('fecha')}-{marca.group('numero')}"
        if identificador in vistos:
            # El sumario repite cada enlace, y además deja copias comentadas en el HTML.
            continue
        if not titulo:
            logger.warning(
                "Disposición %s del BOCYL sin título en el sumario: NO se vigila.", identificador
            )
            continue

        vistos.add(identificador)
        # **El título se consume, la sección y el organismo se arrastran.** No es simetría rota:
        # `<h3>` y `<h5>` son cabeceras de grupo y valen para todas las disposiciones de debajo,
        # mientras que `<p>` es de una sola. Sin este reinicio, una disposición sin título propio
        # heredaría el de la anterior y se archivaría con el título de otra norma — peor que
        # descartarla, porque no falla nada visiblemente. Lo cazó su test.
        suyo, titulo = titulo, ""
        items.append(
            ItemSumario(
                identificador=identificador,
                titulo=suyo[:_LONGITUD_MAXIMA_TITULO],
                url_xml=url_texto(identificador),
                url_pdf=f"{_BASE}/boletines/{fecha:%Y/%m/%d}/pdf/{identificador}.pdf",
                seccion_codigo="",
                seccion_nombre=seccion,
                departamento=organismo or "BOCYL",
                epigrafe=None,
            )
        )

    if len(items) > MAX_ITEMS_POR_DIA:
        # No se trunca en silencio: lo que faltara sería invisible, que es el fallo que este
        # proyecto no se permite (mismo criterio que el ADR 0020).
        raise SumarioInvalido(
            f"El sumario del BOCYL del {fecha} trae {len(items)} disposiciones, por encima del "
            f"tope de {MAX_ITEMS_POR_DIA}. Puede ser una respuesta anómala y no se ingiere."
        )

    if not items:
        # Particularidad 2: un día sin boletín no da 404, da una página corta. Tras el filtro
        # por fecha quedan cero. Es una respuesta válida del mundo, no un fallo del sistema.
        raise SumarioNoDisponible(
            f"El BOCYL no publicó boletín el {fecha}: su sumario no trae ninguna disposición "
            f"de esa fecha ({len(contenido)} bytes, {otras_fechas} enlaces de otros días)."
        )

    return Sumario(
        identificador=f"BOCYL-S-{fecha.isoformat()}",
        fecha_publicacion=fecha,
        # El BOCYL numera por edición y no la publica en el sumario de forma estable. Se deja
        # vacío en vez de deducirlo: la fecha ya identifica el boletín (regla de oro 8).
        numero_diario="",
        items=tuple(items),
    )


def parsear_cuerpo(contenido: bytes, identificador_esperado: str) -> Element:
    """Valida que el cuerpo descargado es el de la disposición que se pidió, y lo devuelve.

    Aquí la URL **nombra** el documento, así que no puede llegar el de otra disposición como
    podía en el BOA. Lo que sí puede llegar es otra cosa bajo la misma URL —una página de error,
    un documento resellado con otra fecha—, y eso el archivo de la 6.5 no puede aceptarlo: su
    afirmación es «el día X esto decía exactamente esto». La fecha va dentro del identificador,
    así que comprobarla no cuesta ni una petición.
    """
    if not contenido.lstrip().startswith(_PROLOGO_XML):
        raise SumarioInvalido(
            f"Se pidió el cuerpo de {identificador_esperado} y la fuente devolvió "
            f"{len(contenido)} bytes que no son XML."
        )

    encontrado = re.fullmatch(r"BOCYL-D-(\d{2})(\d{2})(\d{4})-\d+", identificador_esperado)
    if encontrado is None:
        raise SumarioInvalido(f"Identificador mal formado: {identificador_esperado!r}")

    raiz = xml_safe.parse(contenido)
    publicada = (raiz.findtext("./fechaPublicacion") or "").strip()
    dia, mes, anyo = encontrado.groups()
    if publicada != f"{anyo}-{mes}-{dia}":
        raise SumarioInvalido(
            f"Se pidió el cuerpo de {identificador_esperado} (del {anyo}-{mes}-{dia}) y el XML "
            f"dice publicarse el {publicada or 'sin fecha'}. No se archiva."
        )
    return raiz


__all__ = [
    "CABECERAS_SUMARIO",
    "CABECERAS_TEXTO",
    "MAX_ITEMS_POR_DIA",
    "SumarioInvalido",
    "SumarioNoDisponible",
    "descargar_sumario",
    "parsear_cuerpo",
    "parsear_sumario",
    "url_sumario",
    "url_texto",
]
