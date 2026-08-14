"""Genera el valor de `PANEL_PASSWORD_HASH` para el panel de revisión (ADR 0017).

    docker compose exec backend python -m scripts.generar_hash_panel

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


def main() -> int:
    password = getpass.getpass("Contraseña del panel de revisión: ")
    if len(password) < LONGITUD_MINIMA:
        print(f"Demasiado corta: mínimo {LONGITUD_MINIMA} caracteres.", file=sys.stderr)
        return 1
    if password != getpass.getpass("Repítela: "):
        print("No coinciden.", file=sys.stderr)
        return 1

    print()
    print("Añade esta línea a tu .env (y NUNCA la del .env al repositorio):")
    print()
    print(f"PANEL_PASSWORD_HASH={generar_hash(password)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
