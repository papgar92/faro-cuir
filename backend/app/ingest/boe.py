"""Ingesta del BOE: descarga y lectura del sumario diario.

Fuente verificada en `docs/fuentes.md`: API abierta, sin autenticación, que devuelve el
sumario de un día en XML. Estructura real (comprobada contra el sumario del 2024-12-19, no
deducida de la documentación):

```
response
├── status/code, status/text
└── data/sumario
    ├── metadatos/publicacion, fecha_publicacion
    └── diario @numero
        ├── sumario_diario/identificador, url_pdf
        └── seccion @codigo,nombre
            └── departamento @codigo,nombre
                ├── item                      ← unos cuelgan directos del departamento
                └── epigrafe @nombre
                    └── item                  ← y otros de un epígrafe intermedio
```

Ese doble encaje del `item` es el detalle fácil de pasar por alto: recorrer solo
`departamento/item` se deja fuera casi la mitad de las disposiciones de un día.

Este módulo **no toca la base de datos ni el disco**: descarga, valida y devuelve
estructuras. Persistir es cosa de `services/ingesta.py`. Separarlo permite testear el
parseo con un sumario real guardado como fixture, sin red y sin Postgres.

Todo lo que entra aquí es dato hostil (regla de oro 1): la descarga pasa por
`security/url_guard` y el parseo por `security/xml_safe`, sin excepción.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from xml.etree.ElementTree import Element

import httpx

from app.security import url_guard, xml_safe

# La fuente se identifica por su URL de sumario diario. Ver docs/fuentes.md.
PLANTILLA_URL_SUMARIO = "https://www.boe.es/datosabiertos/api/boe/sumario/{fecha}"

# Los identificadores del BOE que hemos observado tienen forma BOE-A-2024-26484 /
# BOE-S-2024-305. En vez de fijar ese patrón exacto —que sería afirmar algo sobre el formato
# del BOE que no hemos verificado para todos los casos— se comprueba solo que el valor sea un
# identificador plausible: caracteres seguros y longitud acotada. Es una defensa contra lo
# que ese texto podría acabar haciendo (inyección en consultas, nombres de fichero, logs), no
# una validación del formato oficial.
_IDENTIFICADOR_SEGURO = re.compile(r"\A[A-Za-z0-9._-]{1,200}\Z")

_LONGITUD_MAXIMA_TITULO = 2000
_LONGITUD_MAXIMA_URL = 1000


class BoeIngestError(Exception):
    """Algo del sumario no es utilizable. Nunca se rellena a ojo lo que falte."""


class SumarioNoDisponible(BoeIngestError):
    """El BOE responde pero no hay sumario para esa fecha (p. ej. domingos)."""


class SumarioInvalido(BoeIngestError):
    """El sumario llega, pero no tiene la forma que este módulo sabe leer."""


@dataclass(frozen=True)
class ItemSumario:
    """Una entrada del sumario: una disposición publicada ese día."""

    identificador: str
    titulo: str
    url_xml: str
    url_pdf: str | None
    seccion_codigo: str
    seccion_nombre: str
    departamento: str
    epigrafe: str | None


@dataclass(frozen=True)
class Sumario:
    identificador: str
    fecha_publicacion: datetime.date
    numero_diario: str
    items: tuple[ItemSumario, ...]


def url_sumario(fecha: datetime.date) -> str:
    return PLANTILLA_URL_SUMARIO.format(fecha=fecha.strftime("%Y%m%d"))


def descargar_sumario(fecha: datetime.date, *, client: httpx.Client | None = None) -> bytes:
    """Descarga el sumario de un día. Devuelve los bytes crudos, sin tocar.

    Se devuelven crudos a propósito: el sha256 del archivo íntegro (CLAUDE.md 6.5) tiene que
    calcularse sobre exactamente lo que envió el servidor. Cualquier normalización previa
    haría que el hash probara lo que entendimos nosotros en vez de lo que se publicó.
    """
    # La API del BOE responde 400 a un `Accept: */*` (el que pone httpx por defecto) y exige
    # que se le pida un tipo concreto. Comprobado contra el servicio real, no documentado.
    try:
        return url_guard.fetch(
            url_sumario(fecha), headers={"Accept": "application/xml"}, client=client
        )
    except httpx.HTTPStatusError as exc:
        # Los días sin boletín (domingos y algunos festivos) devuelven 404. No es un fallo del
        # sistema y no debe tratarse como tal: si lo fuera, el cron avisaría de un error todos
        # los domingos y esa alarma acabaría ignorándose — que es como se pierden las de verdad.
        if exc.response.status_code == 404:
            raise SumarioNoDisponible(f"El BOE no publicó sumario el {fecha}") from exc
        raise


def _texto_obligatorio(padre: Element, ruta: str, contexto: str) -> str:
    valor = padre.findtext(ruta)
    if valor is None or not valor.strip():
        raise SumarioInvalido(f"Falta {ruta!r} en {contexto}")
    return valor.strip()


def _identificador_valido(valor: str, contexto: str) -> str:
    if not _IDENTIFICADOR_SEGURO.fullmatch(valor):
        raise SumarioInvalido(f"Identificador con caracteres inesperados en {contexto}: {valor!r}")
    return valor


def _acotar(valor: str, maximo: int) -> str:
    """Recorta texto libre de la fuente a una longitud sensata.

    El título sí se recorta (a diferencia del identificador, que se rechaza): un título largo
    es plausible y no queremos tirar un documento por eso, pero tampoco aceptar un campo de
    texto ilimitado que va a acabar en base de datos y en un prompt de LLM.
    """
    return valor[:maximo]


def _leer_item(
    elemento: Element,
    *,
    seccion_codigo: str,
    seccion_nombre: str,
    departamento: str,
    epigrafe: str | None,
) -> ItemSumario:
    identificador = _identificador_valido(
        _texto_obligatorio(elemento, "identificador", "un item del sumario"), "un item del sumario"
    )
    return ItemSumario(
        identificador=identificador,
        titulo=_acotar(
            _texto_obligatorio(elemento, "titulo", f"el item {identificador}"),
            _LONGITUD_MAXIMA_TITULO,
        ),
        url_xml=_acotar(
            _texto_obligatorio(elemento, "url_xml", f"el item {identificador}"),
            _LONGITUD_MAXIMA_URL,
        ),
        url_pdf=_acotar(elemento.findtext("url_pdf", "").strip(), _LONGITUD_MAXIMA_URL) or None,
        seccion_codigo=seccion_codigo,
        seccion_nombre=seccion_nombre,
        departamento=departamento,
        epigrafe=epigrafe,
    )


def parsear_sumario(contenido: bytes, *, fecha_esperada: datetime.date | None = None) -> Sumario:
    """Lee un sumario del BOE ya descargado.

    `fecha_esperada`, si se pasa, se contrasta con la que declara el propio sumario. Pedir el
    día X y archivar el contenido del día Y corrompería el archivo de la sección 6.5 de una
    forma que además sería muy difícil de detectar después.
    """
    raiz = xml_safe.parse(contenido)

    codigo = raiz.findtext("./status/code", "").strip()
    if codigo != "200":
        texto = raiz.findtext("./status/text", "").strip()
        raise SumarioNoDisponible(f"El BOE responde con status {codigo!r} ({texto!r})")

    sumario = raiz.find("./data/sumario")
    if sumario is None:
        raise SumarioInvalido("La respuesta no contiene data/sumario")

    fecha_cruda = _texto_obligatorio(sumario, "./metadatos/fecha_publicacion", "los metadatos")
    try:
        fecha = datetime.datetime.strptime(fecha_cruda, "%Y%m%d").date()
    except ValueError as exc:
        raise SumarioInvalido(f"Fecha de publicación ilegible: {fecha_cruda!r}") from exc

    if fecha_esperada is not None and fecha != fecha_esperada:
        raise SumarioInvalido(
            f"Se pidió el sumario del {fecha_esperada} y el contenido dice ser del {fecha}"
        )

    diario = sumario.find("./diario")
    if diario is None:
        raise SumarioInvalido("El sumario no contiene ningún diario")

    identificador = _identificador_valido(
        _texto_obligatorio(diario, "./sumario_diario/identificador", "el diario"), "el diario"
    )

    items: list[ItemSumario] = []
    for seccion in diario.findall("./seccion"):
        seccion_codigo = seccion.get("codigo", "")
        seccion_nombre = seccion.get("nombre", "")
        for departamento in seccion.findall("./departamento"):
            nombre_departamento = departamento.get("nombre", "")
            # Los dos encajes posibles del item, explícitos para que se vea que no se olvida
            # ninguno: directo bajo el departamento, y bajo un epígrafe intermedio.
            for elemento in departamento.findall("./item"):
                items.append(
                    _leer_item(
                        elemento,
                        seccion_codigo=seccion_codigo,
                        seccion_nombre=seccion_nombre,
                        departamento=nombre_departamento,
                        epigrafe=None,
                    )
                )
            for epigrafe in departamento.findall("./epigrafe"):
                for elemento in epigrafe.findall("./item"):
                    items.append(
                        _leer_item(
                            elemento,
                            seccion_codigo=seccion_codigo,
                            seccion_nombre=seccion_nombre,
                            departamento=nombre_departamento,
                            epigrafe=epigrafe.get("nombre"),
                        )
                    )

    if not items:
        raise SumarioInvalido("El sumario no contiene ningún item")

    return Sumario(
        identificador=identificador,
        fecha_publicacion=fecha,
        numero_diario=diario.get("numero", ""),
        items=tuple(items),
    )
