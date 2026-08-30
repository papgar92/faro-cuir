"""Eje 2 del prefiltro: normas objetivo cuya modificación dispara el filtro. CLAUDE.md 7.3.

Módulo **puro**: no toca la base de datos ni la red. Solo lee un fichero versionado del repo.

Formato JSON leído con la biblioteca estándar: CLAUDE.md sección 3 prohíbe dependencias nuevas
para la watchlist. JSON no admite comentarios, así que cada entrada lleva un campo `nota` — que
además es mejor que un comentario, porque la justificación viaja *con* el dato y se puede
validar y mostrar. (El fichero se llamó `.yaml` un rato, conteniendo JSON; se renombró porque
una extensión que miente sobre su contenido es peor que cualquiera de los dos formatos.)

**El identificador se valida antes de cruzarlo y nunca se usa para construir una URL**
(CLAUDE.md 6.10): lo que sale de un documento externo es dato, jamás una instrucción.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# Identificador de norma tal como lo publica el BOE: BOE-A-2023-5366.
#
# La letra del medio admite **minúscula**, y no es una relajación gratuita: al auditar las 17
# CCAA (2026-08-08) apareció que el BOE también indexa documentos de boletines autonómicos con
# identificadores del tipo `DOG-g-2015-90667` (Diario Oficial de Galicia) o `BON-n-2017-90393`
# (Boletín Oficial de Navarra), con la letra central en minúscula. Hoy la watchlist solo usa
# `BOE-A`, pero rechazar esos formatos significaría que el día que se ingieran boletines
# autonómicos el eje dejaría de cruzar **en silencio** — que es el modo de fallo que este
# módulo existe para evitar.
#
# **Anclado por los dos extremos**: sin el ancla final, "BOE-A-2023-5366/../../etc" pasa la
# validación, y aunque hoy ese valor no se use para construir ninguna ruta, la garantía de 6.10
# tiene que estar en el validador y no en la buena costumbre de quien lo consuma.
PATRON_IDENTIFICADOR = re.compile(r"^[A-Z]{2,6}-[A-Za-z]-\d{4}-\d{1,7}$")

# Rutas donde buscar, en orden. Dentro de docker el repo no está montado entero (solo
# `backend/`), así que `config/` se monta aparte en `/config`; fuera de docker se resuelve
# relativo al repositorio. Se puede forzar con WATCHLIST_PATH.
_RUTAS = (
    Path("/config/watchlist.json"),
    Path(__file__).resolve().parents[3] / "config" / "watchlist.json",
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
    # "estatal" o el código ISO 3166-2:ES de la comunidad ("MD", "CT"...). Permite comprobar la
    # cobertura por comunidad, que es lo que convierte esta lista en algo auditable: sin él, que
    # falte la ley de una CCAA entera no se distingue de que esa CCAA no tenga ley.
    ambito: str = ""
    # --- Qué clase de norma es, y esto SÍ lo mira el clasificador (ADR 0030) --------------------
    # `lgtbi`: norma protectora, toda ella sobre derechos del colectivo. `vehiculo`: norma de
    # materia ajena donde el derecho vive en dos o tres preceptos —la Ley del SNS, el Registro
    # Civil, la LOE—.
    #
    # **La distinción existe porque R-SUP-001 asume que todo lo vigilado es protector** y afirma
    # «retroceso» severidad 4 cuando algo suprime un precepto de una norma vigilada. Sobre una
    # norma-vehículo eso es falso: suprimir el art. 33 de la Ley 16/2003 (formación sanitaria
    # especializada) no es un retroceso LGTBI. Es el error del ADR 0023 un nivel más arriba —allí
    # la supresión y la norma vigilada coexistían en el DOCUMENTO sin tener que ver, aquí
    # coexistirían DENTRO de la norma vigilada—.
    #
    # Vacío = `lgtbi`, porque las 27 entradas anteriores a este campo lo son todas. Que el valor
    # por defecto sea el protector es deliberado: equivocarse hacia `vehiculo` apagaría el signo
    # de una norma que sí lo merece, y eso se nota menos que lo contrario.
    especificidad: str = "lgtbi"
    # --- Solo para la LÍNEA BASE del mapa; nada del pipeline los mira ---------------------------
    # `tipo`: "trans" (ley específica de identidad/expresión de género) o "lgtbi" (ley LGTBI
    # integral). Vacío en las estatales, que no se pintan en el mapa.
    tipo: str = ""
    # ¿Sigue en vigor? **`False` no quiere decir «dejar de vigilarla»**: una norma derogada sigue
    # apareciendo en las referencias de las que la citan, y perder ese rastro sería perder el
    # histórico. Quiere decir que **no cuenta como marco vigente**. Hoy es una: la Ley 14/2012
    # vasca, derogada por la 4/2024. Sin esta distinción la línea base diría que Euskadi tiene una
    # ley que ya no existe.
    vigente: bool = True


@dataclass(frozen=True)
class Watchlist:
    version: str
    normas: tuple[NormaVigilada, ...]
    # Comunidades que NO tienen ley autonómica, con el motivo. **Es información, no un hueco.**
    # Sin esto, "Castilla y León no está en la lista" se lee igual que un olvido de la auditoría;
    # con esto se lee como lo que es: verificado, y no hay norma que vigilar.
    sin_ley: dict[str, str] = field(default_factory=dict)

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

    def buscar(self, identificador: str) -> NormaVigilada | None:
        """La entrada completa, o None. Misma validación de formato que `contiene`.

        Existe para poder decir **a qué territorio afecta** una alerta: la norma vigilada que
        toca es lo único que lo sabe (una ley autonómica publicada en el BOE se ingiere por una
        fuente estatal, así que la fuente no distingue). Sin esto, el mapa no puede colorear la
        comunidad de una reforma autonómica aunque el sistema la haya detectado.
        """
        if not self.contiene(identificador):
            return None
        return next(n for n in self.normas if n.identificador == identificador)


def _localizar() -> Path:
    forzada = os.environ.get("WATCHLIST_PATH")
    candidatas = (Path(forzada),) + _RUTAS if forzada else _RUTAS
    for ruta in candidatas:
        if ruta.is_file():
            return ruta
    raise WatchlistNoDisponible(
        f"no se encuentra watchlist.json en: {[str(r) for r in candidatas]}"
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
                ambito=entrada.get("ambito", ""),
                especificidad=entrada.get("especificidad", "lgtbi"),
                tipo=entrada.get("tipo", ""),
                # Ausente = vigente. Lo excepcional es la derogación, y hacerla explícita en el
                # fichero deja la anomalía a la vista de quien lo lee.
                vigente=entrada.get("vigente", True),
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

    return Watchlist(
        version=version,
        normas=tuple(normas),
        sin_ley=datos.get("_sin_ley_autonomica", {}),
    )


@lru_cache(maxsize=1)
def watchlist() -> Watchlist:
    """La watchlist del proyecto, cacheada por proceso.

    Cacheada porque el prefiltro la consulta una vez por norma y son cientos al día; el
    fichero no cambia mientras el proceso vive. En tests, usar `cargar()` directamente.
    """
    return cargar()
