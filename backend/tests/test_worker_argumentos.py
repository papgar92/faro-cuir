"""Tests de la línea de órdenes del worker: rangos de fechas y modos de mantenimiento.

El worker no tenía tests propios porque su trabajo real lo hacen los servicios, que sí los
tienen. Estos existen por lo que la interfaz **decide**: qué días se ingieren y si se llama o no
al LLM. Un rango mal calculado significa días de boletín que nadie miró y nadie echó de menos,
que es el fallo silencioso que este proyecto no se permite.
"""

from __future__ import annotations

import datetime

import pytest

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
