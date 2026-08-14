"""API pública de alertas: lo aprobado, y solo lo aprobado.

Sin autenticación, como el resto de la API pública, y **de solo lectura**. Lo que la separa de
`api/documentos.py` es que aquí el proyecto no publica un hecho de la fuente sino una conclusión
propia, así que cada respuesta lleva con qué comprobarla: la regla, su versión, los fragmentos
del texto archivado con sus offsets y la huella del documento.

**El control que sostiene todo esto es de dónde se lee.** La consulta parte de `alerta`, no de
`deteccion`. Una fila de `alerta` solo la escribe `services/revision.aprobar` (regla de oro 4),
así que «aprobada por una persona» no es un campo que haya que acordarse de filtrar —y que
alguien pueda olvidar mañana al añadir un endpoint— sino la tabla de la que se parte. Un
`WHERE revisada = true` habría sido equivalente hoy y frágil para siempre.

Hay un test que crea detecciones pendientes, descartadas y clasificadas sin aprobar y comprueba
que **ninguna** aparece aquí.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.database import SessionLocal
from app.models.deteccion import Alerta, Deteccion
from app.models.documento import Documento
from app.models.norma import Norma
from app.pipeline import watchlist
from app.schemas.alerta import (
    AlertaPublica,
    NormaAlerta,
    NormaVigiladaAfectada,
    SpanEvidenciaPublico,
    TextoArchivadoAlerta,
)

router = APIRouter(prefix="/api", tags=["alertas"])

LIMITE_MAXIMO = 100


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


def _lista(valor: Any) -> list[Any]:
    return valor if isinstance(valor, list) else []


def _consulta() -> Select[tuple[Alerta, Deteccion, Norma]]:
    return (
        select(Alerta, Deteccion, Norma)
        .join(Deteccion, Deteccion.id == Alerta.deteccion_id)
        .join(Norma, Norma.id == Deteccion.norma_id)
        # El sumario, explícito y no por relación, porque hace falta **ordenar** por su fecha.
        # `norma` tiene dos documentos (el sumario y el cuerpo, ADR 0015) y por eso la condición
        # va escrita: dejar que el ORM elija sería elegir al azar entre dos caminos distintos.
        .join(Documento, Documento.id == Norma.documento_id)
        # Los dos documentos: el sumario da la fecha de publicación y el cuerpo la huella.
        .options(selectinload(Norma.documento), selectinload(Norma.documento_texto))
    )


def _alerta(alerta: Alerta, deteccion: Deteccion, norma: Norma) -> AlertaPublica:
    """Arma la vista pública. Tolerante con la forma de `evidencia_json`, como el panel.

    Una fila escrita por una versión anterior del clasificador tiene que producir una alerta con
    menos información, no un 500: la alerta ya fue aprobada por una persona y retirarla del
    listado por un problema de formato sería desindexarla en silencio, que es justo lo que este
    proyecto documenta como el daño a evitar (6.5).
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
        norma=NormaAlerta.model_validate(norma),
        texto_archivado=(
            TextoArchivadoAlerta.model_validate(cuerpo) if cuerpo is not None else None
        ),
    )


@router.get("/alertas", response_model=list[AlertaPublica])
def listar_alertas(
    session: Session = Depends(get_session),
    clasificacion: str | None = Query(
        None, description="Filtra por clasificación (avance, retroceso, neutro, indeterminado)"
    ),
    limite: int = Query(20, ge=1, le=LIMITE_MAXIMO),
    desplazamiento: int = Query(0, ge=0),
) -> list[AlertaPublica]:
    """Las alertas emitidas, de la más reciente a la más antigua.

    Ordenadas por **fecha de publicación del boletín** y no por cuándo se aprobaron: una
    cronología de retrocesos es una cronología de lo que pasó, no de cuándo lo miramos nosotros.
    """
    consulta = _consulta()
    if clasificacion is not None:
        # Comparación contra la columna, sin interpolar: el valor viene de fuera y el enum de la
        # base de datos rechaza cualquier cosa que no sea uno de los cuatro.
        consulta = consulta.where(Deteccion.clasificacion == clasificacion)
    filas = session.execute(
        consulta.order_by(Documento.fecha_publicacion.desc(), Alerta.id.desc())
        .limit(limite)
        .offset(desplazamiento)
    ).all()
    return [_alerta(*fila) for fila in filas]


@router.get("/alertas/{alerta_id}", response_model=AlertaPublica)
def obtener_alerta(alerta_id: int, session: Session = Depends(get_session)) -> AlertaPublica:
    fila = session.execute(_consulta().where(Alerta.id == alerta_id)).first()
    if fila is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alerta no encontrada")
    return _alerta(*fila)
