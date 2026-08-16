"""Genera el valor de `PANEL_PASSWORD_HASH` para el panel de revisión (ADR 0017).

    docker compose exec -it backend python -m scripts.generar_hash_panel

Como `medir_fase2.py`, se ejecuta **como módulo**: por ruta, `sys.path` apunta a `scripts/` y
el paquete `app` no se encuentra.

Existe para que nadie tenga que deducir el formato del hash a mano y, sobre todo, para que la
contraseña en claro no pase nunca por una variable de entorno, un fichero ni el historial del
intérprete de órdenes: se teclea, se deriva y solo sale el hash. `getpass` no la muestra en
pantalla y la pide dos veces, porque una contraseña mal tecleada aquí se descubre cuando el
panel no abre y no hay forma de averiguar cuál era.
"""

from __future__ import annotations

import getpass
import sys

from app.security.panel import generar_hash

# Un panel es tan fuerte como su contraseña, y esta protege la única puerta por la que una
# detección se convierte en alerta publicable. No es una política de complejidad con símbolos
# obligatorios —esas producen contraseñas peores y anotadas en un papel—: es longitud mínima.
LONGITUD_MINIMA = 12


def _pedir(prompt: str) -> str:
    """`getpass` o un mensaje que se entienda, nunca un traceback.

    Sin un terminal de verdad —una tubería, un `docker exec` sin `-t`, el prefijo `!` de Claude
    Code— `getpass` no puede apagar el eco y acaba lanzando `EOFError`. Eso salían veinte líneas
    de traza de Python que no dicen qué hacer, y en un script cuyo único trabajo es que alguien
    pueda entrar a aprobar alertas, ese es el peor momento para no explicarse.

    Y **no hay respaldo por `input()` a propósito**: teclear la contraseña con eco es justo lo
    que este script existe para evitar.
    """
    try:
        return getpass.getpass(prompt)
    except (EOFError, OSError):
        for linea in (
            "",
            "Hace falta un terminal interactivo: esta contraseña se teclea sin eco y no se",
            "puede leer de una tubería.",
            "Abre un terminal normal (no el prefijo '!' de Claude Code) y ejecuta:",
            "    docker compose exec -it backend python -m scripts.generar_hash_panel",
            "o, sin docker, desde backend/:  python -m scripts.generar_hash_panel",
        ):
            print(linea, file=sys.stderr)
        raise SystemExit(2) from None


def main() -> int:
    password = _pedir("Contraseña del panel de revisión: ")
    if len(password) < LONGITUD_MINIMA:
        print(f"Demasiado corta: mínimo {LONGITUD_MINIMA} caracteres.", file=sys.stderr)
        return 1
    if password != _pedir("Repítela: "):
        print("No coinciden.", file=sys.stderr)
        return 1

    print()
    print("Añade esta línea a tu .env (y NUNCA la del .env al repositorio):")
    print()
    print(f"PANEL_PASSWORD_HASH={generar_hash(password)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
