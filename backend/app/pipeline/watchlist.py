"""Eje 2 del prefiltro: normas objetivo cuya modificación dispara el filtro. CLAUDE.md 7.3.

Módulo **puro**: no toca la base de datos ni la red. Solo lee un fichero versionado del repo.

Sobre el formato, que tiene una explicación y no es un descuido: `config/watchlist.yaml` está
escrito en **JSON, que es un subconjunto válido de YAML**, y se parsea con el `json` de la
biblioteca estándar. El nombre lo fija CLAUDE.md sección 4 y la prohibición de dependencias
nuevas para la watchlist la fija la sección 3; escribir un parser propio de YAML en un
proyecto de seguridad sería peor que cualquiera de las dos cosas. Si algún día entra PyYAML,
el fichero sigue siendo válido sin tocarlo.

**El identificador se valida antes de cruzarlo y nunca se usa para construir una URL**
(CLAUDE.md 6.10): lo que sale de un documento externo es dato, jamás una instrucción.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# Identificador de norma tal como lo publica el BOE: BOE-A-2023-5366. Se acepta un prefijo de
# boletín de 2 a 6 letras para dejar sitio a los autonómicos sin abrir la puerta a cualquier
# cosa. **Anclado por los dos extremos**: sin el ancla final, "BOE-A-2023-5366/../../etc" pasa
# la validación, y aunque hoy ese valor no se use para construir ninguna ruta, la garantía de
# 6.10 tiene que estar en el validador y no en la buena costumbre de quien lo consuma.
PATRON_IDENTIFICADOR = re.compile(r"^[A-Z]{2,6}-[A-Z]-\d{4}-\d{1,7}$")

# Rutas donde buscar, en orden. Dentro de docker el repo no está montado entero (solo
# `backend/`), así que `config/` se monta aparte en `/config`; fuera de docker se resuelve
# relativo al repositorio. Se puede forzar con WATCHLIST_PATH.
_RUTAS = (
    Path("/config/watchlist.yaml"),
    Path(__file__).resolve().parents[3] / "config" / "watchlist.yaml",
)


class WatchlistNoDisponible(RuntimeError):
    """No se encuentra o no se puede leer la watchlist.

    Se levanta en vez de devolver una lista vacía **a propósito**. Una watchlist vacía no
    falla: el eje referencial deja de disparar y el sistema sigue funcionando, aparentemente
    bien, habiendo perdido en silencio la única defensa contra la instrucción que modifica un
    derecho sin nombrarlo. Un fallo ruidoso al arrancar es infinitamente preferible.
    """


@dataclass(frozen=True)
class NormaVigilada:
    identificador: str
    titulo: str
    nota: str


@dataclass(frozen=True)
class Watchlist:
    version: str
    normas: tuple[NormaVigilada, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "_indice", {n.identificador for n in self.normas})

    def contiene(self, identificador: str) -> bool:
        """¿Está esta norma vigilada? Compara exacto, sin normalizar ni recortar.

        Un identificador que no encaje en `PATRON_IDENTIFICADOR` devuelve False sin más: no se
        intenta arreglarlo. "Arreglar" un identificador que viene de un documento externo es
        justamente cómo se acaba cruzando algo que no era.
        """
        if not PATRON_IDENTIFICADOR.match(identificador):
            return False
        indice: set[str] = self._indice  # type: ignore[attr-defined]
        return identificador in indice


def _localizar() -> Path:
    forzada = os.environ.get("WATCHLIST_PATH")
    candidatas = (Path(forzada),) + _RUTAS if forzada else _RUTAS
    for ruta in candidatas:
        if ruta.is_file():
            return ruta
    raise WatchlistNoDisponible(
        f"no se encuentra watchlist.yaml en: {[str(r) for r in candidatas]}"
    )


def cargar(ruta: Path | None = None) -> Watchlist:
    """Lee y valida la watchlist. Sin caché, para poder usarla en tests con ficheros propios."""
    destino = ruta if ruta is not None else _localizar()
    try:
        datos = json.loads(destino.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise WatchlistNoDisponible(f"no se puede leer {destino}: {error}") from error

    version = datos.get("version")
    if not isinstance(version, str) or not version:
        raise WatchlistNoDisponible(
            f"{destino}: falta 'version'. Sin ella no se puede saber "
            "qué normas hay que reevaluar cuando la lista cambia."
        )

    normas = []
    for entrada in datos.get("normas", []):
        identificador = entrada.get("identificador", "")
        # Se valida al CARGAR y no al cruzar: un identificador mal escrito en el fichero no
        # rompe nada visible, simplemente no cruza nunca con ninguna norma. El eje referencial
        # parecería funcionar mientras deja pasar exactamente lo que debía detectar.
        if not PATRON_IDENTIFICADOR.match(identificador):
            raise WatchlistNoDisponible(
                f"{destino}: identificador con formato inválido: {identificador!r}. "
                "Un identificador inválido no falla al cruzar, solo deja de detectar."
            )
        normas.append(
            NormaVigilada(
                identificador=identificador,
                titulo=entrada.get("titulo", ""),
                nota=entrada.get("nota", ""),
            )
        )

    if not normas:
        raise WatchlistNoDisponible(
            f"{destino}: la watchlist está vacía; el eje referencial "
            "no detectaría nada y no habría forma de notarlo."
        )

    identificadores = [n.identificador for n in normas]
    if len(set(identificadores)) != len(identificadores):
        raise WatchlistNoDisponible(f"{destino}: hay identificadores repetidos")

    return Watchlist(version=version, normas=tuple(normas))


@lru_cache(maxsize=1)
def watchlist() -> Watchlist:
    """La watchlist del proyecto, cacheada por proceso.

    Cacheada porque el prefiltro la consulta una vez por norma y son cientos al día; el
    fichero no cambia mientras el proceso vive. En tests, usar `cargar()` directamente.
    """
    return cargar()
