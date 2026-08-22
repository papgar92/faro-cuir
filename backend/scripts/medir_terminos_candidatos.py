"""¿Aportan algo los términos candidatos? Se mide sobre el corpus YA ARCHIVADO.

Se lanza **como módulo y desde `backend/`**, igual que sus hermanos::

    docker compose exec -T worker python -m scripts.medir_terminos_candidatos 1500

Por ruta no funciona: ejecutar `python scripts/x.py` pone `scripts/` en `sys.path` en vez de la
raíz del paquete, y `app` deja de encontrarse.

Ni una petición de red: los 66.660 cuerpos están en disco, y el `jurista-lgtbi` insistió —con
razón— en que ningún término se añada al vocabulario sin contar antes qué pasa con él y sin él.

## Dos decisiones de método que costaron dos mediciones malas

1. **Solo disposiciones, nunca el corpus entero.** El 61 % son `BOE-B-*`: licitaciones, edictos y
   nombramientos, que no son normativa. Una muestra aleatoria del corpus completo es un 61 % de
   documentos donde un término jurídico **no podría aparecer nunca**, y eso arrastra cualquier
   frecuencia hacia cero por dilución, no por falta de señal. La primera pasada dio cero en todo
   justamente por esto.

2. **Controles positivos obligatorios.** Una medición que devuelve cero en todas las filas puede
   significar «estos términos no aportan» o «el instrumento está roto», y las dos se ven igual.
   Los controles son términos que TIENEN que aparecer; si dan cero, lo que falla es el script y
   ninguna conclusión sobre los candidatos vale nada.

## Cómo leer la salida

- `apariciones`: en cuántos documentos de la muestra sale el término.
- `RESCATARIA`: en cuántos sale **y además el documento no tiene ya ningún término DIRECTO**. Esta
  es la columna que decide: es lo que el término aportaría de verdad, porque lo que ya entra por
  otro directo no lo aporta él.

Un candidato con muchas apariciones y `RESCATARIA` bajo es un término que no añade cobertura y sí
añade ruido al recuento de directos, que es lo que calibra `UMBRAL_DIRECTOS_RELEVANTE`.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models.norma import EstadoPrefiltro, Norma
from app.pipeline.prefiltro import _VOCABULARIO, Categoria, _contiene, _normalizar
from app.services.cuerpo import CuerpoIlegible, leer_cuerpo

# Los controles van PRIMERO para que se vean antes que nada al leer la tabla.
CONTROLES = {
    "articulo": "CONTROL — sale en casi cualquier disposición",
    "resolucion": "CONTROL — frecuentísimo en el BOE",
    "identidad de genero": "CONTROL — término DIRECTO que ya está en el vocabulario",
}

CANDIDATOS = {
    "gays": "el plural que usan los títulos de las leyes de la propia watchlist; `gais` no lo pilla",
    "gay": "OJO: el jurista avisó del falso positivo «ley de Gay-Lussac» en temarios de física",
    "sexo registral": "M-4 · criterio de acceso definido por el registro",
    "sexo al nacer": "M-4",
    "sexo asignado al nacer": "M-4",
    "sexo de nacimiento": "M-4",
    "mencion registral relativa al sexo": "M-4 · forma literal de la Ley 3/2007",
    "mismo sexo": "fórmula del Código Civil y de la Ley 13/2005",
    "doble maternidad": "filiación de familias lesbianas",
    "cisgenero": "",
    "mujeres trans": "",
    "hombres trans": "",
    "alumnado trans": "vector educativo",
    "serofobia": "",
}


def main(argv: list[str]) -> int:
    n_muestra = int(argv[1]) if len(argv) > 1 else 1500
    ajustes = get_settings()
    root = Path(ajustes.almacen_root)
    directos = {t for t, c in _VOCABULARIO.items() if c is Categoria.DIRECTO}

    with SessionLocal() as sesion:
        ids = [
            fila[0]
            for fila in sesion.execute(
                select(Norma.id).where(
                    Norma.prefiltro_estado == EstadoPrefiltro.DESCARTADA,
                    Norma.documento_texto_id.is_not(None),
                    # Ver el docstring: los anuncios diluyen sin aportar.
                    ~Norma.identificador_oficial.like("BOE-B-%"),
                )
            ).all()
        ]
        random.seed(42)
        muestra = random.sample(ids, min(n_muestra, len(ids)))
        print(f"disposiciones descartadas: {len(ids):,} · muestra: {len(muestra):,}")

        todos = {**CONTROLES, **CANDIDATOS}
        apariciones = dict.fromkeys(todos, 0)
        rescataria = dict.fromkeys(todos, 0)
        leidas = 0

        for norma_id in muestra:
            norma = sesion.get(Norma, norma_id)
            if norma is None:
                continue
            try:
                cuerpo = leer_cuerpo(norma, almacen_root=root)
            except CuerpoIlegible:
                continue
            if cuerpo is None:
                continue
            leidas += 1
            texto = _normalizar(cuerpo.texto)
            ya_entra = any(_contiene(texto, termino) for termino in directos)
            for termino in todos:
                if _contiene(texto, _normalizar(termino)):
                    apariciones[termino] += 1
                    if not ya_entra:
                        rescataria[termino] += 1

    print(f"leídas de verdad: {leidas:,}\n")
    print(f"{'término':36} {'apariciones':>11} {'RESCATARÍA':>11}  nota")
    print("-" * 100)
    for termino, nota in todos.items():
        print(f"{termino:36} {apariciones[termino]:>11} {rescataria[termino]:>11}  {nota}")

    if all(apariciones[c] == 0 for c in CONTROLES):
        print(
            "\n*** LOS CONTROLES DAN CERO: el instrumento está roto y ninguna fila de arriba "
            "significa nada. No saques conclusiones de esta ejecución. ***"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
