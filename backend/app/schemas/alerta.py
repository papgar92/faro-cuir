"""Esquemas de la API pública de alertas. Lo que el proyecto afirma en su nombre.

Una fila de `alerta` significa que **una persona la aprobó** (regla de oro 4, ADR 0003 y 0017).
Por eso este es el único sitio del sistema donde una clasificación sale al mundo, y por eso el
endpoint que los usa consulta `alerta` y no `deteccion`: la aprobación no es un campo que haya
que acordarse de mirar, es la existencia de la fila.

Qué viaja, y por qué exactamente esto:

- **La evidencia entera, con offsets.** Publicar «esto es un retroceso» sin publicar sobre qué
  texto es pedir que se fíen, que es lo contrario de lo que esta herramienta le exige a la
  administración. Con el `sha256`, el sello y los offsets, cualquiera recorta el documento
  archivado por su cuenta y contrasta (6.5 y 7.5).
- **La regla y su versión.** «Reglas auditables» (7.6) significa que un tercero pueda
  reconstruir el veredicto leyendo la regla y el texto, sin ejecutar nuestro código.

Qué **no** viaja:

- **`extraccion_json`.** Lo que dijo el modelo no es la conclusión del sistema y no se publica
  como si lo fuera (reglas de oro 3 y 10). El panel de revisión tampoco lo enseña.
- **`nota_revision`.** Es el rastro de auditoría del gate, y a quien la escribe se le dijo que
  «se guarda con la decisión», no que se publica. Publicar algo que su autor no sabía que sería
  público es exactamente la clase de cosa que este proyecto no hace. Si algún día hace falta una
  justificación pública, será un campo distinto y con su etiqueta diciendo que lo es.
- **Nada de quién revisó**, porque no se guarda (6.4).
"""

from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, Field


class SpanEvidenciaPublico(BaseModel):
    """Un fragmento del texto archivado, con sus coordenadas para poder comprobarlo."""

    inicio: int
    fin: int
    fragmento: str


class NormaVigiladaAfectada(BaseModel):
    """La norma protegida que la alerta toca, con el territorio al que pertenece.

    `ambito` es `estatal` o el código ISO 3166-2:ES de la comunidad, y sale de la watchlist —
    no de la fuente. Es la distinción que hace posible el mapa: la Ley 2/2016 de Madrid se
    publica en el **BOE**, así que por fuente sería estatal y la comunidad quedaría en blanco
    justo en el caso que el proyecto existe para enseñar.
    """

    identificador: str
    titulo: str
    ambito: str


class CambioPrecepto(BaseModel):
    """Un precepto reescrito: qué decía y qué dice, con la huella de dónde salió (ADR 0018).

    Es la pieza que convierte una alerta en algo verificable de un vistazo. Hasta el ADR 0018 el
    sistema podía decir «han modificado el artículo 4» y no podía enseñar de qué a qué, porque el
    BOE modificativo publica solo la redacción nueva.

    **`consolidado_sha256` no es decorativo y no es el mismo hash que el de la norma.** Estos dos
    textos salen del *consolidado* del BOE, que es una elaboración de la fuente y no lo que se
    publicó aquel día; sin decir de qué documento salen y con qué huella, quien quiera rebatir el
    diff no sabe contra qué contrastarlo.
    """

    norma_afectada: str
    articulo: str | None
    bloque: str | None
    texto_anterior: str | None
    texto_nuevo: str | None
    fecha_vigencia: datetime.date | None
    consolidado_sha256: str
    # `true` cuando alguno de los dos textos se ha recortado para publicarlo. Se dice en el dato
    # y no solo en la documentación: un artículo cortado que no avisa de que está cortado es una
    # cita falsa, y aquí la cita literal es todo el valor.
    truncado: bool = False


class NormaAlerta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    identificador_oficial: str
    titulo: str
    organo_emisor: str | None
    url_texto: str | None


class TextoArchivadoAlerta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sha256: str
    sello_tiempo: datetime.datetime
    url_original: str


class AlertaPublica(BaseModel):
    """Una detección aprobada y emitida."""

    id: int
    emitida_en: datetime.datetime
    # Del boletín en el que se publicó la norma, no de cuándo la vimos: es la fecha por la que
    # se ordena una cronología de retrocesos.
    fecha_publicacion: datetime.date

    # **Lo que derivó la regla** del texto archivado. Reconstruible por un tercero leyendo la
    # regla y el documento, sin ejecutar nuestro código (7.6).
    clasificacion: str
    # **Lo que fijó la persona que revisó**, si lo fijó. Va aparte y con nombre propio porque es
    # otra fuente de autoridad: la regla se abstiene cuando no puede afirmar el signo —derogar
    # una ley es lo que hace tanto quien la desmonta como quien la sustituye por otra mejor— y
    # quien lee el texto sí puede decirlo. Mezclarlas haría que la fila dijera «retroceso, regla
    # R-DER-001» cuando la regla no dice eso.
    clasificacion_humana: str | None = None
    severidad: int
    # `severidad` y `confianza` las declara cada regla y **nadie las ha calibrado** contra un
    # corpus. Se publican porque ordenar por gravedad declarada es útil y esconderlas sería
    # peor; quien las consuma tiene que poder saber que no son una medición, y por eso lo dice
    # este comentario, la documentación del endpoint y la interfaz donde se pintan.
    confianza: float
    regla_aplicada: str | None
    version_reglas: str | None
    version_texto_plano: str | None

    normas_vigiladas: list[NormaVigiladaAfectada] = Field(default_factory=list)
    spans: list[SpanEvidenciaPublico] = Field(default_factory=list)

    # --- El diff (ADR 0018) ---------------------------------------------------------------
    # Vocabulario protector que estaba en la redacción anterior de un precepto y no está en la
    # nueva. **Es un diagnóstico y así hay que leerlo**: no dice que el término haya desaparecido
    # de la ley —puede seguir en otro artículo que nadie tocó— ni decide el signo de la alerta,
    # que lo pone la regla. Se publica porque es por donde empieza a leer quien revisa.
    terminos_perdidos: list[str] = Field(default_factory=list)
    # Cuántos preceptos reescritos tiene archivado el sistema para esta alerta. Va siempre, en el
    # listado y en el detalle, para que un listado sin `cambios` no se lea como "no hay diff".
    preceptos_con_diff: int = 0
    # Las redacciones enteras. **Solo en el detalle** (`GET /api/alertas/{id}`): una alerta puede
    # traer 36 preceptos con sus dos textos, y meter eso en cada elemento del listado convertiría
    # una página de titulares en varios megas. El listado dice cuántos hay y dónde mirarlos.
    cambios: list[CambioPrecepto] = Field(default_factory=list)

    norma: NormaAlerta
    texto_archivado: TextoArchivadoAlerta | None
