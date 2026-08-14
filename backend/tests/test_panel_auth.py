"""Tests de `security/panel.py`: la autenticación del gate humano (ADR 0017).

Módulo puro (ni base de datos ni HTTP), así que se prueba sin montar nada. Lo que se comprueba
no es que scrypt funcione —eso es de la biblioteca estándar— sino las decisiones propias: que
se falle cerrado cuando falta configuración, que un hash corrupto no se confunda con una
contraseña equivocada, que cerrar sesión invalide de verdad y que la cadencia sea una cadencia
y no un bloqueo permanente.
"""

from __future__ import annotations

import pytest

from app.security import panel

PASSWORD = "una contraseña larga de revisión"
# Derivar cuesta decenas de milisegundos a propósito (es la defensa), así que se hace una vez.
HASH = panel.generar_hash(PASSWORD)


class TestContrasena:
    def test_la_correcta_verifica_y_otra_no(self) -> None:
        assert panel.verificar_password(PASSWORD, hash_almacenado=HASH)
        assert not panel.verificar_password(PASSWORD + "x", hash_almacenado=HASH)

    def test_dos_hashes_de_la_misma_contrasena_son_distintos(self) -> None:
        """Sal por credencial: sin ella, dos despliegues con la misma clave se delatarían."""
        assert panel.generar_hash(PASSWORD) != panel.generar_hash(PASSWORD)

    def test_el_hash_no_contiene_la_contrasena(self) -> None:
        assert PASSWORD not in HASH
        assert HASH.startswith("scrypt$")

    def test_los_parametros_viajan_dentro_del_hash(self) -> None:
        """Para poder subirlos mañana sin invalidar lo ya generado."""
        etiqueta, n, r, p, sal, clave = HASH.split("$")
        assert (etiqueta, int(n), int(r), int(p)) == ("scrypt", 2**14, 8, 1)
        assert len(bytes.fromhex(sal)) == 16
        assert len(bytes.fromhex(clave)) == 32

    def test_sin_hash_configurado_lanza_en_vez_de_dejar_pasar(self) -> None:
        """Falla cerrado. Un panel que se abre porque nadie configuró nada es lo peor posible."""
        with pytest.raises(panel.PanelNoConfigurado):
            panel.verificar_password(PASSWORD, hash_almacenado=None)
        with pytest.raises(panel.PanelNoConfigurado):
            panel.verificar_password(PASSWORD, hash_almacenado="")

    @pytest.mark.parametrize(
        "corrupto",
        [
            "no-es-un-hash",
            "bcrypt$1$2$3$aa$bb",  # algoritmo que no soportamos
            "scrypt$16384$8$1$zz$aa",  # sal que no es hexadecimal
            "scrypt$16384$8$aa$bb",  # le faltan campos
        ],
    )
    def test_un_hash_corrupto_lanza_y_no_se_confunde_con_clave_incorrecta(
        self, corrupto: str
    ) -> None:
        """La distinción importa: un 401 por hash roto se depura durante horas."""
        with pytest.raises(panel.HashPanelInvalido):
            panel.verificar_password(PASSWORD, hash_almacenado=corrupto)

    def test_el_mensaje_de_error_no_lleva_el_hash(self) -> None:
        """Aunque no sea la contraseña, es material de autenticación y no va a un log."""
        with pytest.raises(panel.HashPanelInvalido) as excinfo:
            panel.verificar_password(PASSWORD, hash_almacenado="scrypt$16384$8$1$zz$aa")
        assert "zz" not in str(excinfo.value)

    def test_no_se_deriva_hash_de_una_contrasena_vacia(self) -> None:
        with pytest.raises(ValueError):
            panel.generar_hash("")


class TestSesiones:
    def test_un_token_recien_creado_vale_y_uno_inventado_no(self) -> None:
        sesiones = panel.Sesiones(ttl_segundos=60)
        token, _ = sesiones.crear()
        assert sesiones.es_valida(token)
        assert not sesiones.es_valida("token-inventado")
        assert not sesiones.es_valida(None)
        assert not sesiones.es_valida("")

    def test_dos_sesiones_no_comparten_token(self) -> None:
        sesiones = panel.Sesiones(ttl_segundos=60)
        primero, _ = sesiones.crear()
        segundo, _ = sesiones.crear()
        assert primero != segundo
        assert sesiones.es_valida(primero) and sesiones.es_valida(segundo)

    def test_cerrar_invalida_en_el_servidor(self) -> None:
        """Media razón de no usar un JWT sin estado: esto es un logout de verdad."""
        sesiones = panel.Sesiones(ttl_segundos=60)
        token, _ = sesiones.crear()
        sesiones.cerrar(token)
        assert not sesiones.es_valida(token)

    def test_caduca_sola(self) -> None:
        sesiones = panel.Sesiones(ttl_segundos=0)
        token, _ = sesiones.crear()
        assert not sesiones.es_valida(token)
        assert len(sesiones) == 0

    def test_el_token_no_se_guarda_en_claro(self) -> None:
        """Se indexa por sha256: un volcado de memoria no entrega una sesión usable."""
        sesiones = panel.Sesiones(ttl_segundos=60)
        token, _ = sesiones.crear()
        assert token not in repr(sesiones.__dict__)

    def test_hay_tope_de_sesiones_vivas(self) -> None:
        """Sin tope, el propio control de acceso sería el vector de agotamiento de memoria."""
        sesiones = panel.Sesiones(ttl_segundos=60, maximo=3)
        tokens = [sesiones.crear()[0] for _ in range(5)]
        assert len(sesiones) == 3
        # Se cierran las más antiguas, no se rechaza el login: el revisor no puede quedarse
        # fuera por sesiones que quizá ya nadie usa.
        assert sesiones.es_valida(tokens[-1])
        assert not sesiones.es_valida(tokens[0])


class TestCadencia:
    def test_aguanta_hasta_el_tope_de_fallos_y_luego_avisa(self) -> None:
        cadencia = panel.CadenciaIntentos(intentos=3, ventana_segundos=60)
        assert [cadencia.registrar_fallo() for _ in range(4)] == [True, True, True, False]

    def test_se_recupera_con_el_tiempo_y_no_es_un_bloqueo(self) -> None:
        """Un bloqueo permanente convertiría el freno en una denegación de servicio al revisor."""
        cadencia = panel.CadenciaIntentos(intentos=2, ventana_segundos=0.05)
        assert cadencia.registrar_fallo() and cadencia.registrar_fallo()
        assert not cadencia.registrar_fallo()
        import time

        time.sleep(0.06)
        assert cadencia.registrar_fallo()

    def test_cuenta_los_fallos_de_la_ventana_para_el_log(self) -> None:
        cadencia = panel.CadenciaIntentos(intentos=5, ventana_segundos=600)
        assert cadencia.fallos_en_la_ventana() == 0
        cadencia.registrar_fallo()
        cadencia.registrar_fallo()
        assert cadencia.fallos_en_la_ventana() == 2
