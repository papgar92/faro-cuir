"""API pública de hallazgos históricos. ADR 0025, decisiones 3 y 4.

**Separada de `api/alertas.py` a propósito, y no por orden.** Son dos superficies que afirman
cosas distintas: una alerta dice «una persona lo revisó y decidió publicarlo»; un hallazgo dice
«el archivo prueba que esto cambió y alguien con nombre ya lo denunció, y de este proyecto no lo
ha mirado nadie». Mezclarlas en una ruta con un parámetro las volvería la misma cosa con una
etiqueta, y la etiqueta se cae en el primer refactor.

Quién decide qué sale de aquí es `services/hallazgos.consulta()`, con las tres condiciones en el
`where`. Este módulo no filtra nada por su cuenta: si lo hiciera, habría dos sitios donde se
decide qué se publica sin revisión humana, que es uno de más.

Hay un test que siembra los tres casos que NO deben salir —informe con semáforo `mirar`, informe
`alerta` ya aprobado, e informe `alerta` sin corroboraciones— y comprueba que la lista vuelve
vacía.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.deteccion import Deteccion, InformeRevision
from app.models.documento import Documento
from app.schemas.hallazgo import HallazgoPublico
from app.services import alertas as servicio_alertas
from app.services import hallazgos as servicio

router = APIRouter(prefix="/api", tags=["hallazgos"])

LIMITE_MAXIMO = 100


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


@router.get("/hallazgos", response_model=list[HallazgoPublico])
def listar_hallazgos(
    session: Session = Depends(get_session),
    clasificacion: str | None = Query(
        None, description="Filtra por clasificación (avance, retroceso, neutro, indeterminado)"
    ),
    limite: int = Query(20, ge=1, le=LIMITE_MAXIMO),
    desplazamiento: int = Query(0, ge=0),
) -> list[HallazgoPublico]:
    """Los hallazgos, del boletín más reciente al más antiguo.

    Ordenados por **fecha de publicación del boletín**, igual que las alertas y por la misma
    razón: una cronología de retrocesos es una cronología de lo que pasó, no de cuándo lo
    miramos nosotros. En un histórico de años esto importa más todavía.
    """
    consulta = servicio.consulta()
    if clasificacion is not None:
        # Contra la columna, sin interpolar: el valor viene de fuera y el enum de la base
        # rechaza cualquier cosa que no sea uno de los cuatro.
        consulta = consulta.where(Deteccion.clasificacion == clasificacion)
    filas = session.execute(
        consulta.order_by(Documento.fecha_publicacion.desc(), InformeRevision.id.desc())
        .limit(limite)
        .offset(desplazamiento)
    ).all()
    return [
        # Una muestra por hallazgo, como en el listado de alertas: la tarjeta que anuncia «9
        # preceptos» sin enseñar ninguno le pide al lector que se fíe, que es justo lo que esta
        # herramienta le exige a la administración. El texto entero, en el detalle.
        servicio.con_cambios(
            session,
            informe,
            deteccion,
            norma,
            limite=servicio_alertas.MAX_CAMBIOS_MUESTRA,
            max_caracteres=servicio_alertas.MAX_CARACTERES_MUESTRA,
        )
        for informe, _cola, deteccion, norma in filas
    ]


@router.get("/hallazgos/{hallazgo_id}", response_model=HallazgoPublico)
def obtener_hallazgo(hallazgo_id: int, session: Session = Depends(get_session)) -> HallazgoPublico:
    """Un hallazgo con las redacciones enteras (ADR 0018).

    El 404 sale de la **misma consulta** que el listado, así que un informe que deje de ser
    publicable —porque alguien lo aprobó, o porque se le quitaron las corroboraciones— deja de
    responder aquí sin que haya que acordarse de nada.
    """
    fila = session.execute(servicio.consulta().where(InformeRevision.id == hallazgo_id)).first()
    if fila is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hallazgo no encontrado")
    informe, _cola, deteccion, norma = fila
    return servicio.con_cambios(
        session,
        informe,
        deteccion,
        norma,
        limite=servicio_alertas.MAX_CAMBIOS_PUBLICADOS,
        max_caracteres=servicio_alertas.MAX_CARACTERES_REDACCION,
    )
