"""Ingesta del BOA (Boletín Oficial de Aragón). ADR 0028.

**Tercera fuente del proyecto y segunda autonómica.** Entra por un motivo concreto que la
distingue de la anterior: el DOGC publica solo **disposiciones generales** —leyes, decretos y
órdenes— y el ADR 0019 dejó escrito que sus **resoluciones e instrucciones no están, y son un
vector de retroceso real**. El BOA sí las trae. En el día verificado (2024-01-10) sus 38
disposiciones se reparten así:

| sección | items |
|---|---|
| I. Disposiciones Generales | 1 |
| II. Autoridades y Personal | 10 |
| III. Otras Disposiciones y Acuerdos | 16 |
| V. Anuncios | 11 |

y por rango, **15 de 38 son resoluciones**. O sea que esta fuente cubre justo el hueco que la
anterior dejaba abierto, y no solo suma una comunidad al mapa.

## De dónde sale cada cosa, verificado descargando, no leyendo documentación

El BOA corre sobre BRSCGI, el buscador documental del Gobierno de Aragón. La pieza que hace
esto viable es que **acepta `OUTPUTMODE=XML` sobre una sección de datos abiertos**
(`SEC=OPENDATABOAXML`), y ese endpoint devuelve, en la misma respuesta y para una fecha exacta:
metadatos de sumario **y el texto íntegro** de cada disposición.

- **Sumario de un día:** `DOCS=1-N&PUBL=YYYYMMDD`. Un día normal son ~38 registros y ~380 KB.
- **Cuerpo de una disposición:** `DOCS=n-n&PUBL=YYYYMMDD`, o sea la misma consulta acotada a un
  registro. Es una URL real de la fuente, así que la fase 2 archiva **los bytes que envió el
  servidor** y su `sha256` prueba lo que se publicó, no lo que entendimos nosotros (6.5).

## La particularidad que gobierna este módulo: no hay forma de pedir un documento por su id

BRSCGI no expone el número de control (`<docn>`) como campo consultable —probados `DOCN`,
`DOCN-C` y `TEXT`, los tres devuelven cero registros—. **La única forma de direccionar una
disposición suelta es su posición ordinal dentro del día.** Eso es una dirección frágil por
naturaleza: depende de que la fuente ordene igual el mismo conjunto dos veces.

**No se confía en ella: se comprueba.** `parsear_cuerpo` exige que el `<docn>` que vuelve sea
el que se esperaba y, si no coincide, levanta `SumarioInvalido` y la norma se queda sin cuerpo.
Sin fila, vuelve sola a la cola de la fase 2, que es la vía de fallo normal del proyecto. La
alternativa —archivar lo que llegue— pondría el texto de una norma bajo el identificador de
otra, y eso es exactamente la corrupción de archivo silenciosa que la 6.5 existe para impedir.

## Dos cosas más que hay que saber antes de tocar esto

1. **El XML declara `ISO-8859-1`**, no UTF-8. No se toca: `xml_safe.parse` lo resuelve por el
   prólogo del propio documento, y los bytes que se archivan y se hashean son los crudos.
2. **No hay equivalente del `<analisis>` del BOE.** El registro no dice a qué norma afecta, así
   que el eje referencial (7.3) depende aquí de las citas del texto (`pipeline/citas.py`, ADR
   0022) exactamente igual que en el DOGC. La estructura de referencias es una particularidad
   del BOE, no un estándar, y darla por hecha deja el eje 2 apagado en silencio.
"""

from __future__ import annotations

import datetime
import logging
import re
from xml.etree.ElementTree import Element

import httpx

from app.ingest.boe import ItemSumario, Sumario, SumarioInvalido, SumarioNoDisponible
from app.security import url_guard, xml_safe

# Endpoint de datos abiertos del BOA. `SEC` elige la plantilla de salida y es lo que hace que
# esto devuelva XML estructurado en vez del HTML del diario; `OUTPUTMODE=XML` sin la sección
# correcta se ignora (comprobado: `SEC=OPENDATASUMARIO&OUTPUTMODE=JSON` sigue devolviendo HTML).
_BASE = "https://www.boa.aragon.es/cgi-bin/EBOA/BRSCGI"

# Tope de disposiciones por día. Un día normal trae del orden de 40. El tope existe porque el
# número de registros lo decide la fuente y no nosotros, y sin él una respuesta anómala se
# convertiría en miles de descargas de cuerpo (6.2).
MAX_ITEMS_POR_DIA = 200

CABECERAS = {"Accept": "application/xml"}

logger = logging.getLogger(__name__)

# El número de control del BOA. Nueve dígitos en todo lo verificado; se valida antes de
# componer nada con él porque viene de una fuente externa (6.10).
_PATRON_CONTROL = re.compile(r"^\d{6,12}$")

_LONGITUD_MAXIMA_TITULO = 2000

# **Un día sin boletín no da 404 ni una lista vacía: BRSCGI sirve la portada del diario.**
# HTTP 200, `<!DOCTYPE html>`, 8.127 bytes idénticos en los dos días verificados (2026-08-01 y
# 2026-08-02, sábado y domingo). Un día con boletín empieza siempre por el prólogo XML.
#
# Hay que reconocerlo **antes** de tocar el parser: si el HTML llega a `xml_safe`, salta
# `DtdForbidden` —correctamente, un DOCTYPE es la vía de entrada de XXE— el worker lo trata como
# fallo de control de seguridad y **aborta la tanda entera**. Cada fin de semana mataría un
# bloque de backfill. Que se reconozca aquí no relaja `xml_safe` en nada: este HTML no se
# parsea, se rechaza.
_PROLOGO_XML = b"<?xml"


def url_sumario(fecha: datetime.date) -> str:
    """Consulta del día entero. El filtro por fecha lo hace la fuente, no nosotros.

    Así la petición es idempotente y reproducible: dos ejecuciones del mismo día piden
    literalmente lo mismo, y el `sha256` de las dos respuestas es comparable.
    """
    return (
        f"{_BASE}?CMD=VERLST&OUTPUTMODE=XML&BASE=BOLE"
        f"&DOCS=1-{MAX_ITEMS_POR_DIA}&SEC=OPENDATABOAXML&SEPARADOR="
        f"&PUBL={fecha.strftime('%Y%m%d')}"
    )


def url_texto(fecha: datetime.date, posicion: int) -> str:
    """La misma consulta acotada a un registro. Ver la nota sobre direccionar por posición.

    `posicion` es 1-based, como el propio BRSCGI. No se compone con nada que venga de la
    fuente: sale de enumerar los registros que ya hemos parseado.
    """
    if posicion < 1:
        raise ValueError(f"Posición de registro inválida: {posicion!r}")
    return (
        f"{_BASE}?CMD=VERLST&OUTPUTMODE=XML&BASE=BOLE"
        f"&DOCS={posicion}-{posicion}&SEC=OPENDATABOAXML&SEPARADOR="
        f"&PUBL={fecha.strftime('%Y%m%d')}"
    )


def descargar_sumario(fecha: datetime.date, *, client: httpx.Client | None = None) -> bytes:
    """Descarga el sumario de un día. Devuelve los bytes crudos, sin tocar.

    Crudos a propósito: el `sha256` del archivo íntegro (6.5) tiene que calcularse sobre
    exactamente lo que envió el servidor.
    """
    return url_guard.fetch(url_sumario(fecha), headers=CABECERAS, client=client)


def _texto(registro: Element, etiqueta: str) -> str:
    valor = registro.findtext(etiqueta)
    return valor.strip() if valor else ""


def _registros(contenido: bytes, contexto: str) -> list[Element]:
    raiz = xml_safe.parse(contenido)
    registros = raiz.findall("./registro")
    if not registros:
        raise SumarioInvalido(f"La respuesta del BOA para {contexto} no trae ningún <registro>")
    return registros


def parsear_sumario(contenido: bytes, fecha: datetime.date) -> Sumario:
    """Lee un sumario del BOA ya descargado.

    La fecha se contrasta registro a registro con la que declara la propia fuente: pedir el día
    X y archivar el del día Y corrompería el archivo de la 6.5 de una forma difícil de detectar
    después. Un registro cuya fecha no cuadre no se corrige, se descarta y se dice.
    """
    if not contenido.lstrip().startswith(_PROLOGO_XML):
        # Mismo criterio que el 404 del BOE y la lista vacía del DOGC: es una respuesta válida
        # del mundo, no un fallo del sistema. El mensaje lleva el tamaño a propósito — si esto
        # apareciera muchos días seguidos no sería el calendario, sería la fuente rota, y quien
        # mire el log tiene que poder distinguirlo sin ir a comprobarlo a mano.
        raise SumarioNoDisponible(
            f"El BOA no publicó boletín el {fecha}: la fuente responde 200 con la portada del "
            f"diario ({len(contenido)} bytes, HTML) en vez del XML de datos abiertos."
        )

    esperada = fecha.strftime("%Y%m%d")
    registros = _registros(contenido, f"el sumario del {fecha}")

    if len(registros) >= MAX_ITEMS_POR_DIA:
        # No se trunca en silencio: si un día llegara al tope, lo que falta es invisible y eso
        # es justo el fallo que este proyecto no se permite (ADR 0020, mismo criterio).
        raise SumarioInvalido(
            f"El sumario del BOA del {fecha} trae {len(registros)} registros, el tope de "
            f"MAX_ITEMS_POR_DIA. Puede estar recortado y no se ingiere a medias."
        )

    items: list[ItemSumario] = []
    descartadas = 0
    numero_diario = ""

    for posicion, registro in enumerate(registros, start=1):
        control = _texto(registro, "docn")
        fecha_registro = _texto(registro, "fecha")
        titulo = _texto(registro, "titulo")

        if not _PATRON_CONTROL.match(control) or fecha_registro != esperada or not titulo:
            logger.warning(
                "Registro %s del BOA del %s descartado (control=%r, fecha=%r, con título=%s): "
                "esa disposición NO se vigila.",
                posicion,
                fecha,
                control or "sin número de control",
                fecha_registro or "sin fecha",
                bool(titulo),
            )
            descartadas += 1
            continue

        numero_diario = numero_diario or _texto(registro, "numeroboletin")
        items.append(
            ItemSumario(
                # Prefijo propio y número de control de la fuente. Nunca se usa para componer
                # una ruta de fichero (6.3: las rutas salen del sha256).
                identificador=f"BOA-{control}",
                titulo=titulo[:_LONGITUD_MAXIMA_TITULO],
                # La posición dentro del día es la única dirección que ofrece la fuente. Que sea
                # frágil se resuelve comprobando el `<docn>` al parsear el cuerpo, no confiando.
                url_xml=url_texto(fecha, posicion),
                # El `<url>` del registro trae solo objetos PDF firmados, no el texto. Se deja a
                # None en vez de apuntar a algo que no es el cuerpo.
                url_pdf=None,
                seccion_codigo="",
                seccion_nombre=_texto(registro, "seccion"),
                departamento=_texto(registro, "emisor") or "BOA",
                # El rango es lo que de verdad clasifica una disposición aquí. Va al epígrafe en
                # vez de inventar una sección que la fuente no numera.
                epigrafe=_texto(registro, "rango") or None,
            )
        )

    if not items:
        raise SumarioInvalido(
            f"El sumario del BOA del {fecha} trae {len(registros)} registros y ninguno "
            "utilizable (sin número de control válido, sin título o con otra fecha)."
        )

    if descartadas:
        logger.warning(
            "Sumario del BOA del %s: %s de %s disposiciones quedan fuera de la vigilancia.",
            fecha,
            descartadas,
            len(registros),
        )

    return Sumario(
        identificador=f"BOA-S-{fecha.isoformat()}",
        fecha_publicacion=fecha,
        numero_diario=numero_diario,
        items=tuple(items),
    )


def parsear_cuerpo(contenido: bytes, identificador_esperado: str) -> Element:
    """Valida que el cuerpo descargado es el de la norma que se pidió, y lo devuelve.

    **Este es el control que sostiene el direccionamiento por posición** del que habla la
    cabecera del módulo. La fuente no permite pedir «el documento 007938287»: solo «el registro
    número 12 del día 10/01/2024». Si esa posición dejara de significar lo mismo —porque la
    fuente reordene, añada o retire un registro de un día pasado— archivaríamos el texto de una
    norma bajo el identificador de otra.

    Comprobarlo es barato: el registro trae su propio `<docn>`. Se compara y, si no cuadra, se
    levanta y la norma se queda sin cuerpo, que la devuelve sola a la cola de la fase 2.
    """
    if not contenido.lstrip().startswith(_PROLOGO_XML):
        # Aquí sí es inválido y no "no hay boletín": se pidió un registro concreto de un día que
        # ya sabemos que existe, porque su sumario se parseó. Sigue la vía de fallo de la fase 2
        # —sin fila, la norma vuelve sola a la cola— en vez de reventar la tanda.
        raise SumarioInvalido(
            f"Se pidió el cuerpo de {identificador_esperado} y la fuente devolvió "
            f"{len(contenido)} bytes que no son XML."
        )

    registros = _registros(contenido, f"el cuerpo de {identificador_esperado}")
    if len(registros) != 1:
        raise SumarioInvalido(
            f"Se pidió el cuerpo de {identificador_esperado} y llegaron {len(registros)} "
            "registros; se esperaba exactamente uno."
        )

    registro = registros[0]
    control = _texto(registro, "docn")
    if f"BOA-{control}" != identificador_esperado:
        raise SumarioInvalido(
            f"Se pidió el cuerpo de {identificador_esperado} y la fuente devolvió "
            f"BOA-{control or 'sin número de control'}. La posición del registro dentro del día "
            "ha dejado de significar lo mismo: no se archiva."
        )
    return registro


__all__ = [
    "CABECERAS",
    "MAX_ITEMS_POR_DIA",
    "SumarioInvalido",
    "SumarioNoDisponible",
    "descargar_sumario",
    "parsear_cuerpo",
    "parsear_sumario",
    "url_sumario",
    "url_texto",
]
