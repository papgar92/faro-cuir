"""¿Cuánto tarda de verdad una extracción, y cuánto genera el modelo? Se mide antes de relanzar.

Se lanza **como módulo y desde `backend/`**::

    docker compose exec -T worker python -m scripts.medir_extraccion        # 2 normas
    docker compose exec -T worker python -m scripts.medir_extraccion 5      # 5 normas

## Por qué existe

El 2026-08-28 se descubrió que el extractor llevaba **cinco días quemando tres núcleos y tirando
el 100 % de los resultados**: `llm/ollama.py` no fijaba `num_predict`, así que la generación era
ilimitada y ninguna petición terminaba dentro del timeout. Al arreglarlo hay que **medir antes de
relanzar**, o se repite el mismo error a ciegas — que es exactamente lo que el proyecto lleva
haciendo mal dos veces (ADR 0011 y el error de denominador de `medir_terminos_candidatos`).

## Qué mide, y por qué la primera no cuenta

- **Llamada 1 (fría):** incluye cargar el modelo en RAM (~4,8 GB). Ollama lo descarga tras 5
  minutos de inactividad, así que en una pasada real esto se paga **una vez**, no por norma.
- **Llamadas siguientes (calientes):** el coste por norma de verdad. **Es la cifra con la que hay
  que presupuestar la cola**, no la primera.

Usa el adaptador `llm/ollama.py`, no HTTP directo: la regla 6.9.1 dice que solo ese módulo habla
con Ollama, y un script de medición no es excusa para saltársela — además, medir por otra vía
mediría otra cosa.
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.llm.ollama import ProveedorOllama
from app.llm.provider import PROMPT_SISTEMA, envolver_contenido
from app.models.deteccion import Deteccion
from app.models.norma import EstadoPrefiltro, Norma
from app.pipeline.watchlist import watchlist
from app.services.cuerpo import CuerpoIlegible, leer_cuerpo
from app.services.extraccion import _recortar


def main(argv: list[str]) -> int:
    cuantas = int(argv[1]) if len(argv) > 1 else 2
    ajustes = get_settings()
    root = Path(ajustes.almacen_root)
    lista = watchlist()
    proveedor = ProveedorOllama(
        base_url=ajustes.llm_base_url,
        modelo=ajustes.llm_modelo,
        timeout=ajustes.llm_timeout_segundos,
    )
    print(f"modelo={ajustes.llm_modelo}  timeout={ajustes.llm_timeout_segundos:.0f}s")

    with SessionLocal() as s:
        ya = {f[0] for f in s.execute(select(Deteccion.norma_id)).all()}
        ids = [
            f[0]
            for f in s.execute(
                select(Norma.id)
                .where(
                    Norma.prefiltro_estado.in_(
                        [EstadoPrefiltro.RELEVANTE, EstadoPrefiltro.SOSPECHA]
                    )
                )
                .order_by(Norma.id)
            ).all()
            if f[0] not in ya
        ]
        print(f"cola sin extraer: {len(ids):,}\n")

        tiempos: list[float] = []
        hechas = 0
        for norma_id in ids:
            if hechas >= cuantas:
                break
            norma = s.get(Norma, norma_id)
            if norma is None:
                continue
            try:
                cuerpo = leer_cuerpo(norma, almacen_root=root, lista=lista)
            except CuerpoIlegible:
                continue
            if cuerpo is None:
                continue
            texto, totales = _recortar(cuerpo.texto, identificador=norma.identificador_oficial)

            arranque = time.monotonic()
            try:
                respuesta = proveedor.completar(PROMPT_SISTEMA, envolver_contenido(texto))
                tardo = time.monotonic() - arranque
                estado = f"OK  {len(respuesta):,} caracteres devueltos"
            except Exception as exc:  # noqa: BLE001 - script de medición: el fallo es el dato
                tardo = time.monotonic() - arranque
                estado = f"FALLO {type(exc).__name__}: {str(exc)[:60]}"

            hechas += 1
            tiempos.append(tardo)
            etiqueta = "FRIA (incluye cargar el modelo)" if hechas == 1 else "caliente"
            print(
                f"{hechas}. {norma.identificador_oficial:20} {tardo:7.1f}s  {etiqueta}\n"
                f"   documento {totales:,} car → enviados {len(texto):,} "
                f"({100 * len(texto) / totales:.1f}%)\n"
                f"   {estado}"
            )

    calientes = tiempos[1:]
    print()
    if calientes:
        media = statistics.mean(calientes)
        print(f"COSTE POR NORMA (calientes): {media:.1f}s de media sobre {len(calientes)} medidas")
        print(
            f"Presupuesto de la cola: {len(ids):,} normas × {media:.0f}s = "
            f"{len(ids) * media / 3600:.1f} horas"
        )
    else:
        print("Solo se midió la llamada fría; lanza con 2 o más para tener coste por norma.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
