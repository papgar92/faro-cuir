"""API pública de solo lectura sobre lo ingerido.

Sin autenticación a propósito: el contenido son boletines oficiales, que son públicos por
definición, y la transparencia es el producto. Por eso mismo aquí **solo hay lecturas**: no
existe ningún endpoint que escriba. Lo que modifica el estado del sistema es el worker de
ingesta y, más adelante, el panel de revisión con autenticación (CLAUDE.md sección 4).
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import SessionLocal
from app.models.documento import Documento
from app.schemas.documento import DocumentoDetalle, DocumentoResumen

router = APIRouter(prefix="/api", tags=["documentos"])

# Tope duro de página. La API es pública y sin auth, así que el tamaño de página lo decide el
# servidor y no quien llama: sin esto, un `?limite=1000000` es una denegación de servicio
# gratuita contra la base de datos.
LIMITE_MAXIMO = 100


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


@router.get("/documentos", response_model=list[DocumentoResumen])
def listar_documentos(
    session: Session = Depends(get_session),
    fecha: datetime.date | None = Query(None, description="Filtra por fecha de publicación"),
    limite: int = Query(20, ge=1, le=LIMITE_MAXIMO),
    desplazamiento: int = Query(0, ge=0),
) -> list[Documento]:
    consulta = select(Documento).order_by(Documento.fecha_publicacion.desc(), Documento.id.desc())
    if fecha is not None:
        consulta = consulta.where(Documento.fecha_publicacion == fecha)
    return list(session.scalars(consulta.limit(limite).offset(desplazamiento)).all())


@router.get("/documentos/{documento_id}", response_model=DocumentoDetalle)
def obtener_documento(documento_id: int, session: Session = Depends(get_session)) -> Documento:
    documento = session.scalar(
        # selectinload en vez de dejar que el ORM cargue las normas una a una: un sumario
        # del BOE trae ~250 normas, y sin esto serían ~250 consultas por petición.
        select(Documento)
        .options(selectinload(Documento.normas))
        .where(Documento.id == documento_id)
    )
    if documento is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado")
    return documento
