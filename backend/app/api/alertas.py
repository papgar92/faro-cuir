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
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.deteccion import Alerta, ColaRevision, Deteccion
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
        # **Se filtra por el signo QUE SE VE, no por el que derivó la regla.** Son dos columnas
        # distintas a propósito (ADR 0004: la regla y la persona son dos fuentes de autoridad), y
        # la tarjeta enseña `clasificacion_humana` cuando existe. Filtrar solo por la de la regla
        # hacía que el filtro y la pantalla no hablaran de lo mismo: con tres alertas cuya regla
        # se abstuvo (`indeterminado`) y a las que una persona puso «avance», el botón «Avances»
        # no devolvía ninguna y el botón «Sin signo» las devolvía a las tres — enseñando tarjetas
        # que ponen «Avance» bajo el filtro de las que no tienen signo. Encontrado usando la web
        # el 2026-08-22.
        #
        # `coalesce` y no un `or_`: es la MISMA regla de precedencia que aplica `AlertCard`
        # (`clasificacion_humana ?? clasificacion`), escrita una vez en cada lado. Si algún día
        # cambia la precedencia, tienen que cambiar las dos y el test de abajo lo nota.
        #
        # Comparación contra las columnas, sin interpolar: el valor viene de fuera y el enum de
        # la base rechaza cualquier cosa que no sea uno de los cuatro.
        consulta = consulta.where(
            func.coalesce(ColaRevision.clasificacion_humana, Deteccion.clasificacion)
            == clasificacion
        )
    filas = session.execute(
        consulta.order_by(Documento.fecha_publicacion.desc(), Alerta.id.desc())
        .limit(limite)
        .offset(desplazamiento)
    ).all()
    alertas = []
    for alerta, deteccion, norma, revision in filas:
        publica = servicio.a_publica(alerta, deteccion, norma, revision)
        # Una muestra por alerta: el primer precepto reescrito, recortado. Sin esto la tarjeta
        # anuncia «34 preceptos» y no enseña ninguno, que es pedir que se fíen — lo contrario de
        # lo que esta herramienta le exige a la administración. El texto entero, en el detalle.
        muestra = servicio.cambios_de(
            session,
            norma.id,
            [vigilada.identificador for vigilada in publica.normas_vigiladas],
            emitida_en=alerta.emitida_en,
            limite=servicio.MAX_CAMBIOS_MUESTRA,
            max_caracteres=servicio.MAX_CARACTERES_MUESTRA,
        )
        alertas.append(publica.model_copy(update={"cambios": muestra}))
    return alertas


@router.get("/alertas/{alerta_id}", response_model=AlertaPublica)
def obtener_alerta(alerta_id: int, session: Session = Depends(get_session)) -> AlertaPublica:
    fila = session.execute(servicio.consulta().where(Alerta.id == alerta_id)).first()
    if fila is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alerta no encontrada")
    alerta, deteccion, norma, revision = fila
    # El detalle es el único sitio donde viajan las redacciones enteras (ADR 0018). En el listado
    # serían varios megas por página; aquí son lo que se ha venido a ver.
    publica = servicio.a_publica(alerta, deteccion, norma, revision)
    cambios = servicio.cambios_de(
        session,
        norma.id,
        [vigilada.identificador for vigilada in publica.normas_vigiladas],
        # Lo que se publica es el archivo tal y como estaba al aprobarse, no el de hoy.
        emitida_en=alerta.emitida_en,
    )
    return publica.model_copy(update={"cambios": cambios})
