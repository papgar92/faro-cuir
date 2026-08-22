import { useEffect, useState } from "react";

import { obtenerAlerta, type AlertaApi, type CambioPreceptoApi } from "../../api/client";
import { COLOR_CLASSES, type ClassificationMeta } from "../../lib/classification";
import { formatearFecha, formatearSelloTiempo } from "../../lib/formato";
import { nombreTerritorio } from "../../lib/territorio";
import { CambiosPrecepto } from "../CambiosPrecepto/CambiosPrecepto";
import { ClassificationBadge } from "../ClassificationBadge/ClassificationBadge";

/**
 * Una alerta **real**: una detección que pasó el gate humano (regla de oro 4).
 *
 * La tarjeta enseña la evidencia, no solo el veredicto. Es la misma razón por la que la
 * huella de archivo se publica en vez de guardarse (6.5): el proyecto afirma «esta norma
 * suprime esto», y esa afirmación no vale nada si quien la lee tiene que fiarse. Aquí va el
 * fragmento recortado del texto archivado, con sus offsets, la regla que lo clasificó y el
 * enlace a la fuente oficial para contrastarlo.
 *
 * Deliberadamente **no** hay ningún texto de opinión ni adjetivos: el titular es el título
 * oficial de la norma y el cuerpo son citas literales (regla de oro 2).
 */

/**
 * Los cuatro valores de `deteccion.clasificacion`, que no son los tres del mock de diseño.
 * `indeterminado` se pinta en el color de aviso y **no** en el de retroceso: es el umbral de
 * recall alto de 7.6 —el catálogo ha visto algo y no sabe de qué signo— y teñirlo de rojo
 * sería emitir el veredicto del que la regla se abstuvo.
 */
const META: Record<AlertaApi["clasificacion"], ClassificationMeta> = {
  avance: { label: "Avance", glyph: "▲", color: "adv" },
  retroceso: { label: "Retroceso", glyph: "▼", color: "reg" },
  neutro: { label: "Neutro", glyph: "●", color: "neu" },
  indeterminado: { label: "Sin signo", glyph: "?", color: "alr" },
};

interface AlertCardProps {
  alerta: AlertaApi;
}

export function AlertCard({ alerta }: AlertCardProps) {
  // Si una persona fijó el signo, manda el suyo: leyó el texto entero, que es más de lo que
  // puede hacer una regla. Pero **se dice de quién es cada cosa** justo debajo, porque publicar
  // «avance» sin decir que lo decidió alguien sería atribuirle a la regla algo que no dijo.
  const meta = META[alerta.clasificacion_humana ?? alerta.clasificacion];
  const colors = COLOR_CLASSES[meta.color];
  const territorios = alerta.normas_vigiladas.map((n) => nombreTerritorio(n.ambito));

  // El diff se pide **al abrirlo**, no al pintar la lista: el listado no trae las redacciones
  // (serían varios megas por página) y la mayoría de quien lee una lista no abre ninguna.
  const [abierto, setAbierto] = useState(false);
  const [cambios, setCambios] = useState<CambioPreceptoApi[] | null>(null);
  const [fallo, setFallo] = useState(false);

  useEffect(() => {
    if (!abierto || cambios !== null) return;
    const control = new AbortController();
    obtenerAlerta(alerta.id, control.signal)
      .then((detalle) => setCambios(detalle.cambios))
      .catch((error: unknown) => {
        // Una cancelación al cerrar o cambiar de filtro no es un fallo que enseñar.
        if (control.signal.aborted) return;
        setFallo(true);
        console.error(error);
      });
    return () => control.abort();
  }, [abierto, cambios, alerta.id]);

  return (
    <article
      className={`mb-3 max-w-[900px] rounded border border-line ${colors.borderLeft} border-l-4 bg-surface p-4`}
    >
      <div className="flex flex-wrap items-center gap-2.5">
        <ClassificationBadge meta={meta} />
        {territorios.length > 0 && (
          <span className="text-sm font-semibold text-ink">{territorios.join(" · ")}</span>
        )}
        <span className="ml-auto font-mono text-xs text-ink-3">
          {formatearFecha(alerta.fecha_publicacion)}
        </span>
      </div>

      {/* El título va en `font-sans` y no en `font-serif` a propósito, y conviene dejarlo escrito
          porque es de las reglas que se pierden en la siguiente refactorización: la gramática
          tipográfica del proyecto reserva la serif para SU voz, y este titular no es suyo — es el
          título oficial de la norma, o sea la voz del Estado. */}
      <h3 className="mt-2.5 text-base font-semibold leading-snug text-ink">
        {alerta.norma.titulo}
      </h3>

      {/* Quién firma y con qué rango. Los dos campos ya viajaban en la respuesta y no se pintaban
          en ningún sitio, y para una herramienta cuyo manifiesto dice que un retroceso llega en
          «una instrucción de dos páginas que no firma nadie con nombre conocido», el emisor es
          media noticia: no es lo mismo una ley de un parlamento que una orden de una consejería.
          Un campo vacío se dice, no se deja como hueco: `null` aquí significa que el extractor
          todavía no lo rellena, y callarlo lo haría parecer que la norma no tiene emisor. */}
      <p className="mt-1 font-mono text-[11px] text-ink-3">
        {alerta.norma.organo_emisor ?? "emisor sin extraer todavía"}
      </p>

      {alerta.clasificacion_humana && (
        <p className="mt-1.5 text-xs leading-relaxed text-ink-2">
          Signo fijado por la persona que revisó. La regla{" "}
          <span className="font-mono text-[11px]">{alerta.regla_aplicada}</span> se quedó en{" "}
          «{alerta.clasificacion}»: no puede afirmar el sentido de una derogación sin leer qué
          ocupa el lugar de lo derogado.
        </p>
      )}

      {alerta.spans.length > 0 && (
        <div className="mt-3 rounded border border-line-2 bg-inset p-3">
          <p className="font-mono text-[13px] leading-relaxed text-ink">
            «{alerta.spans[0].fragmento}»
          </p>
          <p className="mt-1.5 font-mono text-[10.5px] text-ink-3">
            texto archivado, caracteres {alerta.spans[0].inicio.toLocaleString("es-ES")}–
            {alerta.spans[0].fin.toLocaleString("es-ES")}
            {alerta.spans.length > 1 &&
              ` · y ${alerta.spans.length - 1} fragmento${alerta.spans.length > 2 ? "s" : ""} más`}
          </p>
        </div>
      )}

      {alerta.terminos_perdidos.length > 0 && (
        <div className="mt-3">
          <p className="text-xs leading-relaxed text-ink-2">
            Vocabulario que estaba en la redacción anterior de los preceptos reescritos y no está
            en la nueva:
          </p>
          <ul className="mt-1.5 flex flex-wrap gap-1.5">
            {alerta.terminos_perdidos.map((termino) => (
              <li
                key={termino}
                className="rounded border border-line-2 bg-inset px-1.5 py-0.5 font-mono text-[11px] text-ink-2"
              >
                {termino}
              </li>
            ))}
          </ul>
          {/* La salvedad va pegada a la lista y no en una nota al pie: sin ella, «desaparece
              identidad de género» se lee como que ya no está en la ley. */}
          <p className="mt-1.5 text-[11px] leading-relaxed text-ink-3">
            Es una pista de por dónde leer, no una conclusión: un término puede seguir vigente en
            otro artículo que la reforma no tocó.
          </p>
        </div>
      )}

      {/* La muestra que trae el listado: el primer precepto, ya recortado por la API. Va sin
          clic porque una tarjeta que dice «34 preceptos modificados» y no enseña ninguno pide
          que te fíes, que es justo lo que este proyecto no hace. */}
      {!abierto && alerta.cambios.length > 0 && (
        <CambiosPrecepto cambios={alerta.cambios} />
      )}

      {alerta.preceptos_con_diff > 0 && (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => setAbierto((previo) => !previo)}
            aria-expanded={abierto}
            className="rounded border border-line-2 bg-inset px-2.5 py-1.5 text-xs font-medium text-ink hover:border-line"
          >
            {abierto
              ? "Ocultar el texto completo"
              : `Ver los ${alerta.preceptos_con_diff} preceptos con su redacción anterior`}
          </button>
          {abierto && fallo && (
            <p className="mt-2 text-xs text-ink-2">
              No se ha podido cargar el texto anterior. La alerta y su evidencia siguen arriba.
            </p>
          )}
          {abierto && cambios !== null && <CambiosPrecepto cambios={cambios} />}
        </div>
      )}

      {alerta.normas_vigiladas.length > 0 && (
        <p className="mt-2.5 text-xs leading-relaxed text-ink-2">
          Toca{" "}
          {alerta.normas_vigiladas.map((n, i) => (
            <span key={n.identificador}>
              {i > 0 && ", "}
              <span className="font-medium text-ink">{n.titulo || n.identificador}</span>
            </span>
          ))}
          .
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11px] text-ink-3">
        <span>{alerta.norma.identificador_oficial}</span>
        <span>
          regla {alerta.regla_aplicada ?? "—"}
          {alerta.version_reglas && ` · catálogo ${alerta.version_reglas}`}
        </span>
        {alerta.texto_archivado && (
          <span title={alerta.texto_archivado.sha256}>
            sha256 {alerta.texto_archivado.sha256.slice(0, 12)}… ·{" "}
            {formatearSelloTiempo(alerta.texto_archivado.sello_tiempo)}
          </span>
        )}
        {alerta.norma.url_texto && (
          <a
            href={alerta.norma.url_texto}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto font-sans text-sm text-link hover:text-ink"
          >
            Comprobar en la fuente oficial →
          </a>
        )}
      </div>
    </article>
  );
}
