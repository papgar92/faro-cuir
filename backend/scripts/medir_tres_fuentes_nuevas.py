"""Qué ha dado el BOCM, el BOPV y el BON: el recuento, y si el cero es de verdad.

Un recuento a secas («780 normas, 0 detecciones») no distingue las dos cosas que hay que
distinguir, y son opuestas:

- **Cero honesto:** el pipeline leyó las 780, encontró las modificaciones que había, y ninguna
  tocaba una norma vigilada. Es el resultado que el ADR 0027 predice —solo el 7 % de las
  disposiciones modifican algo, y ampliar la watchlist rinde ~5 casos al año— y publicarlo es
  obligatorio.
- **Cero ciego:** el eje referencial no funciona sobre estos formatos, así que habría dado cero
  aunque hubiera pasado algo. Eso no es un resultado, es una avería, y encima muda.

Lo que separa una cosa de la otra es **cuántas modificaciones ve el pipeline en total**, tocando
lo que sea. Ese número no está en ninguna columna (el prefiltro solo apunta el eje cuando la
norma citada está en la watchlist), así que aquí se recalcula leyendo los cuerpos archivados.

No sale a la red, no llama al LLM y no escribe nada: solo lee el archivo y cuenta.

    docker compose -f docker-compose.yml -f docker-compose.local.yml exec -T worker \
        python -m scripts.medir_tres_fuentes_nuevas
"""

from __future__ import annotations

import collections
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models.documento import Documento
from app.models.fuente import Fuente
from app.models.norma import Norma
from app.pipeline import watchlist as modulo_watchlist
from app.services.cuerpo import CuerpoIlegible, leer_cuerpo

COMUNIDADES: tuple[str, ...] = ("MD", "NC", "PV")

# Una cita en forma larga de CUALQUIER norma: «Ley 8/2017, de 19 de junio», «Decreto Foral
# 12/2024, de 3 de abril». Es a propósito **más laxa** que `pipeline/citas.py`, que exige además
# que la norma esté en la watchlist: aquí no se decide nada, se mide si el texto trae material
# citable. Un falso positivo de más solo hace la conclusión más conservadora.
CITA_LARGA = re.compile(
    r"\b(?:ley|ley\s+foral|ley\s+org[áa]nica|decreto|decreto\s+foral|decreto\s+legislativo|"
    r"orden|orden\s+foral|resoluci[óo]n)\s+\d+/\d{4}",
    re.IGNORECASE,
)

# El verbo modificativo, sin exigir que gobierne a nadie. Misma lógica: mide presencia de
# material, no produce veredictos.
VERBO_MODIFICATIVO = re.compile(
    r"\bse\s+(?:modifica|modifican|deroga|derogan|a[ñn]ade|a[ñn]aden|suprime|suprimen|"
    r"sustituye|sustituyen)\b",
    re.IGNORECASE,
)


def main() -> int:
    ajustes = get_settings()
    lista = modulo_watchlist.watchlist()
    session: Session
    with SessionLocal() as session:
        fuentes = session.scalars(select(Fuente).where(Fuente.ccaa_codigo.in_(COMUNIDADES))).all()

        print(f"Watchlist {lista.version}: {len(lista.normas)} normas vigiladas en total.")
        print()

        total = collections.Counter[str]()
        for fuente in sorted(fuentes, key=lambda f: f.nombre):
            normas = session.scalars(
                select(Norma)
                .join(Documento, Norma.documento_id == Documento.id)
                .where(Documento.fuente_id == fuente.id)
            ).all()

            cuenta = collections.Counter[str]()
            for norma in normas:
                cuenta["normas"] += 1
                try:
                    cuerpo = leer_cuerpo(norma, almacen_root=ajustes.almacen_root, lista=lista)
                except CuerpoIlegible:
                    cuenta["ilegibles"] += 1
                    continue
                if cuerpo is None:
                    cuenta["sin_cuerpo"] += 1
                    continue
                cuenta["leidas"] += 1
                cuenta[f"nivel_{cuerpo.derivacion}"] += 1
                if CITA_LARGA.search(cuerpo.texto):
                    cuenta["citan_alguna_norma"] += 1
                if VERBO_MODIFICATIVO.search(cuerpo.texto):
                    cuenta["con_verbo_modificativo"] += 1
                if cuerpo.referencias:
                    cuenta["citan_una_vigilada"] += 1
                if any(r.es_modificativa for r in cuerpo.referencias):
                    cuenta["modifican_una_vigilada"] += 1

            _imprimir(fuente.nombre, cuenta)
            total.update(cuenta)

        print()
        _imprimir("TOTAL de las tres", total)
        print()
        _veredicto(total)
    return 0


def _imprimir(titulo: str, c: collections.Counter[str]) -> None:
    normas = c["normas"] or 1
    print(f"{titulo}")
    print(f"  normas ingeridas ............. {c['normas']}")
    print(
        f"  cuerpo leído ................. {c['leidas']}   (ilegibles: {c['ilegibles']}, "
        f"sin cuerpo: {c['sin_cuerpo']})"
    )
    niveles = {k[6:]: v for k, v in c.items() if k.startswith("nivel_")}
    if niveles:
        print(f"  por nivel de derivación ...... {niveles}")
    print(
        f"  citan alguna norma ........... {c['citan_alguna_norma']}"
        f"   ({100 * c['citan_alguna_norma'] / normas:.1f} %)"
    )
    print(
        f"  con verbo modificativo ....... {c['con_verbo_modificativo']}"
        f"   ({100 * c['con_verbo_modificativo'] / normas:.1f} %)"
    )
    print(f"  citan una VIGILADA ........... {c['citan_una_vigilada']}")
    print(f"  MODIFICAN una vigilada ....... {c['modifican_una_vigilada']}")


def _veredicto(c: collections.Counter[str]) -> None:
    """Lo único que este script decide: si el cero se puede publicar o hay que ir a mirar."""
    if c["leidas"] == 0:
        print("VEREDICTO: no se ha podido leer ni un cuerpo. El recuento no vale nada.")
        return
    if c["con_verbo_modificativo"] == 0 and c["citan_alguna_norma"] == 0:
        print(
            "VEREDICTO: CERO CIEGO. Ni una sola de las normas leídas cita a otra ni contiene un\n"
            "verbo modificativo. Sobre un corpus de este tamaño eso no es plausible: apunta a que\n"
            "la derivación de texto de estas fuentes no está entregando el articulado. HAY QUE\n"
            "MIRARLO antes de publicar ninguna cifra de cobertura."
        )
        return
    print(
        "VEREDICTO: CERO HONESTO. El pipeline lee estos cuerpos y encuentra en ellos citas y\n"
        "verbos modificativos; lo que no encuentra es una modificación de una norma vigilada.\n"
        "Es el resultado que predice el ADR 0027 y se publica tal cual."
    )


if __name__ == "__main__":
    raise SystemExit(main())
