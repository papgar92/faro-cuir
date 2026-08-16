"""Etapa 4 del pipeline: aplica el catálogo de reglas y persiste el veredicto. ADR 0016, 7.6.

Separado de `pipeline/reglas.py` con el mismo criterio que `services/prefiltro.py` frente a
`pipeline/prefiltro.py`: allí vive la decisión (qué es una supresión y qué significa), aquí
vive lo que la decisión hace en la base de datos.

**No toca la red ni el LLM.** Lee el cuerpo ya archivado, así que se puede relanzar entero
sobre los 652 documentos del almacén cada vez que cambie una regla, sin gastar una sola
petición al BOE ni los 133,9 s por norma que cuesta el extractor. Esa fue una de las cuatro
razones por las que el ADR 0016 descartó pedirle la supresión al modelo.

## Qué escribe, y por qué no siempre crea fila

- Si la norma **ya tiene** una `deteccion` —el centinela que dejó el extractor (ADR 0009)— se
  actualiza esa fila. Crear otra dejaría dos veredictos para una norma y ninguna forma de
  saber cuál manda.
- Si **no** la tiene, se crea con `extraccion_json` a NULL. Es la forma canónica que el ADR
  0016 describe: una detección derivada de reglas sobre el archivo no necesita que el LLM haya
  pasado por ahí, y de hecho el caso que motivó todo esto es una norma que el extractor no
  conseguía procesar.
- Si ninguna regla dispara, **no se escribe ningún veredicto**. `None` significa "este catálogo
  no tiene nada que decir", que no es "es neutro": hoy el catálogo solo sabe de supresiones, y
  escribir `neutro` sería inventar una conclusión que nadie ha sacado (regla de oro 8).

Nada de esto emite una alerta. Entre este servicio y `alerta` está el gate humano (regla de
oro 4), que sigue siendo obligatorio y sin flag que lo salte.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.deteccion import Alerta, Deteccion, OrigenClasificacion
from app.models.norma import EstadoPrefiltro, Norma, VersionNorma
from app.pipeline import prefiltro, reglas, watchlist
from app.pipeline.texto import VERSION_TEXTO_PLANO
from app.services.cuerpo import leer_cuerpo

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResumenClasificacion:
    """El embudo de esta etapa, con el mismo espíritu que `ResumenPrefiltro`."""

    evaluadas: int
    con_veredicto: int
    # Cuántas produjo cada regla. Una regla que no dispara nunca es una regla que sobra; una
    # que dispara siempre es una que no discrimina. Sin el desglose no se puede afinar una sin
    # tocar las otras — la misma lección que dejó `por_eje` en el prefiltro.
    por_regla: dict[str, int] = field(default_factory=dict)
    # Normas cuyo cuerpo archivado no se pudo leer o parsear. Van aparte de "sin veredicto"
    # porque no son lo mismo: aquí no se ha llegado a mirar nada.
    ilegibles: int = 0
    # Veredictos de una versión anterior del catálogo que la versión actual ya no sostiene.
    # Ver `aplicar`: no se borran solos.
    obsoletos: int = 0


# El mismo conjunto que la cola del extractor, y por el mismo motivo: el clasificador está
# **detrás** del prefiltro en el pipeline de la sección 7, y `descartada` significa fin. Se
# escribe con los dos valores explícitos y no con `!= DESCARTADA` para que una norma
# `pendiente` —sin cuerpo, esperando la fase 2— no entre aquí por descuido.
#
# La pérdida de recall es real y conviene tenerla escrita: una supresión dentro de una norma
# que el prefiltro descartó no se ve. Se acepta porque R-SUP-001, que es la regla que produce
# el veredicto grave, exige que el `<analisis>` declare una modificación de la watchlist — y
# eso ya hace `relevante` a la norma por el eje referencial, así que esa regla no pierde nada.
# Lo que se pierde es R-SUP-002 sobre normas ajenas al ámbito, que es precisamente el ruido que
# el prefiltro existe para quitar de en medio.
_COLA = (EstadoPrefiltro.RELEVANTE, EstadoPrefiltro.SOSPECHA)


def _pendientes(documento_id: int | None, forzar: bool):  # type: ignore[no-untyped-def]
    """Normas con cuerpo archivado a las que hay que (re)pasar el catálogo.

    La cola se pregunta por **las versiones y la fecha, nunca por el estado de la detección**.
    Es la lección que costó una regresión en el prefiltro: preguntar por el resultado hace que
    las normas sin resultado se reevalúen en cada pasada, el worker deja de ser idempotente y
    nadie se entera hasta ver la segunda ejecución procesando cientos de filas.

    Aquí ese caso es la mayoría —la mayor parte de las normas en cola no contienen ninguna
    supresión—, así que "sin veredicto" tiene que ser un estado registrado y no un hueco. Sin
    `reglas_evaluado_en`, cada pasada volvería a leer y parsear del almacén todas las demás.
    """
    consulta = select(Norma).where(
        Norma.documento_texto_id.is_not(None), Norma.prefiltro_estado.in_(_COLA)
    )
    if documento_id is not None:
        consulta = consulta.where(Norma.documento_id == documento_id)
    if not forzar:
        consulta = consulta.where(
            or_(
                Norma.reglas_evaluado_en.is_(None),
                Norma.reglas_version.is_(None),
                Norma.reglas_version != reglas.VERSION_REGLAS,
                # Los spans son offsets sobre el texto derivado: si cambia la derivación,
                # apuntan a otro sitio aunque el catálogo no se haya tocado.
                Norma.reglas_version_texto.is_(None),
                Norma.reglas_version_texto != VERSION_TEXTO_PLANO,
            )
        )
    return consulta.order_by(Norma.id)


def _punteros(deteccion: Deteccion | None) -> tuple[str, ...]:
    """Identificadores que el extractor citó sin texto por ninguno de los dos lados (ADR 0016).

    Se leen del JSON ya persistido y **solo alimentan el diagnóstico** de
    `reglas.corroborar`: ningún veredicto depende de ellos. Es la condición literal del ADR —
    un puntero alucinado es inerte— y por eso este servicio ni siquiera los pasa a la decisión,
    sino a la parte del veredicto que se guarda para poder medir.

    Tolerante con la forma del JSON a propósito: viene de una fila que pudo escribirse con otra
    versión del extractor, y un diagnóstico no puede tumbar la clasificación.
    """
    if deteccion is None or not isinstance(deteccion.extraccion_json, dict):
        return ()
    extraccion = deteccion.extraccion_json.get("extraccion")
    if not isinstance(extraccion, dict):
        return ()
    articulos = extraccion.get("articulos")
    if not isinstance(articulos, list):
        return ()
    return tuple(
        str(articulo.get("identificador", ""))
        for articulo in articulos
        if isinstance(articulo, dict)
        and articulo.get("texto_anterior") is None
        and articulo.get("texto_nuevo") is None
        and articulo.get("identificador")
    )


def _diffs(session: Session, norma_id: int) -> tuple[reglas.Diff, ...]:
    """Las redacciones anterior y nueva que el ADR 0018 archivó para esta norma.

    Se leen aquí y no en `pipeline/reglas.py` porque aquel módulo es puro: recibe datos, no
    consulta. Mismo reparto que con el texto archivado, que también lo lee este servicio.

    Orden por `ordinal` para que el diagnóstico sea determinista: dos pasadas sobre la misma
    base tienen que producir la misma lista de términos perdidos, o `VERSION_REGLAS` deja de
    significar «esto se puede reproducir».
    """
    filas = session.scalars(
        select(VersionNorma)
        .where(VersionNorma.norma_id == norma_id)
        .order_by(VersionNorma.ordinal, VersionNorma.id)
    ).all()
    return tuple(
        reglas.Diff(
            norma_afectada=fila.norma_afectada,
            bloque=fila.bloque,
            articulo=fila.articulo,
            texto_anterior=fila.texto_anterior,
            texto_nuevo=fila.texto_nuevo,
        )
        for fila in filas
    )


def _evidencia_json(veredicto: reglas.Veredicto, *, ahora: datetime.datetime) -> dict[str, object]:
    """Lo que hace falta para que un tercero rebata el veredicto sin ejecutar nuestro código.

    Las dos versiones van dentro y no solo en `norma`: una fila de `deteccion` tiene que poder
    leerse sola. Sin `version_texto_plano` los offsets no significan nada, porque no se sabría
    sobre qué derivación se midieron.
    """
    return {
        "regla": veredicto.regla,
        "version_reglas": veredicto.version_reglas,
        "version_texto_plano": VERSION_TEXTO_PLANO,
        "normas_vigiladas": list(veredicto.normas_vigiladas),
        "spans": [
            {"inicio": prueba.inicio, "fin": prueba.fin, "fragmento": prueba.fragmento}
            for prueba in veredicto.evidencia
        ],
        # Diagnóstico, no evidencia. Va en el mismo JSON porque se mira junto, pero con nombres
        # que dejan claro que no sostiene nada.
        "punteros_corroborados": list(veredicto.punteros_corroborados),
        "punteros_sin_corroborar": list(veredicto.punteros_sin_corroborar),
        # Diagnóstico de R-MOD-001 (ADR 0018). `preceptos_con_diff` es una cifra y no los
        # textos: esos viven en `version_norma`, y copiarlos aquí crearía dos sitios donde
        # leer la misma cita, que es como acaban dejando de coincidir.
        "terminos_perdidos": list(veredicto.terminos_perdidos),
        "preceptos_con_diff": veredicto.preceptos_con_diff,
        "version_vocabulario": prefiltro.VERSION_VOCABULARIO,
        "clasificado_en": ahora.isoformat(),
    }


def aplicar(
    session: Session,
    *,
    almacen_root: Path,
    documento_id: int | None = None,
    forzar: bool = False,
) -> ResumenClasificacion:
    """Pasa el catálogo y persiste. Idempotente: repetirlo sobre lo mismo no cambia nada.

    `documento_id=None` barre toda la tabla; es lo que hay que lanzar tras subir
    `VERSION_REGLAS` (`worker.run --reclasificar`).

    **Un veredicto que la versión nueva del catálogo ya no sostiene no se borra solo**: se
    cuenta y se registra con nivel de aviso para que lo mire una persona. Podría revertirse al
    centinela automáticamente, y se ha decidido que no: una detección es parte del rastro de
    auditoría, y un sistema que retira en silencio conclusiones que ya emitió es exactamente lo
    que este proyecto documenta que hacen las administraciones cuando desindexan una norma
    (6.5). Se queda visible, con la versión que la produjo escrita dentro.
    """
    ahora = datetime.datetime.now(datetime.UTC)
    lista = watchlist.watchlist()

    normas = list(session.scalars(_pendientes(documento_id, forzar)))
    con_veredicto = ilegibles = obsoletos = 0
    por_regla: dict[str, int] = {}

    for norma in normas:
        cuerpo = leer_cuerpo(norma, almacen_root=almacen_root)
        if cuerpo is None:
            # `leer_cuerpo` ya lo ha registrado. No se marca como evaluada: la próxima pasada
            # tiene que volver a intentarlo, porque el fallo puede ser del almacén y no del
            # documento. Mismo criterio de idempotencia que el extractor con una extracción
            # fallida — la que no deja fila vuelve a la cola sola.
            ilegibles += 1
            continue

        deteccion = session.scalar(select(Deteccion).where(Deteccion.norma_id == norma.id))
        veredicto = reglas.clasificar(
            cuerpo.texto,
            referencias=cuerpo.referencias,
            lista=lista,
            punteros=_punteros(deteccion),
            diffs=_diffs(session, norma.id),
        )

        if veredicto is None:
            if deteccion is not None and deteccion.regla_aplicada is not None:
                obsoletos += 1
                logger.warning(
                    "La detección %s de %s la produjo la regla %s y el catálogo %s ya no la "
                    "sostiene. No se retira sola: revísala.",
                    deteccion.id,
                    norma.identificador_oficial,
                    deteccion.regla_aplicada,
                    reglas.VERSION_REGLAS,
                )
        else:
            if deteccion is None:
                # `extraccion_json` a NULL: esta detección no la sostiene el modelo, la sostiene
                # el archivo. Es la forma canónica del ADR 0016.
                deteccion = Deteccion(norma_id=norma.id, extraccion_json=None)
                session.add(deteccion)
            deteccion.clasificacion = veredicto.clasificacion
            deteccion.origen = OrigenClasificacion.DERIVADO_DIFF
            deteccion.regla_aplicada = veredicto.regla
            deteccion.severidad = veredicto.severidad
            deteccion.confianza = veredicto.confianza
            if session.scalar(select(Alerta.id).where(Alerta.deteccion_id == deteccion.id)):
                # La otra cara del hallazgo 1 de la auditoría del 2026-08-16: esta detección ya
                # se publicó, así que reescribir su evidencia cambia lo que lee quien recibió la
                # alerta. No se impide —el catálogo nuevo puede ser mejor y ocultarlo sería peor—
                # pero **no puede pasar en silencio**: es material publicado que cambia sin que
                # nadie lo revise, y hasta que exista un flujo de re-revisión (7.7) esto es lo
                # único que lo hace visible.
                logger.warning(
                    "La detección %s de %s YA TIENE ALERTA EMITIDA y el catálogo %s reescribe su "
                    "evidencia. Lo que se publicó y lo que se publica dejan de coincidir: "
                    "revísalo.",
                    deteccion.id,
                    norma.identificador_oficial,
                    reglas.VERSION_REGLAS,
                )
            deteccion.evidencia_json = _evidencia_json(veredicto, ahora=ahora)
            con_veredicto += 1
            por_regla[veredicto.regla] = por_regla.get(veredicto.regla, 0) + 1

        norma.reglas_version = reglas.VERSION_REGLAS
        norma.reglas_version_texto = VERSION_TEXTO_PLANO
        norma.reglas_evaluado_en = ahora

    session.commit()

    return ResumenClasificacion(
        evaluadas=len(normas),
        con_veredicto=con_veredicto,
        por_regla=por_regla,
        ilegibles=ilegibles,
        obsoletos=obsoletos,
    )
