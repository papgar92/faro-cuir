"""Texto consolidado del BOE: de dónde sale el **texto anterior**. ADR 0018, CLAUDE.md 5 y 7.6.

Módulo **casi puro**: construye una URL y lee un árbol XML ya parseado por
`security/xml_safe.py` (6.1). No abre conexiones —eso es de `services/versionado.py` a través
de `url_guard`— y no toca la base de datos.

## El problema que resuelve

Una norma modificativa del BOE publica la redacción **nueva** («El artículo 4 queda redactado
como sigue: …»), nunca la vieja. Con solo eso archivado, el diff de una modificación no se
puede construir, y por eso el catálogo de reglas (7.6) solo tiene familias que no lo necesitan:
supresión y derogación. Falta la mitad del hecho: qué decía antes.

El BOE publica esa mitad en su **legislación consolidada**, con la estructura verificada contra
documentos reales el 2026-08-15 (no deducida de documentación):

    response > data > bloque[@id="a7"][@tipo="precepto"][@titulo="Artículo 7"]
                        ├── version[@id_norma="BOE-A-2016-6728"][@fecha_vigencia="20160427"]
                        │     └── <p class="articulo">…</p> <p class="parrafo">…</p>
                        └── version[@id_norma="BOE-A-2024-10767"][@fecha_vigencia="20231230"]
                              ├── <p class="parrafo"><strong>(Suprimido)</strong></p>
                              └── <blockquote><p class="nota_pie">Se suprime por el art. …</p>

**Cada bloque guarda sus redacciones sucesivas y cada una dice qué norma la introdujo.** Eso es
exactamente el par (texto_anterior, texto_nuevo) de `version_norma`: la versión cuyo `id_norma`
es la norma que estamos analizando, y la inmediatamente anterior de ese mismo bloque.

Medido sobre el caso insignia del proyecto: `BOE-A-2016-6728` (Ley 2/2016 de Madrid) tiene 81
bloques, **34 con una versión introducida por `BOE-A-2024-10767`** —la reforma madrileña de
2023—, incluido el artículo 4, que pasa de «Reconocimiento del derecho a la identidad de género
libremente manifestada» a «Reconocimiento del respeto a la libertad y dignidad de las personas
transexuales». Ese cambio de título es un retroceso silencioso de manual y hasta hoy el sistema
no tenía con qué verlo.

## Lo que este módulo NO hace, y es deliberado

**No clasifica.** Devuelve el par de textos y quién los introdujo. Que un cambio sea avance o
retroceso lo decide el catálogo de reglas sobre el diff (7.6), con `regla_aplicada` y spans.

**No construye la URL con un identificador que venga de un documento.** La 6.10 es explícita:
un identificador extraído de una fuente externa se compara con la watchlist, pero no se usa
para componer una petición. Aquí la URL se compone con el identificador **de la watchlist**
—fichero versionado en el repo, validado al cargarse— y `url_consolidado` vuelve a validar el
formato antes de interpolarlo. Que el `<analisis>` de la norma del día nombre a esa norma solo
sirve para **elegir** qué entrada de la watchlist mirar.

## El texto consolidado es una elaboración del BOE, no lo publicado

Y por eso no sustituye a nada de lo archivado: se archiva **aparte**, con su propio `sha256` y
su sello (6.5, `tipo='consolidado'`), y cada fila de `version_norma` apunta al documento
consolidado del que salió. Quien quiera rebatir un diff tiene el fichero exacto que lo produjo,
con su huella, sin ejecutar nuestro código.

Consecuencia que hay que tener presente: **la consolidación llega con retraso**. Una norma
publicada hoy puede tardar semanas en aparecer dentro del texto consolidado de la norma que
modifica. Eso no es un fallo, es el ritmo de la fuente; el servicio lo trata reintentando.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from xml.etree.ElementTree import Element

from app.pipeline.watchlist import PATRON_IDENTIFICADOR

# Sube cuando cambie la forma de derivar el texto de un bloque (qué elementos entran y cuáles
# no). Viaja en cada fila de `version_norma` por el mismo motivo que `VERSION_TEXTO_PLANO` en
# `deteccion`: un diff guardado con otra derivación no es comparable con uno de hoy, y como la
# tabla es inmutable (nunca se reescribe una versión), la única forma de saberlo es que la fila
# lo diga.
VERSION_CONSOLIDADO = "2026.08.15.1"

# Endpoint de legislación consolidada de la API de datos abiertos del BOE. Verificado el
# 2026-08-15: responde 200 con `Accept: application/xml`, y **400 sin esa cabecera**.
URL_BASE = "https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/"

CABECERAS = {"Accept": "application/xml"}

_ESPACIOS = re.compile(r"\s+")

# Bloques que **no son articulado** sino avisos del consolidador, y que por tanto no producen
# diff. Es la misma regla que excluye las notas `nota_pie`, aplicada al nivel de bloque.
#
# **Lo encontró la primera ejecución real (2026-08-15), no un test.** El bloque `nota_inicial`
# («Norma derogada, con efectos desde el 2 de marzo de 2023…», «Esta norma pasa a denominarse
# …») lo *añade* la norma modificadora, así que aparecía como una versión sin texto anterior:
# es decir, **como un alta de un precepto que nadie ha añadido**. Justo el tipo de hecho falso
# que una regla futura sobre modificaciones leería como cambio normativo.
#
# La información de esos avisos no se pierde: que una norma derogue a otra ya lo ve el eje
# referencial por el `<analisis>` y lo clasifica R-DER-001, leyendo el texto publicado en vez
# de la glosa del consolidador.
_TIPOS_EDITORIALES = frozenset({"nota_inicial"})


class ConsolidadoError(RuntimeError):
    """El consolidado no se puede usar. Nunca significa 'no hay cambios'."""


class IdentificadorInvalido(ConsolidadoError):
    """Se ha intentado componer una URL con algo que no es un identificador de norma.

    Existe como error propio y no como un `if` suelto porque es un **control de 6.10**: la
    única defensa que vale es la que está en el constructor de la URL, no en la buena costumbre
    de quien lo llama.
    """


class NoConsolidado(ConsolidadoError):
    """La norma no tiene texto consolidado publicado (o todavía no).

    Es una respuesta legítima de la fuente, no una avería: el BOE consolida una parte de lo que
    publica y con retraso. Se distingue del resto de errores para que el servicio pueda contarlo
    aparte y reintentarlo mañana sin que parezca un fallo.
    """


def url_consolidado(identificador: str) -> str:
    """La URL del texto consolidado de una norma. Valida el formato antes de interpolar (6.10).

    El identificador que se le pasa debe venir de `config/watchlist.json`, no de un documento
    descargado. La validación de aquí es defensa en profundidad: si algún día alguien llama a
    esto con lo que dijo un `<analisis>` —o peor, con lo que dijo el modelo—, el patrón anclado
    por los dos extremos impide que eso se convierta en una ruta o en una petición a otro sitio.
    """
    if not PATRON_IDENTIFICADOR.match(identificador):
        raise IdentificadorInvalido(
            f"identificador con formato inválido, no se compone URL: {identificador!r}"
        )
    return f"{URL_BASE}{identificador}"


@dataclass(frozen=True)
class VersionBloque:
    """Una de las redacciones sucesivas de un bloque, con la norma que la introdujo."""

    id_norma: str
    fecha_vigencia: datetime.date | None
    texto: str


@dataclass(frozen=True)
class BloqueConsolidado:
    """Un bloque del texto consolidado (un artículo, una disposición, el preámbulo)."""

    id: str
    titulo: str
    tipo: str
    # En orden de publicación, tal y como las sirve el BOE. La última es la vigente hoy.
    versiones: tuple[VersionBloque, ...]


@dataclass(frozen=True)
class Cambio:
    """Lo que una norma concreta le hizo a un bloque concreto. Materia prima de `version_norma`.

    `texto_anterior` a NULL significa **alta**: el bloque no existía antes de esta norma. Es la
    misma convención que documenta el modelo de dominio, y no se rellena con cadena vacía a
    propósito: "no había texto" y "el texto era vacío" son cosas distintas.
    """

    bloque: str
    titulo: str
    texto_anterior: str | None
    texto_nuevo: str
    fecha_vigencia: datetime.date | None


def _fecha(valor: str | None) -> datetime.date | None:
    """`20231230` → date. Un formato inesperado devuelve None en vez de romper el diff.

    La fecha es contexto útil (desde cuándo rige la redacción nueva), no la evidencia. Perder
    una fecha mal formada no invalida el par de textos, y abortar por ella dejaría el cambio sin
    archivar por un detalle que no sostiene ninguna conclusión.
    """
    if not valor:
        return None
    try:
        return datetime.datetime.strptime(valor.strip(), "%Y%m%d").date()
    except ValueError:
        return None


def _texto_version(version: Element) -> str:
    """El texto normativo de una redacción, **sin las notas del consolidador**.

    Las anotaciones del BOE («Se suprime por el art. único.7 de la Ley 17/2023…») viajan dentro
    de `<blockquote><p class="nota_pie">`. Son metadato editorial, no articulado, y dejarlas
    dentro tendría dos efectos malos a la vez: ensuciaría el diff con texto que no es de la
    norma, y haría que **toda** redacción modificada pareciera distinta por la nota y no por el
    cambio. Se excluyen por elemento y por clase, que son dos formas de decir lo mismo y
    sobreviven a que la fuente cambie una de las dos.
    """
    fragmentos: list[str] = []
    for nodo in version:
        if nodo.tag == "blockquote":
            continue
        if nodo.get("class") == "nota_pie":
            continue
        fragmentos.extend(fragmento.strip() for fragmento in nodo.itertext())
    return _ESPACIOS.sub(" ", " ".join(f for f in fragmentos if f)).strip()


def comprobar_respuesta(raiz: Element) -> None:
    """Levanta si la respuesta no es un consolidado utilizable.

    La API contesta con su propio bloque `<status>` —`404 / La información solicitada no
    existe`— y ese caso es el mayoritario: la mayor parte de lo que publica el BOE no tiene
    texto consolidado. Se comprueba **antes** de mirar bloques para no confundir "no hay
    consolidado" con "el consolidado no menciona a esta norma", que exigen decisiones distintas.
    """
    codigo = (raiz.findtext("./status/code") or "").strip()
    if codigo == "404":
        raise NoConsolidado(raiz.findtext("./status/text") or "sin texto consolidado")
    if codigo and codigo != "200":
        raise ConsolidadoError(f"la API respondió {codigo}: {raiz.findtext('./status/text')!r}")


def extraer_bloques(raiz: Element) -> tuple[BloqueConsolidado, ...]:
    """Los bloques del consolidado con sus redacciones sucesivas.

    `.//bloque` y no una ruta fija por el mismo motivo que en `pipeline/referencias.py`: este
    módulo recibe unas veces la raíz de la respuesta y otras el nodo `<data>`, según quién
    llame, y anclar la ruta obligaría a que todos coincidieran.

    Una versión sin `id_norma` se descarta: sin saber qué norma la introdujo no sirve para
    atribuir un cambio a nadie, que es justo para lo que existe este módulo.
    """
    bloques: list[BloqueConsolidado] = []
    for nodo in raiz.iterfind(".//bloque"):
        if (nodo.get("tipo") or "").strip() in _TIPOS_EDITORIALES:
            continue
        versiones = tuple(
            VersionBloque(
                id_norma=(v.get("id_norma") or "").strip(),
                fecha_vigencia=_fecha(v.get("fecha_vigencia")),
                texto=_texto_version(v),
            )
            for v in nodo.iterfind("version")
            if (v.get("id_norma") or "").strip()
        )
        if not versiones:
            continue
        bloques.append(
            BloqueConsolidado(
                id=(nodo.get("id") or "").strip(),
                titulo=(nodo.get("titulo") or "").strip(),
                tipo=(nodo.get("tipo") or "").strip(),
                versiones=versiones,
            )
        )
    return tuple(bloques)


def cambios_de(bloques: tuple[BloqueConsolidado, ...], identificador: str) -> tuple[Cambio, ...]:
    """Qué le hizo `identificador` a cada bloque: el par (texto anterior, texto nuevo).

    Para cada bloque se busca la redacción que introdujo esa norma y se toma la inmediatamente
    anterior como texto previo. **La comparación del identificador es exacta**, sin normalizar
    ni recortar, igual que en `Watchlist.contiene`: "arreglar" un identificador es como se acaba
    atribuyendo un cambio a quien no lo hizo.

    Si la norma tocó el mismo bloque dos veces —posible en una norma con varias redacciones
    sucesivas del mismo precepto— se toma la **última**, que es la que quedó vigente, y su
    anterior. El caso es raro y la alternativa (emitir dos filas para el mismo bloque) daría dos
    diffs solapados del mismo hecho.
    """
    cambios: list[Cambio] = []
    for bloque in bloques:
        indices = [i for i, v in enumerate(bloque.versiones) if v.id_norma == identificador]
        if not indices:
            continue
        indice = indices[-1]
        version = bloque.versiones[indice]
        anterior = bloque.versiones[indice - 1].texto if indice > 0 else None
        cambios.append(
            Cambio(
                bloque=bloque.id,
                titulo=bloque.titulo,
                texto_anterior=anterior,
                texto_nuevo=version.texto,
                fecha_vigencia=version.fecha_vigencia,
            )
        )
    return tuple(cambios)
