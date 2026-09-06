"""Ingesta del BOPV (Boletín Oficial del País Vasco). ADR 0035.

**Sexta fuente del proyecto y quinta autonómica.** Y la que mejor XML publica de las seis: el
sumario **y** el cuerpo son XML, y el cuerpo se direcciona por identificador. Lo que la hacía
parecer imposible hasta el 2026-09-06 era otra cosa —no se podía pedir un día— y la solución
estaba escondida en un `<iframe>`.

## Las tres URLs, verificadas descargando (2026-09-06)

1. **Calendario del mes:** `/bopv2/datos/{mm}{aaaa}.shtml`. Pesa 1,5 KB y trae dos arrays de
   JavaScript emparejados por posición:

   ```js
   var diasHabilitados = ['20260901','20260902','20260903','20260904'];
   var enlaces = [['s26_0166.shtml'],['s26_0167.shtml'],['s26_0168.shtml'],['s26_0169.shtml']];
   ```

   **Esto es el índice fecha → edición que faltaba.** Sin él, el BOPV solo se podía pedir por
   número de boletín, su sumario no declara de qué día es, y por tanto no había forma de
   comprobar que el boletín que llegó era el que se pidió — que para el archivo de la 6.5 no es
   un inconveniente, es un descarte. Comprobado hacia atrás hasta enero de 2024.

2. **Sumario de una edición:** `/bopv2/datos/{aaaa}/{mm}/s{aa}_{nnnn}.xml`, XML en UTF-8. La
   carpeta del mes es estricta: `s26_0169.xml` existe bajo `/2026/09/` y da 404 bajo `/2026/08/`.

3. **Cuerpo de una disposición:** `/bopv2/datos/{aaaa}/{mm}/{aa}{orden:05d}a.xml`, XML en UTF-8.
   El sumario **no publica la URL ni el identificador de cada disposición**, solo su
   `BOPVSumarioOrden`; el nombre del fichero se deriva de ahí. Verificado con órdenes altos y
   bajos (1 → `2400001a`, 18 → `2400018a`, 3788 → `2603788a`).

## La trampa que decide, y está medida

**Un día puede tener DOS ediciones.** Sondeados los 33 meses con datos entre enero de 2024 y
septiembre de 2026, cinco días traen dos: 2024-04-08, 2025-10-24, 2025-11-03, 2025-12-01 y
2026-05-04. Aproximadamente **uno cada siete meses**.

Quedarse con la primera —que es lo que sale solo si uno lee `enlaces[i]` como si fuera una
cadena y no una lista— **perdería un boletín extraordinario entero, en silencio**. Y un boletín
extraordinario es exactamente donde cae una disposición con prisa: es el caso que este proyecto
existe para no perder. Por eso `resolver_ediciones` devuelve una tupla y el worker recorre todas.

En los 33 meses, `diasHabilitados` y `enlaces` tienen **siempre la misma longitud**. Se comprueba
igual antes de emparejarlos: si algún día dejan de cuadrar, emparejar por posición asignaría a
cada fecha el boletín de otra, y eso sería archivar bajo el día equivocado.

## Dos particularidades del sumario

1. **Es plano.** `BOPVSumarioSeccion`, `BOPVSumarioSubseccion` y `BOPVSumarioOrganismo` son
   cabeceras de grupo que van sueltas entre los pares `BOPVSumarioTitulo`/`BOPVSumarioOrden`, no
   elementos que los contengan. Hay que arrastrar estado, como en el BOCYL (ADR 0029). **Y la
   subsección se reinicia al cambiar de sección**: hay secciones sin subsección, y sin ese
   reinicio heredarían la de la sección anterior.
2. **El título se consume y el orden lo cierra.** Un `BOPVSumarioTitulo` sin su
   `BOPVSumarioOrden` detrás no se archiva: sin el orden no hay cuerpo que pedir.

## Lo que NO trae

No hay equivalente del `<analisis>` del BOE: ni el sumario ni el cuerpo dicen a qué norma afecta
la disposición. El eje referencial (7.3) depende aquí de las citas del texto
(`pipeline/citas.py`, ADR 0022), igual que en el DOGC, el BOA, el BOCYL y el BOCM. Con seis
fuentes, **la estructura de referencias del BOE es oficialmente la excepción y no el estándar**.

Y el cuerpo **no declara su fecha de publicación**, así que no se puede contrastar como en el
BOCYL. Lo que sí declara es su `BOPVOrden`, y contra eso se comprueba: junto con la carpeta del
mes y el prefijo del año, cubre el caso de que la URL sirva otra cosa.
"""

from __future__ import annotations

import datetime
import logging
import re
from xml.etree.ElementTree import Element

import httpx

from app.ingest.boe import ItemSumario, Sumario, SumarioInvalido, SumarioNoDisponible
from app.security import url_guard, xml_safe

_BASE = "https://www.euskadi.eus"

# Tope de disposiciones por edición. Las medidas van de 18 a ~60; el tope existe porque el número
# lo decide la fuente y no nosotros, y sin él una respuesta anómala se convertiría en miles de
# descargas de cuerpo (6.2).
MAX_ITEMS_POR_EDICION = 400

# Tope de ediciones por día. Medido: el máximo observado en 33 meses es 2. El tope está para que
# un calendario manipulado o roto no dispare una tanda de descargas, y por eso es holgado pero
# finito.
MAX_EDICIONES_POR_DIA = 6

CABECERAS_CALENDARIO = {"Accept": "text/html"}
CABECERAS_SUMARIO = {"Accept": "application/xml"}
CABECERAS_TEXTO = {"Accept": "application/xml"}

logger = logging.getLogger(__name__)

_LONGITUD_MAXIMA_TITULO = 2000

# Los dos arrays del calendario. Se leen con expresión regular y **no** ejecutando el JavaScript:
# ejecutar código de una fuente externa sería justo lo contrario de la regla de oro 1.
_DIAS = re.compile(r"var\s+diasHabilitados\s*=\s*\[(?P<cuerpo>[^\]]*)\]\s*;")
_ENLACES = re.compile(r"var\s+enlaces\s*=\s*\[(?P<cuerpo>.*?)\]\s*;", re.DOTALL)
# Dentro de `enlaces`, cada día es a su vez una lista. Este es el punto donde se pierde el
# boletín extraordinario si uno lo lee como si fuera una cadena.
_GRUPO = re.compile(r"\[(?P<cuerpo>[^\]]*)\]")
# `s26_0169.shtml`. Solo esta forma: es lo que después se convierte en una URL (6.10).
_EDICION = re.compile(r"'(?P<edicion>s\d{2}_\d{4})\.shtml'")
_FECHA_CALENDARIO = re.compile(r"'(?P<fecha>\d{8})'")

_IDENTIFICADOR_NORMA = re.compile(r"\ABOPV-D-(\d{4})(\d{2})(\d{2})-(\d{1,6})\Z")


def url_calendario(fecha: datetime.date) -> str:
    """El calendario del mes al que pertenece la fecha. 1,5 KB, y es el índice de todo."""
    return f"{_BASE}/bopv2/datos/{fecha:%m%Y}.shtml"


def url_sumario(fecha: datetime.date, edicion: str) -> str:
    """El sumario de una edición. La carpeta del mes es estricta, comprobado."""
    if not _EDICION.fullmatch(f"'{edicion}.shtml'"):
        raise ValueError(f"Edición del BOPV mal formada: {edicion!r}")
    return f"{_BASE}/bopv2/datos/{fecha:%Y/%m}/{edicion}.xml"


def url_texto(fecha: datetime.date, orden: int) -> str:
    """El cuerpo de una disposición, derivado de su orden.

    El sumario no publica ni la URL ni el identificador de cada disposición: solo el orden. El
    nombre del fichero es `{aa}{orden:05d}a.xml`, verificado con órdenes de 1, 18 y 3788.
    """
    if not 1 <= orden <= 99999:
        raise ValueError(f"Orden del BOPV fuera de rango: {orden!r}")
    return f"{_BASE}/bopv2/datos/{fecha:%Y/%m}/{fecha:%y}{orden:05d}a.xml"


def identificador_norma(fecha: datetime.date, orden: int) -> str:
    """Identificador acuñado por nosotros, como en el BOCYL: la fuente no publica ninguno."""
    return f"BOPV-D-{fecha:%Y%m%d}-{orden}"


def descargar_calendario(fecha: datetime.date, *, client: httpx.Client | None = None) -> bytes:
    return url_guard.fetch(url_calendario(fecha), headers=CABECERAS_CALENDARIO, client=client)


def parsear_calendario(contenido: bytes, fecha: datetime.date) -> tuple[str, ...]:
    """Devuelve **todas** las ediciones publicadas ese día, en orden.

    Vacío no es un fallo: es cómo dice el BOPV que ese día no hubo boletín — la sexta manera
    distinta que se encuentra este proyecto, y la única que lo dice por adelantado para el mes
    entero en vez de al pedir el día.
    """
    # El calendario llega en ISO-8859-1 (lo declara su cabecera). Solo se leen de él dígitos y
    # nombres de fichero ASCII, así que los errores se sustituyen: un byte suelto mal codificado
    # en un texto que ni se archiva ni se cita no debe costar el día entero.
    texto = contenido.decode("iso-8859-1", errors="replace")

    dias_bruto = _DIAS.search(texto)
    enlaces_bruto = _ENLACES.search(texto)
    if dias_bruto is None or enlaces_bruto is None:
        raise SumarioInvalido(
            f"El calendario del BOPV de {fecha:%m/%Y} no tiene la forma esperada "
            f"({len(contenido)} bytes): faltan `diasHabilitados` o `enlaces`."
        )

    dias = _FECHA_CALENDARIO.findall(dias_bruto.group("cuerpo"))
    grupos = _GRUPO.findall(enlaces_bruto.group("cuerpo"))

    if len(dias) != len(grupos):
        # Emparejar por posición dos listas de distinta longitud asignaría a cada fecha el
        # boletín de otra. Se para: archivar bajo el día equivocado es peor que no archivar.
        raise SumarioInvalido(
            f"El calendario del BOPV de {fecha:%m/%Y} declara {len(dias)} días y "
            f"{len(grupos)} grupos de enlaces. No se emparejan por posición."
        )

    buscada = f"{fecha:%Y%m%d}"
    ediciones = tuple(
        edicion
        for dia, grupo in zip(dias, grupos, strict=True)
        if dia == buscada
        for edicion in _EDICION.findall(grupo)
    )

    if len(ediciones) > MAX_EDICIONES_POR_DIA:
        raise SumarioInvalido(
            f"El calendario del BOPV declara {len(ediciones)} ediciones el {fecha}, por encima "
            f"del tope de {MAX_EDICIONES_POR_DIA}. Puede ser una respuesta anómala."
        )
    if len(ediciones) > 1:
        # Medido: pasa ~1 vez cada 7 meses, y es donde cae un boletín extraordinario. Que se vea
        # en el log: si algún día alguien "simplifica" esto a una sola edición, esta línea es la
        # que dice cuánto se estaría perdiendo.
        logger.info("El BOPV publicó %s ediciones el %s: %s", len(ediciones), fecha, ediciones)
    return ediciones


def resolver_ediciones(
    fecha: datetime.date, *, client: httpx.Client | None = None
) -> tuple[str, ...]:
    """Fecha → ediciones de ese día. Una petición de 1,5 KB."""
    ediciones = parsear_calendario(descargar_calendario(fecha, client=client), fecha)
    if not ediciones:
        raise SumarioNoDisponible(
            f"El BOPV no publicó boletín el {fecha}: no está en el calendario de {fecha:%m/%Y}."
        )
    return ediciones


def descargar_sumario(
    fecha: datetime.date, edicion: str, *, client: httpx.Client | None = None
) -> bytes:
    """Descarga el sumario de una edición. Devuelve los bytes crudos, sin tocar.

    Crudos a propósito: el `sha256` del archivo íntegro (6.5) tiene que calcularse sobre
    exactamente lo que envió el servidor.
    """
    return url_guard.fetch(url_sumario(fecha, edicion), headers=CABECERAS_SUMARIO, client=client)


def parsear_sumario(contenido: bytes, fecha: datetime.date, edicion: str) -> Sumario:
    """Lee el sumario de una edición del BOPV.

    **No se puede contrastar la fecha contra el contenido**, porque el sumario no la declara: la
    garantía de que este documento es el del día pedido la da el calendario, que es quien
    empareja fecha y edición. Es una petición más y es lo que hace archivable esta fuente.
    """
    raiz = xml_safe.parse(contenido)

    seccion = subseccion = organismo = titulo = ""
    items: list[ItemSumario] = []
    ordenes: set[int] = set()

    for nodo in raiz:
        valor = (nodo.text or "").strip()
        if nodo.tag == "BOPVSumarioSeccion":
            seccion = valor
            # La subsección es de grupo dentro de la sección, y hay secciones que no la traen.
            # Sin este reinicio, «OTRAS DISPOSICIONES» heredaría la subsección de la anterior.
            subseccion = ""
            titulo = ""
            continue
        if nodo.tag == "BOPVSumarioSubseccion":
            subseccion = valor
            titulo = ""
            continue
        if nodo.tag == "BOPVSumarioOrganismo":
            organismo = valor
            titulo = ""
            continue
        if nodo.tag == "BOPVSumarioTitulo":
            titulo = valor
            continue
        if nodo.tag != "BOPVSumarioOrden":
            continue

        if not titulo:
            # Un orden sin su título delante: no se inventa uno. Se dice y no se vigila, igual
            # que en el BOCYL, porque archivar una norma con el título de otra es peor.
            logger.warning(
                "El sumario del BOPV %s trae el orden %r sin título delante: NO se vigila.",
                edicion,
                valor,
            )
            continue
        try:
            orden = int(valor)
        except ValueError:
            raise SumarioInvalido(f"Orden no numérico en el sumario {edicion}: {valor!r}") from None
        if not 1 <= orden <= 99999:
            raise SumarioInvalido(f"Orden fuera de rango en el sumario {edicion}: {orden}")
        if orden in ordenes:
            raise SumarioInvalido(f"El sumario {edicion} repite el orden {orden}")

        ordenes.add(orden)
        # El título se consume; sección, subsección y organismo se arrastran. Misma asimetría que
        # en el BOCYL y por el mismo motivo: unos son cabeceras de grupo y el otro es de una sola
        # disposición.
        suyo, titulo = titulo, ""
        items.append(
            ItemSumario(
                identificador=identificador_norma(fecha, orden),
                titulo=suyo[:_LONGITUD_MAXIMA_TITULO],
                url_xml=url_texto(fecha, orden),
                url_pdf=None,
                seccion_codigo="",
                seccion_nombre=seccion,
                departamento=organismo or "BOPV",
                epigrafe=subseccion or None,
            )
        )

    if len(items) > MAX_ITEMS_POR_EDICION:
        # No se trunca en silencio: lo que faltara sería invisible (mismo criterio que el ADR
        # 0020 y que el resto de fuentes).
        raise SumarioInvalido(
            f"El sumario {edicion} del BOPV trae {len(items)} disposiciones, por encima del tope "
            f"de {MAX_ITEMS_POR_EDICION}. Puede ser una respuesta anómala y no se ingiere."
        )
    if not items:
        # A diferencia del BOCYL, aquí un sumario vacío **no** es un día sin boletín: el
        # calendario ya ha dicho que ese día hubo edición. Si además llega vacía, algo no cuadra.
        raise SumarioInvalido(f"El sumario {edicion} del BOPV no contiene ninguna disposición")

    return Sumario(
        # La edición va dentro del identificador: sin ella, los dos boletines de un día con
        # edición extraordinaria colisionarían y el segundo se daría por ya ingerido.
        identificador=f"BOPV-S-{fecha:%Y%m%d}-{edicion.split('_')[1]}",
        fecha_publicacion=fecha,
        numero_diario=edicion.split("_")[1].lstrip("0"),
        items=tuple(items),
    )


def parsear_cuerpo(contenido: bytes, identificador_esperado: str) -> Element:
    """Valida que el cuerpo descargado es el de la disposición que se pidió, y lo devuelve.

    El cuerpo del BOPV **no declara su fecha de publicación**, así que no se puede contrastar como
    en el BOCYL (ADR 0029). Lo que sí declara es su `BOPVOrden`, y eso —junto con la carpeta del
    mes y el prefijo del año, que van en la URL— cubre el caso que importa: que la fuente sirva
    otra cosa bajo la misma dirección.
    """
    encontrado = _IDENTIFICADOR_NORMA.fullmatch(identificador_esperado)
    if encontrado is None:
        raise SumarioInvalido(f"Identificador mal formado: {identificador_esperado!r}")

    raiz = xml_safe.parse(contenido)
    declarado = (raiz.findtext("./BOPVOrden") or "").strip()
    esperado = encontrado.group(4)
    if declarado != esperado:
        raise SumarioInvalido(
            f"Se pidió el cuerpo de {identificador_esperado} (orden {esperado}) y el XML dice "
            f"ser el orden {declarado or 'sin orden'}. No se archiva."
        )
    return raiz


__all__ = [
    "CABECERAS_CALENDARIO",
    "CABECERAS_SUMARIO",
    "CABECERAS_TEXTO",
    "MAX_EDICIONES_POR_DIA",
    "MAX_ITEMS_POR_EDICION",
    "SumarioInvalido",
    "SumarioNoDisponible",
    "descargar_calendario",
    "descargar_sumario",
    "identificador_norma",
    "parsear_calendario",
    "parsear_cuerpo",
    "parsear_sumario",
    "resolver_ediciones",
    "url_calendario",
    "url_sumario",
    "url_texto",
]
