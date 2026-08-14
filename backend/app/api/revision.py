"""Panel de revisión: la API del gate humano. Regla de oro 4, ADR 0003 y 0017.

Es la **única** parte de la API que escribe, y la única con autenticación. La API pública
(`api/documentos.py`) es de solo lectura y lo dice en su propia cabecera; esto es la otra mitad
de esa frase.

Tres controles que no son intercambiables y por eso están los tres:

1. **La sesión** (`security/panel.py`): cookie `HttpOnly` con token opaco, comprobada en cada
   petición por la dependencia `revisor_requerido`. Ningún endpoint de este router se sirve sin
   ella salvo el propio login.
2. **La cabecera `X-Faro-Panel`** en todo lo que escribe. La cookie va `SameSite=Strict`, así
   que un formulario de otro sitio ya no la lleva; esto es el cinturón sobre los tirantes,
   porque una cabecera propia no se puede mandar entre orígenes sin un *preflight* de CORS y
   este proyecto no activa CORS a propósito. Con las dos, aprobar una alerta desde otra pestaña
   no es un fallo de una sola configuración.
3. **El método**. Aprobar y descartar son `POST`; no existe forma de resolver un ítem con un
   `GET`, que es como un precargador de enlaces o una etiqueta `<img>` acabarían emitiendo una
   alerta sin que nadie pulsara nada.

Lo que este router **no** hace: emitir la alerta por su cuenta. La emite `services/revision.py`
al aprobar, y solo entonces. No hay ningún endpoint que cree una `alerta` directamente ni flag
que salte la cola, porque la regla de oro 4 no admite excepción.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.database import SessionLocal
from app.models.deteccion import ColaRevision, Deteccion, EstadoRevision
from app.models.norma import Norma
from app.schemas.revision import (
    Credenciales,
    ItemRevision,
    NormaRevision,
    ResolucionRevision,
    SesionAbierta,
    SpanEvidencia,
    TextoArchivadoRevision,
)
from app.security import panel
from app.services import revision as servicio

router = APIRouter(prefix="/api/revision", tags=["revision"])

COOKIE_SESION = "farocuir_panel"
# La cookie solo viaja a las rutas del panel. Un `Path=/` la mandaría también en cada lectura de
# la API pública, que no la necesita para nada: cuanto menos circula un secreto, menos sitios
# hay donde se pueda quedar.
COOKIE_PATH = "/api/revision"
CABECERA_PANEL = "X-Faro-Panel"

LIMITE_MAXIMO = 100

logger = logging.getLogger(__name__)

# Estos tres viven en el proceso, así que **este servicio es de proceso único**: uvicorn se
# arranca sin `--workers` (ver `docker-compose.yml`). Con varios procesos, las sesiones no se
# verían entre ellos (falla cerrado: 401 intermitentes, molesto pero seguro) y la cadencia se
# multiplicaría por el número de workers, que **falla abierto** y es el que importa. Escalar a
# varios procesos exige mover los dos almacenes a un sitio compartido; está en el ADR 0017.
_settings = get_settings()
_sesiones = panel.Sesiones(ttl_segundos=_settings.panel_sesion_ttl_segundos)
_cadencia = panel.CadenciaIntentos(
    intentos=_settings.panel_intentos_por_minuto, ventana_segundos=60.0
)
_cerrojo_password = threading.Lock()


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


def revisor_requerido(
    respuesta: Response,
    farocuir_panel: str | None = Cookie(default=None, alias=COOKIE_SESION),
) -> None:
    """Exige sesión válida. Lanza 401 sin decir por qué falló.

    No se distingue "no hay cookie" de "la cookie caducó" de "el token no existe": tres mensajes
    distintos son tres bits de información gratis para quien está probando.

    De paso marca la respuesta como no almacenable. Va aquí y no en el middleware de cabeceras
    porque es exactamente la condición que lo justifica: **detrás de sesión**. La API pública
    sirve boletines oficiales y puede cachearse; la cola de revisión lleva evidencia y notas de
    quien revisa, y no tiene por qué quedarse en ninguna caché intermedia.
    """
    respuesta.headers["Cache-Control"] = "no-store"
    if not _sesiones.es_valida(farocuir_panel):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión de revisión no válida.",
        )


def cabecera_panel_requerida(
    x_faro_panel: str | None = Header(default=None, alias=CABECERA_PANEL),
) -> None:
    """Segundo control anti-CSRF sobre las escrituras. Ver la cabecera del módulo."""
    if not x_faro_panel:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Falta la cabecera {CABECERA_PANEL}.",
        )


def _lista(valor: Any) -> list[Any]:
    return valor if isinstance(valor, list) else []


def _item(cola: ColaRevision, deteccion: Deteccion, norma: Norma) -> ItemRevision:
    """Arma la vista del ítem. Tolerante con la forma de `evidencia_json` a propósito.

    La fila pudo escribirla una versión anterior del clasificador, y una evidencia que no se
    entiende tiene que producir un ítem con menos información —para que alguien lo mire— y no
    un 500 que saca de la cola algo ya clasificado.
    """
    evidencia = deteccion.evidencia_json if isinstance(deteccion.evidencia_json, dict) else {}
    spans = [
        SpanEvidencia(
            inicio=int(span["inicio"]), fin=int(span["fin"]), fragmento=str(span["fragmento"])
        )
        for span in _lista(evidencia.get("spans"))
        if isinstance(span, dict) and {"inicio", "fin", "fragmento"} <= span.keys()
    ]
    cuerpo = norma.documento_texto
    return ItemRevision(
        id=cola.id,
        estado=cola.estado.value,
        creada_en=cola.creada_en,
        resuelta_en=cola.resuelta_en,
        nota_revision=cola.nota_revision,
        deteccion_id=deteccion.id,
        clasificacion=deteccion.clasificacion.value,
        origen=deteccion.origen.value,
        regla_aplicada=deteccion.regla_aplicada,
        severidad=deteccion.severidad,
        confianza=deteccion.confianza,
        version_reglas=evidencia.get("version_reglas"),
        version_texto_plano=evidencia.get("version_texto_plano"),
        normas_vigiladas=[str(x) for x in _lista(evidencia.get("normas_vigiladas"))],
        spans=spans,
        tiene_extraccion=deteccion.extraccion_json is not None,
        punteros_corroborados=len(_lista(evidencia.get("punteros_corroborados"))),
        punteros_sin_corroborar=len(_lista(evidencia.get("punteros_sin_corroborar"))),
        norma=NormaRevision.model_validate(norma),
        texto_archivado=(
            TextoArchivadoRevision.model_validate(cuerpo) if cuerpo is not None else None
        ),
    )


@router.post("/sesion", response_model=SesionAbierta)
def abrir_sesion(credenciales: Credenciales, respuesta: Response) -> SesionAbierta:
    """Login. Devuelve cuándo caduca; el token va en la cookie y nunca en el cuerpo.

    Sin cabecera anti-CSRF aquí a propósito: un CSRF de login solo consigue iniciarle sesión a
    alguien con una contraseña que el atacante ya tiene, y exigir la cabecera obligaría a
    pedirla antes de tener sesión. Lo que sí hay es cadencia (6.4: global, sin IP).

    **El orden de las tres operaciones es un control, no estilo** (ver `CadenciaIntentos`): se
    comprueba la contraseña primero, se entra si es correcta, y solo un fallo gasta cadencia.
    Al revés, quien no tuviera la contraseña podría dejar fuera a quien sí la tiene.
    """
    respuesta.headers["Cache-Control"] = "no-store"
    settings = get_settings()
    # Serializado: cada comprobación son ~50 ms y 16 MB de scrypt, y ahora se comprueba siempre.
    # Sin el cerrojo, una ráfaga de intentos convierte el control de acceso en un agotamiento de
    # memoria — el mismo razonamiento que el tope de clientes de `rate_limit.py`.
    with _cerrojo_password:
        correcta = panel.verificar_password(
            credenciales.password, hash_almacenado=settings.panel_password_hash
        )

    if not correcta:
        # Nada de la contraseña se registra, ni siquiera su longitud. El contador sí: es un
        # agregado sin identidades, y sin él el único control de acceso del proyecto sería
        # también el único sin rastro. La 6.4 prohíbe inventariar IPs, no contar fallos.
        quedaban = _cadencia.registrar_fallo()
        logger.warning(
            "Intento de acceso al panel fallido (%s fallidos en la ventana actual).",
            _cadencia.fallos_en_la_ventana(),
        )
        if not quedaban:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiados intentos de acceso al panel. Espera unos segundos.",
                headers={"Retry-After": "10"},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales no válidas."
        )

    token, caduca = _sesiones.crear()
    logger.info("Sesión del panel de revisión abierta. Sesiones vivas: %s.", len(_sesiones))
    respuesta.set_cookie(
        COOKIE_SESION,
        token,
        max_age=settings.panel_sesion_ttl_segundos,
        httponly=True,
        # `Secure` sin interruptor para apagarlo: la sesión del gate humano no viaja en claro.
        # Los navegadores tratan `localhost` como origen seguro, así que el desarrollo local a
        # través del proxy de Vite funciona igual.
        secure=True,
        samesite="strict",
        path=COOKIE_PATH,
    )
    return SesionAbierta(caduca_en=caduca)


@router.get(
    "/sesion",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(revisor_requerido)],
)
def comprobar_sesion() -> None:
    """204 si la sesión vale, 401 si no. Es lo que consulta el panel al cargar."""
    return None


@router.delete("/sesion", status_code=status.HTTP_204_NO_CONTENT)
def cerrar_sesion(
    respuesta: Response,
    farocuir_panel: str | None = Cookie(default=None, alias=COOKIE_SESION),
) -> None:
    """Cierre de sesión real: el token se invalida en el servidor, no solo en el navegador.

    Sin `revisor_requerido`: cerrar una sesión que ya no vale tiene que responder que está
    cerrada, no 401. Un logout que falla deja al navegador con la cookie puesta.
    """
    _sesiones.cerrar(farocuir_panel)
    # Los mismos atributos con los que se emitió, `secure` incluido: una cookie de borrado que
    # no coincide en atributos es una cookie que algunos navegadores no consideran la misma.
    respuesta.delete_cookie(
        COOKIE_SESION, path=COOKIE_PATH, httponly=True, secure=True, samesite="strict"
    )
    logger.info("Sesión del panel de revisión cerrada. Sesiones vivas: %s.", len(_sesiones))
    return None


def _consulta_cola() -> Select[tuple[ColaRevision, Deteccion, Norma]]:
    return (
        select(ColaRevision, Deteccion, Norma)
        .join(Deteccion, Deteccion.id == ColaRevision.deteccion_id)
        .join(Norma, Norma.id == Deteccion.norma_id)
        .options(selectinload(Norma.documento_texto))
    )


@router.get("/cola", response_model=list[ItemRevision], dependencies=[Depends(revisor_requerido)])
def listar_cola(
    session: Session = Depends(get_session),
    estado: EstadoRevision = Query(
        EstadoRevision.PENDIENTE, description="Estado del ítem de revisión"
    ),
    limite: int = Query(20, ge=1, le=LIMITE_MAXIMO),
    desplazamiento: int = Query(0, ge=0),
) -> list[ItemRevision]:
    """La cola. Ordenada por severidad declarada y luego por antigüedad.

    El orden lo decide el servidor y no quien llama, igual que el tope de página: es la cola de
    trabajo del gate humano, no un listado configurable.
    """
    filas = session.execute(
        _consulta_cola()
        .where(ColaRevision.estado == estado)
        .order_by(Deteccion.severidad.desc(), ColaRevision.creada_en, ColaRevision.id)
        .limit(limite)
        .offset(desplazamiento)
    ).all()
    return [_item(cola, deteccion, norma) for cola, deteccion, norma in filas]


@router.get(
    "/cola/{cola_id}", response_model=ItemRevision, dependencies=[Depends(revisor_requerido)]
)
def obtener_item(
    cola_id: int,
    session: Session = Depends(get_session),
) -> ItemRevision:
    fila = session.execute(_consulta_cola().where(ColaRevision.id == cola_id)).first()
    if fila is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ítem no encontrado")
    return _item(*fila)


def _resolver(session: Session, cola_id: int, aprobada: bool, nota: str | None) -> ItemRevision:
    try:
        if aprobada:
            servicio.aprobar(session, cola_id, nota=nota)
        else:
            servicio.descartar(session, cola_id, nota=nota)
    except servicio.ItemNoEncontrado as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except servicio.YaResuelta as exc:
        # 409 y no 400: el ítem existe y la petición es correcta; lo que pasa es que el estado
        # del recurso ya no admite esa transición. Es la diferencia entre "te has equivocado" y
        # "llegas tarde", y quien mira la cola desde dos pestañas se encuentra la segunda.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except servicio.RevisionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IntegrityError as exc:
        # La última red del gate: `alerta.deteccion_id` es único, así que dos aprobaciones
        # simultáneas del mismo ítem no pueden producir dos alertas ni aunque las dos pasen la
        # comprobación de estado. Aquí se traduce a la respuesta que ya significa "llegas tarde"
        # en vez de a un 500 que parecería un fallo del servidor.
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Otra revisión resolvió este ítem a la vez.",
        ) from exc
    fila = session.execute(_consulta_cola().where(ColaRevision.id == cola_id)).first()
    if fila is None:  # pragma: no cover - se acaba de resolver en esta misma transacción
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ítem no encontrado")
    return _item(*fila)


@router.post(
    "/cola/{cola_id}/aprobar",
    response_model=ItemRevision,
    dependencies=[Depends(revisor_requerido), Depends(cabecera_panel_requerida)],
)
def aprobar(
    cola_id: int,
    resolucion: ResolucionRevision | None = None,
    session: Session = Depends(get_session),
) -> ItemRevision:
    """Aprueba y **emite la alerta**. Es la acción con consecuencias del sistema entero."""
    return _resolver(session, cola_id, True, resolucion.nota if resolucion else None)


@router.post(
    "/cola/{cola_id}/descartar",
    response_model=ItemRevision,
    dependencies=[Depends(revisor_requerido), Depends(cabecera_panel_requerida)],
)
def descartar(
    cola_id: int,
    resolucion: ResolucionRevision | None = None,
    session: Session = Depends(get_session),
) -> ItemRevision:
    """Descarta. No crea alerta y no borra nada: la detección se queda con su evidencia."""
    return _resolver(session, cola_id, False, resolucion.nota if resolucion else None)
