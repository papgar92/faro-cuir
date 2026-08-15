"""Lectura de alertas emitidas: la consulta y la vista pública, en un solo sitio.

Lo usan los dos canales —`GET /api/alertas` (web) y `GET /api/alertas.xml` (feed Atom, ADR
0010)— y por eso vive aquí y no dentro de un router. No es una separación por gusto
arquitectónico: **la consulta parte de `alerta`, y eso es un control de seguridad**, no un
detalle de implementación.

Una fila de `alerta` solo la escribe `services/revision.aprobar` tras el gate humano (regla de
oro 4). Leer de ahí significa que «esto lo aprobó una persona» no es un `WHERE` que un canal
nuevo pueda olvidarse de poner: es la tabla de la que se parte. Si mañana alguien añade un
tercer canal —correo, webhook— y reutiliza esto, hereda el control. Si escribe su propia
consulta sobre `deteccion`, no lo hereda, y por eso conviene que esto sea lo obvio de usar.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.models.deteccion import Alerta, Deteccion
from app.models.documento import Documento
from app.models.norma import Norma, VersionNorma
from app.pipeline import watchlist
from app.schemas.alerta import (
    AlertaPublica,
    CambioPrecepto,
    NormaAlerta,
    NormaVigiladaAfectada,
    SpanEvidenciaPublico,
    TextoArchivadoAlerta,
)

# Tope por redacción publicada. El artículo más largo del corpus no llega, así que hoy no recorta
# nada; existe para que un precepto desmesurado —o un consolidado manipulado— no convierta una
# respuesta de la API en un problema de memoria de quien la consuma. Cuando recorta, la fila lo
# dice con `truncado`, porque una cita cortada que no avisa es una cita falsa.
MAX_CARACTERES_REDACCION = 8_000


def _lista(valor: Any) -> list[Any]:
    return valor if isinstance(valor, list) else []


def _recortar(texto: str | None) -> tuple[str | None, bool]:
    if texto is None or len(texto) <= MAX_CARACTERES_REDACCION:
        return texto, False
    return texto[:MAX_CARACTERES_REDACCION] + " […]", True


def cambios_de(session: Session, norma_id: int, vigiladas: list[str]) -> list[CambioPrecepto]:
    """Los preceptos reescritos que el ADR 0018 archivó para esta norma.

    **Filtrado por las normas vigiladas que declara la propia alerta**, y no simplemente por
    `norma_id`: una fila de `version_norma` de otra norma afectada no sostiene *esta* alerta, y
    publicarla dentro sería enseñar como evidencia algo que el veredicto no miró.

    Consulta aparte y no dentro de `consulta()` porque solo la usa el detalle: el listado publica
    cuántos hay, no sus textos.
    """
    if not vigiladas:
        return []
    filas = session.execute(
        select(VersionNorma, Documento.sha256)
        .join(Documento, Documento.id == VersionNorma.documento_consolidado_id)
        .where(VersionNorma.norma_id == norma_id, VersionNorma.norma_afectada.in_(vigiladas))
        .order_by(VersionNorma.ordinal, VersionNorma.id)
    ).all()

    cambios = []
    for version, sha256 in filas:
        anterior, corte_anterior = _recortar(version.texto_anterior)
        nuevo, corte_nuevo = _recortar(version.texto_nuevo)
        cambios.append(
            CambioPrecepto(
                norma_afectada=version.norma_afectada,
                articulo=version.articulo,
                bloque=version.bloque,
                texto_anterior=anterior,
                texto_nuevo=nuevo,
                fecha_vigencia=version.fecha_vigencia,
                consolidado_sha256=sha256,
                truncado=corte_anterior or corte_nuevo,
            )
        )
    return cambios


def consulta() -> Select[tuple[Alerta, Deteccion, Norma]]:
    """Alertas emitidas, con su detección y su norma. Ordenar es cosa de quien llame."""
    return (
        select(Alerta, Deteccion, Norma)
        .join(Deteccion, Deteccion.id == Alerta.deteccion_id)
        .join(Norma, Norma.id == Deteccion.norma_id)
        # El sumario, explícito y no por relación, porque hace falta **ordenar** por su fecha.
        # `norma` tiene dos documentos (el sumario y el cuerpo, ADR 0015) y por eso la condición
        # va escrita: dejar que el ORM elija sería elegir al azar entre dos caminos distintos.
        .join(Documento, Documento.id == Norma.documento_id)
        .options(selectinload(Norma.documento), selectinload(Norma.documento_texto))
    )


def a_publica(
    alerta: Alerta,
    deteccion: Deteccion,
    norma: Norma,
    *,
    cambios: list[CambioPrecepto] | None = None,
) -> AlertaPublica:
    """Arma la vista pública. Tolerante con la forma de `evidencia_json` a propósito.

    Una fila escrita por una versión anterior del clasificador tiene que producir una alerta con
    menos información, no un 500: la alerta ya la aprobó una persona, y retirarla del listado
    por un problema de formato sería desindexarla en silencio — justo el daño que este proyecto
    documenta que hay que evitar (6.5).
    """
    evidencia = deteccion.evidencia_json if isinstance(deteccion.evidencia_json, dict) else {}
    lista = watchlist.watchlist()

    vigiladas = []
    for identificador in _lista(evidencia.get("normas_vigiladas")):
        entrada = lista.buscar(str(identificador))
        vigiladas.append(
            NormaVigiladaAfectada(
                identificador=str(identificador),
                titulo=entrada.titulo if entrada else "",
                # Vacío si la watchlist ya no la trae: la alerta se emitió con una versión de la
                # lista que podía ser otra. Se dice que no se sabe, no se inventa un territorio.
                ambito=entrada.ambito if entrada else "",
            )
        )

    cuerpo = norma.documento_texto
    return AlertaPublica(
        id=alerta.id,
        emitida_en=alerta.emitida_en,
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
        # Diagnóstico del ADR 0018, no criterio: ver `pipeline/reglas.terminos_perdidos`.
        terminos_perdidos=[str(t) for t in _lista(evidencia.get("terminos_perdidos"))],
        # La cifra sale de la evidencia guardada al clasificar y no de contar `cambios`: así el
        # listado, que no trae los textos, dice igualmente cuántos preceptos hay archivados.
        preceptos_con_diff=int(evidencia.get("preceptos_con_diff") or 0),
        cambios=cambios or [],
        norma=NormaAlerta.model_validate(norma),
        texto_archivado=(
            TextoArchivadoAlerta.model_validate(cuerpo) if cuerpo is not None else None
        ),
    )
