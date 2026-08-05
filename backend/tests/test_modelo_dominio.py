"""Tests del modelo de dominio: minimizacion de suscriptores e inmutabilidad del historico.

No se testea que SQLAlchemy sepa crear tablas. Se testean las tres reglas del proyecto que
viven en el esquema y que un cambio futuro podria romper sin querer:

1. Los suscriptores son dato de categoria especial (CLAUDE.md 6.4).
2. La clasificacion no puede venir del LLM (regla de oro 2 y 3).
3. El historico de versiones de norma es inmutable (seccion 5).
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.deteccion import OrigenClasificacion
from app.models.suscriptor import Suscriptor
from app.security import hashing
from app.security.hashing import PepperNoConfigurado

PEPPER = "pepper-de-prueba-no-es-el-real"


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as sesion:
        yield sesion
    engine.dispose()


# --- 6.4: minimizacion de datos de suscriptores -------------------------------------------


def test_la_tabla_suscriptor_no_guarda_datos_que_no_necesita() -> None:
    """Lo que hace segura a esta tabla es lo que NO tiene.

    Este test existe para que anadir una de estas columnas sea una decision consciente que
    rompe un test, y no un campo que se cuela un dia porque "puede venir bien". Estar suscrito
    a alertas de derechos trans revela afinidad al colectivo (art. 9 RGPD): cada columna de
    mas es superficie de dano si la base de datos se filtra o se requisa.
    """
    columnas = set(Suscriptor.__table__.columns.keys())
    prohibidas = {
        "email",  # en claro, jamas
        "nombre",
        "apellidos",
        "telefono",
        "ip",
        "direccion_ip",
        "user_agent",
        "ultimo_acceso",
        "ultima_apertura",
        "aperturas",
        "genero",
        "identidad_genero",
    }
    assert columnas & prohibidas == set()


def test_el_email_no_se_guarda_en_claro() -> None:
    assert "email_hash" in Suscriptor.__table__.columns
    assert "email" not in Suscriptor.__table__.columns


def test_hash_email_falla_cerrado_sin_pepper() -> None:
    """Sin pepper se lanza, no se degrada a un hash sin sal.

    Una suscripcion no guardada es un problema. Un padron de personas del colectivo guardado
    con un hash reversible por diccionario es un problema mucho peor.
    """
    for pepper in (None, ""):
        with pytest.raises(PepperNoConfigurado):
            hashing.hash_email("persona@example.org", pepper=pepper)


def test_el_mismo_email_da_siempre_el_mismo_hash() -> None:
    """Es lo que permite que la unicidad funcione sin guardar la direccion."""
    uno = hashing.hash_email("persona@example.org", pepper=PEPPER)
    otro = hashing.hash_email("persona@example.org", pepper=PEPPER)
    assert uno == otro


@pytest.mark.parametrize(
    "variante", ["Persona@Example.org", "  persona@example.org  ", "PERSONA@EXAMPLE.ORG"]
)
def test_el_email_se_normaliza_antes_de_hashear(variante: str) -> None:
    canonico = hashing.hash_email("persona@example.org", pepper=PEPPER)
    assert hashing.hash_email(variante, pepper=PEPPER) == canonico


def test_sin_el_pepper_el_hash_no_es_reproducible() -> None:
    """Por eso el pepper vive en el entorno y no en una columna: si estuviera en la base de
    datos se filtraria junto con lo que protege y no serviria de nada."""
    con_el_nuestro = hashing.hash_email("persona@example.org", pepper=PEPPER)
    con_otro = hashing.hash_email("persona@example.org", pepper="otro-pepper")
    assert con_el_nuestro != con_otro


def test_el_hash_no_contiene_el_email() -> None:
    hash_ = hashing.hash_email("persona@example.org", pepper=PEPPER)
    assert "persona" not in hash_
    assert "example" not in hash_
    assert len(hash_) == 64


def test_el_token_de_baja_es_aleatorio_y_no_deriva_del_email() -> None:
    tokens = {hashing.token_baja_opaco() for _ in range(100)}
    assert len(tokens) == 100, "hay colisiones: el token no es aleatorio de verdad"
    for token in tokens:
        assert len(token) >= 32
        assert "persona" not in token


def test_se_puede_guardar_un_suscriptor_sin_conocer_su_email(session: Session) -> None:
    """El flujo completo de la 6.4: se guarda el hash y un token opaco, nada mas."""
    suscriptor = Suscriptor(
        email_hash=hashing.hash_email("persona@example.org", pepper=PEPPER),
        webhook_url=None,
        ccaa_interes=["Andalucía", "Comunidad de Madrid"],
        token_baja_opaco=hashing.token_baja_opaco(),
    )
    session.add(suscriptor)
    session.commit()

    guardado = session.get(Suscriptor, suscriptor.id)
    assert guardado is not None
    assert "persona@example.org" not in str(guardado.__dict__.values())


# --- Reglas de oro 2 y 3: el LLM no clasifica ----------------------------------------------


def test_no_existe_un_origen_de_clasificacion_que_sea_el_llm() -> None:
    """La regla de oro 2 hecha esquema.

    La clasificacion avance/retroceso se deriva del diff con reglas auditables. Al no existir
    el valor en el vocabulario, la CHECK de la base de datos hace que guardar "esto lo dijo el
    modelo" no sea siquiera representable, en vez de depender de que nadie lo escriba.
    """
    valores = {miembro.value for miembro in OrigenClasificacion}
    assert valores == {"derivado_diff", "heuristica"}
    assert not any("llm" in valor or "modelo" in valor for valor in valores)


# --- Seccion 5: el historico es inmutable ---------------------------------------------------


def _engine_postgres() -> object | None:
    """Engine contra el Postgres real, o None si no hay ninguno accesible.

    El trigger de inmutabilidad es especifico de PostgreSQL, asi que este test no puede correr
    sobre el SQLite que usa el resto de la suite. En CI hay un Postgres 16 con las migraciones
    aplicadas y el test corre; en local sin `docker compose` levantado, se salta.
    """
    # connect_timeout bajo: sin el, cuando no hay Postgres accesible el intento tarda minutos
    # en rendirse y bloquea la suite entera en vez de saltarse un test.
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"connect_timeout": 3})
    try:
        with engine.connect() as conexion:
            conexion.execute(text("SELECT 1 FROM version_norma LIMIT 1"))
    except SQLAlchemyError:
        engine.dispose()
        return None
    return engine


@pytest.mark.parametrize("operacion", ["UPDATE", "DELETE"])
def test_el_historico_de_versiones_no_se_puede_alterar(operacion: str) -> None:
    """La inmutabilidad se hace cumplir en la base de datos, no solo en el ORM.

    Un control que dependa de que nadie escriba un UPDATE a mano no es un control. Y si el
    archivo de lo que se publico se pudiera editar despues, no serviria como archivo.
    """
    engine = _engine_postgres()
    if engine is None:
        pytest.skip("no hay un PostgreSQL con las migraciones aplicadas")

    sentencias = {
        "UPDATE": "UPDATE version_norma SET texto_nuevo = 'reescrito' WHERE ordinal = 1",
        "DELETE": "DELETE FROM version_norma WHERE ordinal = 1",
    }

    try:
        with engine.begin() as conexion:  # type: ignore[attr-defined]
            conexion.execute(
                text(
                    "INSERT INTO fuente (nombre, tipo, formato, url_base, activa) "
                    "VALUES ('tmp-test', 'boe', 'api', 'https://x', true)"
                )
            )
            conexion.execute(
                text(
                    "INSERT INTO documento (fuente_id, identificador_oficial, fecha_publicacion,"
                    " url_original, sha256, sello_tiempo, ruta_almacen, estado_pipeline) "
                    "SELECT id, 'TMP-TEST-1', '2024-12-19', 'https://x', repeat('a', 64),"
                    " now(), 'aa/aa/x.xml', 'ingerido' FROM fuente WHERE nombre = 'tmp-test'"
                )
            )
            conexion.execute(
                text(
                    "INSERT INTO norma (documento_id, identificador_oficial, titulo) "
                    "SELECT id, 'TMP-TEST-N1', 'titulo' FROM documento "
                    "WHERE identificador_oficial = 'TMP-TEST-1'"
                )
            )
            conexion.execute(
                text(
                    "INSERT INTO version_norma (norma_id, ordinal, texto_nuevo) "
                    "SELECT id, 1, 'texto original' FROM norma "
                    "WHERE identificador_oficial = 'TMP-TEST-N1'"
                )
            )
            with pytest.raises(SQLAlchemyError, match="inmutable"):
                conexion.execute(text(sentencias[operacion]))
            # El fallo aborta la transaccion entera, asi que las filas de prueba no llegan a
            # persistir: no hace falta limpiar (y de hecho no se podria, por el mismo trigger).
    finally:
        engine.dispose()  # type: ignore[attr-defined]
