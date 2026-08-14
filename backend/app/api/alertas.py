"""API pública de alertas: lo aprobado, y solo lo aprobado.

Sin autenticación, como el resto de la API pública, y **de solo lectura**. Lo que la separa de
`api/documentos.py` es que aquí el proyecto no publica un hecho de la fuente sino una conclusión
propia, así que cada respuesta lleva con qué comprobarla: la regla, su versión, los fragmentos
del texto archivado con sus offsets y la huella del documento.

La consulta y la vista viven en `services/alertas.py`, compartidas con el feed Atom (ADR 0010).
Ahí está escrito por qué partir de la tabla `alerta` es el control y no un detalle.

Hay un test que crea detecciones pendientes, descartadas y clasificadas sin aprobar y comprueba
que **ninguna** aparece aquí.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.deteccion import Alerta, Deteccion
from app.models.documento import Documento
from app.schemas.alerta import AlertaPublica
from app.services import alertas as servicio

router = APIRouter(prefix="/api", tags=["alertas"])

LIMITE_MAXIMO = 100


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


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
    consulta = servicio.consulta()
    if clasificacion is not None:
        # Comparación contra la columna, sin interpolar: el valor viene de fuera y el enum de la
        # base de datos rechaza cualquier cosa que no sea uno de los cuatro.
        consulta = consulta.where(Deteccion.clasificacion == clasificacion)
    filas = session.execute(
        consulta.order_by(Documento.fecha_publicacion.desc(), Alerta.id.desc())
        .limit(limite)
        .offset(desplazamiento)
    ).all()
    return [servicio.a_publica(*fila) for fila in filas]


@router.get("/alertas/{alerta_id}", response_model=AlertaPublica)
def obtener_alerta(alerta_id: int, session: Session = Depends(get_session)) -> AlertaPublica:
    fila = session.execute(servicio.consulta().where(Alerta.id == alerta_id)).first()
    if fila is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alerta no encontrada")
    return servicio.a_publica(*fila)
