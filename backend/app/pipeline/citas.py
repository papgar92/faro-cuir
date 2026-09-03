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
    # «por la que se modifica» y «por el que se modifica» ESTUVIERON AQUI y se quitaron el
    # 2026-08-30: son la construccion con la que una norma se NOMBRA, no una clausula de este
    # documento. Quitarlas no pierde nada -- «se modifica» sigue casando dentro de la misma
    # frase-- y es lo que permite que `_verbo_previo` vea el «por la que» que va delante.
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


# Si el título trae un número de norma `N/AAAA`, es de un rango **numerado** y entonces tiene que
# poder citarse: que no encaje en `_FORMA_LARGA` significa que está mal escrito. Si no lo trae, su
# rango no se cita así y quedar fuera del eje no es un fallo sino una limitación estructural.
#
# El corte es por el número y no por una lista de tipos a propósito: «Decreto de 14 de noviembre de
# 1958» empieza por un tipo que normalmente sí va numerado y aun así no lleva número, y una lista
# de tipos lo daría por mal escrito cuando su título es exactamente el oficial.
_LLEVA_NUMERO = re.compile(r"^[^,]{0,60}?\b\d{1,4}/\d{4}\b", re.IGNORECASE)


def cita_esperable(titulo: str) -> bool:
    """¿Debería esta norma poder citarse en el texto de otra?

    Separa las dos razones por las que `forma_larga` puede devolver `None`, que hasta el
    2026-08-23 estaban confundidas y solo podían estarlo mientras la watchlist fueron 24 leyes:

    - **El título está mal escrito** → hay que arreglarlo, y el test lo pone rojo.
    - **El rango no lleva número** (una instrucción, una orden, el Reglamento del Registro Civil
      de 1958) → no hay nada que arreglar. Esa entrada dispara por el `<analisis>` del BOE, que es
      donde de verdad viven sus modificaciones, pero **es invisible para el eje de citas** y por
      tanto para el DOGC y para cualquier fuente futura que no publique `<analisis>`.

    Lo segundo no se puede tapar ni se puede llamar fallo: se declara. Ver ADR 0022.
    """
    return _LLEVA_NUMERO.match(_normalizar(titulo)) is not None


def forma_larga(titulo: str) -> str | None:
    """La forma con la que se cita una norma en el texto de otra, o `None`.

    Se **deriva del título** de la watchlist en vez de guardarse como campo aparte: un campo nuevo
    sería otro dato que mantener sincronizado con el que ya está al lado.

    **Devuelve `None` para las entradas de rango no numerado**, y eso es correcto — ver
    `cita_esperable`. El comentario que había aquí decía «el título ya empieza por esa forma en las
    21 entradas (verificado el 2026-08-19)» y dejó de ser cierto el 2026-08-23, al entrar las dos
    Instrucciones de la DGSJFP. Se sustituye en vez de actualizar la cifra: una invariante que hay
    que recontar a mano cada vez que alguien toca un JSON no es una invariante, es una nota que
    caduca sin avisar. Quien la comprueba ahora es `cita_esperable` y el test que la usa.
    """
    coincidencia = _FORMA_LARGA.match(_normalizar(titulo))
    return coincidencia.group(1) if coincidencia else None


# **«…por la que se modifica X» es el NOMBRE de otra norma, no una cláusula de este documento.**
#
# El título oficial de la LOMLOE es literalmente «Ley Orgánica 3/2020, de 29 de diciembre, por la
# que se modifica la Ley Orgánica 2/2006, de 3 de mayo, de Educación». Toda norma educativa
# española la cita por su nombre completo, así que **todas parecían modificar la LOE** en cuanto
# la LOE entró en la watchlist (ADR 0030).
#
# Medido el 2026-08-30 sobre las 893 normas de la cola del clasificador: de 143 referencias
# modificativas a normas vigiladas, **81 tenían el verbo dentro de un título**. Y no era solo cosa
# de las norma-vehículo nuevas — 2 de esas 81 apuntaban a las leyes madrileñas, que son el caso
# insignia del proyecto.
#
# Es el mismo error que el ADR 0023 un paso más atrás: allí el verbo estaba suelto en el documento
# y no pegado a la norma; aquí está pegado, pero pertenece al nombre de otra.
_TITULO_AJENO = re.compile(r"por\s+(?:la|el|las|los)\s+(?:que|cual|cuales)\s*$", re.IGNORECASE)


# **El verbo tiene que GOBERNAR la cita, no solo caer cerca de ella.**
#
# Tercer paso de la misma idea. El ADR 0023 exigió que el verbo fuera de la norma vigilada y no
# de cualquier supresión del documento; el arreglo del 2026-08-30, que no perteneciera al nombre
# de otra norma. Queda el resto: el verbo está suelto en el documento, dentro de la ventana, y
# **la cita no es su objeto**. ESTADO.md lo dejó anotado como *«no hay una construcción que lo
# delate, solo distancia»* y como *«no se toca a ojo»*.
#
# Medido el 2026-09-03 con `scripts/medir_ventana_verbo.py` sobre las 925 normas de la cola: de
# las **89** referencias modificativas a normas vigiladas, **22 son de las de abajo y las 22 son
# ruido**. Quedan 67, y entre ellas siguen enteras la valenciana de 31 preceptos, la madrileña,
# la catalana y las cinco de la cartera del SNS.
#
# **Y la distancia, que era la solución evidente, es la mala**: recortar `VENTANA_VERBO` a 60
# deja el mismo número (67) pero se lleva por delante dos modificaciones **reales** —el apartado
# 5 del art. 8 de la ley LGTBI valenciana (67 caracteres) y cinco preceptos de la ley trans
# valenciana en `BOE-A-2026-16931` (105)— a cambio de conservar ruido de 4 caracteres. La misma
# cifra por fuera y lo contrario por dentro: es exactamente lo que la medición existía para ver.

# 1. Empieza un texto citado. Lo que se nombre ahí dentro es del documento **modificado**, no de
#    este: «…queda redactado como sigue: "…de conformidad con el art. 117.9 de la Ley 2/2006"».
_ABRE_CITA = re.compile(r"[:«\"“]")

# 2. La cita no es el objeto del verbo sino el término de una referencia: se la nombra para
#    situar algo. «…los cuerpos docentes **a que se refiere la** Ley Orgánica 2/2006». Seis de
#    los 22 descartes son esta forma sobre la LOE, y todos en oposiciones y conciertos.
_CONECTOR_REFERENCIAL = re.compile(
    r"\b(?:a\s+(?:que|los?\s+que|las?\s+que|la\s+que|el\s+que)\s+se\s+refiere"
    r"|regulad[oa]s?\s+por|derivad[oa]s?\s+de|previst[oa]s?\s+en|establecid[oa]s?\s+en"
    r"|contemplad[oa]s?\s+en|de\s+conformidad\s+con|dada\s+por|segun\s+lo\s+previsto\s+en"
    r"|en\s+los\s+terminos)\b",
    re.IGNORECASE,
)

# 3. Otra norma citada por su forma larga entre el verbo y la nuestra: **el verbo lo reclama la
#    más cercana**. Es el criterio del ADR 0023 aplicado entre dos candidatas en vez de entre el
#    documento y la norma.
_OTRA_NORMA = re.compile(
    r"\b(?:ley organica|ley foral|ley|real decreto|decreto|orden|resolucion|instruccion)"
    r"\s+[\w./-]*\d[\w./-]*",
    re.IGNORECASE,
)

# 4. Se cierra una frase en medio. Un punto de abreviatura no cierra nada, y en este corpus las
#    que aparecen pegadas a una mayúscula son pocas y conocidas; lo que no esté aquí cuenta como
#    frontera, que es el lado que **conserva** la referencia (perder una modificación real es el
#    fallo caro, no al revés).
_ABREVIATURAS = frozenset(
    ("art", "arts", "num", "apdo", "apdos", "disp", "pag", "pags", "cap", "sr", "sra", "d", "f")
)
_FRONTERA = re.compile(r"(?<![\w.])(\w*)\.\s+(?=[A-ZÁÉÍÓÚÑ])")

# 5. La forma casó dentro de una palabra más larga. `_VERBOS` es una alternancia y casa la
#    primera que encaja, así que «se modifica» casa también dentro de «se modificaron», que
#    **narra en pasado lo que hizo otra norma** y es preámbulo, no articulado. Las formas que
#    acaban a media palabra a propósito —«queda modificad», para masculino y femenino— quedan
#    fuera de la comprobación.
_FORMAS_CERRADAS = frozenset(
    forma for forma, _ in _FORMAS if not forma.endswith(("modificad", "redactad", "derogad"))
)
_TODAS_LAS_FORMAS = frozenset(forma for forma, _ in _FORMAS)
_PALABRA = re.compile(r"\w*")


def _cierra_frase(entre: str) -> bool:
    for coincidencia in _FRONTERA.finditer(entre):
        if coincidencia.group(1).lower() in _ABREVIATURAS:
            continue
        return True
    return False


def _flexion_ajena(forma: str, entre: str) -> bool:
    if forma not in _FORMAS_CERRADAS:
        return False
    palabra = _PALABRA.match(entre)
    resto = palabra.group(0) if palabra is not None else ""
    return bool(resto) and (forma + resto) not in _TODAS_LAS_FORMAS


def _gobierna(forma: str, entre: str) -> bool:
    """¿Es la cita el objeto de este verbo, o solo cae detrás de él?

    `entre` es el texto que va del final del verbo al principio de la cita. En una cláusula de
    verdad ahí solo hay el objeto —«el apartado 2 del artículo 8 de la», «los anexos I, II y III
    del»—; las cinco construcciones de arriba son las que aparecen cuando no lo es.

    **Se comprueba con una lista de lo que descarta y no de lo que acepta**, a propósito: una
    lista de formas admitidas convertiría cualquier redacción no prevista en un falso negativo, y
    un falso negativo aquí es invisible (7.1). Estas cinco están medidas sobre el corpus; lo que
    no esté en ellas sigue pasando.
    """
    return not (
        _ABRE_CITA.search(entre)
        or _CONECTOR_REFERENCIAL.search(entre)
        or _OTRA_NORMA.search(entre)
        or _cierra_frase(entre)
        or _flexion_ajena(forma, entre)
    )


def _es_titulo_propio(titulo: str, cita: str) -> bool:
    """¿La construcción está en el título del PROPIO documento, que sí declara lo que hace?

    «Orden SND/454/2025, de 9 de mayo, **por la que se modifican** los anexos I, II, III y VI del
    Real Decreto 1030/2006» es una modificación de verdad: la anuncia el documento en su nombre.
    Se reconoce porque **el título del propio documento lleva la construcción**; ahí no hace falta
    comprobar qué norma nombra, porque el documento solo puede estar hablando de lo que él hace.

    Sin esta salvedad el arreglo se llevaría por delante 12 casos reales de los 81 medidos, y uno
    de ellos toca el RD 1030/2006 —la cartera de servicios del SNS—, que está vigilado.
    """
    if not titulo or not cita:
        return False
    del_titulo = _clave(titulo)
    if "por la que se modific" not in del_titulo and "por el que se modific" not in del_titulo:
        return False
    # **Y la norma citada tiene que ser la que ese título nombra.** Sin esta segunda condición se
    # cuela justo el ruido que motivó el arreglo: «Orden EFD/998/2025, por la que se modifica la
    # Orden EDU/2739/2009» lleva la construcción en su propio título, pero lo que modifica es esa
    # orden — la LOE solo aparece citada más abajo, dentro del nombre de la LOMLOE.
    return _clave(cita) in del_titulo


def _verbo_previo(texto_normalizado: str, inicio: int, titulo: str = "", cita: str = "") -> str:
    """El verbo modificativo más cercano por delante de la cita, o `CITA` si no hay ninguno.

    Un verbo precedido de «por la que» pertenece al **nombre de otra norma** y no cuenta, salvo
    que ese nombre sea el del propio documento (ver `_TITULO_AJENO` y `_es_titulo_propio`). Y un
    verbo que no **gobierna** la cita tampoco cuenta, aunque caiga dentro de la ventana (ver
    `_gobierna`).
    """
    ventana = texto_normalizado[max(0, inicio - VENTANA_VERBO) : inicio]
    ultimo = None
    for coincidencia in _VERBOS.finditer(ventana):
        anterior = ventana[: coincidencia.start()]
        if _TITULO_AJENO.search(anterior) and not _es_titulo_propio(titulo, cita):
            continue
        if not _gobierna(coincidencia.group(0).lower(), ventana[coincidencia.end() :]):
            continue
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


def extraer_referencias_citadas(
    texto: str, lista: Watchlist, titulo: str = ""
) -> tuple[ReferenciaAnterior, ...]:
    """Normas de la watchlist citadas en el texto, con el verbo que las acompaña.

    Una norma por identificador, con el verbo **más fuerte** encontrado: si aparece dos veces y
    solo una lleva «se modifica», la norma la modifica. Quedarse con la última coincidencia
    convertiría el resultado en una lotería de orden de aparición.

    `titulo` es el del **propio documento** y sirve para una sola cosa: distinguir «…por la que se
    modifica X» cuando forma parte del nombre de otra norma —que no es una modificación de este
    documento— de cuando forma parte del suyo, que sí lo es. Vacío es seguro: sin título, toda
    esa construcción se trata como ajena, que es el lado conservador.
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
        verbo = _verbo_previo(normalizado, coincidencia.start(), titulo, coincidencia.group(0))
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
