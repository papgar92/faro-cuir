"""Ingesta del BON (Boletín Oficial de Navarra). ADR 0036.

**Séptima fuente del proyecto y sexta autonómica**, y la primera del **nivel HTML**
(`pipeline/texto_html.py`): la primera cuyo articulado no se publica en ningún formato
documental, ni XML ni PDF. Lo que hace admisible ese nivel —contenedor declarado, canario de
tamaño y degradación a `ilegible`— está en ese módulo y en el ADR; aquí va lo que es de Navarra.

## Las tres URLs, verificadas descargando (2026-09-06)

1. **Índice:** `/es/boletines`. Lista **los cuatro últimos** boletines con su número y su fecha.
   Es el atajo del día a día: una petición y la mayoría de las veces basta.
2. **Sumario:** `/es/boletin/-/sumario/{aaaa}/{numero}`. Declara su propia cabecera
   —`BOLETÍN Nº 6 - 9 de enero de 2024`—, que es lo que permite **comprobar que el boletín que
   llegó es el del día que se pidió**. Sin esa cabecera esta fuente no sería archivable (6.5).
3. **Cuerpo:** `/es/anuncio/-/texto/{aaaa}/{numero}/{orden}`. HTML. **El orden empieza en 0**,
   no en 1.

## Fecha → número: no hay índice, se busca y se comprueba

El BON **no publica un calendario**. Su `?anio=&mes=&dia=` existe y **ignora la fecha**: pedirle
el 10 de enero de 2024 devuelve el último boletín publicado, byte por byte igual que pedirle
cualquier otro día. Es la misma trampa del RSS del BOCYL (ADR 0029) y, como allí, se descubre
pidiendo dos días distintos y comparando, no leyendo la documentación.

Lo que sí hay es que **cada sumario declara su fecha**, así que se puede buscar y verificar:

1. Se mira el índice. Si la fecha está entre los cuatro últimos, resuelto en una petición.
2. Si no, **bisección sobre el número de boletín** dentro del año, que es monótono en la fecha
   (comprobado: 1 → 2 ene, 6 → 9 ene, 120 → 11 jun, 253 → 16 dic de 2024). Cada sondeo lee la
   cabecera del candidato, así que **la fecha nunca se supone: la declara el documento**.
3. Y después se miran los vecinos, por lo que viene ahora.

Coste: hasta `MAX_SONDEOS` peticiones por día resuelto, y cada sumario pesa ~100 KB. Para la
pasada diaria casi siempre es una; **para un backfill es cara, y conviene saberlo antes de
lanzarlo** en vez de descubrirlo a mitad.

## Un día puede traer dos boletines, aquí también

Igual que el BOPV (ADR 0035): los boletines **253 y 254 son los dos del 16 de diciembre de
2024**, y el 254 trae **una sola disposición**. La diferencia a favor del BON es que lo dice: su
cabecera añade ` - EXTRAORDINARIO`.

Por eso `resolver_ediciones` no para al encontrar una: mira los vecinos hasta que la fecha
cambia. Quedarse con la primera perdería un boletín extraordinario entero y en silencio, que es
lo que este proyecto existe para no hacer.

## Dos trampas del HTML del sumario

1. **El atributo `title` del enlace lleva comillas sin escapar** —`la subvención "Subvenciones a
   entidades…"`—, así que leerlo como atributo lo trunca en la primera comilla interior. **El
   título se toma del texto del enlace**, no del atributo.
2. **El ámbito y la sección son cabeceras de grupo** (`<p class="… b-ambito">`,
   `b-seccion`), como en el BOCYL y el BOPV: se arrastran, y la sección se reinicia al cambiar
   de ámbito.

## Cómo dice que un número no existe

Con **HTTP 200 y una página vacía**: pedirle el boletín 999 de 2024 responde 200, sin cabecera y
sin ninguna disposición. Es la séptima forma distinta que se encuentra este proyecto, y ninguna
fuente la documenta.
"""

from __future__ import annotations

import datetime
import html as _html
import logging
import re
from dataclasses import dataclass
from html.parser import HTMLParser

import httpx

from app.ingest.boe import ItemSumario, Sumario, SumarioInvalido, SumarioNoDisponible
from app.security import url_guard

_BASE = "https://bon.navarra.es"

# Tope de disposiciones por boletín. Los días medidos van de 1 a 78; el tope existe porque el
# número lo decide la fuente y no nosotros (6.2).
MAX_ITEMS_POR_EDICION = 400

# Tope de ediciones por día. Medido: el máximo observado es 2 (el ordinario y su extraordinario).
MAX_EDICIONES_POR_DIA = 6

# Tope del número de boletín dentro de un año. 2024 llegó a 254 contando extraordinarios; 400 da
# margen de sobra y acota la bisección a 9 sondeos.
MAX_NUMERO = 400

# Tope duro de peticiones por resolución de fecha. La bisección necesita 9 y el barrido de
# vecinos 2 en un día normal (3 si hay extraordinario), así que 16 deja margen y sigue acotando.
#
# **Agotarlo es un error, no un final.** Antes el barrido de vecinos lo comprobaba en su `while`
# y se paraba sin más: eso truncaba la lista de ediciones **en silencio**, que es exactamente lo
# que el ADR 0020 prohíbe. Ahora lo levanta quien cuenta los sondeos, y la pasada falla en alto.
MAX_SONDEOS = 16

CABECERAS_HTML = {"Accept": "text/html"}
CABECERAS_TEXTO = {"Accept": "text/html"}

logger = logging.getLogger(__name__)

_LONGITUD_MAXIMA_TITULO = 2000

_MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

# `BOLETÍN Nº 254 - 16 de diciembre de 2024 - EXTRAORDINARIO`. La `Nº` se escribe con entidades
# distintas según la página, así que se admite cualquier cosa corta entre la N y el número.
_CABECERA = re.compile(
    r"BOLET[IÍ]N\s*N\S{0,3}\s*(?P<numero>\d{1,4})\s*-\s*"
    r"(?P<dia>\d{1,2})\s+de\s+(?P<mes>[a-záéíóúñ]+)\s+de\s+(?P<anyo>\d{4})"
    r"(?P<extra>\s*-\s*EXTRAORDINARIO)?",
    re.IGNORECASE,
)

_ENLACE_TEXTO = re.compile(
    r"/es/anuncio/-/texto/(?P<anyo>\d{4})/(?P<numero>\d{1,4})/(?P<orden>\d+)"
)
_ETIQUETA = re.compile(r"<[^>]+>")
_ESPACIOS = re.compile(r"\s+")

_IDENTIFICADOR_NORMA = re.compile(r"\ABON-D-(\d{4})-(\d{1,4})-(\d{1,5})\Z")


@dataclass(frozen=True)
class Cabecera:
    """Lo que un sumario del BON declara de sí mismo. Es lo que lo hace archivable."""

    numero: int
    fecha: datetime.date
    extraordinario: bool


def url_indice() -> str:
    return f"{_BASE}/es/boletines"


def url_sumario(anyo: int, numero: int) -> str:
    if not 1 <= numero <= MAX_NUMERO or not 1900 <= anyo <= 2999:
        raise ValueError(f"Boletín del BON fuera de rango: {anyo}/{numero}")
    return f"{_BASE}/es/boletin/-/sumario/{anyo}/{numero}"


def url_texto(anyo: int, numero: int, orden: int) -> str:
    """El cuerpo de una disposición. **El orden empieza en 0**, comprobado."""
    if not 0 <= orden <= 99999:
        raise ValueError(f"Orden del BON fuera de rango: {orden!r}")
    # Valida año y número reutilizando el rango de `url_sumario`: los tres van a una URL y
    # ninguno los pone este módulo, salen del sumario (6.10).
    url_sumario(anyo, numero)
    return f"{_BASE}/es/anuncio/-/texto/{anyo}/{numero}/{orden}"


def identificador_norma(anyo: int, numero: int, orden: int) -> str:
    """Acuñado por nosotros: la fuente no publica ningún identificador de disposición."""
    return f"BON-D-{anyo}-{numero}-{orden}"


def _texto_visible(contenido: bytes) -> str:
    """El texto de la página sin marcado. Solo para leer cabeceras, nunca para articulado."""
    bruto = contenido.decode("utf-8", errors="replace")
    bruto = re.sub(r"(?is)<(script|style).*?</\1>", " ", bruto)

    return _ESPACIOS.sub(" ", _html.unescape(_ETIQUETA.sub(" ", bruto)))


def parsear_cabecera(contenido: bytes) -> Cabecera | None:
    """`BOLETÍN Nº 6 - 9 de enero de 2024`, o `None` si la página no la trae.

    `None` es la respuesta normal a un número que no existe: el BON contesta 200 con una página
    vacía, no un 404.
    """
    encontrada = _CABECERA.search(_texto_visible(contenido))
    if encontrada is None:
        return None
    mes = _MESES.get(encontrada.group("mes").lower())
    if mes is None:
        return None
    try:
        fecha = datetime.date(int(encontrada.group("anyo")), mes, int(encontrada.group("dia")))
    except ValueError:
        return None
    return Cabecera(
        numero=int(encontrada.group("numero")),
        fecha=fecha,
        extraordinario=encontrada.group("extra") is not None,
    )


def _descargar_sumario_crudo(
    anyo: int, numero: int, *, client: httpx.Client | None = None
) -> bytes:
    return url_guard.fetch(url_sumario(anyo, numero), headers=CABECERAS_HTML, client=client)


def _cabecera_de(anyo: int, numero: int, *, client: httpx.Client | None) -> Cabecera | None:
    return parsear_cabecera(_descargar_sumario_crudo(anyo, numero, client=client))


def resolver_ediciones(
    fecha: datetime.date, *, client: httpx.Client | None = None
) -> tuple[int, ...]:
    """Fecha → números de boletín de ese día. **Todos**, no el primero.

    La fecha nunca se supone: cada candidato que se mira declara la suya, y solo se acepta el que
    la declara igual a la pedida. Si el tope de sondeos se agota se para y se dice, en vez de
    seguir pidiendo a ciegas.
    """
    sondeos = 0

    def cabecera(numero: int) -> Cabecera | None:
        nonlocal sondeos
        if sondeos >= MAX_SONDEOS:
            raise SumarioInvalido(
                f"Resolver el boletín del BON del {fecha} ha agotado el tope de {MAX_SONDEOS} "
                f"sondeos. No se sigue pidiendo a ciegas."
            )
        sondeos += 1
        return _cabecera_de(fecha.year, numero, client=client)

    encontrado = _bisecar(fecha, cabecera)
    if encontrado is None:
        raise SumarioNoDisponible(f"El BON no publicó boletín el {fecha}")

    # Los vecinos, por el extraordinario. El 16 de diciembre de 2024 tiene el 253 y el 254.
    numeros = [encontrado]
    for paso in (-1, 1):
        siguiente = encontrado + paso
        while 1 <= siguiente <= MAX_NUMERO:
            vecina = cabecera(siguiente)
            if vecina is None or vecina.fecha != fecha:
                break
            numeros.append(siguiente)
            siguiente += paso

    numeros.sort()
    if len(numeros) > MAX_EDICIONES_POR_DIA:
        raise SumarioInvalido(
            f"El BON declara {len(numeros)} ediciones el {fecha}, por encima del tope de "
            f"{MAX_EDICIONES_POR_DIA}. Puede ser una respuesta anómala."
        )
    if len(numeros) > 1:
        # Medido: pasa de verdad. Que se vea en el log, para que nadie "simplifique" esto a una
        # sola edición sin saber lo que se estaría perdiendo.
        logger.info("El BON publicó %s ediciones el %s: %s", len(numeros), fecha, numeros)
    return tuple(numeros)


def _bisecar(fecha: datetime.date, cabecera) -> int | None:  # type: ignore[no-untyped-def]
    """El número de boletín de una fecha, buscándolo por bisección sobre un año.

    El número es monótono en la fecha dentro del año (comprobado sobre 2024). Un número que no
    existe devuelve `None` y se trata como «más allá del final», que es lo que es: el BON
    responde 200 con página vacía a cualquier número por encima del último publicado.
    """
    bajo, alto = 1, MAX_NUMERO
    hallado: int | None = None
    while bajo <= alto:
        medio = (bajo + alto) // 2
        actual = cabecera(medio)
        if actual is None:
            alto = medio - 1
            continue
        if actual.fecha == fecha:
            hallado = medio
            break
        if actual.fecha < fecha:
            bajo = medio + 1
        else:
            alto = medio - 1
    return hallado


def descargar_sumario(
    fecha: datetime.date, numero: int, *, client: httpx.Client | None = None
) -> bytes:
    """Descarga el sumario de una edición. Devuelve los bytes crudos, sin tocar (6.5)."""
    return _descargar_sumario_crudo(fecha.year, numero, client=client)


class _LectorSumario(HTMLParser):
    """Lee ámbito, sección y disposiciones del sumario. Solo metadatos: ni un carácter de texto."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ambito = ""
        self.seccion = ""
        self.entradas: list[tuple[str, str, str, int]] = []
        self._clase = ""
        self._enlace: tuple[int, int] | None = None
        self._trozos: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        atributos = dict(attrs)
        if tag == "p":
            self._clase = atributos.get("class") or ""
            self._trozos = []
            return
        if tag == "a":
            enlace = _ENLACE_TEXTO.search(atributos.get("href") or "")
            if enlace is not None:
                self._enlace = (int(enlace.group("numero")), int(enlace.group("orden")))
                self._trozos = []

    def handle_endtag(self, tag: str) -> None:
        texto = _ESPACIOS.sub(" ", " ".join(self._trozos)).strip()
        if tag == "a" and self._enlace is not None:
            if texto:
                self.entradas.append((self.ambito, self.seccion, texto, self._enlace[1]))
            self._enlace = None
            self._trozos = []
            return
        if tag == "p" and self._enlace is None:
            clases = self._clase.split()
            if "b-ambito" in clases:
                self.ambito = texto
                # La sección es de grupo **dentro** del ámbito: sin este reinicio, un ámbito sin
                # sección propia heredaría la del anterior y etiquetaría mal sus normas.
                self.seccion = ""
            elif "b-seccion" in clases:
                self.seccion = texto
            self._clase = ""
            self._trozos = []

    def handle_data(self, data: str) -> None:
        recorte = data.strip()
        if recorte:
            self._trozos.append(recorte)


def parsear_sumario(contenido: bytes, fecha: datetime.date, numero: int) -> Sumario:
    """Lee un sumario del BON ya descargado, comprobando que es el que se pidió.

    **La cabecera no es decoración: es la única garantía de esta fuente.** El BON no tiene
    calendario y su búsqueda por fecha miente, así que si el sumario que llega no declara la
    fecha y el número que se pidieron, no se archiva.
    """
    cabecera = parsear_cabecera(contenido)
    if cabecera is None:
        raise SumarioInvalido(
            f"El sumario {numero} del BON de {fecha.year} no declara su cabecera "
            f"({len(contenido)} bytes). No se archiva algo que no dice qué es."
        )
    if cabecera.numero != numero or cabecera.fecha != fecha:
        raise SumarioInvalido(
            f"Se pidió el boletín {numero} del BON del {fecha} y el contenido dice ser el "
            f"{cabecera.numero} del {cabecera.fecha}. No se archiva."
        )

    lector = _LectorSumario()
    lector.feed(contenido.decode("utf-8", errors="replace"))
    lector.close()

    items: list[ItemSumario] = []
    vistos: set[int] = set()
    for ambito, seccion, titulo, orden in lector.entradas:
        if orden in vistos:
            continue
        vistos.add(orden)
        items.append(
            ItemSumario(
                identificador=identificador_norma(fecha.year, numero, orden),
                titulo=titulo[:_LONGITUD_MAXIMA_TITULO],
                url_xml=url_texto(fecha.year, numero, orden),
                url_pdf=None,
                seccion_codigo="",
                seccion_nombre=ambito,
                # El BON no publica el órgano emisor como dato aparte: va dentro del título. No
                # se deduce del texto (regla de oro 8); la sección es lo más cercano que hay.
                departamento=seccion or "BON",
                epigrafe=seccion or None,
            )
        )

    if len(items) > MAX_ITEMS_POR_EDICION:
        raise SumarioInvalido(
            f"El boletín {numero} del BON del {fecha} trae {len(items)} disposiciones, por "
            f"encima del tope de {MAX_ITEMS_POR_EDICION}. Puede ser una respuesta anómala."
        )
    if not items:
        raise SumarioInvalido(
            f"El boletín {numero} del BON del {fecha} declara su cabecera pero no trae ninguna "
            f"disposición."
        )

    return Sumario(
        identificador=f"BON-S-{fecha:%Y%m%d}-{numero}",
        fecha_publicacion=fecha,
        numero_diario=str(numero),
        items=tuple(items),
    )


def parsear_cuerpo(contenido: bytes, identificador_esperado: str) -> None:
    """Comprueba que el cuerpo descargado es el de la disposición que se pidió.

    **No devuelve un árbol**, a diferencia de las otras cinco fuentes: aquí el cuerpo es HTML y
    quien lo convierte en texto es `pipeline/texto_html.py`, con su contenedor declarado. Esto
    solo verifica que la página trae la cabecera del boletín correcto, que es lo que impide
    archivar bajo una norma el contenido de otra.
    """
    encontrado = _IDENTIFICADOR_NORMA.fullmatch(identificador_esperado)
    if encontrado is None:
        raise SumarioInvalido(f"Identificador mal formado: {identificador_esperado!r}")

    anyo, numero, _ = (int(g) for g in encontrado.groups())
    cabecera = parsear_cabecera(contenido)
    if cabecera is None:
        raise SumarioInvalido(
            f"El cuerpo de {identificador_esperado} no declara la cabecera de su boletín "
            f"({len(contenido)} bytes). No se archiva."
        )
    if cabecera.numero != numero or cabecera.fecha.year != anyo:
        raise SumarioInvalido(
            f"Se pidió el cuerpo de {identificador_esperado} y la página dice ser del boletín "
            f"{cabecera.numero} de {cabecera.fecha.year}. No se archiva."
        )


__all__ = [
    "CABECERAS_HTML",
    "CABECERAS_TEXTO",
    "MAX_EDICIONES_POR_DIA",
    "MAX_ITEMS_POR_EDICION",
    "MAX_NUMERO",
    "MAX_SONDEOS",
    "Cabecera",
    "SumarioInvalido",
    "SumarioNoDisponible",
    "descargar_sumario",
    "identificador_norma",
    "parsear_cabecera",
    "parsear_cuerpo",
    "parsear_sumario",
    "resolver_ediciones",
    "url_indice",
    "url_sumario",
    "url_texto",
]
