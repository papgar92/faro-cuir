"""Vista pública de un **hallazgo histórico**. ADR 0025, decisiones 3 y 4.

## Qué es esto y en qué se diferencia de una alerta

Un hallazgo **no es una alerta y no vive en la tabla `alerta`**. Sale de tener un informe de
apoyo con semáforo `alerta` y **no** tener aprobación humana. Las dos superficies afirman cosas
distintas y por eso tienen esquema distinto:

- **`AlertaPublica`**: una persona lo revisó y decidió publicarlo. Lleva `emitida_en` y puede
  llevar `clasificacion_humana`, porque hubo alguien que decidió.
- **`HallazgoPublico`** (esto): el archivo prueba que el cambio ocurrió y alguien con nombre ya
  lo documentó. **Nadie de este proyecto lo ha revisado**, y el esquema lo dice con un campo que
  no se puede poner a `True` (`revisado_por_humano`).

Gracias a eso la frase de la portada —«nada se publica sin revisión humana»— **sigue siendo
literalmente cierta**: un hallazgo no es una publicación del proyecto, es una cita doble.

## Qué del informe sale aquí, y qué no

El informe de apoyo (`schemas/revision.InformeApoyo`) tiene más campos que los que se publican.
La proyección pública es **deliberadamente más estrecha**, y el criterio es la regla de oro 2:

| campo | ¿sale? | por qué |
|---|---|---|
| `resumen`, `a_quien_afecta` | sí | son descriptivos: qué hace la norma y a quién le pasa |
| `citas` | sí | literales del texto archivado, comprobables contra la fuente |
| `corroboraciones` | sí | **son el motivo de que esto se pueda publicar** (decisión 4) |
| `refutacion` | sí | sin ella esto sería un sello de goma. Va siempre, como en el panel |
| `recomendacion` | **no** | es «yo publicaría esto»: la opinión del asistente |
| `semaforo` | **no** | es el color de una cola de trabajo interna, no información pública |

Dejar fuera la recomendación no es prudencia decorativa. Con ella, lo que la web enseñaría sería
«un asistente de IA cree que esto es un retroceso» —exactamente lo que la decisión 4 del ADR 0025
describe como lo que NO se puede publicar—. Sin ella se enseñan dos hechos verificables por
separado y ninguno nuestro: que el cambio ocurrió (el documento sellado) y que alguien con nombre
ya lo denunció (el enlace). Quien lea puede comprobar los dos por su cuenta.
"""

from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.alerta import (
    CambioPrecepto,
    NormaAlerta,
    NormaVigiladaAfectada,
    SpanEvidenciaPublico,
    TextoArchivadoAlerta,
)
from app.schemas.revision import CitaInforme, CorroboracionInforme


class InformeHallazgo(BaseModel):
    """La parte publicable del informe de apoyo. Ver la tabla del módulo para qué falta y por qué.

    `corroboraciones` **nunca está vacía aquí**: un informe sin corroborar no llega a ser un
    hallazgo, y eso lo garantiza la consulta de `services/hallazgos.consulta()`, no este esquema.
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    resumen: str
    a_quien_afecta: str | None
    # Obligatoria también de cara al público, y por el mismo motivo que en el panel: lo que se
    # publica sin que nadie lo haya revisado tiene que venir con las instrucciones para
    # desmontarlo. Es lo único que separa esto de un titular.
    refutacion: str
    citas: list[CitaInforme] = Field(default_factory=list)
    corroboraciones: list[CorroboracionInforme] = Field(default_factory=list)
    # «Esto lo preparó X el día Y y no lo ha revisado nadie.» La interfaz tiene que enseñarlo
    # pegado al contenido, no en un pie de página (ADR 0025, decisión 2).
    generado_por: str
    generado_en: datetime.datetime


class HallazgoPublico(BaseModel):
    """Un cambio normativo que el archivo prueba y que nadie de este proyecto ha revisado."""

    model_config = ConfigDict(extra="forbid")

    # El identificador del informe. Estable: hay como mucho un informe por ítem de cola.
    id: int

    # **Constante y no configurable.** Es un `Literal[False]`, así que ni un cambio de código
    # despistado ni un `model_copy(update=...)` pueden ponerlo a `True` sin que Pydantic falle.
    # Un hallazgo que pudiera decir que lo revisó alguien sería un hallazgo que miente sobre lo
    # único que lo distingue de una alerta.
    revisado_por_humano: Literal[False] = False

    # Cuándo se escribió el informe. Es lo más parecido a `emitida_en` que tiene un hallazgo, y
    # se llama distinto a propósito: nadie lo emitió.
    generado_en: datetime.datetime
    fecha_publicacion: datetime.date

    # La clasificación de las REGLAS (ADR 0004 y 0016), no del asistente ni del informe. Puede
    # ser `indeterminado`, y entonces es que el catálogo no sostiene ningún signo: eso se publica
    # tal cual, porque afirmar un signo que no se puede sostener es lo que prohíbe la regla 2.
    clasificacion: str
    severidad: int
    confianza: float
    regla_aplicada: str | None
    version_reglas: str | None
    version_texto_plano: str | None

    normas_vigiladas: list[NormaVigiladaAfectada] = Field(default_factory=list)
    spans: list[SpanEvidenciaPublico] = Field(default_factory=list)
    preceptos_con_diff: int = 0
    cambios: list[CambioPrecepto] = Field(default_factory=list)

    norma: NormaAlerta
    texto_archivado: TextoArchivadoAlerta | None

    informe: InformeHallazgo
