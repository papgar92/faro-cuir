"""Selecciona candidatos para el gold set y escribe sus borradores. NO los etiqueta.

Ejecutar: `docker compose exec -T backend python -m scripts.preparar_gold_set`

## Qué hace y qué NO hace

Etiquetar es trabajo humano y es el cuello de botella del proyecto (CLAUDE.md 7.8). Lo que se
puede automatizar sin contaminarlo es todo lo demás: **elegir qué documentos merece la pena
etiquetar y dejar rellenado lo que es un hecho** —identificador, fecha, título, órgano, el
`sha256` del cuerpo archivado y la URL oficial para leerlo—.

Los tres campos de juicio (`prefiltro_esperado`, `ejes_esperados`, `notas`) se dejan **fuera del
borrador**, no a `null`: un borrador incompleto no valida contra `esquema.py`, así que no puede
colarse en `casos/` sin que alguien lo haya mirado.

**Y no se dice qué opina el sistema de cada documento.** Ni los términos que encontró el
prefiltro, ni su estado, ni si disparó algún eje. Es la misma disciplina anti-anclaje que el
fichero de `jurista-lgtbi` impone a sus informes: si quien etiqueta lee primero el veredicto,
deja de juzgar y pasa a confirmar, y entonces el gold set mide si el sistema se parece a sí
mismo. Por el mismo motivo **esto no etiqueta**: un corpus etiquetado por el mismo modelo que
escribe el pipeline no mide nada.

## Por qué el muestreo es estratificado y no aleatorio a secas

Un muestreo aleatorio sobre 82.000 normas devolvería casi solo negativos —el prefiltro descarta
el 99 %— y mediría precisión con mucho gasto humano y recall con ninguno.

Pero elegir solo entre lo que el prefiltro dejó pasar es peor: **los falsos negativos viven, por
definición, entre las descartadas**. Un gold set construido solo con lo que el sistema ya señaló
no puede encontrar nunca lo que se le escapa, que es justamente el fallo que este proyecto llama
invisible (7.1).

Así que se muestrea de los dos lados, con la semilla fija para que la selección sea reproducible,
y **el estrato de cada caso se anota**: cualquier tasa que se calcule después tiene que decir
sobre qué base se calculó.

## Qué se prioriza hoy, y por qué

Medido sobre los 32 casos existentes el 2026-08-30:

- **BOE 24, DOGC 8, BOA 0, BOCYL 0.** Las dos fuentes integradas esta semana no tienen ni un
  caso, así que el gold set **no puede medirlas en absoluto**.
- **Un solo caso con `clasificacion_esperada`**, cuando el catálogo de reglas ya tiene cinco
  familias. La etapa 3 es hoy inmedible.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from sqlalchemy import func, select

from app.config import get_settings
from app.database import SessionLocal
from app.models.documento import Documento
from app.models.fuente import Fuente, TipoFuente
from app.models.norma import EstadoPrefiltro, Norma
from app.pipeline.texto import texto_plano
from app.security import xml_safe
from app.security.xml_safe import XmlSafeError

BORRADORES = Path(__file__).resolve().parent.parent / "tests" / "gold_set" / "borradores"
CASOS = Path(__file__).resolve().parent.parent / "tests" / "gold_set" / "casos"

# Fija y escrita, no pasada por argumento: la selección tiene que poder repetirse dentro de seis
# meses y dar exactamente los mismos documentos.
SEMILLA = 20260830

# De dónde se saca cada estrato. `senalada` mide precisión —¿acierta lo que el sistema marca?—
# y `descartada` mide recall, que es la mitad que no se puede medir de ninguna otra forma.
ESTRATOS = {
    "senalada": (EstadoPrefiltro.SOSPECHA, EstadoPrefiltro.RELEVANTE),
    "descartada": (EstadoPrefiltro.DESCARTADA,),
}

# La URL oficial para leer el documento. Se compone solo para el BOE, que es el único de las
# cuatro fuentes cuyo identificador basta para localizarlo; en las demás se deja la que archivó
# la ingesta.
_URL_BOE = "https://www.boe.es/diario_boe/txt.php?id={}"


def _url_oficial(norma: Norma) -> str:
    if norma.identificador_oficial.startswith("BOE-A-"):
        return _URL_BOE.format(norma.identificador_oficial)
    return norma.url_texto or ""


def _ya_etiquetados() -> set[str]:
    return {
        json.loads(f.read_text(encoding="utf-8"))["identificador_oficial"]
        for f in CASOS.glob("*.json")
    }


def _ya_propuestos() -> set[str]:
    """Borradores que ya existen, para no volver a proponerlos.

    **La semilla fija hace reproducible el barajado, no la muestra**, y la diferencia se vio el
    2026-08-30: entre dos ejecuciones el backfill del BOA siguió ingiriendo, así que la población
    de partida creció y el mismo `random.Random` eligió otros documentos. Resultado: 16 borradores
    del BOA donde debían ser 8.

    No es dañino —más cobertura de una fuente que tenía cero— pero **la reproducibilidad hay que
    enunciarla como lo que es**: repetir la selección exige el mismo corpus, no solo la misma
    semilla. Saltando lo ya propuesto, reejecutar completa en vez de duplicar.
    """
    return {
        json.loads(f.read_text(encoding="utf-8"))["identificador_oficial"]
        for f in BORRADORES.glob("*.json")
    }


def _propuestos_en(prefijo: str, estrato: str) -> int:
    """Cuántos borradores hay ya de esta fuente y este estrato. El estrato viaja en el borrador."""
    total = 0
    for fichero in BORRADORES.glob(f"{prefijo.lower()}-*.json"):
        datos = json.loads(fichero.read_text(encoding="utf-8"))
        if datos.get("_estrato") == estrato:
            total += 1
    return total


def _muestra(session, prefijo: str, estados, cantidad: int, excluir: set[str]):  # type: ignore[no-untyped-def]
    """Documentos de una fuente y un estrato, elegidos con semilla fija.

    Se ordena por `id` antes de barajar para que el conjunto de partida no dependa del orden en
    que la base decida devolver las filas: sin eso, la «semilla fija» no garantizaría nada.
    """
    consulta = (
        select(Norma, Documento)
        .join(Documento, Documento.id == Norma.documento_id)
        .where(
            Norma.identificador_oficial.like(f"{prefijo}%"),
            Norma.prefiltro_estado.in_(estados),
            Norma.documento_texto_id.is_not(None),
        )
        .order_by(Norma.id)
    )
    filas = [
        (n, d) for n, d in session.execute(consulta).all() if n.identificador_oficial not in excluir
    ]
    generador = random.Random(f"{SEMILLA}:{prefijo}:{'-'.join(sorted(e.value for e in estados))}")
    generador.shuffle(filas)
    return filas[:cantidad]


def _texto_derivado(norma: Norma, almacen_root: Path) -> str | None:
    """El texto tal y como lo lee el pipeline. Lo mismo que mide `_caracteres`."""
    cuerpo = norma.documento_texto
    if cuerpo is None:
        return None
    try:
        return texto_plano(xml_safe.parse((almacen_root / cuerpo.ruta_almacen).read_bytes()))
    except (OSError, XmlSafeError):
        return None


def _cuaderno(session, almacen_root: Path) -> int:  # type: ignore[no-untyped-def]
    """Un cuaderno de lectura por fuente, con el texto ENTERO de cada borrador dentro.

    Existe porque el coste real de etiquetar no es decidir, es **abrir 32 pestañas**. Con el
    cuaderno se lee del tirón, sin salir del editor y sin conexión.

    **Va el texto completo, no un extracto, y eso no es comodidad: es la validez de la medida.**
    Un resumen o unos párrafos escogidos harían imposible detectar un falso negativo —lo que se
    escapa está, por definición, en la parte que nadie mira— y el estrato `descartada` existe
    justamente para encontrarlos (7.1).

    **Y no lleva nada de lo que opina el sistema**: ni estado, ni términos, ni ejes. Misma
    disciplina anti-anclaje que el borrador.

    Se ordena de menor a mayor. Sobre la muestra del 2026-08-30, cinco documentos son el 64 % de
    los 906.641 caracteres: leyendo de corto a largo se etiquetan 27 de 32 con un tercio del
    esfuerzo, y los cinco grandes quedan para su propio rato.
    """
    escritos = 0
    for prefijo in ("BOE", "DOGC", "BOA", "BOCYL"):
        entradas = []
        for fichero in sorted(BORRADORES.glob(f"{prefijo.lower()}-*.json")):
            datos = json.loads(fichero.read_text(encoding="utf-8"))
            norma = session.scalar(
                select(Norma).where(Norma.identificador_oficial == datos["identificador_oficial"])
            )
            if norma is not None:
                entradas.append((datos.get("_caracteres") or 0, datos, norma))
        if not entradas:
            continue
        entradas.sort(key=lambda entrada: entrada[0])

        total = sum(caracteres for caracteres, _, _ in entradas)
        partes = [
            f"# Cuaderno de etiquetado — {prefijo}",
            "",
            f"{len(entradas)} documentos, {total:,} caracteres. De más corto a más largo.",
            "",
            "Tras leer uno **entero**, completa su JSON en `borradores/` con `prefiltro_esperado`,",
            "`ejes_esperados` y `notas`, borra los campos con guion bajo y muévelo a `casos/`.",
            "La guía de cada valor está en `gold_set/esquema.py`; la regla que más importa es",
            "**ante la duda, `sospecha`**.",
            "",
            "---",
            "",
        ]
        for caracteres, datos, norma in entradas:
            texto = _texto_derivado(norma, almacen_root) or "(no se pudo derivar el texto)"
            organo = datos.get("organo_emisor") or "—"
            partes += [
                f"## {datos['identificador_oficial']}",
                "",
                f"**{datos['titulo']}**",
                "",
                f"- Fecha: {datos['fecha_publicacion']} · Órgano: {organo}",
                f"- {caracteres:,} caracteres · Oficial: {datos.get('_leer_en') or '—'}",
                "",
                "```text",
                texto,
                "```",
                "",
                "---",
                "",
            ]
        destino = BORRADORES / f"cuaderno-{prefijo.lower()}.md"
        destino.write_text("\n".join(partes), encoding="utf-8")
        print(f"  {destino.name}: {len(entradas)} documentos, {total:,} caracteres")
        escritos += 1
    return escritos


def _caracteres(norma: Norma, almacen_root: Path) -> int | None:
    """Cuánto texto hay que leer. Es lo que decide si un caso cuesta cinco minutos o cuarenta.

    Se deriva igual que lo hace el pipeline (`texto_plano`), no del tamaño del fichero: el XML
    del BOE trae metadatos que nadie lee, y el DOGC guarda el articulado escapado dentro de un
    atributo. Un tamaño en disco no diría cuánto hay que leer de verdad.
    """
    cuerpo = norma.documento_texto
    if cuerpo is None:
        return None
    try:
        crudo = (almacen_root / cuerpo.ruta_almacen).read_bytes()
        return len(texto_plano(xml_safe.parse(crudo)))
    except (OSError, XmlSafeError):
        # El caso puede etiquetarse igual leyendo la fuente oficial: el campo es una comodidad,
        # no un requisito. Un `null` aquí no invalida nada.
        return None


def _borrador(
    norma: Norma,
    documento: Documento,
    fuente: Fuente,
    estrato: str,
    almacen_root: Path,
) -> dict[str, object]:
    """Solo hechos. Los tres campos de juicio se omiten a propósito (ver la cabecera)."""
    cuerpo = norma.documento_texto
    return {
        "identificador_oficial": norma.identificador_oficial,
        "fuente": "boe" if fuente.tipo == TipoFuente.BOE else "boletin_autonomico",
        "fecha_publicacion": documento.fecha_publicacion.isoformat(),
        "titulo": norma.titulo,
        "organo_emisor": norma.organo_emisor,
        "sha256_cuerpo": cuerpo.sha256 if cuerpo is not None else None,
        "_estrato": estrato,
        "_leer_en": _url_oficial(norma),
        "_caracteres": _caracteres(norma, almacen_root),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--senaladas", type=int, default=4, help="por fuente, del estrato señalada")
    parser.add_argument(
        "--descartadas", type=int, default=4, help="por fuente, del estrato descartada"
    )
    parser.add_argument(
        "--cuaderno",
        action="store_true",
        help="además, un cuaderno de lectura por fuente con el texto entero de cada borrador",
    )
    args = parser.parse_args(argv)

    BORRADORES.mkdir(exist_ok=True)
    etiquetados, propuestos = _ya_etiquetados(), _ya_propuestos()
    ya = etiquetados | propuestos
    print(
        f"Ya etiquetados: {len(etiquetados)} en casos/. "
        f"Ya propuestos: {len(propuestos)} borradores. Ninguno se repite.\n"
    )

    escritos = 0
    almacen_root = get_settings().almacen_root
    with SessionLocal() as session:
        fuentes = {f.id: f for f in session.scalars(select(Fuente))}
        for prefijo in ("BOE", "DOGC", "BOA", "BOCYL"):
            for estrato, estados in ESTRATOS.items():
                objetivo = args.senaladas if estrato == "senalada" else args.descartadas
                # **Se completa HASTA el objetivo, no se suma.** La primera versión saltaba lo ya
                # propuesto y pedía `objetivo` más, así que cada reejecución engordaba la muestra
                # en vez de dejarla igual. Un script de muestreo que no es idempotente convierte
                # «reproducible» en una palabra sin contenido.
                cantidad = max(0, objetivo - _propuestos_en(prefijo, estrato))
                filas = _muestra(session, prefijo, estados, cantidad, ya) if cantidad else []
                total = session.scalar(
                    select(func.count())
                    .select_from(Norma)
                    .where(
                        Norma.identificador_oficial.like(f"{prefijo}%"),
                        Norma.prefiltro_estado.in_(estados),
                    )
                )
                print(f"  {prefijo:6} {estrato:11} {len(filas)} de {total or 0} disponibles")
                for norma, documento in filas:
                    datos = _borrador(
                        norma, documento, fuentes[documento.fuente_id], estrato, almacen_root
                    )
                    destino = BORRADORES / f"{norma.identificador_oficial.lower()}.json"
                    destino.write_text(
                        json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                    )
                    escritos += 1

    if args.cuaderno:
        print("\nCuadernos de lectura:")
        with SessionLocal() as session:
            _cuaderno(session, almacen_root)

    print(f"\n{escritos} borradores en {BORRADORES}.")
    print(
        "\nPara etiquetar uno: leerlo en `_leer_en`, añadir `prefiltro_esperado`,\n"
        "`ejes_esperados` y `notas`, borrar los campos con guion bajo y moverlo a `casos/`.\n"
        "El esquema rechaza el fichero mientras falte cualquiera de los tres."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
