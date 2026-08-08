"""`/health` contra una base de datos real.

Este test **no puede pasar sin PostgreSQL**: comprueba justamente que `/health` verifica la
conexión de verdad y no devuelve "ok" a ciegas, así que sustituir la base por un doble
vaciaría el test de contenido.

Lo que sí se arregla aquí es cómo falla cuando no hay base de datos. Antes reventaba con
`assert 503 == 200`, que es un rojo que **acusa al código de un fallo que no ha cometido**:
la aplicación estaba respondiendo correctamente que no alcanza la base. Un rojo que miente
sobre su causa acaba siendo un rojo que se ignora, y una suite con un fallo permanente que
todo el mundo sabe saltar deja de servir para avisar de nada.

Ahora se distingue: sin PostgreSQL alcanzable **se salta con el motivo y el remedio
escritos**; con PostgreSQL delante se exige el 200 y no se perdona. Es el mismo criterio que
ya usaba `test_modelo_dominio.py` para los tests que necesitan las migraciones aplicadas.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine as engine_real
from app.main import app


def _hay_postgres() -> bool:
    """¿Se alcanza la base? Se prueba contra **la misma URL que usa el endpoint**.

    Se comprueba aparte y no deduciéndolo del 503 de `/health`: si el motivo del salto
    saliera de la propia respuesta, el test se saltaría también cuando el endpoint estuviera
    roto de verdad, que es exactamente el fallo que tiene que detectar.

    Engine propio y no el del endpoint solo por el `connect_timeout`. Fuera de docker,
    `DATABASE_URL` apunta a `db`, que no resuelve, y sin tope la sonda se quedaba **más de
    cuatro minutos** esperando al DNS antes de decidir saltar: un test que tarda eso en
    saltarse acaba haciendo que nadie ejecute la suite desde el host. El engine de producción
    no se toca — allí un timeout corto sería una decisión de disponibilidad, no de test.
    """
    sonda = create_engine(engine_real.url, connect_args={"connect_timeout": 2})
    try:
        with sonda.connect() as conexion:
            conexion.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
    finally:
        sonda.dispose()


def test_health_responde_200() -> None:
    if not _hay_postgres():
        pytest.skip(
            "no hay un PostgreSQL alcanzable en DATABASE_URL. Levanta la pila con "
            "`docker compose up -d` y ejecuta la suite dentro del contenedor: "
            "`docker compose exec backend python -m pytest`. Desde el host no basta, "
            "porque DATABASE_URL apunta a `db`, que solo resuelve en la red de compose."
        )

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_health_degrada_a_503_cuando_no_alcanza_la_base(monkeypatch: pytest.MonkeyPatch) -> None:
    """El otro lado del contrato, y el que de verdad importa en un healthcheck.

    Que `/health` devuelva 200 con la base delante demuestra poco: lo demostraría igual un
    endpoint que devolviera 200 siempre. Lo que hay que fijar es que **degrada** — que no
    arrastra al contenedor a declararse sano mientras no puede leer una sola fila. De este
    healthcheck cuelga el `depends_on: service_healthy` del compose y la exención del
    limitador de peticiones, así que un falso "ok" aquí se propaga.

    Se sustituye el engine del módulo del endpoint y no la variable de entorno: `app.database`
    crea el engine **al importarse**, así que a estas alturas cambiar `DATABASE_URL` no
    tocaría el engine que `/health` ya tiene cogido, y el test pasaría por el motivo
    equivocado.

    Corre siempre, con o sin PostgreSQL: no necesita ninguno, necesita justo lo contrario.
    """
    # Puerto 1: reservado y sin nadie escuchando. El `connect_timeout` no es cosmético —
    # medido: sin él este test tardaba **130 s** en Windows, porque un SYN a un puerto
    # filtrado se reintenta en vez de recibir un RST. Un test de degradación que tarda dos
    # minutos en degradar es un test que se acaba borrando.
    engine_muerto = create_engine(
        "postgresql+psycopg://nadie@127.0.0.1:1/no_existe",
        connect_args={"connect_timeout": 1},
    )
    monkeypatch.setattr("app.api.health.engine", engine_muerto)

    try:
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 503
        assert response.json() == {"status": "error", "database": "unreachable"}
    finally:
        engine_muerto.dispose()
