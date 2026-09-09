"""Ingesta del BOCM (Boletín Oficial de la Comunidad de Madrid). ADR 0034.

**Quinta fuente del proyecto y cuarta autonómica.** Y la más barata desde el BOE, por un motivo
que conviene decir antes que nada: **su sumario diario se direcciona por la fecha y nada más**, y
su cuerpo tiene *la misma forma que el del BOE* —`documento > metadatos, analisis, texto`—, así
que `pipeline/texto.texto_plano` ya sabía leerlo sin tocar una línea.

## De dónde sale cada cosa, verificado descargando (2026-09-06)

- **Sumario de un día:** `CM_Boletin_BOCM/AAAA/MM/DD/BOCM-AAAAMMDD.xml`, XML **sin prólogo**, con
  `metadatos` y un árbol `secciones > seccion > apartado > organismo > disposicion`. Cada
  disposición trae `identificador`, `rango`, `titulo` y sus URLs (`url_xml`, `url_pdf`, …).
- **Cuerpo de una disposición:** el `url_xml` que declara el propio sumario, direccionado **por
  identificador**: `CM_Orden_BOCM/AAAA/MM/DD/BOCM-AAAAMMDD-N.xml`.
- **Día sin boletín: 404**, igual que el BOE. La primera pregunta que hay que hacerle a una
  fuente nueva (ADR 0029) y aquí la respuesta es la cómoda.

## Las dos trampas, y la segunda envenena el archivo en silencio

1. **El sumario repite la lista entera, en triángulo.** El día 2026-09-04 trae **2.701
   elementos `<disposicion>` para 73 disposiciones reales**: la primera aparece 73 veces, la
   segunda 72, la tercera 71… (73·74/2 = 2.701 exactamente). Por eso el fichero pesa 2,9 MB en
   vez de ~80 KB. Contar `<disposicion>` da 37 veces el número real, y sin deduplicar la fase 2
   pediría 2.701 cuerpos en lugar de 73. **Las copias son idénticas** —mismo identificador, mismo
   título, misma sección—, comprobado, así que deduplicar por identificador es seguro.

2. **`<fecha_publicacion>` de los metadatos NO es la fecha de publicación**, es la del día
   anterior. Verificado en tres días seguidos: `BOCM-20260904` declara `2026/09/03`,
   `BOCM-20260903` declara `2026/09/02` y `BOCM-20260901` declara `2026/08/31`. Es la fecha de
   cierre de la edición, no la de la portada. **Validar contra ella habría rechazado todos los
   días, o peor: archivado cada boletín bajo el día anterior**, y la afirmación de la 6.5 —«el
   día X esto decía exactamente esto»— habría quedado desplazada un día para toda la fuente sin
   que fallara nada visiblemente. Lo que sí cuadra con la fecha pedida es `<identificador>`
   (`BOCM-AAAAMMDD`), y es contra eso contra lo que se comprueba.

## Lo que NO trae

El cuerpo tiene un bloque `<analisis>`, pero **no es el `<analisis>` del BOE**: aquí solo lleva
`seccion`, `apartado`, `organismo` y `tipo_disposicion`. No dice a qué norma afecta la
disposición. El eje referencial (7.3) depende aquí de las citas del texto (`pipeline/citas.py`,
ADR 0022), igual que en el DOGC, el BOA y el BOCYL. **La estructura de referencias sigue siendo
una particularidad del BOE, no un estándar.**

## Por qué esta fuente vale más de lo que parece

Madrid es **uniprovincial y no tiene BOP** (`docs/fuentes.md`): sus ayuntamientos publican sus
ordenanzas aquí. Integrar el BOCM mete por primera vez en el sistema el **nivel local** de la
sección 1, que llevaba 0 de 43 fuentes. La sección `III. ADMINISTRACIÓN LOCAL AYUNTAMIENTOS` del
sumario es exactamente eso.
"""

from __future__ import annotations

import datetime
import re
from xml.etree.ElementTree import Element

import httpx

from app.ingest.boe import ItemSumario, Sumario, SumarioInvalido, SumarioNoDisponible
from app.security import url_guard, xml_safe

_BASE = "https://www.bocm.es"

# Tope de disposiciones por día. Los días medidos traen entre 51 y 73; el tope existe porque el
# número lo decide la fuente y no nosotros, y sin él una respuesta anómala se convertiría en
# miles de descargas de cuerpo (6.2). Se compara con el recuento YA deduplicado: contar antes de
# deduplicar dispararía el tope cualquier día normal, por la trampa 1.
MAX_ITEMS_POR_DIA = 400

CABECERAS_SUMARIO = {"Accept": "application/xml"}
CABECERAS_TEXTO = {"Accept": "application/xml"}

_LONGITUD_MAXIMA_TITULO = 2000
_LONGITUD_MAXIMA_URL = 1000

# `BOCM-20260904-1`. El identificador se valida antes de usarse para nada (6.10), y aquí además
# sirve para comprobar que el cuerpo que llega es el que se pidió.
_IDENTIFICADOR = re.compile(r"\ABOCM-(\d{4})(\d{2})(\d{2})-(\d{1,6})\Z")
_IDENTIFICADOR_SUMARIO = re.compile(r"\ABOCM-(\d{4})(\d{2})(\d{2})\Z")


def url_sumario(fecha: datetime.date) -> str:
    """El sumario de un día, direccionado **solo por la fecha**.

    Sin número de edición, que es lo que obliga a resolver a casi todas las demás candidatas
    (`docs/fuentes.md`). La carpeta y el nombre repiten la misma fecha; la fuente también sirve
    el mismo documento bajo la carpeta del día anterior, pero se pide por el día de portada
    porque es el que va a acabar en el archivo.
    """
    return f"{_BASE}/boletin/CM_Boletin_BOCM/{fecha:%Y/%m/%d}/BOCM-{fecha:%Y%m%d}.xml"


def descargar_sumario(fecha: datetime.date, *, client: httpx.Client | None = None) -> bytes:
    """Descarga el sumario de un día. Devuelve los bytes crudos, sin tocar.

    Crudos a propósito: el `sha256` del archivo íntegro (6.5) tiene que calcularse sobre
    exactamente lo que envió el servidor.
    """
    try:
        return url_guard.fetch(url_sumario(fecha), headers=CABECERAS_SUMARIO, client=client)
    except httpx.HTTPStatusError as exc:
        # Igual que el BOE: los días sin boletín dan 404 y eso no es un fallo del sistema.
        # Verificado con el domingo 2026-09-06.
        if exc.response.status_code == 404:
            raise SumarioNoDisponible(f"El BOCM no publicó boletín el {fecha}") from exc
        raise


def _texto(elemento: Element, ruta: str, contexto: str) -> str:
    valor = elemento.findtext(ruta)
    if valor is None or not valor.strip():
        raise SumarioInvalido(f"Falta {ruta!r} en {contexto}")
    return valor.strip()


def parsear_sumario(contenido: bytes, fecha: datetime.date) -> Sumario:
    """Lee un sumario del BOCM ya descargado.

    Dos cosas que no son detalle de implementación y están explicadas arriba: se deduplica por
    identificador (trampa 1) y se contrasta la fecha contra `<identificador>` y **nunca** contra
    `<fecha_publicacion>` (trampa 2).
    """
    raiz = xml_safe.parse(contenido)

    metadatos = raiz.find("./metadatos")
    if metadatos is None:
        raise SumarioInvalido("El sumario del BOCM no contiene metadatos")

    identificador = _texto(metadatos, "identificador", "los metadatos")
    encontrado = _IDENTIFICADOR_SUMARIO.fullmatch(identificador)
    if encontrado is None:
        raise SumarioInvalido(f"Identificador de sumario inesperado: {identificador!r}")

    anyo, mes, dia = encontrado.groups()
    declarada = datetime.date(int(anyo), int(mes), int(dia))
    if declarada != fecha:
        # Pedir el día X y archivar el del día Y corrompería el archivo de la 6.5 de una forma
        # muy difícil de detectar después (mismo criterio que en `boe.parsear_sumario`).
        raise SumarioInvalido(
            f"Se pidió el sumario del BOCM del {fecha} y el contenido dice ser {identificador}"
        )

    items: list[ItemSumario] = []
    vistos: set[str] = set()
    repetidas = 0

    for seccion in raiz.iterfind("./diario/secciones/seccion"):
        nombre_seccion = seccion.get("nombre", "")
        for apartado in seccion.iterfind("./apartado"):
            nombre_apartado = apartado.get("nombre") or None
            for organismo in apartado.iterfind("./organismo"):
                nombre_organismo = organismo.get("nombre", "")
                for disposicion in organismo.iterfind("./disposicion"):
                    item = _leer_disposicion(
                        disposicion,
                        fecha=fecha,
                        seccion=nombre_seccion,
                        apartado=nombre_apartado,
                        organismo=nombre_organismo,
                    )
                    if item.identificador in vistos:
                        # Trampa 1. No se avisa por cada una: en un día normal esto ocurre
                        # miles de veces y llenaría el log del worker de ruido.
                        repetidas += 1
                        continue
                    vistos.add(item.identificador)
                    items.append(item)

    if len(items) > MAX_ITEMS_POR_DIA:
        # No se trunca en silencio: lo que faltara sería invisible, que es el fallo que este
        # proyecto no se permite (mismo criterio que el ADR 0020 y que el BOCYL).
        raise SumarioInvalido(
            f"El sumario del BOCM del {fecha} trae {len(items)} disposiciones distintas, por "
            f"encima del tope de {MAX_ITEMS_POR_DIA}. Puede ser una respuesta anómala."
        )

    if not items:
        raise SumarioInvalido(f"El sumario del BOCM del {fecha} no contiene ninguna disposición")

    return Sumario(
        identificador=identificador,
        # **La fecha del identificador, no la de `<fecha_publicacion>`.** Ver trampa 2.
        fecha_publicacion=fecha,
        numero_diario=metadatos.findtext("numero", "").strip(),
        items=tuple(items),
    )


def _leer_disposicion(
    disposicion: Element,
    *,
    fecha: datetime.date,
    seccion: str,
    apartado: str | None,
    organismo: str,
) -> ItemSumario:
    identificador = _texto(disposicion, "identificador", "una disposición del sumario")
    encontrado = _IDENTIFICADOR.fullmatch(identificador)
    if encontrado is None:
        raise SumarioInvalido(f"Identificador con forma inesperada: {identificador!r}")

    anyo, mes, dia, _ = encontrado.groups()
    if datetime.date(int(anyo), int(mes), int(dia)) != fecha:
        # El BOCM no arrastra enlaces de otros días como el BOCYL (ADR 0029), pero se comprueba
        # igual: es una línea y cierra la puerta a que el archivo diga que algo se publicó un día
        # en el que no se publicó.
        raise SumarioInvalido(
            f"La disposición {identificador} no es del {fecha}, y viene en su sumario"
        )

    return ItemSumario(
        identificador=identificador,
        titulo=_texto(disposicion, "titulo", identificador)[:_LONGITUD_MAXIMA_TITULO],
        url_xml=_texto(disposicion, "url_xml", identificador)[:_LONGITUD_MAXIMA_URL],
        url_pdf=(disposicion.findtext("url_pdf", "").strip() or None),
        seccion_codigo="",
        seccion_nombre=seccion,
        # El organismo del BOCM es el ayuntamiento cuando la sección es la local, y la consejería
        # cuando es la autonómica. En los dos casos es quien emite, que es lo que la columna dice.
        departamento=organismo or "BOCM",
        epigrafe=apartado,
    )


def parsear_cuerpo(contenido: bytes, identificador_esperado: str) -> Element:
    """Valida que el cuerpo descargado es el de la disposición que se pidió, y lo devuelve.

    La URL nombra el documento, así que no puede llegar el de otra disposición por un desliz de
    posición como en el BOA. Lo que sí puede llegar es otra cosa bajo la misma URL —una página de
    error, un documento resellado—, y eso el archivo de la 6.5 no puede aceptarlo.

    **No se exige prólogo `<?xml`**, a diferencia del BOCYL: el BOCM sirve su XML sin declaración
    (comprobado, sumario y cuerpo). Quien decide si esto es XML es `xml_safe`, que es quien tiene
    que decidirlo.
    """
    if _IDENTIFICADOR.fullmatch(identificador_esperado) is None:
        raise SumarioInvalido(f"Identificador mal formado: {identificador_esperado!r}")

    raiz = xml_safe.parse(contenido)
    declarado = (raiz.findtext("./metadatos/identificador") or "").strip()
    if declarado != identificador_esperado:
        raise SumarioInvalido(
            f"Se pidió el cuerpo de {identificador_esperado} y el XML dice ser "
            f"{declarado or 'sin identificador'}. No se archiva."
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
]
