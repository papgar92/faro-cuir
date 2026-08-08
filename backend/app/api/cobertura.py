"""`GET /api/cobertura` — qué fuentes se conocen y cuáles se vigilan de verdad. ADR 0014.

Este endpoint existe para que la interfaz pueda **declarar sus huecos** en vez de callárselos.
Antes del ADR 0014 el sistema no tenía forma de expresar la diferencia entre "no sabemos que
haya nada" y "no estamos mirando"; ahora la tiene, y esta es la ruta que la publica.

Solo lectura y sin autenticación, como el resto de la API pública: lo que se expone es qué
boletines oficiales existen y cuáles se están leyendo, que es exactamente la información que
un proyecto de vigilancia tiene la obligación de hacer verificable sobre sí mismo.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.fuente import Fuente
from app.schemas.cobertura import Cobertura, CoberturaCcaa, CoberturaNivel

router = APIRouter(prefix="/api", tags=["cobertura"])


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


@router.get("/cobertura", response_model=Cobertura)
def obtener_cobertura(session: Session = Depends(get_session)) -> Cobertura:
    """Agrega en la base y no en Python.

    No es optimización prematura sobre 61 filas: es que la agregación en SQL no puede
    desincronizarse con lo que hay en la tabla. Contar en Python obligaría a traerse las filas
    y a repetir aquí la definición de "vigilada", que ya es la columna `activa`.
    """
    filas = session.execute(
        select(
            Fuente.ccaa_codigo,
            Fuente.ccaa,
            Fuente.ambito_territorial,
            func.count().label("conocidas"),
            func.count().filter(Fuente.activa).label("vigiladas"),
        ).group_by(Fuente.ccaa_codigo, Fuente.ccaa, Fuente.ambito_territorial)
    ).all()

    por_ccaa: dict[str, CoberturaCcaa] = {}
    conocidas_total = 0
    vigiladas_total = 0

    for codigo, nombre, ambito, conocidas, vigiladas in filas:
        conocidas_total += conocidas
        vigiladas_total += vigiladas
        # El BOE no pertenece a ninguna comunidad: suma al total y no al desglose. Meterlo en
        # una comunidad inventada seria peor que dejarlo fuera del mapa.
        if codigo is None or nombre is None:
            continue
        entrada = por_ccaa.setdefault(
            codigo,
            CoberturaCcaa(ccaa_codigo=codigo, ccaa=nombre, niveles=[], conocidas=0, vigiladas=0),
        )
        entrada.niveles.append(
            CoberturaNivel(ambito=str(ambito), conocidas=conocidas, vigiladas=vigiladas)
        )
        entrada.conocidas += conocidas
        entrada.vigiladas += vigiladas

    for entrada in por_ccaa.values():
        entrada.niveles.sort(key=lambda nivel: nivel.ambito)

    return Cobertura(
        conocidas=conocidas_total,
        vigiladas=vigiladas_total,
        por_ccaa=sorted(por_ccaa.values(), key=lambda c: c.ccaa_codigo),
    )
