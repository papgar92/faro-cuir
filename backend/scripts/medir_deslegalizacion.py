"""¿Cuánto dispararía una regla de deslegalización (M-8)? Se mide ANTES de escribirla.

Se lanza **como módulo y desde `backend/`**, igual que sus hermanos::

    docker compose exec -T worker python -m scripts.medir_deslegalizacion

Ni una petición de red: los cuerpos están en disco.

## Qué se está midiendo

M-8 del informe de puntos ciegos del `jurista-lgtbi` (2026-08-23): la **deslegalización**. Una
ley que sustituye una garantía concreta por una remisión al reglamento —«en los términos que
reglamentariamente se determinen»— deja el derecho dependiendo de un reglamento que puede no
llegar nunca. El informe la trajo esbozada como `R-DES-001`, sentido `indeterminado`, con un
aviso que es justo lo que hay que comprobar:

> «se faculta a», «reglamentariamente se determinará» aparecen en casi toda norma con rango de
> ley. Como término suelto serían el nuevo «igualdad de trato».

## DOS POBLACIONES, y esa es la lección de esta medición

La primera versión de este script muestreaba 800 documentos al azar y daba **0** en la columna
que decide. Parecía una respuesta y no lo era: solo **22 normas de 69.388** disparan el eje
referencial, así que en 800 al azar la esperanza de encontrar una es **0,25**. El cero medía el
tamaño de la muestra, no la regla. Es el mismo error de denominador que ya se cometió dos veces
en este repositorio (ADR 0011, y `medir_terminos_candidatos` con su 61 % de anuncios), y por eso
ahora se miden dos poblaciones distintas y se dice cuál contesta a qué:

1. **Censo dirigido** — TODAS las normas donde la regla podría aportar: las que tocan una norma
   vigilada o ya producen veredicto. Son pocas y se recorren enteras, sin muestreo. **Esta es la
   población que contesta si la regla aporta.**
2. **Muestra aleatoria de disposiciones** — la tasa base: cada cuánto aparece la construcción en
   normativa cualquiera. **Contesta si la regla haría ruido**, que es el riesgo que avisó el
   jurista. No contesta lo primero.

## Las columnas

- `remisión`: cláusula de remisión reglamentaria **pegada a un precepto** (misma cláusula,
  criterio de `_clausulas_con`, que es el del ADR 0023).
- `+vigilada`: además el `<analisis>` declara que toca una norma de `config/watchlist.json`.
- `NUEVA`: además, **el catálogo de hoy devuelve `None`**. Única columna que mide recall
  añadido: lo que ya entra por R-MOD-001 no lo aporta esta regla, lo reetiqueta.

## Controles

Si los controles positivos dan cero, el script **se niega a dar resultados** y sale con código 1:
una tabla de ceros no distingue «no dispara» de «está roto».
"""

from __future__ import annotations

import random
import re
import sys
from pathlib import Path

from sqlalchemy import Text, select

from app.config import get_settings
from app.database import SessionLocal
from app.models.deteccion import Deteccion
from app.models.norma import Norma
from app.pipeline.reglas import (
    _PRECEPTO,
    _SUPRESION,
    _clausulas_con,
    _vigiladas,
    clasificar,
)
from app.pipeline.watchlist import Watchlist, watchlist
from app.services.cuerpo import CuerpoIlegible, leer_cuerpo

# El candidato. Se define AQUÍ y no en `pipeline/reglas.py` a propósito: mientras no esté medido
# es una hipótesis, y una hipótesis no vive en el catálogo que produce veredictos.
#
# Se busca la **construcción que difiere** la regulación a una norma futura de rango inferior, no
# la palabra «reglamento»: «el reglamento de la Ley 4/2023» es una cita, no una deslegalización.
_REMISION = re.compile(
    r"\breglamentariamente\s+se\s+(?:determinar|establecer|regular|fijar|desarrollar)"
    r"|\bque\s+(?:se\s+)?(?:determinen?|establezcan?|fijen?|regulen?)\s+reglamentariamente\b"
    r"|\ben\s+la\s+forma\s+que\s+(?:se\s+)?determine\s+reglamentariamente\b"
    r"|\bmediante\s+(?:el\s+)?desarrollo\s+reglamentario\b"
    r"|\bse\s+(?:faculta|habilita|autoriza)\s+al?\s+[^.;:»]{0,60}?\s+para\s+"
    r"(?:dictar|desarrollar|aprobar|establecer)\b",
    re.IGNORECASE,
)


class Recuento:
    """Lo que se cuenta de cada población, para poder imprimirlas con el mismo formato."""

    def __init__(self, nombre: str) -> None:
        self.nombre = nombre
        self.leidas = 0
        self.control_precepto = 0
        self.control_supresion = 0
        self.remision = 0
        self.vigilada = 0
        self.remision_y_vigilada = 0
        self.nuevas = 0
        self.ejemplos: list[tuple[str, str]] = []

    def mide(self, norma: Norma, texto: str, referencias: tuple, lista: Watchlist) -> None:  # type: ignore[type-arg]
        self.leidas += 1
        if _PRECEPTO.search(texto):
            self.control_precepto += 1
        if _SUPRESION.search(texto):
            self.control_supresion += 1

        vigiladas = _vigiladas(referencias, lista)
        if vigiladas:
            self.vigilada += 1

        remision = _clausulas_con(texto, _REMISION, _PRECEPTO)
        if not remision:
            return
        self.remision += 1
        if not vigiladas:
            return
        self.remision_y_vigilada += 1

        if clasificar(texto, referencias=referencias, lista=lista) is None:
            self.nuevas += 1
            if len(self.ejemplos) < 10:
                self.ejemplos.append((norma.identificador_oficial, remision[0].fragmento))

    def imprime(self) -> None:
        print(f"\n=== {self.nombre} · {self.leidas:,} leídas ===")
        print(f"  {'CONTROL cita un precepto':44} {self.control_precepto:>7}")
        print(f"  {'CONTROL construcción de supresión':44} {self.control_supresion:>7}")
        print(f"  {'CONTROL toca una norma vigilada':44} {self.vigilada:>7}")
        print("  " + "-" * 54)
        print(f"  {'remisión pegada a un precepto':44} {self.remision:>7}")
        print(f"  {'  + toca una norma vigilada':44} {self.remision_y_vigilada:>7}")
        print(f"  {'  + el catálogo de hoy calla (NUEVA)':44} {self.nuevas:>7}")


def _recorrer(sesion, ids, root: Path, lista: Watchlist, recuento: Recuento) -> None:  # type: ignore[no-untyped-def]
    for norma_id in ids:
        norma = sesion.get(Norma, norma_id)
        if norma is None:
            continue
        try:
            cuerpo = leer_cuerpo(norma, almacen_root=root, lista=lista)
        except CuerpoIlegible:
            continue
        if cuerpo is None:
            continue
        recuento.mide(norma, cuerpo.texto, cuerpo.referencias, lista)


def main(argv: list[str]) -> int:
    n_muestra = int(argv[1]) if len(argv) > 1 else 1500
    ajustes = get_settings()
    root = Path(ajustes.almacen_root)
    lista = watchlist()

    with SessionLocal() as sesion:
        # Población 1: censo dirigido. Las que ya producen veredicto y las que el eje
        # referencial marcó — o sea, donde la watchlist está en juego. Sin muestreo.
        con_veredicto = {
            fila[0]
            for fila in sesion.execute(
                select(Deteccion.norma_id).where(Deteccion.regla_aplicada.is_not(None))
            ).all()
        }
        referencial = {
            fila[0]
            for fila in sesion.execute(
                select(Norma.id).where(
                    Norma.prefiltro_ejes.is_not(None),
                    Norma.prefiltro_ejes.cast(Text).like("%referencial%"),
                )
            ).all()
        }
        dirigido = sorted(con_veredicto | referencial)

        # Población 2: tasa base sobre disposiciones (los anuncios `BOE-B-*` diluyen).
        todas = [
            fila[0]
            for fila in sesion.execute(
                select(Norma.id).where(
                    Norma.documento_texto_id.is_not(None),
                    ~Norma.identificador_oficial.like("BOE-B-%"),
                )
            ).all()
        ]
        random.seed(42)
        muestra = random.sample(todas, min(n_muestra, len(todas)))

        print(
            f"censo dirigido: {len(dirigido):,} normas "
            f"({len(con_veredicto):,} con veredicto ∪ {len(referencial):,} del eje referencial)"
        )
        print(f"disposiciones con cuerpo: {len(todas):,} · muestra aleatoria: {len(muestra):,}")

        censo = Recuento("CENSO DIRIGIDO — contesta si la regla APORTA")
        base = Recuento("MUESTRA ALEATORIA — contesta si la regla hace RUIDO")
        _recorrer(sesion, dirigido, root, lista, censo)
        _recorrer(sesion, muestra, root, lista, base)

    censo.imprime()
    base.imprime()

    if censo.ejemplos:
        print("\nLo que la regla añadiría a la cola de revisión:")
        for ident, fragmento in censo.ejemplos:
            print(f"\n  {ident}\n    {fragmento[:300]}")

    # El censo dirigido es pequeño y puede legítimamente no traer supresiones; el control que
    # tiene que cumplirse en las dos poblaciones es el precepto, y en el censo además la
    # vigilada, que es como se construyó.
    if base.control_precepto == 0 or base.control_supresion == 0 or censo.vigilada == 0:
        print(
            "\n*** LOS CONTROLES FALLAN: el instrumento está roto y ninguna cifra de arriba "
            "significa nada. No saques conclusiones de esta ejecución. ***"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
