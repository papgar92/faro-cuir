"""Esquemas del panel de revisión (gate humano). Escritos a mano, como los de la API pública.

Aquí la razón de escribirlos a mano es distinta y más fuerte: esta API sí lleva autenticación,
así que la tentación de "publicar el modelo entero, total, solo lo ve quien revisa" es mayor. Lo
que se publica en el panel es lo que el revisor necesita **para verificar**, no todo lo que hay.

Lo que deliberadamente **no** viaja al panel:

- **`extraccion_json`, o sea lo que dijo el modelo.** Se publica que existe y cuántos punteros
  trae, no su contenido. El revisor decide mirando el texto archivado y la evidencia que el
  catálogo recortó de él (7.5 y 7.6); poner al lado la prosa del LLM invita a leerla como si
  fuera la conclusión del sistema, que es justo lo que las reglas de oro 3 y 10 impiden. Cuando
  el panel enseñe la extracción tendrá que hacerlo diciendo de quién es cada afirmación, y eso
  es una decisión de diseño con su propio momento.
- **`ruta_almacen`**, igual que en la API pública: es una ruta del servidor.
- **Quién revisó**, porque no se guarda (6.4).
"""

from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.alerta import CambioPrecepto
from app.services.revision import MAX_NOTA


class SpanEvidencia(BaseModel):
    """Un fragmento del **texto archivado** sobre el que se aplicó la regla.

    Los offsets van con el fragmento a propósito: el fragmento es para leerlo y los offsets son
    para comprobarlo. Con `inicio`, `fin` y la versión de la derivación del texto, un tercero
    puede recortar el documento archivado por su cuenta y contrastar que dice esto — que es la
    diferencia entre auditar y creerse lo que le pintan (7.5).
    """

    inicio: int
    fin: int
    fragmento: str


class NormaRevision(BaseModel):
    """La norma a la que se refiere el veredicto, con lo justo para identificarla y abrirla."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    identificador_oficial: str
    titulo: str
    organo_emisor: str | None
    url_texto: str | None
    prefiltro_estado: str
    prefiltro_ejes: list[str] | None


class TextoArchivadoRevision(BaseModel):
    """La huella del cuerpo archivado. Es lo que hace comprobable todo lo demás (6.5)."""

    model_config = ConfigDict(from_attributes=True)

    sha256: str
    sello_tiempo: datetime.datetime
    url_original: str


class ItemRevision(BaseModel):
    """Un ítem de la cola, tal y como lo ve quien tiene que decidir."""

    id: int
    estado: str
    creada_en: datetime.datetime
    resuelta_en: datetime.datetime | None
    nota_revision: str | None

    deteccion_id: int
    clasificacion: str
    origen: str
    regla_aplicada: str | None
    severidad: int
    confianza: float
    # Sin calibrar y dicho aquí, no solo en el código: `severidad` y `confianza` son valores
    # declarados por cada regla y nadie los ha medido contra un corpus todavía. El panel los
    # enseña porque ordenar la cola por gravedad declarada es útil; citarlos como dato, no.
    version_reglas: str | None
    version_texto_plano: str | None
    normas_vigiladas: list[str] = Field(default_factory=list)
    # Lo que fijó quien revisó, si lo hizo. Se enseña en el panel para que una segunda pasada
    # sepa que aquí ya hubo una decisión humana y cuál fue.
    clasificacion_humana: str | None = None
    spans: list[SpanEvidencia] = Field(default_factory=list)

    # Que el extractor haya pasado o no por esta norma, sin publicar lo que dijo. Ver la
    # cabecera del módulo.
    tiene_extraccion: bool
    punteros_corroborados: int
    punteros_sin_corroborar: int

    # El diff archivado (ADR 0018), **entero y sin recorte por fecha**: quien revisa tiene que
    # ver lo que hay ahora, porque su decisión es la que autoriza a publicarlo. Se reutiliza el
    # tipo público a propósito — si el panel enseñara una forma distinta de la que se publica,
    # nadie estaría revisando lo que sale.
    cambios: list[CambioPrecepto] = Field(default_factory=list)

    norma: NormaRevision
    texto_archivado: TextoArchivadoRevision | None


class ResolucionRevision(BaseModel):
    """Cuerpo de aprobar/descartar. Todo opcional y acotado."""

    model_config = ConfigDict(extra="forbid")

    nota: str | None = Field(default=None, max_length=MAX_NOTA)
    # El signo que fija la persona, cuando la regla no lo afirmó. Opcional a propósito: lo normal
    # es aprobar sin tocarlo, y exigirlo convertiría cada revisión en una obligación de opinar.
    clasificacion: Literal["avance", "retroceso", "neutro", "indeterminado"] | None = None


class Credenciales(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Sin campo de usuario: no hay tabla de usuarios (ver `security/panel.py`). Añadir uno
    # sugeriría que existen cuentas y que el sistema sabe quién entra, y no es así.
    password: str = Field(min_length=1, max_length=256)


class SesionAbierta(BaseModel):
    """Lo único que devuelve el login. El token va en la cookie `HttpOnly`, nunca en el cuerpo."""

    caduca_en: datetime.datetime
