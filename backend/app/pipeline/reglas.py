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

Porque es la única clasificable con lo que hoy está archivado. Una norma modificativa del BOE
publica la redacción **nueva** («El artículo 4 queda redactado como sigue: …»), no la vieja, y
`version_norma` está vacía: el diff de una *modificación* todavía no se puede construir. La
supresión, en cambio, no necesita texto anterior — el hecho es que el precepto deja de existir.

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
from app.pipeline.referencias import ReferenciaAnterior
from app.pipeline.watchlist import Watchlist

# Sube cuando cambie cualquier patrón, umbral o veredicto de este fichero. Se guarda junto a
# cada detección y obliga a reevaluar lo anterior, igual que `VERSION_VOCABULARIO` y la versión
# de la watchlist: sin esto, dos alertas de fechas distintas no serían comparables porque no se
# sabría si las produjo el mismo catálogo.
VERSION_REGLAS = "2026.08.09"

# --- Identificadores estables de regla ---------------------------------------------------
# Van a `deteccion.regla_aplicada` y son parte del contrato de auditoría: no se renombran. Si
# una regla cambia de criterio, sube `VERSION_REGLAS`; si se sustituye por otra distinta, se
# usa un identificador nuevo y el viejo queda retirado, nunca reutilizado con otro significado.
R_SUP_NORMA_VIGILADA = "R-SUP-001"
R_SUP_SIN_NORMA_VIGILADA = "R-SUP-002"

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


def supresiones(texto: str) -> tuple[Evidencia, ...]:
    """Cláusulas del texto archivado que suprimen un precepto, con sus offsets.

    Dos condiciones, las dos necesarias: una construcción **operativa** de supresión y una
    referencia a precepto **en la misma cláusula**. Cada cláusula se emite una sola vez aunque
    contenga dos construcciones («Se suprime el Título XIV y se sustituye el Título XIII…»).

    Una cláusula desmesurada —un documento sin puntuación, por accidente o a propósito— se
    recorta a una ventana alrededor de la construcción encontrada, y entonces la referencia a
    precepto se exige **dentro de la ventana**: si al recortar se pierde, la cláusula deja de
    valer como evidencia. Es la decisión conservadora correcta, porque el span es justamente lo
    que un revisor va a leer para decidir.
    """
    encontradas: list[Evidencia] = []
    vistas: set[tuple[int, int]] = set()
    fronteras = _fronteras(texto)
    for coincidencia in _SUPRESION.finditer(texto):
        inicio, fin = _clausula(texto, coincidencia.start(), fronteras)
        if fin - inicio > MAX_CARACTERES_EVIDENCIA:
            margen = (MAX_CARACTERES_EVIDENCIA - (coincidencia.end() - coincidencia.start())) // 2
            inicio = max(inicio, coincidencia.start() - margen)
            fin = min(fin, coincidencia.end() + margen)
        if (inicio, fin) in vistas:
            continue
        vistas.add((inicio, fin))
        fragmento = texto[inicio:fin]
        if _PRECEPTO.search(fragmento):
            encontradas.append(Evidencia(inicio=inicio, fin=fin, fragmento=fragmento))
        if len(encontradas) == MAX_EVIDENCIAS:
            break
    return tuple(encontradas)


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


def clasificar(
    texto: str,
    *,
    referencias: tuple[ReferenciaAnterior, ...] = (),
    lista: Watchlist,
    punteros: tuple[str, ...] = (),
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
    - **R-SUP-002 → `indeterminado`.** Hay supresión pero no se identifica norma vigilada. Es
      el umbral de recall alto de 7.6: entra en la cola de revisión sin afirmar nada. Se
      distingue del centinela del ADR 0009 (`indeterminado`/`heuristica`/`regla_aplicada NULL`)
      justamente por traer regla y evidencia.

    `severidad` y `confianza` son **atributos declarados de cada regla, provisionales y sin
    calibrar**, del mismo modo que `UMBRAL_DIRECTOS_RELEVANTE` en el prefiltro: no salen de
    ninguna medición y no se citan como dato hasta que el gold set los recalibre. Están porque
    las columnas existen y ponerlas a cero las haría leerse como "confianza nula".
    """
    evidencia = supresiones(texto)
    if not evidencia:
        return None

    corroborados, sin_corroborar = corroborar(punteros, evidencia)
    vigiladas = _vigiladas(referencias, lista)

    if vigiladas:
        return Veredicto(
            regla=R_SUP_NORMA_VIGILADA,
            clasificacion=Clasificacion.RETROCESO,
            severidad=4,
            confianza=0.8,
            evidencia=evidencia,
            normas_vigiladas=vigiladas,
            punteros_corroborados=corroborados,
            punteros_sin_corroborar=sin_corroborar,
        )
    return Veredicto(
        regla=R_SUP_SIN_NORMA_VIGILADA,
        clasificacion=Clasificacion.INDETERMINADO,
        severidad=2,
        confianza=0.4,
        evidencia=evidencia,
        punteros_corroborados=corroborados,
        punteros_sin_corroborar=sin_corroborar,
    )
