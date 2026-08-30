"""De dónde sale un hallazgo histórico. ADR 0025, decisiones 3 y 4.

Un hallazgo **no se crea, se deriva**. No hay tabla `hallazgo` y no debe haberla: existe cuando
se dan a la vez tres condiciones, y las tres se comprueban **en la consulta**, no en un filtro
posterior ni en la interfaz.

1. **Hay informe de apoyo con semáforo `alerta`.** O sea: un asistente que leyó el texto
   archivado diría que esto se publica.
2. **No hay fila en `alerta`.** Nadie lo ha revisado. Si alguien lo aprueba, deja de ser un
   hallazgo y pasa a ser una alerta — la misma detección, la otra superficie, y sin que nadie
   tenga que acordarse de moverlo de sitio.
3. **El informe trae al menos una corroboración.** Es la decisión 4 del ADR 0025 y es la que
   hace publicable algo que nadie ha revisado: sin ella, lo que la web enseñaría es «un
   asistente de IA cree que esto es un retroceso», que es un juicio propio del sistema y lo
   prohíbe la regla de oro 2.

**Las tres van en el `where` a propósito.** Un filtro en Python después de la consulta se salta
con un `limit` mal puesto, con una ruta nueva que reutilice la consulta sin el filtro, o con un
refactor que mueva el bucle. En el `where` no hay forma de pedir la lista sin las condiciones,
porque no existe una consulta sin ellas.

## Por qué esto no es la tabla `alerta` con un flag

Porque un flag se puede poner a `True`. La separación del ADR 0025 es que **viven en sitios
distintos de la base y se construyen de forma distinta**: `alerta` solo la escribe
`services/revision.aprobar`, y un hallazgo no se escribe en ningún sitio. Así la frase de la
portada —«nada se publica sin revisión humana»— sigue siendo literalmente cierta, y no depende
de que nadie toque una etiqueta.
"""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.deteccion import (
    Alerta,
    ColaRevision,
    Deteccion,
    InformeRevision,
    Semaforo,
)
from app.models.documento import Documento
from app.models.norma import Norma
from app.pipeline import watchlist
from app.schemas.alerta import (
    CambioPrecepto,
    NormaAlerta,
    NormaVigiladaAfectada,
    SpanEvidenciaPublico,
    TextoArchivadoAlerta,
)
from app.schemas.hallazgo import HallazgoPublico, InformeHallazgo


def _lista(valor: Any) -> list[Any]:
    return valor if isinstance(valor, list) else []


def consulta() -> Select[tuple[InformeRevision, ColaRevision, Deteccion, Norma]]:
    """Los hallazgos publicables. Las tres condiciones del módulo, en el `where`.

    `json_array_length` existe igual en PostgreSQL y en SQLite, así que la condición de las
    corroboraciones se comprueba en la base en los dos sitios: en producción y en los tests. Que
    el test corra contra el mismo control que producción es la mitad de su valor.
    """
    return (
        select(InformeRevision, ColaRevision, Deteccion, Norma)
        .join(ColaRevision, ColaRevision.id == InformeRevision.cola_revision_id)
        .join(Deteccion, Deteccion.id == ColaRevision.deteccion_id)
        .join(Norma, Norma.id == Deteccion.norma_id)
        # El sumario, explícito y no por relación: hace falta ORDENAR por su fecha, y `norma`
        # tiene dos documentos (el sumario y el cuerpo, ADR 0015). Mismo criterio y misma razón
        # que en `services/alertas.consulta()`.
        .join(Documento, Documento.id == Norma.documento_id)
        # (2) Nadie lo ha aprobado. `outerjoin` + `IS NULL` es la forma de decir "no existe" que
        # se puede combinar con el resto de la consulta.
        .outerjoin(Alerta, Alerta.deteccion_id == Deteccion.id)
        .where(InformeRevision.semaforo == Semaforo.ALERTA)  # (1)
        .where(Alerta.id.is_(None))  # (2)
        .where(func.json_array_length(InformeRevision.corroboraciones) > 0)  # (3)
        .options(selectinload(Norma.documento), selectinload(Norma.documento_texto))
    )


def a_publico(
    informe: InformeRevision,
    deteccion: Deteccion,
    norma: Norma,
    *,
    cambios: list[CambioPrecepto] | None = None,
) -> HallazgoPublico:
    """Arma la vista pública del hallazgo.

    Tolerante con la forma de `evidencia_json`, por el mismo motivo que `alertas.a_publica`: una
    fila escrita por una versión anterior del clasificador tiene que producir un hallazgo con
    menos información, no un 500.
    """
    evidencia = deteccion.evidencia_json if isinstance(deteccion.evidencia_json, dict) else {}
    lista = watchlist.watchlist()

    vigiladas = []
    for identificador in _lista(evidencia.get("normas_vigiladas")):
        entrada = lista.buscar(str(identificador))
        vigiladas.append(
            NormaVigiladaAfectada(
                identificador=str(identificador),
                # Vacío si la watchlist ya no la trae: se dice que no se sabe, no se inventa.
                titulo=entrada.titulo if entrada else "",
                ambito=entrada.ambito if entrada else "",
            )
        )

    cuerpo = norma.documento_texto
    return HallazgoPublico(
        id=informe.id,
        generado_en=informe.generado_en,
        fecha_publicacion=norma.documento.fecha_publicacion,
        clasificacion=deteccion.clasificacion.value,
        severidad=deteccion.severidad,
        confianza=deteccion.confianza,
        regla_aplicada=deteccion.regla_aplicada,
        version_reglas=evidencia.get("version_reglas"),
        version_texto_plano=evidencia.get("version_texto_plano"),
        normas_vigiladas=vigiladas,
        spans=[
            SpanEvidenciaPublico(
                inicio=int(span["inicio"]), fin=int(span["fin"]), fragmento=str(span["fragmento"])
            )
            for span in _lista(evidencia.get("spans"))
            if isinstance(span, dict) and {"inicio", "fin", "fragmento"} <= span.keys()
        ],
        preceptos_con_diff=int(evidencia.get("preceptos_con_diff") or 0),
        cambios=cambios or [],
        norma=NormaAlerta.model_validate(norma),
        texto_archivado=(
            TextoArchivadoAlerta.model_validate(cuerpo) if cuerpo is not None else None
        ),
        # La proyección estrecha del esquema: `recomendacion` y `semaforo` no viajan. Como
        # `InformeHallazgo` lleva `extra="forbid"` y se construye campo a campo, añadir uno al
        # modelo de la base no lo publica solo.
        informe=InformeHallazgo.model_validate(informe),
    )


def corte_temporal(informe: InformeRevision) -> datetime.datetime:
    """Hasta cuándo se publican los preceptos reescritos de un hallazgo.

    En una alerta el corte es `emitida_en`, y el motivo está escrito en `alertas.cambios_de`:
    material que llega después de la aprobación no lo ha revisado nadie, así que no se publica
    colgado de una aprobación vieja.

    Un hallazgo no tiene aprobación, pero el mismo problema existe con otro dueño: el asistente
    escribió el informe leyendo el archivo tal y como estaba en `generado_en`. Si el BOE
    consolida más preceptos la semana que viene —y lo hace con retraso, por eso existe
    `--versionar`—, publicarlos bajo este hallazgo sería enseñar redacciones que **ni siquiera el
    asistente vio** y presentarlas como parte de lo que dijo. El corte es `generado_en`.
    """
    return informe.generado_en


def con_cambios(
    session: Session,
    informe: InformeRevision,
    deteccion: Deteccion,
    norma: Norma,
    *,
    limite: int,
    max_caracteres: int,
) -> HallazgoPublico:
    """El hallazgo con sus preceptos reescritos, recortados al corte temporal de arriba."""
    # Import local: `alertas` no importa a `hallazgos`, así que no hay ciclo, pero mantenerlo
    # aquí deja claro que lo compartido es SOLO la lectura de `version_norma` y no la consulta.
    from app.services import alertas as servicio_alertas

    publico = a_publico(informe, deteccion, norma)
    cambios = servicio_alertas.cambios_de(
        session,
        norma.id,
        [vigilada.identificador for vigilada in publico.normas_vigiladas],
        emitida_en=corte_temporal(informe),
        limite=limite,
        max_caracteres=max_caracteres,
    )
    return publico.model_copy(update={"cambios": cambios})
