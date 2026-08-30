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
    args = parser.parse_args(argv)

    BORRADORES.mkdir(exist_ok=True)
    ya = _ya_etiquetados()
    print(f"Ya etiquetados: {len(ya)} casos en casos/. No se vuelven a proponer.\n")

    escritos = 0
    almacen_root = get_settings().almacen_root
    with SessionLocal() as session:
        fuentes = {f.id: f for f in session.scalars(select(Fuente))}
        for prefijo in ("BOE", "DOGC", "BOA", "BOCYL"):
            for estrato, estados in ESTRATOS.items():
                cantidad = args.senaladas if estrato == "senalada" else args.descartadas
                filas = _muestra(session, prefijo, estados, cantidad, ya)
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

    print(f"\n{escritos} borradores en {BORRADORES}.")
    print(
        "\nPara etiquetar uno: leerlo en `_leer_en`, añadir `prefiltro_esperado`,\n"
        "`ejes_esperados` y `notas`, borrar los campos con guion bajo y moverlo a `casos/`.\n"
        "El esquema rechaza el fichero mientras falte cualquiera de los tres."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
