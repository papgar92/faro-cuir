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
  const meta = META[alerta.clasificacion];
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

      <h3 className="mt-2.5 text-base font-semibold leading-snug text-ink">
        {alerta.norma.titulo}
      </h3>

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

      {alerta.preceptos_con_diff > 0 && (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => setAbierto((previo) => !previo)}
            aria-expanded={abierto}
            className="rounded border border-line-2 bg-inset px-2.5 py-1.5 text-xs font-medium text-ink hover:border-line"
          >
            {abierto ? "Ocultar" : "Ver"} qué cambió · {alerta.preceptos_con_diff} precepto
            {alerta.preceptos_con_diff > 1 ? "s" : ""} con la redacción anterior archivada
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
