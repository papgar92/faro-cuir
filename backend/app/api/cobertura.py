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
from app.models.documento import Documento, TipoDocumento
from app.models.fuente import Fuente
from app.models.norma import EstadoPrefiltro, Norma
from app.schemas.cobertura import Cobertura, CoberturaCcaa, CoberturaNivel

router = APIRouter(prefix="/api", tags=["cobertura"])


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


def _legibilidad(session: Session) -> dict[str | None, tuple[int, int]]:
    """Cuántas normas hay por comunidad y cuántas de ellas el pipeline no puede leer (ADR 0020).

    **Esto es lo que separa "vigilada" de "leída".** `Fuente.activa` dice que estamos suscritos a
    un boletín; no dice que sus documentos se puedan analizar. El DOGC lo demostró: fuente activa,
    ingesta correcta, huella y sello en cada documento, y 172 de 264 normas cuyo cuerpo archivado
    es la página de error del portal. Sin esta consulta, la única ruta del proyecto que existe
    para **declarar sus huecos** (ADR 0014) sería la única que no ve este.

    Se agrega en SQL por lo mismo que la consulta de fuentes: contar en Python obligaría a traerse
    miles de filas y a repetir aquí qué significa `ilegible`, que ya es un valor del enum.

    La clave `None` son las normas de fuentes sin comunidad —el BOE—, que suman al total y no al
    desglose. Se devuelven en vez de filtrarse para que el total del sistema no mienta por omisión.
    """
    filas = session.execute(
        select(
            Fuente.ccaa_codigo,
            func.count().label("normas"),
            func.count()
            .filter(Norma.prefiltro_estado == EstadoPrefiltro.ILEGIBLE)
            .label("ilegibles"),
        )
        .select_from(Norma)
        .join(Documento, Documento.id == Norma.documento_id)
        .join(Fuente, Fuente.id == Documento.fuente_id)
        .group_by(Fuente.ccaa_codigo)
    ).all()
    return {codigo: (normas, ilegibles) for codigo, normas, ilegibles in filas}


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

    legibilidad = _legibilidad(session)

    por_ccaa: dict[str, CoberturaCcaa] = {}
    conocidas_total = 0
    vigiladas_total = 0
    normas_total = 0
    ilegibles_total = 0

    for codigo, nombre, ambito, conocidas, vigiladas in filas:
        conocidas_total += conocidas
        vigiladas_total += vigiladas
        # El BOE no pertenece a ninguna comunidad: suma al total y no al desglose. Meterlo en
        # una comunidad inventada seria peor que dejarlo fuera del mapa.
        if codigo is None or nombre is None:
            continue
        entrada = por_ccaa.setdefault(
            codigo,
            CoberturaCcaa(
                ccaa_codigo=codigo,
                ccaa=nombre,
                niveles=[],
                conocidas=0,
                vigiladas=0,
                normas=0,
                ilegibles=0,
            ),
        )
        entrada.niveles.append(
            CoberturaNivel(ambito=str(ambito), conocidas=conocidas, vigiladas=vigiladas)
        )
        entrada.conocidas += conocidas
        entrada.vigiladas += vigiladas

    # El recuento de normas se suma **por comunidad y no por nivel**: la fila de `norma` sabe de
    # qué fuente viene, así que el desglose por ámbito sería exacto, pero un cuarto número dentro
    # de cada barra la vuelve ilegible y el hueco que hay que ver es el de la comunidad.
    for codigo, (normas, ilegibles) in legibilidad.items():
        normas_total += normas
        ilegibles_total += ilegibles
        entrada_ccaa = por_ccaa.get(codigo) if codigo is not None else None
        if entrada_ccaa is None:
            # Normas del BOE (sin comunidad), o de una fuente que ya no está en la tabla. Suman
            # al total y no al desglose, igual que las fuentes.
            continue
        entrada_ccaa.normas += normas
        entrada_ccaa.ilegibles += ilegibles

    for entrada in por_ccaa.values():
        entrada.niveles.sort(key=lambda nivel: nivel.ambito)

    # Los sumarios, que es lo que `GET /api/documentos` lista y lo que la portada llama
    # «documentos archivados». Los cuerpos y los consolidados no se cuentan aquí por lo mismo que
    # no se listan allí (ADR 0015): son material del archivo, no boletines ingeridos.
    documentos = session.scalar(
        select(func.count()).select_from(Documento).where(Documento.tipo == TipoDocumento.SUMARIO)
    )

    return Cobertura(
        conocidas=conocidas_total,
        vigiladas=vigiladas_total,
        normas=normas_total,
        ilegibles=ilegibles_total,
        documentos=documentos or 0,
        por_ccaa=sorted(por_ccaa.values(), key=lambda c: c.ccaa_codigo),
    )
