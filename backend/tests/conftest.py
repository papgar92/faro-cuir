"""Configuración común de la suite.

`app.database` crea el engine al importarse, y `app.config` exige `DATABASE_URL`. En CI esa
variable viene del entorno del job; en local, ejecutando `pytest` desde `backend/`, el
fichero `.env` de la raíz del repo no se encuentra y la suite entera fallaba al recolectar,
incluidos los tests que no tocan la base de datos para nada.

Aquí se pone un valor por defecto **solo si no hay ninguno**, así que no pisa la
configuración de CI ni la de nadie. Es una cadena de conexión de relleno: los tests
unitarios no llegan a conectarse con ella (los que necesitan base de datos montan su propio
engine), solo hace que el import funcione.
"""

from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://tests@localhost:5432/farocuir_tests")
