"""Tests de la línea de órdenes del worker: rangos de fechas y modos de mantenimiento.

El worker no tenía tests propios porque su trabajo real lo hacen los servicios, que sí los
tienen. Estos existen por lo que la interfaz **decide**: qué días se ingieren y si se llama o no
al LLM. Un rango mal calculado significa días de boletín que nadie miró y nadie echó de menos,
que es el fallo silencioso que este proyecto no se permite.
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.database import Base
from app.models.fuente import AmbitoTerritorial, FormatoFuente, Fuente, TipoFuente
from app.security.url_guard import FalloDeRed
from worker import run
from worker.run import _dias, _parsear_argumentos


class TestRangoDeDias:
    def test_sin_hasta_es_un_solo_dia(self) -> None:
        dia = datetime.date(2024, 12, 19)

        assert _dias(dia, None) == [dia]

    def test_el_rango_incluye_los_dos_extremos(self) -> None:
        """Un rango que se dejara fuera el último día perdería un boletín entero cada vez."""
        dias = _dias(datetime.date(2024, 12, 17), datetime.date(2024, 12, 19))

        assert dias == [
            datetime.date(2024, 12, 17),
            datetime.date(2024, 12, 18),
            datetime.date(2024, 12, 19),
        ]

    def test_un_hasta_anterior_no_produce_un_rango_al_reves(self) -> None:
        """Con las fechas cambiadas se ingiere el día pedido, no cero días ni el mes al revés."""
        dia = datetime.date(2024, 12, 19)

        assert _dias(dia, datetime.date(2024, 12, 1)) == [dia]


class TestArgumentos:
    def test_ingerir_exige_saber_de_donde(self) -> None:
        with pytest.raises(SystemExit):
            _parsear_argumentos(["--fecha", "2024-12-19"])

    def test_los_modos_de_mantenimiento_no_necesitan_fuente(self) -> None:
        """Ninguno ingiere, así que pedirles `--fuente` sería pedir un dato que no usan."""
        for modo in ("--reprefiltrar", "--fase2", "--versionar", "--reclasificar"):
            assert _parsear_argumentos([modo]).fuente is None

    def test_sin_extraccion_es_opcional_y_por_defecto_no_se_salta_el_llm(self) -> None:
        """El valor por defecto importa: saltarse el LLM sin querer deja normas sin extraer.

        No se pierden —la cola es una consulta y una pasada normal las recoge— pero nadie se
        enteraría de que la pasada de hoy no las miró.
        """
        normal = _parsear_argumentos(["--fuente", "boe", "--fecha", "2024-12-19"])
        backfill = _parsear_argumentos(
            [
                "--fuente",
                "boe",
                "--fecha",
                "2024-11-15",
                "--hasta",
                "2024-12-16",
                "--sin-extraccion",
            ]
        )

        assert normal.sin_extraccion is False
        assert backfill.sin_extraccion is True
        assert backfill.hasta == datetime.date(2024, 12, 16)

    def test_una_fecha_con_formato_raro_se_rechaza_al_parsear(self) -> None:
        """Y no dentro del bucle: un rango que empieza mal no puede llegar a pedirle nada al BOE."""
        with pytest.raises(SystemExit):
            _parsear_argumentos(["--fuente", "boe", "--fecha", "19-12-2024"])


class TestUnFalloDeRedNoRompeLaPasada:
    """El incidente del 2026-09-11, fijado (ADR 0038).

    Un handshake TLS que expiró en el BON subió sin que nadie lo cogiera y **rompió el proceso
    con un traceback**. Costó el día de Navarra entero, que nada recupera solo. Y en un rango
    habría cortado el backfill a la mitad, aunque `main` promete lo contrario.
    """

    @staticmethod
    def _entorno(monkeypatch: pytest.MonkeyPatch, revienta: Exception) -> None:
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(engine)
        fabrica = sessionmaker(bind=engine)
        with fabrica() as sesion:
            sesion.add(
                Fuente(
                    nombre="Boletín Oficial de Navarra",
                    tipo=TipoFuente.BOLETIN_AUTONOMICO,
                    ambito_territorial=AmbitoTerritorial.AUTONOMICO,
                    ccaa="Navarra",
                    ccaa_codigo="NC",
                    formato=FormatoFuente.HTML,
                    url_base="https://bon.navarra.es/",
                    licencia_reutil=None,
                    activa=True,
                )
            )
            sesion.commit()

        def ingerir_que_falla(*_args: object, **_kwargs: object) -> tuple[object, ...]:
            raise revienta

        monkeypatch.setattr(run, "SessionLocal", fabrica)
        monkeypatch.setitem(
            run.FUENTES, "bon", (TipoFuente.BOLETIN_AUTONOMICO, "NC", ingerir_que_falla)
        )

    def test_se_registra_y_se_sale_con_1_en_vez_de_reventar(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._entorno(monkeypatch, FalloDeRed("bon.navarra.es no contestó en 3 intentos"))

        codigo = run._ingerir_dia(
            datetime.date(2026, 9, 11),
            get_settings(),
            fuente_pedida="bon",
            sin_extraccion=True,
        )

        assert codigo == 1

    def test_no_se_confunde_con_un_control_de_seguridad(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Salida 3 es «la fuente nos devolvió algo que no aceptamos», y aquí no devolvió nada.

        Si un timeout saliera con 3, el registro que existe para que un rechazo real no se pierda
        entre los fallos rutinarios de red se llenaría de fallos rutinarios de red.
        """
        self._entorno(monkeypatch, FalloDeRed("se agotó el tiempo"))

        codigo = run._ingerir_dia(
            datetime.date(2026, 9, 11),
            get_settings(),
            fuente_pedida="bon",
            sin_extraccion=True,
        )

        assert codigo != 3
