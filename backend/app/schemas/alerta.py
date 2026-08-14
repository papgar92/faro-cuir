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

    clasificacion: str
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

    norma: NormaAlerta
    texto_archivado: TextoArchivadoAlerta | None
