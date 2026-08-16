"""Esquemas de salida de la API pública.

Son deliberadamente distintos de los modelos de SQLAlchemy y no se generan a partir de ellos.
Un `from_attributes` sobre el modelo entero publicaría cualquier columna que se añada mañana
sin que nadie lo decida; escribir el esquema a mano hace que exponer un campo nuevo sea un
acto explícito. En una API pública sin autenticación eso importa.
"""

from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict


class TextoArchivado(BaseModel):
    """La prueba de archivo del texto íntegro de una norma (CLAUDE.md 6.5, ADR 0005 y 0015).

    Se publica entero y a propósito. El proyecto afirma «el día X esta norma decía esto», y esa
    afirmación **no vale nada si quien la lee no puede comprobarla**: con el `sha256` y el
    `sello_tiempo` delante, cualquiera puede descargar el texto de la fuente oficial, calcular
    el hash y contrastarlo. Publicar la garantía sin publicar la huella sería pedir que se
    fíen, que es justo lo contrario de lo que hace esta herramienta.

    `null` significa que el cuerpo aún no se ha descargado (cola de la fase 2), no que no
    exista. Es una distinción que la interfaz debe respetar.
    """

    model_config = ConfigDict(from_attributes=True)

    sha256: str
    sello_tiempo: datetime.datetime
    # La URL de la que se descargó, para que la verificación se pueda repetir sin adivinar de
    # dónde salió. `ruta_almacen` sigue sin publicarse: es una ruta del servidor.
    url_original: str


class NormaResumen(BaseModel):
    """Una norma tal y como se lista en la API pública."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    identificador_oficial: str
    titulo: str
    organo_emisor: str | None
    # Nulos mientras el extractor no haya procesado la norma. Se exponen igualmente para que
    # el cliente distinga "todavía no analizado" de "analizado y sin ámbito claro".
    rango: str | None
    ambito: str | None
    url_texto: str | None

    # Etapa 1 del pipeline (ADR 0007). Se publica a propósito: es lo que permite a cualquiera
    # comprobar por qué una norma no llegó a analizarse, en vez de tener que fiarse. Un
    # filtro que decide en silencio qué se mira y qué no es justo lo que este proyecto
    # denuncia en la administración; sería incoherente esconder el nuestro.
    prefiltro_estado: str
    # Términos del vocabulario que la hicieron pasar. Lista vacía si se descartó, null si
    # todavía no se ha evaluado — la misma distinción que guarda la tabla.
    prefiltro_terminos: list[str] | None
    # Qué eje disparó (7.3): `lexico`, `referencial`, o los dos. Se publica por el mismo
    # motivo que los términos: sin él, "esta norma pasó" no se puede auditar desde fuera. Y
    # es lo único que distingue una norma que pasó porque su texto habla del colectivo de una
    # que pasó porque **modifica una norma vigilada diga lo que diga su texto** — que es el
    # caso silencioso, el que justifica el proyecto entero.
    prefiltro_ejes: list[str] | None
    # Cuántos términos directos distintos se contaron. Es la magnitud que separa `relevante`
    # de `sospecha` (umbral de 7.3), así que sin ella el estado no se puede contrastar.
    prefiltro_directos: int | None
    # El texto íntegro archivado, con su huella. `null` mientras la fase 2 no lo haya bajado.
    texto_archivado: TextoArchivado | None


class DocumentoResumen(BaseModel):
    """Un documento ingerido. Incluye la huella para que el archivo sea comprobable."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    identificador_oficial: str
    fecha_publicacion: datetime.date
    url_original: str
    # El sha256 y el sello se publican a propósito (CLAUDE.md 6.5): quien reciba una alerta
    # debe poder verificar por su cuenta que el contenido archivado es el que se publicó.
    sha256: str
    sello_tiempo: datetime.datetime
    estado_pipeline: str
    # `sumario`, `texto_norma` (ADR 0015) o `consolidado` (ADR 0018). Se publica porque sin él
    # tres filas con la misma forma significan cosas distintas, y quien consuma la API no tendría
    # cómo saber cuál está mirando. El listado devuelve solo sumarios; por id se puede pedir
    # cualquiera, y ahí este campo es lo único que separa **lo que se publicó aquel día** de una
    # elaboración posterior de la fuente. Un `consolidado` tiene además dos rasgos que conviene
    # no leer mal: su `identificador_oficial` lo componemos nosotros (lleva el hash del
    # contenido, porque el consolidado de una norma cambia cada vez que alguien la modifica) y su
    # `fecha_publicacion` es el día en que lo descargamos, no una fecha de boletín.
    tipo: str
    # `ruta_almacen` NO se expone: es una ruta del sistema de ficheros del servidor y no le
    # sirve de nada a un cliente. Publicar rutas internas solo regala información.


class DocumentoDetalle(DocumentoResumen):
    normas: list[NormaResumen]
