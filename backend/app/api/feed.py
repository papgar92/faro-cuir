"""Canal de difusión **pull**: un feed Atom de las alertas emitidas. CLAUDE.md 6.4, ADR 0010.

Este endpoint es el canal principal de difusión del proyecto, y la razón es de protección de
datos antes que de comodidad: **quien se suscribe con su lector no le dice a nadie quién es**.
No hay lista, no hay fichero de suscriptores, no hay brecha posible y desaparece medio capítulo
de cumplimiento — el correo y los webhooks quedan como vías secundarias y opcionales.

Tres cosas que hacen que eso sea verdad y no una intención:

1. **No se registra quién descarga el feed.** El limitador de peticiones ya funcionaba sin
   persistir IPs (6.4), y desde el 2026-08-14 el log de acceso de uvicorn está apagado por lo
   mismo. Un canal pull que apuntara las IPs de quien lo lee reconstruiría exactamente el
   fichero que existe para no tener, y encima sin consentimiento.
2. **No hay tokens ni claves por suscriptor.** Un feed personalizado es una lista de
   suscriptores con otro nombre: cada URL única identificaría a una persona.
3. **Solo sale lo aprobado**, igual que en `GET /api/alertas` y por el mismo motivo: se lee de
   `alerta`, y esa tabla solo la escribe el gate humano.

## Sobre generar XML aquí

La sección 6.1 obliga a `defusedxml` para **parsear** contenido no confiable, y este módulo no
parsea nada: serializa datos propios que ya han pasado por el pipeline. `ElementTree` como
serializador no tiene superficie de XXE —no hay entrada que resolver— y escapa el contenido de
texto y los atributos, que es la única defensa que hace falta al escribir. Componer el XML a
mano con f-strings sí habría sido un problema: el título de una norma del BOE trae comillas y
ampersands a diario.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator
from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.deteccion import Alerta
from app.models.documento import Documento
from app.schemas.alerta import AlertaPublica
from app.services import alertas as servicio

router = APIRouter(prefix="/api", tags=["feed"])

ATOM = "http://www.w3.org/2005/Atom"
TIPO_CONTENIDO = "application/atom+xml; charset=utf-8"

# Cuántas alertas caben en el feed. Un lector solo necesita lo reciente, y un feed que crece sin
# tope acaba siendo una descarga grande que alguien pide cada quince minutos.
MAXIMO_ENTRADAS = 50

# Dominio del identificador de cada entrada (RFC 4151). **No es una URL y no se resuelve**: es
# un identificador estable y único que el lector usa para saber si ya vio esta alerta. Se usa
# una `tag:` URI justamente porque el proyecto todavía no tiene dominio público, y usar una URL
# provisional convertiría un cambio de hosting en un feed entero marcado como no leído.
DOMINIO_TAG = "farocuir.example,2026"

ETIQUETA_CLASIFICACION = {
    "avance": "Avance",
    "retroceso": "Retroceso",
    "neutro": "Neutro",
    "indeterminado": "Sin signo",
}


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


def _resumen(alerta: AlertaPublica) -> str:
    """El cuerpo de la entrada: qué dice el archivo, con qué regla y cómo comprobarlo.

    Texto plano y no HTML a propósito. Un lector de feeds lo enseña igual, no hay nada que
    maquetar —son citas literales de un boletín— y así no existe la duda de si el contenido de
    un documento externo acaba interpretándose como marcado en el cliente de alguien.
    """
    lineas = [
        f"{ETIQUETA_CLASIFICACION.get(alerta.clasificacion, alerta.clasificacion)} "
        f"· {alerta.norma.identificador_oficial}"
        f" · publicado el {alerta.fecha_publicacion.isoformat()}",
        "",
    ]
    if alerta.normas_vigiladas:
        lineas += [
            "Afecta a: "
            + "; ".join(f"{n.titulo or n.identificador}" for n in alerta.normas_vigiladas),
            "",
        ]
    if alerta.spans:
        lineas.append("Evidencia, recortada del texto archivado:")
        lineas += [
            f"  «{span.fragmento}» (caracteres {span.inicio}–{span.fin})" for span in alerta.spans
        ]
        lineas.append("")
    if alerta.preceptos_con_diff:
        # El diff entero (ADR 0018) no cabe en una entrada de feed —36 preceptos con sus dos
        # redacciones—, así que aquí va lo que orienta y el enlace lleva al detalle. Lo que sí
        # viaja es la lista de vocabulario, porque es lo que dice **por dónde** mirar.
        lineas.append(
            f"El sistema tiene archivada la redacción anterior de {alerta.preceptos_con_diff} "
            "precepto(s) de la norma afectada."
        )
        if alerta.terminos_perdidos:
            lineas.append(
                "Vocabulario que estaba en la redacción anterior de esos preceptos y no está en "
                "la nueva: " + ", ".join(alerta.terminos_perdidos) + "."
            )
            lineas.append(
                "Es una pista de por dónde leer, no una conclusión: un término puede seguir "
                "vigente en otro artículo que la reforma no tocó."
            )
        lineas.append("")
    lineas.append(
        f"Clasificado por la regla {alerta.regla_aplicada or '—'}"
        + (f" del catálogo {alerta.version_reglas}" if alerta.version_reglas else "")
        + "."
    )
    if alerta.texto_archivado:
        # La huella va en el feed, no solo en la web: quien recibe esto por un lector tiene que
        # poder comprobar el archivo sin volver a nuestra página (6.5). Un aviso que hay que
        # creerse porque lo dice quien lo manda no es lo que este proyecto quiere ser.
        lineas += [
            f"Texto archivado el {alerta.texto_archivado.sello_tiempo.isoformat()}, "
            f"sha256 {alerta.texto_archivado.sha256}.",
            f"Fuente oficial: {alerta.texto_archivado.url_original}",
        ]
    lineas.append(
        "Esta alerta la ha revisado y aprobado una persona antes de publicarse. "
        "Faro Cuir publica el cambio y su evidencia; la valoración es de quien la lee."
    )
    return "\n".join(lineas)


def _entrada(padre: Element, alerta: AlertaPublica) -> None:
    entrada = SubElement(padre, "entry")
    SubElement(entrada, "id").text = f"tag:{DOMINIO_TAG}:alerta/{alerta.id}"
    SubElement(entrada, "title").text = (
        f"{ETIQUETA_CLASIFICACION.get(alerta.clasificacion, alerta.clasificacion)}: "
        f"{alerta.norma.titulo}"
    )
    SubElement(entrada, "updated").text = alerta.emitida_en.isoformat()
    SubElement(entrada, "published").text = alerta.emitida_en.isoformat()
    if alerta.norma.url_texto:
        # El enlace lleva a la **fuente oficial** y no a una página nuestra, porque todavía no
        # existe una URL por alerta en el frontend. Es mejor así de todas formas: lo que se
        # quiere es que quien lea esto lo contraste en el BOE.
        SubElement(
            entrada,
            "link",
            {"rel": "alternate", "type": "text/html", "href": alerta.norma.url_texto},
        )
    SubElement(entrada, "content", {"type": "text"}).text = _resumen(alerta)
    categoria = SubElement(entrada, "category", {"term": alerta.clasificacion})
    categoria.set("label", ETIQUETA_CLASIFICACION.get(alerta.clasificacion, alerta.clasificacion))


@router.get(
    "/alertas.xml",
    response_class=Response,
    responses={200: {"content": {TIPO_CONTENIDO: {}}}},
)
def feed_atom(request: Request, session: Session = Depends(get_session)) -> Response:
    """Feed Atom de las alertas emitidas. Sin autenticación, sin token y sin saber quién lee."""
    filas = session.execute(
        servicio.consulta()
        .order_by(Documento.fecha_publicacion.desc(), Alerta.id.desc())
        .limit(MAXIMO_ENTRADAS)
    ).all()
    alertas = [servicio.a_publica(*fila) for fila in filas]

    feed = Element("feed", {"xmlns": ATOM, "xml:lang": "es"})
    SubElement(feed, "id").text = f"tag:{DOMINIO_TAG}:alertas"
    SubElement(feed, "title").text = "Faro Cuir · alertas normativas LGTBI+"
    SubElement(feed, "subtitle").text = (
        "Cambios normativos que afectan a los derechos del colectivo LGTBI+, con el fragmento "
        "exacto del texto archivado y la huella para comprobarlo. Cada alerta la ha aprobado "
        "una persona."
    )
    # `updated` del feed: la alerta más reciente, o ahora si no hay ninguna. Sin esto, un lector
    # no puede saber si merece la pena descargar.
    SubElement(feed, "updated").text = (
        max(a.emitida_en for a in alertas).isoformat()
        if alertas
        else datetime.datetime.now(datetime.UTC).isoformat()
    )
    autor = SubElement(feed, "author")
    SubElement(autor, "name").text = "Faro Cuir"
    # `str(request.url)` y no una URL de configuración: el feed se autodescribe con la dirección
    # por la que de verdad se ha pedido, así que funciona igual en local, tras un proxy o en el
    # día que haya dominio propio, sin una variable más que mantener sincronizada.
    SubElement(feed, "link", {"rel": "self", "type": TIPO_CONTENIDO, "href": str(request.url)})

    for alerta in alertas:
        _entrada(feed, alerta)

    # `encoding="unicode"` devuelve el árbol sin declaración XML y la ponemos nosotros: es la
    # forma de controlar exactamente qué sale por delante sin recortar cadenas.
    cuerpo = '<?xml version="1.0" encoding="utf-8"?>\n' + tostring(feed, encoding="unicode")
    return Response(content=cuerpo.encode("utf-8"), media_type=TIPO_CONTENIDO)
