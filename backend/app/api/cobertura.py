"""`GET /api/cobertura` — qué fuentes se conocen y cuáles se vigilan de verdad. ADR 0014.

Este endpoint existe para que la interfaz pueda **declarar sus huecos** en vez de callárselos.
Antes del ADR 0014 el sistema no tenía forma de expresar la diferencia entre "no sabemos que
haya nada" y "no estamos mirando"; ahora la tiene, y esta es la ruta que la publica.

Solo lectura y sin autenticación, como el resto de la API pública: lo que se expone es qué
boletines oficiales existen y cuáles se están leyendo, que es exactamente la información que
un proyecto de vigilancia tiene la obligación de hacer verificable sobre sí mismo.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.documento import Documento, TipoDocumento
from app.models.fuente import Fuente
from app.models.norma import EstadoPrefiltro, Norma
from app.pipeline import watchlist
from app.schemas.cobertura import Cobertura, CoberturaCcaa, CoberturaNivel, LeyVigente

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


def _ultima_publicacion(session: Session) -> dict[str | None, datetime.date]:
    """La fecha del boletín más reciente archivado de cada comunidad.

    Es lo que convierte «vigilada, sin alertas» de promesa en medición. La trama del mapa dice
    que ahí se mira; sin fecha no dice desde cuándo, y «lo leímos ayer y no había nada» se pinta
    igual que «lo leímos en marzo y desde entonces nadie ha vuelto».

    Se agrega en SQL por lo mismo que `_legibilidad`, y se toma de **sumarios**: son los
    boletines, y contar cuerpos o consolidados daría la fecha de un texto que puede ser de hace
    años (una norma de 2014 se descarga hoy, ADR 0015).

    La clave `None` es el BOE, que no pertenece a ninguna comunidad.
    """
    filas = session.execute(
        select(Fuente.ccaa_codigo, func.max(Documento.fecha_publicacion))
        .select_from(Documento)
        .join(Fuente, Fuente.id == Documento.fuente_id)
        .where(Documento.tipo == TipoDocumento.SUMARIO)
        .group_by(Fuente.ccaa_codigo)
    ).all()
    return {codigo: fecha for codigo, fecha in filas if fecha is not None}


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

    for codigo, fecha in _ultima_publicacion(session).items():
        if codigo is None:
            continue
        entrada_fecha = por_ccaa.get(codigo)
        if entrada_fecha is not None:
            entrada_fecha.ultima_publicacion = fecha

    # Qué comunidades no tienen ley autonómica que vigilar. El dato ya estaba verificado en la
    # watchlist y no llegaba a ninguna pantalla; ver la nota del campo en el esquema.
    lista = watchlist.watchlist()
    sin_ley = lista.sin_ley

    # Línea base por comunidad: las leyes autonómicas **en vigor**. Las derogadas se siguen
    # vigilando —no se pierde el rastro histórico— pero no son marco vigente.
    leyes: dict[str, list[LeyVigente]] = {}
    for norma in lista.normas:
        if norma.ambito in ("", "estatal") or not norma.vigente:
            continue
        leyes.setdefault(norma.ambito, []).append(
            LeyVigente(identificador=norma.identificador, titulo=norma.titulo, tipo=norma.tipo)
        )

    # **Una comunidad sin ley autonómica tiene que salir aunque no tenga ninguna fuente
    # registrada.** `por_ccaa` se construye desde las filas de `fuente`, y las uniprovinciales no
    # tienen BOP propio, así que Asturias —una de las dos sin ley, con Castilla y León— no
    # aparecía en la respuesta y su ausencia de marco no habría llegado a ninguna pantalla.
    # Justo la mitad del dato, y la mitad que menos se ve.
    #
    # No altera los totales: `conocidas_total` y `vigiladas_total` se suman de la consulta, no
    # de este diccionario.
    # Una comunidad con ley pero sin fuente registrada tampoco puede faltar: su marco es un
    # hecho, lo vigilemos o no. Mismo motivo que la vuelta de `sin_ley` de abajo.
    for codigo in list(sin_ley) + list(leyes):
        por_ccaa.setdefault(
            codigo,
            CoberturaCcaa(
                ccaa_codigo=codigo,
                # El código, no un nombre. `frontend/src/lib/territorio.ts` deriva los nombres
                # de la geometría del mapa precisamente para no mantener dos listas de
                # comunidades —«Euskadi» aquí y «País Vasco» allí es como se cruzan sin que
                # nada falle—, así que el backend no inventa una segunda tabla para dos filas.
                ccaa=codigo,
                niveles=[],
                conocidas=0,
                vigiladas=0,
                normas=0,
                ilegibles=0,
            ),
        )

    for codigo, entrada in por_ccaa.items():
        entrada.niveles.sort(key=lambda nivel: nivel.ambito)
        entrada.sin_ley_autonomica = sin_ley.get(codigo)
        entrada.leyes_vigentes = sorted(leyes.get(codigo, []), key=lambda ley: ley.identificador)

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
