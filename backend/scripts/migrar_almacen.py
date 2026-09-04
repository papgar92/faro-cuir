"""Sube el archivo de la 6.5 del disco local al almacén de objetos. ADR 0032.

    docker compose exec -T worker python -m scripts.migrar_almacen --solo-verificar
    docker compose exec -T worker python -m scripts.migrar_almacen

**Verifica antes de subir, y esa es la mitad del valor de este script.** Cada fichero del
almacén se llama como su sha256, así que recalcularlo y compararlo con el nombre comprueba de
paso la propiedad entera de la sección 6.5: que el archivo pueda demostrar qué decía cada
documento el día que se publicó. Un fichero cuyo contenido ya no case con su nombre **no se
sube**, se enumera y se para: copiarlo propagaría a la nube un archivo que ya no prueba nada.

Por eso existe `--solo-verificar`, que es lo primero que conviene lanzar: recorre el árbol, dice
si el archivo está íntegro y no toca la red.

**Es reanudable e idempotente.** Pregunta primero qué claves hay ya en el bucket y se salta esas,
así que una subida interrumpida se retoma sola. Y como la clave *es* el sha256 del contenido,
volver a subir un objeto escribe exactamente los mismos bytes.

**No toca la base de datos.** `documento.ruta_almacen` guarda la misma cadena en los dos
destinos (ADR 0032), así que migrar el almacén no reescribe ni una fila: cuando esto acabe, se
rellenan las cuatro variables `ALMACEN_S3_*` y el sistema lee del bucket.
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

from app.config import get_settings
from app.security import hashing
from app.services import almacen_remoto


def _relativa(fichero: Path, raiz: Path) -> str:
    return str(PurePosixPath(*fichero.relative_to(raiz).parts))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts.migrar_almacen")
    parser.add_argument(
        "--solo-verificar",
        action="store_true",
        help="Comprueba que cada fichero case con su sha256, y para ahí. No sale a la red.",
    )
    parser.add_argument(
        "--limite",
        type=int,
        metavar="N",
        help="Sube como mucho N ficheros y para. Lo que quede se retoma en la pasada siguiente.",
    )
    parser.add_argument(
        "--hilos",
        type=int,
        default=16,
        metavar="N",
        help=(
            "Subidas en paralelo (por defecto 16). El limite es la latencia de cada PUT, no la "
            "CPU: de uno en uno, 84.000 objetos son horas. Bajalo si el proveedor se queja."
        ),
    )
    args = parser.parse_args(argv)

    raiz = get_settings().almacen_root
    if not raiz.is_dir():
        print(f"No existe el almacén local {raiz}", file=sys.stderr)
        return 2

    # **Se recorre por estructura, no por extensión.** `relative_storage_path` produce siempre
    # tres segmentos (`ab/cd/<sha256>.ext`), así que el glob de dos niveles *es* la definición de
    # «documento archivado». Todo lo demás que haya bajo la raíz —y hay: las marcas `.hechos` que
    # dejan los backfill para poder reanudarse, sus logs y algún json— es estado operativo del
    # worker, no archivo, y **no sube al bucket**: allí solo va lo que la 6.5 promete conservar.
    # La primera versión de esto barría con `rglob("*")` y filtraba por extensión, y lo que hizo
    # fue reventar contra la primera marca de backfill.
    ficheros = sorted(f for f in raiz.glob("*/*/*") if f.is_file() and f.suffix != ".tmp")
    # El conjunto se construye UNA vez. Escrito como `if f not in set(ficheros)` dentro de la
    # generadora, Python lo rehace por cada fichero: 84.165 conjuntos de 84.165 elementos, y el
    # script se quedaba colgado antes de tocar la red. Costó dos ejecuciones darse cuenta porque
    # el sintoma era "tarda mucho", que en algo que recorre 1,6 GB no llama la atencion.
    conocidos = set(ficheros)
    ajenos = sorted(
        _relativa(f, raiz) for f in raiz.rglob("*") if f.is_file() and f not in conocidos
    )
    print(f"{len(ficheros)} documentos archivados en {raiz}")
    if ajenos:
        print(f"{len(ajenos)} ficheros ajenos al archivo, que NO se suben: {', '.join(ajenos)}")

    ya_estan: set[str] = set()
    if not args.solo_verificar:
        if not almacen_remoto.configurado():
            print(
                "ALMACEN_S3_BUCKET no está configurado. Rellena las cuatro variables "
                "ALMACEN_S3_* (ver .env.example) o lanza con --solo-verificar.",
                file=sys.stderr,
            )
            return 2
        ya_estan = almacen_remoto.listar_claves()
        print(f"{len(ya_estan)} ya estaban en el bucket; esas se saltan.")

    pendientes = ficheros
    if not args.solo_verificar:
        pendientes = [f for f in ficheros if _relativa(f, raiz) not in ya_estan]
        if args.limite is not None:
            pendientes = pendientes[: args.limite]
            print(f"--limite: solo {len(pendientes)} en esta pasada.")

    def _uno(fichero: Path) -> str:
        """Verifica un fichero y, si procede, lo sube. Devuelve qué le pasó.

        Cada llamada es independiente —lee su fichero, calcula su hash y sube su objeto— así que
        el pool no comparte nada mutable. El cliente de boto3 sí se comparte, y es seguro
        hacerlo: lo que su documentación desaconseja es *crearlo* desde varios hilos, y de eso
        se ocupa el cerrojo de `almacen_remoto.cliente`.
        """
        contenido = fichero.read_bytes()
        digest = hashing.sha256_hex(contenido)
        ruta = _relativa(fichero, raiz)

        # La comprobación que hace de esto algo más que una copia: el nombre promete un sha256
        # y el contenido tiene que cumplirlo. Si no, el archivo dejó de poder afirmar nada
        # sobre ese documento y hay que mirarlo a mano antes de propagarlo.
        #
        # `UnsafeStoragePath` se captura y se cuenta como corrupto en vez de dejarse subir: un
        # fichero con la forma del archivo pero una extensión que el proyecto nunca escribe es
        # justo lo que hay que enseñar, no lo que hay que propagar por una excepción sin capturar.
        try:
            esperada = hashing.relative_storage_path(digest, fichero.suffix)
        except hashing.UnsafeStoragePath:
            esperada = None
        if ruta != esperada:
            return f"corrupto:{ruta}"

        if args.solo_verificar:
            return "verificado"

        almacen_remoto.escribir(ruta, contenido)
        return "subido"

    corruptos: list[str] = []
    subidos = 0
    saltados = len(ficheros) - len(pendientes)
    # En paralelo porque el cuello de botella es la latencia de cada PUT, no la CPU ni el disco:
    # de uno en uno, 84.000 objetos son horas de esperar respuestas. Los hilos van sobrados para
    # esto (el trabajo es E/S y suelta el GIL) y no hacen falta procesos.
    with ThreadPoolExecutor(max_workers=args.hilos) as pool:
        for hechos, resultado in enumerate(pool.map(_uno, pendientes), start=1):
            if resultado.startswith("corrupto:"):
                corruptos.append(resultado.split(":", 1)[1])
            elif resultado == "subido":
                subidos += 1
            if hechos % 2000 == 0:
                print(f"  {hechos}/{len(pendientes)}  (subidos {subidos})", flush=True)

    print(
        f"\nverificados: {len(pendientes)}  subidos: {subidos}  ya estaban o saltados: {saltados}"
    )
    if corruptos:
        # Salida distinta de cero y la lista entera: un archivo que no cumple su propia huella
        # es el peor hallazgo posible en este proyecto y no puede quedar en una línea de log.
        print(f"\n{len(corruptos)} FICHEROS QUE NO CASAN CON SU sha256 (no se han subido):")
        for ruta in corruptos:
            print(f"  {ruta}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
