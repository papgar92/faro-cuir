"""Etapa 4 del pipeline: el catálogo de reglas del clasificador. CLAUDE.md 7.6, ADR 0016.

Módulo **puro**: ni base de datos ni red ni LLM. Recibe el texto ya archivado (derivado con
`pipeline/texto.texto_plano`) y las referencias del `<analisis>`, y devuelve un veredicto con
la regla que lo produjo y los rangos de caracteres que lo sostienen.

**Ninguna regla consulta al modelo ni lee un campo que venga de su juicio** (7.6). Esto no es
una cautela de estilo: es lo que permite que una alerta publicada la reconstruya un tercero
leyendo la regla y el texto archivado, sin ejecutar nuestro código. «Queda suprimido» lo
comprueba cualquiera con el XML y el `sha256` delante; `accion == "supresion"` escrito por un
modelo de 3B parámetros no lo comprueba nadie. Ese fue el argumento central del ADR 0016.

## Por qué la primera familia de reglas es la supresión

Porque era la única clasificable con lo que había archivado cuando se escribió. Una norma
modificativa del BOE publica la redacción **nueva** («El artículo 4 queda redactado como sigue:
…»), no la vieja, y `version_norma` estaba vacía: el diff de una *modificación* no se podía
construir. La supresión, en cambio, no necesita texto anterior — el hecho es que el precepto deja
de existir. (El ADR 0018 llenó `version_norma`; ver la tercera familia, más abajo.)

## La segunda familia: derogación, y por qué NO produce «retroceso»

La derogación es la otra familia que no necesita texto anterior, y por eso es la que sigue. Pero
su veredicto es `indeterminado` y no `retroceso`, **y el motivo es el caso insignia del propio
proyecto**: `BOE-A-2023-5366` —la Ley 4/2023— deroga `BOE-A-2007-5585` —la Ley 3/2007, que está
en la watchlist— y es un **avance**, porque la sustituye ampliando protección.

Una regla ingenua «deroga norma vigilada → retroceso», que es la extensión aparentemente natural
de R-SUP-001, clasificaría al revés justo la norma que este proyecto usa para explicar por qué
existe. El supuesto de R-SUP-001 —la watchlist son normas protectoras, luego quitarles preceptos
quita protección— **no se transporta a la derogación**, porque derogar una norma entera es lo que
hace tanto quien la desmonta como quien la sustituye por otra mejor.

Distinguir los dos casos exige saber **qué ocupa el lugar de la norma derogada**. Así que la
decisión honesta es la que 7.6 llama el umbral de recall alto: severidad alta, sin signo, a la
cola de revisión con su evidencia para que la mire una persona. Afirmar el signo aquí sería
exactamente lo que la regla de oro 2 prohíbe.

## La tercera familia: modificación (R-MOD-001), desde el ADR 0018

`version_norma` **ya no está vacía**: el texto anterior de un precepto modificado se archiva
desde el consolidado del BOE. Eso no cambia lo que el catálogo puede *afirmar* —una reescritura
sigue sin decir hacia dónde, y por eso R-MOD-001 tampoco emite signo— pero cambia por completo lo
que puede **enseñar**. Una alerta que decía «han modificado el artículo 4» pasa a enseñar que
pasó de «reconocimiento del derecho a la identidad de género libremente manifestada» a
«reconocimiento del respeto a la libertad y dignidad de las personas transexuales», con las dos
redacciones sacadas de documentos archivados con su huella.

El diff entra en el veredicto como **evidencia y diagnóstico, nunca como criterio**: ver
`terminos_perdidos`, donde está escrito el contraejemplo que impide convertirlo en signo. Y
acompaña a **todas** las reglas que identifican una norma vigilada, no solo a esta: lo enseñó la
primera pasada real, donde las dos reformas madrileñas disparan R-SUP-001 —que va antes— y
atarlo a R-MOD-001 habría dejado el caso insignia del proyecto sin el antes y el después.

**R-MOD-001 no ha disparado ni una vez sobre el corpus de tres días**, porque las dos normas que
reescriben preceptos de la watchlist también suprimen alguno y R-SUP-001 manda. O sea que su
precisión sobre texto real está **sin observar**, al contrario que las otras dos familias. Dicho
aquí para que nadie la cuente como comprobada (regla de oro 8).

## Qué se midió antes de escribir esto, y qué no

Sobre los 655 ficheros archivados (652 cuerpos de tres días de BOE), el detector dispara en
**7 documentos y 40 cláusulas**. Sobre `BOE-A-2024-10767` localiza **12 cláusulas de
supresión**, dos más de las diez que el sondeo manual del ADR 0016 recogió («Se suprime el
apartado 2 del artículo 8» y «Se suprime el siguiente texto del apartado 2 del artículo 36»):
o sea que el catálogo encuentra más que la lectura a mano que lo justificó, no menos. Y
rechaza correctamente el único falso positivo obvio del documento, un «suprimir» en infinitivo
dentro de la redacción *nueva* de un artículo («Ninguna persona podrá ser presionada para
ocultar, suprimir o negar su condición sexual»).

**Eso es precisión observada sobre un corpus de tres días, no cobertura.** Cuántas supresiones
reales se escapan no se sabe y no se puede saber sin el gold set; el ADR 0016 lo deja escrito
como consecuencia y aquí se repite donde duele: *ninguna cifra de cobertura de estas reglas se
publica antes del gold set*, igual que con el eje léxico.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field

from app.models.deteccion import Clasificacion
from app.pipeline import prefiltro
from app.pipeline.referencias import ReferenciaAnterior
from app.pipeline.watchlist import Watchlist

# Sube cuando cambie cualquier patrón, umbral o veredicto de este fichero. Se guarda junto a
# cada detección y obliga a reevaluar lo anterior, igual que `VERSION_VOCABULARIO` y la versión
# de la watchlist: sin esto, dos alertas de fechas distintas no serían comparables porque no se
# sabría si las produjo el mismo catálogo.
VERSION_REGLAS = "2026.08.15.1"

# --- Identificadores estables de regla ---------------------------------------------------
# Van a `deteccion.regla_aplicada` y son parte del contrato de auditoría: no se renombran. Si
# una regla cambia de criterio, sube `VERSION_REGLAS`; si se sustituye por otra distinta, se
# usa un identificador nuevo y el viejo queda retirado, nunca reutilizado con otro significado.
R_SUP_NORMA_VIGILADA = "R-SUP-001"
R_SUP_SIN_NORMA_VIGILADA = "R-SUP-002"
R_DER_NORMA_VIGILADA = "R-DER-001"
R_MOD_NORMA_VIGILADA = "R-MOD-001"

# Construcciones **operativas** de supresión: las que un texto normativo usa para borrar algo,
# no para hablar de borrar. La distinción no es gramatical por gusto — es la que rechaza el
# infinitivo «para ocultar, suprimir o negar su condición sexual», que está dentro de la
# redacción nueva de un artículo y no suprime nada.
#
# Las dos primeras familias están **verificadas contra documentos reales** (las 12 cláusulas de
# `BOE-A-2024-10767` y las 28 restantes del barrido). Las dos últimas —«queda sin contenido»,
# «se deja sin contenido»— son fórmulas legislativas habituales que **no han aparecido en el
# corpus de tres días**: se incluyen porque el coste de un falso positivo aquí es una revisión
# humana de más, y el de un falso negativo es no ver una supresión. Está dicho para que nadie
# las cuente como comprobadas (regla de oro 8).
_SUPRESION = re.compile(
    r"\bse\s+suprim(?:e|en)\b"
    r"|\bqueda(?:n)?\s+suprimid[oa]s?\b"
    r"|\bqueda(?:n)?\s+sin\s+contenido\b"
    r"|\bse\s+deja(?:n)?\s+sin\s+contenido\b",
    re.IGNORECASE,
)

# Construcciones **operativas** de derogación, con el mismo criterio que `_SUPRESION`: las que
# derogan, no las que hablan de derogar. El corpus enseña exactamente dónde está la línea, y
# estas cuatro formas salen de él (12 referencias `DEROGA` sobre 652 cuerpos archivados):
#
#   OPERATIVAS  «Queda derogada la Ley 3/2007, de 15 de marzo…»
#               «Quedan derogados el Real Decreto 296/1996… y el Real Decreto 386/1996…»
#               «…se deroga expresamente el Real Decreto 296/1996, de 23 de febrero…»
#   RUIDO       «…y por el que se deroga la Directiva 95/46/CE…»  ← cita del título de un
#               reglamento europeo dentro del preámbulo: no deroga nada aquí.
#               «…por el que se derogan los Reglamentos (UE)…»    ← lo mismo.
#               «Se derogan las disposiciones de igual o inferior rango que contradigan…»
#               ← cláusula de arrastre genérica, sin norma identificada: no dice qué cae.
#
# `se deroga` a secas queda fuera **a propósito** y es lo que separa las dos columnas: aparece
# en las tres formas de ruido y en ninguna de las operativas sin ir acompañado de «expresamente».
_DEROGACION = re.compile(
    r"\bqueda(?:n)?\s+derogad[oa]s?\b" r"|\bse\s+deroga(?:n)?\s+expresamente\b",
    re.IGNORECASE,
)

# Cómo se nombra una norma **concreta**, para exigirlo en la misma cláusula que la derogación
# igual que `_PRECEPTO` se exige en la de supresión.
#
# El número (`3/2007`, `905/2022`) es obligatorio y es lo único que separa una derogación real
# de la **cláusula de arrastre**, que aparece al final de casi toda norma reglamentaria:
#
#   REAL     «Queda derogada la Ley 3/2007, de 15 de marzo…»
#            «Quedan derogados el Real Decreto 296/1996… y el Real Decreto 386/1996…»
#   ARRASTRE «Quedan derogadas cuantas disposiciones de igual o inferior rango se opongan a lo
#             establecido en la presente ley.»   ← 3 de las 8 cláusulas del corpus son esto
#
# La de arrastre trae la palabra «ley», así que pedir solo la palabra no la distingue: eso fue
# un fallo de la primera versión de esta regla, detectado al revisar las ocho cláusulas del
# corpus una a una. No dice qué norma cae, luego no se puede verificar contra el archivo, luego
# no vale como evidencia — que es exactamente para lo que existe la evidencia.
#
# **Precio, y hay que escribirlo:** una norma derogada solo por su nombre, sin número («queda
# derogada la Ley de Enjuiciamiento Criminal»), no produce evidencia y por tanto tampoco
# veredicto, aunque el `<analisis>` la declare. Es pérdida de recall a cambio de que ningún span
# persistido sea ilegible para quien lo revise. No se ha visto ningún caso así en el corpus de
# tres días, y eso **no** es lo mismo que decir que no ocurra (regla de oro 8).
_NORMA_CITADA = re.compile(
    r"\b(?:ley(?:es)?\s+org[áa]nicas?|ley(?:es)?|real(?:es)?\s+decretos?"
    r"(?:\s+legislativos?|\s+leyes?)?|decretos?(?:\s+legislativos?)?|reglamentos?"
    r"|[óo]rden(?:es)?|directivas?)"
    r"[^.;:»]{0,40}?\b\d{1,4}\s*/\s*\d{2,4}\b",
    re.IGNORECASE,
)

# Construcciones **operativas** de nueva redacción: las que reescriben un precepto. Tercera
# familia (R-MOD-001), posible desde el ADR 0018 — antes se podía detectar la cláusula pero no
# había con qué enseñar qué cambiaba, y una alerta que dice «han modificado el artículo 4» sin
# poder decir de qué a qué no sirve para revisar nada.
#
# `se modifica` a secas queda fuera **por la misma razón que `se deroga`** en `_DEROGACION`, y
# el ruido es aún más abundante: media exposición de motivos del BOE dice «Real Decreto por el
# que se modifica el Real Decreto …» citando el título de otra norma. Lo que distingue a una
# modificación operativa es que **anuncia el texto que viene detrás**.
_MODIFICACION = re.compile(
    r"\bqueda(?:n)?\s+redactad[oa]s?\b"
    r"|\bcon\s+la\s+siguiente\s+redacci[óo]n\b"
    r"|\bpasa(?:n)?\s+a\s+tener\s+la\s+siguiente\s+redacci[óo]n\b"
    r"|\bqueda(?:n)?\s+modificad[oa]s?\s+(?:en\s+)?los?\s+siguientes\s+t[ée]rminos\b",
    re.IGNORECASE,
)

# Cómo se nombra un precepto. Se exige que aparezca **en la misma cláusula** que la
# construcción de supresión: sin este requisito, «se suprime la referencia a…» o una frase del
# preámbulo pasarían igual.
_PRECEPTO = re.compile(
    r"\b(?:art[íi]culos?|art\.|apartados?|t[íi]tulos?|cap[íi]tulos?|secci(?:[óo]n|ones)"
    r"|disposici(?:[óo]n|ones)|anexos?|p[áa]rrafos?|incisos?|ep[íi]grafes?)\b",
    re.IGNORECASE,
)

# Frontera de oración sobre el texto derivado, que viene en una sola línea con los espacios
# colapsados (`pipeline/texto.py`). Es lo que acota el span de evidencia a la cláusula que
# contiene la supresión, en vez de a una ventana de N caracteres que empieza a media frase.
#
# Dos detalles que costaron una pasada de prueba y por eso están escritos:
# - El cierre admite `»`, `”`, `"` y `)` además de `.;:`, porque el BOE cierra las redacciones
#   nuevas con `.»` y sin eso la cláusula siguiente arrastraba el artículo entero anterior.
# - El comienzo NO admite dígito. Si lo admitiera, «art. 33.4» y «Ley 4/2023, de 28 de
#   febrero» se partirían por la mitad, que es justo donde vive la cita del precepto.
_FRONTERA_ORACION = re.compile(r"(?<=[.;:»”\"\)])\s+(?=[«\"“(]|[A-ZÁÉÍÓÚÑ])")

# Un identificador de precepto reducido a su número: "24", "X", "36". Sirve **solo** para el
# diagnóstico de punteros (ver `corroborar`), nunca para decidir un veredicto.
_NUMERO_DE_PRECEPTO = re.compile(r"\b(?:\d{1,4}|[IVXLC]{1,7})\b")

# Topes de lo que puede acabar persistido. El texto archivado es dato no confiable de una
# fuente externa (regla de oro 1), así que un documento sin un solo punto —o con mil cláusulas
# de supresión— no puede convertirse en una fila de tamaño arbitrario en la base de datos y en
# la interfaz. Las cifras salen del corpus real: la cláusula más larga medida son 184
# caracteres y el documento con más supresiones tiene 12, así que hay dos órdenes de margen.
MAX_CARACTERES_EVIDENCIA = 1_000
MAX_EVIDENCIAS = 50


@dataclass(frozen=True)
class Evidencia:
    """Un rango de caracteres del texto archivado que sostiene un veredicto.

    Los offsets son absolutos sobre el texto derivado del documento entero, que es el mismo
    material que pide 7.5 para la trazabilidad de la extracción. No se recorta a una ventana ni
    se guarda solo el fragmento: el fragmento sin sus coordenadas no se puede volver a
    localizar en el archivo, y entonces "verificar contra la fuente" vuelve a ser "fiarse".
    """

    inicio: int
    fin: int
    fragmento: str

    def verifica(self, texto: str) -> bool:
        """¿El rango, recortado del texto archivado, es literalmente lo que dice el fragmento?

        Mismo control que 7.5 aplica a la salida del LLM, aquí aplicado a la nuestra. Una
        regla que emitiera unos offsets desplazados —el error fácil en cuanto haya ventanas o
        truncado— produciría una alerta que señala al párrafo equivocado del archivo, y eso es
        peor que no señalar nada.
        """
        return texto[self.inicio : self.fin] == self.fragmento


@dataclass(frozen=True)
class Diff:
    """Una redacción anterior y la nueva, tal como las archivó el ADR 0018.

    Llega como **dato ya leído**, no como una consulta: este módulo es puro y no toca la base de
    datos ni la red. Quien lo llama (`services/clasificacion.py`) traduce las filas de
    `version_norma` a esto.
    """

    norma_afectada: str
    bloque: str | None
    articulo: str | None
    texto_anterior: str | None
    texto_nuevo: str | None


@dataclass(frozen=True)
class Veredicto:
    """Lo que una regla concluye, con todo lo que hace falta para rebatirlo.

    `regla` y `evidencia` son el requisito de 7.6 y no son adorno: sin ellos, "¿por qué esto es
    un retroceso?" solo se puede contestar ejecutando nuestro código.
    """

    regla: str
    clasificacion: Clasificacion
    severidad: int
    confianza: float
    evidencia: tuple[Evidencia, ...]
    # Normas de la watchlist que este documento modifica o deroga, según el `<analisis>` del
    # propio BOE. Vacío en R-SUP-002.
    normas_vigiladas: tuple[str, ...] = ()
    # Diagnóstico de los punteros de la extracción (ADR 0016). **No participan en el
    # veredicto**: están aquí para poder medir si el modelo ve supresiones que las reglas no
    # ven, que es la condición que el ADR pone para reabrirse.
    punteros_corroborados: tuple[str, ...] = ()
    punteros_sin_corroborar: tuple[str, ...] = ()
    # Diagnóstico de R-MOD-001: términos directos del vocabulario que estaban en la redacción
    # anterior y no están en la nueva (ADR 0018). **Tampoco participa en el veredicto** — ver
    # `terminos_perdidos`, donde está el contraejemplo que lo impide.
    terminos_perdidos: tuple[str, ...] = ()
    # Cuántos preceptos de normas vigiladas trae el diff archivado. Va como cifra y no como
    # texto: los textos ya están en `version_norma`, y duplicarlos dentro de `deteccion` haría
    # que la misma cita viviera en dos sitios que pueden dejar de coincidir.
    preceptos_con_diff: int = 0
    version_reglas: str = field(default=VERSION_REGLAS)


def _fronteras(texto: str) -> tuple[list[int], list[int]]:
    """Las fronteras de oración del texto, una sola vez: (dónde acaban, dónde empiezan).

    Se calculan enteras y por adelantado **por corrección, no por rendimiento**. La versión
    anterior buscaba la frontera anterior con `finditer(texto, 0, posicion)`, y eso recorta la
    cadena en `posicion`: una frontera que termine justo ahí deja de encontrarse porque su
    lookahead se queda fuera del recorte. Consecuencia: dos construcciones de la misma oración
    devolvían dos cláusulas distintas —«Veinticuatro. Se suprime el Título XIV y se suprime el
    Título XV.» daba dos evidencias solapadas— y la deduplicación por rango no podía verlo. El
    rango de una oración tiene que depender de la oración, no de por dónde se la mire.
    """
    fines: list[int] = []
    comienzos: list[int] = []
    for frontera in _FRONTERA_ORACION.finditer(texto):
        comienzos.append(frontera.start())
        fines.append(frontera.end())
    return fines, comienzos


def _clausula(texto: str, posicion: int, fronteras: tuple[list[int], list[int]]) -> tuple[int, int]:
    """Rango de la oración que contiene `posicion`."""
    fines, comienzos = fronteras
    anterior = bisect.bisect_right(fines, posicion)
    siguiente = bisect.bisect_right(comienzos, posicion)
    inicio = fines[anterior - 1] if anterior else 0
    fin = comienzos[siguiente] if siguiente < len(comienzos) else len(texto)
    return inicio, fin


def _clausulas_con(
    texto: str, construccion: re.Pattern[str], acompanante: re.Pattern[str]
) -> tuple[Evidencia, ...]:
    """Cláusulas donde `construccion` aparece acompañada de `acompanante`, con sus offsets.

    El esqueleto que comparten las dos familias del catálogo: encontrar la construcción
    operativa, acotarla a su oración, exigir en esa misma oración la referencia que la hace
    verificable —un precepto para la supresión, una norma para la derogación— y emitir cada
    oración una sola vez aunque contenga dos construcciones.

    Está factorizado y no copiado por el mismo motivo que `services/cuerpo.py`: dos copias de
    este recorte son dos criterios de evidencia distintos en cuanto alguien toque una, y el
    span es lo único que un revisor lee para decidir. Los topes y el degradado tienen que ser
    los mismos para todas las reglas o el catálogo deja de ser un catálogo.

    Una cláusula desmesurada —un documento sin puntuación, por accidente o a propósito— se
    recorta a una ventana alrededor de la construcción encontrada, y entonces el acompañante se
    exige **dentro de la ventana**: si al recortar se pierde, la cláusula deja de valer como
    evidencia. Es la decisión conservadora correcta.
    """
    encontradas: list[Evidencia] = []
    vistas: set[tuple[int, int]] = set()
    fronteras = _fronteras(texto)
    for coincidencia in construccion.finditer(texto):
        inicio, fin = _clausula(texto, coincidencia.start(), fronteras)
        if fin - inicio > MAX_CARACTERES_EVIDENCIA:
            margen = (MAX_CARACTERES_EVIDENCIA - (coincidencia.end() - coincidencia.start())) // 2
            inicio = max(inicio, coincidencia.start() - margen)
            fin = min(fin, coincidencia.end() + margen)
        if (inicio, fin) in vistas:
            continue
        vistas.add((inicio, fin))
        fragmento = texto[inicio:fin]
        if acompanante.search(fragmento):
            encontradas.append(Evidencia(inicio=inicio, fin=fin, fragmento=fragmento))
        if len(encontradas) == MAX_EVIDENCIAS:
            break
    return tuple(encontradas)


def supresiones(texto: str) -> tuple[Evidencia, ...]:
    """Cláusulas del texto archivado que suprimen un precepto, con sus offsets.

    Dos condiciones, las dos necesarias: una construcción **operativa** de supresión y una
    referencia a precepto **en la misma cláusula**. Cada cláusula se emite una sola vez aunque
    contenga dos construcciones («Se suprime el Título XIV y se sustituye el Título XIII…»).
    """
    return _clausulas_con(texto, _SUPRESION, _PRECEPTO)


def derogaciones(texto: str) -> tuple[Evidencia, ...]:
    """Cláusulas del texto archivado que derogan una norma, con sus offsets.

    Mismas dos condiciones que `supresiones`, cambiando qué acompaña a la construcción: aquí se
    exige que la cláusula **nombre una norma**. Es lo que deja fuera la cláusula de arrastre
    («quedan derogadas cuantas disposiciones se opongan a lo dispuesto en este real decreto»),
    que aparece en casi toda norma reglamentaria y no dice qué cae: como evidencia no se puede
    verificar contra el archivo, que es para lo que existe la evidencia.
    """
    return _clausulas_con(texto, _DEROGACION, _NORMA_CITADA)


def modificaciones(texto: str) -> tuple[Evidencia, ...]:
    """Cláusulas del texto archivado que dan nueva redacción a un precepto, con sus offsets.

    Mismas dos condiciones que las otras dos familias: construcción **operativa** —una que
    anuncia el texto que viene detrás, no una que cite el título de otra norma— y una referencia
    a precepto en la misma cláusula.
    """
    return _clausulas_con(texto, _MODIFICACION, _PRECEPTO)


def terminos_perdidos(diffs: tuple[Diff, ...]) -> tuple[str, ...]:
    """Términos **directos** del vocabulario que estaban en la redacción anterior y ya no están.

    **Es un diagnóstico, no una entrada del veredicto**, exactamente igual que `corroborar` con
    los punteros del extractor. Se calcula porque es lo primero que quiere saber quien revisa
    —«¿qué ha desaparecido?»— y porque es reproducible: mismo vocabulario versionado que el
    prefiltro, mismos textos archivados.

    **Y no decide el signo, por un contraejemplo real que está en este mismo corpus.** Las leyes
    autonómicas de 2016 dicen «personas transexuales» y las reformas posteriores suelen decir
    «personas trans»: ahí desaparece un término directo y es modernización del lenguaje, no
    recorte. Al revés también pasa —el artículo 4 de la Ley 2/2016 madrileña cambia
    «identidad de género libremente manifestada» por «personas transexuales», y eso sí recorta—.
    La diferencia entre los dos casos no está en qué término desaparece sino en qué dice el
    precepto, y eso lo lee una persona. Convertir esta lista en un veredicto sería justamente lo
    que la regla de oro 2 prohíbe.

    **Lo que dice, con precisión, para que nadie lo lea de más:** que el término estaba en la
    redacción **anterior de ese precepto** y no está en la **nueva del mismo precepto**. No dice
    que haya desaparecido de la ley — puede seguir en otro artículo que nadie tocó. Es una pista
    de por dónde empezar a leer, no un recuento de lo perdido.
    """
    perdidos: list[str] = []
    for diff in diffs:
        if not diff.texto_anterior:
            continue
        antes = set(prefiltro.terminos_presentes(diff.texto_anterior, solo_directos=True))
        despues = set(prefiltro.terminos_presentes(diff.texto_nuevo or "", solo_directos=True))
        perdidos.extend(sorted(antes - despues))
    return tuple(dict.fromkeys(perdidos))


def corroborar(
    punteros: tuple[str, ...], evidencia: tuple[Evidencia, ...]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Reparte los punteros del extractor en (corroborados, sin corroborar).

    **Es un diagnóstico, no una entrada del veredicto.** Un puntero que el texto archivado no
    corrobora no produce clasificación ninguna —no puede, porque las reglas no lo miran— y eso
    es exactamente la condición que el ADR 0016 pone para que un puntero alucinado sea inerte
    (regla de oro 10). Se cuenta para poder contestar la única pregunta que reabriría ese ADR:
    ¿ve el modelo supresiones que estas reglas no ven?

    La correspondencia se hace por el número del precepto («art. 24» ↔ «El artículo 24 queda
    suprimido») y es deliberadamente tosca: afinarla no cambiaría ningún veredicto, solo el
    diagnóstico.
    """
    corroborados: list[str] = []
    sin_corroborar: list[str] = []
    for puntero in punteros:
        numeros = set(_NUMERO_DE_PRECEPTO.findall(puntero))
        encaja = bool(numeros) and any(
            numeros & set(_NUMERO_DE_PRECEPTO.findall(prueba.fragmento)) for prueba in evidencia
        )
        (corroborados if encaja else sin_corroborar).append(puntero)
    return tuple(corroborados), tuple(sin_corroborar)


def _vigiladas(referencias: tuple[ReferenciaAnterior, ...], lista: Watchlist) -> tuple[str, ...]:
    """Normas de la watchlist que este documento **toca** según el `<analisis>` oficial.

    Se exige el verbo modificativo (`MODIFICA`, `DEROGA`, `SUPRIME`…) y no la mera cita, por lo
    mismo que en el eje referencial del prefiltro: citar la Ley 4/2023 en el temario de una
    oposición no es tocarla.
    """
    return tuple(
        dict.fromkeys(
            referencia.identificador
            for referencia in referencias
            if referencia.es_modificativa and lista.contiene(referencia.identificador)
        )
    )


def _derogadas(referencias: tuple[ReferenciaAnterior, ...], lista: Watchlist) -> tuple[str, ...]:
    """Normas de la watchlist que este documento **deroga**, según el `<analisis>` oficial.

    Más estricto que `_vigiladas`: exige el verbo `DEROGA` y no cualquiera de los modificativos.
    R-DER-001 habla de la desaparición de una norma vigilada entera, y `MODIFICA` no lo es; sin
    esta distinción la regla dispararía sobre cualquier retoque y su severidad 4 dejaría de
    significar nada.
    """
    return tuple(
        dict.fromkeys(
            referencia.identificador
            for referencia in referencias
            if referencia.verbo == "DEROGA" and lista.contiene(referencia.identificador)
        )
    )


def clasificar(
    texto: str,
    *,
    referencias: tuple[ReferenciaAnterior, ...] = (),
    lista: Watchlist,
    punteros: tuple[str, ...] = (),
    diffs: tuple[Diff, ...] = (),
) -> Veredicto | None:
    """Aplica el catálogo. Devuelve `None` cuando ninguna regla dispara.

    `None` significa "este catálogo no tiene nada que decir de esta norma", que no es lo mismo
    que "es neutra": hoy el catálogo solo sabe de supresiones. Por eso el servicio que lo llama
    no escribe un veredicto de "neutro" cuando esto devuelve `None` — inventaría una conclusión
    que nadie ha sacado.

    ## Los dos veredictos y el supuesto que separa uno de otro

    - **R-SUP-001 → `retroceso`.** Hay supresión de precepto *y* el `<analisis>` del BOE declara
      que este documento modifica o deroga una norma de `config/watchlist.json`. El supuesto,
      dicho para poder discutirlo: la watchlist es un catálogo de normas **protectoras**, así
      que suprimir preceptos de una de ellas es presuntamente quitar protección. Su modo de
      fallo conocido es el simétrico —suprimir un precepto *restrictivo* de una norma vigilada
      sería un avance y esta regla lo llamaría retroceso—; se acepta porque el veredicto no se
      publica sin gate humano (regla de oro 4) y porque el gold set es lo que puede medirlo.
    - **R-DER-001 → `indeterminado`.** El `<analisis>` declara que este documento **deroga** una
      norma de la watchlist, y el cuerpo trae la cláusula operativa que lo hace. Severidad alta
      —desaparece una norma vigilada entera— y **sin signo, a propósito**: ver la sección «La
      segunda familia» de la cabecera. Derogar es lo que hace tanto quien desmonta una ley como
      quien la sustituye por otra mejor, y cuál de las dos cosas es exige el diff contra
      `version_norma`, que está vacía.
    - **R-MOD-001 → `indeterminado`.** El documento da **nueva redacción** a un precepto y el
      `<analisis>` declara que modifica una norma de la watchlist. Es la familia que abre el ADR
      0018, y **sigue sin afirmar signo**, por lo mismo que R-DER-001: que un artículo se
      reescriba no dice hacia dónde. Lo que cambia respecto a antes no es el veredicto, es la
      evidencia — el diff archivado permite enseñar el antes y el después literales, y
      `terminos_perdidos` dice qué vocabulario protector desapareció. Eso convierte una alerta
      que decía «han tocado el artículo 4» en una que enseña que pasó de «reconocimiento del
      derecho a la identidad de género libremente manifestada» a otra cosa. **Dispara aunque el
      diff todavía no esté** (la consolidación llega con retraso, ADR 0018): la modificación de
      una norma vigilada merece revisión humana igual, y sin diff la alerta trae la cláusula.
    - **R-SUP-002 → `indeterminado`.** Hay supresión pero no se identifica norma vigilada. Es
      el umbral de recall alto de 7.6: entra en la cola de revisión sin afirmar nada. Se
      distingue del centinela del ADR 0009 (`indeterminado`/`heuristica`/`regla_aplicada NULL`)
      justamente por traer regla y evidencia.

    ## Orden de las reglas, que no es arbitrario

    Se evalúan de más específica a menos, y cada una emite **su propia** evidencia: la que
    sostiene *ese* veredicto, no todas las cláusulas del documento. R-SUP-001 va primero porque
    es la única que afirma un signo; R-DER-001 antes que R-SUP-002 porque una norma vigilada
    derogada pesa más que una supresión suelta en una norma que no lo está.

    `severidad` y `confianza` son **atributos declarados de cada regla, provisionales y sin
    calibrar**, del mismo modo que `UMBRAL_DIRECTOS_RELEVANTE` en el prefiltro: no salen de
    ninguna medición y no se citan como dato hasta que el gold set los recalibre. Están porque
    las columnas existen y ponerlas a cero las haría leerse como "confianza nula".
    """
    supresion = supresiones(texto)
    derogacion = derogaciones(texto)
    modificacion = modificaciones(texto)
    if not supresion and not derogacion and not modificacion:
        return None

    vigiladas = _vigiladas(referencias, lista)
    derogadas = _derogadas(referencias, lista)

    # El diff archivado acompaña a **toda** regla que identifique una norma vigilada, no solo a
    # R-MOD-001. Lo enseñó la primera pasada real: las dos reformas madrileñas disparan
    # R-SUP-001, que va antes en el orden, así que atar el diff a R-MOD-001 dejaba el caso
    # insignia del proyecto sin el antes y el después justo en la alerta donde más falta hacen.
    # Sigue sin decidir nada: es material para quien revisa, en las tres reglas igual.
    propios = tuple(d for d in diffs if d.norma_afectada in vigiladas)
    perdidos = terminos_perdidos(propios)

    if supresion and vigiladas:
        corroborados, sin_corroborar = corroborar(punteros, supresion)
        return Veredicto(
            regla=R_SUP_NORMA_VIGILADA,
            clasificacion=Clasificacion.RETROCESO,
            severidad=4,
            confianza=0.8,
            evidencia=supresion,
            normas_vigiladas=vigiladas,
            punteros_corroborados=corroborados,
            punteros_sin_corroborar=sin_corroborar,
            terminos_perdidos=perdidos,
            preceptos_con_diff=len(propios),
        )

    if derogacion and derogadas:
        corroborados, sin_corroborar = corroborar(punteros, derogacion)
        derogados = tuple(d for d in diffs if d.norma_afectada in derogadas)
        return Veredicto(
            regla=R_DER_NORMA_VIGILADA,
            clasificacion=Clasificacion.INDETERMINADO,
            severidad=4,
            confianza=0.5,
            evidencia=derogacion,
            normas_vigiladas=derogadas,
            punteros_corroborados=corroborados,
            punteros_sin_corroborar=sin_corroborar,
            terminos_perdidos=terminos_perdidos(derogados),
            preceptos_con_diff=len(derogados),
        )

    if modificacion and vigiladas:
        corroborados, sin_corroborar = corroborar(punteros, modificacion)
        return Veredicto(
            regla=R_MOD_NORMA_VIGILADA,
            clasificacion=Clasificacion.INDETERMINADO,
            severidad=3,
            confianza=0.5,
            evidencia=modificacion,
            normas_vigiladas=vigiladas,
            punteros_corroborados=corroborados,
            punteros_sin_corroborar=sin_corroborar,
            terminos_perdidos=perdidos,
            preceptos_con_diff=len(propios),
        )

    if supresion:
        corroborados, sin_corroborar = corroborar(punteros, supresion)
        return Veredicto(
            regla=R_SUP_SIN_NORMA_VIGILADA,
            clasificacion=Clasificacion.INDETERMINADO,
            severidad=2,
            confianza=0.4,
            evidencia=supresion,
            punteros_corroborados=corroborados,
            punteros_sin_corroborar=sin_corroborar,
        )
    return None
