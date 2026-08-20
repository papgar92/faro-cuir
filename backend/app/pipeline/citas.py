"""Referencias sacadas del **texto**, no de los metadatos. Segunda fuente del eje 2 (7.3).

El eje referencial nació leyendo el bloque `<analisis>` del BOE, que trae la norma afectada y el
verbo (`MODIFICA`, `DEROGA`) ya estructurados. Con una sola fuente eso bastaba. Con la segunda no:

    cuerpos legibles            BOE 2.968      DOGC 92
    con referencias legibles    211 (7,1 %)    **0**

El DOGC sí publica un bloque `<references>` en su Akoma Ntoso, pero **no dice a quién afecta la
norma**: sus `activeRef` apuntan al propio documento con `showAs="Modificado"`/`"Derogado"` —son
ciclo de vida— y los `passiveRef` son normas *posteriores*. Comprobado el 2026-08-19 en cuatro
documentos, uno de ellos titulado literalmente «de modificación del Decreto 358/2004»: la norma
afectada no aparece en ningún metadato, **solo en el texto**.

O sea que en la segunda fuente del proyecto el eje que cubre el agujero estructural del
diccionario no existía. Este módulo lo reconstruye a partir de lo único que hay: la cita.

## La trampa que se midió, y que decide el diseño entero

Buscar la forma corta —«Ley 2/2021»— **no vale**, y no es una precaución teórica. Medido sobre
los 264 cuerpos del DOGC, la forma corta produjo 4 coincidencias con verbo modificativo al lado y
**las 4 eran falsas**:

- «Ley 2/2021» cazó la *Ley 2/2021 de medidas fiscales de Catalunya*, no la Ley 2/2021 de Canarias
  que está en la watchlist. La numeración de leyes se repite en cada comunidad y en el Estado.
- «Ley 4/2023» cazó «**Decreto ley** 4/2023, de 19 de diciembre», porque la forma corta es una
  subcadena de la larga de otra norma distinta.
- «Ley 2/2014» cazó la *Ley 2/2014 de medidas fiscales de Catalunya*, no la de Galicia.

Con la forma larga —número **y** fecha— las cuatro desaparecen, que es la respuesta correcta:
ninguna de esas normas toca nada de la watchlist. Por eso aquí **solo se usa la forma larga**, y
por eso hay una condición explícita contra «decreto ley»: sin ella, `\\bley 4/2023` sigue
encajando dentro de «decreto ley 4/2023».

## Qué NO hace este módulo

- **No construye ninguna URL con lo que encuentra** (6.10). Devuelve el identificador **de la
  watchlist**, que es un fichero versionado del repositorio; la cadena que aparecía en el
  documento se usa para localizar y se tira. Es la misma regla que ya cumple el eje referencial
  con el `<analisis>`.
- **No decide nada.** Devuelve `ReferenciaAnterior`, exactamente el mismo tipo que produce el
  bloque del BOE, para que el prefiltro y el versionado no tengan que saber de dónde salió la
  evidencia. Quien decide sigue siendo `prefiltro.evaluar`.
- **No inventa el verbo.** Si junto a la cita no hay ninguna forma verbal de modificación, la
  referencia se emite con `CITA`, que no está en `VERBOS_MODIFICATIVOS` y por tanto no dispara el
  eje. Mencionar una ley no es tocarla — es el mismo criterio con el que el BOE distingue
  `MODIFICA` de una cita cualquiera.

## Lo que aporta hoy, medido y sin adornar

Reevaluado el corpus entero (3.232 normas, 3.060 cuerpos legibles) el 2026-08-19: el eje
referencial dispara en **3 normas, las mismas 3 que ya disparaba con el `<analisis>`**. O sea que
la aportación **única de este módulo** sobre el corpus es **cero**, y hay que decirlo así en vez
de presentar el 3 como si fuera suyo.

**Ojo con no confundir eso con la aportación del eje**, que sí dejó de ser cero al día siguiente:
`BOE-A-2014-11444` (gold set) entra en la cola **solo** por el eje referencial —cero términos
directos, y el léxico la descarta desde el ADR 0021— pero quien la caza ahí es el `<analisis>`,
no este módulo. Son dos cifras distintas y las dos hay que decirlas enteras.

Lo que sí está demostrado son dos cosas, y ninguna es un adjetivo:

1. **Encuentra la modificación leyendo solo el texto.** Sobre `BOE-A-2024-10767` —la reforma
   madrileña de 2023, el caso que el proyecto usa para explicarse— saca `BOE-A-2016-6728` con
   verbo `SUPRIME` sin tocar el `<analisis>`. Lo delató un test que se puso rojo al conectarlo:
   neutralizar el metadato ya no basta para neutralizar la referencia.
2. **No produce falsos positivos** sobre 3.060 cuerpos, que es lo que hay que exigirle a un
   módulo que busca citas de leyes en texto libre.

Y lo que cubre no ha ocurrido todavía en este corpus: un decreto autonómico que modifique la ley
trans de su comunidad. En el DOGC eso es hoy **invisible sin este módulo**, porque su bloque de
referencias no dice a quién afecta la norma.
"""

from __future__ import annotations

import re

from app.pipeline.referencias import ReferenciaAnterior
from app.pipeline.watchlist import Watchlist

# Cuántos caracteres se miran **hacia atrás** desde la cita buscando el verbo. El texto
# dispositivo pone el verbo antes: «Se modifica el artículo 7 de la Ley 11/2014, de 10 de
# octubre». Mirar solo hacia atrás y no en las dos direcciones evita el caso en que el verbo
# pertenece a la frase siguiente, que habla de otra norma.
VENTANA_VERBO = 200

# Formas verbales tal y como aparecen en el articulado, con el verbo canónico al que equivalen.
# Se comparan sin tildes y sin distinguir mayúsculas (`re.IGNORECASE`), así que aquí se escriben
# en minúscula y sin tildes.
#
# La lista es **corta a propósito**, igual que `VERBOS_MODIFICATIVOS` en `referencias.py`: una
# forma desconocida no cuenta como modificación. Perder una redacción rara cuesta un puesto en la
# cola —el eje léxico sigue mirando—; dar por modificación cualquier mención metería en la cola
# todas las normas que citan algo, que es de lo que el eje referencial vino a librarnos.
_FORMAS: tuple[tuple[str, str], ...] = (
    ("se modifica", "MODIFICA"),
    ("se modifican", "MODIFICA"),
    ("de modificacion de", "MODIFICA"),
    ("por la que se modifica", "MODIFICA"),
    ("por el que se modifica", "MODIFICA"),
    ("queda modificad", "MODIFICA"),
    ("queda redactad", "MODIFICA"),
    ("nueva redaccion", "MODIFICA"),
    ("se deroga", "DEROGA"),
    ("se derogan", "DEROGA"),
    ("queda derogad", "DEROGA"),
    ("se anade", "ANADE"),
    ("se anaden", "ANADE"),
    ("se introduce", "ANADE"),
    ("se suprime", "SUPRIME"),
    ("se suprimen", "SUPRIME"),
    ("se sustituye", "SUSTITUYE"),
    ("queda sin efecto", "DEJA SIN EFECTO"),
)

_VERBOS = re.compile("|".join(re.escape(forma) for forma, _ in _FORMAS), re.IGNORECASE)
_CANONICO = dict(_FORMAS)

# Las tildes que pueden aparecer dentro de una cita («Ley Orgánica») y la eñe. `translate` con un
# mapa de un carácter a otro **conserva la longitud**, y eso no es un detalle: los offsets que
# devuelve la búsqueda sobre el texto normalizado se usan para recortar el texto ORIGINAL, así
# que cualquier normalización que cambiara la longitud desplazaría la cita que se enseña. Por lo
# mismo aquí no se pasa a minúsculas —`str.lower()` puede cambiar la longitud en algunos
# caracteres— sino que la comparación se hace con `re.IGNORECASE`.
_ESPACIOS = re.compile(r"\s+")
_TILDES = str.maketrans("áéíóúÁÉÍÓÚñÑ", "aeiouAEIOUnN")

# La forma larga: tipo, número/año, y la fecha. Es la que no colisiona entre comunidades.
_FORMA_LARGA = re.compile(
    r"^((?:ley organica|ley foral|ley|real decreto|decreto)\s+[\d/]+,\s+de\s+\d+\s+de\s+\w+)",
    re.IGNORECASE,
)


def _normalizar(texto: str) -> str:
    """Quita tildes, y nada más. **Conserva la longitud** (ver `_TILDES`).

    Deliberadamente **no** reutiliza `prefiltro._normalizar`: aquel colapsa espacios, guiones y
    separadores porque busca términos, y aquí las barras y las comas de «11/2014, de 10 de
    octubre» son parte de lo que identifica a la norma. Además, colapsar movería los offsets.
    """
    return texto.translate(_TILDES)


def forma_larga(titulo: str) -> str | None:
    """La forma con la que se cita una norma en el texto de otra, o `None`.

    Se **deriva del título** de la watchlist en vez de guardarse como campo aparte: el título ya
    empieza por esa forma en las 21 entradas (verificado el 2026-08-19), y un campo nuevo sería
    otro dato que mantener sincronizado con el que ya está al lado.
    """
    coincidencia = _FORMA_LARGA.match(_normalizar(titulo))
    return coincidencia.group(1) if coincidencia else None


def _verbo_previo(texto_normalizado: str, inicio: int) -> str:
    """El verbo modificativo más cercano por delante de la cita, o `CITA` si no hay ninguno."""
    ventana = texto_normalizado[max(0, inicio - VENTANA_VERBO) : inicio]
    ultimo = None
    for coincidencia in _VERBOS.finditer(ventana):
        # `.lower()` porque el texto conserva sus mayúsculas —«Se modifica» al empezar frase— y
        # las claves de `_CANONICO` están en minúscula. Aquí sí se puede: es una cadena corta que
        # no vuelve a usarse para calcular ningún offset.
        ultimo = coincidencia.group(0).lower()
    return _CANONICO[ultimo] if ultimo is not None else "CITA"


def _indice(lista: Watchlist) -> tuple[re.Pattern[str] | None, dict[str, str]]:
    """Un solo patrón con todas las citas, y de la cita al identificador.

    **Una pasada por documento y no una por norma vigilada.** No es optimización prematura: la
    primera versión recorría el texto 21 veces —una por entrada de la watchlist— y sobre el corpus
    real, con documentos de hasta 2 MB, eso multiplicaba por cuatro el tiempo de reevaluarlo todo.
    El resultado es idéntico; lo que cambia es que el texto se recorre una vez.
    """
    por_cita: dict[str, str] = {}
    for vigilada in lista.normas:
        cita = forma_larga(vigilada.titulo)
        if cita is not None:
            por_cita[_clave(cita)] = vigilada.identificador
    if not por_cita:
        return None, por_cita
    alternativas = "|".join(
        r"\s+".join(re.escape(parte) for parte in cita.split(" ") if parte) for cita in por_cita
    )
    return re.compile(f"(?<!decreto )(?:{alternativas})", re.IGNORECASE), por_cita


def _clave(cita: str) -> str:
    """La forma con la que se busca una cita en el índice: sin tildes, sin mayúsculas y con los
    espacios colapsados. Se aplica igual a las citas de la watchlist y a lo que encuentra el
    patrón, que es lo que permite que las dos coincidan aunque el documento tenga un salto de
    línea en medio."""
    return _ESPACIOS.sub(" ", _normalizar(cita).lower()).strip()


def extraer_referencias_citadas(texto: str, lista: Watchlist) -> tuple[ReferenciaAnterior, ...]:
    """Normas de la watchlist citadas en el texto, con el verbo que las acompaña.

    Una norma por identificador, con el verbo **más fuerte** encontrado: si aparece dos veces y
    solo una lleva «se modifica», la norma la modifica. Quedarse con la última coincidencia
    convertiría el resultado en una lotería de orden de aparición.
    """
    if not texto:
        return ()
    patron, por_cita = _indice(lista)
    if patron is None:
        return ()
    normalizado = _normalizar(texto)
    encontradas: dict[str, ReferenciaAnterior] = {}

    for coincidencia in patron.finditer(normalizado):
        identificador = por_cita.get(_clave(coincidencia.group(0)))
        if identificador is None:
            # Inalcanzable: el patrón se construye desde las mismas claves. Se comprueba en vez
            # de suponerse porque un `KeyError` aquí tumbaría la lectura de un cuerpo entero.
            continue
        verbo = _verbo_previo(normalizado, coincidencia.start())
        previa = encontradas.get(identificador)
        if previa is None or (previa.verbo == "CITA" and verbo != "CITA"):
            encontradas[identificador] = ReferenciaAnterior(
                # El identificador es **el de la watchlist**, no una cadena del documento.
                identificador=identificador,
                verbo=verbo,
                # El recorte del texto, para que quien revise vea de dónde salió. Se guarda
                # el original y no el normalizado: lo que se enseña es el archivo.
                texto=texto[max(0, coincidencia.start() - 80) : coincidencia.end() + 80].strip(),
            )
    return tuple(encontradas.values())
