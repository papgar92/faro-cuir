"""Etapa 1 del pipeline: prefiltro de tres ejes (CLAUDE.md secciones 7.2 y 7.3).

**Qué decide este filtro cambió con el ADR 0011 y es lo primero que hay que entender.** Ya no
decide qué se descarga —se descarga el día entero, porque un día de BOE cuesta 10 s de red—
sino **qué entra en el LLM y en qué orden**, porque una extracción cuesta 133,9 s. El prefiltro
dejó de ser la puerta de la red y pasó a ser la puerta del modelo.

**Ajustado a recall máximo, no a precisión.** Mejor 50 falsos positivos que 1 falso negativo:
un falso positivo cuesta un puesto en la cola; un falso negativo es una norma que recorta un
derecho y que el sistema no llegó a mirar nunca. No son errores comparables, así que el filtro
no se equilibra: se sesga.

Dos ejes, **combinados con OR y jamás con AND** (7.3). Con AND, dos filtros de alto recall se
convierten en uno de bajo recall:

- **Eje léxico**: ~90 términos con variantes morfológicas y clínicas antiguas.
- **Eje referencial**: la norma modifica o deroga algo de `config/watchlist.json`. Cubre el
  agujero estructural del diccionario — una instrucción que elimina un derecho no dice
  "identidad de género", dice "se modifica el epígrafe 4.3 del anexo II".

El eje 3 (semántico por embeddings) está fuera de alcance a propósito (sección 8).

## El corte de términos directos, y por qué no puede hacer daño

Al evaluarse sobre el **texto íntegro** en vez del título, el eje léxico cambia de calibración
por completo: sobre 200.000 caracteres, la *presencia* de un término no discrimina —una
convocatoria de oposición cita la Ley 4/2023 en el temario— así que hay que contar **cuántos**
términos directos distintos aparecen.

Ese corte **está sin validar y solo lo puede validar el gold set**. Por eso está construido de
forma que equivocarse salga barato: el umbral separa `RELEVANTE` de `SOSPECHA`, **nunca decide
un descarte**. Una norma con un solo término directo entra igualmente en la cola del extractor,
solo que la última. Si el umbral está mal, el coste es latencia; nunca un falso negativo.

Y sobre el título solo —sin texto íntegro— **no se descarta jamás** (7.1): el título es
exactamente lo que un retroceso silencioso puede redactar de forma anodina, así que decidir
sobre él es decidir sobre lo que el redactor controla.

El módulo es **puro**: no toca la base de datos ni la red. Persistir es trabajo de
`services/prefiltro.py`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from app.models.norma import EjePrefiltro, EstadoPrefiltro
from app.pipeline.referencias import ReferenciaAnterior
from app.pipeline.watchlist import Watchlist

# Versión del vocabulario. Se guarda junto a cada resultado para que una norma evaluada con
# un diccionario viejo sea reconocible y se pueda reevaluar. Súbela SIEMPRE que cambien los
# términos o el umbral: sin eso, "esta norma se descartó" deja de ser comprobable.
VERSION_VOCABULARIO = "2026.08.08"

# Cuántos términos DIRECTOS distintos hacen falta, sobre el texto íntegro, para que una norma
# entre como RELEVANTE en vez de como SOSPECHA.
#
# **PROVISIONAL. No publiques este número como si estuviera comprobado.** Sale de los cuatro
# documentos que se midieron en el ADR 0011 y cuatro documentos no calibran nada:
#
#     Ley 4/2023 (positivo conocido) ......... 43 términos
#     LO 1/2023 (negativo difícil) ........... 11
#     Ley 3/2023 de Empleo (negativo) ......... 9
#     Resolución de Sanidad (negativo) ........ 3
#
# Ojo, que es una trampa fácil: esos cuatro números son de **todos** los términos, directos y
# de contexto, mientras que aquí se cuentan solo los directos. No son directamente
# comparables, así que el 8 no es "el punto medio entre 11 y 43" — es un valor de arranque
# puesto para que el sistema funcione mientras no haya con qué calibrarlo.
#
# Lo único que sostiene esta elección es que **no puede causar un falso negativo** (ver el
# encabezado). Validarlo es trabajo del gold set.
UMBRAL_DIRECTOS_RELEVANTE = 8


class Categoria(StrEnum):
    """Para qué sirve cada término. No cambia la decisión, sí permite medir el ruido."""

    # Coincidir con uno de estos es señal suficiente por sí sola: son términos que no
    # aparecen en un título del BOE por casualidad.
    DIRECTO = "directo"
    # Términos del dominio donde el retroceso se materializa (sanidad, educación, registro
    # civil) pero que también salen en normas que no van de esto. Se aceptan igual —recall
    # máximo— y se etiquetan aparte para poder medir cuánto ruido aporta cada uno y decidir
    # con datos, no de oídas, si alguno hay que ajustar.
    CONTEXTO = "contexto"


# Términos en minúsculas y sin tildes: la normalización de `_normalizar` se aplica igual al
# texto y al término, así que aquí se escriben ya en esa forma.
#
# Cada entrada cubre una forma de nombrar lo mismo, incluidas las que usa quien redacta para
# no nombrarlo. Se incluyen a propósito las variantes antiguas o clínicas ("disforia de
# genero", "transexualidad") porque una norma que recorta derechos suele usar el vocabulario
# de hace veinte años, no el actual.
_VOCABULARIO: dict[str, Categoria] = {
    # --- Colectivo e identidad ------------------------------------------------------------
    "lgtbi": Categoria.DIRECTO,
    "lgtb": Categoria.DIRECTO,
    "lgtbiq": Categoria.DIRECTO,
    "lgbti": Categoria.DIRECTO,
    "lgbt": Categoria.DIRECTO,
    "homosexual": Categoria.DIRECTO,
    "homosexualidad": Categoria.DIRECTO,
    "bisexual": Categoria.DIRECTO,
    "lesbiana": Categoria.DIRECTO,
    "lesbianas": Categoria.DIRECTO,
    "gais": Categoria.DIRECTO,
    "transexual": Categoria.DIRECTO,
    "transexuales": Categoria.DIRECTO,
    "transexualidad": Categoria.DIRECTO,
    "transgenero": Categoria.DIRECTO,
    "intersexual": Categoria.DIRECTO,
    "intersexualidad": Categoria.DIRECTO,
    "no binario": Categoria.DIRECTO,
    "no binaria": Categoria.DIRECTO,
    "personas trans": Categoria.DIRECTO,
    "poblacion trans": Categoria.DIRECTO,
    "menores trans": Categoria.DIRECTO,
    "queer": Categoria.DIRECTO,
    # --- Identidad y expresión de género ---------------------------------------------------
    "identidad de genero": Categoria.DIRECTO,
    "identidad sexual": Categoria.DIRECTO,
    "expresion de genero": Categoria.DIRECTO,
    "autodeterminacion de genero": Categoria.DIRECTO,
    "libre desarrollo de la personalidad": Categoria.CONTEXTO,
    "disforia de genero": Categoria.DIRECTO,
    "identidad de genero sentida": Categoria.DIRECTO,
    "genero sentido": Categoria.DIRECTO,
    "sexo sentido": Categoria.DIRECTO,
    # --- Orientación ------------------------------------------------------------------------
    "orientacion sexual": Categoria.DIRECTO,
    # Las formas pegadas («afectivosexual») se listan aparte porque la normalización solo
    # colapsa separadores: sin guion ni espacio no hay nada que colapsar, y sin estas
    # entradas se perderían en silencio. Un test lo fija.
    "orientacion afectivo sexual": Categoria.DIRECTO,
    "orientacion afectivosexual": Categoria.DIRECTO,
    "diversidad sexual": Categoria.DIRECTO,
    "diversidad afectivo sexual": Categoria.DIRECTO,
    "diversidad afectivosexual": Categoria.DIRECTO,
    # --- Discriminación y odio ---------------------------------------------------------------
    "lgtbifobia": Categoria.DIRECTO,
    "lgtbfobia": Categoria.DIRECTO,
    "homofobia": Categoria.DIRECTO,
    "transfobia": Categoria.DIRECTO,
    "bifobia": Categoria.DIRECTO,
    "lesbofobia": Categoria.DIRECTO,
    "delitos de odio": Categoria.CONTEXTO,
    "discriminacion por razon de sexo": Categoria.CONTEXTO,
    "igualdad de trato": Categoria.CONTEXTO,
    "no discriminacion": Categoria.CONTEXTO,
    # --- Terapias de conversión --------------------------------------------------------------
    "terapia de conversion": Categoria.DIRECTO,
    "terapias de conversion": Categoria.DIRECTO,
    "terapias de aversion": Categoria.DIRECTO,
    "terapias reparativas": Categoria.DIRECTO,
    # --- Educativo ---------------------------------------------------------------------------
    "coeducacion": Categoria.DIRECTO,
    "coeducativo": Categoria.DIRECTO,
    "diversidad familiar": Categoria.DIRECTO,
    "diversidad familiar y afectiva": Categoria.DIRECTO,
    "educacion afectivo sexual": Categoria.DIRECTO,
    "educacion afectivosexual": Categoria.DIRECTO,
    "educacion sexual": Categoria.CONTEXTO,
    "convivencia escolar": Categoria.CONTEXTO,
    "acoso escolar": Categoria.CONTEXTO,
    "plan de igualdad": Categoria.CONTEXTO,
    # Con ñ: `_normalizar` la preserva, así que el término debe escribirse con ella o no
    # coincidiría nunca. Hay un test que lo fija.
    "protocolo de acompañamiento": Categoria.DIRECTO,
    "acompañamiento a la identidad de genero": Categoria.DIRECTO,
    # --- Sanitario ----------------------------------------------------------------------------
    "cartera de servicios": Categoria.CONTEXTO,
    "cartera comun de servicios": Categoria.CONTEXTO,
    "unidad de identidad de genero": Categoria.DIRECTO,
    "tratamiento hormonal": Categoria.DIRECTO,
    "hormonacion": Categoria.DIRECTO,
    "bloqueadores de la pubertad": Categoria.DIRECTO,
    "cirugia de reasignacion": Categoria.DIRECTO,
    "reasignacion de sexo": Categoria.DIRECTO,
    "reproduccion humana asistida": Categoria.CONTEXTO,
    "reproduccion asistida": Categoria.CONTEXTO,
    # --- Documental / registral ----------------------------------------------------------------
    "rectificacion registral": Categoria.DIRECTO,
    "rectificacion registral del sexo": Categoria.DIRECTO,
    "mencion registral del sexo": Categoria.DIRECTO,
    "mencion del sexo": Categoria.DIRECTO,
    "cambio de nombre": Categoria.CONTEXTO,
    "registro civil": Categoria.CONTEXTO,
    "filiacion": Categoria.CONTEXTO,
    "familias homoparentales": Categoria.DIRECTO,
    "homoparental": Categoria.DIRECTO,
    # --- Deportivo ------------------------------------------------------------------------------
    "categoria femenina": Categoria.CONTEXTO,
    "competicion femenina": Categoria.CONTEXTO,
}


def _normalizar(texto: str) -> str:
    """Baja a minúsculas, quita tildes y colapsa cualquier cosa que no sea letra o dígito.

    Lo tercero es lo que importa: en el BOE la misma idea aparece como «afectivo-sexual»,
    «afectivo sexual» y «afectivosexual», y con comillas angulares en medio. Al convertir
    todo separador en un espacio único, un solo término del vocabulario cubre las variantes
    en vez de tener que enumerarlas.

    La ñ se preserva: quitarle la tilde a `acompañamiento` lo convertiría en `acompanamiento`
    y ese es justamente el término que se escribe en el diccionario, así que ambos lados
    acaban en la misma forma.
    """
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    sin_tildes = "".join(
        caracter
        for caracter in descompuesto
        # Se conserva la tilde de la ñ (U+0303) para no fusionar `ano`/`año`; el resto de
        # marcas diacríticas se descartan.
        if unicodedata.category(caracter) != "Mn" or caracter == "̃"
    )
    recompuesto = unicodedata.normalize("NFC", sin_tildes)
    return " ".join(re.sub(r"[^0-9a-zñ]+", " ", recompuesto).split())


# El vocabulario ya se escribe normalizado, pero se vuelve a pasar por `_normalizar` para que
# un término mal escrito (con tilde, con guion) no deje de coincidir nunca en silencio.
_VOCABULARIO_NORMALIZADO: dict[str, tuple[str, Categoria]] = {
    _normalizar(termino): (termino, categoria) for termino, categoria in _VOCABULARIO.items()
}


@dataclass(frozen=True)
class ResultadoPrefiltro:
    estado: EstadoPrefiltro
    # Términos del vocabulario que han coincidido, en el orden en que se escriben en el
    # diccionario. Vacío si se descarta.
    terminos: tuple[str, ...]
    # Qué ejes dispararon. Vacío si se descarta. Lista y no valor único porque van en OR y
    # pueden coincidir los dos, y saber que coincidieron ambos es un dato distinto.
    ejes: tuple[EjePrefiltro, ...]
    # Términos DIRECTOS distintos contados. Es la magnitud del corte, y se expone para poder
    # recalibrarlo con el gold set sin recontar 436 documentos.
    directos: int
    # Normas de la watchlist que esta disposición modifica o deroga.
    referencias_watchlist: tuple[str, ...]
    version: str
    version_watchlist: str | None

    @property
    def relevante(self) -> bool:
        return self.estado is EstadoPrefiltro.RELEVANTE

    @property
    def entra_en_la_cola(self) -> bool:
        """Si acabará pasando por el LLM. **Esto y no `relevante` es la cola del extractor.**

        `relevante` sigue existiendo porque hay código y tests que preguntan por él, pero
        filtrar la cola por `relevante` perdería en silencio todo lo marcado como sospecha.
        """
        return self.estado.entra_en_la_cola_del_extractor

    @property
    def solo_por_contexto(self) -> bool:
        """True si pasó únicamente por términos genéricos.

        Mide cuánto ruido mete la lista de contexto, y por tanto qué se puede afinar sin tocar
        el recall de los términos directos.
        """
        return bool(self.terminos) and all(
            _VOCABULARIO_NORMALIZADO[_normalizar(t)][1] is Categoria.CONTEXTO for t in self.terminos
        )


def _contiene(texto_normalizado: str, termino_normalizado: str) -> bool:
    """Busca el término respetando límites de palabra.

    Sin esto, `lgtb` coincidiría dentro de cualquier palabra que lo contuviera y `trans`
    dispararía con «transporte», «transitoria» o «transparencia», que en el BOE salen cada
    día. Como el texto ya está normalizado a palabras separadas por un espacio, basta con
    exigir espacio (o extremo) a cada lado.
    """
    patron = rf"(?:^| ){re.escape(termino_normalizado)}(?:$| )"
    return re.search(patron, texto_normalizado) is not None


def terminos_presentes(texto: str, *, solo_directos: bool = False) -> tuple[str, ...]:
    """Qué términos del vocabulario aparecen en un texto. Sin decidir nada.

    Se saca del cuerpo de `evaluar` para que el catálogo de reglas (7.6) pueda preguntar lo
    mismo sobre otro material —las dos redacciones de un artículo modificado, ADR 0018— **con
    el mismo vocabulario y la misma normalización**. Dos formas de contar términos serían dos
    vocabularios en cuanto alguien tocara uno, y entonces "este término estaba y ya no está"
    dejaría de ser comprobable.

    No decide: devuelve presencia. Quien llame pone el significado.
    """
    normalizado = _normalizar(texto)
    return tuple(
        original
        for termino, (original, categoria) in _VOCABULARIO_NORMALIZADO.items()
        if (not solo_directos or categoria is Categoria.DIRECTO) and _contiene(normalizado, termino)
    )


def evaluar(
    titulo: str,
    *,
    organo_emisor: str | None = None,
    texto_integro: str | None = None,
    referencias: tuple[ReferenciaAnterior, ...] = (),
    lista: Watchlist | None = None,
) -> ResultadoPrefiltro:
    """Aplica los dos ejes del prefiltro y decide el estado.

    `texto_integro=None` significa **fase 1**: solo se ha visto el sumario. En ese caso el
    resultado nunca puede ser `DESCARTADA` (CLAUDE.md 7.1) — como mucho `PENDIENTE`, que es
    "sigue esperando a que alguien lea el documento". El título es exactamente lo que un
    retroceso silencioso puede redactar de forma anodina.

    El órgano emisor entra siempre en el texto examinado porque a veces es donde está la
    señal: una resolución de la «Dirección General de Igualdad y Diversidad» puede tener un
    título puramente administrativo. Añadirlo solo puede subir el recall.
    """
    sobre_texto_integro = texto_integro is not None
    base = texto_integro if sobre_texto_integro else titulo
    coincidencias = terminos_presentes(f"{base} {organo_emisor or ''}")
    directos = sum(
        1
        for termino in coincidencias
        if _VOCABULARIO_NORMALIZADO[_normalizar(termino)][1] is Categoria.DIRECTO
    )

    # --- Eje 2: referencial. Se evalúa aunque el léxico no dispare; van en OR. --------------
    tocadas: tuple[str, ...] = ()
    if lista is not None:
        tocadas = tuple(
            referencia.identificador
            for referencia in referencias
            # `es_modificativa` es lo que separa "toca esta norma" de "la cita en el temario".
            if referencia.es_modificativa and lista.contiene(referencia.identificador)
        )

    ejes: list[EjePrefiltro] = []
    if coincidencias:
        ejes.append(EjePrefiltro.LEXICO)
    if tocadas:
        ejes.append(EjePrefiltro.REFERENCIAL)

    version_watchlist = lista.version if lista is not None else None

    def resultado(estado: EstadoPrefiltro) -> ResultadoPrefiltro:
        descarta = estado in (EstadoPrefiltro.DESCARTADA, EstadoPrefiltro.PENDIENTE)
        return ResultadoPrefiltro(
            estado=estado,
            # Al descartar se guarda lista vacía y no los términos: no hubo ninguno. Y al
            # quedar pendiente tampoco se guardan, porque todavía no es un veredicto.
            terminos=() if descarta else coincidencias,
            ejes=() if descarta else tuple(ejes),
            directos=directos,
            referencias_watchlist=tocadas,
            version=VERSION_VOCABULARIO,
            version_watchlist=version_watchlist,
        )

    # --- Decisión. El orden importa y es el de la fuerza de la señal. -----------------------
    if tocadas:
        # Modificar una norma de la watchlist pasa el filtro **por definición, diga lo que
        # diga su texto** (7.3). No se compara con el umbral léxico: son ejes distintos.
        return resultado(EstadoPrefiltro.RELEVANTE)

    if not coincidencias:
        # Sin señal de ningún eje. Solo se puede descartar habiendo leído el documento.
        return resultado(
            EstadoPrefiltro.DESCARTADA if sobre_texto_integro else EstadoPrefiltro.PENDIENTE
        )

    if not sobre_texto_integro:
        # Fase 1: el título sirve para priorizar, nunca para descartar. Un término directo en
        # el título es señal fuerte —así se encontró la Ley 4/2023— y el umbral de conteo no
        # se aplica aquí: ningún título contiene ocho términos distintos.
        return resultado(EstadoPrefiltro.RELEVANTE if directos else EstadoPrefiltro.SOSPECHA)

    # Fase 2, sobre el texto íntegro: el conteo separa el que regula del que solo cita.
    # **Por debajo del umbral no se descarta, se pospone.**
    return resultado(
        EstadoPrefiltro.RELEVANTE
        if directos >= UMBRAL_DIRECTOS_RELEVANTE
        else EstadoPrefiltro.SOSPECHA
    )
