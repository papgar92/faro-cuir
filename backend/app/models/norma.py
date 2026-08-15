from __future__ import annotations

import datetime
import enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.documento import Documento


class RangoNorma(enum.StrEnum):
    LEY = "ley"
    DECRETO = "decreto"
    ORDEN = "orden"
    INSTRUCCION = "instruccion"
    RESOLUCION = "resolucion"
    PROPOSICION = "proposicion"


class AmbitoNorma(enum.StrEnum):
    """Ámbito sobre el que actúa la norma. Vocabulario de CLAUDE.md sección 5.

    Estos son los ámbitos donde el retroceso silencioso se materializa en la práctica: la
    cartera de servicios sanitarios, el currículo educativo, el acceso al empleo, y el
    procedimiento de rectificación registral de sexo y nombre (`documental`).
    """

    SANITARIO = "sanitario"
    EDUCATIVO = "educativo"
    LABORAL = "laboral"
    DOCUMENTAL = "documental"
    DEPORTIVO = "deportivo"
    GENERAL = "general"


class EstadoPrefiltro(enum.StrEnum):
    """Resultado de la etapa 1 del pipeline sobre una norma (CLAUDE.md sección 7.2).

    Vive aquí y no en `pipeline/prefiltro.py` para que la dependencia vaya en la dirección
    correcta: el pipeline conoce el modelo, no al revés.

    `PENDIENTE` es un estado real, no un hueco: una norma ingerida antes de que existiera el
    prefiltro —o después de subir la versión del vocabulario— está sin evaluar, y eso no es
    lo mismo que estar descartada.

    **Qué deciden estos estados cambió con el ADR 0011 y es fácil leerlo mal.** Ya no deciden
    qué se descarga —se descarga el día entero— sino **qué entra en el LLM y en qué orden**.
    Un día de BOE cuesta 10 s de red; una extracción cuesta 133,9 s. El caro es el modelo, así
    que el prefiltro pasó de ser la puerta de la red a ser la puerta del LLM.

    `SOSPECHA` no es "descárgalo para mirarlo": es "ya está descargado y mirado, y merece un
    puesto en la cola del extractor, aunque sea el último". Nunca se descarta sin revisar.
    """

    PENDIENTE = "pendiente"
    SOSPECHA = "sospecha"
    RELEVANTE = "relevante"
    DESCARTADA = "descartada"

    @property
    def entra_en_la_cola_del_extractor(self) -> bool:
        """Si esta norma tiene que acabar pasando por el LLM.

        Existe para que la cola del extractor no se escriba nunca como `== RELEVANTE`: eso fue
        cierto hasta el ADR 0011 y ahora perdería en silencio todo lo marcado como sospecha,
        que es justo lo que no se puede perder.
        """
        return self in (EstadoPrefiltro.SOSPECHA, EstadoPrefiltro.RELEVANTE)


class EjePrefiltro(enum.StrEnum):
    """Qué eje del prefiltro hizo pasar a una norma (CLAUDE.md sección 7.3).

    Los ejes se combinan con **OR, nunca con AND**: con AND, dos filtros de alto recall se
    convierten en uno de bajo recall, que es lo contrario de lo que busca este proyecto.

    Se registra cuál disparó porque sin eso no se puede afinar un eje sin tocar los otros ni
    medir si el referencial aporta algo o solo duplica al léxico.

    El eje 3 (semántico por embeddings) está fuera de alcance a propósito (sección 8) y **su
    valor no se declara aquí**: si no existe en el enum, no existe en la CHECK, y nadie puede
    escribirlo por error antes de que el eje exista.
    """

    LEXICO = "lexico"
    REFERENCIAL = "referencial"


class Norma(Base):
    """Un ítem normativo identificado dentro de un documento. CLAUDE.md sección 5."""

    __tablename__ = "norma"
    __table_args__ = (
        # Un mismo documento no puede traer dos veces el mismo identificador oficial. Igual
        # que en `documento`, es lo que hace que reprocesar un sumario no duplique filas.
        UniqueConstraint("documento_id", "identificador_oficial", name="uq_norma_doc_ident"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    documento_id: Mapped[int] = mapped_column(
        ForeignKey("documento.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # No está en la lista de la sección 5, se añade porque la ingesta ya lo produce: es el
    # identificador que da la fuente a cada ítem del sumario (p. ej. "BOE-A-2024-26484") y sin
    # él no hay forma estable de reconocer que un ítem ya se había visto.
    identificador_oficial: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    titulo: Mapped[str] = mapped_column(Text, nullable=False)
    # También añadido: la URL del texto completo que publica el sumario. Es lo que el pipeline
    # descarga vía `url_guard` en la fase 2 — para **todas** las normas del día, no solo para
    # las que pasan el prefiltro: el umbral de la fase 2 es cero desde el ADR 0011.
    url_texto: Mapped[str | None] = mapped_column(String(1000))

    # --- Fase 2: dónde está archivado el cuerpo de esta norma (ADR 0015) -------------------
    # NULL mientras no se haya descargado, y esa condición **es** la cola de trabajo de la
    # fase 2: `documento_texto_id IS NULL AND url_texto IS NOT NULL`. Se escribe como consulta
    # y no como estado nuevo a propósito — un estado habría que mantenerlo sincronizado, y una
    # consulta sobre la FK no puede desincronizarse de la realidad que describe.
    #
    # Ojo con la dirección de la lectura: esto NO es "el documento de esta norma" (eso es
    # `documento_id`, el sumario del que salió), es "el documento crudo que contiene su texto
    # íntegro". Son dos hechos distintos, de dos descargas distintas y con dos sellos de
    # tiempo distintos, y por eso son dos columnas.
    documento_texto_id: Mapped[int | None] = mapped_column(
        ForeignKey("documento.id", ondelete="RESTRICT"), index=True
    )

    # Nulos hasta que el extractor los determine. Al ingerir un sumario solo tenemos el
    # título; deducir el rango o el ámbito de él a ojo sería justo el tipo de invención que
    # prohíbe la regla de oro 8. Mejor NULL explícito que un valor plausible inventado.
    rango: Mapped[RangoNorma | None] = mapped_column(
        Enum(
            RangoNorma,
            native_enum=False,
            length=20,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
    organo_emisor: Mapped[str | None] = mapped_column(String(300))
    ambito: Mapped[AmbitoNorma | None] = mapped_column(
        Enum(
            AmbitoNorma,
            native_enum=False,
            length=20,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        index=True,
    )

    # --- Etapa 1 del pipeline: prefiltro léxico -------------------------------------------
    # Se guarda el resultado en vez de recalcularlo al vuelo, aunque el filtro sea
    # determinista y barato, porque lo que importa no es el veredicto sino poder sostenerlo:
    # con qué vocabulario se evaluó, qué término disparó y cuándo. Recalculando, "esta norma
    # se descartó el día 3" dejaría de ser comprobable en cuanto cambiara el diccionario.
    prefiltro_estado: Mapped[EstadoPrefiltro] = mapped_column(
        Enum(
            EstadoPrefiltro,
            native_enum=False,
            length=20,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=EstadoPrefiltro.PENDIENTE,
        server_default=EstadoPrefiltro.PENDIENTE.value,
        index=True,
    )
    # Términos del vocabulario que hicieron saltar la norma. JSON genérico y no JSONB: aquí
    # no se consulta por contenido, solo se lee junto a su fila; JSONB añadiría un tipo
    # específico del dialecto a cambio de nada.
    prefiltro_terminos: Mapped[list[str] | None] = mapped_column(JSON)
    # Qué ejes dispararon (7.2: "se guarda además qué eje disparó, no solo los términos").
    # Lista y no un valor único porque los ejes van en OR y pueden coincidir varios: que
    # dispararan los dos es un dato distinto de que disparara uno. Lista vacía —no NULL— al
    # descartar, mismo criterio que `prefiltro_terminos`.
    prefiltro_ejes: Mapped[list[str] | None] = mapped_column(JSON)
    # Cuántos términos DIRECTOS distintos se contaron. Se persiste porque es la magnitud que
    # separa relevante de sospecha (7.3, eje 1) y **su corte está sin validar**: cuando el gold
    # set permita calibrarlo hará falta el número real de cada norma ya evaluada para
    # recalibrar sin volver a descargar y recontar cientos de documentos.
    prefiltro_directos: Mapped[int | None] = mapped_column(Integer)
    # Versión del vocabulario con la que se evaluó. Es lo que permite saber qué normas hay
    # que reevaluar cuando el diccionario cambia.
    prefiltro_version: Mapped[str | None] = mapped_column(String(20))
    # Ídem para la watchlist del eje referencial. Va aparte de `prefiltro_version` porque los
    # dos ejes se afinan por separado, y compartir columna obligaría a reevaluarlo todo cada
    # vez que cambia cualquiera de los dos.
    prefiltro_version_watchlist: Mapped[str | None] = mapped_column(String(20))
    # Con qué versión de `pipeline/texto.texto_plano` se derivó el cuerpo evaluado, o NULL si
    # se evaluó **solo sobre el título** (fase 1). Es la tercera versión que se guarda por
    # fila, junto al vocabulario y la watchlist, y hace dos trabajos que ninguna otra columna
    # puede hacer:
    #
    # 1. **Dispara la reevaluación cuando llega el cuerpo.** Una norma evaluada sobre título
    #    tiene las mismas versiones de vocabulario y watchlist que una evaluada sobre texto
    #    íntegro; sin esta columna, la que quedó en `pendiente` seguiría en `pendiente` para
    #    siempre después de descargar su cuerpo, porque nada la marcaría como reevaluable.
    # 2. **Impide dar por bueno un recall que no lo es.** El gold set se etiqueta sobre texto
    #    íntegro (7.8): comparar contra una evaluación hecha sobre el título es un límite
    #    superior, no una medición. Con esta columna se puede separar una cosa de la otra en
    #    una consulta, en vez de tener que acordarse.
    prefiltro_version_texto: Mapped[str | None] = mapped_column(String(20))
    prefiltro_evaluado_en: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Etapa 4 del pipeline: catálogo de reglas (ADR 0016) -------------------------------
    # Con qué versión de `pipeline/reglas.py` se pasó el catálogo por esta norma, y cuándo.
    # Existe por lo mismo que `prefiltro_version_texto`, y hace falta aquí y no en `deteccion`
    # por un caso que no tiene fila donde apuntarse: **la norma que se evaluó y no disparó
    # ninguna regla**. Sin esta columna, esa norma no se distingue de una sin evaluar, y cada
    # pasada volvería a leer y parsear su cuerpo del almacén — 652 ficheros hoy — para llegar
    # otra vez a la misma nada. Es el mismo fallo silencioso que rompió la idempotencia del
    # prefiltro al llegar el estado `sospecha`, y por eso se resuelve igual: preguntando por la
    # versión y por la fecha, nunca por el estado.
    #
    # Son **dos** versiones y no una, con el mismo criterio que el prefiltro guarda por
    # separado la del vocabulario, la de la watchlist y la del texto: los spans de evidencia
    # son offsets sobre el texto derivado, así que un cambio en `texto_plano` los mueve todos
    # aunque el catálogo de reglas no se haya tocado. Con una sola columna, ese cambio dejaría
    # detecciones apuntando a rangos desplazados del archivo y nada las marcaría como
    # reevaluables.
    reglas_version: Mapped[str | None] = mapped_column(String(20))
    reglas_version_texto: Mapped[str | None] = mapped_column(String(20))
    reglas_evaluado_en: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))

    # Las dos relaciones necesitan `foreign_keys` explícito porque hay dos FK a la misma tabla
    # (ADR 0015). `documento_texto` no tiene `back_populates`: desde el cuerpo no se navega a
    # la norma, y declarar la vuelta solo añadiría una segunda forma de decir lo mismo.
    documento: Mapped[Documento] = relationship(
        back_populates="normas", foreign_keys=[documento_id]
    )
    documento_texto: Mapped[Documento | None] = relationship(foreign_keys=[documento_texto_id])

    @property
    def texto_archivado(self) -> Documento | None:
        """El mismo objeto que `documento_texto`, con el nombre que usa la API pública.

        Existe para que el esquema de salida pueda llamarlo por lo que **significa** —el texto
        de esta norma, archivado y con huella— sin que el nombre interno (que dice de qué
        columna cuelga) se convierta en contrato público.
        """
        return self.documento_texto


class VersionNorma(Base):
    """Versionado de una norma: aquí vive el diff. CLAUDE.md sección 5.

    **El histórico es inmutable.** No es una convención de código: la migración instala un
    trigger en PostgreSQL que rechaza cualquier UPDATE o DELETE sobre esta tabla. Esa
    inmutabilidad es parte del valor del proyecto — si el archivo de lo que se publicó se
    pudiera editar después, no serviría como archivo. Corregir un error significa insertar
    una versión nueva que lo diga, nunca reescribir la anterior.
    """

    __tablename__ = "version_norma"
    __table_args__ = (
        # Clave natural del diff (ADR 0018): esta norma, sobre esta otra, en este bloque. Es lo
        # que hace idempotente al servicio de versionado — reejecutarlo sobre lo mismo no puede
        # duplicar filas — y vive en la base de datos y no solo en el `SELECT` previo del
        # código, porque la tabla es de solo inserción: una fila duplicada **no se puede
        # borrar** (el trigger rechaza DELETE), así que aquí prevenir es la única opción.
        UniqueConstraint("norma_id", "norma_afectada", "bloque", name="uq_version_norma_bloque"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # La norma **modificadora**: la que se publicó y estamos analizando, no la que resulta
    # modificada. El diff que guarda esta fila es lo que esta norma le hizo a otra, y es así
    # porque la modificada casi nunca está en `norma` — la Ley 2/2016 de Madrid es de hace ocho
    # años y no salió de ningún sumario que hayamos ingerido. Ver ADR 0018.
    norma_id: Mapped[int] = mapped_column(
        ForeignKey("norma.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Identificador oficial de la norma **modificada** (`BOE-A-2016-6728`). Se guarda como texto
    # y no como FK precisamente por lo anterior: apuntar a una fila que no existe obligaría a
    # inventarse una `norma` sin sumario del que colgar, y el identificador oficial es el dato
    # que de verdad la nombra en cualquier fuente.
    norma_afectada: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    # Bloque del texto consolidado al que corresponde el diff ("a7", "dd", "ti"). NULL si la
    # fuente no lo identifica. No es lo mismo que `articulo`: aquel es el rótulo legible
    # («Artículo 7») y este el ancla con la que se vuelve al documento archivado.
    bloque: Mapped[str | None] = mapped_column(String(100))
    # Dónde está archivado —con su `sha256` y su sello (6.5)— el documento del que salió este
    # diff. NOT NULL a propósito: una versión sin la evidencia que la sostiene sería justo lo
    # que este proyecto no publica. Es el consolidado del BOE, que **no es el texto publicado
    # aquel día** sino una elaboración posterior de la propia fuente; por eso se archiva aparte
    # y se declara con `tipo='consolidado'`.
    documento_consolidado_id: Mapped[int] = mapped_column(
        ForeignKey("documento.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Desde cuándo rige la redacción nueva, según la fuente. Contexto, no evidencia.
    fecha_vigencia: Mapped[datetime.date | None] = mapped_column(Date)
    # Versión de la derivación con la que se extrajo el texto de cada bloque
    # (`ingest/boe_consolidado.VERSION_CONSOLIDADO`). Va en la fila porque la tabla es inmutable:
    # si la derivación cambia, las filas viejas se quedan como están y lo único que permite
    # saber que no son comparables con las nuevas es esta columna.
    version_derivacion: Mapped[str] = mapped_column(String(20), nullable=False)
    # Encadenamiento: una norma que modifica a otra genera una versión nueva que apunta a la
    # anterior. NULL en la primera versión conocida de una norma.
    version_anterior_id: Mapped[int | None] = mapped_column(
        ForeignKey("version_norma.id", ondelete="RESTRICT"), index=True
    )
    # Número de orden dentro de la norma, para poder recorrer el histórico sin depender de
    # los ids autoincrementales.
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # El diff, artículo a artículo. `articulo` es el identificador dentro de la norma
    # ("art. 3.2", "disposición adicional segunda"); se guarda como texto libre porque la
    # forma de citar varía entre boletines y normalizarla sería inventar una taxonomía.
    articulo: Mapped[str | None] = mapped_column(String(300))
    # NULL en una alta (no había texto anterior) y en una derogación (no hay texto nuevo).
    # La combinación de cuál de los dos es NULL es, de hecho, la señal más limpia de si el
    # cambio es un alta, una modificación o una derogación.
    texto_anterior: Mapped[str | None] = mapped_column(Text)
    texto_nuevo: Mapped[str | None] = mapped_column(Text)

    creada_en: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
